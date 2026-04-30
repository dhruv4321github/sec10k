"""Async analysis job runner.

Implementation note: this uses FastAPI's BackgroundTasks for simplicity, which
runs jobs in the same process. Production would use Celery + Redis (or RQ /
Arq / Dramatiq) so jobs survive restarts and can scale across workers. The
run_job() interface here is identical to what such a backend would call, so
the migration is a single-file change.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from app.config import get_settings
from app.models.database import Document, Job, SessionLocal
from app.services import document_processor, rag_pipeline

log = logging.getLogger(__name__)


def run_job(job_id: uuid.UUID) -> None:
    """Background worker entry point — looks up the job, runs it, writes result."""
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).one_or_none()
        if not job:
            log.error("run_job: job %s not found", job_id)
            return
        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        db.commit()

        try:
            if job.kind == "ingest":
                doc = document_processor.create_document(
                    db,
                    url=job.payload["url"],
                    company=job.payload.get("company"),
                    ticker=job.payload.get("ticker"),
                    fiscal_year=job.payload.get("fiscal_year"),
                )
                document_processor.run_ingest(doc.id)
                db.refresh(doc)
                job.result = {
                    "document_id": str(doc.id),
                    "company": doc.company,
                    "status": doc.status,
                    "chunk_count": doc.chunk_count,
                }

            elif job.kind == "ask":
                query = job.payload["query"]
                settings = get_settings()
                hits = rag_pipeline.retrieve(
                    db, query=query, top_k=settings.top_k,
                    candidates=settings.retrieval_candidates,
                    company_filter=job.payload.get("company_filter"),
                    section_filter=job.payload.get("section_filter"),
                )
                ans = rag_pipeline.answer_question(query, hits)
                job.result = {
                    "answer": ans["answer"],
                    "model": ans["model"],
                    "sources": [
                        {
                            "chunk_id": str(h.chunk_id),
                            "company": h.company,
                            "section": h.section,
                            "snippet": h.text[:400],
                            "score": round(h.score, 6),
                        }
                        for h in hits
                    ],
                }

            elif job.kind == "compare":
                # Per-company retrieval for an explicit comparison
                topic = job.payload["topic"]
                companies = job.payload["companies"]
                settings = get_settings()
                per_company = {}
                for c in companies:
                    hits = rag_pipeline.retrieve(
                        db, query=topic, top_k=settings.top_k,
                        candidates=settings.retrieval_candidates,
                        company_filter=c,
                    )
                    ans = rag_pipeline.answer_question(
                        f"What does {c} say about: {topic}", hits
                    )
                    per_company[c] = {
                        "answer": ans["answer"],
                        "sources": [
                            {"section": h.section, "snippet": h.text[:300], "score": round(h.score, 6)}
                            for h in hits
                        ],
                    }
                job.result = {"topic": topic, "by_company": per_company}

            else:
                raise ValueError(f"Unknown job kind: {job.kind}")

            job.status = "done"
        except Exception as e:
            log.exception("Job %s failed", job_id)
            job.status = "error"
            job.error = str(e)[:2000]
        finally:
            job.finished_at = datetime.now(timezone.utc)
            db.commit()
    finally:
        db.close()
