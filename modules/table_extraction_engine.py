"""
Lightweight table-extraction helper layer for the Municipal Credit Deal Workspace.

This module is intentionally dependency-light: it works with the app's existing
`st.session_state['parsed_documents']` structure, so it does not require new OCR
packages to run. It gives the app a safer A/B/C layer:

A. Table Candidate Detector
B. Text/Table Reconstruction Fallback
C. Confidence Scoring + review status

Use this as `modules/table_extraction_engine.py` in the GitHub repo.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd


TABLE_KEYWORDS: Dict[str, List[str]] = {
    "top_taxpayers": [
        "top taxpayers",
        "largest taxpayers",
        "principal taxpayers",
        "major taxpayers",
        "taxpayer concentration",
        "largest special tax payers",
        "special tax levy",
    ],
    "overlapping_debt": [
        "overlapping debt",
        "direct and overlapping debt",
        "statement of overlapping debt",
        "overlapping bonded debt",
    ],
    "reserve_fund": [
        "reserve fund",
        "initial reserve",
        "reserve account",
        "reserve requirement",
    ],
    "debt_service": [
        "debt service",
        "annual debt service",
        "debt service schedule",
        "cashflow",
        "cash flow",
        "special tax levy",
        "annual special tax",
    ],
    "value_to_lien": [
        "value-to-lien",
        "value to lien",
        "assessed value",
        "appraised value",
    ],
}


def safe_text(value: Any) -> str:
    """Convert missing values to an empty string for extraction routines."""
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value)


def money_to_float(value: Any) -> Optional[float]:
    """Parse common money/number strings safely."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            if pd.isna(value):
                return None
        except Exception:
            pass
        return float(value)

    text = safe_text(value).strip()
    if not text:
        return None

    # Keep the first number-like token.
    match = re.search(r"[-+]?\$?\s*([0-9][0-9,]*(?:\.\d+)?)", text)
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", ""))
    except Exception:
        return None


