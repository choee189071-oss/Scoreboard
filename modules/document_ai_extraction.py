# modules/document_ai_extraction.py
"""
Document-first AI Extraction Module

This module avoids asking AI to freely search the web for values.
Instead, the workflow is:

1. Analyst uploads source documents/tables.
2. The app parses text/tables locally.
3. AI extracts candidate scorecard values ONLY from uploaded context.
4. Analyst reviews/approves values.
5. Approved values are passed into the scorecard.

This is much more stable than web-search-only extraction.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

import pandas as pd


SCORECARD_FIELD_MAP = {
    "Median Household EBI (% of U.S.)": "median_household_ebi_percent_of_us",
    "Unemployment Rate Difference vs U.S. (%)": "unemployment_rate_difference_vs_us",
    "MSA Participation": "msa_participation",
    "Real Estate Market Volatility": "real_estate_market_volatility",
    "Population Growth Difference vs U.S. (%)": "population_growth_difference_vs_us",
    "Top 10 Taxpayers as % of Total Levy": "top10_taxpayers_percent_of_total_levy",
    "Largest Taxpayer as % of Total Levy": "largest_taxpayer_percent_of_total_levy",
    "District Size (Parcels)": "district_size_parcels",
    "Est. Value-to-Lien": "est_value_to_lien",
    "Maximum Loss-to-Maturity (MLTM) %": "maximum_loss_to_maturity_percent",
    "Conveyance to Homeowners": "conveyance_to_homeowners",
}

DEFAULT_TARGETS = list(SCORECARD_FIELD_MAP.keys())


def get_openai_api_key(user_supplied_key: Optional[str] = None) -> Optional[str]:
    if user_supplied_key:
        return user_supplied_key.strip()
    return os.getenv("OPENAI_API_KEY")


def _extract_json_from_text(text: str) -> Dict[str, Any]:
    if not text:
        return {}

    text = text.strip()

    try:
        return json.loads(text)
    except Exception:
        pass

    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except Exception:
            pass

    obj = re.search(r"(\{.*\})", text, flags=re.DOTALL)
    if obj:
        try:
            return json.loads(obj.group(1))
        except Exception:
            pass

    return {}


def _coerce_numeric(value: Any) -> Optional[float]:
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()
    if not text:
        return None

    ratio_match = re.search(r"(-?\d+(?:\.\d+)?)\s*(?:to|-to-|:)\s*1", text.lower())
    if ratio_match:
        return float(ratio_match.group(1))

    cleaned = text.replace("$", "").replace(",", "").replace("%", "")
    match = re.search(r"-?\d+(?:\.\d+)?", cleaned)
    if match:
        return float(match.group(0))

    return None


def read_uploaded_file_to_context(uploaded_file) -> Dict[str, Any]:
    """
    Parse uploaded file into text/tables.

    Supported:
    - .csv
    - .xlsx / .xls
    - .txt
    - .pdf, if pypdf is installed

    Returns:
    {
      "file_name": ...,
      "file_type": ...,
      "text": ...,
      "tables": [...]
    }
    """
    file_name = uploaded_file.name
    suffix = file_name.lower().split(".")[-1]

    result = {
        "file_name": file_name,
        "file_type": suffix,
        "text": "",
        "tables": [],
        "warnings": [],
    }

    try:
        if suffix == "csv":
            df = pd.read_csv(uploaded_file)
            result["tables"].append(
                {
                    "table_name": file_name,
                    "columns": list(df.columns),
                    "preview": df.head(50).to_dict(orient="records"),
                }
            )
            result["text"] = df.head(100).to_csv(index=False)

        elif suffix in ["xlsx", "xls"]:
            excel = pd.ExcelFile(uploaded_file)
            text_parts = []
            for sheet in excel.sheet_names[:10]:
                df = excel.parse(sheet)
                result["tables"].append(
                    {
                        "table_name": f"{file_name}::{sheet}",
                        "columns": list(df.columns),
                        "preview": df.head(50).to_dict(orient="records"),
                    }
                )
                text_parts.append(f"\n\n--- SHEET: {sheet} ---\n")
                text_parts.append(df.head(100).to_csv(index=False))
            result["text"] = "\n".join(text_parts)

        elif suffix == "txt":
            raw = uploaded_file.read()
            try:
                result["text"] = raw.decode("utf-8")
            except UnicodeDecodeError:
                result["text"] = raw.decode("latin1")

        elif suffix == "pdf":
            try:
                from pypdf import PdfReader
                reader = PdfReader(uploaded_file)
                pages = []
                for i, page in enumerate(reader.pages[:80]):
                    page_text = page.extract_text() or ""
                    pages.append(f"\n\n--- PAGE {i + 1} ---\n{page_text}")
                result["text"] = "\n".join(pages)
            except Exception as exc:
                result["warnings"].append(
                    f"PDF parsing failed. Install pypdf or upload extracted text/table instead. Error: {exc}"
                )

        else:
            result["warnings"].append(f"Unsupported file type: {suffix}")

    except Exception as exc:
        result["warnings"].append(f"Failed to parse {file_name}: {exc}")

    return result


def build_document_context(parsed_docs: List[Dict[str, Any]], max_chars: int = 60000) -> str:
    """
    Combines parsed documents into a context string, capped for token control.
    """
    parts = []

    for doc in parsed_docs:
        parts.append(f"\n\n================ DOCUMENT: {doc.get('file_name')} ================\n")
        if doc.get("warnings"):
            parts.append(f"Warnings: {doc.get('warnings')}\n")

        text = doc.get("text", "") or ""
        parts.append(text[:max_chars // max(1, len(parsed_docs))])

    return "\n".join(parts)[:max_chars]


def build_document_extraction_prompt(
    issuer_name: str,
    state: str,
    county_or_region: str,
    bond_type: str,
    selected_targets: List[str],
    document_context: str,
) -> str:
    target_instructions = []
    for target in selected_targets:
        target_instructions.append(
            {
                "scorecard_field": target,
                "scorecard_key": SCORECARD_FIELD_MAP.get(target, ""),
            }
        )

    return f"""
