# modules/ai_data_pull.py
"""
AI-Assisted Data Pull module for the Municipal Credit Analytics Platform.

What this module does:
1. Uses OpenAI's Responses API with web search to look for relevant public information.
2. Extracts candidate values for scorecard inputs.
3. Returns source/evidence tables for analyst review.
4. Maps approved values into the Special Assessment scorecard input format.

Important:
- This is an analyst-support workflow, not an official source of truth.
- All AI-extracted values should be reviewed before use.
- For production use, add deterministic APIs for Census, BLS/FRED, EMMA/OS parsing, and county assessor data.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

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

TARGET_TO_SOURCE_HINTS = {
    "Median Household EBI (% of U.S.)": "Census ACS, local economic profile, official statement appendix",
    "Unemployment Rate Difference vs U.S. (%)": "BLS LAUS, FRED, official statement economic appendix",
    "MSA Participation": "OMB/Census MSA definitions, official statement location description",
    "Real Estate Market Volatility": "housing market reports, real estate trend sources, official statement disclosures",
    "Population Growth Difference vs U.S. (%)": "Census ACS, official statement population table",
    "Top 10 Taxpayers as % of Total Levy": "official statement, special tax report, levy report, taxpayer table",
    "Largest Taxpayer as % of Total Levy": "official statement, special tax report, top taxpayer table",
    "District Size (Parcels)": "official statement, appraiser report, engineer's report, special tax consultant report",
    "Est. Value-to-Lien": "assessed value, direct debt, overlapping debt, official statement appendix",
    "Maximum Loss-to-Maturity (MLTM) %": "debt service schedule, projected levy, reserve fund, official statement appendix",
    "Conveyance to Homeowners": "appraiser report, official statement development status, builder ownership table",
}


def _extract_json_from_text(text: str) -> Dict[str, Any]:
    """
    Try to robustly extract JSON from a model response.
    """
    if not text:
        return {}

    text = text.strip()

    try:
        return json.loads(text)
    except Exception:
        pass

    # Try fenced code block
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception:
            pass

    # Try first JSON object
    match = re.search(r"(\{.*\})", text, flags=re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception:
            pass

    return {}


def _coerce_numeric(value: Any) -> Optional[float]:
    """
    Convert strings like '16.1%', '15.53-to-1', '$1,234,000' into float when possible.
    """
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()
    if not text:
        return None

    # Handle ratios like 16-to-1 or 15.53-to-1
    ratio_match = re.search(r"(-?\d+(?:\.\d+)?)\s*(?:to|-to-|:)\s*1", text.lower())
    if ratio_match:
        return float(ratio_match.group(1))

    cleaned = text.replace("$", "").replace(",", "").replace("%", "")
    match = re.search(r"-?\d+(?:\.\d+)?", cleaned)
    if match:
        return float(match.group(0))

    return None


def get_openai_api_key(user_supplied_key: Optional[str] = None) -> Optional[str]:
    """
    Priority:
    1. user_supplied_key from Streamlit input
    2. environment variable OPENAI_API_KEY
    3. Streamlit secrets are handled in streamlit_app.py and passed in
    """
    if user_supplied_key:
        return user_supplied_key.strip()
    return os.getenv("OPENAI_API_KEY")


def build_ai_data_pull_prompt(
    issuer_name: str,
    state: str,
    county_or_region: str,
    bond_type: str,
    os_link: str,
    selected_targets: List[str],
) -> str:
    target_instructions = []
    for target in selected_targets:
        target_instructions.append(
            {
                "field": target,
                "scorecard_key": SCORECARD_FIELD_MAP.get(target, ""),
                "preferred_sources": TARGET_TO_SOURCE_HINTS.get(target, ""),
            }
        )

    return f"""
You are assisting a municipal credit analyst. Find public-source evidence and extract candidate values for a Special Assessment Debt scorecard.

Issuer / District: {issuer_name}
State: {state}
County / Region: {county_or_region}
Bond Type: {bond_type}
Official Statement / EMMA / Source Link if provided: {os_link or "Not provided"}

