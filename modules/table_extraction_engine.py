"""
Full-OS table extraction engine for muni credit workflows.

Replacement target:
    modules/table_extraction_engine.py

What this version adds:
P1. Full OS scan: page-by-page scanning across the entire parsed OS, not only early pages.
P2. Taxpayer Page Finder: richer keyword search with page numbers and ± page windows.
P3. OCR fallback: optional OCR for candidate pages when pdf text/table reconstruction fails.
    - Gracefully degrades if pdf2image / pytesseract / poppler are unavailable.
P4. Calculator-ready outputs: reconstructed taxpayer rows can be approved and pushed into
    Taxpayer Concentration Builder + scorecard fields by streamlit_app.py.
"""

from __future__ import annotations

import io
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence

import pandas as pd


TABLE_KEYWORDS: Dict[str, List[str]] = {
    "top_taxpayers": [
        "top taxpayers",
        "top ten taxpayers",
        "largest taxpayers",
        "largest taxpayer",
        "principal taxpayers",
        "major taxpayers",
        "largest special tax payers",
        "largest special tax payor",
        "special tax payers",
        "special tax levy",
        "taxpayer concentration",
        "largest property owners",
        "largest landowners",
        "principal property owners",
        "major property owners",
        "ownership concentration",
        "owners of property",
        "property owners representing",
        "taxable property owners",
    ],
    "overlapping_debt": [
        "overlapping debt",
        "direct and overlapping debt",
        "statement of direct and overlapping debt",
        "statement of overlapping debt",
        "overlapping bonded debt",
        "direct debt",
    ],
    "reserve_fund": [
        "reserve fund",
        "initial reserve",
        "reserve account",
        "reserve requirement",
        "debt service reserve fund",
    ],
    "debt_service": [
        "debt service",
        "annual debt service",
        "debt service schedule",
        "cashflow",
        "cash flow",
        "annual special tax",
        "special tax revenues",
        "principal and interest",
    ],
    "value_to_lien": [
        "value-to-lien",
        "value to lien",
        "assessed value",
        "appraised value",
        "valuation-to-lien",
    ],
}

TAXPAYER_ROW_HINTS = [
    " llc", " lp", " l.p", " inc", " corp", " corporation", " company", " co.",
    " homes", " home", " land", " partners", " partnership", " holdings", " group",
    " ranch", " communities", " properties", " property", " development", " builder",
]


def safe_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value)


def money_to_float(value: Any) -> Optional[float]:
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
    match = re.search(r"[-+]?\$?\s*([0-9][0-9,]*(?:\.\d+)?)", text)
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", ""))
    except Exception:
        return None


def percent_to_float(value: Any) -> Optional[float]:
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
    pieces: List[str] = []
    if table.get("table_name"):
        pieces.append(str(table.get("table_name")))
    preview = table.get("preview", []) or []
    raw = table.get("raw")
    try:
        if raw:
            pieces.append(pd.DataFrame(raw).astype(str).head(60).to_string(index=False, header=False))
        else:
            df = pd.DataFrame(preview)
            if not df.empty:
                pieces.append(" ".join([str(c) for c in df.columns]))
                pieces.append(df.astype(str).head(60).to_string(index=False))
    except Exception:
        pieces.append(str(preview or raw or ""))
    return "\n".join(pieces)


def _split_document_into_pages(text: Any) -> List[Dict[str, Any]]:
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
            pages.append({"page": page_no, "text": content[start:end].strip()})
        return pages

    chunk_size = 9000
    overlap = 1200
    pos = 0
    chunk_no = 1
    while pos < len(content):
        pages.append({"page": chunk_no, "text": content[pos: pos + chunk_size]})
        if pos + chunk_size >= len(content):
            break
        pos += max(chunk_size - overlap, 1)
        chunk_no += 1
    return pages


