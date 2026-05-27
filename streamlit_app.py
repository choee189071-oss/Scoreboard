import streamlit as st
import pandas as pd

from modules.scoring_special_assessment import calculate_special_assessment_scorecard

st.set_page_config(page_title="S&P Scoreboard Automation", layout="wide")

st.title("S&P Special Assessment Debt Scoreboard")

# =========================================================
# Sidebar
# =========================================================

criteria_type = st.sidebar.selectbox(
    "Criteria Type",
    [
        "Special Assessment Debt",
    ],
)

st.sidebar.markdown("---")
st.sidebar.caption("Prototype Analyst Support Tool")

# =========================================================
# INPUTS
# =========================================================

st.header("A. Economic Fundamentals Assessment")

col1, col2 = st.columns(2)

with col1:

    median_household_ebi_percent_of_us = st.number_input(
        "Median Household EBI (% of U.S.)",
        value=144.0,
        step=1.0,
    )

    unemployment_rate_difference_vs_us = st.number_input(
        "Unemployment Rate Difference vs U.S. (%)",
        value=-0.3,
        step=0.1,
    )

    population_growth_difference_vs_us = st.number_input(
        "Population Growth Difference vs U.S. (%)",
        value=0.5,
        step=0.1,
    )

with col2:

    msa_participation = st.selectbox(
        "MSA Participation",
        [
            "Yes; Broad & Diverse",
            "Yes; Not Broad & Diverse",
            "No",
        ],
    )

    real_estate_market_volatility = st.selectbox(
        "Real Estate Market Volatility",
        [
            "Low Volatility; Stable Prices; Low Distress",
            "Elevated Volatility; Stable Prices; Affordability Worse Than National Figures",
            "Falling Local Home Prices; High Price Volatility; Low Affordability; Rising Distress",
            "Falling Local Home Prices; High Price Volatility; Significantly Worse Affordability; Rising Distress",
        ],
    )

# =========================================================
# DISTRICT CHARACTERISTICS
# =========================================================

st.header("B. District Characteristics Assessment")

col3, col4 = st.columns(2)

with col3:

    top10_taxpayers_percent_of_total_levy = st.number_input(
        "Top 10 Taxpayers as % of Total Levy",
        value=16.1,
        step=0.1,
    )

    largest_taxpayer_percent_of_total_levy = st.number_input(
        "Largest Taxpayer as % of Total Levy",
        value=6.1,
        step=0.1,
    )

    district_size_parcels = st.number_input(
        "District Size (Parcels)",
        value=5900,
        step=100,
    )

with col4:

    conveyance_to_homeowners = st.selectbox(
        "Conveyance to Homeowners",
        [
            "All or Nearly All Conveyed",
            "Most Conveyed",
            "Fairly Developed with Significant Conveyance (Some Developer Concentration)",
            "Developed; Significant Undeveloped Parcels Comprise Minority (Large Developer Concentration)",
            "Undeveloped with Limited Vertical Construction; High Concentration",
        ],
        index=2,
    )

    est_value_to_lien = st.number_input(
        "Est. Value-to-Lien",
        value=15.5,
        step=0.1,
    )

# =========================================================
# FINANCIAL PROFILE
# =========================================================

st.header("C. Financial Profile Assessment")

maximum_loss_to_maturity_percent = st.number_input(
    "Maximum Loss-to-Maturity (MLTM) %",
    value=13.9,
    step=0.1,
)

# =========================================================
# OVERRIDES
# =========================================================

st.header("D. Overriding Factors / Caps")

col5, col6, col7 = st.columns(3)

with col5:

    negative_override_notches = st.number_input(
        "Negative Override Notches",
        value=0,
        step=1,
    )

with col6:

    holistic_adjustment_notches = st.number_input(
        "Holistic Adjustment Notches",
        value=0,
        step=1,
    )

with col7:

    rating_cap = st.selectbox(
        "Rating Cap",
        [
            "None",
            "bbb",
            "bb",
            "b category",
        ],
    )

# =========================================================
# RUN
# =========================================================

if st.button("Calculate Scorecard"):

    inputs = {
        "median_household_ebi_percent_of_us": median_household_ebi_percent_of_us,
        "unemployment_rate_difference_vs_us": unemployment_rate_difference_vs_us,
        "msa_participation": msa_participation,
        "real_estate_market_volatility": real_estate_market_volatility,
        "population_growth_difference_vs_us": population_growth_difference_vs_us,
        "top10_taxpayers_percent_of_total_levy": top10_taxpayers_percent_of_total_levy,
        "conveyance_to_homeowners": conveyance_to_homeowners,
        "largest_taxpayer_percent_of_total_levy": largest_taxpayer_percent_of_total_levy,
        "district_size_parcels": district_size_parcels,
        "est_value_to_lien": est_value_to_lien,
        "maximum_loss_to_maturity_percent": maximum_loss_to_maturity_percent,
        "negative_override_notches": negative_override_notches,
        "holistic_adjustment_notches": holistic_adjustment_notches,
        "rating_cap": rating_cap,
    }

    results = calculate_special_assessment_scorecard(inputs)

    st.success("Scorecard Calculated")

    metric1, metric2, metric3, metric4 = st.columns(4)

    metric1.metric(
        "Economic Fundamentals",
        results["economic_fundamentals_assessment"],
    )

    metric2.metric(
        "District Characteristics",
        results["district_characteristics_assessment"],
    )

    metric3.metric(
        "Financial Profile",
        results["financial_profile_assessment"],
    )

    metric4.metric(
        "Indicative Rating",
        results["indicative_rating"],
    )

    st.markdown("---")

    st.subheader("Full Results")

    st.json(results)
