# modules/scoring_special_assessment.py
"""
Special Assessment Debt Scorecard Engine

Structured analyst-support implementation of a Special Assessment Debt workflow:

1. Economic Fundamentals Assessment
2. District Characteristics Assessment
3. Financial Profile Assessment / Maximum Loss-to-Maturity (MLTM) Matrix
4. Factor Score Weighted Average
5. Initial Indicative Rating
6. Overriding Factors / Caps / Holistic Analysis placeholders

Important:
This is a prototype analytical tool. It is not an official S&P model.
"""

from typing import Any, Dict, Optional


SPECIAL_ASSESSMENT_FACTOR_WEIGHTS = {
    "Economic Fundamentals Assessment": 0.15,
    "District Characteristics Assessment": 0.35,
    "Financial Profile Assessment": 0.50,
}

ECONOMIC_FUNDAMENTALS_SUBFACTOR_WEIGHTS = {
    "Household Income Levels": 0.20,
    "Unemployment Rate": 0.20,
    "Participation in Broad and Diverse MSA": 0.20,
    "Real Estate Market Characteristics": 0.20,
    "Population Trends": 0.20,
}

DISTRICT_CHARACTERISTICS_SUBFACTOR_WEIGHTS = {
    "Top 10 Taxpayers as % of Total Levy": 0.25,
    "Conveyance to Homeowners / Development Status": 0.25,
    "Largest Taxpayer as % of Total Levy": 0.20,
    "District Size (Parcels)": 0.15,
    "Estimated Value-to-Lien Ratio": 0.15,
}

INITIAL_INDICATIVE_RATING_SCALE = [
    (1.00, 1.30, "aaa"),
    (1.30, 1.60, "aa+"),
    (1.60, 1.90, "aa"),
    (1.90, 2.20, "aa-"),
    (2.20, 2.50, "a+"),
    (2.50, 2.80, "a"),
    (2.80, 3.10, "a-"),
    (3.10, 3.40, "bbb+"),
    (3.40, 3.70, "bbb"),
    (3.70, 4.00, "bbb-"),
    (4.00, 4.25, "bb+"),
    (4.25, 4.50, "bb"),
    (4.50, 4.75, "bb-"),
    (4.75, 5.01, "b category"),
]

RATING_LADDER = [
    "aaa", "aa+", "aa", "aa-", "a+", "a", "a-",
    "bbb+", "bbb", "bbb-", "bb+", "bb", "bb-", "b category"
]


def safe_float(value: Any, default: float = 3.0) -> float:
    try:
        if value is None or value == "":
            return float(default)
        return float(value)
    except Exception:
        return float(default)


def normalize_text(value: Any) -> str:
    return str(value).lower().strip().replace(" ", "_").replace("-", "_").replace("/", "_")


def assessment_to_category(numeric_assessment: float) -> str:
    if numeric_assessment <= 1.5:
        return "Very Strong"
    if numeric_assessment <= 2.5:
        return "Strong"
    if numeric_assessment <= 3.5:
        return "Adequate"
    if numeric_assessment <= 4.5:
        return "Weak"
    return "Very Weak"


def notch_rating(rating: str, notches: int) -> str:
    """
    Positive notches improve the rating.
    Negative notches weaken the rating.
    """
    if rating not in RATING_LADDER:
        return rating

    current_index = RATING_LADDER.index(rating)
    new_index = current_index - notches
    new_index = max(0, min(new_index, len(RATING_LADDER) - 1))
    return RATING_LADDER[new_index]


def apply_rating_cap(rating: str, cap: Optional[str]) -> str:
    """
    Apply a rating cap by preventing the rating from being better than the cap.
    Example: cap='bb' means aaa through bb+ are capped at bb.
    """
    if not cap or cap == "None":
        return rating
    if rating not in RATING_LADDER or cap not in RATING_LADDER:
        return rating

    rating_index = RATING_LADDER.index(rating)
    cap_index = RATING_LADDER.index(cap)

    if rating_index < cap_index:
        return cap
    return rating


# ---------------------------------------------------------------------
# A. Economic Fundamentals Assessment
# ---------------------------------------------------------------------

