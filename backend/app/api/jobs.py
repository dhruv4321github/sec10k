"""Analysis-job endpoints — the optional/preferred pair from the spec.

  POST /analysis-jobs       Submit an async analysis job
  GET  /analysis-jobs/{id}  Poll job status
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.models.database import Job, get_db
from app.models.schemas import JobCreateRequest, JobOut
from app.services.jobs import run_job

router = APIRouter(prefix="/analysis-jobs", tags=["analysis-jobs"])

_VALID_KINDS = {"ingest", "ask", "compare"}


@router.post("", response_model=JobOut, status_code=202)
def create_job(
    body: JobCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    if body.kind not in _VALID_KINDS:
        raise HTTPException(400, f"Unknown kind. Valid: {sorted(_VALID_KINDS)}")
    if body.kind == "ingest" and "url" not in body.payload:
        raise HTTPException(400, "ingest payload requires 'url'")
    if body.kind == "ask" and "query" not in body.payload:
        raise HTTPException(400, "ask payload requires 'query'")
    if body.kind == "compare":
        if "topic" not in body.payload or "companies" not in body.payload:
            raise HTTPException(400, "compare payload requires 'topic' and 'companies'")
        if not isinstance(body.payload["companies"], list) or len(body.payload["companies"]) < 2:
            raise HTTPException(400, "'companies' must be a list of at least 2 names")

    job = Job(kind=body.kind, payload=body.payload, status="queued")
    db.add(job); db.commit(); db.refresh(job)
    background_tasks.add_task(run_job, job.id)
    return job


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: uuid.UUID, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).one_or_none()
    if not job:
        raise HTTPException(404, "Job not found")
    return job
