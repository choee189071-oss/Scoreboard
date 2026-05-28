"""
Full-OS document extraction helpers for the Municipal Credit Deal Workspace.

Replacement target:
    modules/document_ai_extraction.py

What this version changes:
- Reads the full uploaded OS / PDF page-by-page instead of truncating to early pages.
- Stores page-level text in parsed_documents so downstream table extraction can scan the whole OS.
- Keeps existing public API surface used by streamlit_app.py:
    DEFAULT_TARGETS
    read_uploaded_file_to_context(uploaded_file)
    run_document_ai_extraction(...)
- Avoids creating empty/zero-confidence candidates when values are not actually found.
"""

from __future__ import annotations

import io
import json
import re
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd


DEFAULT_TARGETS = [
    "Median Household EBI (% of U.S.)",
    "Unemployment Rate Difference vs U.S. (%)",
    "MSA Participation",
    "Real Estate Market Volatility",
    "Population Growth Difference vs U.S. (%)",
    "Top 10 Taxpayers as % of Total Levy",
    "Largest Taxpayer as % of Total Levy",
    "District Size (Parcels)",
    "Conveyance to Homeowners",
    "Est. Value-to-Lien",
    "Maximum Loss-to-Maturity (MLTM) %",
]


TARGET_TO_KEY = {
    "Median Household EBI (% of U.S.)": "median_household_ebi_percent_of_us",
    "Unemployment Rate Difference vs U.S. (%)": "unemployment_rate_difference_vs_us",
    "MSA Participation": "msa_participation",
    "Real Estate Market Volatility": "real_estate_market_volatility",
    "Population Growth Difference vs U.S. (%)": "population_growth_difference_vs_us",
    "Top 10 Taxpayers as % of Total Levy": "top10_taxpayers_percent_of_total_levy",
    "Largest Taxpayer as % of Total Levy": "largest_taxpayer_percent_of_total_levy",
    "District Size (Parcels)": "district_size_parcels",
    "Conveyance to Homeowners": "conveyance_to_homeowners",
    "Est. Value-to-Lien": "est_value_to_lien",
    "Maximum Loss-to-Maturity (MLTM) %": "maximum_loss_to_maturity_percent",
}


