# modules/scoring_special_assessment.py

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


def safe_float(value, default=3):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def score_income(ebi_percent_of_us):
    ebi = safe_float(ebi_percent_of_us, default=100)

    if ebi >= 150:
        return 1
    elif ebi >= 110:
        return 2
    elif ebi >= 85:
        return 3
    elif ebi >= 70:
        return 4
    else:
        return 5


def score_unemployment(unemployment_delta_vs_us):
    delta = safe_float(unemployment_delta_vs_us, default=0)

    if delta <= -2:
        return 1
    elif delta <= -1:
        return 2
    elif delta <= 1:
        return 3
    elif delta <= 2:
        return 4
    else:
        return 5


def score_msa(msa_status):
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
    growth_delta = safe_float(population_growth_vs_us, default=0)

    if growth_delta > 0:
        return 1
    elif growth_delta == 0:
        return 2
    elif growth_delta > -2:
        return 3
    elif growth_delta > -5:
        return 4
    else:
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


def map_score_to_initial_indicative_rating(weighted_score):
    for low, high, rating in RATING_SCALE:
        if low <= weighted_score < high:
            return rating

    return "Not Rated"


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


def apply_negative_overriding_factors(initial_rating, overriding_factors=None):
    return initial_rating


def apply_rating_caps(initial_rating, caps=None):
    return initial_rating


def apply_holistic_adjustment(rating_after_caps, holistic_adjustment=0):
    return rating_after_caps


def calculate_special_assessment_scorecard(inputs):
    economic_results = calculate_economic_fundamentals_score(inputs)

    economic_score = economic_results["economic_fundamentals_score"]
    district_score = safe_float(inputs.get("district_characteristics_score", 3), default=3)
    financial_score = safe_float(inputs.get("financial_profile_score", 3), default=3)

    weighted_score = calculate_weighted_score(
        economic_score,
        district_score,
        financial_score,
    )

    initial_rating = map_score_to_initial_indicative_rating(weighted_score)

    rating_after_overrides = apply_negative_overriding_factors(initial_rating)
    rating_after_caps = apply_rating_caps(rating_after_overrides)
    final_indicative_rating = apply_holistic_adjustment(rating_after_caps)

    return {
        **economic_results,
        "district_characteristics_score": district_score,
        "financial_profile_score": financial_score,
        "weighted_score": weighted_score,
        "initial_indicative_rating": initial_rating,
        "final_indicative_rating": final_indicative_rating,
    }
