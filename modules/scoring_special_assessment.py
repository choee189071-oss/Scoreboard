# modules/scoring_special_assessment.py
"""
Special Assessment Debt Scorecard Engine

This file is designed to sit inside:

    modules/scoring_special_assessment.py

It supports the Streamlit Special Assessment Debt scorecard workflow and uses
terms aligned with the sample scorecard / S&P-style methodology language.

Important:
This is a prototype analyst-support tool. It is not an official S&P model.
"""

from typing import Any, Dict, Optional


# =============================================================================
# Core Framework
# =============================================================================

SPECIAL_ASSESSMENT_FACTOR_WEIGHTS = {
    "Economic Fundamentals Assessment": 0.15,
    "District Characteristics Assessment": 0.35,
    "Financial Profile Assessment": 0.50,
}

ECONOMIC_FUNDAMENTALS_SUBFACTOR_WEIGHTS = {
    "Median Household EBI": 0.20,
    "Unemployment Rate": 0.20,
    "MSA Participation": 0.20,
    "Real Estate Market Volatility": 0.20,
    "Population Growth": 0.20,
}

DISTRICT_CHARACTERISTICS_SUBFACTOR_WEIGHTS = {
    "Top 10 Taxpayers as % of Total Levy": 0.25,
    "Conveyance to Homeowners": 0.25,
    "Largest Taxpayer as % of Total Levy": 0.20,
    "District Size (Parcels)": 0.15,
    "Est. Value-to-Lien": 0.15,
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
    "aaa",
    "aa+",
    "aa",
    "aa-",
    "a+",
    "a",
    "a-",
    "bbb+",
    "bbb",
    "bbb-",
    "bb+",
    "bb",
    "bb-",
    "b category",
]


# =============================================================================
# Utility Functions
# =============================================================================

def safe_float(value: Any, default: float = 3.0) -> float:
    """Safely convert values to float."""
    try:
        if value is None or value == "":
            return float(default)
        return float(value)
    except Exception:
        return float(default)


def normalize_text(value: Any) -> str:
    """
    Normalize labels from Streamlit dropdowns / CSV uploads.

    This allows the function to accept both:
    - human-readable scorecard terms
    - machine-readable snake_case terms
    """
    text = str(value).lower().strip()
    text = text.replace("&", "and")
    text = text.replace("/", " ")
    text = text.replace("-", " ")
    text = text.replace(";", " ")
    text = text.replace(",", " ")
    text = text.replace("(", " ")
    text = text.replace(")", " ")
    text = text.replace("%", " percent ")
    text = " ".join(text.split())
    return text.replace(" ", "_")


