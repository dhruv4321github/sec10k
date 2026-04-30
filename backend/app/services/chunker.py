"""Section-aware recursive chunker.

Splits text into target-token chunks with overlap. Prefers paragraph boundaries,
falls back to sentences, then fixed-size character windows.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

log = logging.getLogger(__name__)

# tiktoken needs to fetch its BPE files on first use. If that fails (e.g.
# offline build), fall back to a 4-char-per-token heuristic that's good
# enough for chunk sizing.
try:
    import tiktoken
    _ENC = tiktoken.get_encoding("cl100k_base")

    def count_tokens(text: str) -> int:
        return len(_ENC.encode(text, disallowed_special=()))
except Exception as _e:  # pragma: no cover
    log.warning("tiktoken unavailable (%s); using char/4 heuristic for token counts", _e)

    def count_tokens(text: str) -> int:
        return max(1, len(text) // 4)


@dataclass
class ChunkPiece:
    text: str
    char_start: int
    char_end: int
    token_count: int


_PARA_RE = re.compile(r"\n\s*\n")
_SENT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z(])")


def _split_paragraphs(text: str) -> list[tuple[int, int, str]]:
    spans = []
    cursor = 0
    for m in _PARA_RE.finditer(text):
        end = m.start()
        if end > cursor:
            spans.append((cursor, end, text[cursor:end]))
        cursor = m.end()
    if cursor < len(text):
        spans.append((cursor, len(text), text[cursor:]))
    return [s for s in spans if s[2].strip()]


def _split_sentences(text: str, base_offset: int) -> list[tuple[int, int, str]]:
    spans = []
    cursor = 0
    for m in _SENT_RE.finditer(text):
        end = m.start()
        if end > cursor:
            spans.append((base_offset + cursor, base_offset + end, text[cursor:end]))
        cursor = m.end()
    if cursor < len(text):
        spans.append((base_offset + cursor, base_offset + len(text), text[cursor:]))
    return [s for s in spans if s[2].strip()]


def _hard_split(text: str, base_offset: int, target_tokens: int) -> list[tuple[int, int, str]]:
    target_chars = target_tokens * 4
    out = []
    pos = 0
    while pos < len(text):
        end = min(len(text), pos + target_chars)
        out.append((base_offset + pos, base_offset + end, text[pos:end]))
        pos = end
    return out


def chunk_text(
    text: str,
    target_tokens: int = 800,
    overlap_tokens: int = 100,
    base_offset: int = 0,
) -> list[ChunkPiece]:
    if not text.strip():
        return []

    paragraphs = _split_paragraphs(text)
    units: list[tuple[int, int, str, int]] = []
    for s, e, t in paragraphs:
        tk = count_tokens(t)
        if tk <= target_tokens:
            units.append((base_offset + s, base_offset + e, t, tk))
        else:
            for ss, se, st in _split_sentences(t, base_offset + s):
                stk = count_tokens(st)
                if stk <= target_tokens:
                    units.append((ss, se, st, stk))
                else:
                    for ps, pe, pt in _hard_split(st, ss, target_tokens):
                        units.append((ps, pe, pt, count_tokens(pt)))

    chunks: list[ChunkPiece] = []
    i = 0
    while i < len(units):
        cur_text = ""
        cur_start = units[i][0]
        cur_end = units[i][1]
        cur_tokens = 0
        j = i
        while j < len(units) and cur_tokens + units[j][3] <= target_tokens:
            sep = "\n\n" if cur_text else ""
            cur_text += sep + units[j][2]
            cur_end = units[j][1]
            cur_tokens += units[j][3]
            j += 1
        if cur_tokens == 0:
            cur_text = units[i][2]
            cur_end = units[i][1]
            cur_tokens = units[i][3]
            j = i + 1

        chunks.append(ChunkPiece(
            text=cur_text.strip(),
            char_start=cur_start, char_end=cur_end,
            token_count=cur_tokens,
        ))
        if j >= len(units):
            break

        if overlap_tokens <= 0:
            i = j
        else:
            shed = 0
            k = j - 1
            while k > i and shed < overlap_tokens:
                shed += units[k][3]
                k -= 1
            i = max(i + 1, k + 1)

    return chunks