You are assisting a municipal credit analyst.

Use ONLY the uploaded document context below. Do NOT search the web. Do NOT invent values.
If a value is not present or cannot be reasonably derived from the uploaded material, return null.

Issuer / District: {issuer_name}
State: {state}
County / Region: {county_or_region}
Bond Type: {bond_type}

Targets:
{json.dumps(target_instructions, indent=2)}

Scorecard categorical labels allowed:
- MSA Participation:
  1. "Yes; Broad & Diverse"
  2. "Yes; Not Broad & Diverse"
  3. "No"

- Real Estate Market Volatility:
  1. "Low Volatility; Stable Prices; Low Distress"
  2. "Elevated Volatility; Stable Prices; Affordability Worse Than National Figures"
  3. "Falling Local Home Prices; High Price Volatility; Low Affordability; Rising Distress"
  4. "Falling Local Home Prices; High Price Volatility; Significantly Worse Affordability; Rising Distress"

- Conveyance to Homeowners:
  1. "All or Nearly All Conveyed"
  2. "Most Conveyed"
  3. "Fairly Developed with Significant Conveyance (Some Developer Concentration)"
  4. "Developed; Significant Undeveloped Parcels Comprise Minority (Large Developer Concentration)"
  5. "Undeveloped with Limited Vertical Construction; High Concentration"

