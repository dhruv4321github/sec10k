"""FastAPI app entry point."""
import logging
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.models.database import init_db
from app.api import documents, questions, jobs


def configure_logging() -> None:
    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    root = logging.getLogger()
    if root.handlers:
        return
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s :: %(message)s"))
    root.addHandler(h)
    root.setLevel(level)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(
        title="SEC 10-K Analyst API",
        version="0.2.0",
        description="Ingest SEC 10-K filings and answer questions about them with RAG.",
    )

    # CORS — frontend dev server runs on :3000 in another container.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    def _startup() -> None:
        init_db()

    @app.get("/healthz", tags=["health"])
    def healthz():
        return {"status": "ok"}

    # Spec-compliant routers (no /api/ prefix; paths match the assignment exactly):
    #   POST   /documents/ingest                       (required)
    #   GET    /documents                              (required)
    #   GET    /documents/{id}/sections                (required)
    #   POST   /questions/ask                          (required)
    #   POST   /analysis-jobs                          (optional/preferred)
    #   GET    /analysis-jobs/{id}                     (optional/preferred)
    app.include_router(documents.router)
    app.include_router(questions.router)
    app.include_router(jobs.router)
    return app


app = create_app()