def assessment_to_category(numeric_assessment: float) -> str:
    """Convert numeric assessment to descriptor."""
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

    Example:
        rating = "a-"
        cap = "bb"
        output = "bb"
    """
    if not cap or cap == "None":
        return rating

    if rating not in RATING_LADDER or cap not in RATING_LADDER:
        return rating

    rating_index = RATING_LADDER.index(rating)
    cap_index = RATING_LADDER.index(cap)

    # Larger index = weaker rating.
    if rating_index < cap_index:
        return cap

    return rating


# =============================================================================
# A. Economic Fundamentals Assessment
# =============================================================================

def assess_median_household_ebi(median_household_ebi_percent_of_us: Any) -> int:
    """
    Median Household EBI as % of U.S.

    Very Strong: >150%
    Strong: 110%-150%
    Adequate: 85%-110%
    Weak: 70%-85%
    Very Weak: <70%
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

    Example:
        Local unemployment = 4.1%
        U.S. unemployment = 4.4%
        Difference = -0.3%
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
    MSA Participation.

    Accepted labels include:
    - Yes; Broad & Diverse
    - Yes; Not Broad & Diverse
    - No
    """
    status = normalize_text(msa_participation)

    mapping = {
        "yes_broad_and_diverse": 1,
        "broad_and_diverse": 1,
        "broad_diverse": 1,
        "broad_diverse_msa": 1,

        "moderate": 2,
        "moderate_msa": 2,

        "yes_not_broad_and_diverse": 3,
        "not_broad_and_diverse": 3,
        "not_broad_diverse": 3,
        "not_broad_diverse_msa": 3,

        "no": 4,
        "not_in_msa": 4,
        "not_part_of_msa": 4,
    }

    return mapping.get(status, 3)


def assess_real_estate_market_volatility(real_estate_market_volatility: Any) -> int:
    """
    Real Estate Market Volatility / Characteristics.

    Accepted scorecard-style labels include:
    - Low Volatility; Stable Prices; Low Distress
    - Elevated Volatility; Stable Prices; Affordability Worse Than National Figures
    - Falling Local Home Prices; High Price Volatility; Low Affordability; Rising Distress
    - Falling Local Home Prices; High Price Volatility; Significantly Worse Affordability; Rising Distress
    """
    status = normalize_text(real_estate_market_volatility)

    mapping = {
        "low_volatility_stable_prices_low_distress": 1,
        "stable_low_volatility": 1,
        "low_volatility": 1,

        # In the sample matrix, the "Strong" real estate box can still describe
        # low volatility / stable prices / low distress.
        "low_volatility_stable_prices_low_distress_strong": 2,
        "stable_moderate": 2,
        "stable": 2,

        "elevated_volatility_stable_prices_affordability_worse_than_national_figures": 3,
        "elevated_volatility": 3,
        "average": 3,

        "falling_local_home_prices_high_price_volatility_low_affordability_rising_distress": 4,
        "falling_prices": 4,

        "falling_local_home_prices_high_price_volatility_significantly_worse_affordability_rising_distress": 5,
        "distressed": 5,
        "high_distress": 5,
    }

    return mapping.get(status, 3)


def assess_population_growth(population_growth_difference_vs_us: Any) -> int:
    """
    Population Growth relative to U.S. growth.

    Positive = higher than national growth rate.
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
    median_household_ebi_assessment = assess_median_household_ebi(
        inputs.get("median_household_ebi_percent_of_us", inputs.get("ebi_percent_of_us", 100))
    )

    unemployment_rate_assessment = assess_unemployment_rate(
        inputs.get("unemployment_rate_difference_vs_us", inputs.get("unemployment_delta_vs_us", 0))
    )

    msa_participation_assessment = assess_msa_participation(
        inputs.get("msa_participation", inputs.get("msa_status", "Yes; Not Broad & Diverse"))
    )

    real_estate_market_volatility_assessment = assess_real_estate_market_volatility(
        inputs.get(
            "real_estate_market_volatility",
            inputs.get("real_estate_market_characteristics", inputs.get("real_estate_status", "Stable")),
        )
    )

    population_growth_assessment = assess_population_growth(
        inputs.get("population_growth_difference_vs_us", inputs.get("population_growth_vs_us", 0))
    )

    numeric_assessment = (
        median_household_ebi_assessment * ECONOMIC_FUNDAMENTALS_SUBFACTOR_WEIGHTS["Median Household EBI"]
        + unemployment_rate_assessment * ECONOMIC_FUNDAMENTALS_SUBFACTOR_WEIGHTS["Unemployment Rate"]
        + msa_participation_assessment * ECONOMIC_FUNDAMENTALS_SUBFACTOR_WEIGHTS["MSA Participation"]
        + real_estate_market_volatility_assessment * ECONOMIC_FUNDAMENTALS_SUBFACTOR_WEIGHTS["Real Estate Market Volatility"]
        + population_growth_assessment * ECONOMIC_FUNDAMENTALS_SUBFACTOR_WEIGHTS["Population Growth"]
    )

    numeric_assessment = round(numeric_assessment, 2)

    return {
        "median_household_ebi_assessment": median_household_ebi_assessment,
        "unemployment_rate_assessment": unemployment_rate_assessment,
        "msa_participation_assessment": msa_participation_assessment,
        "real_estate_market_volatility_assessment": real_estate_market_volatility_assessment,
        "population_growth_assessment": population_growth_assessment,
        "economic_fundamentals_assessment": numeric_assessment,
        "economic_fundamentals_assessment_category": assessment_to_category(numeric_assessment),
    }


# =============================================================================
# B. District Characteristics Assessment
# =============================================================================

def assess_top10_taxpayers_percent_of_total_levy(top10_taxpayers_percent_of_total_levy: Any) -> int:
    """
    Top 10 Taxpayers as % of Total Levy.

    Very Strong: <5%
    Strong: 5%-15%
    Adequate: 15%-25%
    Weak: 25%-40%
    Very Weak: >40%
    """
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