def assess_household_income_levels(median_household_ebi_percent_of_us: Any) -> int:
    """
    Median household effective buying income as % of U.S.
    """
    value = safe_float(median_household_ebi_percent_of_us, default=100)

    if value >= 150:
        return 1
    if value >= 110:
        return 2
    if value >= 85:
        return 3
    if value >= 70:
        return 4
    return 5


def assess_unemployment_rate(unemployment_rate_difference_vs_us: Any) -> int:
    """
    Local unemployment rate minus national unemployment rate.
    Example: local 3%, U.S. 5% => -2.
    """
    delta = safe_float(unemployment_rate_difference_vs_us, default=0)

    if delta <= -2:
        return 1
    if delta <= -1:
        return 2
    if delta <= 1:
        return 3
    if delta <= 2:
        return 4
    return 5


def assess_msa_participation(msa_participation: Any) -> int:
    """
    Options:
    - broad_diverse_msa
    - moderate_msa
    - not_broad_diverse_msa
    - not_in_msa
    """
    status = normalize_text(msa_participation)

    mapping = {
        "broad_diverse_msa": 1,
        "broad_and_diverse_msa": 1,
        "broad_diverse": 1,
        "moderate_msa": 2,
        "moderate": 2,
        "not_broad_diverse_msa": 3,
        "not_broad_and_diverse_msa": 3,
        "not_broad_diverse": 3,
        "not_in_msa": 4,
        "not_part_of_msa": 4,
        "not_part_of_an_msa": 4,
    }

    return mapping.get(status, 3)


def assess_real_estate_market_characteristics(real_estate_market_characteristics: Any) -> int:
    """
    Options:
    - stable_low_volatility
    - stable_moderate
    - elevated_volatility
    - falling_prices
    - distressed
    """
    status = normalize_text(real_estate_market_characteristics)

    mapping = {
        "stable_low_volatility": 1,
        "low_volatility": 1,
        "stable_moderate": 2,
        "stable": 2,
        "elevated_volatility": 3,
        "average": 3,
        "falling_prices": 4,
        "falling_local_home_prices": 4,
        "distressed": 5,
        "high_distress": 5,
    }

    return mapping.get(status, 3)


def assess_population_trends(population_growth_difference_vs_us: Any) -> int:
    """
    Local population growth minus U.S. population growth.
    Positive means growing faster than the U.S.
    """
    delta = safe_float(population_growth_difference_vs_us, default=0)

    if delta > 0:
        return 1
    if delta == 0:
        return 2
    if delta > -2:
        return 3
    if delta > -5:
        return 4
    return 5


def calculate_economic_fundamentals_assessment(inputs: Dict[str, Any]) -> Dict[str, Any]:
    income_assessment = assess_household_income_levels(
        inputs.get("median_household_ebi_percent_of_us", inputs.get("ebi_percent_of_us", 100))
    )
    unemployment_assessment = assess_unemployment_rate(
        inputs.get("unemployment_rate_difference_vs_us", inputs.get("unemployment_delta_vs_us", 0))
    )
    msa_assessment = assess_msa_participation(
        inputs.get("msa_participation", inputs.get("msa_status", "not_broad_diverse_msa"))
    )
    real_estate_assessment = assess_real_estate_market_characteristics(
        inputs.get("real_estate_market_characteristics", inputs.get("real_estate_status", "stable_moderate"))
    )
    population_assessment = assess_population_trends(
        inputs.get("population_growth_difference_vs_us", inputs.get("population_growth_vs_us", 0))
    )

    numeric_assessment = (
        income_assessment * ECONOMIC_FUNDAMENTALS_SUBFACTOR_WEIGHTS["Household Income Levels"]
        + unemployment_assessment * ECONOMIC_FUNDAMENTALS_SUBFACTOR_WEIGHTS["Unemployment Rate"]
        + msa_assessment * ECONOMIC_FUNDAMENTALS_SUBFACTOR_WEIGHTS["Participation in Broad and Diverse MSA"]
        + real_estate_assessment * ECONOMIC_FUNDAMENTALS_SUBFACTOR_WEIGHTS["Real Estate Market Characteristics"]
        + population_assessment * ECONOMIC_FUNDAMENTALS_SUBFACTOR_WEIGHTS["Population Trends"]
    )

    numeric_assessment = round(numeric_assessment, 2)

    return {
        "household_income_levels_assessment": income_assessment,
        "unemployment_rate_assessment": unemployment_assessment,
        "msa_participation_assessment": msa_assessment,
        "real_estate_market_characteristics_assessment": real_estate_assessment,
        "population_trends_assessment": population_assessment,
        "economic_fundamentals_assessment": numeric_assessment,
        "economic_fundamentals_assessment_category": assessment_to_category(numeric_assessment),
    }


