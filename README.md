# 📑 SEC 10-K Filing Analyst

A FastAPI + React application that ingests SEC 10-K annual reports, extracts their major sections, and answers questions about them with retrieval-augmented generation.

Built for the FairPlay AI Engineer take-home.

![Python](https://img.shields.io/badge/Python-3.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)
![React](https://img.shields.io/badge/React-18-blue)
![Postgres](https://img.shields.io/badge/Postgres-pgvector-purple)
![OpenAI](https://img.shields.io/badge/OpenAI-API-black)

---

## What it does

1. **Ingest** a 10-K from a SEC EDGAR URL — fetches, parses, chunks, embeds, indexes.
2. **Extract** the four major Items: Business (1), Risk Factors (1A), Management's Discussion and Analysis (7), Financial Statements (8).
3. **Ask** questions over the indexed filings — answers are grounded in retrieved chunks and include citations (company + section + snippet).

---

## Quick start

### 1. Configure
```bash
cp .env.example .env
# edit .env: set OPENAI_API_KEY=sk-...
# also set SEC_USER_AGENT="Your Name your-email@example.com"
# (SEC requires a real contact in the User-Agent header.)
```

### 2. Run
```bash
docker compose up --build
```

Three services start:
- **Postgres + pgvector** on `:5432`
- **FastAPI backend** on `:8000`
- **React frontend** on `:3000`

### 3. Open the app
- **Frontend:** http://localhost:3000
- **API docs (Swagger):** http://localhost:8000/docs

### 4. Try it
1. Click **+ Add** on any of the three filing cards (AAPL / MSFT / NVDA).
2. Watch the card show a yellow "Parsing… this may take a few seconds" banner with a spinner. Wait for it to reach **Ready**.
3. Switch to **Sections** to read the extracted Items.
4. Switch to **Ask**, click an example question, and watch the answer come back with clickable `[1]` `[2]` citation chips that scroll to the supporting evidence below.
5. Conversations persist to localStorage — use the left sidebar to switch between past conversations or start new ones.

---

## API Reference

The endpoint paths match the assignment spec exactly — no `/api/` prefix.

### Required (all four implemented)

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/documents/ingest` | Ingest a new SEC 10-K filing |
| `GET` | `/documents` | List all ingested documents |
| `GET` | `/documents/{id}/sections` | Get extracted sections (with full text) for a document |
| `POST` | `/questions/ask` | Submit a question for RAG-based Q&A |

### Optional / Preferred (both implemented)

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/analysis-jobs` | Submit an async analysis job |
| `GET` | `/analysis-jobs/{id}` | Poll the status of an analysis job |

The job runner supports three kinds:
- `ingest` — payload `{url, company?, ticker?, fiscal_year?}`
- `ask` — payload `{query, company_filter?, section_filter?}`
- `compare` — payload `{topic, companies: [str, str, ...]}` — runs per-company retrieval and produces side-by-side answers.

### Convenience extras

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/documents/{id}` | Get one document |
| `GET` | `/documents/{id}/sections/{name}` | Get a single section by name |
| `DELETE` | `/documents/{id}` | Delete a document and its chunks |
| `GET` | `/healthz` | Liveness probe |

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    React Frontend (:3000)                 │
│  Filings tab · Sections tab · Ask tab (with chat history) │
└─────────────────────────┬────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────┐
│                  FastAPI Backend (:8000)                  │
│  /documents   /questions   /analysis-jobs                 │
│        │           │              │                       │
│        ▼           ▼              ▼                       │
│  Ingestion    RAG pipeline   Job runner                   │
│  (fetch +     (vector        (BackgroundTasks)            │
│   parse +      similarity)                                │
│   chunk +                                                 │
│   embed)                                                  │
└─────────────────────────┬────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────┐
│  Postgres + pgvector (:5432)                              │
│  documents · sections · chunks · jobs                     │
│  (chunks have an embedding column for vector search)      │
└──────────────────────────────────────────────────────────┘
```

## Section extraction

The 10-K layout includes every Item header twice: once in the Table of Contents (with newlines from table-row flattening, plus a page number), and once in the body (item label + canonical title on a single line, immediately followed by section content). I exploit that difference.

For every canonical Item from the standard 10-K layout, the extractor builds a regex that matches `Item N. <full canonical title>` separated by **inline whitespace only** (`[ \t]+`). The TOC's intervening newlines fail this constraint, so only the body match fires. The regex also tolerates curly apostrophes (U+2019) which Apple's filing actually uses.

Sections are then sliced from each Item's body anchor to the start of the next item's anchor.

## Chunking

Section-aware recursive chunking: paragraph → sentence → fixed character window. Target **800 tokens** per chunk, **100 token** overlap between successive chunks. Token counting uses tiktoken (`cl100k_base`, matches OpenAI's models). Each chunk carries `(document_id, section, ordinal, char_start, char_end)` for precise citations.

## Retrieval

**Vector similarity retrieval.** For each question:

1. Embed the query (OpenAI `text-embedding-3-small`, 1536d).
2. **Vector search**: top-K by cosine distance via pgvector `<=>`.
3. Top-K go to the LLM with a strict prompt requiring `[n]` citations.

**Per-company retrieval for comparisons.** When no company filter is set and multiple filings are ingested, the server retrieves top-K from *each* company's chunks separately and concatenates. This is what makes "Compare risk factors between Apple and NVIDIA" work — without it, vector similarity tends to pile all retrieved chunks into one company.

## Tradeoffs

| Decision | Why | What I gave up |
|---|---|---|
| Single Postgres for metadata + vectors | Simple ops, transactional ingestion | Pure vector DBs scale further at 100M+ chunks |
| Section regex with full canonical titles | Reliable, predictable, debuggable | Won't generalize to non-standard filings |
| `text-embedding-3-small` | Cheap, fast | `text-embedding-3-large` slightly better recall |
| `gpt-4o-mini` for synthesis | Cheap, fast, good enough | `gpt-4o` writes cleaner comparisons |
| `BackgroundTasks` for async jobs | Zero infra | Doesn't survive restarts; no retries |
| Vector-only retrieval, no reranker | Simple, fast | Hybrid (FTS + RRF) or cross-encoder reranker could improve recall |
| BeautifulSoup HTML → text | Works on actual SEC filings | iXBRL-aware parsing would extract structured financials |
| Per-company retrieval for compare | Each company is represented in context | More embedding/DB work per query |
| Chat history in localStorage | No server state needed; survives navigation | Bound to one browser; no cross-device sync |

## Assumptions

- Filings come from `sec.gov/Archives/edgar/...` in HTML form. The parser handles Apple's, Microsoft's, and NVIDIA's 2025 layouts.
- A document is identified by `(CIK, accession)` derived from the URL — re-ingesting is idempotent.
- "Section" means Items 1, 1A, 7, 8. Sub-items aren't split out.
- Item titles match the canonical 10-K layout. Some filings may use slight variations in format; the title regex tolerates whitespace and apostrophe variants but assumes the words are correct.

## Limitations

- Tables and footnotes inside Item 8 are flattened to text. Numeric Q&A on cross-tabulated figures is unreliable; production would need iXBRL parsing.
- No hybrid retrieval or reranker — pure vector similarity.
- No auth, no rate limiting, no per-tenant isolation.
- No streaming of LLM output.
- Chat history is per-browser (localStorage).

## How I'd improve it for production

1. **Real job queue** (Celery + Redis) — `BackgroundTasks` doesn't survive restarts and won't scale across workers. The `run_job()` interface here is identical to what Celery would call, so the migration is one file.
2. **Hybrid retrieval + reranker** — add FTS with RRF fusion and a cross-encoder reranker before the LLM.
3. **Eval harness** with a fixed Q&A set + LLM-as-judge for faithfulness and citation precision. The example questions in the spec are a starting point.
4. **Streaming** answers via SSE so the UI gets tokens as they generate.
5. **iXBRL-aware parsing** — modern filings carry machine-readable financial facts; right now we throw them away by going through HTML text.
6. **Server-side chat history** keyed by user, with cross-device sync, replacing localStorage.
7. **Auth + multi-tenancy**, embedding cache (by content hash), response cache.
8. **Eval-driven chunking** — try semantic chunking (split on embedding-distance peaks) and per-section strategies once the eval harness exists.

---

## Project structure

```
sec10k/
├── README.md
├── docker-compose.yml          # Three services: db, backend, frontend
├── .env.example
│
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py             # FastAPI entry, CORS, routers
│       ├── config.py           # Settings via pydantic-settings
│       ├── models/
│       │   ├── database.py     # SQLAlchemy ORM + init_db()
│       │   └── schemas.py      # Pydantic request/response models
│       ├── api/
│       │   ├── documents.py    # /documents/* (required)
│       │   ├── questions.py    # /questions/ask (required)
│       │   └── jobs.py         # /analysis-jobs/* (optional)
│       └── services/
│           ├── sec_fetcher.py
│           ├── parser.py
│           ├── section_extractor.py  # Full-title boundary matching
│           ├── chunker.py
│           ├── document_processor.py
│           ├── rag_pipeline.py       # Hybrid retrieval + LLM
│           └── jobs.py               # Async job runner
│
└── frontend/
    ├── Dockerfile
    ├── package.json            # CRA, axios, react
    ├── public/index.html
    └── src/
        ├── index.js
        ├── App.jsx             # Tabs + 4-second status polling
        ├── components/
        │   ├── DocumentUpload.jsx  # 3 quick-add presets, status pills
        │   ├── SectionsView.jsx    # Browse extracted Items
        │   └── ChatInterface.jsx   # Persisted chat history
        ├── services/
        │   └── api.js          # Axios wrapper
        └── styles/
            └── App.css
```

---

## Sample requests and responses

See `docs/SAMPLES.md` for full examples. Quick taste:

```bash
# Ingest a filing (returns 202 immediately, runs in background)
curl -X POST http://localhost:8000/documents/ingest \
  -H "Content-Type: application/json" \
  -d '{"url":"https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/aapl-20250927.htm",
       "company":"Apple Inc.","ticker":"AAPL","fiscal_year":2025}'

# Ask a question
curl -X POST http://localhost:8000/questions/ask \
  -H "Content-Type: application/json" \
  -d '{"query":"What are the top business risks?","company_filter":"Apple Inc."}'

# Compare across companies (no company_filter → server does per-company retrieval)
curl -X POST http://localhost:8000/questions/ask \
  -H "Content-Type: application/json" \
  -d '{"query":"Compare risk factors between Apple and NVIDIA"}'
```

---

## What worked well, what I'd improve next, what I'd do differently for production

**What worked well**
- **Single Postgres for everything.** Vectors, FTS, metadata, jobs — all transactional, all in one connection. Right call at this scale.
- **Vector similarity retrieval with pgvector.** Clean, simple, and good enough for most queries.
- **Full-title section extraction.** The pattern of `Item N. <canonical title>` separated by *inline* whitespace is a clean way to distinguish body anchors from TOC entries. Once I saw that the TOC has newlines between the item number and its title (because of how my HTML→text flattening handles tables), the heuristic basically wrote itself.
- **Per-company retrieval for comparisons.** A small change with a big effect on the example "compare risk factors" question.

**What I'd improve next**
- **Hybrid retrieval + reranker.** Add FTS with RRF fusion, then a cross-encoder reranker on top. Single highest-leverage quality win.
- **Eval harness.** Right now I'm eyeballing answer quality. With ~30 reference Q&A pairs and an LLM-as-judge for faithfulness, every "improvement" stops being vibes and becomes measurable.
- **Table/iXBRL parsing in Item 8.** Item 8 is a wall of text right now; it should be structured financial data.

**What I'd do differently for a production-scale system**
- **Start with the eval harness.** Without it, every improvement is vibes.
- **Replace `BackgroundTasks` with Celery from day one.** Migration is annoying once endpoints have real callers.
- **Treat ingestion as a versioned pipeline.** Each filing has an `ingest_version`; when chunking or embedding changes, you re-process incrementally rather than wiping the DB.
- **Streaming answers**, **per-tenant cost controls**, **response caching with content hashes**, **embedding cache.**
- **Server-side chat history**, with proper auth.
