"""Pydantic request/response models for the API."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict, HttpUrl


# ─────── Documents ───────

class IngestRequest(BaseModel):
    url: HttpUrl
    company: Optional[str] = None
    ticker: Optional[str] = None
    fiscal_year: Optional[int] = None


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company: str
    ticker: Optional[str]
    cik: Optional[str]
    accession: Optional[str]
    fiscal_year: Optional[int]
    source_url: str
    status: str
    error: Optional[str]
    raw_text_chars: int
    chunk_count: int
    created_at: datetime
    updated_at: datetime


# ─────── Sections ───────

class SectionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    item_label: Optional[str]
    char_count: int
    text: str


class SectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    name: str
    item_label: Optional[str]
    text: str


class SectionsListOut(BaseModel):
    document_id: uuid.UUID
    company: str
    sections: list[SectionSummary]


# ─────── Q&A ───────

class AskRequest(BaseModel):
    """Request body for POST /questions/ask.

    `top_k` is intentionally NOT exposed — the spec doesn't mention it, and
    making it a knob in the UI invites misuse. The server uses a sensible
    default from settings.
    """
    query: str = Field(..., min_length=3, description="The question to ask")
    company_filter: Optional[str] = Field(
        None,
        description="Restrict retrieval to one company. If omitted, the server "
                    "retrieves per-company so multi-company comparisons work.",
    )
    section_filter: Optional[str] = Field(
        None,
        description="Restrict retrieval to one section name (e.g. 'Risk Factors').",
    )


class Source(BaseModel):
    chunk_id: uuid.UUID
    company: str
    section: str
    snippet: str
    score: float


class AskResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    answer: str
    sources: list[Source]
    model_used: str
    retrieval: dict


# ─────── Analysis Jobs (optional/preferred) ───────

class JobCreateRequest(BaseModel):
    """Submit an async analysis job.

    Supported kinds:
      - 'ingest' : payload {url, company?, ticker?, fiscal_year?}
      - 'ask'    : payload {query, company_filter?, section_filter?}
      - 'compare': payload {topic, companies: [str, str, ...]}
    """
    kind: str = Field(..., description="ingest | ask | compare")
    payload: dict = Field(default_factory=dict)


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: str
    status: str
    payload: dict
    result: Optional[dict]
    error: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