# ---------------------------------------------------------------------
# B. District Characteristics Assessment
# ---------------------------------------------------------------------

def assess_top10_taxpayers_percent_of_total_levy(top10_taxpayers_percent_of_total_levy: Any) -> int:
    value = safe_float(top10_taxpayers_percent_of_total_levy, default=25)

    if value < 5:
        return 1
    if value <= 15:
        return 2
    if value <= 25:
        return 3
    if value <= 40:
        return 4
    return 5


def assess_conveyance_to_homeowners_development_status(conveyance_development_status: Any) -> int:
    status = normalize_text(conveyance_development_status)

    mapping = {
        "built_out_all_end_users": 1,
        "all_or_nearly_all_conveyed": 1,
        "substantially_built_out": 1,
        "built_out_most_end_users": 2,
        "most_conveyed": 2,
        "mostly_built_out": 2,
        "mature_some_developer_concentration": 3,
        "fairly_developed": 3,
        "mixed": 3,
        "majority_developed_significant_undeveloped": 4,
        "developed_significant_undeveloped": 4,
        "new_majority_undeveloped": 5,
        "undeveloped": 5,
        "limited_vertical_construction": 5,
    }

    return mapping.get(status, 3)


def assess_largest_taxpayer_percent_of_total_levy(largest_taxpayer_percent_of_total_levy: Any) -> int:
    value = safe_float(largest_taxpayer_percent_of_total_levy, default=8)

    if value <= 1:
        return 1
    if value <= 3:
        return 2
    if value <= 8:
        return 3
    if value <= 15:
        return 4
    return 5


def assess_district_size_parcels(district_size_parcels: Any) -> int:
    parcels = safe_float(district_size_parcels, default=1000)

    if parcels > 4000:
        return 1
    if parcels >= 1500:
        return 2
    if parcels >= 400:
        return 3
    if parcels >= 200:
        return 4
    return 5


def assess_estimated_value_to_lien_ratio(estimated_value_to_lien_ratio: Any) -> int:
    ratio = safe_float(estimated_value_to_lien_ratio, default=10)

    if ratio > 40:
        return 1
    if ratio >= 20:
        return 2
    if ratio >= 10:
        return 3
    if ratio >= 5:
        return 4
    return 5


