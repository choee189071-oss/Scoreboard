# modules/scoring_special_assessment.py

SPECIAL_ASSESSMENT_WEIGHTS = {
    "Economic Fundamentals": 0.15,
    "District Characteristics": 0.35,
    "Financial Profile": 0.50,
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
    (4.75, 5.00, "b category"),
]


def map_score_to_initial_indicative_rating(weighted_score):
    for low, high, rating in RATING_SCALE:
        if low <= weighted_score < high:
            return rating

    if weighted_score == 5.00:
        return "b category"

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
    """
    Placeholder:
    Later we can apply notch-down logic for:
    - insufficient governance
    - weak management
    - incremental operating risk
    - event risk
    - third-party credit exposure
    """
    return initial_rating


def apply_rating_caps(initial_rating, caps=None):
    """
    Placeholder:
    Later we can apply caps for:
    - unable to withstand permanent delinquency on undeveloped parcels
    - high concentration causing insufficient cash flows
    - related government cap
    - sizable operating risk
    """
    return initial_rating


def apply_holistic_adjustment(rating_after_caps, holistic_adjustment=0):
    """
    Placeholder:
    holistic_adjustment can be:
    +1 = one notch better
    0 = no change
    -1 = one notch worse
    """
    return rating_after_caps


def calculate_special_assessment_scorecard(inputs):
    economic_score = inputs.get("economic_fundamentals_score")
    district_score = inputs.get("district_characteristics_score")
    financial_score = inputs.get("financial_profile_score")

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
        "economic_fundamentals_score": economic_score,
        "district_characteristics_score": district_score,
        "financial_profile_score": financial_score,
        "weighted_score": weighted_score,
        "initial_indicative_rating": initial_rating,
        "final_indicative_rating": final_indicative_rating,
    }
