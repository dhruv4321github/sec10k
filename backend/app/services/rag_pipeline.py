"""Hybrid retrieval (pgvector + Postgres FTS, fused via RRF) + OpenAI answer composition."""
from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass
from typing import Optional

from openai import OpenAI
from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_settings
from app.services.document_processor import embed_query

log = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    company: str
    section: str
    text: str
    score: float


_RRF_K = 60


def retrieve(
    db: Session,
    query: str,
    top_k: int = 5,
    candidates: int = 20,
    company_filter: Optional[str] = None,
    section_filter: Optional[str] = None,
) -> list[RetrievedChunk]:
    """Hybrid retrieval: vector + FTS, fused via reciprocal rank fusion."""
    qvec = embed_query(query)

    # vector
    where_clauses = ["embedding IS NOT NULL"]
    params: dict = {"qvec": str(qvec), "limit": candidates}
    if company_filter:
        where_clauses.append("LOWER(company) = LOWER(:company)")
        params["company"] = company_filter
    if section_filter:
        where_clauses.append("LOWER(section_name) = LOWER(:section)")
        params["section"] = section_filter
    where_sql = " AND ".join(where_clauses)

    vec_rows = db.execute(sql_text(f"""
        SELECT id, document_id, company, section_name, text
        FROM chunks
        WHERE {where_sql}
        ORDER BY embedding <=> CAST(:qvec AS vector)
        LIMIT :limit
    """), params).all()

    # lexical
    lex_params: dict = {"q": query, "limit": candidates}
    lex_where = ["tsv @@ plainto_tsquery('english', :q)"]
    if company_filter:
        lex_where.append("LOWER(company) = LOWER(:company)")
        lex_params["company"] = company_filter
    if section_filter:
        lex_where.append("LOWER(section_name) = LOWER(:section)")
        lex_params["section"] = section_filter
    lex_where_sql = " AND ".join(lex_where)

    lex_rows = db.execute(sql_text(f"""
        SELECT id, document_id, company, section_name, text
        FROM chunks
        WHERE {lex_where_sql}
        ORDER BY ts_rank_cd(tsv, plainto_tsquery('english', :q)) DESC
        LIMIT :limit
    """), lex_params).all()

    # RRF fusion
    fused: dict[uuid.UUID, RetrievedChunk] = {}
    for i, row in enumerate(vec_rows):
        cid = row.id
        rrf = 1.0 / (_RRF_K + i + 1)
        if cid not in fused:
            fused[cid] = RetrievedChunk(
                chunk_id=cid, document_id=row.document_id,
                company=row.company, section=row.section_name,
                text=row.text, score=rrf,
            )
        else:
            fused[cid].score += rrf

    for i, row in enumerate(lex_rows):
        cid = row.id
        rrf = 1.0 / (_RRF_K + i + 1)
        if cid not in fused:
            fused[cid] = RetrievedChunk(
                chunk_id=cid, document_id=row.document_id,
                company=row.company, section=row.section_name,
                text=row.text, score=rrf,
            )
        else:
            fused[cid].score += rrf

    ranked = sorted(fused.values(), key=lambda r: r.score, reverse=True)[:top_k]
    log.info("Retrieved %d candidates → top %d", len(fused), len(ranked))
    return ranked


# ──────────────────────────── LLM ────────────────────────────

_SYSTEM_PROMPT = """You are a careful financial-document analyst. You answer questions about SEC 10-K filings using ONLY the numbered context chunks provided. Each chunk has a company and a section.

Rules:
- Use only information present in the context. If the answer is not supported, say so explicitly.
- When you make a claim, cite the chunks that support it inline using [n] notation.
- Prefer concise, structured answers (bullets or short paragraphs) for list-type questions.
- For comparative questions across companies, organize the answer by company.
- Do not invent figures. Quote numbers exactly as they appear in the chunks."""


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=15), reraise=True)
def _chat(messages: list[dict]) -> dict:
    settings = get_settings()
    client = OpenAI(api_key=settings.openai_api_key)
    resp = client.chat.completions.create(
        model=settings.openai_chat_model, messages=messages, temperature=0.1,
    )
    return {"content": resp.choices[0].message.content or "", "model": resp.model}


def _format_context(chunks: list[RetrievedChunk]) -> str:
    parts = []
    for i, c in enumerate(chunks, start=1):
        parts.append(f"[{i}] Company: {c.company} | Section: {c.section}\n{c.text}")
    return "\n\n---\n\n".join(parts)


def answer_question(question: str, chunks: list[RetrievedChunk]) -> dict:
    if not chunks:
        return {
            "answer": "I couldn't find any relevant content in the ingested filings to answer this question.",
            "model": get_settings().openai_chat_model,
            "used_indices": [],
        }
    context = _format_context(chunks)
    user_msg = (
        f"Context chunks:\n\n{context}\n\n"
        f"Question: {question}\n\n"
        "Answer using only the context above, with [n] citations."
    )
    out = _chat([
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ])
    used = sorted({
        int(m.group(1)) for m in re.finditer(r"\[(\d+)\]", out["content"])
        if 1 <= int(m.group(1)) <= len(chunks)
    })
    return {"answer": out["content"], "model": out["model"], "used_indices": used}
