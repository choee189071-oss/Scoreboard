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

st.sidebar.markdown("---")
st.sidebar.caption(
    "Prototype analytical tool. This is not an official S&P model."
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
                help="Local population growth minus U.S. population growth.",
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

        maximum_loss_to_maturity_percent = st.number_input(
            "Maximum Loss to Maturity / MLTM (%)",
            min_value=0.0,
            max_value=100.0,
            value=15.0,
            step=0.5,
            help="Stress-test estimate of the maximum permanent revenue loss that can be sustained through maturity.",
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
            "maximum_loss_to_maturity_percent": maximum_loss_to_maturity_percent,
        }

        if st.button("Calculate Scorecard", type="primary"):
            results = calculate_special_assessment_scorecard(inputs)

            st.subheader("Scorecard Results")

            m1, m2, m3, m4, m5 = st.columns(5)

            m1.metric("Economic Fundamentals", results["economic_fundamentals_score"])
            m2.metric("District Characteristics", results["district_characteristics_score"])
            m3.metric("Financial Profile", results["financial_profile_score"])
            m4.metric("Weighted Score", results["weighted_score"])
            m5.metric("Indicative Rating", results["final_indicative_rating"])

            st.markdown("### Factor Breakdown")

            economic_df = pd.DataFrame(
                [
                    ["Income", results["income_score"]],
                    ["Unemployment", results["unemployment_score"]],
                    ["MSA", results["msa_score"]],
                    ["Real Estate Market", results["real_estate_score"]],
                    ["Population Trend", results["population_score"]],
                ],
                columns=["Economic Subfactor", "Score"],
            )

            district_df = pd.DataFrame(
                [
                    ["Top 10 Taxpayer Concentration", results["top10_taxpayer_concentration_score"]],
                    ["Development Status", results["development_status_score"]],
                    ["Largest Taxpayer Exposure", results["largest_taxpayer_exposure_score"]],
                    ["District Size", results["district_size_score"]],
                    ["Value To Lien", results["value_to_lien_score"]],
                ],
                columns=["District Subfactor", "Score"],
            )

            c1, c2 = st.columns(2)
            with c1:
                st.dataframe(economic_df, use_container_width=True)
            with c2:
                st.dataframe(district_df, use_container_width=True)

            st.markdown("### Financial Profile Matrix Inputs")
            st.write(
                {
                    "Top 10 taxpayer bucket": results["financial_top10_taxpayer_bucket"],
                    "MLTM bucket": results["mltm_bucket"],
                    "MLTM %": results["maximum_loss_to_maturity_percent"],
                }
            )

            with st.expander("Raw Results JSON"):
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
            st.dataframe(df, use_container_width=True)

            st.success("File uploaded successfully.")

            inputs = df.iloc[0].to_dict()
            results = calculate_special_assessment_scorecard(inputs)

            st.subheader("Scorecard Results")

            m1, m2, m3, m4, m5 = st.columns(5)

            m1.metric("Economic Fundamentals", results["economic_fundamentals_score"])
            m2.metric("District Characteristics", results["district_characteristics_score"])
            m3.metric("Financial Profile", results["financial_profile_score"])
            m4.metric("Weighted Score", results["weighted_score"])
            m5.metric("Indicative Rating", results["final_indicative_rating"])

            with st.expander("Raw Results JSON"):
                st.json(results)
