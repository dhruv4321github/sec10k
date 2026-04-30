"""Extract major 10-K Item sections from cleaned plaintext.

Strategy
--------
A 10-K's Item headers always appear twice:
  - In the Table of Contents, formatted as e.g. "Item 1.\\nBusiness\\n5\\n"
    (with newlines from table-row flattening, plus a page number).
  - In the body, formatted as "Item 1. Business" all on one line, immediately
    followed by section content.

We exploit that difference. For every canonical Item, we build a regex that
matches the item label + the FULL canonical title separated by *inline*
whitespace only ([ \\t]+). The TOC's intervening newlines fail this constraint,
so only the body match fires.

We then sort all body anchors by position and slice each target section
from its anchor to the next item's anchor.

This handles the bugs in the original implementation where:
  - "Item 1A" inside an Item 7 cross-reference ("Item 1A of this Form 10-K
    under the heading 'Risk Factors'") would be picked up as the start of
    Risk Factors.
  - Item 8's body would be a single Item 9A sentence because of weak anchors.
  - Item 1 would bleed past its real boundary because next-item detection
    was fuzzy.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

log = logging.getLogger(__name__)


# Canonical Item titles for the standard 10-K layout. Order matters — these
# are listed in document order. Apostrophes are written as straight ASCII;
# the title pattern broadens them to a class that also matches U+2019 etc.
ITEM_DEFS: list[tuple[str, str]] = [
    ('1',  'Business'),
    ('1A', 'Risk Factors'),
    ('1B', 'Unresolved Staff Comments'),
    ('1C', 'Cybersecurity'),
    ('2',  'Properties'),
    ('3',  'Legal Proceedings'),
    ('4',  'Mine Safety Disclosures'),
    ('5',  "Market for Registrant's Common Equity, Related Stockholder Matters and Issuer Purchases of Equity Securities"),
    ('6',  'Reserved'),  # body shows "Item 6. [Reserved]"
    ('7',  "Management's Discussion and Analysis of Financial Condition and Results of Operations"),
    ('7A', 'Quantitative and Qualitative Disclosures About Market Risk'),
    ('8',  'Financial Statements and Supplementary Data'),
    ('9',  'Changes in and Disagreements with Accountants on Accounting and Financial Disclosure'),
    ('9A', 'Controls and Procedures'),
    ('9B', 'Other Information'),
    ('9C', 'Disclosure Regarding Foreign Jurisdictions that Prevent Inspections'),
    ('10', 'Directors, Executive Officers and Corporate Governance'),
    ('11', 'Executive Compensation'),
    ('12', 'Security Ownership of Certain Beneficial Owners and Management and Related Stockholder Matters'),
    ('13', 'Certain Relationships and Related Transactions, and Director Independence'),
    ('14', 'Principal Accountant Fees and Services'),
    ('15', 'Exhibit and Financial Statement Schedules'),
    ('16', 'Form 10-K Summary'),
]

# Items we actually extract and store as named sections in the database.
TARGET_ITEMS: list[tuple[str, str]] = [
    ('1',  'Business'),
    ('1A', 'Risk Factors'),
    ('7',  "Management's Discussion and Analysis"),  # Display name (shorter than full title)
    ('8',  'Financial Statements'),
]

# Apostrophe class — straight, U+2019 (right single quote, most common in real
# filings), U+2018 (left single quote, occasional), U+02BC (modifier letter apostrophe).
_APOS = "['\u2019\u2018\u02BC]"


@dataclass
class ExtractedSection:
    name: str
    item_label: str
    char_start: int
    char_end: int
    text: str


def _title_pattern(title: str) -> str:
    """Build a fuzzy regex for a canonical title that:
       - allows any apostrophe variant where the literal had a straight apostrophe;
       - allows any *inline* whitespace ([ \\t]+) between words — but NOT newlines.
    The inline-only whitespace is the key: it makes the pattern reject TOC entries,
    which after HTML-table flattening have newlines between the item number,
    the title, and the page number.
    """
    words = title.split()
    parts = [re.escape(w).replace("'", _APOS) for w in words]
    return r"[ \t]+".join(parts)


def _find_body_match(text: str, item_num: str, item_title: str) -> list[re.Match]:
    """Find all places where this item's header appears in the body."""
    if item_num == '6':
        # Body: "Item 6. [Reserved]" — the brackets are part of the literal text.
        # Allow them optional in case of variations.
        pat = r"\bItem[ \t]+6\.[ \t]+\[?Reserved\]?"
    else:
        pat = rf"\bItem[ \t]+{re.escape(item_num)}\.[ \t]+{_title_pattern(item_title)}"
    return list(re.finditer(pat, text, re.IGNORECASE))


def extract_sections(text: str) -> list[ExtractedSection]:
    """Extract the four target Item sections from filing plaintext.

    Returns sections in document order, each containing the item header line
    plus the body up to the next item.
    """
    # Find body anchors for every item we know about (target items + neighbours,
    # since neighbours act as section ENDS).
    boundaries: list[tuple[int, str, str]] = []  # (start, num, title)
    for num, title in ITEM_DEFS:
        matches = _find_body_match(text, num, title)
        if not matches:
            log.debug("No body anchor for Item %s", num)
            continue
        # Multiple matches usually mean the TOC also matched (rare with our inline-ws
        # rule, but possible if the TOC layout collapsed onto one line). Take the LAST
        # — body always comes after TOC in source order.
        m = matches[-1]
        boundaries.append((m.start(), num, title))

    boundaries.sort(key=lambda b: b[0])

    if not boundaries:
        log.warning("No Item anchors found in document of %d chars", len(text))
        return []

    # Build the output for each TARGET item by slicing from its anchor to the
    # next anchor in document order.
    target_nums = {num: name for num, name in TARGET_ITEMS}
    extracted: list[ExtractedSection] = []
    for i, (start, num, _t) in enumerate(boundaries):
        if num not in target_nums:
            continue
        end = boundaries[i + 1][0] if i + 1 < len(boundaries) else len(text)
        body = text[start:end].strip()
        if len(body) < 200:
            log.warning("Section Item %s body too short (%d chars), skipping", num, len(body))
            continue
        extracted.append(ExtractedSection(
            name=target_nums[num],
            item_label=f"Item {num}",
            char_start=start,
            char_end=end,
            text=body,
        ))

    log.info("Extracted %d sections", len(extracted))
    return extracted
