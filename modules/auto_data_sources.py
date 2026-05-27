# modules/auto_data_sources.py
"""
Stable Auto Data Source Layer

This module focuses on structured, relatively reliable data sources:
- Census / ACS for income and population
- FRED for macro indicators
- BLS / county / housing as manual-required placeholders until production connectors are configured

Major improvements:
1. Better Census error handling
2. URL debug output
3. ACS year fallback
4. County/place FIPS validation
5. Expanded FRED series
6. Cleaner statuses:
   - success
   - setup_needed
   - manual_required
   - failed
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import pandas as pd
import requests


# =============================================================================
# Config
# =============================================================================

DEFAULT_FRED_SERIES = {
    "UNRATE": {
        "label": "U.S. Unemployment Rate",
        "target_data": "National unemployment",
        "unit": "%",
    },
    "DGS10": {
        "label": "10-Year Treasury Constant Maturity",
        "target_data": "Treasury rate",
        "unit": "%",
    },
    "DGS2": {
        "label": "2-Year Treasury Constant Maturity",
        "target_data": "Treasury rate",
        "unit": "%",
    },
    "DGS30": {
        "label": "30-Year Treasury Constant Maturity",
        "target_data": "Treasury rate",
        "unit": "%",
    },
    "CPIAUCSL": {
        "label": "Consumer Price Index",
        "target_data": "Inflation proxy",
        "unit": "index",
    },
    "FEDFUNDS": {
        "label": "Effective Federal Funds Rate",
        "target_data": "Policy rate",
        "unit": "%",
    },
}


# =============================================================================
# Helpers
# =============================================================================

def safe_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        if value is None or value == "":
            return default
        if isinstance(value, str) and value.strip() == ".":
            return default
        return float(value)
    except Exception:
        return default


def validate_fips(value: str, expected_length: int, label: str) -> Optional[str]:
    value = str(value).strip()

    if not re.fullmatch(r"\d+", value):
        return f"{label} must contain digits only."

    if len(value) != expected_length:
        return f"{label} should be {expected_length} digits. Current value: {value}"

    return None


def fetch_json_with_debug(url: str, timeout: int = 20) -> Dict[str, Any]:
    """
    Returns:
    {
      ok: bool,
      json: Any,
      status_code: int,
      url: str,
      text_preview: str,
      error: str
    }
    """
    try:
        response = requests.get(url, timeout=timeout)
        text_preview = response.text[:500]

        if response.status_code != 200:
            return {
                "ok": False,
                "json": None,
                "status_code": response.status_code,
                "url": url,
                "text_preview": text_preview,
                "error": f"HTTP {response.status_code}",
            }

        try:
            data = response.json()
        except Exception as exc:
            return {
                "ok": False,
                "json": None,
                "status_code": response.status_code,
                "url": url,
                "text_preview": text_preview,
                "error": f"Response was not valid JSON: {exc}",
            }

        return {
            "ok": True,
            "json": data,
            "status_code": response.status_code,
            "url": url,
            "text_preview": text_preview,
            "error": "",
        }

    except Exception as exc:
        return {
            "ok": False,
            "json": None,
            "status_code": None,
            "url": url,
            "text_preview": "",
            "error": str(exc),
        }


def make_result(
    data_source: str,
    target_data: str,
    status: str,
    value: Any = None,
    source_url: str = "",
    notes: str = "",
    **kwargs,
) -> Dict[str, Any]:
    out = {
        "data_source": data_source,
        "target_data": target_data,
        "status": status,
        "value": value,
        "source_url": source_url,
        "notes": notes,
    }
    out.update(kwargs)
    return out


# =============================================================================
# Census / ACS
# =============================================================================

def build_census_acs_url(
    state_fips: str,
    place_or_county: str,
    geography_type: str = "county",
    year: int = 2023,
    api_key: Optional[str] = None,
) -> str:
    """
    ACS 5-year profile variables:
    - DP03_0062E: Median household income
    - DP05_0001E: Total population
    """
    base = f"https://api.census.gov/data/{year}/acs/acs5/profile"
    variables = "NAME,DP03_0062E,DP05_0001E"

    if geography_type == "county":
        get_for = f"county:{place_or_county}"
    elif geography_type == "place":
        get_for = f"place:{place_or_county}"
    else:
        raise ValueError("geography_type must be 'county' or 'place'.")

    params = {
        "get": variables,
        "for": get_for,
        "in": f"state:{state_fips}",
    }

    if api_key:
        params["key"] = api_key

    return f"{base}?{urlencode(params)}"


def build_us_acs_url(year: int = 2023, api_key: Optional[str] = None) -> str:
    base = f"https://api.census.gov/data/{year}/acs/acs5/profile"
    variables = "NAME,DP03_0062E,DP05_0001E"

    params = {
        "get": variables,
        "for": "us:1",
    }

    if api_key:
        params["key"] = api_key

    return f"{base}?{urlencode(params)}"


def parse_census_profile_response(data: Any) -> Dict[str, Any]:
    if not isinstance(data, list) or len(data) < 2:
        raise ValueError("Census response did not include a data row.")

    header = data[0]
    row = data[1]
    record = dict(zip(header, row))

    return {
        "name": record.get("NAME"),
        "median_household_income": safe_float(record.get("DP03_0062E")),
        "population": safe_float(record.get("DP05_0001E")),
        "raw": record,
    }


def get_census_acs_profile(
    state_fips: str,
    place_or_county: str,
    geography_type: str = "county",
    year: int = 2023,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    state_error = validate_fips(state_fips, 2, "State FIPS")
    if state_error:
        return make_result(
            data_source="Census / ACS",
            target_data="Income, population",
            status="failed",
            notes=state_error,
        )

    geo_len = 3 if geography_type == "county" else 5
    geo_error = validate_fips(place_or_county, geo_len, "County / Place FIPS")
    if geo_error:
        return make_result(
            data_source="Census / ACS",
            target_data="Income, population",
            status="failed",
            notes=geo_error,
        )

    url = build_census_acs_url(
        state_fips=state_fips,
        place_or_county=place_or_county,
        geography_type=geography_type,
        year=year,
        api_key=api_key,
    )

    result = fetch_json_with_debug(url)

    if not result["ok"]:
        return make_result(
            data_source="Census / ACS",
            target_data="Income, population",
            status="failed",
            source_url=url,
            notes=(
                f"Census pull failed for ACS {year}. "
                f"{result['error']}. Response preview: {result['text_preview'][:180]}"
            ),
            debug_url=url,
            http_status=result.get("status_code"),
        )

    try:
        parsed = parse_census_profile_response(result["json"])
    except Exception as exc:
        return make_result(
            data_source="Census / ACS",
            target_data="Income, population",
            status="failed",
            source_url=url,
            notes=f"Census response parsed but did not contain expected fields: {exc}",
            debug_url=url,
        )

    return {
        "data_source": "Census / ACS",
        "target_data": "Income, population",
        "status": "success",
        "source_url": url,
        "notes": f"Pulled ACS {year} profile for {parsed.get('name')}.",
        "name": parsed.get("name"),
        "median_household_income": parsed.get("median_household_income"),
        "population": parsed.get("population"),
        "raw": parsed.get("raw"),
        "acs_year": year,
    }


def get_us_acs_profile(year: int = 2023, api_key: Optional[str] = None) -> Dict[str, Any]:
    url = build_us_acs_url(year=year, api_key=api_key)
    result = fetch_json_with_debug(url)

    if not result["ok"]:
        return make_result(
            data_source="Census / ACS",
            target_data="U.S. income, population benchmark",
            status="failed",
            source_url=url,
            notes=f"U.S. Census benchmark pull failed for ACS {year}: {result['error']}",
            debug_url=url,
        )

    try:
        parsed = parse_census_profile_response(result["json"])
    except Exception as exc:
        return make_result(
            data_source="Census / ACS",
            target_data="U.S. income, population benchmark",
            status="failed",
            source_url=url,
            notes=f"U.S. Census response did not contain expected fields: {exc}",
            debug_url=url,
        )

    return {
        "data_source": "Census / ACS",
        "target_data": "U.S. income, population benchmark",
        "status": "success",
        "source_url": url,
        "notes": f"Pulled ACS {year} U.S. benchmark.",
        "name": parsed.get("name"),
        "median_household_income": parsed.get("median_household_income"),
        "population": parsed.get("population"),
        "raw": parsed.get("raw"),
        "acs_year": year,
    }


def calculate_ebi_percent_of_us(local_income: Any, us_income: Any) -> Optional[float]:
    local_income = safe_float(local_income)
    us_income = safe_float(us_income)

    if not local_income or not us_income:
        return None

    return round(local_income / us_income * 100, 1)


def get_census_income_population_bundle(
    state_fips: str,
    place_or_county: str,
    geography_type: str = "county",
    year: int = 2023,
    api_key: Optional[str] = None,
    fallback_years: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """
    Pull local and U.S. ACS profile data.

    If selected year fails, try fallback years.
    """
    if fallback_years is None:
        fallback_years = [year, year - 1, year - 2, year - 3]

    attempted = []

    for candidate_year in fallback_years:
        local = get_census_acs_profile(
            state_fips=state_fips,
            place_or_county=place_or_county,
            geography_type=geography_type,
            year=candidate_year,
            api_key=api_key,
        )
        us = get_us_acs_profile(year=candidate_year, api_key=api_key)

        attempted.append(
            {
                "year": candidate_year,
                "local_status": local.get("status"),
                "us_status": us.get("status"),
                "local_notes": local.get("notes"),
                "us_notes": us.get("notes"),
                "local_url": local.get("source_url"),
                "us_url": us.get("source_url"),
            }
        )

        if local.get("status") == "success" and us.get("status") == "success":
            ebi_percent = calculate_ebi_percent_of_us(
                local.get("median_household_income"),
                us.get("median_household_income"),
            )

            return {
                "data_source": "Census / ACS",
                "target_data": "Income, population",
                "status": "success",
                "median_household_ebi_percent_of_us": ebi_percent,
                "local_median_household_income": local.get("median_household_income"),
                "us_median_household_income": us.get("median_household_income"),
                "local_population": local.get("population"),
                "us_population": us.get("population"),
                "local_name": local.get("name"),
                "source_url": local.get("source_url"),
                "us_source_url": us.get("source_url"),
                "acs_year": candidate_year,
                "notes": (
                    f"ACS {candidate_year}: EBI proxy = local median household income "
                    f"divided by U.S. median household income."
                ),
                "attempted_years": attempted,
            }

    return {
        "data_source": "Census / ACS",
        "target_data": "Income, population",
        "status": "failed",
        "median_household_ebi_percent_of_us": None,
        "source_url": attempted[0].get("local_url") if attempted else "",
        "notes": (
            "Census ACS pull failed after fallback attempts. "
            "Check State FIPS, County/Place FIPS, geography type, and ACS year."
        ),
        "attempted_years": attempted,
    }


# =============================================================================
# FRED
# =============================================================================

def get_fred_series_latest(series_id: str, api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Fetch latest observation from FRED.

    Requires FRED_API_KEY for live use.
    """
    api_key = api_key or os.getenv("FRED_API_KEY")
    meta = DEFAULT_FRED_SERIES.get(series_id, {})

    if not api_key:
        return make_result(
            data_source="FRED",
            target_data=meta.get("target_data", series_id),
            status="setup_needed",
            value=None,
            source_url=f"https://fred.stlouisfed.org/series/{series_id}",
            notes="Add FRED_API_KEY to enable live FRED pulls.",
            series_id=series_id,
            label=meta.get("label", series_id),
            unit=meta.get("unit", ""),
        )

    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "sort_order": "desc",
        "limit": 5,
    }

    try:
        response = requests.get(url, params=params, timeout=20)
        text_preview = response.text[:300]

        if response.status_code != 200:
            return make_result(
                data_source="FRED",
                target_data=meta.get("target_data", series_id),
                status="failed",
                source_url=f"https://fred.stlouisfed.org/series/{series_id}",
                notes=f"FRED returned HTTP {response.status_code}. Preview: {text_preview}",
                series_id=series_id,
                label=meta.get("label", series_id),
                unit=meta.get("unit", ""),
            )

        data = response.json()
        observations = data.get("observations", [])

        latest = None
        for obs in observations:
            value = safe_float(obs.get("value"))
            if value is not None:
                latest = obs
                break

        if latest is None:
            return make_result(
                data_source="FRED",
                target_data=meta.get("target_data", series_id),
                status="failed",
                source_url=f"https://fred.stlouisfed.org/series/{series_id}",
                notes="FRED returned observations, but no numeric value was available.",
                series_id=series_id,
                label=meta.get("label", series_id),
                unit=meta.get("unit", ""),
            )

        return make_result(
            data_source="FRED",
            target_data=meta.get("target_data", series_id),
            status="success",
            value=safe_float(latest.get("value")),
            source_url=f"https://fred.stlouisfed.org/series/{series_id}",
            notes="Latest available FRED observation.",
            series_id=series_id,
            label=meta.get("label", series_id),
            unit=meta.get("unit", ""),
            date=latest.get("date"),
        )

    except Exception as exc:
        return make_result(
            data_source="FRED",
            target_data=meta.get("target_data", series_id),
            status="failed",
            source_url=f"https://fred.stlouisfed.org/series/{series_id}",
            notes=f"FRED pull failed: {exc}",
            series_id=series_id,
            label=meta.get("label", series_id),
            unit=meta.get("unit", ""),
        )