Targets:
{json.dumps(target_instructions, indent=2)}

Rules:
1. Prefer official sources: official statement, EMMA documents, issuer reports, census/BLS/FRED/official government sources.
2. If you cannot find a value, return null and explain what source is missing.
3. Do not invent values.
4. Return a confidence score from 0 to 1 for each extracted value.
5. Return source URLs when available.
6. For categorical fields, use one of the scorecard labels:
   - MSA Participation: "Yes; Broad & Diverse", "Yes; Not Broad & Diverse", "No"
   - Real Estate Market Volatility: "Low Volatility; Stable Prices; Low Distress",
     "Elevated Volatility; Stable Prices; Affordability Worse Than National Figures",
     "Falling Local Home Prices; High Price Volatility; Low Affordability; Rising Distress",
     "Falling Local Home Prices; High Price Volatility; Significantly Worse Affordability; Rising Distress"
   - Conveyance to Homeowners: "All or Nearly All Conveyed", "Most Conveyed",
     "Fairly Developed with Significant Conveyance (Some Developer Concentration)",
     "Developed; Significant Undeveloped Parcels Comprise Minority (Large Developer Concentration)",
     "Undeveloped with Limited Vertical Construction; High Concentration"

Return JSON only, with this exact structure:
{{
  "issuer_name": "...",
  "summary": "brief analyst-facing summary",
  "extracted_fields": [
    {{
      "scorecard_field": "Top 10 Taxpayers as % of Total Levy",
      "scorecard_key": "top10_taxpayers_percent_of_total_levy",
      "value": "16.1%",
      "numeric_value": 16.1,
      "unit": "%",
      "source_name": "Official Statement",
      "source_url": "https://...",
      "confidence": 0.85,
      "notes": "short explanation"
    }}
  ],
  "source_evidence": [
    {{
      "source_type": "Official Statement / EMMA",
      "target_data": "levy, taxpayer concentration, debt service",
      "source_name": "...",
      "source_url": "https://...",
      "status": "found / not found / needs analyst review",
      "notes": "..."
    }}
  ],
  "warnings": ["..."]
}}
"""


def run_openai_web_data_pull(
    issuer_name: str,
    state: str,
    county_or_region: str,
    bond_type: str,
    os_link: str,
    selected_targets: List[str],
    api_key: Optional[str] = None,
    model: str = "gpt-4.1-mini",
) -> Dict[str, Any]:
    """
    Uses OpenAI Responses API with web search tool.

    If your account/model does not support web_search_preview, the function will return
    a useful error message for the Streamlit UI.
    """
    resolved_key = get_openai_api_key(api_key)

    if not resolved_key:
        return {
            "ok": False,
            "error": "Missing OpenAI API key. Add OPENAI_API_KEY to Streamlit secrets or environment variables.",
            "issuer_name": issuer_name,
            "summary": "",
            "extracted_fields": [],
            "source_evidence": [],
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
            "source_evidence": [],
            "warnings": ["Install the openai package."],
        }

    client = OpenAI(api_key=resolved_key)
    prompt = build_ai_data_pull_prompt(
        issuer_name=issuer_name,
        state=state,
        county_or_region=county_or_region,
        bond_type=bond_type,
        os_link=os_link,
        selected_targets=selected_targets,
    )

    try:
        response = client.responses.create(
            model=model,
            tools=[{"type": "web_search_preview"}],
            input=prompt,
        )

        text = getattr(response, "output_text", None)

        if not text:
            # Fallback for SDK response shape changes
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
                "source_evidence": [],
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
            "source_evidence": [],
            "warnings": ["OpenAI web data pull failed."],
        }


def extracted_fields_to_dataframe(result: Dict[str, Any]) -> pd.DataFrame:
    fields = result.get("extracted_fields", []) or []
    if not fields:
        return pd.DataFrame(
            columns=[
                "approve",
                "scorecard_field",
                "scorecard_key",
                "value",
                "numeric_value",
                "unit",
                "source_name",
                "source_url",
                "confidence",
                "notes",
            ]
        )

    df = pd.DataFrame(fields)

    for col in [
        "scorecard_field",
        "scorecard_key",
        "value",
        "numeric_value",
        "unit",
        "source_name",
        "source_url",
        "confidence",
        "notes",
    ]:
        if col not in df.columns:
            df[col] = None

    df["approve"] = df["confidence"].fillna(0).astype(float) >= 0.70

    # Fill numeric values if missing
    df["numeric_value"] = df.apply(
        lambda row: row["numeric_value"] if pd.notna(row["numeric_value"]) else _coerce_numeric(row["value"]),
        axis=1,
    )

    return df[
        [
            "approve",
            "scorecard_field",
            "scorecard_key",
            "value",
            "numeric_value",
            "unit",
            "source_name",
            "source_url",
            "confidence",
            "notes",
        ]
    ]


def source_evidence_to_dataframe(result: Dict[str, Any]) -> pd.DataFrame:
    evidence = result.get("source_evidence", []) or []
    if not evidence:
        return pd.DataFrame(
            columns=["source_type", "target_data", "source_name", "source_url", "status", "notes"]
        )

    df = pd.DataFrame(evidence)

    for col in ["source_type", "target_data", "source_name", "source_url", "status", "notes"]:
        if col not in df.columns:
            df[col] = None

    return df[["source_type", "target_data", "source_name", "source_url", "status", "notes"]]


def approved_fields_to_scorecard_inputs(approved_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Convert approved AI extracted fields into scorecard input dictionary.
    """
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