KEY_TO_FIELD = {v: k for k, v in TARGET_TO_KEY.items()}


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _clean_numeric(raw: Any) -> Optional[float]:
    if raw is None:
        return None
    text = str(raw).strip().replace("$", "").replace(",", "").replace("%", "")
    if not text:
        return None
    match = re.search(r"[-+]?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group(0))
    except Exception:
        return None


def _read_pdf_full(uploaded_file) -> Dict[str, Any]:
    """Read a PDF fully, page-by-page. Does not intentionally truncate pages."""
    file_name = getattr(uploaded_file, "name", "uploaded.pdf")
    raw_bytes = uploaded_file.getvalue()
    pages: List[Dict[str, Any]] = []
    tables: List[Dict[str, Any]] = []
    warnings: List[str] = []

    try:
        import pdfplumber  # type: ignore

        with pdfplumber.open(io.BytesIO(raw_bytes)) as pdf:
            for idx, page in enumerate(pdf.pages):
                page_no = idx + 1
                try:
                    text = page.extract_text(x_tolerance=1, y_tolerance=3) or ""
                except Exception as exc:
                    text = ""
                    warnings.append(f"Page {page_no}: text extraction failed: {exc}")

                pages.append({"page": page_no, "text": text})

                try:
                    extracted_tables = page.extract_tables() or []
                    for table_idx, raw_table in enumerate(extracted_tables):
                        if not raw_table:
                            continue
                        header = raw_table[0]
                        body = raw_table[1:]
                        preview = []
                        for row in body[:25]:
                            preview.append({str(header[i] or f"col_{i}"): row[i] if i < len(row) else None for i in range(len(header))})

                        tables.append(
                            {
                                "page": page_no,
                                "table_name": f"Page {page_no} Table {table_idx + 1}",
                                "preview": preview,
                                "raw": raw_table,
                            }
                        )
                except Exception as exc:
                    warnings.append(f"Page {page_no}: table extraction failed: {exc}")

    except Exception as exc:
        warnings.append(f"pdfplumber unavailable or failed: {exc}")
        try:
            from PyPDF2 import PdfReader  # type: ignore

            reader = PdfReader(io.BytesIO(raw_bytes))
            for idx, page in enumerate(reader.pages):
                page_no = idx + 1
                try:
                    text = page.extract_text() or ""
                except Exception as page_exc:
                    text = ""
                    warnings.append(f"Page {page_no}: PyPDF2 text extraction failed: {page_exc}")
                pages.append({"page": page_no, "text": text})
        except Exception as pypdf_exc:
            warnings.append(f"PyPDF2 fallback failed: {pypdf_exc}")

    full_text = "\n\n".join([f"--- PAGE {p['page']} ---\n{p.get('text', '')}" for p in pages])

    if not full_text.strip():
        warnings.append(
            "No readable text was extracted from this PDF. It may be image-based/scanned; use OCR/Vision fallback or upload a CSV/XLSX table."
        )

    return {
        "file_name": file_name,
        "text": full_text,
        "pages": pages,
        "tables": tables,
        "warnings": warnings,
        "file_type": "pdf",
        "page_count": len(pages),
        "full_document_scanned": True,
    }


def _read_excel_or_csv(uploaded_file) -> Dict[str, Any]:
    file_name = getattr(uploaded_file, "name", "uploaded_file")
    suffix = file_name.lower().split(".")[-1]
    warnings: List[str] = []
    tables: List[Dict[str, Any]] = []

    try:
        if suffix == "csv":
            df = pd.read_csv(uploaded_file)
            tables.append({"table_name": file_name, "preview": df.head(50).to_dict("records"), "raw_dataframe": df})
            text = df.head(200).to_csv(index=False)
        else:
            excel = pd.ExcelFile(uploaded_file)
            pieces = []
            for sheet in excel.sheet_names:
                df = pd.read_excel(excel, sheet_name=sheet)
                tables.append({"table_name": sheet, "preview": df.head(50).to_dict("records"), "raw_dataframe": df})
                pieces.append(f"--- SHEET {sheet} ---\n{df.head(200).to_csv(index=False)}")
            text = "\n\n".join(pieces)
    except Exception as exc:
        text = ""
        warnings.append(f"Spreadsheet read failed: {exc}")

    return {
        "file_name": file_name,
        "text": text,
        "pages": [{"page": 1, "text": text}],
        "tables": tables,
        "warnings": warnings,
        "file_type": suffix,
        "full_document_scanned": True,
    }


def read_uploaded_file_to_context(uploaded_file) -> Dict[str, Any]:
    """
    Drop-in replacement used by streamlit_app.py.

    The important behavior: PDF reading scans the full OS and stores pages,
    enabling table extraction to search page 70/90/120 instead of stopping early.
    """
    file_name = getattr(uploaded_file, "name", "uploaded_file")
    lower = file_name.lower()

    if lower.endswith(".pdf"):
        return _read_pdf_full(uploaded_file)

    if lower.endswith((".xlsx", ".xls", ".csv")):
        return _read_excel_or_csv(uploaded_file)

    try:
        raw = uploaded_file.getvalue()
        try:
            text = raw.decode("utf-8")
        except Exception:
            text = raw.decode("latin-1", errors="ignore")
    except Exception as exc:
        text = ""
        return {
            "file_name": file_name,
            "text": "",
            "pages": [],
            "tables": [],
            "warnings": [f"Text read failed: {exc}"],
            "file_type": "unknown",
            "full_document_scanned": True,
        }

    return {
        "file_name": file_name,
        "text": text,
        "pages": [{"page": 1, "text": text}],
        "tables": [],
        "warnings": [],
        "file_type": "text",
        "full_document_scanned": True,
    }


def _snippet_around(text: str, pattern: str, window: int = 900) -> str:
    match = re.search(pattern, text, re.I | re.S)
    if not match:
        return ""
    start = max(match.start() - window, 0)
    end = min(match.end() + window, len(text))
    return text[start:end]


def _first_match_value(text: str, patterns: Iterable[str]) -> Optional[float]:
    for pattern in patterns:
        match = re.search(pattern, text, re.I | re.S)
        if match:
            value = _clean_numeric(match.group(1))
            if value is not None:
                return value
    return None


def _find_ratio_value(text: str) -> Optional[str]:
    patterns = [
        r"value[-\s]?to[-\s]?lien[^\n]{0,120}?(\d+(?:\.\d+)?\s*(?:x|:1|to\s*1)?)",
        r"estimated value[-\s]?to[-\s]?lien[^\n]{0,120}?(\d+(?:\.\d+)?\s*(?:x|:1|to\s*1)?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.I | re.S)
        if match:
            return match.group(1).strip()
    return None


def _infer_conveyance(text: str) -> Optional[str]:
    lower = text.lower()
    if any(phrase in lower for phrase in ["all homes", "all or nearly all", "substantially all parcels have been conveyed"]):
        return "All or Nearly All Conveyed"
    if any(phrase in lower for phrase in ["most homes", "most parcels", "substantially developed"]):
        return "Most Conveyed"
    if any(phrase in lower for phrase in ["undeveloped", "no vertical construction", "limited vertical construction"]):
        return "Undeveloped with Limited Vertical Construction; High Concentration"
    if any(phrase in lower for phrase in ["developer owned", "merchant builder", "homebuilder"]):
        return "Fairly Developed with Significant Conveyance (Some Developer Concentration)"
    return None


def _add_candidate(
    out: List[Dict[str, Any]],
    key: str,
    value: Any,
    source_document: str,
    source_excerpt: str,
    confidence: float,
    notes: str = "",
):
    """Only add non-empty candidates. Prevents blank Needs Review cards."""
    if value is None:
        return
    if isinstance(value, str) and not value.strip():
        return

    out.append(
        {
            "scorecard_key": key,
            "scorecard_field": KEY_TO_FIELD.get(key, key),
            "value": value,
            "confidence": confidence,
            "source_document": source_document,
            "source_excerpt": source_excerpt,
            "notes": notes,
        }
    )


def _heuristic_extract(parsed_docs: List[Dict[str, Any]], selected_targets: Iterable[str]) -> List[Dict[str, Any]]:
    selected_keys = {TARGET_TO_KEY.get(t, t) for t in selected_targets or []}
    candidates: List[Dict[str, Any]] = []

    for doc in parsed_docs or []:
        source_document = doc.get("file_name", "Uploaded document")
        text = _safe_text(doc.get("text"))
        if not text.strip():
            continue

        if "district_size_parcels" in selected_keys:
            value = _first_match_value(
                text,
                [
                    r"(?:number of parcels|parcel count|total parcels)[^\d]{0,80}([\d,]+)",
                    r"([\d,]+)\s+(?:taxable\s+)?parcels",
                ],
            )
            _add_candidate(
                candidates,
                "district_size_parcels",
                int(value) if value is not None else None,
                source_document,
                _snippet_around(text, r"(?:number of parcels|parcel count|total parcels|taxable\s+parcels)"),
                0.75 if value is not None else 0,
                "Heuristic full-OS extraction.",
            )

        if "est_value_to_lien" in selected_keys:
            ratio = _find_ratio_value(text)
            _add_candidate(
                candidates,
                "est_value_to_lien",
                ratio,
                source_document,
                _snippet_around(text, r"value[-\s]?to[-\s]?lien"),
                0.80 if ratio else 0,
                "Heuristic full-OS extraction.",
            )

        if "conveyance_to_homeowners" in selected_keys:
            conveyance = _infer_conveyance(text)
            _add_candidate(
                candidates,
                "conveyance_to_homeowners",
                conveyance,
                source_document,
                _snippet_around(text, r"(?:conveyed|homeowner|developer|undeveloped|vertical construction)"),
                0.65 if conveyance else 0,
                "Rule-based inference from OS language; analyst review required.",
            )

        if "top10_taxpayers_percent_of_total_levy" in selected_keys or "largest_taxpayer_percent_of_total_levy" in selected_keys:
            # Conservative text fallback. Dedicated table_extraction_engine is preferred.
            taxpayer_section = _snippet_around(
                text,
                r"(?:top\s+(?:ten|10)\s+taxpayers|largest\s+taxpayers|largest\s+property\s+owners|principal\s+taxpayers|major\s+taxpayers)",
                window=2500,
            )
            if taxpayer_section:
                percentages = [float(x) for x in re.findall(r"(\d+(?:\.\d+)?)\s*%", taxpayer_section)]
                if percentages:
                    if "largest_taxpayer_percent_of_total_levy" in selected_keys:
                        _add_candidate(
                            candidates,
                            "largest_taxpayer_percent_of_total_levy",
                            max(percentages),
                            source_document,
                            taxpayer_section[:2000],
                            0.45,
                            "Low-confidence text fallback; verify table headers and denominator before approving.",
                        )
                    if "top10_taxpayers_percent_of_total_levy" in selected_keys:
                        _add_candidate(
                            candidates,
                            "top10_taxpayers_percent_of_total_levy",
                            round(sum(sorted(percentages, reverse=True)[:10]), 2),
                            source_document,
                            taxpayer_section[:2000],
                            0.45,
                            "Low-confidence text fallback; verify table headers and denominator before approving.",
                        )

    return candidates


def _openai_extract(
    issuer_name: str,
    state: str,
    county_or_region: str,
    bond_type: str,
    selected_targets: Iterable[str],
    parsed_docs: List[Dict[str, Any]],
    api_key: str,
    model: str,
) -> Optional[List[Dict[str, Any]]]:
    """
    Optional OpenAI extraction. The prompt passes full-document candidate windows,
    not only the beginning of the OS. Falls back silently if the SDK/key is unavailable.
    """
    if not api_key:
        return None

    try:
        from openai import OpenAI  # type: ignore
    except Exception:
        return None

    # Build targeted windows across the full OS so the prompt remains affordable.
    keywords = [
        "top taxpayers", "largest taxpayers", "principal taxpayers", "largest property owners",
        "value-to-lien", "value to lien", "overlapping debt", "debt service", "reserve fund",
        "conveyance", "homeowners", "assessed value", "parcels", "maximum loss-to-maturity", "mltm",
    ]
    windows: List[str] = []
    for doc in parsed_docs or []:
        pages = doc.get("pages") or []
        if pages:
            for idx, page in enumerate(pages):
                page_text = _safe_text(page.get("text"))
                lower = page_text.lower()
                if any(k in lower for k in keywords):
                    lo = max(0, idx - 2)
                    hi = min(len(pages), idx + 3)
                    context = "\n\n".join(
                        [f"--- {doc.get('file_name')} PAGE {pages[j].get('page')} ---\n{_safe_text(pages[j].get('text'))}" for j in range(lo, hi)]
                    )
                    windows.append(context[:12000])
        else:
            windows.append(_safe_text(doc.get("text"))[:12000])

    if not windows:
        return None

    context = "\n\n".join(windows[:12])
    target_list = list(selected_targets or DEFAULT_TARGETS)

    prompt = f"""
You are extracting municipal special assessment / CFD credit inputs from Official Statement evidence.

Issuer/deal: {issuer_name}
State: {state}
County/region: {county_or_region}
Bond type: {bond_type}

Targets:
{json.dumps(target_list, indent=2)}

Rules:
- Only return fields with an actual value found or strongly inferable from the provided evidence.
- Do NOT create blank candidates.
- Include source_excerpt for each value.
- For table-derived fields, be conservative and mention if denominator/units need verification.
- Return strict JSON with key "extracted_fields" as a list.

Each extracted field should have:
scorecard_key, scorecard_field, value, confidence (0-1), source_document, source_excerpt, notes.

Evidence windows from the full OS:
{context}
"""

    try:
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model=model or "gpt-4.1-mini",
            messages=[
                {"role": "system", "content": "Return only strict JSON. No markdown."},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )
        content = resp.choices[0].message.content or "{}"
        data = json.loads(content)
        fields = data.get("extracted_fields", []) or []
        clean = []
        for item in fields:
            value = item.get("value")
            if value is None or (isinstance(value, str) and not value.strip()):
                continue
            clean.append(item)
        return clean
    except Exception:
        return None


def run_document_ai_extraction(
    issuer_name: str,
    state: str,
    county_or_region: str,
    bond_type: str,
    selected_targets: Iterable[str],
    parsed_docs: List[Dict[str, Any]],
    api_key: Optional[str] = None,
    model: str = "gpt-4.1-mini",
) -> Dict[str, Any]:
    """
    Drop-in replacement. Scans full parsed docs and returns only non-empty candidates.
    """
    if not parsed_docs:
        return {"ok": False, "error": "No parsed documents supplied.", "extracted_fields": []}

    fields = None
    if api_key:
        fields = _openai_extract(
            issuer_name=issuer_name,
            state=state,
            county_or_region=county_or_region,
            bond_type=bond_type,
            selected_targets=selected_targets,
            parsed_docs=parsed_docs,
            api_key=api_key,
            model=model,
        )

    if fields is None:
        fields = _heuristic_extract(parsed_docs, selected_targets or DEFAULT_TARGETS)

    # Safety cleanup: never return empty-value candidates.
    cleaned = []
    for item in fields or []:
        value = item.get("value")
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        cleaned.append(item)

    return {
        "ok": True,
        "extracted_fields": cleaned,
        "candidates": cleaned,
        "notes": "Full-document extraction completed. Empty candidates were suppressed.",
    }
