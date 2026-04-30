"""Fetch filings from SEC EDGAR.

SEC requires a real User-Agent on every request:
https://www.sec.gov/os/accessing-edgar-data
"""
from __future__ import annotations

import logging
import re
from typing import Optional
from urllib.parse import urlparse

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.config import get_settings

log = logging.getLogger(__name__)


class SECFetchError(RuntimeError):
    pass


_ARCHIVES_PATH_RE = re.compile(
    r"/Archives/edgar/data/(?P<cik>\d+)/(?P<accession>\d+)/", re.IGNORECASE
)


def parse_sec_url(url: str) -> dict[str, Optional[str]]:
    parsed = urlparse(url)
    out = {"cik": None, "accession": None}
    m = _ARCHIVES_PATH_RE.search(parsed.path)
    if m:
        out["cik"] = m.group("cik").lstrip("0") or m.group("cik")
        acc = m.group("accession")
        if len(acc) == 18 and acc.isdigit():
            out["accession"] = f"{acc[:10]}-{acc[10:12]}-{acc[12:]}"
        else:
            out["accession"] = acc
    return out


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((httpx.HTTPError, SECFetchError)),
    reraise=True,
)
def fetch_filing(url: str, timeout: float = 60.0) -> str:
    settings = get_settings()
    headers = {
        "User-Agent": settings.sec_user_agent,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Encoding": "gzip, deflate",
        "Host": "www.sec.gov",
    }
    log.info("Fetching SEC filing: %s", url)
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        r = client.get(url, headers=headers)
        if r.status_code >= 400:
            raise SECFetchError(f"SEC returned {r.status_code} for {url}")
        if not r.text or len(r.text) < 1000:
            raise SECFetchError(f"Suspiciously short body from {url} ({len(r.text)} chars)")
        return r.text
