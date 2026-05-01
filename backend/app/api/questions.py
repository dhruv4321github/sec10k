"""RAG question-answering endpoint.

  POST /questions/ask  Submit a question for RAG-based Q&A

The interesting choice here is how we handle "compare X between two companies"
questions. Pure top-k retrieval over all chunks tends to lopsidedly favor
whichever company's wording matches the query best, so the LLM never sees
the other company's evidence and the comparison fails.

Fix: when no company_filter is supplied, we retrieve per-company (top-k from
each ready company's chunks) and concatenate. The LLM sees evidence from
every company and can compare cleanly.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.database import Document, get_db
from app.models.schemas import AskRequest, AskResponse, Source
from app.services import rag_pipeline

router = APIRouter(prefix="/questions", tags=["questions"])


@router.post("/ask", response_model=AskResponse)
def ask(body: AskRequest, db: Session = Depends(get_db)):
    """Answer a question using only retrieved context from ingested filings."""
    settings = get_settings()
    top_k = settings.top_k

    if body.company_filter:
        hits = rag_pipeline.retrieve(
            db, query=body.query, top_k=top_k,
            company_filter=body.company_filter,
            section_filter=body.section_filter,
        )
    else:
        # Multi-company question — retrieve per-company so every ingested
        # company is represented in the context. This is what makes
        # "Compare risk factors between Apple and NVIDIA" work.
        ready_companies = [
            r[0] for r in
            db.query(Document.company)
              .filter(Document.status == "ready")
              .distinct()
              .all()
        ]
        if not ready_companies:
            raise HTTPException(404, "No ready filings available — ingest one first.")

        if len(ready_companies) == 1:
            hits = rag_pipeline.retrieve(
                db, query=body.query, top_k=top_k,
                company_filter=ready_companies[0],
                section_filter=body.section_filter,
            )
        else:
            per_company_k = max(3, top_k)
            all_hits = []
            for company in ready_companies:
                ch = rag_pipeline.retrieve(
                    db, query=body.query, top_k=per_company_k,
                    company_filter=company,
                    section_filter=body.section_filter,
                )
                all_hits.extend(ch)
            all_hits.sort(key=lambda h: h.score, reverse=True)
            hits = all_hits

    if not hits:
        raise HTTPException(
            404,
            "No relevant content found — ingest at least one filing or relax filters.",
        )

    result = rag_pipeline.answer_question(body.query, hits)
    return AskResponse(
        answer=result["answer"],
        sources=[
            Source(
                chunk_id=h.chunk_id,
                company=h.company,
                section=h.section,
                snippet=h.text[:500],
                score=round(h.score, 6),
            )
            for h in hits
        ],
        model_used=result["model"],
        retrieval={
            "top_k": top_k,
            "company_filter": body.company_filter,
            "section_filter": body.section_filter,
            "mode": "single" if body.company_filter else "per_company",
        },
    )
