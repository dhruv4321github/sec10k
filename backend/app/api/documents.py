"""Document endpoints — paths match the assignment spec exactly.

  POST   /documents/ingest                       Ingest a 10-K
  GET    /documents                              List ingested documents
  GET    /documents/{id}                         Get one document
  GET    /documents/{id}/sections                List extracted sections
  GET    /documents/{id}/sections/{section_name} Get one section's full text
  DELETE /documents/{id}                         Delete a document
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.models.database import Document, Section, get_db
from app.models.schemas import (
    DocumentOut, IngestRequest, SectionOut, SectionSummary, SectionsListOut,
)
from app.services import document_processor

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/ingest", response_model=DocumentOut, status_code=status.HTTP_202_ACCEPTED)
def ingest_document(
    body: IngestRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Ingest a 10-K from a SEC EDGAR HTML URL.

    Returns 202 immediately with a 'pending' document; the actual fetch + parse
    + embed runs in a background task. Idempotent on (CIK, accession).
    """
    doc = document_processor.create_document(
        db,
        url=str(body.url),
        company=body.company,
        ticker=body.ticker,
        fiscal_year=body.fiscal_year,
    )
    if doc.status != "ready":
        background_tasks.add_task(document_processor.run_ingest, doc.id)
    return doc


@router.get("", response_model=list[DocumentOut])
def list_documents(db: Session = Depends(get_db)):
    """List every ingested document, newest first."""
    return db.query(Document).order_by(Document.created_at.desc()).all()


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(document_id: uuid.UUID, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id).one_or_none()
    if not doc:
        raise HTTPException(404, "Document not found")
    return doc


@router.delete("/{document_id}", status_code=204)
def delete_document(document_id: uuid.UUID, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id).one_or_none()
    if not doc:
        raise HTTPException(404, "Document not found")
    db.delete(doc)
    db.commit()


@router.get("/{document_id}/sections", response_model=SectionsListOut)
def list_sections(document_id: uuid.UUID, db: Session = Depends(get_db)):
    """Get the four extracted sections (Items 1, 1A, 7, 8) for a document."""
    doc = db.query(Document).filter(Document.id == document_id).one_or_none()
    if not doc:
        raise HTTPException(404, "Document not found")
    sections = (
        db.query(Section)
        .filter(Section.document_id == document_id)
        .order_by(Section.ordinal)
        .all()
    )
    return SectionsListOut(
        document_id=doc.id, company=doc.company,
        sections=[
            SectionSummary(id=s.id, name=s.name, item_label=s.item_label, char_count=len(s.text), text=s.text)
            for s in sections
        ],
    )


@router.get("/{document_id}/sections/{section_name}", response_model=SectionOut)
def get_section(document_id: uuid.UUID, section_name: str, db: Session = Depends(get_db)):
    sec = (
        db.query(Section)
        .filter(Section.document_id == document_id)
        .filter(Section.name.ilike(section_name))
        .one_or_none()
    )
    if not sec:
        raise HTTPException(404, "Section not found")
    return sec
