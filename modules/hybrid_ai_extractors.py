"""
Hybrid AI extraction layer for the Municipal Credit Deal Workspace.

Purpose
-------
For every credit-analysis section, use the same safe data-acquisition pattern:
1) OpenAI Responses API structured JSON extraction first when an API key is available,
2) use regex only as a conservative backup/debug layer,
3) return reviewable candidates only,
4) let Streamlit/analyst approval decide what enters calculators/scorecards.

This module is intentionally UI-free. streamlit_app.py renders the workflow and approval buttons.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests


# -----------------------------------------------------------------------------
# Section / field configuration
# -----------------------------------------------------------------------------

@dataclass(frozen=True)
class HybridField:
    key: str
    label: str
    scorecard_key: Optional[str]
    value_type: str  # money | percent | number | text | table
    preferred_source: str
    regex_patterns: Tuple[str, ...]
    keywords: Tuple[str, ...]
    guidance: str


HYBRID_SECTIONS: Dict[str, Dict[str, Any]] = {
    "market_economic": {
        "title": "Market & Economic Context",
        "subtitle": "Public-data first; AI fallback only for missing context/classification notes.",
        "fields": [
            HybridField(
                key="median_household_ebi_percent_of_us",
                label="Median Household EBI (% of U.S.)",
                scorecard_key="median_household_ebi_percent_of_us",
                value_type="percent",
                preferred_source="Census / ACS public data connector",
                regex_patterns=(),
                keywords=("median household income", "effective buying income", "ebi"),
                guidance="Use Census/ACS connector when possible. AI should not invent income values; it may only extract from cited text.",
            ),
            HybridField(
                key="population_growth_difference_vs_us",
                label="Population Growth Difference vs U.S. (%)",
                scorecard_key="population_growth_difference_vs_us",
                value_type="percent",
                preferred_source="Census / ACS public data connector",
                regex_patterns=(),
                keywords=("population", "population growth", "acs"),
                guidance="Prefer calculated Census local growth minus U.S. growth. AI fallback must be labelled as sourced/extracted or left blank.",
            ),
            HybridField(
                key="msa_participation",
                label="MSA Participation",
                scorecard_key="msa_participation",
                value_type="text",
                preferred_source="Rule-based geography classifier + analyst review",
                regex_patterns=(),
                keywords=("metropolitan", "msa", "regional economy"),
                guidance="Classification only. Must remain reviewable when inferred.",
            ),
        ],
    },
    "assessed_tax_base": {
        "title": "Assessed Value / Tax Base",
        "subtitle": "AI-first OS extraction; regex is backup/debug only.",
        "fields": [
            HybridField(
                key="appraised_value_for_vtl",
                label="Appraised / Market Value for VTL",
                scorecard_key="total_assessed_value",
                value_type="money",
                preferred_source="Official Statement value-to-lien / value-to-burden table; Appraisal Report aggregate market value",
                regex_patterns=(
                    r"(?:aggregate\s+)?(?:minimum\s+)?market\s+value[^$]{0,320}\$\s*([0-9][0-9,]*(?:\.\d+)?)",
                    r"appraised\s+value[^$]{0,320}\$\s*([0-9][0-9,]*(?:\.\d+)?)",
                    r"total[^\n]{0,180}?\$\s*([0-9][0-9,]*(?:\.\d+)?)\s+\$\s*[0-9][0-9,]*(?:\.\d+)?\s+\$\s*[0-9][0-9,]*(?:\.\d+)?\s+\$\s*[0-9][0-9,]*(?:\.\d+)?\s+[0-9]+(?:\.\d+)?\s*:?1",
                ),
                keywords=("appraised value", "market value", "aggregate minimum market value", "value-to-burden", "value-to-lien", "total land secured debt"),
                guidance="For CFD/special-tax deals, use appraised or aggregate market value for VTL when assessed value is not disclosed. Do not use debt/tax-liability rows as value.",
            ),
            HybridField(
                key="developed_property_assessed_value",
                label="Developed Property Assessed Value",
                scorecard_key=None,
                value_type="money",
                preferred_source="Official Statement / Assessor developed-property AV disclosure",
                regex_patterns=(
                    r"developed\s+property[^\$]{0,320}assessed\s+value[^\$]{0,220}\$\s*([0-9][0-9,]*(?:\.\d+)?)",
                    r"preliminary\s+assessed\s+value[^\$]{0,320}developed\s+property[^\$]{0,220}\$\s*([0-9][0-9,]*(?:\.\d+)?)",
                    r"preliminary\s+assessed\s+value[^\$]{0,320}\$\s*([0-9][0-9,]*(?:\.\d+)?)",
                ),
                keywords=("developed property", "preliminary assessed value", "fiscal year"),
                guidance="Use as supplemental context; total taxable AV usually drives total district tax base.",
            ),
        ],
    },
    "housing_proxy": {
        "title": "Housing Proxy",
        "subtitle": "Public housing-series pull first; AI source scout only fills missing inventory/distress signals.",
        "fields": [
            HybridField(
                key="home_price_yoy",
                label="Home Price YoY %",
                scorecard_key=None,
                value_type="percent",
                preferred_source="FHFA HPI / verified housing data source",
                regex_patterns=(),
                keywords=("home price", "hpi", "fhfa", "housing"),
                guidance="Prefer FHFA HPI or another direct public series. Do not treat AI narrative as observed price data.",
            ),
            HybridField(
                key="inventory_yoy",
                label="Inventory YoY %",
                scorecard_key=None,
                value_type="percent",
                preferred_source="Verified inventory source / Realtor dataset / source scout link",
                regex_patterns=(),
                keywords=("inventory", "active listings", "new listing count", "housing supply"),
                guidance="Show link and source date. If inferred, label as inferred housing stress, not observed foreclosure/delinquency.",
            ),
            HybridField(
                key="real_estate_market_volatility",
                label="Real Estate Market Volatility",
                scorecard_key="real_estate_market_volatility",
                value_type="text",
                preferred_source="Derived housing classifier after analyst review",
                regex_patterns=(),
                keywords=("housing", "volatility", "distress", "foreclosure", "delinquency"),
                guidance="Classification field; keep warnings when based on inferred housing stress.",
            ),
        ],
    },
    "taxbase_concentration": {
        "title": "Tax Base & Concentration",
        "subtitle": "AI-first table extraction; page finder/regex are backup/debug only.",
        "fields": [
            HybridField(
                key="top10_taxpayers_percent_of_total_levy",
                label="Top 10 Taxpayers as % of Total Levy",
                scorecard_key="top10_taxpayers_percent_of_total_levy",
                value_type="percent",
                preferred_source="Largest Taxpayers / Special Tax Levy table in OS",
                regex_patterns=(),
                keywords=("largest taxpayers", "top taxpayers", "top ten taxpayers", "special tax levy", "taxpayer concentration"),
                guidance="If a table is present, calculate sum of top taxpayer levy percentages. Do not confuse assessed-value share with levy share unless policy allows it.",
            ),
            HybridField(
                key="largest_taxpayer_percent_of_total_levy",
                label="Largest Taxpayer as % of Total Levy",
                scorecard_key="largest_taxpayer_percent_of_total_levy",
                value_type="percent",
                preferred_source="Largest Taxpayers / Special Tax Levy table in OS",
                regex_patterns=(
                    r"responsible\s+for\s+approximately\s+([0-9]{1,3}(?:\.\d+)?)\s*%\s+of\s+(?:the\s+)?(?:projected\s+)?Fiscal\s+Year\s+\d{4}-\d{2}\s+Special\s+Tax",
                    r"responsible\s+for\s+approximately\s+([0-9]{1,3}(?:\.\d+)?)\s*%\s+of\s+(?:the\s+)?(?:projected\s+)?[^.]{0,160}Special\s+Tax",
                ),
                keywords=("largest taxpayers", "largest taxpayer", "special tax levy", "property owner"),
                guidance="Usually the first row of the taxpayer table. Cross-check against top-10 total; largest should not exceed top-10.",
            ),
            HybridField(
                key="district_size_parcels",
                label="District Size (Parcels)",
                scorecard_key="district_size_parcels",
                value_type="number",
                preferred_source="OS development status / taxable parcels disclosure",
                regex_patterns=(
                    r"contains\s+([0-9][0-9,]*)\s+taxable\s+parcels",
                    r"([0-9][0-9,]*)\s+taxable\s+parcels",
                    r"there\s+are\s+([0-9][0-9,]*)\s+parcels\s+of\s+developed\s+property",
                ),
                keywords=("taxable parcels", "developed property", "approved property", "undeveloped property"),
                guidance="Prefer total taxable parcels unless scorecard specifically requests developed parcels only.",
            ),
            HybridField(
                key="conveyance_to_homeowners",
                label="Conveyance to Homeowners",
                scorecard_key="conveyance_to_homeowners",
                value_type="text",
                preferred_source="OS development status / homeowner conveyance disclosure",
                regex_patterns=(),
                keywords=("conveyed to individual homeowners", "completed", "homeowners", "development status"),
                guidance="Classification should be reviewable. Use exact unit counts when available.",
            ),
        ],
    },
    "leverage_vtl": {
        "title": "Leverage & Value-to-Lien",
        "subtitle": "AI-first extraction of AV/debt/VTL; regex is backup/debug only.",
        "fields": [
            HybridField(
                key="appraised_value_for_vtl",
                label="Appraised / Market Value for VTL",
                scorecard_key="total_assessed_value",
                value_type="money",
                preferred_source="OS Value-to-Burden / Appraisal Report aggregate market value",
                regex_patterns=(
                    r"(?:aggregate\s+)?(?:minimum\s+)?market\s+value[^$]{0,320}\$\s*([0-9][0-9,]*(?:\.\d+)?)",
                    r"appraised\s+value[^$]{0,320}\$\s*([0-9][0-9,]*(?:\.\d+)?)",
                    r"total[^\n]{0,180}?\$\s*([0-9][0-9,]*(?:\.\d+)?)\s+\$\s*[0-9][0-9,]*(?:\.\d+)?\s+\$\s*[0-9][0-9,]*(?:\.\d+)?\s+\$\s*[0-9][0-9,]*(?:\.\d+)?\s+[0-9]+(?:\.\d+)?\s*:?1",
                ),
                keywords=("appraised value", "market value", "aggregate minimum market value", "value-to-burden", "value to burden", "value-to-lien", "total land secured debt"),
                guidance="For special tax / CFD deals, if assessed value is not disclosed but appraised value or aggregate market value is disclosed for value-to-lien/value-to-burden analysis, return that as appraised_value_for_vtl. Never use debt/tax-liability rows as value.",
            ),
            HybridField(
                key="direct_debt",
                label="Direct Debt",
                scorecard_key=None,
                value_type="money",
                preferred_source="Estimated Direct and Overlapping Indebtedness table",
                regex_patterns=(
                    r"Principal\s+Amount\s+of\s+Bonds\s*\$\s*([0-9][0-9,]*(?:\.\d+)?)",
                    r"\$\s*([0-9][0-9,]*(?:\.\d+)?)\s+COMMUNITY\s+FACILITIES\s+DISTRICT",
                ),
                keywords=("direct debt", "overlapping debt", "indebtedness", "series 2015 bonds"),
                guidance="Usually includes this bond issue and parity/direct obligations. Verify table labels.",
            ),
            HybridField(
                key="overlapping_debt",
                label="Overlapping Debt",
                scorecard_key=None,
                value_type="money",
                preferred_source="Estimated Direct and Overlapping Indebtedness table",
                regex_patterns=(),
                keywords=("overlapping debt", "overlapping indebtedness", "general obligation debt"),
                guidance="Verify whether overlapping GO debt is included or excluded from the selected VTL definition.",
            ),
            HybridField(
                key="est_value_to_lien",
                label="Est. Value-to-Lien",
                scorecard_key="est_value_to_lien",
                value_type="number",
                preferred_source="OS Estimated Assessed Value-to-Lien Ratios section",
                regex_patterns=(
                    r"(?:resulting\s+in\s+an\s+)?estimated\s+assessed\s+value[-\s]*to[-\s]*lien\s+ratio[^.]{0,360}?approximately\s+([0-9]+(?:\.\d+)?)\s*-?to-?1",
                    r"value[-\s]*to[-\s]*lien\s+ratio[^.]{0,360}?approximately\s+([0-9]+(?:\.\d+)?)\s*-?to-?1",
                ),
                keywords=("value-to-lien", "value to lien", "assessed value-to-lien ratios"),
                guidance="Use OS-disclosed VTL when source definition matches scorecard definition; otherwise calculate from AV/debt.",
            ),
        ],
    },
    "cashflow_mltm": {
        "title": "Cashflow & MLTM Stress",
        "subtitle": "AI-first extraction of reserve/debt-service schedule; regex is backup/debug only.",
        "fields": [
            HybridField(
                key="initial_reserve_fund",
                label="Initial Reserve Fund",
                scorecard_key=None,
                value_type="money",
                preferred_source="Sources and Uses / Reserve Fund disclosure",
                regex_patterns=(
                    r"Reserve\s+Fund(?:\(1\))?\s*\$\s*([0-9][0-9,]*(?:\.\d+)?)",
                    r"reserve\s+requirement[^\$]{0,240}\$\s*([0-9][0-9,]*(?:\.\d+)?)",
                    r"deposit\s+to\s+the\s+Reserve\s+Fund[^\$]{0,240}\$\s*([0-9][0-9,]*(?:\.\d+)?)",
                ),
                keywords=("reserve fund", "reserve requirement", "sources and uses"),
                guidance="Use exact reserve amount and date. Do not confuse with costs of issuance or improvement fund.",
            ),
            HybridField(
                key="maximum_loss_to_maturity_percent",
                label="Maximum Loss-to-Maturity (MLTM) %",
                scorecard_key="maximum_loss_to_maturity_percent",
                value_type="percent",
                preferred_source="Calculated from approved cashflow schedule",
                regex_patterns=(
                    r"maximum\s+loss[-\s]*to[-\s]*maturity[^%]{0,220}([0-9]+(?:\.\d+)?)\s*%",
                    r"MLTM[^%]{0,220}([0-9]+(?:\.\d+)?)\s*%",
                ),
                keywords=("debt service schedule", "annual debt service", "special tax", "reserve fund", "mltm"),
                guidance="Best practice: calculate from approved schedule and reserve, not from an isolated AI estimate.",
            ),
            HybridField(
                key="mltm_cashflow_table",
                label="MLTM Cashflow Table",
                scorecard_key=None,
                value_type="table",
                preferred_source="Debt Service Schedule + special tax levy / revenue table",
                regex_patterns=(),
                keywords=("debt service schedule", "period ending", "principal", "interest", "total", "special tax levy"),
                guidance="Requires year, special tax levy/revenue, and annual debt service columns. Analyst must review before calculation.",
            ),
        ],
    },
}


# -----------------------------------------------------------------------------
# Basic utilities
# -----------------------------------------------------------------------------


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", _safe_text(text)).strip()


def _clean_money(value: Any) -> Optional[float]:
    text = _safe_text(value)
    m = re.search(r"[-+]?\$?\s*([0-9][0-9,]*(?:\.\d+)?)", text)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except Exception:
        return None


def _clean_number(value: Any) -> Optional[float]:
    text = _safe_text(value).replace(",", "")
    m = re.search(r"[-+]?\d+(?:\.\d+)?", text)
    if not m:
        return None
    try:
        return float(m.group(0))
    except Exception:
        return None


def _coerce_value(raw: Any, value_type: str) -> Any:
    if raw is None:
        return None
    if value_type == "money":
        return _clean_money(raw)
    if value_type in {"percent", "number"}:
        return _clean_number(raw)
    if value_type == "text":
        text = _normalize_space(str(raw))
        return text or None
    return raw


_TEXT_KEYS = (
    "text",
    "content",
    "raw_text",
    "full_text",
    "extracted_text",
    "page_text",
    "parsed_text",
    "markdown",
    "context",
    "ocr_text",
)

_PAGE_LIST_KEYS = (
    "pages",
    "page_texts",
    "page_text",
    "parsed_pages",
    "ocr_pages",
)


def _split_marked_pages(text: str, file_name: str = "Uploaded document") -> List[Dict[str, Any]]:
    """Split text containing markers like --- PAGE 12 --- into page dicts."""
    text = _safe_text(text)
    if not text.strip():
        return []
    # Matches both "--- PAGE 12 ---" and "--- Uploaded.pdf PAGE 12 ---".
    marker_re = re.compile(r"---\s*(?:[^\n\r]{0,120}?\s+)?PAGE\s+(\d{1,5})\s*---", flags=re.I)
    matches = list(marker_re.finditer(text))
    if not matches:
        return [{"document": file_name, "page": 1, "text": text}]
    pages: List[Dict[str, Any]] = []
    for idx, match in enumerate(matches):
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        page_text = text[start:end]
        try:
            page_no = int(match.group(1))
        except Exception:
            page_no = idx + 1
        pages.append({"document": file_name, "page": page_no, "text": page_text})
    return pages


def _extract_pages_from_page_list(obj: Any, file_name: str) -> List[Dict[str, Any]]:
    pages: List[Dict[str, Any]] = []
    if not isinstance(obj, list):
        return pages
    for i, page in enumerate(obj):
        page_no = i + 1
        txt = ""
        if isinstance(page, dict):
            page_no = int(page.get("page") or page.get("page_number") or page.get("page_no") or i + 1)
            for key in _TEXT_KEYS:
                if isinstance(page.get(key), str) and page.get(key).strip():
                    txt = page.get(key)
                    break
            # Some parsers use nested text arrays.
            if not txt and isinstance(page.get("lines"), list):
                txt = "\n".join(_safe_text(x.get("text") if isinstance(x, dict) else x) for x in page.get("lines"))
        else:
            txt = _safe_text(page)
        if txt.strip():
            pages.append({"document": file_name, "page": page_no, "text": txt})
    return pages


def _extract_pages_from_pdf_bytes(raw_bytes: Any, file_name: str) -> List[Dict[str, Any]]:
    """Last-resort parser used when parsed_docs has bytes but no page text.

    This fixes the common Streamlit state problem where a document record exists
    but pages/text were created by an older parser version or were never filled.
    """
    if not raw_bytes:
        return []
    if isinstance(raw_bytes, str):
        try:
            # Do not assume base64; most apps store bytes directly. If it is a
            # text representation, this will simply fail and return [].
            raw_bytes = raw_bytes.encode("latin-1", errors="ignore")
        except Exception:
            return []
    if not isinstance(raw_bytes, (bytes, bytearray)):
        return []

    pages: List[Dict[str, Any]] = []
    try:
        import io
        import pdfplumber  # type: ignore
        with pdfplumber.open(io.BytesIO(bytes(raw_bytes))) as pdf:
            for idx, page in enumerate(pdf.pages):
                try:
                    txt = page.extract_text(x_tolerance=1, y_tolerance=3) or ""
                except Exception:
                    txt = ""
                if txt.strip():
                    pages.append({"document": file_name, "page": idx + 1, "text": txt})
        if pages:
            return pages
    except Exception:
        pass

    try:
        import io
        from PyPDF2 import PdfReader  # type: ignore
        reader = PdfReader(io.BytesIO(bytes(raw_bytes)))
        for idx, page in enumerate(reader.pages):
            try:
                txt = page.extract_text() or ""
            except Exception:
                txt = ""
            if txt.strip():
                pages.append({"document": file_name, "page": idx + 1, "text": txt})
    except Exception:
        return []
    return pages


def _pages_from_docs(parsed_docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Robustly convert parsed document objects into page-level text.

    Important: candidate-page detection is not allowed to be a gate for regex/AI.
    This function tries every common parser shape so the hybrid resolver can always
    build full OS text when any text exists.

    2026-05-28 fix:
    - If a doc already has page-level text, do NOT also re-split the full-text
      copy. This avoids double-counting pages.
    - If a doc has no page/text but does contain raw PDF bytes, parse those bytes
      here as a last-resort recovery path.
    """
    pages: List[Dict[str, Any]] = []
    for doc_idx, doc in enumerate(parsed_docs or []):
        if not isinstance(doc, dict):
            txt = _safe_text(doc)
            if txt.strip():
                pages.extend(_split_marked_pages(txt, f"Uploaded document {doc_idx + 1}"))
            continue

        file_name = doc.get("file_name") or doc.get("name") or doc.get("filename") or f"Uploaded document {doc_idx + 1}"

        doc_pages: List[Dict[str, Any]] = []

        # 1) Page-list style parsers.
        for list_key in _PAGE_LIST_KEYS:
            extracted = _extract_pages_from_page_list(doc.get(list_key), file_name)
            if extracted:
                doc_pages.extend(extracted)

        # 2) Full-text style parsers. Only use this when page-list text is absent,
        # otherwise we duplicate pages and inflate scan coverage metrics.
        if not doc_pages:
            for key in _TEXT_KEYS:
                txt = doc.get(key)
                if isinstance(txt, str) and txt.strip():
                    doc_pages.extend(_split_marked_pages(txt, file_name))

        # 3) Raw PDF-byte fallback. This is the important recovery path for stale
        # session_state records where parsed_documents has one doc but pages/text
        # are empty. It only works if raw bytes were stored in the parsed doc.
        if not doc_pages:
            for bytes_key in ("raw_bytes", "raw_file_bytes", "file_bytes", "bytes", "content_bytes"):
                if bytes_key in doc and doc.get(bytes_key):
                    doc_pages = _extract_pages_from_pdf_bytes(doc.get(bytes_key), file_name)
                    if doc_pages:
                        # Cache recovered pages back into the session-state doc so
                        # subsequent regex/candidate/debug passes do not re-parse
                        # the PDF bytes repeatedly.
                        try:
                            doc["pages"] = [{"page": p.get("page"), "text": p.get("text", "")} for p in doc_pages]
                            doc["text"] = "\n\n".join(
                                f"--- PAGE {p.get('page')} ---\n{p.get('text','')}" for p in doc_pages
                            )
                            doc["page_count"] = len(doc_pages)
                            doc["full_document_scanned"] = True
                        except Exception:
                            pass
                        break

        # 4) Nested context/payload structures.
        if not doc_pages:
            for nested_key in ("document", "payload", "result", "data"):
                nested = doc.get(nested_key)
                if isinstance(nested, dict):
                    doc_pages.extend(_pages_from_docs([{**nested, "file_name": file_name}]))

        pages.extend(doc_pages)

    # Deduplicate exact document/page/text repeats while keeping order.
    seen = set()
    deduped: List[Dict[str, Any]] = []
    for p in pages:
        txt = _safe_text(p.get("text", ""))
        if not txt.strip():
            continue
        try:
            page_no = int(p.get("page") or 1)
        except Exception:
            page_no = 1
        key = (_safe_text(p.get("document")), page_no, hash(txt[:800]))
        if key in seen:
            continue
        seen.add(key)
        deduped.append({"document": _safe_text(p.get("document")) or "Uploaded document", "page": page_no, "text": txt})
    return deduped


