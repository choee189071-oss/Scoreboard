# modules/scoring_special_assessment.py
"""
S&P Special Assessment Scorecard Engine

This module converts the Special Assessment framework into a structured scoring engine.

Important note:
This is an internal analytical approximation based on the visible S&P criteria framework.
It is not an official S&P model and should be used as an analyst-support tool, not as a
replacement for professional credit judgment.
"""

SPECIAL_ASSESSMENT_WEIGHTS = {
    "Economic Fundamentals": 0.15,
    "District Characteristics": 0.35,
    "Financial Profile": 0.50,
}

ECONOMIC_SUBFACTOR_WEIGHTS = {
    "Income": 0.20,
    "Unemployment": 0.20,
    "MSA": 0.20,
    "Real Estate Market": 0.20,
    "Population Trend": 0.20,
}

DISTRICT_SUBFACTOR_WEIGHTS = {
    "Top 10 Taxpayer Concentration": 0.25,
    "Development Status": 0.25,
    "Largest Taxpayer Exposure": 0.20,
    "District Size": 0.15,
    "Value To Lien": 0.15,
}

RATING_SCALE = [
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


def safe_float(value, default=3.0):
    """Convert value to float safely."""
    try:
        if value is None or value == "":
            return float(default)
        return float(value)
    except Exception:
        return float(default)


# ---------------------------------------------------------------------
# A. Economic Fundamentals
# ---------------------------------------------------------------------

def score_income(ebi_percent_of_us):
    """
    Median household effective buying income as % of U.S.
    Very Strong: >=150
    Strong: 110-150
    Adequate: 85-110
    Weak: 70-85
    Very Weak: <70
    """
    ebi = safe_float(ebi_percent_of_us, default=100)

    if ebi >= 150:
        return 1
    if ebi >= 110:
        return 2
    if ebi >= 85:
        return 3
    if ebi >= 70:
        return 4
    return 5


def score_unemployment(unemployment_delta_vs_us):
    """
    Local unemployment rate minus national unemployment rate.
    Example: local 3%, U.S. 5% => -2.
    """
    delta = safe_float(unemployment_delta_vs_us, default=0)

    if delta <= -2:
        return 1
    if delta <= -1:
        return 2
    if delta <= 1:
        return 3
    if delta <= 2:
        return 4
    return 5


def score_msa(msa_status):
    """
    MSA status options:
    - broad_diverse
    - moderate
    - not_broad_diverse
    - not_in_msa
    """
    status = str(msa_status).lower().strip()

    mapping = {
        "broad_diverse": 1,
        "broad and diverse": 1,
        "strong_msa": 1,
        "moderate": 2,
        "not_broad_diverse": 3,
        "not broad and diverse": 3,
        "not_in_msa": 4,
        "not part of msa": 4,
        "not part of an msa": 4,
    }

    return mapping.get(status, 3)


def score_real_estate_market(real_estate_status):
    """
    Real estate market status options:
    - stable_low_volatility
    - stable_moderate
    - elevated_volatility
    - falling_prices
    - distressed
    """
    status = str(real_estate_status).lower().strip()

    mapping = {
        "stable_low_volatility": 1,
        "low_volatility": 1,
        "stable_moderate": 2,
        "stable": 2,
        "elevated_volatility": 3,
        "average": 3,
        "falling_prices": 4,
        "falling local home prices": 4,
        "distressed": 5,
        "high_distress": 5,
    }

    return mapping.get(status, 3)


def score_population_trend(population_growth_vs_us):
    """
    Local population growth minus U.S. population growth.
    Positive means growing faster than the U.S.
    """
    growth_delta = safe_float(population_growth_vs_us, default=0)

    if growth_delta > 0:
        return 1
    if growth_delta == 0:
        return 2
    if growth_delta > -2:
        return 3
    if growth_delta > -5:
        return 4
    return 5


def calculate_economic_fundamentals_score(inputs):
    income_score = score_income(inputs.get("ebi_percent_of_us", 100))
    unemployment_score = score_unemployment(inputs.get("unemployment_delta_vs_us", 0))
    msa_score = score_msa(inputs.get("msa_status", "not_broad_diverse"))
    real_estate_score = score_real_estate_market(
        inputs.get("real_estate_status", "stable_moderate")
    )
    population_score = score_population_trend(
        inputs.get("population_growth_vs_us", 0)
    )

    economic_score = (
        income_score * ECONOMIC_SUBFACTOR_WEIGHTS["Income"]
        + unemployment_score * ECONOMIC_SUBFACTOR_WEIGHTS["Unemployment"]
        + msa_score * ECONOMIC_SUBFACTOR_WEIGHTS["MSA"]
        + real_estate_score * ECONOMIC_SUBFACTOR_WEIGHTS["Real Estate Market"]
        + population_score * ECONOMIC_SUBFACTOR_WEIGHTS["Population Trend"]
    )

    return {
        "income_score": income_score,
        "unemployment_score": unemployment_score,
        "msa_score": msa_score,
        "real_estate_score": real_estate_score,
        "population_score": population_score,
        "economic_fundamentals_score": round(economic_score, 2),
    }


# ---------------------------------------------------------------------
# B. District Characteristics
# ---------------------------------------------------------------------

def score_top10_taxpayer_concentration(top10_percent_of_levy):
    """
    Top 10 taxpayers as % of levy.
    Very Strong: <5
    Strong: 5-15
    Adequate: 15-25
    Weak: 25-40
    Very Weak: >40
    """
    x = safe_float(top10_percent_of_levy, default=25)

    if x < 5:
        return 1
    if x <= 15:
        return 2
    if x <= 25:
        return 3
    if x <= 40:
        return 4
    return 5


def score_development_status(development_status):
    """
    Development status options:
    - built_out_all_end_users
    - built_out_most_end_users
    - mature_some_developer_concentration
    - majority_developed_significant_undeveloped
    - new_majority_undeveloped
    """
    status = str(development_status).lower().strip()

    mapping = {
        "built_out_all_end_users": 1,
        "built_out_most_end_users": 2,
        "mature_some_developer_concentration": 3,
        "majority_developed_significant_undeveloped": 4,
        "new_majority_undeveloped": 5,
    }

    return mapping.get(status, 3)


def score_largest_taxpayer_exposure(largest_taxpayer_percent_of_levy):
    """
    Largest taxpayer as % of levy.
    Very Strong: <=1
    Strong: 1-3
    Adequate: 3-8
    Weak: 8-15
    Very Weak: >15
    """
    x = safe_float(largest_taxpayer_percent_of_levy, default=8)

    if x <= 1:
        return 1
    if x <= 3:
        return 2
    if x <= 8:
        return 3
    if x <= 15:
        return 4
    return 5


def score_district_size(number_of_parcels):
    """
    Number of parcels.
    Very Strong: >4000
    Strong: 1500-4000
    Adequate: 400-1500
    Weak: 200-400
    Very Weak: <200
    """
    parcels = safe_float(number_of_parcels, default=1000)

    if parcels > 4000:
        return 1
    if parcels >= 1500:
        return 2
    if parcels >= 400:
        return 3
    if parcels >= 200:
        return 4
    return 5


def score_value_to_lien(vtl_ratio):
    """
    Overall value-to-lien ratio.
    Very Strong: >40x
    Strong: 20x-40x
    Adequate: 10x-20x
    Weak: 5x-10x
    Very Weak: <5x
    """
    vtl = safe_float(vtl_ratio, default=10)

    if vtl > 40:
        return 1
    if vtl >= 20:
        return 2
    if vtl >= 10:
        return 3
    if vtl >= 5:
        return 4
    return 5


def calculate_district_characteristics_score(inputs):
    top10_score = score_top10_taxpayer_concentration(
        inputs.get("top10_taxpayer_percent_of_levy", 25)
    )
    development_score = score_development_status(
        inputs.get("development_status", "mature_some_developer_concentration")
    )
    largest_taxpayer_score = score_largest_taxpayer_exposure(
        inputs.get("largest_taxpayer_percent_of_levy", 8)
    )
    district_size_score = score_district_size(
        inputs.get("number_of_parcels", 1000)
    )
    vtl_score = score_value_to_lien(
        inputs.get("value_to_lien_ratio", 10)
    )

    district_score = (
        top10_score * DISTRICT_SUBFACTOR_WEIGHTS["Top 10 Taxpayer Concentration"]
        + development_score * DISTRICT_SUBFACTOR_WEIGHTS["Development Status"]
        + largest_taxpayer_score * DISTRICT_SUBFACTOR_WEIGHTS["Largest Taxpayer Exposure"]
        + district_size_score * DISTRICT_SUBFACTOR_WEIGHTS["District Size"]
        + vtl_score * DISTRICT_SUBFACTOR_WEIGHTS["Value To Lien"]
    )

    return {
        "top10_taxpayer_concentration_score": top10_score,
        "development_status_score": development_score,
        "largest_taxpayer_exposure_score": largest_taxpayer_score,
        "district_size_score": district_size_score,
        "value_to_lien_score": vtl_score,
        "district_characteristics_score": round(district_score, 2),
    }


# ---------------------------------------------------------------------
# C. Financial Profile
# ---------------------------------------------------------------------

def score_financial_profile(top10_percent_of_levy, maximum_loss_to_maturity_percent):
    """
    Financial Profile is scored using a matrix:
    Top 10 taxpayer concentration x Maximum Loss to Maturity (MLTM).

    Numeric translation:
    Very Strong = 1
    Strong = 2
    Adequate = 3
    Weak = 4
    Very Weak = 5
    Mixed categories use midpoint scores.
    """
    top10 = safe_float(top10_percent_of_levy, default=25)
    mltm = safe_float(maximum_loss_to_maturity_percent, default=15)

    # MLTM bucket
    if mltm >= 40:
        mltm_bucket = ">=40"
    elif mltm >= 35:
        mltm_bucket = "35-40"
    elif mltm >= 30:
        mltm_bucket = "30-35"
    elif mltm >= 25:
        mltm_bucket = "25-30"
    elif mltm >= 20:
        mltm_bucket = "20-25"
    elif mltm >= 15:
        mltm_bucket = "15-20"
    elif mltm >= 10:
        mltm_bucket = "10-15"
    elif mltm >= 5:
        mltm_bucket = "5-10"
    else:
        mltm_bucket = "<=5"

    # Top 10 taxpayer bucket
    if top10 <= 5:
        top10_bucket = "<=5"
    elif top10 <= 15:
        top10_bucket = "5-15"
    elif top10 <= 25:
        top10_bucket = "15-25"
    elif top10 <= 40:
        top10_bucket = "25-40"
    else:
        top10_bucket = ">=40"

    matrix = {
        "<=5": {
            ">=40": 1,
            "35-40": 1,
            "30-35": 1,
            "25-30": 1.5,
            "20-25": 2,
            "15-20": 2.5,
            "10-15": 3,
            "5-10": 3.5,
            "<=5": 4.5,
        },
        "5-15": {
            ">=40": 1.5,
            "35-40": 1.5,
            "30-35": 1.5,
            "25-30": 2,
            "20-25": 2.5,
            "15-20": 3,
            "10-15": 3.5,
            "5-10": 3.5,
            "<=5": 4.5,
        },
        "15-25": {
            ">=40": 2.5,
            "35-40": 2.5,
            "30-35": 2.5,
            "25-30": 3,
            "20-25": 3.5,
            "15-20": 3.5,
            "10-15": 4,
            "5-10": 4.5,
            "<=5": 4.5,
        },
        "25-40": {
            ">=40": 2.5,
            "35-40": 3.5,
            "30-35": 3.5,
            "25-30": 3.5,
            "20-25": 4,
            "15-20": 4.5,
            "10-15": 4.5,
            "5-10": 4.5,
            "<=5": 5,
        },
        ">=40": {
            ">=40": 3.5,
            "35-40": 4,
            "30-35": 4,
            "25-30": 4.5,
            "20-25": 4.5,
            "15-20": 5,
            "10-15": 5,
            "5-10": 5,
            "<=5": 5,
        },
    }

    score = matrix[top10_bucket][mltm_bucket]

    return {
        "maximum_loss_to_maturity_percent": mltm,
        "financial_top10_taxpayer_bucket": top10_bucket,
        "mltm_bucket": mltm_bucket,
        "financial_profile_score": score,
    }


# ---------------------------------------------------------------------
# Overall Scorecard
# ---------------------------------------------------------------------

def calculate_weighted_score(
    economic_fundamentals_score,
    district_characteristics_score,
    financial_profile_score,
):
    weighted_score = (
        economic_fundamentals_score * SPECIAL_ASSESSMENT_WEIGHTS["Economic Fundamentals"]
        + district_characteristics_score * SPECIAL_ASSESSMENT_WEIGHTS["District Characteristics"]
        + financial_profile_score * SPECIAL_ASSESSMENT_WEIGHTS["Financial Profile"]
    )

    return round(weighted_score, 2)


def map_score_to_initial_indicative_rating(weighted_score):
    for low, high, rating in RATING_SCALE:
        if low <= weighted_score < high:
            return rating
    return "Not Rated"


def calculate_special_assessment_scorecard(inputs):
    economic_results = calculate_economic_fundamentals_score(inputs)
    district_results = calculate_district_characteristics_score(inputs)
    financial_results = score_financial_profile(
        inputs.get("top10_taxpayer_percent_of_levy", 25),
        inputs.get("maximum_loss_to_maturity_percent", 15),
    )

    economic_score = economic_results["economic_fundamentals_score"]
    district_score = district_results["district_characteristics_score"]
    financial_score = financial_results["financial_profile_score"]

    weighted_score = calculate_weighted_score(
        economic_score,
        district_score,
        financial_score,
    )

    initial_rating = map_score_to_initial_indicative_rating(weighted_score)

    return {
        **economic_results,
        **district_results,
        **financial_results,
        "weighted_score": weighted_score,
        "initial_indicative_rating": initial_rating,
        "final_indicative_rating": initial_rating,
    }
