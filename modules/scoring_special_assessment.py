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


def safe_float(value, default=3):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


# -------------------------
# A. Economic Fundamentals
# -------------------------

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
        "moderate": 2,
        "not_broad_diverse": 3,
        "not_in_msa": 4,
    }

    return mapping.get(status, 3)


def score_real_estate_market(real_estate_status):
    status = str(real_estate_status).lower().strip()

    mapping = {
        "stable_low_volatility": 1,
        "stable_moderate": 2,
        "elevated_volatility": 3,
        "falling_prices": 4,
        "distressed": 5,
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
    real_estate_score = score_real_estate_market(inputs.get("real_estate_status", "stable_moderate"))
    population_score = score_population_trend(inputs.get("population_growth_vs_us", 0))

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


# -----------------------------
# B. District Characteristics
# -----------------------------

def score_top10_taxpayer_concentration(top10_percent_of_levy):
    x = safe_float(top10_percent_of_levy, default=25)

    if x < 5:
        return 1
    elif x <= 15:
        return 2
    elif x <= 25:
        return 3
    elif x <= 40:
        return 4
    else:
        return 5


def score_development_status(development_status):
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
    x = safe_float(largest_taxpayer_percent_of_levy, default=8)

    if x <= 1:
        return 1
    elif x <= 3:
        return 2
    elif x <= 8:
        return 3
    elif x <= 15:
        return 4
    else:
        return 5


def score_district_size(number_of_parcels):
    parcels = safe_float(number_of_parcels, default=1000)

    if parcels > 4000:
        return 1
    elif parcels >= 1500:
        return 2
    elif parcels >= 400:
        return 3
    elif parcels >= 200:
        return 4
    else:
        return 5


def score_value_to_lien(vtl_ratio):
    vtl = safe_float(vtl_ratio, default=10)

    if vtl > 40:
        return 1
    elif vtl >= 20:
        return 2
    elif vtl >= 10:
        return 3
    elif vtl >= 5:
        return 4
    else:
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


# -------------------------
# Overall Scorecard
# -------------------------

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

    economic_score = economic_results["economic_fundamentals_score"]
    district_score = district_results["district_characteristics_score"]
    financial_score = safe_float(inputs.get("financial_profile_score", 3), default=3)

    weighted_score = calculate_weighted_score(
        economic_score,
        district_score,
        financial_score,
    )

    initial_rating = map_score_to_initial_indicative_rating(weighted_score)

    return {
        **economic_results,
        **district_results,
        "financial_profile_score": financial_score,
        "weighted_score": weighted_score,
        "initial_indicative_rating": initial_rating,
        "final_indicative_rating": initial_rating,
    }
