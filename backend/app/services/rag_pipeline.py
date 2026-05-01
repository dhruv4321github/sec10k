"""Vector retrieval (pgvector cosine similarity) + OpenAI answer composition."""
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


def retrieve(
    db: Session,
    query: str,
    top_k: int = 5,
    company_filter: Optional[str] = None,
    section_filter: Optional[str] = None,
) -> list[RetrievedChunk]:
    """Retrieve the top-K most similar chunks by cosine distance."""
    qvec = embed_query(query)

    where_clauses = ["embedding IS NOT NULL"]
    params: dict = {"qvec": str(qvec), "limit": top_k}
    if company_filter:
        where_clauses.append("LOWER(company) = LOWER(:company)")
        params["company"] = company_filter
    if section_filter:
        where_clauses.append("LOWER(section_name) = LOWER(:section)")
        params["section"] = section_filter
    where_sql = " AND ".join(where_clauses)

    rows = db.execute(sql_text(f"""
        SELECT id, document_id, company, section_name, text,
               1 - (embedding <=> CAST(:qvec AS vector)) AS score
        FROM chunks
        WHERE {where_sql}
        ORDER BY embedding <=> CAST(:qvec AS vector)
        LIMIT :limit
    """), params).all()

    results = [
        RetrievedChunk(
            chunk_id=row.id, document_id=row.document_id,
            company=row.company, section=row.section_name,
            text=row.text, score=row.score,
        )
        for row in rows
    ]
    log.info("Retrieved top %d chunks by vector similarity", len(results))
    return results


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