def calculate_district_characteristics_assessment(inputs: Dict[str, Any]) -> Dict[str, Any]:
    top10_assessment = assess_top10_taxpayers_percent_of_total_levy(
        inputs.get("top10_taxpayers_percent_of_total_levy", inputs.get("top10_taxpayer_percent_of_levy", 25))
    )
    conveyance_assessment = assess_conveyance_to_homeowners_development_status(
        inputs.get("conveyance_to_homeowners_development_status", inputs.get("development_status", "mature_some_developer_concentration"))
    )
    largest_taxpayer_assessment = assess_largest_taxpayer_percent_of_total_levy(
        inputs.get("largest_taxpayer_percent_of_total_levy", inputs.get("largest_taxpayer_percent_of_levy", 8))
    )
    district_size_assessment = assess_district_size_parcels(
        inputs.get("district_size_parcels", inputs.get("number_of_parcels", 1000))
    )
    value_to_lien_assessment = assess_estimated_value_to_lien_ratio(
        inputs.get("estimated_value_to_lien_ratio", inputs.get("value_to_lien_ratio", 10))
    )

    numeric_assessment = (
        top10_assessment * DISTRICT_CHARACTERISTICS_SUBFACTOR_WEIGHTS["Top 10 Taxpayers as % of Total Levy"]
        + conveyance_assessment * DISTRICT_CHARACTERISTICS_SUBFACTOR_WEIGHTS["Conveyance to Homeowners / Development Status"]
        + largest_taxpayer_assessment * DISTRICT_CHARACTERISTICS_SUBFACTOR_WEIGHTS["Largest Taxpayer as % of Total Levy"]
        + district_size_assessment * DISTRICT_CHARACTERISTICS_SUBFACTOR_WEIGHTS["District Size (Parcels)"]
        + value_to_lien_assessment * DISTRICT_CHARACTERISTICS_SUBFACTOR_WEIGHTS["Estimated Value-to-Lien Ratio"]
    )

    numeric_assessment = round(numeric_assessment, 2)

    return {
        "top10_taxpayers_percent_of_total_levy_assessment": top10_assessment,
        "conveyance_to_homeowners_development_status_assessment": conveyance_assessment,
        "largest_taxpayer_percent_of_total_levy_assessment": largest_taxpayer_assessment,
        "district_size_parcels_assessment": district_size_assessment,
        "estimated_value_to_lien_ratio_assessment": value_to_lien_assessment,
        "district_characteristics_assessment": numeric_assessment,
        "district_characteristics_assessment_category": assessment_to_category(numeric_assessment),
    }


# ---------------------------------------------------------------------
# C. Financial Profile Assessment
# ---------------------------------------------------------------------

def calculate_financial_profile_assessment(
    top10_taxpayers_percent_of_total_levy: Any,
    maximum_loss_to_maturity_percent: Any,
) -> Dict[str, Any]:
    """
    Financial Profile Assessment is coded as:
    Top 10 Taxpayers as % of Total Levy x Maximum Loss-to-Maturity (MLTM).
    """
    top10 = safe_float(top10_taxpayers_percent_of_total_levy, default=25)
    mltm = safe_float(maximum_loss_to_maturity_percent, default=15)

    if mltm >= 40:
        mltm_bucket = ">=40%"
    elif mltm >= 35:
        mltm_bucket = "35%-40%"
    elif mltm >= 30:
        mltm_bucket = "30%-35%"
    elif mltm >= 25:
        mltm_bucket = "25%-30%"
    elif mltm >= 20:
        mltm_bucket = "20%-25%"
    elif mltm >= 15:
        mltm_bucket = "15%-20%"
    elif mltm >= 10:
        mltm_bucket = "10%-15%"
    elif mltm >= 5:
        mltm_bucket = "5%-10%"
    else:
        mltm_bucket = "<=5%"

    if top10 <= 5:
        top10_bucket = "<=5%"
    elif top10 <= 15:
        top10_bucket = "5%-15%"
    elif top10 <= 25:
        top10_bucket = "15%-25%"
    elif top10 <= 40:
        top10_bucket = "25%-40%"
    else:
        top10_bucket = ">=40%"

    matrix = {
        "<=5%":   {">=40%": 1,   "35%-40%": 1,   "30%-35%": 1,   "25%-30%": 1.5, "20%-25%": 2,   "15%-20%": 2.5, "10%-15%": 3,   "5%-10%": 3.5, "<=5%": 4.5},
        "5%-15%":  {">=40%": 1.5, "35%-40%": 1.5, "30%-35%": 1.5, "25%-30%": 2,   "20%-25%": 2.5, "15%-20%": 3,   "10%-15%": 3.5, "5%-10%": 3.5, "<=5%": 4.5},
        "15%-25%": {">=40%": 2.5, "35%-40%": 2.5, "30%-35%": 2.5, "25%-30%": 3,   "20%-25%": 3.5, "15%-20%": 3.5, "10%-15%": 4,   "5%-10%": 4.5, "<=5%": 4.5},
        "25%-40%": {">=40%": 2.5, "35%-40%": 3.5, "30%-35%": 3.5, "25%-30%": 3.5, "20%-25%": 4,   "15%-20%": 4.5, "10%-15%": 4.5, "5%-10%": 4.5, "<=5%": 5},
        ">=40%":  {">=40%": 3.5, "35%-40%": 4,   "30%-35%": 4,   "25%-30%": 4.5, "20%-25%": 4.5, "15%-20%": 5,   "10%-15%": 5,   "5%-10%": 5,   "<=5%": 5},
    }

    numeric_assessment = matrix[top10_bucket][mltm_bucket]

    return {
        "maximum_loss_to_maturity_percent": mltm,
        "financial_profile_top10_taxpayers_bucket": top10_bucket,
        "maximum_loss_to_maturity_bucket": mltm_bucket,
        "financial_profile_assessment": numeric_assessment,
        "financial_profile_assessment_category": assessment_to_category(numeric_assessment),
    }


