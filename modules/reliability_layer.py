# modules/reliability_layer.py
"""
Source Reliability Layer

Adds institutional workflow controls:
1. Confidence Score
2. Analyst Override
3. Evidence Viewer
4. Source Priority Engine
5. Missing Data Tracker
6. Review Dashboard

Design:
- Everything becomes a "candidate input" first.
- Analyst reviews, approves, overrides, or rejects.
- Only final approved values feed the scorecard.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd


REQUIRED_SCORECARD_FIELDS = [
    {
        "scorecard_field": "Median Household EBI (% of U.S.)",
        "scorecard_key": "median_household_ebi_percent_of_us",
        "category": "Economic Fundamentals",
        "required": True,
    },
    {
        "scorecard_field": "Unemployment Rate Difference vs U.S. (%)",
        "scorecard_key": "unemployment_rate_difference_vs_us",
        "category": "Economic Fundamentals",
        "required": True,
    },
    {
        "scorecard_field": "MSA Participation",
        "scorecard_key": "msa_participation",
        "category": "Economic Fundamentals",
        "required": True,
    },
    {
        "scorecard_field": "Real Estate Market Volatility",
        "scorecard_key": "real_estate_market_volatility",
        "category": "Economic Fundamentals",
        "required": True,
    },
    {
        "scorecard_field": "Population Growth Difference vs U.S. (%)",
        "scorecard_key": "population_growth_difference_vs_us",
        "category": "Economic Fundamentals",
        "required": True,
    },
    {
        "scorecard_field": "Top 10 Taxpayers as % of Total Levy",
        "scorecard_key": "top10_taxpayers_percent_of_total_levy",
        "category": "District Characteristics",
        "required": True,
    },
    {
        "scorecard_field": "Largest Taxpayer as % of Total Levy",
        "scorecard_key": "largest_taxpayer_percent_of_total_levy",
        "category": "District Characteristics",
        "required": True,
    },
    {
        "scorecard_field": "District Size (Parcels)",
        "scorecard_key": "district_size_parcels",
        "category": "District Characteristics",
        "required": True,
    },
    {
        "scorecard_field": "Conveyance to Homeowners",
        "scorecard_key": "conveyance_to_homeowners",
        "category": "District Characteristics",
        "required": True,
    },
    {
        "scorecard_field": "Est. Value-to-Lien",
        "scorecard_key": "est_value_to_lien",
        "category": "District Characteristics",
        "required": True,
    },
    {
        "scorecard_field": "Maximum Loss-to-Maturity (MLTM) %",
        "scorecard_key": "maximum_loss_to_maturity_percent",
        "category": "Financial Profile",
        "required": True,
    },
]


SOURCE_PRIORITY = {
    "uploaded appendix": 100,
    "uploaded os": 95,
    "official statement": 95,
    "uploaded document": 90,
    "uploaded table": 90,
    "emma": 90,
    "county assessor": 85,
    "county open data": 85,
    "census / acs": 80,
    "census": 80,
    "bls": 80,
    "fred": 75,
    "housing data": 60,
    "real estate source": 55,
    "ai estimate": 40,
    "manual input": 70,
    "unknown": 20,
}


def normalize_source_type(source_type: Any) -> str:
    if source_type is None:
        return "unknown"

    text = str(source_type).strip().lower()

    if not text:
        return "unknown"

    if "appendix" in text:
        return "uploaded appendix"
    if "official statement" in text or "os" == text:
        return "official statement"
    if "emma" in text:
        return "emma"
    if "county" in text and "assessor" in text:
        return "county assessor"
    if "county" in text:
        return "county open data"
    if "census" in text or "acs" in text:
        return "census / acs"
    if "bls" in text or "laus" in text:
        return "bls"
    if "fred" in text:
        return "fred"
    if "housing" in text or "zillow" in text or "redfin" in text:
        return "housing data"
    if "ai" in text:
        return "ai estimate"
    if "manual" in text:
        return "manual input"
    if "upload" in text or "document" in text or "xlsx" in text or "pdf" in text:
        return "uploaded document"

    return text


def get_source_priority(source_type: Any) -> int:
    normalized = normalize_source_type(source_type)
    return SOURCE_PRIORITY.get(normalized, SOURCE_PRIORITY["unknown"])


def confidence_label(confidence: Any) -> str:
    try:
        c = float(confidence)
    except Exception:
        return "Unknown"

    if c >= 0.80:
        return "High"
    if c >= 0.55:
        return "Medium"
    return "Low"


def review_status(row: pd.Series) -> str:
    approved = bool(row.get("approve", False))
    rejected = bool(row.get("reject", False))
    confidence = row.get("confidence", 0)
    override_value = row.get("analyst_override_value", None)

    if rejected:
        return "Rejected"
    if override_value not in [None, ""]:
        return "Approved with Override" if approved else "Override Pending Approval"
    if approved:
        return "Approved"
    if confidence_label(confidence) == "Low":
        return "Needs Review"
    return "Pending"


def final_value_from_row(row: pd.Series) -> Any:
    override_value = row.get("analyst_override_value", None)
    numeric_override = row.get("analyst_override_numeric_value", None)

    if numeric_override not in [None, ""]:
        return numeric_override

    if override_value not in [None, ""]:
        return override_value

    numeric_value = row.get("numeric_value", None)
    if numeric_value not in [None, ""]:
        return numeric_value

    return row.get("value", None)


def make_candidate_from_auto_result(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Convert auto connector result into a candidate scorecard input when possible.
    """
    data_source = item.get("data_source", "")
    target_data = item.get("target_data", "")
    status = item.get("status", "")

    if status not in ["success", "placeholder"]:
        return None

    if item.get("median_household_ebi_percent_of_us") is not None:
        return {
            "approve": True,
            "reject": False,
            "scorecard_field": "Median Household EBI (% of U.S.)",
            "scorecard_key": "median_household_ebi_percent_of_us",
            "value": item.get("median_household_ebi_percent_of_us"),
            "numeric_value": item.get("median_household_ebi_percent_of_us"),
            "unit": "%",
            "source_type": data_source,
            "source_document": data_source,
            "source_url": item.get("source_url", ""),
            "source_excerpt": item.get("notes", ""),
            "confidence": 0.85,
            "analyst_override_value": "",
            "analyst_override_numeric_value": "",
            "notes": item.get("notes", ""),
        }

    return None


