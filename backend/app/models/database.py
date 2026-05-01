"""SQLAlchemy ORM models.

No Alembic — `init_db()` creates the pgvector extension and all tables on
backend startup. This is fine for a take-home; production would use
versioned migrations.
"""
from __future__ import annotations

import uuid
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    String, Text, Integer, ForeignKey, DateTime, Index, UniqueConstraint, func, text,
    create_engine, JSON,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship, sessionmaker, DeclarativeBase, Session
from pgvector.sqlalchemy import Vector

from app.config import get_settings

log = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


_settings = get_settings()
engine = create_engine(_settings.database_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Session:
    """FastAPI dependency."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


# ──────────────────────────── Models ────────────────────────────

class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    company: Mapped[str] = mapped_column(String(128), nullable=False)
    ticker: Mapped[Optional[str]] = mapped_column(String(16))
    cik: Mapped[Optional[str]] = mapped_column(String(20))
    accession: Mapped[Optional[str]] = mapped_column(String(32))
    fiscal_year: Mapped[Optional[int]] = mapped_column(Integer)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)

    # pending → parsing → embedding → ready (or → error)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    error: Mapped[Optional[str]] = mapped_column(Text)

    raw_text_chars: Mapped[int] = mapped_column(Integer, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    sections: Mapped[list["Section"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("cik", "accession", name="uq_documents_cik_accession"),
    )


class Section(Base):
    __tablename__ = "sections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    item_label: Mapped[Optional[str]] = mapped_column(String(16))
    ordinal: Mapped[int] = mapped_column(Integer, default=0)
    char_start: Mapped[int] = mapped_column(Integer, default=0)
    char_end: Mapped[int] = mapped_column(Integer, default=0)
    text: Mapped[str] = mapped_column(Text, nullable=False)

    document: Mapped[Document] = relationship(back_populates="sections")

    __table_args__ = (
        Index("ix_sections_document", "document_id"),
        UniqueConstraint("document_id", "name", name="uq_sections_doc_name"),
    )


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    section_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sections.id", ondelete="CASCADE")
    )
    section_name: Mapped[str] = mapped_column(String(64), nullable=False)
    company: Mapped[str] = mapped_column(String(128), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, default=0)
    char_start: Mapped[int] = mapped_column(Integer, default=0)
    char_end: Mapped[int] = mapped_column(Integer, default=0)
    text: Mapped[str] = mapped_column(Text, nullable=False)

    embedding: Mapped[Optional[list[float]]] = mapped_column(Vector(_settings.embedding_dim))

    document: Mapped[Document] = relationship(back_populates="chunks")

    __table_args__ = (
        Index("ix_chunks_document", "document_id"),
        Index("ix_chunks_section", "section_id"),
        Index("ix_chunks_company", "company"),
    )


class Job(Base):
    """Async analysis job — backs POST/GET /analysis-jobs."""
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)  # ingest | ask | compare
    status: Mapped[str] = mapped_column(String(16), default="queued")  # queued|running|done|error
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[Optional[dict]] = mapped_column(JSON)
    error: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


# ──────────────────────────── Init ────────────────────────────

def init_db() -> None:
    """Create the pgvector extension, all tables, and the ivfflat vector index."""
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(engine)
    # ivfflat index has to be created manually because SQLAlchemy doesn't model it.
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_chunks_embedding
            ON chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)
        """))
    log.info("Database initialized")