def percent_to_float(value: Any) -> Optional[float]:
    """Parse percent strings into numeric percent units, e.g. '12.5%' -> 12.5."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            if pd.isna(value):
                return None
        except Exception:
            pass
        return float(value)
    text = safe_text(value)
    match = re.search(r"([-+]?\d+(?:\.\d+)?)\s*%?", text)
    if not match:
        return None
    try:
        return float(match.group(1))
    except Exception:
        return None


def _table_preview_text(table: Dict[str, Any]) -> str:
    """Flatten a parsed table preview into text so the same detectors work on tables."""
    pieces: List[str] = []
    if table.get("table_name"):
        pieces.append(str(table.get("table_name")))
    preview = table.get("preview", []) or []
    try:
        df = pd.DataFrame(preview)
        if not df.empty:
            pieces.append(" ".join([str(c) for c in df.columns]))
            pieces.append(df.astype(str).head(30).to_string(index=False))
    except Exception:
        pieces.append(str(preview))
    return "\n".join(pieces)


def _split_document_into_pages(text: Any) -> List[Dict[str, Any]]:
    """
    Split parsed OS text into page-like chunks.

    Your app's PDF parser often stores text like:
        --- PAGE 1 ---
        ...
        --- PAGE 2 ---

    This helper scans the *entire* OS instead of only the first preview chunk.
    If page markers are unavailable, it falls back to large rolling chunks so
    long OS documents are still searched end-to-end.
    """
    content = safe_text(text)
    if not content.strip():
        return []

    marker_pattern = re.compile(r"---\s*PAGE\s+(\d+)\s*---", re.I)
    matches = list(marker_pattern.finditer(content))

    pages: List[Dict[str, Any]] = []
    if matches:
        for idx, match in enumerate(matches):
            page_no = int(match.group(1))
            start = match.end()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(content)
            page_text = content[start:end].strip()
            pages.append({"page": page_no, "text": page_text})
        return pages

    # Fallback: scan the whole document in chunks. This prevents long OS files
    # from being limited to the front matter.
    chunk_size = 9000
    overlap = 1200
    pos = 0
    chunk_no = 1
    while pos < len(content):
        chunk = content[pos: pos + chunk_size]
        pages.append({"page": chunk_no, "text": chunk})
        if pos + chunk_size >= len(content):
            break
        pos += max(chunk_size - overlap, 1)
        chunk_no += 1
    return pages


def _window_pages(pages: List[Dict[str, Any]], page_index: int, radius: int = 2) -> str:
    """Return candidate page ± radius pages as a single extraction context."""
    start = max(page_index - radius, 0)
    end = min(page_index + radius + 1, len(pages))
    pieces: List[str] = []
    for p in pages[start:end]:
        pieces.append(f"--- PAGE {p.get('page', '?')} ---\n{safe_text(p.get('text'))}")
    return "\n\n".join(pieces)


def detect_candidate_pages(parsed_docs: Iterable[Dict[str, Any]], window_radius: int = 2) -> List[Dict[str, Any]]:
    """
    Detect document pages/tables likely to contain useful credit-analysis tables.

    IMPORTANT: this scans the entire parsed OS page-by-page, not just the first
    few pages. When a keyword is found, the returned preview contains the matched
    page plus ±2 pages by default so tables that span pages can be reconstructed.
    """
    candidates: List[Dict[str, Any]] = []

    for doc in parsed_docs or []:
        doc_name = doc.get("file_name") or doc.get("name") or "Uploaded document"
        pages = _split_document_into_pages(doc.get("text", ""))

        # 1) Full-document page scan.
        for page_index, page in enumerate(pages):
            page_text = safe_text(page.get("text"))
            lower = page_text.lower()
            if not lower.strip():
                continue

            for label, phrases in TABLE_KEYWORDS.items():
                score = 0
                hits: List[str] = []
                for phrase in phrases:
                    if phrase in lower:
                        score += 1
                        hits.append(phrase)

                if score > 0:
                    context = _window_pages(pages, page_index, radius=window_radius)
                    candidates.append(
                        {
                            "document": doc_name,
                            "table_name": None,
                            "candidate_type": label,
                            "chunk_type": "document_page_window",
                            "page": page.get("page"),
                            "window_radius": window_radius,
                            "score": score,
                            "matched_terms": hits,
                            "preview": context[:20000],
                            "page_preview": page_text[:4000],
                        }
                    )

        # 2) Parsed-table scan, if available from the parser.
        for table in doc.get("tables", []) or []:
            table_text = _table_preview_text(table)
            lower = table_text.lower()
            if not lower.strip():
                continue

            for label, phrases in TABLE_KEYWORDS.items():
                score = 0
                hits: List[str] = []
                for phrase in phrases:
                    if phrase in lower:
                        score += 1
                        hits.append(phrase)
                if score > 0:
                    candidates.append(
                        {
                            "document": doc_name,
                            "table_name": table.get("table_name") or "Parsed table",
                            "candidate_type": label,
                            "chunk_type": "parsed_table",
                            "page": table.get("page"),
                            "score": score + 2,  # parsed tables are higher quality than raw text hits
                            "matched_terms": hits,
                            "preview": table_text[:20000],
                        }
                    )

    return sorted(candidates, key=lambda x: (x.get("score", 0), len(x.get("matched_terms", []))), reverse=True)


def reconstruct_taxpayer_table_from_text(text: Any) -> pd.DataFrame:
    """
    Reconstruct a taxpayer table from text lines.

    Looks for rows with a name and a percentage. This is intentionally conservative;
    the analyst should review the preview before calculating.
    """
    rows: List[Dict[str, Any]] = []

    for raw_line in safe_text(text).splitlines():
        line = raw_line.strip()
        if not line:
            continue

        # Prefer explicit percent signs, but also allow last numeric token if the
        # line contains taxpayer-like labels.
        pct_match = re.search(r"([-+]?\d+(?:\.\d+)?)\s*%", line)
        if pct_match:
            pct = percent_to_float(pct_match.group(1))
            name = line[: pct_match.start()].strip(" -—|:\t")
        else:
            if not any(word in line.lower() for word in [" llc", " lp", " inc", " company", " homes", " land", " partners"]):
                continue
            nums = re.findall(r"[-+]?\d+(?:\.\d+)?", line)
            if not nums:
                continue
            pct = percent_to_float(nums[-1])
            name = line.rsplit(nums[-1], 1)[0].strip(" -—|:\t")

        if pct is None:
            continue
        # Filter likely false positives.
        if pct < 0 or pct > 100:
            continue
        if len(name) < 3:
            continue

        rows.append({"taxpayer_name": name, "levy_percent": pct})

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.drop_duplicates().head(25).reset_index(drop=True)
    return df


def _find_amount(text: str, patterns: List[str]) -> Optional[float]:
    for pattern in patterns:
        match = re.search(pattern, text, re.I | re.S)
        if match:
            value = money_to_float(match.group(1))
            if value is not None:
                return value
    return None


def extract_vtl_inputs_from_text(text: Any) -> Dict[str, Optional[float]]:
    """Extract assessed value, direct debt, and overlapping debt from text."""
    content = safe_text(text)

    assessed_value = _find_amount(
        content,
        [
            r"total assessed value[^$\d]{0,120}\$?\s*([\d,]+(?:\.\d+)?)",
            r"assessed value[^$\d]{0,120}\$?\s*([\d,]+(?:\.\d+)?)",
            r"fiscal year[^\n]{0,160}assessed value[^$\d]{0,120}\$?\s*([\d,]+(?:\.\d+)?)",
        ],
    )

    direct_debt = _find_amount(
        content,
        [
            r"direct debt[^$\d]{0,160}\$?\s*([\d,]+(?:\.\d+)?)",
            r"bonds outstanding[^$\d]{0,160}\$?\s*([\d,]+(?:\.\d+)?)",
            r"principal amount[^$\d]{0,160}\$?\s*([\d,]+(?:\.\d+)?)",
        ],
    )

    overlapping_debt = _find_amount(
        content,
        [
            r"total overlapping debt[^$\d]{0,160}\$?\s*([\d,]+(?:\.\d+)?)",
            r"overlapping debt[^$\d]{0,160}\$?\s*([\d,]+(?:\.\d+)?)",
            r"direct and overlapping debt[^$\d]{0,200}\$?\s*([\d,]+(?:\.\d+)?)",
        ],
    )

    return {
        "assessed_value": assessed_value,
        "direct_debt": direct_debt,
        "overlapping_debt": overlapping_debt,
    }


def extract_mltm_cashflow_from_text(text: Any) -> pd.DataFrame:
    """
    Reconstruct a rough MLTM cashflow schedule from lines containing year + two amounts.

    The first two non-year numeric values are treated as special_tax_levy and
    annual_debt_service. Analyst review is required.
    """
    rows: List[Dict[str, Any]] = []

    for raw_line in safe_text(text).splitlines():
        line = raw_line.strip()
        if not line:
            continue

        year_match = re.search(r"\b(20\d{2})\b", line)
        if not year_match:
            continue

        year = int(year_match.group(1))
        numeric_tokens = re.findall(r"[-+]?\$?\s*\d[\d,]*(?:\.\d+)?", line)
        values: List[float] = []
        for tok in numeric_tokens:
            parsed = money_to_float(tok)
            if parsed is None:
                continue
            if int(parsed) == year:
                continue
            values.append(parsed)

        if len(values) >= 2:
            rows.append(
                {
                    "year": year,
                    "special_tax_levy": values[0],
                    "annual_debt_service": values[1],
                }
            )

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.drop_duplicates(subset=["year"]).sort_values("year").reset_index(drop=True)
    return df


def confidence_score(found_value_count: int, expected_count: int, source_match: bool = True) -> int:
    """Return a 0-100 confidence score based on completeness and source match."""
    if expected_count <= 0:
        return 0
    found = max(0, min(found_value_count, expected_count))
    score = int((found / expected_count) * 80)
    if source_match:
        score += 20
    return min(score, 100)


def confidence_status(score: int) -> str:
    """
    Platform-wide table-extraction reliability tiers.

    >= 80: Tier 1 / source-verified or strongly reconstructed
    20-79: Tier 2 / evidence located or partial reconstruction; manual review required
    < 20: Tier 3 / no reliable evidence located or reconstruction failed
    """
    if score >= 80:
        return "tier_1_source_verified"
    if score >= 20:
        return "tier_2_needs_manual_review"
    return "tier_3_low_confidence"
