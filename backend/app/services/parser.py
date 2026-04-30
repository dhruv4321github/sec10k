"""Parse SEC 10-K HTML into clean plaintext."""
from __future__ import annotations

import re
from typing import Optional

from bs4 import BeautifulSoup

_WS_RE = re.compile(r"[ \t\u00A0]+")
_NEWLINES_RE = re.compile(r"\n{3,}")


def html_to_text(html: str) -> str:
    """Convert filing HTML to clean plaintext, preserving paragraph breaks."""
    soup = BeautifulSoup(html, "lxml")

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    for tag in soup.find_all(attrs={"style": re.compile(r"display\s*:\s*none", re.I)}):
        tag.decompose()

    block_tags = {"p", "div", "br", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6",
                  "table", "section", "article", "header", "footer"}
    for tag in soup.find_all(block_tags):
        tag.append("\n")

    text = soup.get_text()
    text = text.replace("\xa0", " ")
    text = _WS_RE.sub(" ", text)
    text = _NEWLINES_RE.sub("\n\n", text)
    text = "\n".join(line.strip() for line in text.splitlines())
    return text.strip()


def detect_company(html: str, text: str) -> Optional[str]:
    candidates = [
        ("Apple Inc.", r"\bApple Inc\."),
        ("Microsoft Corporation", r"\bMicrosoft Corporation\b"),
        ("NVIDIA Corporation", r"\bNVIDIA Corporation\b"),
    ]
    head = "\n".join(text.splitlines()[:60])
    for name, pat in candidates:
        if re.search(pat, head, re.IGNORECASE):
            return name

    for line in text.splitlines()[:30]:
        s = line.strip()
        if 4 <= len(s) <= 80 and s.upper() == s and any(c.isalpha() for c in s):
            return s.title()
    return None
