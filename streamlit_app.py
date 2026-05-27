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
    [
        "General Fund",
        "Special Assessment",
        "Water / Wastewater",
    ],
)

st.write(f"Currently Selected: {criteria_type}")

if criteria_type != "Special Assessment":
    st.info("Scoring engine for this criteria type has not been built yet.")

else:
    input_mode = st.sidebar.radio(
        "Input Mode",
        ["Manual Input", "Upload CSV"],
    )

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

        st.subheader("B. Other Factor Scores")

        col3, col4 = st.columns(2)

        with col3:
            district_characteristics_score = st.number_input(
                "District Characteristics Score",
                min_value=1.0,
                max_value=5.0,
                value=3.0,
                step=0.5,
            )

        with col4:
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
            "district_characteristics_score": district_characteristics_score,
            "financial_profile_score": financial_profile_score,
        }

        if st.button("Calculate Scorecard"):
            results = calculate_special_assessment_scorecard(inputs)

            st.subheader("Scorecard Results")

            metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)

            metric_col1.metric(
                "Economic Fundamentals",
                results["economic_fundamentals_score"],
            )

            metric_col2.metric(
                "District Characteristics",
                results["district_characteristics_score"],
            )

            metric_col3.metric(
                "Financial Profile",
                results["financial_profile_score"],
            )

            metric_col4.metric(
                "Indicative Rating",
                results["final_indicative_rating"],
            )

            st.json(results)

    else:
        st.subheader("Upload Financial Data")

        uploaded_file = st.file_uploader(
            "Upload CSV File",
            type=["csv"],
        )

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
