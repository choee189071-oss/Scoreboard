import streamlit as st
import pandas as pd

from modules.scoring_special_assessment import (
    calculate_special_assessment_scorecard
)

st.set_page_config(
    page_title="S&P Scoreboard Automation",
    layout="wide"
)

st.title("S&P Scoreboard Automation")

criteria_type = st.sidebar.selectbox(
    "Select Criteria",
    [
        "General Fund",
        "Special Assessment",
        "Water / Wastewater"
    ]
)

st.write(f"Currently Selected: {criteria_type}")

# =========================================================
# SPECIAL ASSESSMENT SECTION
# =========================================================

if criteria_type == "Special Assessment":

    st.header("A. Economic Fundamentals")

    col1, col2 = st.columns(2)

    with col1:
        ebi_percent_of_us = st.number_input(
            "Median Household EBI (% of U.S.)",
            value=110.0
        )

        unemployment_delta_vs_us = st.number_input(
            "Unemployment Delta vs U.S. (%)",
            value=0.0
        )

        population_growth_vs_us = st.number_input(
            "Population Growth vs U.S. (%)",
            value=0.0
        )

    with col2:
        msa_status = st.selectbox(
            "MSA Status",
            [
                "broad_diverse",
                "not_broad_diverse",
                "not_in_msa"
            ]
        )

        real_estate_status = st.selectbox(
            "Real Estate Market",
            [
                "stable_strong",
                "stable_moderate",
                "declining_weak"
            ]
        )

    st.divider()

    st.header("B. District Characteristics")

    col3, col4 = st.columns(2)

    with col3:

        top10_taxpayer_percent = st.number_input(
            "Top 10 Taxpayer Concentration (%)",
            value=10.0
        )

        largest_taxpayer_percent = st.number_input(
            "Largest Taxpayer (%)",
            value=2.0
        )

        parcel_count = st.number_input(
            "Parcel Count",
            value=2000
        )

    with col4:

        development_status = st.selectbox(
            "Development Status",
            [
                "built_out",
                "mostly_built_out",
                "mixed",
                "undeveloped"
            ]
        )

        overall_vtl = st.number_input(
            "Overall VTL Ratio (x)",
            value=20.0
        )

    st.divider()

    st.header("C. Financial Profile Matrix Inputs")

    col5, col6 = st.columns(2)

    with col5:

        maximum_loss_to_maturity_percent = st.number_input(
            "Maximum Loss to Maturity (%)",
            value=20.0
        )

    with col6:

        financial_top10_taxpayer_percent = st.number_input(
            "Financial Matrix: Top 10 Taxpayer (%)",
            value=10.0
        )

    st.divider()

    if st.button("Calculate Scorecard"):

        inputs = {
            "ebi_percent_of_us": ebi_percent_of_us,
            "unemployment_delta_vs_us": unemployment_delta_vs_us,
            "msa_status": msa_status,
            "real_estate_status": real_estate_status,
            "population_growth_vs_us": population_growth_vs_us,

            "top10_taxpayer_percent": top10_taxpayer_percent,
            "largest_taxpayer_percent": largest_taxpayer_percent,
            "parcel_count": parcel_count,
            "development_status": development_status,
            "overall_vtl": overall_vtl,

            "maximum_loss_to_maturity_percent": maximum_loss_to_maturity_percent,
            "financial_top10_taxpayer_percent": financial_top10_taxpayer_percent,
        }

        results = calculate_special_assessment_scorecard(inputs)

        st.success("Scorecard Calculated Successfully")

        # =====================================================
        # ECONOMIC
        # =====================================================

        st.subheader("Economic Fundamentals")

        econ_df = pd.DataFrame({
            "Metric": [
                "Economic Score",
                "Economic Category"
            ],
            "Value": [
                results.get("economic_fundamentals_score"),
                results.get("economic_category")
            ]
        })

        st.dataframe(econ_df, use_container_width=True)

        # =====================================================
        # DISTRICT
        # =====================================================

        st.subheader("District Characteristics")

        district_df = pd.DataFrame({
            "Metric": [
                "District Score",
                "District Category"
            ],
            "Value": [
                results.get("district_characteristics_score"),
                results.get("district_category")
            ]
        })

        st.dataframe(district_df, use_container_width=True)

        # =====================================================
        # FINANCIAL
        # =====================================================

        st.subheader("Financial Profile")

        financial_df = pd.DataFrame({
            "Metric": [
                "Financial Score",
                "Financial Category",
                "Top 10 Taxpayer Bucket",
                "MLTM Bucket"
            ],
            "Value": [
                results.get("financial_profile_score"),
                results.get("financial_category"),
                results.get("financial_top10_taxpayer_bucket", "N/A"),
                results.get("mltm_bucket", "N/A")
            ]
        })

        st.dataframe(financial_df, use_container_width=True)

        # =====================================================
        # FINAL
        # =====================================================

        st.subheader("Final Results")

        final_df = pd.DataFrame({
            "Metric": [
                "Weighted Score",
                "Initial Indicative Rating",
                "Final Indicative Rating"
            ],
            "Value": [
                results.get("weighted_score"),
                results.get("initial_indicative_rating"),
                results.get("final_indicative_rating")
            ]
        })

        st.dataframe(final_df, use_container_width=True)
