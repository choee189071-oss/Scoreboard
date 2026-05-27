import streamlit as st
import pandas as pd

from modules.scoring_special_assessment import calculate_special_assessment_scorecard

st.set_page_config(
    page_title="S&P Scoreboard Automation",
    layout="wide",
)

st.title("S&P Scoreboard Automation")

criteria_type = st.sidebar.selectbox(
    "Select Criteria",
    ["General Fund", "Special Assessment Debt", "Water / Wastewater"],
)

st.sidebar.markdown("---")
st.sidebar.caption("Prototype analyst-support scorecard. Not an official S&P model.")

if criteria_type != "Special Assessment Debt":
    st.info("Scoring engine for this criteria type has not been built yet.")
    st.stop()

input_mode = st.sidebar.radio("Input Mode", ["Manual Input", "Upload CSV"])

st.header("Special Assessment Debt Scorecard")


def render_results(results: dict):
    st.subheader("Scorecard Summary")

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Economic Fundamentals Assessment", results.get("economic_fundamentals_assessment"))
    m2.metric("District Characteristics Assessment", results.get("district_characteristics_assessment"))
    m3.metric("Financial Profile Assessment", results.get("financial_profile_assessment"))
    m4.metric("Factor Score Weighted Average", results.get("factor_score_weighted_average"))
    m5.metric("Indicative Rating", results.get("indicative_rating"))

    st.markdown("### Key Credit Factor Assessments")

    factor_df = pd.DataFrame(
        [
            [
                "Economic Fundamentals Assessment",
                "15%",
                results.get("economic_fundamentals_assessment"),
                results.get("economic_fundamentals_assessment_category"),
            ],
            [
                "District Characteristics Assessment",
                "35%",
                results.get("district_characteristics_assessment"),
                results.get("district_characteristics_assessment_category"),
            ],
            [
                "Financial Profile Assessment",
                "50%",
                results.get("financial_profile_assessment"),
                results.get("financial_profile_assessment_category"),
            ],
        ],
        columns=["Key Credit Factor", "Weight", "Numeric Assessment", "Assessment Category"],
    )
    st.dataframe(factor_df, use_container_width=True)

    c1, c2 = st.columns(2)

    with c1:
        st.markdown("### Economic Fundamentals Subfactor Assessments")
        economic_df = pd.DataFrame(
            [
                ["Household Income Levels", results.get("household_income_levels_assessment")],
                ["Unemployment Rate", results.get("unemployment_rate_assessment")],
                ["Participation in Broad and Diverse MSA", results.get("msa_participation_assessment")],
                ["Real Estate Market Characteristics", results.get("real_estate_market_characteristics_assessment")],
                ["Population Trends", results.get("population_trends_assessment")],
            ],
            columns=["Subfactor", "Numeric Assessment"],
        )
        st.dataframe(economic_df, use_container_width=True)

    with c2:
        st.markdown("### District Characteristics Subfactor Assessments")
        district_df = pd.DataFrame(
            [
                ["Top 10 Taxpayers as % of Total Levy", results.get("top10_taxpayers_percent_of_total_levy_assessment")],
                ["Conveyance to Homeowners / Development Status", results.get("conveyance_to_homeowners_development_status_assessment")],
                ["Largest Taxpayer as % of Total Levy", results.get("largest_taxpayer_percent_of_total_levy_assessment")],
                ["District Size (Parcels)", results.get("district_size_parcels_assessment")],
                ["Estimated Value-to-Lien Ratio", results.get("estimated_value_to_lien_ratio_assessment")],
            ],
            columns=["Subfactor", "Numeric Assessment"],
        )
        st.dataframe(district_df, use_container_width=True)

    st.markdown("### Financial Profile Assessment Matrix Inputs")
    financial_df = pd.DataFrame(
        [
            ["Top 10 Taxpayers Bucket", results.get("financial_profile_top10_taxpayers_bucket", "N/A")],
            ["Maximum Loss-to-Maturity (MLTM) Bucket", results.get("maximum_loss_to_maturity_bucket", "N/A")],
            ["Maximum Loss-to-Maturity (MLTM) %", results.get("maximum_loss_to_maturity_percent", "N/A")],
            ["Financial Profile Assessment", results.get("financial_profile_assessment", "N/A")],
        ],
        columns=["Metric", "Value"],
    )
    st.dataframe(financial_df, use_container_width=True)

    st.markdown("### Overriding Factors / Caps / Holistic Analysis")
    adjustment_df = pd.DataFrame(
        [
            ["Initial Indicative Rating", results.get("initial_indicative_rating")],
            ["Negative Overriding Factors (Notches)", results.get("negative_override_notches")],
            ["Rating After Overriding Factors", results.get("rating_after_overriding_factors")],
            ["Holistic Analysis Adjustment (Notches)", results.get("holistic_adjustment_notches")],
            ["Rating After Holistic Analysis", results.get("rating_after_holistic_analysis")],
            ["Rating Cap", results.get("rating_cap")],
            ["Indicative Rating", results.get("indicative_rating")],
        ],
        columns=["Item", "Value"],
    )
    st.dataframe(adjustment_df, use_container_width=True)

    with st.expander("Raw Results JSON"):
        st.json(results)


