"""Orchestrates the full ingestion pipeline.

Pipeline:
  1. Fetch HTML from SEC
  2. Parse to plaintext
  3. Detect company (or accept user-provided)
  4. Extract sections (Items 1, 1A, 7, 8)
  5. Chunk each section
  6. Embed chunks via OpenAI (batched)
  7. Persist to database
"""
from __future__ import annotations

import logging
import uuid
from typing import Iterable, Sequence, Optional

from openai import OpenAI
from sqlalchemy.orm import Session
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_settings
from app.models.database import Document, Section, Chunk, SessionLocal
from app.services import sec_fetcher, parser, section_extractor, chunker

log = logging.getLogger(__name__)


_BATCH_SIZE = 96


def _client() -> OpenAI:
    return OpenAI(api_key=get_settings().openai_api_key)


@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=1, min=2, max=20), reraise=True)
def _embed_batch(client: OpenAI, model: str, batch: Sequence[str]) -> list[list[float]]:
    resp = client.embeddings.create(model=model, input=list(batch))
    return [d.embedding for d in resp.data]


def embed_texts(texts: Iterable[str]) -> list[list[float]]:
    settings = get_settings()
    client = _client()
    out: list[list[float]] = []
    batch: list[str] = []
    for t in texts:
        batch.append(t)
        if len(batch) >= _BATCH_SIZE:
            out.extend(_embed_batch(client, settings.openai_embedding_model, batch))
            batch = []
    if batch:
        out.extend(_embed_batch(client, settings.openai_embedding_model, batch))
    log.info("Embedded %d chunks with %s", len(out), settings.openai_embedding_model)
    return out


def embed_query(text: str) -> list[float]:
    settings = get_settings()
    client = _client()
    return _embed_batch(client, settings.openai_embedding_model, [text])[0]


# ──────────────────────────── Ingest ────────────────────────────

def create_document(
    db: Session,
    url: str,
    company: Optional[str] = None,
    ticker: Optional[str] = None,
    fiscal_year: Optional[int] = None,
) -> Document:
    """Create the Document row in 'pending' status. Idempotent on (cik, accession)."""
    parsed = sec_fetcher.parse_sec_url(url)

    if parsed["cik"] and parsed["accession"]:
        existing = (
            db.query(Document)
            .filter(Document.cik == parsed["cik"], Document.accession == parsed["accession"])
            .one_or_none()
        )
        if existing:
            log.info("Document already exists: %s", existing.id)
            return existing

    doc = Document(
        company=company or "Unknown",
        ticker=ticker,
        cik=parsed["cik"],
        accession=parsed["accession"],
        fiscal_year=fiscal_year,
        source_url=url,
        status="pending",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def run_ingest(document_id: uuid.UUID) -> None:
    """Background worker: fetch + parse + extract + chunk + embed."""
    settings = get_settings()
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == document_id).one_or_none()
        if not doc:
            log.error("run_ingest: document %s not found", document_id)
            return
        if doc.status == "ready":
            return

        try:
            doc.status = "parsing"
            db.commit()

            html = sec_fetcher.fetch_filing(doc.source_url)
            text = parser.html_to_text(html)
            log.info("Parsed %d chars of plaintext", len(text))

            if doc.company == "Unknown":
                detected = parser.detect_company(html, text)
                if detected:
                    doc.company = detected

            doc.raw_text_chars = len(text)

            sections = section_extractor.extract_sections(text)
            if not sections:
                raise RuntimeError("No sections extracted from filing")

            section_objs: list[Section] = []
            for ord_, sec in enumerate(sections):
                obj = Section(
                    document_id=doc.id,
                    name=sec.name,
                    item_label=sec.item_label,
                    ordinal=ord_,
                    char_start=sec.char_start,
                    char_end=sec.char_end,
                    text=sec.text,
                )
                db.add(obj)
                section_objs.append(obj)
            db.flush()

            doc.status = "embedding"
            db.commit()

            all_pieces: list[tuple[Section, chunker.ChunkPiece]] = []
            for sec_obj, sec in zip(section_objs, sections):
                pieces = chunker.chunk_text(
                    sec.text,
                    target_tokens=settings.chunk_size,
                    overlap_tokens=settings.chunk_overlap,
                    base_offset=sec.char_start,
                )
                for p in pieces:
                    all_pieces.append((sec_obj, p))
            log.info("Created %d chunks across %d sections", len(all_pieces), len(section_objs))

            chunk_texts = [p.text for _, p in all_pieces]
            vectors = embed_texts(chunk_texts)
            assert len(vectors) == len(all_pieces)

            for ord_, ((sec_obj, piece), vec) in enumerate(zip(all_pieces, vectors)):
                ch = Chunk(
                    document_id=doc.id,
                    section_id=sec_obj.id,
                    section_name=sec_obj.name,
                    company=doc.company,
                    ordinal=ord_,
                    char_start=piece.char_start,
                    char_end=piece.char_end,
                    text=piece.text,
                    embedding=vec,
                )
                db.add(ch)
            db.flush()

            doc.chunk_count = len(all_pieces)
            doc.status = "ready"
            doc.error = None
            db.commit()
            log.info("Ingest complete for document %s (%s)", doc.id, doc.company)

        except Exception as e:
            log.exception("Ingest failed for %s: %s", document_id, e)
            doc.status = "error"
            doc.error = str(e)[:2000]
            db.commit()
    finally:
        db.close()