def get_fred_bundle(
    series_ids: Optional[List[str]] = None,
    api_key: Optional[str] = None,
) -> List[Dict[str, Any]]:
    if series_ids is None:
        series_ids = ["UNRATE", "DGS10", "DGS2", "DGS30", "CPIAUCSL", "FEDFUNDS"]

    return [get_fred_series_latest(series_id, api_key=api_key) for series_id in series_ids]


# =============================================================================
# Manual-required placeholders
# =============================================================================

def get_bls_unemployment_manual_required(local_area_name: str = "") -> Dict[str, Any]:
    return make_result(
        data_source="BLS / LAUS",
        target_data="Local unemployment",
        status="manual_required",
        source_url="https://www.bls.gov/lau/",
        notes=(
            "Local unemployment requires LAUS area series mapping. "
            "For now, enter local vs U.S. unemployment manually or upload an economic appendix."
        ),
        local_area_name=local_area_name,
    )


def get_county_open_data_manual_required(county_name: str = "") -> Dict[str, Any]:
    return make_result(
        data_source="County Open Data / Assessor",
        target_data="Assessed value",
        status="manual_required",
        source_url="",
        notes=(
            "County assessor data formats vary. "
            "Use document upload for assessed value / VTL support, or configure a county-specific connector."
        ),
        county_name=county_name,
    )