if input_mode == "Manual Input":
    st.subheader("A. Economic Fundamentals Assessment")

    col1, col2 = st.columns(2)
    with col1:
        median_household_ebi_percent_of_us = st.number_input(
            "Median Household Effective Buying Income (% of U.S.)",
            min_value=0.0,
            max_value=500.0,
            value=144.0,
            step=1.0,
        )
        unemployment_rate_difference_vs_us = st.number_input(
            "Unemployment Rate Difference vs U.S. (%)",
            value=-0.3,
            step=0.1,
            help="Local unemployment rate minus national unemployment rate. Example: local 3%, U.S. 5% = -2.",
        )
        population_growth_difference_vs_us = st.number_input(
            "Population Growth Difference vs U.S. (%)",
            value=0.5,
            step=0.1,
            help="Local population growth minus U.S. population growth.",
        )
    with col2:
        msa_participation = st.selectbox(
            "Participation in Broad and Diverse MSA",
            ["broad_diverse_msa", "moderate_msa", "not_broad_diverse_msa", "not_in_msa"],
        )
        real_estate_market_characteristics = st.selectbox(
            "Real Estate Market Characteristics",
            ["stable_low_volatility", "stable_moderate", "elevated_volatility", "falling_prices", "distressed"],
        )

    st.subheader("B. District Characteristics Assessment")

    col3, col4 = st.columns(2)
    with col3:
        top10_taxpayers_percent_of_total_levy = st.number_input(
            "Top 10 Taxpayers as % of Total Levy",
            min_value=0.0,
            max_value=100.0,
            value=16.1,
            step=0.1,
        )
        largest_taxpayer_percent_of_total_levy = st.number_input(
            "Largest Taxpayer as % of Total Levy",
            min_value=0.0,
            max_value=100.0,
            value=6.1,
            step=0.1,
        )
        district_size_parcels = st.number_input(
            "District Size (Parcels)",
            min_value=0,
            value=5900,
            step=100,
        )
    with col4:
        conveyance_to_homeowners_development_status = st.selectbox(
            "Conveyance to Homeowners / Development Status",
            [
                "built_out_all_end_users",
                "built_out_most_end_users",
                "mature_some_developer_concentration",
                "majority_developed_significant_undeveloped",
                "new_majority_undeveloped",
            ],
            index=2,
        )
        estimated_value_to_lien_ratio = st.number_input(
            "Estimated Value-to-Lien Ratio",
            min_value=0.0,
            value=15.5,
            step=0.1,
        )

    st.subheader("C. Financial Profile Assessment")

    maximum_loss_to_maturity_percent = st.number_input(
        "Maximum Loss-to-Maturity (MLTM) %",
        min_value=0.0,
        max_value=100.0,
        value=13.9,
        step=0.1,
    )

    st.subheader("D. Overriding Factors / Caps / Holistic Analysis")

    col5, col6, col7 = st.columns(3)
    with col5:
        negative_override_notches = st.number_input(
            "Negative Overriding Factors (Notches)",
            min_value=0,
            max_value=5,
            value=0,
            step=1,
        )
    with col6:
        holistic_adjustment_notches = st.number_input(
            "Holistic Analysis Adjustment (Notches)",
            min_value=-1,
            max_value=1,
            value=0,
            step=1,
        )
    with col7:
        rating_cap = st.selectbox("Rating Cap", ["None", "bbb", "bb", "b category"])

    inputs = {
        "median_household_ebi_percent_of_us": median_household_ebi_percent_of_us,
        "unemployment_rate_difference_vs_us": unemployment_rate_difference_vs_us,
        "msa_participation": msa_participation,
        "real_estate_market_characteristics": real_estate_market_characteristics,
        "population_growth_difference_vs_us": population_growth_difference_vs_us,
        "top10_taxpayers_percent_of_total_levy": top10_taxpayers_percent_of_total_levy,
        "conveyance_to_homeowners_development_status": conveyance_to_homeowners_development_status,
        "largest_taxpayer_percent_of_total_levy": largest_taxpayer_percent_of_total_levy,
        "district_size_parcels": district_size_parcels,
        "estimated_value_to_lien_ratio": estimated_value_to_lien_ratio,
        "maximum_loss_to_maturity_percent": maximum_loss_to_maturity_percent,
        "negative_override_notches": negative_override_notches,
        "holistic_adjustment_notches": holistic_adjustment_notches,
        "rating_cap": rating_cap,
    }

    if st.button("Calculate Scorecard", type="primary"):
        results = calculate_special_assessment_scorecard(inputs)
        render_results(results)

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
                    return pd.read_csv(file, encoding=encoding, sep=sep, engine="python")
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
        render_results(results)