def assess_conveyance_to_homeowners(conveyance_to_homeowners: Any) -> int:
    """
    Conveyance to Homeowners / Developer Concentration.

    Accepted scorecard-style labels:
    - All or Nearly All Conveyed
    - Most Conveyed
    - Fairly Developed with Significant Conveyance (Some Developer Concentration)
    - Developed; Significant Undeveloped Parcels Comprise Minority (Large Developer Concentration)
    - Undeveloped with Limited Vertical Construction; High Concentration
    """
    status = normalize_text(conveyance_to_homeowners)

    mapping = {
        "all_or_nearly_all_conveyed": 1,
        "all_nearly_all_conveyed": 1,
        "built_out_all_end_users": 1,

        "most_conveyed": 2,
        "built_out_most_end_users": 2,

        "fairly_developed_with_significant_conveyance_some_developer_concentration": 3,
        "fairly_developed": 3,
        "mature_some_developer_concentration": 3,
        "some_developer_concentration": 3,

        "developed_significant_undeveloped_parcels_comprise_minority_large_developer_concentration": 4,
        "majority_developed_significant_undeveloped": 4,
        "large_developer_concentration": 4,

        "undeveloped_with_limited_vertical_construction_high_concentration": 5,
        "new_majority_undeveloped": 5,
        "undeveloped": 5,
        "high_concentration": 5,
    }

    return mapping.get(status, 3)


def assess_largest_taxpayer_percent_of_total_levy(largest_taxpayer_percent_of_total_levy: Any) -> int:
    """
    Largest Taxpayer as % of Total Levy.

    Very Strong: <1%
    Strong: 1%-3%
    Adequate: 3%-8%
    Weak: 8%-15%
    Very Weak: >15%
    """
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
    """
    District Size (Parcels).

    Very Strong: 4,000+
    Strong: 1,500-4,000
    Adequate: 400-1,500
    Weak: 200-400
    Very Weak: <200
    """
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


def assess_est_value_to_lien(est_value_to_lien: Any) -> int:
    """
    Est. Value-to-Lien.

    Very Strong: >40x
    Strong: 20x-40x
    Adequate: 10x-20x
    Weak: <10x
    Very Weak: <10x with significant portion of parcels carrying VTL <5x

    Because the system currently only receives a single VTL ratio, this function maps:
    5x-10x => Weak
    <5x => Very Weak
    """
    ratio = safe_float(est_value_to_lien, default=10)

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

    conveyance_assessment = assess_conveyance_to_homeowners(
        inputs.get(
            "conveyance_to_homeowners",
            inputs.get(
                "conveyance_to_homeowners_development_status",
                inputs.get("development_status", "Fairly Developed with Significant Conveyance (Some Developer Concentration)"),
            ),
        )
    )

    largest_taxpayer_assessment = assess_largest_taxpayer_percent_of_total_levy(
        inputs.get("largest_taxpayer_percent_of_total_levy", inputs.get("largest_taxpayer_percent_of_levy", 8))
    )

    district_size_assessment = assess_district_size_parcels(
        inputs.get("district_size_parcels", inputs.get("number_of_parcels", 1000))
    )

    est_value_to_lien_assessment = assess_est_value_to_lien(
        inputs.get(
            "est_value_to_lien",
            inputs.get("estimated_value_to_lien_ratio", inputs.get("value_to_lien_ratio", 10)),
        )
    )

    numeric_assessment = (
        top10_assessment * DISTRICT_CHARACTERISTICS_SUBFACTOR_WEIGHTS["Top 10 Taxpayers as % of Total Levy"]
        + conveyance_assessment * DISTRICT_CHARACTERISTICS_SUBFACTOR_WEIGHTS["Conveyance to Homeowners"]
        + largest_taxpayer_assessment * DISTRICT_CHARACTERISTICS_SUBFACTOR_WEIGHTS["Largest Taxpayer as % of Total Levy"]
        + district_size_assessment * DISTRICT_CHARACTERISTICS_SUBFACTOR_WEIGHTS["District Size (Parcels)"]
        + est_value_to_lien_assessment * DISTRICT_CHARACTERISTICS_SUBFACTOR_WEIGHTS["Est. Value-to-Lien"]
    )

    numeric_assessment = round(numeric_assessment, 2)

    return {
        "top10_taxpayers_percent_of_total_levy_assessment": top10_assessment,
        "conveyance_to_homeowners_assessment": conveyance_assessment,
        "largest_taxpayer_percent_of_total_levy_assessment": largest_taxpayer_assessment,
        "district_size_parcels_assessment": district_size_assessment,
        "est_value_to_lien_assessment": est_value_to_lien_assessment,
        "district_characteristics_assessment": numeric_assessment,
        "district_characteristics_assessment_category": assessment_to_category(numeric_assessment),
    }