def _pages_from_doc(doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    pages = doc.get("pages") or []
    if pages:
        normalized = []
        for i, p in enumerate(pages):
            if isinstance(p, dict):
                normalized.append({"page": p.get("page", i + 1), "text": safe_text(p.get("text", ""))})
            else:
                normalized.append({"page": i + 1, "text": safe_text(p)})
        return normalized
    return _split_document_into_pages(doc.get("text", ""))


def _window_pages(pages: List[Dict[str, Any]], page_index: int, radius: int = 2) -> str:
    start = max(page_index - radius, 0)
    end = min(page_index + radius + 1, len(pages))
    pieces = []
    for p in pages[start:end]:
        pieces.append(f"--- PAGE {p.get('page', '?')} ---\n{safe_text(p.get('text'))}")
    return "\n\n".join(pieces)


def detect_candidate_pages(
    parsed_docs: Iterable[Dict[str, Any]],
    window_radius: int = 2,
    target_types: Optional[Sequence[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Find likely pages/tables across the full OS.

    Returns page windows so tables spanning multiple pages have enough context.
    """
    candidates: List[Dict[str, Any]] = []
    allowed = set(target_types or TABLE_KEYWORDS.keys())

    for doc in parsed_docs or []:
        doc_name = doc.get("file_name") or doc.get("name") or "Uploaded document"
        pages = _pages_from_doc(doc)

        for page_index, page in enumerate(pages):
            page_text = safe_text(page.get("text"))
            lower = page_text.lower()
            if not lower.strip():
                continue

            for label, phrases in TABLE_KEYWORDS.items():
                if label not in allowed:
                    continue
                score = 0
                hits: List[str] = []
                for phrase in phrases:
                    if phrase in lower:
                        # Stronger weight for highly specific taxpayer/debt words.
                        score += 2 if phrase in ["top taxpayers", "top ten taxpayers", "largest taxpayers", "largest property owners", "direct and overlapping debt", "debt service schedule"] else 1
                        hits.append(phrase)

                if score > 0:
                    context = _window_pages(pages, page_index, radius=window_radius)
                    candidates.append({
                        "document": doc_name,
                        "candidate_type": label,
                        "chunk_type": "document_page_window",
                        "page": page.get("page"),
                        "page_index": page_index,
                        "window_radius": window_radius,
                        "score": score,
                        "matched_terms": hits,
                        "preview": context[:30000],
                        "page_preview": page_text[:5000],
                    })

        for table in doc.get("tables", []) or []:
            table_text = _table_preview_text(table)
            lower = table_text.lower()
            if not lower.strip():
                continue
            for label, phrases in TABLE_KEYWORDS.items():
                if label not in allowed:
                    continue
                score = 0
                hits = []
                for phrase in phrases:
                    if phrase in lower:
                        score += 1
                        hits.append(phrase)
                if score > 0:
                    candidates.append({
                        "document": doc_name,
                        "table_name": table.get("table_name") or "Parsed table",
                        "candidate_type": label,
                        "chunk_type": "parsed_table",
                        "page": table.get("page"),
                        "score": score + 3,
                        "matched_terms": hits,
                        "preview": table_text[:30000],
                    })

    return sorted(candidates, key=lambda x: (x.get("score", 0), len(x.get("matched_terms", []))), reverse=True)


def _clean_taxpayer_name(name: str) -> str:
    name = re.sub(r"\s{2,}", " ", safe_text(name)).strip(" -—|:\t")
    name = re.sub(r"^(taxpayer|property owner|owner|name)\s+", "", name, flags=re.I)
    # Remove obvious page/table artifacts.
    name = re.sub(r"^\d+\s+", "", name)
    return name.strip()


def reconstruct_taxpayer_table_from_text(text: Any) -> pd.DataFrame:
    """
    Reconstruct taxpayer rows from OCR/plain text.

    Conservative but more table-aware than line-only extraction:
    - explicit percent rows: taxpayer name ... 12.34%
    - table rows with company-like name and last numeric token <= 100 treated as levy/share percent
    - avoids front-matter false positives where no taxpayer-like names exist.
    """
    rows: List[Dict[str, Any]] = []
    raw_lines = [ln.strip() for ln in safe_text(text).splitlines() if ln and ln.strip()]

    for raw_line in raw_lines:
        line = re.sub(r"\s+", " ", raw_line).strip()
        lower = line.lower()
        if len(line) < 6:
            continue
        if any(skip in lower for skip in ["table of contents", "official statement", "new issue", "not rated"]):
            continue

        pct: Optional[float] = None
        name: str = ""

        # Case 1: explicit percent sign.
        pct_matches = list(re.finditer(r"([-+]?\d+(?:\.\d+)?)\s*%", line))
        if pct_matches:
            m = pct_matches[-1]
            pct = percent_to_float(m.group(1))
            name = _clean_taxpayer_name(line[:m.start()])

        # Case 2: no percent sign, but row appears to be a taxpayer row and ends with a small percent-like number.
        if pct is None:
            has_name_hint = any(h in lower for h in TAXPAYER_ROW_HINTS)
            nums = re.findall(r"[-+]?\d+(?:\.\d+)?", line)
            if has_name_hint and nums:
                maybe_pct = percent_to_float(nums[-1])
                if maybe_pct is not None and 0 <= maybe_pct <= 100:
                    pct = maybe_pct
                    name = _clean_taxpayer_name(line.rsplit(nums[-1], 1)[0])

        if pct is None or pct < 0 or pct > 100:
            continue
        if len(name) < 3:
            continue
        # Need at least one letter and not just table headers.
        if not re.search(r"[A-Za-z]", name):
            continue
        if name.lower() in ["total", "subtotal", "taxpayer", "property owner", "owner"]:
            continue

        rows.append({"taxpayer_name": name, "levy_percent": float(pct)})

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.drop_duplicates(subset=["taxpayer_name", "levy_percent"]).head(25).reset_index(drop=True)
    return df


def ocr_taxpayer_candidate_pages(parsed_docs: Iterable[Dict[str, Any]], candidate: Dict[str, Any], dpi: int = 220) -> Dict[str, Any]:
    """
    Optional OCR fallback for a located taxpayer candidate page window.

    Requirements in deployment if you want this to actually OCR:
        pdf2image
        pytesseract
        poppler-utils system package
        tesseract-ocr system package

    If dependencies or raw PDF bytes are unavailable, returns ok=False with a clear message.
    """
    doc_name = candidate.get("document")
    page = candidate.get("page")
    radius = int(candidate.get("window_radius", 2) or 2)
    if not doc_name or page is None:
        return {"ok": False, "error": "Candidate page metadata is missing."}

    doc_match = None
    for doc in parsed_docs or []:
        if (doc.get("file_name") or doc.get("name")) == doc_name:
            doc_match = doc
            break
    if not doc_match:
        return {"ok": False, "error": "Source document is no longer available in session."}

    raw_bytes = doc_match.get("raw_bytes") or doc_match.get("pdf_bytes")
    if raw_bytes is None:
        return {"ok": False, "error": "Raw PDF bytes were not stored. Re-upload the OS using the updated parser, then rerun OCR Mode."}

    try:
        from pdf2image import convert_from_bytes  # type: ignore
        import pytesseract  # type: ignore
    except Exception as exc:
        return {"ok": False, "error": f"OCR dependencies are unavailable: {exc}"}

    try:
        page_num = int(page)
        first_page = max(page_num - radius, 1)
        last_page = page_num + radius
        images = convert_from_bytes(raw_bytes, dpi=dpi, first_page=first_page, last_page=last_page)
        pieces = []
        for offset, image in enumerate(images):
            current_page = first_page + offset
            ocr_text = pytesseract.image_to_string(image)
            pieces.append(f"--- OCR PAGE {current_page} ---\n{ocr_text}")
        text = "\n\n".join(pieces)
        df = reconstruct_taxpayer_table_from_text(text)
        return {"ok": True, "text": text, "table": df, "pages": list(range(first_page, last_page + 1))}
    except Exception as exc:
        return {"ok": False, "error": f"OCR failed: {exc}"}


def _find_amount(text: str, patterns: List[str]) -> Optional[float]:
    for pattern in patterns:
        match = re.search(pattern, text, re.I | re.S)
        if match:
            value = money_to_float(match.group(1))
            if value is not None:
                return value
    return None


def extract_vtl_inputs_from_text(text: Any) -> Dict[str, Optional[float]]:
    content = safe_text(text)
    assessed_value = _find_amount(content, [
        r"total assessed value[^$\d]{0,160}\$?\s*([\d,]+(?:\.\d+)?)",
        r"assessed value[^$\d]{0,160}\$?\s*([\d,]+(?:\.\d+)?)",
        r"fiscal year[^\n]{0,180}assessed value[^$\d]{0,160}\$?\s*([\d,]+(?:\.\d+)?)",
    ])
    direct_debt = _find_amount(content, [
        r"direct debt[^$\d]{0,180}\$?\s*([\d,]+(?:\.\d+)?)",
        r"bonds outstanding[^$\d]{0,180}\$?\s*([\d,]+(?:\.\d+)?)",
        r"principal amount[^$\d]{0,180}\$?\s*([\d,]+(?:\.\d+)?)",
    ])
    overlapping_debt = _find_amount(content, [
        r"total overlapping debt[^$\d]{0,180}\$?\s*([\d,]+(?:\.\d+)?)",
        r"overlapping debt[^$\d]{0,180}\$?\s*([\d,]+(?:\.\d+)?)",
        r"direct and overlapping debt[^$\d]{0,220}\$?\s*([\d,]+(?:\.\d+)?)",
    ])
    return {"assessed_value": assessed_value, "direct_debt": direct_debt, "overlapping_debt": overlapping_debt}


def extract_mltm_cashflow_from_text(text: Any) -> pd.DataFrame:
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
            rows.append({"year": year, "special_tax_levy": values[0], "annual_debt_service": values[1]})
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.drop_duplicates(subset=["year"]).sort_values("year").reset_index(drop=True)
    return df


def confidence_score(found_value_count: int, expected_count: int, source_match: bool = True) -> int:
    if expected_count <= 0:
        return 0
    found = max(0, min(found_value_count, expected_count))
    score = int((found / expected_count) * 80)
    if source_match:
        score += 20
    return min(score, 100)


def confidence_status(score: int) -> str:
    if score >= 80:
        return "tier_1_source_verified"
    if score >= 20:
        return "tier_2_needs_manual_review"
    return "tier_3_low_confidence"
