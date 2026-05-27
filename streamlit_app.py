import streamlit as st
import pandas as pd

from modules.scoring_special_assessment import calculate_special_assessment_scorecard

st.set_page_config(page_title="S&P Scoreboard Automation", layout="wide")

st.title("S&P Scoreboard Automation")

criteria_type = st.sidebar.selectbox(
    "Select Criteria",
    ["General Fund", "Special Assessment", "Water / Wastewater"],
)

st.sidebar.markdown("---")
st.sidebar.caption("Prototype analyst-support tool. Not an official S&P model.")

if criteria_type != "Special Assessment":
    st.info("Scoring engine for this criteria type has not been built yet.")
    st.stop()

input_mode = st.sidebar.radio("Input Mode", ["Manual Input", "Upload CSV"])

st.header("Special Assessment Debt Scorecard")

def render_results(results: dict):
    st.subheader("Scorecard Summary")

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Economic", results.get("economic_fundamentals_score"))
    m2.metric("District", results.get("district_characteristics_score"))
    m3.metric("Financial", results.get("financial_profile_score"))
    m4.metric("Weighted Score", results.get("weighted_score"))
    m5.metric("Final Rating", results.get("final_indicative_rating"))

    st.markdown("### Factor Score Breakdown")

    factor_df = pd.DataFrame(
        [
            ["Economic Fundamentals", "15%", results.get("economic_fundamentals_score"), results.get("economic_fundamentals_category")],
            ["District Characteristics", "35%", results.get("district_characteristics_score"), results.get("district_characteristics_category")],
            ["Financial Profile", "50%", results.get("financial_profile_score"), results.get("financial_profile_category")],
        ],
        columns=["Factor", "Weight", "Score", "Category"],
    )
    st.dataframe(factor_df, use_container_width=True)

    c1, c2 = st.columns(2)

    with c1:
        st.markdown("### Economic Fundamentals")
        econ_df = pd.DataFrame(
            [
                ["Income", results.get("income_score")],
                ["Unemployment", results.get("unemployment_score")],
                ["MSA", results.get("msa_score")],
                ["Real Estate Market", results.get("real_estate_score")],
                ["Population Trend", results.get("population_score")],
            ],
            columns=["Subfactor", "Score"],
        )
        st.dataframe(econ_df, use_container_width=True)

    with c2:
        st.markdown("### District Characteristics")
        district_df = pd.DataFrame(
            [
                ["Top 10 Taxpayer Concentration", results.get("top10_taxpayer_concentration_score")],
                ["Development Status", results.get("development_status_score")],
                ["Largest Taxpayer Exposure", results.get("largest_taxpayer_exposure_score")],
                ["District Size", results.get("district_size_score")],
                ["Value To Lien", results.get("value_to_lien_score")],
            ],
            columns=["Subfactor", "Score"],
        )
        st.dataframe(district_df, use_container_width=True)

    st.markdown("### Financial Profile Matrix")
    financial_df = pd.DataFrame(
        [
            ["Top 10 Taxpayer Bucket", results.get("financial_top10_taxpayer_bucket", "N/A")],
            ["MLTM Bucket", results.get("mltm_bucket", "N/A")],
            ["MLTM %", results.get("maximum_loss_to_maturity_percent", "N/A")],
            ["Financial Profile Score", results.get("financial_profile_score", "N/A")],
        ],
        columns=["Metric", "Value"],
    )
    st.dataframe(financial_df, use_container_width=True)

    st.markdown("### Rating Adjustments")
    adjustment_df = pd.DataFrame(
        [
            ["Initial Indicative Rating", results.get("initial_indicative_rating")],
            ["Negative Override Notches", results.get("negative_override_notches")],
            ["Holistic Adjustment Notches", results.get("holistic_adjustment_notches")],
            ["Rating Cap", results.get("rating_cap")],
            ["Final Indicative Rating", results.get("final_indicative_rating")],
        ],
        columns=["Item", "Value"],
    )
    st.dataframe(adjustment_df, use_container_width=True)

    with st.expander("Raw JSON"):
        st.json(results)


if input_mode == "Manual Input":
    st.subheader("A. Economic Fundamentals")

    col1, col2 = st.columns(2)
    with col1:
        ebi_percent_of_us = st.number_input("Median Household EBI (% of U.S.)", min_value=0.0, max_value=500.0, value=144.0, step=1.0)
        unemployment_delta_vs_us = st.number_input("Unemployment Rate Difference vs U.S. (%)", value=-0.3, step=0.1)
        population_growth_vs_us = st.number_input("Population Growth Difference vs U.S. (%)", value=0.5, step=0.1)
    with col2:
        msa_status = st.selectbox("MSA Status", ["broad_diverse", "moderate", "not_broad_diverse", "not_in_msa"])
        real_estate_status = st.selectbox("Real Estate Market Status", ["stable_low_volatility", "stable_moderate", "elevated_volatility", "falling_prices", "distressed"])

    st.subheader("B. District Characteristics")

    col3, col4 = st.columns(2)
    with col3:
        top10_taxpayer_percent_of_levy = st.number_input("Top 10 Taxpayers (% of Levy)", min_value=0.0, max_value=100.0, value=16.1, step=0.1)
        largest_taxpayer_percent_of_levy = st.number_input("Largest Taxpayer (% of Levy)", min_value=0.0, max_value=100.0, value=6.1, step=0.1)
        number_of_parcels = st.number_input("Number of Parcels", min_value=0, value=5900, step=100)
    with col4:
        development_status = st.selectbox(
            "Development / Conveyance Status",
            [
                "built_out_all_end_users",
                "built_out_most_end_users",
                "mature_some_developer_concentration",
                "majority_developed_significant_undeveloped",
                "new_majority_undeveloped",
            ],
            index=2,
        )
        value_to_lien_ratio = st.number_input("Overall Value-to-Lien Ratio", min_value=0.0, value=15.5, step=0.1)

    st.subheader("C. Financial Profile / Stress Test")

    maximum_loss_to_maturity_percent = st.number_input(
        "Maximum Loss to Maturity / MLTM (%)",
        min_value=0.0,
        max_value=100.0,
        value=13.9,
        step=0.1,
    )

    st.subheader("D. Overrides / Caps")

    col5, col6, col7 = st.columns(3)
    with col5:
        negative_override_notches = st.number_input("Negative Override Notches", min_value=0, max_value=5, value=0, step=1)
    with col6:
        holistic_adjustment_notches = st.number_input("Holistic Adjustment Notches", min_value=-1, max_value=1, value=0, step=1)
    with col7:
        rating_cap = st.selectbox("Rating Cap", ["None", "bbb", "bb", "b category"])

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