def candidates_from_auto_results(auto_results: List[Dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for item in auto_results or []:
        candidate = make_candidate_from_auto_result(item)
        if candidate:
            rows.append(candidate)

    return normalize_candidate_dataframe(pd.DataFrame(rows))


def candidates_from_document_ai_result(result: Dict[str, Any]) -> pd.DataFrame:
    fields = (result or {}).get("extracted_fields", []) or []
    rows = []

    for field in fields:
        source_document = field.get("source_document", "")
        rows.append(
            {
                "approve": bool(float(field.get("confidence", 0) or 0) >= 0.70),
                "reject": False,
                "scorecard_field": field.get("scorecard_field"),
                "scorecard_key": field.get("scorecard_key"),
                "value": field.get("value"),
                "numeric_value": field.get("numeric_value"),
                "unit": field.get("unit"),
                "source_type": normalize_source_type(source_document),
                "source_document": source_document,
                "source_url": field.get("source_url", ""),
                "source_excerpt": field.get("source_excerpt", ""),
                "confidence": field.get("confidence", 0),
                "analyst_override_value": "",
                "analyst_override_numeric_value": "",
                "notes": field.get("notes", ""),
            }
        )

    return normalize_candidate_dataframe(pd.DataFrame(rows))


def normalize_candidate_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "approve",
        "reject",
        "scorecard_field",
        "scorecard_key",
        "value",
        "numeric_value",
        "unit",
        "final_value",
        "confidence",
        "confidence_label",
        "source_priority",
        "source_type",
        "source_document",
        "source_url",
        "source_excerpt",
        "analyst_override_value",
        "analyst_override_numeric_value",
        "review_status",
        "notes",
    ]

    if df is None or df.empty:
        return pd.DataFrame(columns=columns)

    df = df.copy()

    for col in columns:
        if col not in df.columns and col not in ["final_value", "confidence_label", "source_priority", "review_status"]:
            df[col] = ""

    df["approve"] = df["approve"].fillna(False).astype(bool)
    df["reject"] = df["reject"].fillna(False).astype(bool)
    df["confidence"] = pd.to_numeric(df["confidence"], errors="coerce").fillna(0.0)
    df["confidence_label"] = df["confidence"].apply(confidence_label)
    df["source_priority"] = df["source_type"].apply(get_source_priority)
    df["final_value"] = df.apply(final_value_from_row, axis=1)
    df["review_status"] = df.apply(review_status, axis=1)

    return df[columns]


def combine_candidate_sources(
    auto_results: List[Dict[str, Any]],
    document_ai_result: Optional[Dict[str, Any]],
    manual_candidates: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    frames = []

    auto_df = candidates_from_auto_results(auto_results)
    if not auto_df.empty:
        frames.append(auto_df)

    doc_df = candidates_from_document_ai_result(document_ai_result or {})
    if not doc_df.empty:
        frames.append(doc_df)

    if manual_candidates is not None and not manual_candidates.empty:
        frames.append(normalize_candidate_dataframe(manual_candidates))

    if not frames:
        return normalize_candidate_dataframe(pd.DataFrame())

    combined = pd.concat(frames, ignore_index=True)
    combined = normalize_candidate_dataframe(combined)

    # Sort by scorecard field, approval, source priority, confidence
    combined = combined.sort_values(
        by=["scorecard_key", "approve", "source_priority", "confidence"],
        ascending=[True, False, False, False],
    ).reset_index(drop=True)

    return combined


def approved_candidates_to_scorecard_inputs(reviewed_df: pd.DataFrame) -> Dict[str, Any]:
    if reviewed_df is None or reviewed_df.empty:
        return {}

    df = normalize_candidate_dataframe(reviewed_df)
    df = df[(df["approve"] == True) & (df["reject"] == False)]

    if df.empty:
        return {}

    # For duplicate fields, use highest source priority + confidence
    df = df.sort_values(
        by=["scorecard_key", "source_priority", "confidence"],
        ascending=[True, False, False],
    )

    inputs: Dict[str, Any] = {}
    for _, row in df.iterrows():
        key = row.get("scorecard_key")
        if not key or key in inputs:
            continue
        inputs[key] = row.get("final_value")

    return inputs


def missing_data_tracker(approved_inputs: Dict[str, Any]) -> pd.DataFrame:
    rows = []
    approved_inputs = approved_inputs or {}

    for field in REQUIRED_SCORECARD_FIELDS:
        key = field["scorecard_key"]
        value = approved_inputs.get(key)

        is_missing = value in [None, "", "None"]

        rows.append(
            {
                "category": field["category"],
                "scorecard_field": field["scorecard_field"],
                "scorecard_key": key,
                "status": "Missing" if is_missing else "Available",
                "current_value": value,
                "required": field["required"],
            }
        )

    return pd.DataFrame(rows)


def source_priority_table() -> pd.DataFrame:
    rows = []
    for source, priority in SOURCE_PRIORITY.items():
        rows.append({"source_type": source, "priority_score": priority})
    return pd.DataFrame(rows).sort_values("priority_score", ascending=False)


def build_reliability_summary(reviewed_df: pd.DataFrame, approved_inputs: Dict[str, Any]) -> Dict[str, Any]:
    candidates = normalize_candidate_dataframe(reviewed_df)
    missing_df = missing_data_tracker(approved_inputs)

    return {
        "total_candidates": int(len(candidates)),
        "approved_candidates": int((candidates["approve"] == True).sum()) if not candidates.empty else 0,
        "rejected_candidates": int((candidates["reject"] == True).sum()) if not candidates.empty else 0,
        "high_confidence_candidates": int((candidates["confidence_label"] == "High").sum()) if not candidates.empty else 0,
        "medium_confidence_candidates": int((candidates["confidence_label"] == "Medium").sum()) if not candidates.empty else 0,
        "low_confidence_candidates": int((candidates["confidence_label"] == "Low").sum()) if not candidates.empty else 0,
        "available_required_fields": int((missing_df["status"] == "Available").sum()),
        "missing_required_fields": int((missing_df["status"] == "Missing").sum()),
    }