# =============================================================================
# C. Financial Profile Assessment
# =============================================================================

def calculate_financial_profile_assessment(
    top10_taxpayers_percent_of_total_levy: Any,
    maximum_loss_to_maturity_percent: Any,
) -> Dict[str, Any]:
    """
    Financial Profile Assessment Matrix.

    Dimensions:
    - Top 10 Taxpayers as % of Total Levy
    - Maximum Loss-to-Maturity (MLTM) %
    """
    top10 = safe_float(top10_taxpayers_percent_of_total_levy, default=25)
    mltm = safe_float(maximum_loss_to_maturity_percent, default=15)

    # MLTM bucket
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

    # Top 10 bucket
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
        "<=5%": {
            ">=40%": 1,
            "35%-40%": 1,
            "30%-35%": 1,
            "25%-30%": 1.5,
            "20%-25%": 2,
            "15%-20%": 2.5,
            "10%-15%": 3,
            "5%-10%": 3.5,
            "<=5%": 4.5,
        },
        "5%-15%": {
            ">=40%": 1.5,
            "35%-40%": 1.5,
            "30%-35%": 1.5,
            "25%-30%": 2,
            "20%-25%": 2.5,
            "15%-20%": 3,
            "10%-15%": 3.5,
            "5%-10%": 3.5,
            "<=5%": 4.5,
        },
        "15%-25%": {
            ">=40%": 2.5,
            "35%-40%": 2.5,
            "30%-35%": 2.5,
            "25%-30%": 3,
            "20%-25%": 3.5,
            "15%-20%": 3.5,
            "10%-15%": 4,
            "5%-10%": 4.5,
            "<=5%": 4.5,
        },
        "25%-40%": {
            ">=40%": 2.5,
            "35%-40%": 3.5,
            "30%-35%": 3.5,
            "25%-30%": 3.5,
            "20%-25%": 4,
            "15%-20%": 4.5,
            "10%-15%": 4.5,
            "5%-10%": 4.5,
            "<=5%": 5,
        },
        ">=40%": {
            ">=40%": 3.5,
            "35%-40%": 4,
            "30%-35%": 4,
            "25%-30%": 4.5,
            "20%-25%": 4.5,
            "15%-20%": 5,
            "10%-15%": 5,
            "5%-10%": 5,
            "<=5%": 5,
        },
    }

    numeric_assessment = matrix[top10_bucket][mltm_bucket]

    return {
        "maximum_loss_to_maturity_percent": mltm,
        "financial_profile_top10_taxpayers_bucket": top10_bucket,
        "maximum_loss_to_maturity_bucket": mltm_bucket,
        "financial_profile_assessment": numeric_assessment,
        "financial_profile_assessment_category": assessment_to_category(numeric_assessment),
    }


# =============================================================================
# Overall Scorecard
# =============================================================================

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
    """
    Main function called by Streamlit.

    Expected main inputs:
    - median_household_ebi_percent_of_us
    - unemployment_rate_difference_vs_us
    - msa_participation
    - real_estate_market_volatility
    - population_growth_difference_vs_us
    - top10_taxpayers_percent_of_total_levy
    - conveyance_to_homeowners
    - largest_taxpayer_percent_of_total_levy
    - district_size_parcels
    - est_value_to_lien
    - maximum_loss_to_maturity_percent
    - negative_override_notches
    - holistic_adjustment_notches
    - rating_cap
    """
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

        # Backward-compatible aliases
        "weighted_score": factor_score_weighted_average,
        "final_indicative_rating": indicative_rating,
        "economic_fundamentals_score": economic_results["economic_fundamentals_assessment"],
        "district_characteristics_score": district_results["district_characteristics_assessment"],
        "financial_profile_score": financial_results["financial_profile_assessment"],
    }