Return JSON only with this exact structure:
{{
  "issuer_name": "{issuer_name}",
  "summary": "brief analyst-facing summary of what was found",
  "extracted_fields": [
    {{
      "scorecard_field": "Top 10 Taxpayers as % of Total Levy",
      "scorecard_key": "top10_taxpayers_percent_of_total_levy",
      "value": "16.1%",
      "numeric_value": 16.1,
      "unit": "%",
      "source_document": "file name or sheet name",
      "source_excerpt": "short excerpt from uploaded document supporting the value",
      "confidence": 0.85,
      "notes": "short explanation"
    }}
  ],
  "derived_calculations": [
    {{
      "calculation_name": "Top 10 concentration",
      "formula": "sum of top 10 levy percentages",
      "inputs_used": ["..."],
      "output_value": "16.1%",
      "notes": "..."
    }}
  ],
  "warnings": ["..."]
}}

Uploaded document context:
{document_context}
"""


def run_document_ai_extraction(
    issuer_name: str,
    state: str,
    county_or_region: str,
    bond_type: str,
    selected_targets: List[str],
    parsed_docs: List[Dict[str, Any]],
    api_key: Optional[str] = None,
    model: str = "gpt-4.1-mini",
) -> Dict[str, Any]:
    resolved_key = get_openai_api_key(api_key)

    if not resolved_key:
        return {
            "ok": False,
            "error": "Missing OpenAI API key. Add OPENAI_API_KEY to Streamlit secrets or environment variables.",
            "issuer_name": issuer_name,
            "summary": "",
            "extracted_fields": [],
            "derived_calculations": [],
            "warnings": ["No API key provided."],
        }

    try:
        from openai import OpenAI
    except Exception as exc:
        return {
            "ok": False,
            "error": f"OpenAI Python package is not installed: {exc}",
            "issuer_name": issuer_name,
            "summary": "",
            "extracted_fields": [],
            "derived_calculations": [],
            "warnings": ["Install the openai package."],
        }

    document_context = build_document_context(parsed_docs)
    prompt = build_document_extraction_prompt(
        issuer_name=issuer_name,
        state=state,
        county_or_region=county_or_region,
        bond_type=bond_type,
        selected_targets=selected_targets,
        document_context=document_context,
    )

    client = OpenAI(api_key=resolved_key)

    try:
        response = client.responses.create(
            model=model,
            input=prompt,
            text={
                "format": {
                    "type": "json_object"
                }
            },
        )

        text = getattr(response, "output_text", None)
        if not text:
            try:
                text = response.output[0].content[0].text
            except Exception:
                text = str(response)

        parsed = _extract_json_from_text(text)

        if not parsed:
            return {
                "ok": False,
                "error": "AI response could not be parsed as JSON.",
                "raw_response": text,
                "issuer_name": issuer_name,
                "summary": "",
                "extracted_fields": [],
                "derived_calculations": [],
                "warnings": ["JSON parsing failed."],
            }

        parsed["ok"] = True
        return parsed

    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc),
            "issuer_name": issuer_name,
            "summary": "",
            "extracted_fields": [],
            "derived_calculations": [],
            "warnings": ["Document AI extraction failed."],
        }


def extracted_fields_to_dataframe(result: Dict[str, Any]) -> pd.DataFrame:
    fields = result.get("extracted_fields", []) or []
    columns = [
        "approve",
        "scorecard_field",
        "scorecard_key",
        "value",
        "numeric_value",
        "unit",
        "source_document",
        "source_excerpt",
        "confidence",
        "notes",
    ]

    if not fields:
        return pd.DataFrame(columns=columns)

    df = pd.DataFrame(fields)

    for col in columns:
        if col not in df.columns and col != "approve":
            df[col] = None

    df["approve"] = df.get("confidence", pd.Series([0] * len(df))).fillna(0).astype(float) >= 0.70

    df["numeric_value"] = df.apply(
        lambda row: row["numeric_value"] if pd.notna(row["numeric_value"]) else _coerce_numeric(row["value"]),
        axis=1,
    )

    return df[columns]


def derived_calculations_to_dataframe(result: Dict[str, Any]) -> pd.DataFrame:
    calculations = result.get("derived_calculations", []) or []
    if not calculations:
        return pd.DataFrame(columns=["calculation_name", "formula", "inputs_used", "output_value", "notes"])

    df = pd.DataFrame(calculations)
    for col in ["calculation_name", "formula", "inputs_used", "output_value", "notes"]:
        if col not in df.columns:
            df[col] = None
    return df[["calculation_name", "formula", "inputs_used", "output_value", "notes"]]


def approved_fields_to_scorecard_inputs(approved_df: pd.DataFrame) -> Dict[str, Any]:
    inputs: Dict[str, Any] = {}

    if approved_df is None or approved_df.empty:
        return inputs

    df = approved_df.copy()
    if "approve" in df.columns:
        df = df[df["approve"] == True]

    for _, row in df.iterrows():
        key = row.get("scorecard_key")
        if not key:
            continue

        numeric_value = row.get("numeric_value")
        raw_value = row.get("value")

        if pd.notna(numeric_value):
            inputs[key] = float(numeric_value)
        else:
            inputs[key] = raw_value

    return inputs


def build_mock_document_ai_result(issuer_name: str, selected_targets: List[str]) -> Dict[str, Any]:
    mock_values = {
        "Median Household EBI (% of U.S.)": ("144%", 144.0, "%", "sample_economic_appendix.xlsx", "Median Household EBI: 144% of U.S."),
        "Unemployment Rate Difference vs U.S. (%)": ("-0.3%", -0.3, "%", "sample_economic_appendix.xlsx", "4.1% vs 4.4%"),
        "MSA Participation": ("Yes; Broad & Diverse", None, "", "sample_economic_appendix.xlsx", "Sacramento-Roseville-Arden MSA"),
        "Real Estate Market Volatility": ("Low Volatility; Stable Prices; Low Distress", None, "", "sample_economic_appendix.xlsx", "Stable prices and low distress"),
        "Population Growth Difference vs U.S. (%)": ("0.5%", 0.5, "%", "sample_economic_appendix.xlsx", "Population growth above national growth"),
        "Top 10 Taxpayers as % of Total Levy": ("16.1%", 16.1, "%", "sample_top_taxpayers.xlsx", "Top 10 % of Total Levy: 16.10%"),
        "Largest Taxpayer as % of Total Levy": ("6.1%", 6.1, "%", "sample_top_taxpayers.xlsx", "Lennar Landbank: 6.10%"),
        "District Size (Parcels)": ("5900", 5900.0, "parcels", "sample_district_characteristics.xlsx", "District Size: +5,900"),
        "Est. Value-to-Lien": ("15.5-to-1", 15.5, "x", "sample_vtl.xlsx", "Direct & Overlapping VTL: 15.53-to-1"),
        "Maximum Loss-to-Maturity (MLTM) %": ("13.9%", 13.9, "%", "sample_mltm.xlsx", "S&P MLTM: 13.9%"),
        "Conveyance to Homeowners": ("Fairly Developed with Significant Conveyance (Some Developer Concentration)", None, "", "sample_builder_table.xlsx", "Fairly Developed"),
    }

    extracted = []
    for target in selected_targets:
        value, numeric, unit, doc, excerpt = mock_values.get(target, (None, None, "", "mock", "not found"))
        extracted.append(
            {
                "scorecard_field": target,
                "scorecard_key": SCORECARD_FIELD_MAP.get(target, ""),
                "value": value,
                "numeric_value": numeric,
                "unit": unit,
                "source_document": doc,
                "source_excerpt": excerpt,
                "confidence": 0.85,
                "notes": "Mock value for workflow testing.",
            }
        )

    return {
        "ok": True,
        "issuer_name": issuer_name,
        "summary": "Mock document-first extraction completed.",
        "extracted_fields": extracted,
        "derived_calculations": [
            {
                "calculation_name": "Scorecard-ready input extraction",
                "formula": "Document extraction + analyst review",
                "inputs_used": selected_targets,
                "output_value": "candidate scorecard fields",
                "notes": "Mock mode only.",
            }
        ],
        "warnings": ["Mock mode only; not based on uploaded files."],
    }