def flatten_parsed_docs_to_full_text(parsed_docs: List[Dict[str, Any]]) -> str:
    """
    Build full document text independent of candidate-page detection.
    This is the backbone of the hybrid resolver: regex must scan this text even
    when candidate_pages == 0.
    """
    pages = _pages_from_docs(parsed_docs)
    if pages:
        return _full_text_from_pages(pages)
    chunks: List[str] = []
    for doc in parsed_docs or []:
        if isinstance(doc, dict):
            for key in _TEXT_KEYS:
                txt = doc.get(key)
                if isinstance(txt, str) and txt.strip():
                    chunks.append(txt)
        else:
            txt = _safe_text(doc)
            if txt.strip():
                chunks.append(txt)
    return "\n\n".join(chunks)


def _full_text_from_pages(pages: List[Dict[str, Any]]) -> str:
    return "\n\n".join(f"--- {p['document']} PAGE {p['page']} ---\n{p.get('text','')}" for p in pages)


def _evidence_window(pages: List[Dict[str, Any]], document: str, page_no: int, radius: int = 1, max_chars: int = 9000) -> str:
    selected = [p for p in pages if p.get("document") == document and abs(int(p.get("page", 0)) - int(page_no)) <= radius]
    text = _full_text_from_pages(selected)
    return text[:max_chars]


