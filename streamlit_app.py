import streamlit as st
import pandas as pd

from modules.scoring_special_assessment import (
    calculate_special_assessment_scorecard,
)

st.set_page_config(
    page_title="S&P Scoreboard Automation",
    layout="wide",
)

st.title("S&P Scoreboard Automation")

criteria_type = st.sidebar.selectbox(
    "Select Criteria",
    ["General Fund", "Special Assessment", "Water / Wastewater"],
)

st.write(f"Currently Selected: {criteria_type}")

if criteria_type != "Special Assessment":
    st.info("Scoring engine for this criteria type has not been built yet.")

else:
    input_mode = st.sidebar.radio("Input Mode", ["Manual Input", "Upload CSV"])

    st.header("Special Assessment Scorecard")

    if input_mode == "Manual Input":
        st.subheader("A. Economic Fundamentals")

        col1, col2 = st.columns(2)

        with col1:
            ebi_percent_of_us = st.number_input(
                "Median Household EBI (% of U.S.)",
                min_value=0.0,
                max_value=500.0,
                value=100.0,
                step=1.0,
            )

            unemployment_delta_vs_us = st.number_input(
                "Unemployment Rate Difference vs U.S. (%)",
                value=0.0,
                step=0.1,
                help="Local unemployment rate minus national unemployment rate. Example: local 3%, U.S. 5% = -2.",
            )

            population_growth_vs_us = st.number_input(
                "Population Growth Difference vs U.S. (%)",
                value=0.0,
                step=0.1,
            )

        with col2:
            msa_status = st.selectbox(
                "MSA Status",
                [
                    "broad_diverse",
                    "moderate",
                    "not_broad_diverse",
                    "not_in_msa",
                ],
            )

            real_estate_status = st.selectbox(
                "Real Estate Market Status",
                [
                    "stable_low_volatility",
                    "stable_moderate",
                    "elevated_volatility",
                    "falling_prices",
                    "distressed",
                ],
            )

        st.subheader("B. District Characteristics")

        col3, col4 = st.columns(2)

        with col3:
            top10_taxpayer_percent_of_levy = st.number_input(
                "Top 10 Taxpayers (% of Levy)",
                min_value=0.0,
                max_value=100.0,
                value=15.0,
                step=0.5,
            )

            largest_taxpayer_percent_of_levy = st.number_input(
                "Largest Taxpayer (% of Levy)",
                min_value=0.0,
                max_value=100.0,
                value=3.0,
                step=0.5,
            )

            number_of_parcels = st.number_input(
                "Number of Parcels",
                min_value=0,
                value=1500,
                step=100,
            )

        with col4:
            development_status = st.selectbox(
                "Development Status",
                [
                    "built_out_all_end_users",
                    "built_out_most_end_users",
                    "mature_some_developer_concentration",
                    "majority_developed_significant_undeveloped",
                    "new_majority_undeveloped",
                ],
            )

            value_to_lien_ratio = st.number_input(
                "Overall Value-to-Lien Ratio",
                min_value=0.0,
                value=20.0,
                step=1.0,
            )

        st.subheader("C. Financial Profile")

        financial_profile_score = st.number_input(
            "Financial Profile Score",
            min_value=1.0,
            max_value=5.0,
            value=3.0,
            step=0.5,
        )

        inputs = {
            "ebi_percent_of_us": ebi_percent_of_us,
            "unemployment_delta_vs_us": unemployment_delta_vs_us,
            "msa_status": msa_status,
            "real_estate_status": real_estate_status,
            "population_growth_vs_us": population_growth_vs_us,
            "top10_taxpayer_percent_of_levy": top10_taxpayer_percent_of_levy,
            "development_status": development_status,
            "largest_taxpayer_percent_of_levy": largest_taxpayer_percent_of_levy,
            "number_of_parcels": number_of_parcels,
            "value_to_lien_ratio": value_to_lien_ratio,
            "financial_profile_score": financial_profile_score,
        }

        if st.button("Calculate Scorecard"):
            results = calculate_special_assessment_scorecard(inputs)

            st.subheader("Scorecard Results")

            m1, m2, m3, m4 = st.columns(4)

            m1.metric("Economic Fundamentals", results["economic_fundamentals_score"])
            m2.metric("District Characteristics", results["district_characteristics_score"])
            m3.metric("Financial Profile", results["financial_profile_score"])
            m4.metric("Indicative Rating", results["final_indicative_rating"])

            st.json(results)

    else:
        st.subheader("Upload Financial Data")

        uploaded_file = st.file_uploader("Upload CSV File", type=["csv"])

        def read_uploaded_csv(file):
            encodings = ["utf-8", "utf-8-sig", "latin1", "cp1252"]
            separators = [",", "\t", ";", "|"]

            last_error = None

            for encoding in encodings:
                for sep in separators:
                    try:
                        file.seek(0)
                        return pd.read_csv(
                            file,
                            encoding=encoding,
                            sep=sep,
                            engine="python",
                        )
                    except Exception as e:
                        last_error = e

            raise last_error

        if uploaded_file is not None:
            df = read_uploaded_csv(uploaded_file)

            st.subheader("Preview Data")
            st.dataframe(df)

            st.success("File uploaded successfully.")

            inputs = df.iloc[0].to_dict()
            results = calculate_special_assessment_scorecard(inputs)

            st.subheader("Scorecard Results")
            st.json(results)
