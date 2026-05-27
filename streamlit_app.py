import streamlit as st
import pandas as pd

from modules.scoring_special_assessment import (
    calculate_special_assessment_scorecard,
    calculate_taxpayer_concentration,
    calculate_value_to_lien,
    calculate_mltm_from_cashflow,
)

st.set_page_config(page_title="Municipal Credit Analytics Platform", layout="wide")

st.title("Municipal Credit Analytics Platform")
st.caption(
    "Scoreboards + analytical calculators + future AI-assisted data pull workflow."
)

# =============================================================================
# Session State Defaults
# =============================================================================

defaults = {
    "top10_taxpayers_percent_of_total_levy": 16.1,
    "largest_taxpayer_percent_of_total_levy": 6.1,
    "est_value_to_lien": 15.5,
    "maximum_loss_to_maturity_percent": 13.9,
    "last_scorecard_results": None,
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


# =============================================================================
# Sidebar: Platform Structure
# =============================================================================

st.sidebar.header("1. Scoreboard Type")

scoreboard_type = st.sidebar.selectbox(
    "Select Scoreboard",
    [
        "Special Assessment Debt",
        "General Obligation / General Fund",
        "Water / Wastewater",
    ],
)

st.sidebar.header("2. Analysis Mode")

analysis_mode = st.sidebar.radio(
    "Select Mode",
    [
        "Manual Input",
        "Upload File",
        "AI-Assisted Data Pull",
    ],
)

st.sidebar.header("3. Analytical Workspace")

workspace = st.sidebar.selectbox(
    "Select Workspace",
    [
        "Main Scoreboard",
        "Taxpayer Concentration Builder",
        "Value-to-Lien Calculator",
        "MLTM Stress Test",
        "Source / Evidence Manager",
        "Explanation View",
    ],
)

st.sidebar.markdown("---")
st.sidebar.caption("Prototype analyst-support platform. Not an official S&P model.")


# =============================================================================
# General Render Helpers
# =============================================================================

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


def render_scorecard_results(results: dict):
    st.subheader("Scorecard Summary")

    c1, c2, c3, c4, c5 = st.columns(5)

    c1.metric("Economic Fundamentals", results.get("economic_fundamentals_assessment"))
    c2.metric("District Characteristics", results.get("district_characteristics_assessment"))
    c3.metric("Financial Profile", results.get("financial_profile_assessment"))
    c4.metric("Factor Score Weighted Average", results.get("factor_score_weighted_average"))
    c5.metric("Indicative Rating", results.get("indicative_rating"))

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

    st.markdown("### Explanation")
    st.markdown(results.get("scorecard_explanation", ""))

    with st.expander("Raw Results JSON"):
        st.json(results)


def calculate_current_scorecard(inputs: dict):
    results = calculate_special_assessment_scorecard(inputs)
    st.session_state["last_scorecard_results"] = results
    return results


# =============================================================================
# Non-Special Assessment Placeholders
# =============================================================================

if scoreboard_type != "Special Assessment Debt":
    st.header(scoreboard_type)
    st.info(
        "This scoreboard type is reserved for the next build. "
        "The platform layout is ready; scoring logic can be added in separate modules."
    )

    st.markdown(
        """
### Future structure

- **General Obligation / General Fund**
  - economy
  - budgetary performance
  - liquidity
  - debt and long-term liabilities
  - institutional framework

- **Water / Wastewater**
  - enterprise risk profile
  - financial risk profile
  - debt service coverage
  - liquidity
  - rate-setting flexibility
"""
    )
    st.stop()


# =============================================================================
# AI-Assisted Data Pull Placeholder
# =============================================================================

if analysis_mode == "AI-Assisted Data Pull":
    st.header("AI-Assisted Data Pull")
    st.warning(
        "This mode is a structured placeholder. The UI is ready for future API integration, "
        "but it is not yet connected to live data sources."
    )

    col1, col2 = st.columns(2)

    with col1:
        issuer_name = st.text_input("Issuer / District Name", value="Laguna Ridge CFD")
        state = st.text_input("State", value="CA")
        county = st.text_input("County / Region", value="Sacramento County")
        bond_type = st.selectbox(
            "Bond Type",
            ["Special Assessment Debt", "CFD / Mello-Roos", "Special Tax Bonds"],
        )

    with col2:
        os_link = st.text_input("Official Statement / EMMA Link")
        data_targets = st.multiselect(
            "Data to Search For",
            [
                "Median Household EBI",
                "Unemployment Rate",
                "MSA Participation",
                "Real Estate Market Volatility",
                "Population Growth",
                "Top 10 Taxpayers",
                "Assessed Value",
                "Direct Debt",
                "Overlapping Debt",
                "MLTM Inputs",
            ],
            default=[
                "Median Household EBI",
                "Top 10 Taxpayers",
                "Assessed Value",
                "MLTM Inputs",
            ],
        )

    st.markdown("### Intended AI/Data Workflow")
    st.dataframe(
        pd.DataFrame(
            [
                ["Census / ACS", "Income, population", "Pending API integration"],
                ["BLS / FRED", "Unemployment", "Pending API integration"],
                ["EMMA / OS", "levy, taxpayer concentration, debt service", "Pending parser"],
                ["County Assessor", "assessed value", "Pending web/API integration"],
                ["Real Estate Sources", "housing market trend/distress", "Pending source manager"],
            ],
            columns=["Source Type", "Target Data", "Status"],
        ),
        use_container_width=True,
    )

    st.info(
        "Next coding step: connect this page to OpenAI API + selected public data APIs, "
        "then return source links, extracted values, confidence scores, and analyst review controls."
    )
    st.stop()


# =============================================================================
# Workspace: Main Scoreboard
# =============================================================================

if workspace == "Main Scoreboard":
    st.header("Special Assessment Debt Scoreboard")

    if analysis_mode == "Upload File":
        st.subheader("Upload Scorecard Inputs")

        uploaded_file = st.file_uploader("Upload CSV File", type=["csv"])

        st.caption(
            "CSV should include fields such as median_household_ebi_percent_of_us, "
            "top10_taxpayers_percent_of_total_levy, est_value_to_lien, maximum_loss_to_maturity_percent, etc."
        )

        if uploaded_file is not None:
            df = read_uploaded_csv(uploaded_file)
            st.dataframe(df, use_container_width=True)

            if not df.empty:
                inputs = df.iloc[0].to_dict()
                results = calculate_current_scorecard(inputs)
                render_scorecard_results(results)

        st.stop()

    st.subheader("A. Economic Fundamentals Assessment")

    col1, col2 = st.columns(2)

    with col1:
        median_household_ebi_percent_of_us = st.number_input(
            "Median Household EBI (% of U.S.)",
            min_value=0.0,
            max_value=500.0,
            value=144.0,
            step=1.0,
        )

        unemployment_rate_difference_vs_us = st.number_input(
            "Unemployment Rate Difference vs U.S. (%)",
            value=-0.3,
            step=0.1,
            help="Local unemployment rate minus national unemployment rate.",
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

    st.subheader("B. District Characteristics Assessment")

    col3, col4 = st.columns(2)

    with col3:
        top10_taxpayers_percent_of_total_levy = st.number_input(
            "Top 10 Taxpayers as % of Total Levy",
            min_value=0.0,
            max_value=100.0,
            value=float(st.session_state["top10_taxpayers_percent_of_total_levy"]),
            step=0.1,
        )

        largest_taxpayer_percent_of_total_levy = st.number_input(
            "Largest Taxpayer as % of Total Levy",
            min_value=0.0,
            max_value=100.0,
            value=float(st.session_state["largest_taxpayer_percent_of_total_levy"]),
            step=0.1,
        )

        district_size_parcels = st.number_input(
            "District Size (Parcels)",
            min_value=0,
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
            min_value=0.0,
            value=float(st.session_state["est_value_to_lien"]),
            step=0.1,
        )

    st.subheader("C. Financial Profile Assessment")

    maximum_loss_to_maturity_percent = st.number_input(
        "Maximum Loss-to-Maturity (MLTM) %",
        min_value=0.0,
        max_value=100.0,
        value=float(st.session_state["maximum_loss_to_maturity_percent"]),
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
        rating_cap = st.selectbox(
            "Rating Cap",
            ["None", "bbb", "bb", "b category"],
        )

    inputs = {
        "median_household_ebi_percent_of_us": median_household_ebi_percent_of_us,
        "unemployment_rate_difference_vs_us": unemployment_rate_difference_vs_us,
        "msa_participation": msa_participation,
        "real_estate_market_volatility": real_estate_market_volatility,
        "population_growth_difference_vs_us": population_growth_difference_vs_us,
        "top10_taxpayers_percent_of_total_levy": top10_taxpayers_percent_of_total_levy,
        "largest_taxpayer_percent_of_total_levy": largest_taxpayer_percent_of_total_levy,
        "district_size_parcels": district_size_parcels,
        "conveyance_to_homeowners": conveyance_to_homeowners,
        "est_value_to_lien": est_value_to_lien,
        "maximum_loss_to_maturity_percent": maximum_loss_to_maturity_percent,
        "negative_override_notches": negative_override_notches,
        "holistic_adjustment_notches": holistic_adjustment_notches,
        "rating_cap": rating_cap,
    }

    if st.button("Calculate Scorecard", type="primary"):
        results = calculate_current_scorecard(inputs)
        render_scorecard_results(results)


# =============================================================================
# Workspace: Taxpayer Concentration Builder
# =============================================================================

elif workspace == "Taxpayer Concentration Builder":
    st.header("Taxpayer Concentration Builder")

    st.write(
        "This tool calculates **Top 10 Taxpayers as % of Total Levy** and "
        "**Largest Taxpayer as % of Total Levy**, then saves the results to the Main Scorecard."
    )

    mode = st.radio("Input Mode", ["Manual Table", "Upload CSV"])

    if mode == "Manual Table":
        default_taxpayers = pd.DataFrame(
            {
                "taxpayer_name": [
                    "Lennar Landbank",
                    "Lennar",
                    "Risewell Landbank",
                    "Risewell",
                    "Beazer Landbank",
                    "Beazer",
                    "Dignity Community Care",
                    "Ridge EG West LP",
                    "PF Portfolio 2 LP",
                    "EGBL 15 LLC",
                ],
                "levy_percent": [6.1, 0.0, 4.0, 0.0, 1.5, 0.0, 1.5, 1.4, 0.9, 0.7],
            }
        )

        taxpayer_df = st.data_editor(
            default_taxpayers,
            num_rows="dynamic",
            use_container_width=True,
        )

    else:
        uploaded = st.file_uploader("Upload taxpayer CSV", type=["csv"])
        if uploaded is not None:
            taxpayer_df = read_uploaded_csv(uploaded)
            st.dataframe(taxpayer_df, use_container_width=True)
        else:
            taxpayer_df = pd.DataFrame()

    if st.button("Calculate Concentration"):
        concentration = calculate_taxpayer_concentration(taxpayer_df)

        st.session_state["top10_taxpayers_percent_of_total_levy"] = concentration["top10_taxpayers_percent_of_total_levy"]
        st.session_state["largest_taxpayer_percent_of_total_levy"] = concentration["largest_taxpayer_percent_of_total_levy"]

        c1, c2 = st.columns(2)
        c1.metric("Top 10 Taxpayers as % of Total Levy", concentration["top10_taxpayers_percent_of_total_levy"])
        c2.metric("Largest Taxpayer as % of Total Levy", concentration["largest_taxpayer_percent_of_total_levy"])

        st.markdown("### Ranked Taxpayer Table")
        st.dataframe(concentration["taxpayer_table"], use_container_width=True)

        st.success("Values saved to the Main Scorecard session.")


# =============================================================================
# Workspace: Value-to-Lien Calculator
# =============================================================================

elif workspace == "Value-to-Lien Calculator":
    st.header("Value-to-Lien Calculator")

    st.write(
        "This tool calculates **Est. Value-to-Lien** from assessed value and debt base, "
        "then saves the result to the Main Scorecard."
    )

    col1, col2 = st.columns(2)

    with col1:
        assessed_value = st.number_input(
            "Assessed Value",
            min_value=0.0,
            value=3454244692.0,
            step=1000000.0,
        )

        direct_debt = st.number_input(
            "Direct Debt",
            min_value=0.0,
            value=183240000.0,
            step=1000000.0,
        )

    with col2:
        overlapping_debt = st.number_input(
            "Overlapping Debt",
            min_value=0.0,
            value=38445099.0,
            step=1000000.0,
        )

        include_overlapping_debt = st.checkbox(
            "Include Overlapping Debt",
            value=True,
        )

    if st.button("Calculate Value-to-Lien"):
        vtl_results = calculate_value_to_lien(
            assessed_value,
            direct_debt,
            overlapping_debt,
            include_overlapping_debt,
        )

        st.session_state["est_value_to_lien"] = vtl_results["estimated_value_to_lien"]

        c1, c2, c3 = st.columns(3)
        c1.metric("Debt Base for VTL", f"{vtl_results['debt_base_for_vtl']:,.0f}")
        c2.metric("Est. Value-to-Lien", vtl_results["estimated_value_to_lien"])
        c3.metric("Saved to Main Scorecard", "Yes")

        st.json(vtl_results)


# =============================================================================
# Workspace: MLTM Stress Test
# =============================================================================

elif workspace == "MLTM Stress Test":
    st.header("Maximum Loss-to-Maturity (MLTM) Stress Test")

    st.write(
        "This simplified tool estimates the maximum permanent revenue loss that can be applied "
        "to projected special tax levy while still covering debt service through maturity."
    )

    initial_reserve_fund = st.number_input(
        "Initial Reserve Fund",
        min_value=0.0,
        value=15439154.0,
        step=100000.0,
    )

    mode = st.radio("Input Mode", ["Manual Table", "Upload CSV"])

    if mode == "Manual Table":
        default_cashflow = pd.DataFrame(
            {
                "year": list(range(2027, 2037)),
                "special_tax_levy": [
                    12191803, 12460759, 12710019, 12959939, 13219518,
                    13492483, 13758628, 14025653, 14138513, 14239823
                ],
                "annual_debt_service": [
                    11108912, 11327963, 11554563, 11781763, 12017744,
                    12265894, 12507844, 12750594, 12853194, 12945294
                ],
            }
        )

        cashflow_df = st.data_editor(
            default_cashflow,
            num_rows="dynamic",
            use_container_width=True,
        )

    else:
        uploaded = st.file_uploader("Upload MLTM cashflow CSV", type=["csv"])
        if uploaded is not None:
            cashflow_df = read_uploaded_csv(uploaded)
            st.dataframe(cashflow_df, use_container_width=True)
        else:
            cashflow_df = pd.DataFrame()

    if st.button("Calculate MLTM"):
        mltm_results = calculate_mltm_from_cashflow(
            cashflow_df,
            initial_reserve_fund=initial_reserve_fund,
        )

        st.session_state["maximum_loss_to_maturity_percent"] = mltm_results["maximum_loss_to_maturity_percent"]

        c1, c2, c3 = st.columns(3)
        c1.metric("Estimated MLTM %", mltm_results["maximum_loss_to_maturity_percent"])
        c2.metric("Total Revenue", f"{mltm_results['total_revenue']:,.0f}")
        c3.metric("Total Debt Service", f"{mltm_results['total_debt_service']:,.0f}")

        st.markdown("### Stress Cashflow Table")
        st.dataframe(mltm_results["mltm_cashflow_table"], use_container_width=True)

        st.success("MLTM value saved to the Main Scorecard session.")


# =============================================================================
# Workspace: Source / Evidence Manager
# =============================================================================

elif workspace == "Source / Evidence Manager":
    st.header("Source / Evidence Manager")

    st.write(
        "This workspace is designed for tracking source evidence for each scorecard input. "
        "It is ready for future AI/API extraction."
    )

    source_df = pd.DataFrame(
        [
            ["Median Household EBI", "Census / ACS", "", "Pending"],
            ["Unemployment Rate", "BLS / FRED", "", "Pending"],
            ["MSA Participation", "Census / OMB MSA data", "", "Pending"],
            ["Real Estate Market Volatility", "Real estate market source", "", "Pending"],
            ["Population Growth", "Census / ACS", "", "Pending"],
            ["Top 10 Taxpayers", "Official Statement / Levy report", "", "Pending"],
            ["Est. Value-to-Lien", "Assessed value + debt schedule", "", "Pending"],
            ["MLTM Inputs", "Debt service + levy forecast", "", "Pending"],
        ],
        columns=["Scorecard Field", "Preferred Source Type", "Source Link / Note", "Status"],
    )

    edited_sources = st.data_editor(
        source_df,
        num_rows="dynamic",
        use_container_width=True,
    )

    st.info(
        "Future AI-assisted workflow: the system will populate extracted value, source URL, "
        "confidence score, and analyst approval status here."
    )


# =============================================================================
# Workspace: Explanation View
# =============================================================================

elif workspace == "Explanation View":
    st.header("Explanation View")

    if not st.session_state.get("last_scorecard_results"):
        st.info("Run the Main Scorecard first to generate an explanation.")
    else:
        results = st.session_state["last_scorecard_results"]
        st.markdown(results.get("scorecard_explanation", ""))

        with st.expander("Raw Results JSON"):
            st.json(results)