def build_mock_ai_result(
    issuer_name: str,
    selected_targets: List[str],
) -> Dict[str, Any]:
    """
    Useful for debugging the UI without spending API credits.
    """
    mock_values = {
        "Median Household EBI (% of U.S.)": ("144%", 144.0, "%", "Sample workbook / OS appendix"),
        "Unemployment Rate Difference vs U.S. (%)": ("-0.3%", -0.3, "%", "Sample workbook / BLS comparison"),
        "MSA Participation": ("Yes; Broad & Diverse", None, "", "Sample workbook"),
        "Real Estate Market Volatility": ("Low Volatility; Stable Prices; Low Distress", None, "", "Sample workbook"),
        "Population Growth Difference vs U.S. (%)": ("0.5%", 0.5, "%", "Sample workbook / Census comparison"),
        "Top 10 Taxpayers as % of Total Levy": ("16.1%", 16.1, "%", "Sample workbook / Top Ten Taxpayers"),
        "Largest Taxpayer as % of Total Levy": ("6.1%", 6.1, "%", "Sample workbook / Top Ten Taxpayers"),
        "District Size (Parcels)": ("5900", 5900.0, "parcels", "Sample workbook"),
        "Est. Value-to-Lien": ("15.5-to-1", 15.5, "x", "Sample workbook / VTL calculation"),
        "Maximum Loss-to-Maturity (MLTM) %": ("13.9%", 13.9, "%", "Sample workbook / MLTM schedule"),
        "Conveyance to Homeowners": ("Fairly Developed with Significant Conveyance (Some Developer Concentration)", None, "", "Sample workbook"),
    }

    extracted = []
    for target in selected_targets:
        value, numeric_value, unit, source_name = mock_values.get(target, (None, None, "", "Mock source"))
        extracted.append(
            {
                "scorecard_field": target,
                "scorecard_key": SCORECARD_FIELD_MAP.get(target, ""),
                "value": value,
                "numeric_value": numeric_value,
                "unit": unit,
                "source_name": source_name,
                "source_url": "",
                "confidence": 0.80,
                "notes": "Mock debug value. Replace with live AI extraction when ready.",
            }
        )

    return {
        "ok": True,
        "issuer_name": issuer_name,
        "summary": "Mock AI/data pull completed for UI testing.",
        "extracted_fields": extracted,
        "source_evidence": [
            {
                "source_type": "Sample / Debug",
                "target_data": ", ".join(selected_targets),
                "source_name": "Mock source manager",
                "source_url": "",
                "status": "debug only",
                "notes": "Use live OpenAI web search for real source evidence.",
            }
        ],
        "warnings": ["Mock mode only."],
    }
