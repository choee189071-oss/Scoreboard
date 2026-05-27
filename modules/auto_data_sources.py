# modules/auto_data_sources.py
"""
Auto data source connectors for the Municipal Credit Analytics Platform.

This module focuses on relatively stable / structured data sources:
- Census / ACS for income and population
- BLS placeholder for unemployment
- FRED placeholder for macro rates / unemployment proxy
- County open data placeholder
- Housing data placeholder

The design goal:
Use automatic connectors for stable, structured data.
Use document upload + AI extraction for complex PDF-heavy deal-specific data.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import pandas as pd
import requests


def safe_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def fetch_json(url: str, timeout: int = 20) -> Any:
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    return response.json()


def get_census_acs_profile(
    state_fips: str,
    place_or_county: str,
    geography_type: str = "county",
    year: int = 2023,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Fetch ACS 5-year profile values.

    geography_type:
    - "county": place_or_county should be county FIPS, e.g. Sacramento County = "067"
    - "place": place_or_county should be place FIPS

    Variables:
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

    url = f"{base}?{urlencode(params)}"
    data = fetch_json(url)

    header = data[0]
    row = data[1]
    record = dict(zip(header, row))

    return {
        "source": "Census ACS 5-year Profile",
        "source_url": url,
        "name": record.get("NAME"),
        "median_household_income": safe_float(record.get("DP03_0062E")),
        "population": safe_float(record.get("DP05_0001E")),
        "raw": record,
    }


def get_us_acs_profile(year: int = 2023, api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Fetch U.S. ACS 5-year profile values for comparison.
    """
    base = f"https://api.census.gov/data/{year}/acs/acs5/profile"
    variables = "NAME,DP03_0062E,DP05_0001E"

    params = {
        "get": variables,
        "for": "us:1",
    }

    if api_key:
        params["key"] = api_key

    url = f"{base}?{urlencode(params)}"
    data = fetch_json(url)

    header = data[0]
    row = data[1]
    record = dict(zip(header, row))

    return {
        "source": "Census ACS 5-year Profile",
        "source_url": url,
        "name": record.get("NAME"),
        "median_household_income": safe_float(record.get("DP03_0062E")),
        "population": safe_float(record.get("DP05_0001E")),
        "raw": record,
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
) -> Dict[str, Any]:
    """
    Returns local income/population, U.S. benchmark, and local income as % of U.S.
    """
    local = get_census_acs_profile(
        state_fips=state_fips,
        place_or_county=place_or_county,
        geography_type=geography_type,
        year=year,
        api_key=api_key,
    )

    us = get_us_acs_profile(year=year, api_key=api_key)

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
        "local_name": local.get("name"),
        "source_url": local.get("source_url"),
        "us_source_url": us.get("source_url"),
        "notes": "EBI proxy calculated as local median household income divided by U.S. median household income.",
    }


def get_fred_series_latest(series_id: str, api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Fetch latest observation from FRED.

    Requires FRED_API_KEY for live use.
    """
    api_key = api_key or os.getenv("FRED_API_KEY")

    if not api_key:
        return {
            "data_source": "FRED",
            "series_id": series_id,
            "status": "missing_api_key",
            "value": None,
            "source_url": f"https://fred.stlouisfed.org/series/{series_id}",
            "notes": "Add FRED_API_KEY to enable live FRED pulls.",
        }

    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "sort_order": "desc",
        "limit": 1,
    }

    response = requests.get(url, params=params, timeout=20)
    response.raise_for_status()
    data = response.json()
    obs = data.get("observations", [{}])[0]

    return {
        "data_source": "FRED",
        "series_id": series_id,
        "status": "success",
        "date": obs.get("date"),
        "value": safe_float(obs.get("value")),
        "source_url": f"https://fred.stlouisfed.org/series/{series_id}",
        "notes": "Latest available FRED observation.",
    }


def get_bls_unemployment_placeholder(local_area_name: str = "") -> Dict[str, Any]:
    """
    Placeholder for BLS LAUS integration.

    BLS local unemployment requires correct area series IDs.
    This function makes the workflow explicit without pretending the connector is complete.
    """
    return {
        "data_source": "BLS / LAUS",
        "target_data": "Unemployment",
        "status": "placeholder",
        "local_area_name": local_area_name,
        "unemployment_rate_difference_vs_us": None,
        "source_url": "https://www.bls.gov/lau/",
        "notes": "Needs LAUS series mapping. For now, enter local vs U.S. unemployment manually or upload appendix.",
    }


def get_county_open_data_placeholder(county_name: str = "") -> Dict[str, Any]:
    return {
        "data_source": "County Open Data / Assessor",
        "target_data": "Assessed value",
        "status": "placeholder",
        "county_name": county_name,
        "assessed_value": None,
        "source_url": "",
        "notes": "County assessor data formats vary. Use document upload or configure county-specific connectors.",
    }


def get_housing_data_placeholder(location_name: str = "") -> Dict[str, Any]:
    return {
        "data_source": "Housing Data",
        "target_data": "Housing market trend / distress proxy",
        "status": "placeholder",
        "location_name": location_name,
        "real_estate_market_volatility": None,
        "source_url": "",
        "notes": "Use manual review or document upload until a stable housing data source is selected.",
    }


def auto_pull_structured_data(
    state_fips: str,
    place_or_county: str,
    geography_type: str,
    county_name: str,
    location_name: str,
    census_year: int = 2023,
    census_api_key: Optional[str] = None,
    fred_api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Unified auto data pull for stable/structured sources.
    """
    results: List[Dict[str, Any]] = []
    approved_inputs: Dict[str, Any] = {}

    try:
        census_bundle = get_census_income_population_bundle(
            state_fips=state_fips,
            place_or_county=place_or_county,
            geography_type=geography_type,
            year=census_year,
            api_key=census_api_key,
        )
        results.append(census_bundle)

        if census_bundle.get("median_household_ebi_percent_of_us") is not None:
            approved_inputs["median_household_ebi_percent_of_us"] = census_bundle["median_household_ebi_percent_of_us"]

    except Exception as exc:
        results.append(
            {
                "data_source": "Census / ACS",
                "target_data": "Income, population",
                "status": "error",
                "notes": str(exc),
            }
        )

    # FRED examples: national unemployment and Treasury yield placeholders.
    results.append(get_fred_series_latest("UNRATE", api_key=fred_api_key))
    results.append(get_fred_series_latest("DGS10", api_key=fred_api_key))

    results.append(get_bls_unemployment_placeholder(local_area_name=location_name))
    results.append(get_county_open_data_placeholder(county_name=county_name))
    results.append(get_housing_data_placeholder(location_name=location_name))

    return {
        "results": results,
        "approved_inputs": approved_inputs,
    }


def auto_data_results_to_dataframe(results: List[Dict[str, Any]]) -> pd.DataFrame:
    if not results:
        return pd.DataFrame()

    rows = []
    for item in results:
        rows.append(
            {
                "Data Source": item.get("data_source"),
                "Target Data": item.get("target_data", item.get("series_id")),
                "Status": item.get("status"),
                "Extracted / Calculated Value": (
                    item.get("median_household_ebi_percent_of_us")
                    if item.get("median_household_ebi_percent_of_us") is not None
                    else item.get("value")
                ),
                "Source URL": item.get("source_url"),
                "Notes": item.get("notes"),
            }
        )

    return pd.DataFrame(rows)
