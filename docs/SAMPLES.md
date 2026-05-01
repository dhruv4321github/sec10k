# Sample API requests and responses

All examples assume the backend is running at `http://localhost:8000`.

---

## 1. Ingest a 10-K — `POST /documents/ingest`

```bash
curl -X POST http://localhost:8000/documents/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/aapl-20250927.htm",
    "company": "Apple Inc.",
    "ticker": "AAPL",
    "fiscal_year": 2025
  }'
```

Response (HTTP 202 Accepted) — returns immediately; ingestion runs in the background.
```json
{
  "id": "8e6c5a2b-3c0a-4f1e-9c8d-1234567890ab",
  "company": "Apple Inc.",
  "ticker": "AAPL",
  "cik": "320193",
  "accession": "0000320193-25-000079",
  "fiscal_year": 2025,
  "source_url": "https://www.sec.gov/...",
  "status": "pending",
  "error": null,
  "raw_text_chars": 0,
  "chunk_count": 0,
  "created_at": "2026-04-30T...",
  "updated_at": "2026-04-30T..."
}
```

Poll `GET /documents/{id}` until `status` reaches `"ready"`.

---

## 2. List documents — `GET /documents`

```bash
curl http://localhost:8000/documents
```

```json
[
  {
    "id": "8e6c...", "company": "Apple Inc.", "ticker": "AAPL",
    "status": "ready", "chunk_count": 79, "fiscal_year": 2025, "...": "..."
  },
  {
    "id": "f1a2...", "company": "NVIDIA Corporation", "ticker": "NVDA",
    "status": "ready", "chunk_count": 64, "fiscal_year": 2025, "...": "..."
  }
]
```

---

## 3. List sections of a document — `GET /documents/{id}/sections`

```bash
curl http://localhost:8000/documents/8e6c.../sections
```

```json
{
  "document_id": "8e6c...",
  "company": "Apple Inc.",
  "sections": [
    { "id": "...", "name": "Business", "item_label": "Item 1", "char_count": 16009 },
    { "id": "...", "name": "Risk Factors", "item_label": "Item 1A", "char_count": 68057 },
    { "id": "...", "name": "Management's Discussion and Analysis", "item_label": "Item 7", "char_count": 17891 },
    { "id": "...", "name": "Financial Statements", "item_label": "Item 8", "char_count": 60183 }
  ]
}
```

---

## 4. Ask a question — `POST /questions/ask`

### Single-company question
```bash
curl -X POST http://localhost:8000/questions/ask \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the top business risks described by Apple?",
    "company_filter": "Apple Inc.",
    "section_filter": "Risk Factors"
  }'
```

### Multi-company comparison (no company_filter → server does per-company retrieval)
```bash
curl -X POST http://localhost:8000/questions/ask \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Compare risk factors between Apple and NVIDIA"
  }'
```

Response shape:
```json
{
  "answer": "Apple [1][3] and NVIDIA [4][6] each describe...\n\n- Apple emphasizes...\n- NVIDIA emphasizes...",
  "sources": [
    {
      "chunk_id": "uuid",
      "company": "Apple Inc.",
      "section": "Risk Factors",
      "snippet": "The Company's business is subject to risks including macroeconomic conditions...",
      "score": 0.0331
    },
    {
      "chunk_id": "uuid",
      "company": "NVIDIA Corporation",
      "section": "Risk Factors",
      "snippet": "Our business depends on global supply chains and concentrated suppliers...",
      "score": 0.0298
    }
    ...
  ],
  "model_used": "gpt-4o-mini-2024-07-18",
  "retrieval": {
    "top_k": 5,
    "company_filter": null,
    "section_filter": null,
    "mode": "per_company"
  }
}
```

The `mode` field shows whether the server did standard vector retrieval (`single`) or per-company retrieval (`per_company`).

---

## 5. Submit an async analysis job — `POST /analysis-jobs`

### Ingest as a job
```bash
curl -X POST http://localhost:8000/analysis-jobs \
  -H "Content-Type: application/json" \
  -d '{
    "kind": "ingest",
    "payload": {
      "url": "https://www.sec.gov/Archives/edgar/data/789019/000095017025100235/msft-20250630.htm",
      "company": "Microsoft Corporation",
      "ticker": "MSFT",
      "fiscal_year": 2025
    }
  }'
```

### Compare topic across companies
```bash
curl -X POST http://localhost:8000/analysis-jobs \
  -H "Content-Type: application/json" \
  -d '{
    "kind": "compare",
    "payload": {
      "topic": "supply chain concentration risk",
      "companies": ["Apple Inc.", "NVIDIA Corporation"]
    }
  }'
```

Response (HTTP 202) returns the job ID and `status: "queued"`. Poll `GET /analysis-jobs/{id}`.

---

## 6. Poll a job — `GET /analysis-jobs/{id}`

```bash
curl http://localhost:8000/analysis-jobs/a1b2c3...
```

```json
{
  "id": "a1b2c3...",
  "kind": "compare",
  "status": "done",
  "payload": {"topic": "...", "companies": ["Apple Inc.", "NVIDIA Corporation"]},
  "result": {
    "topic": "supply chain concentration risk",
    "by_company": {
      "Apple Inc.": {
        "answer": "Apple's filing emphasizes...",
        "sources": [{ "section": "Risk Factors", "snippet": "...", "score": 0.0331 }]
      },
      "NVIDIA Corporation": {
        "answer": "NVIDIA describes...",
        "sources": [{ "section": "Risk Factors", "snippet": "...", "score": 0.0298 }]
      }
    }
  },
  "error": null,
  "created_at": "...",
  "started_at": "...",
  "finished_at": "..."
}
```

---

## Mapping the spec's example questions to API calls

| Spec example | API call |
|---|---|
| What are the top business risks described by the company? | `POST /questions/ask` with `company_filter` and `section_filter: "Risk Factors"` |
| What does the company say about revenue growth or business performance? | `POST /questions/ask` with `section_filter: "Management's Discussion and Analysis"` |
| What are the company's main business segments or operating priorities? | `POST /questions/ask` with `section_filter: "Business"` |
| Compare risk factors between two companies. | `POST /questions/ask` with NO `company_filter` (server does per-company retrieval), or `POST /analysis-jobs` with `kind: "compare"` |
| What themes appear repeatedly in management discussion? | `POST /questions/ask` with `section_filter: "Management's Discussion and Analysis"`, no company filter |