def get_housing_data_manual_required(location_name: str = "") -> Dict[str, Any]:
    return make_result(
        data_source="Housing Data",
        target_data="Housing market trend / distress proxy",
        status="manual_required",
        source_url="",
        notes=(
            "Housing market condition is partly qualitative. "
            "Use manual analyst review or upload supporting housing data until a stable source is selected."
        ),
        location_name=location_name,
    )


# =============================================================================
# Unified Auto Pull
# =============================================================================

def auto_pull_structured_data(
    state_fips: str,
    place_or_county: str,
    geography_type: str,
    county_name: str,
    location_name: str,
    census_year: int = 2023,
    census_api_key: Optional[str] = None,
    fred_api_key: Optional[str] = None,
    fred_series_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    results: List[Dict[str, Any]] = []
    approved_inputs: Dict[str, Any] = {}

    census_bundle = get_census_income_population_bundle(
        state_fips=state_fips,
        place_or_county=place_or_county,
        geography_type=geography_type,
        year=census_year,
        api_key=census_api_key,
    )
    results.append(census_bundle)

    if census_bundle.get("status") == "success":
        if census_bundle.get("median_household_ebi_percent_of_us") is not None:
            approved_inputs["median_household_ebi_percent_of_us"] = census_bundle["median_household_ebi_percent_of_us"]

    results.extend(get_fred_bundle(series_ids=fred_series_ids, api_key=fred_api_key))

    results.append(get_bls_unemployment_manual_required(local_area_name=location_name))
    results.append(get_county_open_data_manual_required(county_name=county_name))
    results.append(get_housing_data_manual_required(location_name=location_name))

    return {
        "results": results,
        "approved_inputs": approved_inputs,
    }


def auto_data_results_to_dataframe(results: List[Dict[str, Any]]) -> pd.DataFrame:
    if not results:
        return pd.DataFrame()

    rows = []
    for item in results:
        extracted = None

        if item.get("median_household_ebi_percent_of_us") is not None:
            extracted = item.get("median_household_ebi_percent_of_us")
        elif item.get("value") is not None:
            extracted = item.get("value")

        if item.get("unit") and extracted is not None:
            extracted_display = f"{extracted} {item.get('unit')}"
        else:
            extracted_display = extracted

        rows.append(
            {
                "Data Source": item.get("data_source"),
                "Series / Label": item.get("label", item.get("series_id", "")),
                "Target Data": item.get("target_data", item.get("series_id")),
                "Status": item.get("status"),
                "Date / Year": item.get("date", item.get("acs_year", "")),
                "Extracted / Calculated Value": extracted_display,
                "Source URL": item.get("source_url"),
                "Notes": item.get("notes"),
            }
        )

    return pd.DataFrame(rows)