def _infer_page_from_fulltext_position(full_text: str, pos: int) -> Optional[int]:
    before = _safe_text(full_text[:pos])[-2500:]
    matches = list(re.finditer(r"PAGE\s+(\d{1,5})\s*---", before, flags=re.I))
    if not matches:
        return None
    try:
        return int(matches[-1].group(1))
    except Exception:
        return None


def _scan_field_in_full_text(field: HybridField, full_text: str) -> List[Dict[str, Any]]:
    """Regex scan against the full OS text, not just candidate pages."""
    results: List[Dict[str, Any]] = []
    if not full_text.strip() or not field.regex_patterns:
        return results

    search_text = _normalize_space(full_text)
    # Normalization changes offsets, so evidence snippets come from normalized text.
    for pattern in field.regex_patterns:
        for match in re.finditer(pattern, search_text, flags=re.I | re.S):
            raw = match.group(1) if match.groups() else match.group(0)
            value = _coerce_value(raw, field.value_type)
            if value is None or value == "":
                continue
            start = max(match.start() - 520, 0)
            end = min(match.end() + 720, len(search_text))
            excerpt = search_text[start:end]
            page = _infer_page_from_fulltext_position(search_text, match.start())
            confidence = 0.90
            lower_match = match.group(0).lower()
            if field.key in {"all_taxable_assessed_value", "assessed_value"} and "all" in lower_match and "taxable" in lower_match:
                confidence = 0.97
            elif "preliminary assessed value" in lower_match or "developed property" in lower_match:
                confidence = 0.86
            results.append({
                "field_key": field.key,
                "label": field.label,
                "scorecard_key": field.scorecard_key,
                "value": value,
                "value_type": field.value_type,
                "confidence": confidence,
                "method": "Regex Full-OS Scan",
                "tier": "Tier 1",
                "source_document": "Full parsed OS text",
                "page": page,
                "evidence": excerpt,
                "preferred_source": field.preferred_source,
                "guidance": field.guidance,
            })
    return results