# ---------------------------------------------------------------------
# Overall Scorecard
# ---------------------------------------------------------------------

def calculate_factor_score_weighted_average(
    economic_fundamentals_assessment: float,
    district_characteristics_assessment: float,
    financial_profile_assessment: float,
) -> float:
    weighted_average = (
        economic_fundamentals_assessment * SPECIAL_ASSESSMENT_FACTOR_WEIGHTS["Economic Fundamentals Assessment"]
        + district_characteristics_assessment * SPECIAL_ASSESSMENT_FACTOR_WEIGHTS["District Characteristics Assessment"]
        + financial_profile_assessment * SPECIAL_ASSESSMENT_FACTOR_WEIGHTS["Financial Profile Assessment"]
    )
    return round(weighted_average, 2)


def map_factor_score_to_initial_indicative_rating(factor_score_weighted_average: float) -> str:
    for low, high, rating in INITIAL_INDICATIVE_RATING_SCALE:
        if low <= factor_score_weighted_average < high:
            return rating
    return "Not Rated"


def calculate_special_assessment_scorecard(inputs: Dict[str, Any]) -> Dict[str, Any]:
    economic_results = calculate_economic_fundamentals_assessment(inputs)
    district_results = calculate_district_characteristics_assessment(inputs)

    top10_value = inputs.get(
        "top10_taxpayers_percent_of_total_levy",
        inputs.get("top10_taxpayer_percent_of_levy", 25),
    )
    financial_results = calculate_financial_profile_assessment(
        top10_value,
        inputs.get("maximum_loss_to_maturity_percent", 15),
    )

    factor_score_weighted_average = calculate_factor_score_weighted_average(
        economic_results["economic_fundamentals_assessment"],
        district_results["district_characteristics_assessment"],
        financial_results["financial_profile_assessment"],
    )

    initial_indicative_rating = map_factor_score_to_initial_indicative_rating(
        factor_score_weighted_average
    )

    negative_override_notches = int(safe_float(inputs.get("negative_override_notches", 0), 0))
    holistic_adjustment_notches = int(safe_float(inputs.get("holistic_adjustment_notches", 0), 0))
    rating_cap = inputs.get("rating_cap", "None")

    rating_after_overriding_factors = notch_rating(initial_indicative_rating, -negative_override_notches)
    rating_after_holistic_analysis = notch_rating(rating_after_overriding_factors, holistic_adjustment_notches)
    indicative_rating = apply_rating_cap(rating_after_holistic_analysis, rating_cap)

    return {
        **economic_results,
        **district_results,
        **financial_results,
        "factor_score_weighted_average": factor_score_weighted_average,
        "initial_indicative_rating": initial_indicative_rating,
        "negative_override_notches": negative_override_notches,
        "holistic_adjustment_notches": holistic_adjustment_notches,
        "rating_cap": rating_cap,
        "rating_after_overriding_factors": rating_after_overriding_factors,
        "rating_after_holistic_analysis": rating_after_holistic_analysis,
        "indicative_rating": indicative_rating,

        # Backward-compatible aliases for older UI/code
        "weighted_score": factor_score_weighted_average,
        "final_indicative_rating": indicative_rating,
        "economic_fundamentals_score": economic_results["economic_fundamentals_assessment"],
        "district_characteristics_score": district_results["district_characteristics_assessment"],
        "financial_profile_score": financial_results["financial_profile_assessment"],
    }