def _document_scan_debug(parsed_docs: List[Dict[str, Any]], regex_candidates: Optional[List[Dict[str, Any]]] = None, candidate_pages: Optional[List[Dict[str, Any]]] = None, ai_requested: bool = False, api_key_available: bool = False, ai_candidates: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    pages = _pages_from_docs(parsed_docs)
    full_text = flatten_parsed_docs_to_full_text(parsed_docs)
    return {
        "parsed_documents": len(parsed_docs or []),
        "pages_scanned": len(pages),
        "full_text_characters": len(full_text),
        "regex_candidates": len(regex_candidates or []),
        "candidate_pages": len(candidate_pages or []),
        "ai_requested": bool(ai_requested),
        "api_key_available": bool(api_key_available),
        "ai_used": bool(ai_candidates),
    }


def _looks_like_taxbase_concentration_fields(fields: Iterable[HybridField]) -> bool:
    """Detect the Tax Base & Concentration resolver from its field keys.

    This keeps candidate-page search section-aware without changing the public
    function signature used by streamlit_app.py.
    """
    keys = {getattr(f, "key", "") for f in fields}
    return bool({
        "top10_taxpayers_percent_of_total_levy",
        "largest_taxpayer_percent_of_total_levy",
        "district_size_parcels",
        "conveyance_to_homeowners",
    } & keys)


def _looks_like_leverage_fields(fields: Iterable[HybridField]) -> bool:
    keys = {getattr(f, "key", "") for f in fields}
    return bool({"appraised_value_for_vtl", "assessed_value", "direct_debt", "overlapping_debt", "est_value_to_lien"} & keys)


def _looks_like_cashflow_fields(fields: Iterable[HybridField]) -> bool:
    keys = {getattr(f, "key", "") for f in fields}
    return bool({"initial_reserve_fund", "maximum_loss_to_maturity_percent", "mltm_cashflow_table"} & keys)


def find_candidate_pages_for_fields(parsed_docs: List[Dict[str, Any]], fields: Iterable[HybridField], max_pages: int = 12) -> List[Dict[str, Any]]:
    """Find evidence pages for the selected section only.

    2026-05-28 fix:
    The old version used a global TOC target list containing "reserve fund" for
    every section. In the Tax Base & Concentration workflow, this caused the page
    finder to rank reserve-fund / front-matter pages above the actual land
    ownership and special-tax levy table. AI fallback then received the wrong
    page window and returned zero values.

    This version makes TOC/page keywords section-aware and gives high weight to
    table headers such as "Land Ownership and Current Special Tax Levy" and
    "Percentage of Total Special Tax Levy".
    """
    fields = list(fields or [])
    pages = _pages_from_docs(parsed_docs)
    hits: List[Dict[str, Any]] = []

    is_taxbase = _looks_like_taxbase_concentration_fields(fields)
    is_leverage = _looks_like_leverage_fields(fields)
    is_cashflow = _looks_like_cashflow_fields(fields)

    all_keywords: List[str] = []
    for field in fields:
        all_keywords.extend([k.lower() for k in field.keywords])
        all_keywords.append(str(field.label or "").lower())

    # Section-specific evidence phrases. These are deliberately broad because
    # OSs rarely use the same exact taxpayer-table title.
    if is_taxbase:
        all_keywords.extend([
            "land ownership and current special tax levy",
            "land ownership in the district",
            "special tax levy",
            "percentage of total special tax levy",
            "fee title owner",
            "lessee or other user",
            "current annual special tax levy",
            "concentration of property ownership",
            "responsible for more than ten percent",
            "owners of property subject to the levy",
            "shares of the most recent annual special tax levy",
        ])
    elif is_leverage:
        all_keywords.extend([
            "value-to-burden ratio",
            "value to burden ratio",
            "value-to-lien",
            "value to lien",
            "appraised value",
            "market value",
            "aggregate minimum market value",
            "value-to-burden ratio based on appraised value",
            "total land secured debt",
            "overlapping land secured debt",
            "special tax bonds",
            "direct and overlapping governmental obligations",
            "direct and overlapping bonded debt",
            "outstanding direct and overlapping bonded debt",
        ])
    elif is_cashflow:
        all_keywords.extend([
            "scheduled debt service",
            "projected debt service coverage",
            "debt service schedule",
            "reserve fund",
            "reserve requirement",
            "sources and uses of funds",
        ])

    all_keywords = list(dict.fromkeys([k.strip() for k in all_keywords if k and k.strip()]))

    def term_weight(term: str) -> int:
        t = term.lower()
        if is_taxbase and any(core in t for core in [
            "land ownership and current special tax levy",
            "percentage of total special tax levy",
            "special tax levy",
            "fee title owner",
        ]):
            return 12
        if any(core in t for core in ["largest", "top ten", "top taxpayers", "taxpayer", "value-to-lien", "value to lien", "debt service"]):
            return 6
        if any(core in t for core in ["assessed", "taxable property", "reserve fund"]):
            return 4
        return 1

    for p in pages:
        lower = _safe_text(p.get("text", "")).lower()
        matched = [k for k in all_keywords if k in lower]
        if matched:
            score = sum(term_weight(k) for k in matched)

            # Extra table-structure boost for Tax Base & Concentration.
            if is_taxbase:
                if "percentage" in lower and "total special tax levy" in lower:
                    score += 25
                if "fee title owner" in lower and "special tax levy" in lower:
                    score += 20
                if "land ownership" in lower and "special tax levy" in lower:
                    score += 20
                # De-prioritize front matter / TOC pages that merely mention the phrase.
                if "table of contents" in lower and "percentage of total special tax levy" not in lower:
                    score -= 8

            if is_leverage:
                if "value-to-burden ratio based on appraised value" in lower:
                    score += 35
                if "appraised value" in lower and "special tax bonds" in lower and "overlapping" in lower:
                    score += 30
                if "total land secured debt" in lower and "value-to-burden" in lower:
                    score += 25
                if "aggregate minimum market value" in lower or "market value of the developed property" in lower:
                    score += 18
                # Avoid debt-only/tax-liability pages unless they also contain value-to-burden/value table context.
                if "total property tax liability" in lower and "appraised value" not in lower:
                    score -= 20

            if is_cashflow:
                if "debt service schedule" in lower and "principal" in lower and "interest" in lower and "total" in lower:
                    score += 25
                if "date" in lower and "principal" in lower and "interest" in lower:
                    score += 15
                if "sources of funds" in lower and "reserve fund" in lower:
                    score += 15

            hits.append({**p, "matched_terms": matched[:12], "page_score": score})

    # TOC helper: only search TOC headings relevant to the current section.
    if is_taxbase:
        toc_targets = [
            "land ownership and current special tax levy",
            "special tax levies and delinquencies",
            "concentration of property ownership",
            "development in the district",
            "the district",
        ]
    elif is_leverage:
        toc_targets = [
            "value-to-burden ratio",
            "value-to-lien ratios",
            "appraised property value",
            "appraised values",
            "direct and overlapping governmental obligations",
            "estimated assessed value-to-lien ratios",
            "assessed value",
        ]
    elif is_cashflow:
        toc_targets = [
            "debt service schedule",
            "scheduled debt service",
            "projected debt service coverage",
            "reserve fund",
            "sources and uses of funds",
            "2025 reserve fund",
        ]
    else:
        toc_targets = [k for k in all_keywords if len(k) >= 8][:12]

    for p in pages[:20]:
        text = _safe_text(p.get("text", ""))
        lower = text.lower()
        # Only treat likely front matter as TOC. This prevents normal body pages
        # from generating accidental page-number jumps.
        if "table of contents" not in lower and int(p.get("page", 9999)) > 15:
            continue
        for target in toc_targets:
            m = re.search(re.escape(target) + r"[^0-9]{0,110}(\d{1,3})", text, flags=re.I)
            if m:
                try:
                    reported_page = int(m.group(1))
                except Exception:
                    continue
                for offset in range(0, 14):
                    actual = reported_page + offset
                    for match_page in [q for q in pages if int(q.get("page", 0)) == actual]:
                        base_score = 18 if is_taxbase else (16 if is_leverage or is_cashflow else 10)
                        hits.append({**match_page, "matched_terms": [f"TOC: {target} → {reported_page}"], "page_score": base_score})

    # Deduplicate document/page, keep highest score and matched terms.
    dedup: Dict[Tuple[str, int], Dict[str, Any]] = {}
    for h in hits:
        key = (_safe_text(h.get("document")), int(h.get("page", 0)))
        if key not in dedup or h.get("page_score", 0) > dedup[key].get("page_score", 0):
            dedup[key] = h

    return sorted(dedup.values(), key=lambda x: x.get("page_score", 0), reverse=True)[:max_pages]

# -----------------------------------------------------------------------------
# Regex extraction
# -----------------------------------------------------------------------------


def _extract_taxbase_levy_table_candidates(pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extract taxpayer concentration from Special Tax Levy table pages.

    Designed for OS tables whose rows include annual Special Tax Levy and
    "Percentage of Total Special Tax Levy". It calculates:
    - Largest taxpayer % = max row percentage
    - Top 10 taxpayers % = sum of the 10 largest row percentages

    The function returns reviewable candidates only; analyst approval remains
    required in the Streamlit reliability layer.
    """
    results: List[Dict[str, Any]] = []
    best_page = None
    best_percentages: List[float] = []
    best_score = -1

    for page in pages:
        raw_text = _safe_text(page.get("text", ""))
        lower = raw_text.lower()
        if not (
            "special tax levy" in lower
            and (
                "percentage of total" in lower
                or "percentage" in lower and "total special" in lower
                or "fee title owner" in lower
            )
        ):
            continue

        # Focus on the taxpayer table area when possible.
        table_text = raw_text
        start_markers = [
            "Land Ownership and Current Special Tax Levy",
            "Land Ownership in the District",
            "Percentage of Total",
        ]
        for marker in start_markers:
            pos = table_text.lower().find(marker.lower())
            if pos >= 0:
                table_text = table_text[pos:]
                break
        end_pos = table_text.lower().find("sources:")
        if end_pos > 0:
            table_text = table_text[:end_pos]
        totals_pos = table_text.lower().find("totals:")
        if totals_pos > 0:
            table_body = table_text[:totals_pos]
        else:
            table_body = table_text

        # Capture the percentage immediately following a dollar/levy amount.
        # Examples:
        #   $40,517.72  9.17%
        #   35,331.08  7.99
        pct_matches = re.findall(
            # Require a true levy amount, either dollar-prefixed or containing
            # a thousands comma. This avoids accidentally treating acreage
            # decimals like "1.95" as monetary values.
            r"(?:\$\s*\d{1,3}(?:,\d{3})*|\d{1,3},\d{3})\.\d{2}\s+([0-9]{1,2}(?:\.\d{1,2})?)\s*%?",
            table_body,
            flags=re.I,
        )
        percentages: List[float] = []
        for raw in pct_matches:
            try:
                val = float(raw)
            except Exception:
                continue
            if 0 < val < 100:
                percentages.append(val)

        # Remove accidental duplicates while preserving order.
        deduped: List[float] = []
        for val in percentages:
            if not any(abs(val - existing) < 0.0001 for existing in deduped):
                deduped.append(val)
        percentages = deduped

        score = len(percentages)
        if "fee title owner" in lower:
            score += 5
        if "percentage of total special tax levy" in _normalize_space(raw_text).lower():
            score += 10

        if len(percentages) >= 3 and score > best_score:
            best_score = score
            best_page = page
            best_percentages = percentages

    if not best_page or not best_percentages:
        return results

    sorted_pcts = sorted(best_percentages, reverse=True)
    largest = round(sorted_pcts[0], 2)
    top10 = round(sum(sorted_pcts[:10]), 2)
    evidence = _normalize_space(_safe_text(best_page.get("text", "")))[:3500]

    results.append({
        "field_key": "largest_taxpayer_percent_of_total_levy",
        "label": "Largest Taxpayer as % of Total Levy",
        "scorecard_key": "largest_taxpayer_percent_of_total_levy",
        "value": largest,
        "value_type": "percent",
        "confidence": 0.93,
        "method": "Regex Special Tax Levy Table Parser",
        "tier": "Tier 1",
        "source_document": best_page.get("document"),
        "page": best_page.get("page"),
        "evidence": evidence,
        "preferred_source": "Land Ownership / Special Tax Levy table in OS",
        "guidance": "Largest row percentage from the Special Tax Levy table. Verify this is levy share, not assessed-value share.",
        "notes": f"Parsed {len(best_percentages)} levy-share percentages from the table.",
    })
    results.append({
        "field_key": "top10_taxpayers_percent_of_total_levy",
        "label": "Top 10 Taxpayers as % of Total Levy",
        "scorecard_key": "top10_taxpayers_percent_of_total_levy",
        "value": top10,
        "value_type": "percent",
        "confidence": 0.91,
        "method": "Regex Special Tax Levy Table Parser",
        "tier": "Tier 1",
        "source_document": best_page.get("document"),
        "page": best_page.get("page"),
        "evidence": evidence,
        "preferred_source": "Land Ownership / Special Tax Levy table in OS",
        "guidance": "Sum of the 10 largest levy-share percentages from the Special Tax Levy table. Verify treatment when there are fewer than 10 taxpayers or affiliated owners.",
        "notes": f"Top 10 sum from {len(best_percentages)} parsed levy-share percentages.",
    })
    return results


def regex_extract_fields(parsed_docs: List[Dict[str, Any]], section_id: str) -> List[Dict[str, Any]]:
    """
    Regex extraction now ALWAYS scans the full parsed OS text first.
    Candidate pages are useful for evidence windows, but they do not gate extraction.
    """
    section = HYBRID_SECTIONS.get(section_id)
    if not section:
        return []
    fields: List[HybridField] = section["fields"]
    pages = _pages_from_docs(parsed_docs)
    full_text = flatten_parsed_docs_to_full_text(parsed_docs)
    results: List[Dict[str, Any]] = []

    # A) Full-OS scan. This catches values even when page finder returns zero pages.
    for field in fields:
        results.extend(_scan_field_in_full_text(field, full_text))

    # A2) Specialized Special Tax Levy table parser for Tax Base & Concentration.
    # This handles multi-line taxpayer/land-ownership tables that normal one-line
    # regex patterns cannot parse reliably.
    if section_id == "taxbase_concentration":
        results.extend(_extract_taxbase_levy_table_candidates(pages))

    # B) Page-by-page scan for better page/source evidence when possible.
    for field in fields:
        for page in pages:
            text = _safe_text(page.get("text", ""))
            if not text.strip() or not field.regex_patterns:
                continue
            search_text = _normalize_space(text)
            for pattern in field.regex_patterns:
                for match in re.finditer(pattern, search_text, flags=re.I | re.S):
                    raw = match.group(1) if match.groups() else match.group(0)
                    value = _coerce_value(raw, field.value_type)
                    if value is None or value == "":
                        continue
                    start = max(match.start() - 360, 0)
                    end = min(match.end() + 520, len(search_text))
                    excerpt = search_text[start:end]
                    confidence = 0.92
                    lower_match = match.group(0).lower()
                    if field.key in {"all_taxable_assessed_value", "assessed_value"} and "all" in lower_match and "taxable" in lower_match:
                        confidence = 0.98
                    elif "preliminary assessed value" in lower_match or "developed property" in lower_match:
                        confidence = 0.86
                    results.append({
                        "field_key": field.key,
                        "label": field.label,
                        "scorecard_key": field.scorecard_key,
                        "value": value,
                        "value_type": field.value_type,
                        "confidence": confidence,
                        "method": "Regex Full-OS Scan",
                        "tier": "Tier 1",
                        "source_document": page.get("document"),
                        "page": page.get("page"),
                        "evidence": excerpt,
                        "preferred_source": field.preferred_source,
                        "guidance": field.guidance,
                    })

    # C) Special narrative-derived fields for Tax Base & Concentration.
    if section_id == "taxbase_concentration":
        # District size often appears as "includes 14 separate Assessor's parcels"
        # rather than "14 taxable parcels". Capture that language too.
        for page in pages:
            text = _normalize_space(_safe_text(page.get("text", "")))
            lower = text.lower()
            parcel_match = re.search(
                r"(?:district|taxable property)[^.]{0,180}?(?:includes|comprises|contains)[^.]{0,80}?([0-9][0-9,]*)\s+(?:separate\s+)?(?:orange\s+county\s+assessor(?:’s|'s)?\s+)?parcels",
                text,
                flags=re.I,
            )
            if parcel_match:
                value = _clean_number(parcel_match.group(1))
                if value is not None:
                    results.append({
                        "field_key": "district_size_parcels",
                        "label": "District Size (Parcels)",
                        "scorecard_key": "district_size_parcels",
                        "value": int(value),
                        "value_type": "number",
                        "confidence": 0.84,
                        "method": "Regex Narrative Scan",
                        "tier": "Tier 1",
                        "source_document": page.get("document"),
                        "page": page.get("page"),
                        "evidence": text[:1600],
                        "preferred_source": "OS district description / taxable parcels disclosure",
                        "guidance": "Narrative parcel count extracted from OS. Verify taxable vs developed parcel definition.",
                    })
                    break

        for page in pages:
            text = _normalize_space(_safe_text(page.get("text", "")))
            lower = text.lower()
            if "conveyed to individual homeowners" in lower or "sold to individual homeowners" in lower:
                results.append({
                    "field_key": "conveyance_to_homeowners",
                    "label": "Conveyance to Homeowners",
                    "scorecard_key": "conveyance_to_homeowners",
                    "value": "Most Conveyed",
                    "value_type": "text",
                    "confidence": 0.95,
                    "method": "Regex Full-OS Scan / Narrative Classifier",
                    "tier": "Tier 1",
                    "source_document": page.get("document"),
                    "page": page.get("page"),
                    "evidence": text[:1200],
                    "preferred_source": "OS development status / homeowner conveyance disclosure",
                    "guidance": "Verify unit counts and whether classification should be Most Conveyed vs Fairly Developed.",
                })
                break

    # Deduplicate. Prefer page-level evidence over full-text evidence at similar confidence.
    best: Dict[str, Dict[str, Any]] = {}
    for r in results:
        key = r["field_key"]
        score = float(r.get("confidence", 0) or 0)
        if r.get("source_document") != "Full parsed OS text":
            score += 0.01
        if key not in best:
            best[key] = r
            best[key]["_rank_score"] = score
        elif score > float(best[key].get("_rank_score", 0) or 0):
            best[key] = r
            best[key]["_rank_score"] = score
    final = []
    for r in best.values():
        r.pop("_rank_score", None)
        final.append(r)
    return final


# -----------------------------------------------------------------------------
# OpenAI Responses API fallback
# -----------------------------------------------------------------------------

def _json_schema_for_fields(fields: Iterable[HybridField]) -> Dict[str, Any]:
    properties: Dict[str, Any] = {}
    required: List[str] = []
    for field in fields:
        if field.value_type in {"money", "percent", "number"}:
            val_schema = {"type": ["number", "null"]}
        elif field.value_type == "table":
            val_schema = {
                "type": ["array", "null"],
                "items": {"type": "object", "additionalProperties": {"type": ["string", "number", "null"]}},
            }
        else:
            val_schema = {"type": ["string", "null"]}
        properties[field.key] = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "value": val_schema,
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "page": {"type": ["integer", "null"]},
                "evidence": {"type": "string"},
                "source_label": {"type": "string"},
                "notes": {"type": "string"},
            },
            "required": ["value", "confidence", "page", "evidence", "source_label", "notes"],
        }
        required.append(field.key)
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": required,
    }


def _extract_output_text(response_json: Dict[str, Any]) -> str:
    if not isinstance(response_json, dict):
        return ""
    if response_json.get("output_text"):
        return _safe_text(response_json.get("output_text"))
    pieces: List[str] = []
    for item in response_json.get("output", []) or []:
        for content in item.get("content", []) or []:
            if content.get("type") in {"output_text", "text"} and content.get("text"):
                pieces.append(content.get("text"))
    return "\n".join(pieces)


def ai_extract_fields_from_text(
    *,
    section_id: str,
    fields: List[HybridField],
    candidate_text: str,
    api_key: str,
    model: str = "gpt-4.1-mini",
    issuer_name: str = "",
    state: str = "",
    county_name: str = "",
) -> Dict[str, Any]:
    if not api_key:
        return {"ok": False, "error": "OpenAI API key is required for AI fallback."}

    field_instructions = "\n".join(
        f"- {f.key}: {f.label}; type={f.value_type}; preferred source={f.preferred_source}; rule={f.guidance}"
        for f in fields
    )
    prompt = f"""
You are a municipal credit analyst extracting deal inputs from an Official Statement text window.

Issuer / district: {issuer_name}
State: {state}
County: {county_name}
Section: {HYBRID_SECTIONS.get(section_id, {}).get('title', section_id)}

Extract ONLY values that are explicitly supported by the provided text. Do not invent values.
If a field is not found, return value=null, confidence=0, page=null, and notes explaining what is missing.
Never return 0 unless the source explicitly states the value is zero. Missing is null, not 0.
Prefer deal-specific values over general county values.
For appraised_value_for_vtl / assessed value: for special tax / CFD deals, if assessed value is not disclosed but appraised value, aggregate market value, or value-to-burden table value is disclosed for value-to-lien/value-to-burden analysis, return that value as appraised_value_for_vtl. Distinguish value, direct debt, overlapping debt, tax liability, and total land-secured indebtedness. Do NOT use debt tables, property-tax-liability tables, overlapping-debt rows, or $0 debt rows as value.
For taxpayer concentration, do not confuse assessed-value share with levy/special tax share unless the source clearly says levy/special tax share.
For district size: prefer taxable units/residential lots/parcels securing the bonds. Do NOT use assessor/APN parcels or building sites unless the text explicitly says those are the taxable units securing the special tax.
For MLTM, prefer a calculated schedule or explicit MLTM; do not make up a stress value.

Fields:
{field_instructions}

Text window:
{candidate_text[:32000]}
""".strip()

    schema = _json_schema_for_fields(fields)
    payload = {
        "model": model,
        "input": [
            {"role": "system", "content": "Return strictly valid JSON matching the supplied schema. Be conservative and source-grounded."},
            {"role": "user", "content": prompt},
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "municipal_credit_extraction",
                "strict": True,
                "schema": schema,
            }
        },
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    try:
        response = requests.post("https://api.openai.com/v1/responses", headers=headers, json=payload, timeout=120)
        if response.status_code >= 400:
            # Fallback to plain prompt JSON in case account/model does not support strict schema.
            fallback_payload = {
                "model": model,
                "input": prompt + "\n\nReturn JSON only.",
            }
            response = requests.post("https://api.openai.com/v1/responses", headers=headers, json=fallback_payload, timeout=120)
        if response.status_code >= 400:
            return {"ok": False, "error": f"OpenAI Responses API failed: {response.status_code} {response.text[:500]}"}
        data = response.json()
        text = _extract_output_text(data)
        if not text.strip():
            return {"ok": False, "error": "OpenAI returned no output text.", "raw": data}
        try:
            parsed = json.loads(text)
        except Exception:
            # Try to isolate JSON object.
            m = re.search(r"\{[\s\S]*\}", text)
            if not m:
                return {"ok": False, "error": "OpenAI output was not JSON.", "output_text": text[:1000]}
            parsed = json.loads(m.group(0))
        return {"ok": True, "data": parsed, "raw_response_id": data.get("id")}
    except Exception as exc:
        return {"ok": False, "error": f"OpenAI extraction exception: {exc}"}


def _is_usable_candidate(candidate: Dict[str, Any], field_lookup: Dict[str, HybridField]) -> bool:
    """Reject obvious false positives before the UI review queue.

    Key principle: a page hit is not a field extraction. Missing numeric values must
    remain missing/null; do not show $0 or 0% as a high-confidence candidate unless
    the source explicitly states zero.
    """
    field_key = candidate.get("field_key")
    field = field_lookup.get(field_key)
    value = candidate.get("value")

    if value is None or value == "":
        return False

    if field and field.value_type in {"money", "percent", "number"}:
        try:
            numeric = float(value)
        except Exception:
            return False

        evidence = _safe_text(candidate.get("evidence", "")).lower()
        # Almost every false positive we saw became 0 with high confidence.
        # Only keep zero if the evidence explicitly says the field is zero.
        if numeric == 0:
            # For extraction targets, zero is almost always a debt-table/tax-liability artifact,
            # not a valid AV/VTL/MLTM candidate. Require manual entry if truly zero.
            if field_key in {"appraised_value_for_vtl", "all_taxable_assessed_value", "assessed_value", "direct_debt", "overlapping_debt", "est_value_to_lien", "initial_reserve_fund", "maximum_loss_to_maturity_percent"}:
                return False
            if not re.search(r"(?:\$\s*0(?:\.00)?|\b0(?:\.0+)?\s*%)", evidence):
                return False

    return True


def _build_ai_candidate_text(
    *,
    pages: List[Dict[str, Any]],
    candidate_pages: List[Dict[str, Any]],
    full_text: str,
    section_id: str = "",
    max_chars: int = 32000,
) -> str:
    """Build a compact text packet for AI-first extraction.

    We prefer relevant page windows to keep the API call fast and avoid timeout,
    but fall back to the front of full text when no page helper is available.
    """
    chunks: List[str] = []
    seen = set()

    def add_window(doc, page_num, radius=1, max_window_chars=5500):
        try:
            page_num = int(page_num)
        except Exception:
            return
        key = (str(doc), page_num, radius)
        if key in seen:
            return
        seen.add(key)
        window = _evidence_window(pages, doc, page_num, radius=radius, max_chars=max_window_chars)
        if window.strip():
            chunks.append(window.strip())

    if candidate_pages:
        for hit in candidate_pages[:10]:
            add_window(hit.get("document"), hit.get("page", 1), radius=1)

    # AI-first should not be trapped by a weak regex/page finder. Add section-specific
    # keyword windows from the full page set so tables like Hesperia Table 4B are seen.
    section_terms = {
        "assessed_tax_base": ["appraised value", "aggregate minimum market value", "market value", "value-to-burden", "value-to-lien"],
        "leverage_vtl": ["value-to-burden", "value-to-lien", "appraised value", "aggregate minimum market value", "total land secured debt", "overlapping land secured debt"],
        "cashflow_mltm": ["debt service schedule", "date principal interest total", "reserve fund", "sources of funds"],
        "taxbase_concentration": ["special tax levy", "percentage of total special tax levy", "conveyed to individual homeowners", "developed area"],
    }.get(section_id, [])
    for p in pages:
        lower = _safe_text(p.get("text", "")).lower()
        if any(term in lower for term in section_terms):
            add_window(p.get("document"), p.get("page", 1), radius=1)
            if sum(len(c) for c in chunks) > max_chars * 0.9:
                break

    if not chunks and full_text.strip():
        chunks.append(full_text[:max_chars])

    candidate_text = "\n\n".join(chunks)
    return candidate_text[:max_chars]


def run_hybrid_section_extraction(
    *,
    section_id: str,
    parsed_docs: List[Dict[str, Any]],
    api_key: Optional[str] = None,
    model: str = "gpt-4.1-mini",
    issuer_name: str = "",
    state: str = "",
    county_name: str = "",
    force_ai: bool = False,
    ai_first: bool = True,
) -> Dict[str, Any]:
    section = HYBRID_SECTIONS.get(section_id)
    if not section:
        return {"ok": False, "error": f"Unknown hybrid section: {section_id}"}

    fields: List[HybridField] = section["fields"]
    field_lookup = {f.key: f for f in fields}
    pages = _pages_from_docs(parsed_docs)
    full_text = flatten_parsed_docs_to_full_text(parsed_docs)

    # Candidate pages are evidence helpers only, not extraction gates.
    candidate_pages = find_candidate_pages_for_fields(parsed_docs, fields, max_pages=10)

    # AI-FIRST extraction: when an API key is available, ask AI for all fields first.
    # Regex is now only a backup/debug layer or a fill-in for fields AI left null.
    ai_candidates: List[Dict[str, Any]] = []
    ai_error = None
    ai_requested = bool(api_key and (ai_first or force_ai))

    if ai_requested:
        candidate_text = _build_ai_candidate_text(
            pages=pages,
            candidate_pages=candidate_pages,
            full_text=full_text,
            section_id=section_id,
            max_chars=32000,
        )
        if not candidate_text.strip():
            ai_error = "No parsed text was available for AI extraction. Re-upload a text-readable/OCR PDF."
        else:
            ai_result = ai_extract_fields_from_text(
                section_id=section_id,
                fields=fields,
                candidate_text=candidate_text,
                api_key=api_key or "",
                model=model,
                issuer_name=issuer_name,
                state=state,
                county_name=county_name,
            )
            if ai_result.get("ok"):
                data = ai_result.get("data") or {}
                for f in fields:
                    item = data.get(f.key) or {}
                    value = _coerce_value(item.get("value"), f.value_type)
                    if value is None or value == "":
                        continue
                    candidate = {
                        "field_key": f.key,
                        "label": f.label,
                        "scorecard_key": f.scorecard_key,
                        "value": value,
                        "value_type": f.value_type,
                        "confidence": float(item.get("confidence") or 0.55),
                        "method": "OpenAI Responses API Structured Extraction",
                        "tier": "AI First",
                        "source_document": item.get("source_label") or "Uploaded OS / source window",
                        "page": item.get("page"),
                        "evidence": item.get("evidence") or "",
                        "preferred_source": f.preferred_source,
                        "guidance": f.guidance,
                        "notes": item.get("notes") or "",
                        "response_id": ai_result.get("raw_response_id"),
                    }
                    if _is_usable_candidate(candidate, field_lookup):
                        ai_candidates.append(candidate)
            else:
                ai_error = ai_result.get("error")

    # Regex backup/debug. Always run it for transparency, but do not let it beat AI.
    regex_candidates_raw = regex_extract_fields(parsed_docs, section_id)
    regex_candidates = [c for c in regex_candidates_raw if _is_usable_candidate(c, field_lookup)]

    # If no API key exists, regex becomes the only source. If AI ran, regex only fills missing keys.
    candidates_by_key: Dict[str, Dict[str, Any]] = {}
    for c in ai_candidates:
        candidates_by_key[c["field_key"]] = c
    for c in regex_candidates:
        if c["field_key"] not in candidates_by_key:
            # Lower regex confidence slightly when used as backup, so reviewers know it is secondary.
            if ai_requested:
                c = dict(c)
                c["method"] = f"Regex Backup / Debug ({c.get('method', 'Regex')})"
                c["confidence"] = min(float(c.get("confidence", 0) or 0), 0.70)
            candidates_by_key[c["field_key"]] = c

    final_candidates = list(candidates_by_key.values())
    final_found = {c["field_key"] for c in final_candidates if c.get("value") not in [None, ""]}
    still_missing = [
        {"field_key": f.key, "label": f.label, "preferred_source": f.preferred_source, "guidance": f.guidance}
        for f in fields if f.key not in final_found
    ]

    scan_debug = _document_scan_debug(
        parsed_docs,
        regex_candidates=regex_candidates,
        candidate_pages=candidate_pages,
        ai_requested=ai_requested,
        api_key_available=bool(api_key),
        ai_candidates=ai_candidates,
    )
    scan_debug["ai_first"] = bool(ai_first)
    scan_debug["regex_raw_candidates"] = len(regex_candidates_raw)
    scan_debug["regex_usable_candidates"] = len(regex_candidates)

    return {
        "ok": True,
        "section_id": section_id,
        "title": section["title"],
        "subtitle": section.get("subtitle", ""),
        "regex_candidates": regex_candidates,
        "ai_candidates": ai_candidates,
        "candidates": final_candidates,
        "missing": still_missing,
        "candidate_pages": [
            {"document": h.get("document"), "page": h.get("page"), "matched_terms": h.get("matched_terms", []), "page_score": h.get("page_score", 0)}
            for h in candidate_pages
        ],
        "ai_error": ai_error,
        "scan_debug": scan_debug,
    }
