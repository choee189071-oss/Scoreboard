import streamlit as st
import pandas as pd

from modules.scoring_special_assessment import (
    calculate_special_assessment_scorecard,
    calculate_taxpayer_concentration,
    calculate_value_to_lien,
    calculate_mltm_from_cashflow,
)

from modules.auto_data_sources import (
    auto_pull_structured_data,
    auto_data_results_to_dataframe,
)

from modules.document_ai_extraction import (
    DEFAULT_TARGETS,
    read_uploaded_file_to_context,
    run_document_ai_extraction,
    derived_calculations_to_dataframe,
)

from modules.reliability_layer import (
    combine_candidate_sources,
    normalize_candidate_dataframe,
    approved_candidates_to_scorecard_inputs,
    missing_data_tracker,
    source_priority_table,
    build_reliability_summary,
)

st.set_page_config(page_title="Municipal Credit Analytics Platform", layout="wide")

st.title("Municipal Credit Analytics Platform")
st.caption(
    "Unified workflow with source reliability layer: Auto data pull + document extraction + analyst review + scorecard."
)


# =============================================================================
# Session Defaults
# =============================================================================

defaults = {
    "approved_inputs": {},
    "auto_data_results": [],
    "parsed_documents": [],
    "last_document_ai_result": None,
    "last_scorecard_results": None,
    "review_candidates": pd.DataFrame(),
    "top10_taxpayers_percent_of_total_levy": 16.1,
    "largest_taxpayer_percent_of_total_levy": 6.1,
    "est_value_to_lien": 15.5,
    "maximum_loss_to_maturity_percent": 13.9,
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


# =============================================================================
# Sidebar
# =============================================================================

st.sidebar.header("Scoreboard")
scoreboard_type = st.sidebar.selectbox(
    "Scoreboard Type",
    [
        "Special Assessment Debt",
        "General Obligation / General Fund",
        "Water / Wastewater",
    ],
)

st.sidebar.header("Workflow")
workflow_mode = st.sidebar.radio(
    "Mode",
    [
        "Integrated Analyst Workflow",
        "Manual Input Only",
    ],
)

st.sidebar.markdown("---")
st.sidebar.caption("Prototype analyst-support platform. Not an official S&P model.")


# =============================================================================
# Helper Functions
# =============================================================================

def render_metric_row(results: dict):
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Economic", results.get("economic_fundamentals_assessment"))
    c2.metric("District", results.get("district_characteristics_assessment"))
    c3.metric("Financial", results.get("financial_profile_assessment"))
    c4.metric("Weighted Avg.", results.get("factor_score_weighted_average"))
    c5.metric("Indicative Rating", results.get("indicative_rating"))


def render_scorecard_results(results: dict):
    st.success("Scorecard calculated.")
    render_metric_row(results)

    factor_df = pd.DataFrame(
        [
            ["Economic Fundamentals Assessment", "15%", results.get("economic_fundamentals_assessment"), results.get("economic_fundamentals_assessment_category")],
            ["District Characteristics Assessment", "35%", results.get("district_characteristics_assessment"), results.get("district_characteristics_assessment_category")],
            ["Financial Profile Assessment", "50%", results.get("financial_profile_assessment"), results.get("financial_profile_assessment_category")],
        ],
        columns=["Key Credit Factor", "Weight", "Numeric Assessment", "Category"],
    )
    st.dataframe(factor_df, use_container_width=True)

    with st.expander("Rating Explanation", expanded=True):
        st.markdown(results.get("scorecard_explanation", ""))

    with st.expander("Raw Results JSON"):
        st.json(results)


def calculate_current_scorecard(inputs: dict):
    results = calculate_special_assessment_scorecard(inputs)
    st.session_state["last_scorecard_results"] = results
    return results


def merge_approved_inputs(new_inputs: dict):
    current = st.session_state.get("approved_inputs", {}) or {}
    current.update(new_inputs)
    st.session_state["approved_inputs"] = current

    for key, value in new_inputs.items():
        st.session_state[key] = value


def get_default_scorecard_inputs():
    approved = st.session_state.get("approved_inputs", {}) or {}

    return {
        "median_household_ebi_percent_of_us": approved.get("median_household_ebi_percent_of_us", 144.0),
        "unemployment_rate_difference_vs_us": approved.get("unemployment_rate_difference_vs_us", -0.3),
        "msa_participation": approved.get("msa_participation", "Yes; Broad & Diverse"),
        "real_estate_market_volatility": approved.get("real_estate_market_volatility", "Low Volatility; Stable Prices; Low Distress"),
        "population_growth_difference_vs_us": approved.get("population_growth_difference_vs_us", 0.5),
        "top10_taxpayers_percent_of_total_levy": approved.get("top10_taxpayers_percent_of_total_levy", st.session_state.get("top10_taxpayers_percent_of_total_levy", 16.1)),
        "largest_taxpayer_percent_of_total_levy": approved.get("largest_taxpayer_percent_of_total_levy", st.session_state.get("largest_taxpayer_percent_of_total_levy", 6.1)),
        "district_size_parcels": approved.get("district_size_parcels", 5900),
        "conveyance_to_homeowners": approved.get("conveyance_to_homeowners", "Fairly Developed with Significant Conveyance (Some Developer Concentration)"),
        "est_value_to_lien": approved.get("est_value_to_lien", st.session_state.get("est_value_to_lien", 15.5)),
        "maximum_loss_to_maturity_percent": approved.get("maximum_loss_to_maturity_percent", st.session_state.get("maximum_loss_to_maturity_percent", 13.9)),
        "negative_override_notches": approved.get("negative_override_notches", 0),
        "holistic_adjustment_notches": approved.get("holistic_adjustment_notches", 0),
        "rating_cap": approved.get("rating_cap", "None"),
    }


def refresh_candidates():
    candidates = combine_candidate_sources(
        auto_results=st.session_state.get("auto_data_results", []),
        document_ai_result=st.session_state.get("last_document_ai_result"),
        manual_candidates=None,
    )
    st.session_state["review_candidates"] = candidates
    return candidates


def source_status_cards():
    auto_count = len(st.session_state.get("auto_data_results", []) or [])
    doc_count = len(st.session_state.get("parsed_documents", []) or [])
    approved_count = len(st.session_state.get("approved_inputs", {}) or {})
    candidates = st.session_state.get("review_candidates", pd.DataFrame())
    candidate_count = 0 if candidates is None or candidates.empty else len(candidates)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Auto Data Sources", auto_count)
    c2.metric("Parsed Documents", doc_count)
    c3.metric("Candidate Inputs", candidate_count)
    c4.metric("Approved Inputs", approved_count)


def show_reliability_dashboard():
    candidates = st.session_state.get("review_candidates", pd.DataFrame())
    approved = st.session_state.get("approved_inputs", {}) or {}
    summary = build_reliability_summary(candidates, approved)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Candidates", summary["total_candidates"])
    c2.metric("Approved", summary["approved_candidates"])
    c3.metric("High Confidence", summary["high_confidence_candidates"])
    c4.metric("Missing Required", summary["missing_required_fields"])


# =============================================================================
# Placeholder for other scoreboards
# =============================================================================

if scoreboard_type != "Special Assessment Debt":
    st.header(scoreboard_type)
    st.info("This scoreboard type is reserved for the next build. The reliability workflow shell is ready.")
    st.stop()


# =============================================================================
# Main Unified Page
# =============================================================================

source_status_cards()

tab_auto, tab_docs, tab_review, tab_scorecard, tab_calcs, tab_sources = st.tabs(
    [
        "1 Auto Data Pull",
        "2 Documents",
        "3 Reliability Review",
        "4 Scorecard",
        "5 Calculators",
        "6 Sources & Evidence",
    ]
)


# =============================================================================
# Tab 1: Auto Data Pull
# =============================================================================

with tab_auto:
    st.header("Auto Data Pull")
    st.write(
        "Use automatic connectors for stable and structured data. "
        "Complex PDF-heavy deal data should still be uploaded in the Documents tab."
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        state_fips = st.text_input("State FIPS", value="06", help="California = 06")
        geography_type = st.selectbox("Geography Type", ["county", "place"])
        place_or_county = st.text_input("County / Place FIPS", value="067", help="Sacramento County = 067")

    with col2:
        county_name = st.text_input("County Name", value="Sacramento County")
        location_name = st.text_input("Location / MSA Name", value="Sacramento-Roseville-Arden")
        census_year = st.number_input("ACS Year", min_value=2018, max_value=2024, value=2023, step=1)

    with col3:
        try:
            default_census_key = st.secrets.get("CENSUS_API_KEY", "")
        except Exception:
            default_census_key = ""
        try:
            default_fred_key = st.secrets.get("FRED_API_KEY", "")
        except Exception:
            default_fred_key = ""

        census_api_key = st.text_input("Census API Key Override", type="password", value="")
        fred_api_key = st.text_input("FRED API Key Override", type="password", value="")

    if st.button("Run Structured Auto Pull", type="primary"):
        with st.spinner("Pulling structured data..."):
            bundle = auto_pull_structured_data(
                state_fips=state_fips,
                place_or_county=place_or_county,
                geography_type=geography_type,
                county_name=county_name,
                location_name=location_name,
                census_year=int(census_year),
                census_api_key=census_api_key or default_census_key or None,
                fred_api_key=fred_api_key or default_fred_key or None,
            )

        st.session_state["auto_data_results"] = bundle.get("results", [])
        merge_approved_inputs(bundle.get("approved_inputs", {}))
        refresh_candidates()
        st.success("Auto data pull completed. Candidate inputs were added to Reliability Review.")

    if st.session_state.get("auto_data_results"):
        st.subheader("Auto Data Results")
        auto_df = auto_data_results_to_dataframe(st.session_state["auto_data_results"])
        st.dataframe(auto_df, use_container_width=True)

    st.markdown("### Connector Strategy")
    st.dataframe(
        pd.DataFrame(
            [
                ["Census / ACS", "Income, population", "Auto connector"],
                ["BLS / LAUS", "Local unemployment", "Next connector; currently placeholder"],
                ["FRED", "Macro rates / national unemployment", "Optional API key"],
                ["County Open Data", "Assessed value", "County-specific connector later"],
                ["Housing Data", "Trend / distress proxy", "Source decision later"],
                ["EMMA / OS", "Deal-specific PDF/tables", "Upload + document extraction"],
            ],
            columns=["Source", "Target Data", "Current Treatment"],
        ),
        use_container_width=True,
    )


# =============================================================================
# Tab 2: Documents
# =============================================================================

with tab_docs:
    st.header("Document Upload & Parsing")
    st.write(
        "Upload OS, appendices, taxpayer tables, debt service schedules, MLTM tables, or VTL workbooks. "
        "AI extraction will only use these uploaded files."
    )

    uploaded_files = st.file_uploader(
        "Upload source files",
        type=["pdf", "csv", "xlsx", "xls", "txt"],
        accept_multiple_files=True,
    )

    if uploaded_files:
        parsed_docs = []
        with st.spinner("Parsing uploaded documents..."):
            for uploaded_file in uploaded_files:
                parsed_docs.append(read_uploaded_file_to_context(uploaded_file))

        st.session_state["parsed_documents"] = parsed_docs
        st.success(f"Parsed {len(parsed_docs)} document(s).")

    parsed_docs = st.session_state.get("parsed_documents", [])

    if parsed_docs:
        for doc in parsed_docs:
            with st.expander(doc.get("file_name"), expanded=False):
                if doc.get("warnings"):
                    for warning in doc.get("warnings"):
                        st.warning(warning)

                st.text_area("Parsed Text Preview", doc.get("text", "")[:5000], height=220)

                for table in doc.get("tables", []):
                    st.write(table.get("table_name"))
                    st.dataframe(pd.DataFrame(table.get("preview", [])), use_container_width=True)
    else:
        st.info("No parsed documents yet.")


# =============================================================================
# Tab 3: Reliability Review
# =============================================================================

with tab_review:
    st.header("Reliability Review")
    st.write(
        "Candidate values from auto connectors and document AI extraction are reviewed here. "
        "Only approved final values feed the scorecard."
    )

    show_reliability_dashboard()

    parsed_docs = st.session_state.get("parsed_documents", [])

    with st.expander("Run Document AI Extraction", expanded=False):
        try:
            default_openai_key = st.secrets.get("OPENAI_API_KEY", "")
        except Exception:
            default_openai_key = ""

        col1, col2 = st.columns(2)

        with col1:
            issuer_name = st.text_input("Issuer / District Name", value="Laguna Ridge CFD")
            state = st.text_input("State", value="CA")
            county_or_region = st.text_input("County / Region", value="Sacramento County")
            bond_type = st.selectbox("Bond Type", ["Special Assessment Debt", "CFD / Mello-Roos", "Special Tax Bonds"])

        with col2:
            model = st.selectbox("OpenAI Model", ["gpt-4.1-mini", "gpt-4.1", "gpt-4o-mini"], index=0)
            api_key_input = st.text_input("OpenAI API Key Override", type="password", value="")

        selected_targets = st.multiselect("Fields to Extract from Uploaded Documents", DEFAULT_TARGETS, default=DEFAULT_TARGETS)

        if not parsed_docs:
            st.warning("Upload documents first in Tab 2.")

        if st.button("Run Document Extraction", type="primary", disabled=not parsed_docs):
            with st.spinner("Extracting scorecard candidates from uploaded documents..."):
                result = run_document_ai_extraction(
                    issuer_name=issuer_name,
                    state=state,
                    county_or_region=county_or_region,
                    bond_type=bond_type,
                    selected_targets=selected_targets,
                    parsed_docs=parsed_docs,
                    api_key=api_key_input or default_openai_key,
                    model=model,
                )

            st.session_state["last_document_ai_result"] = result
            refresh_candidates()

            if not result.get("ok", False):
                st.error(result.get("error", "Document extraction failed."))
            else:
                st.success("Document extraction completed. Candidate inputs added below.")

    if st.button("Refresh Candidate Inputs"):
        refresh_candidates()
        st.success("Candidates refreshed.")

    candidates = st.session_state.get("review_candidates", pd.DataFrame())
    candidates = normalize_candidate_dataframe(candidates)

    st.markdown("### Candidate Input Review Table")
    st.caption(
        "Edit approve/reject, analyst override fields, and notes. "
        "The final value uses analyst override first, then extracted numeric value, then extracted raw value."
    )

    reviewed_df = st.data_editor(
        candidates,
        use_container_width=True,
        num_rows="dynamic",
        key="reliability_review_table",
        column_config={
            "source_excerpt": st.column_config.TextColumn("source_excerpt", width="large"),
            "notes": st.column_config.TextColumn("notes", width="large"),
            "confidence": st.column_config.NumberColumn("confidence", min_value=0.0, max_value=1.0, step=0.05),
            "source_priority": st.column_config.NumberColumn("source_priority", disabled=True),
            "confidence_label": st.column_config.TextColumn("confidence_label", disabled=True),
            "review_status": st.column_config.TextColumn("review_status", disabled=True),
            "final_value": st.column_config.TextColumn("final_value", disabled=True),
        },
    )

    reviewed_df = normalize_candidate_dataframe(reviewed_df)
    st.session_state["review_candidates"] = reviewed_df

    if st.button("Approve Reviewed Values to Scorecard", type="primary"):
        approved_inputs = approved_candidates_to_scorecard_inputs(reviewed_df)
        merge_approved_inputs(approved_inputs)
        st.success("Approved reviewed values saved to scorecard inputs.")

    st.markdown("### Missing Data Tracker")
    missing_df = missing_data_tracker(st.session_state.get("approved_inputs", {}))
    st.dataframe(missing_df, use_container_width=True)

    st.markdown("### Evidence Viewer")
    if reviewed_df.empty:
        st.info("No candidate evidence available yet.")
    else:
        candidate_labels = [
            f"{idx}: {row['scorecard_field']} | {row['value']} | {row['source_document']}"
            for idx, row in reviewed_df.iterrows()
        ]
        selected_label = st.selectbox("Select Evidence Item", candidate_labels)
        selected_idx = int(selected_label.split(":")[0])
        selected = reviewed_df.loc[selected_idx].to_dict()

        c1, c2 = st.columns(2)
        with c1:
            st.write("**Field:**", selected.get("scorecard_field"))
            st.write("**Extracted Value:**", selected.get("value"))
            st.write("**Final Value:**", selected.get("final_value"))
            st.write("**Confidence:**", selected.get("confidence_label"), selected.get("confidence"))
            st.write("**Source Priority:**", selected.get("source_priority"))
        with c2:
            st.write("**Source Type:**", selected.get("source_type"))
            st.write("**Source Document:**", selected.get("source_document"))
            st.write("**Source URL:**", selected.get("source_url"))
            st.write("**Review Status:**", selected.get("review_status"))

        st.text_area("Source Excerpt", selected.get("source_excerpt", ""), height=180)
        st.text_area("Analyst Notes", selected.get("notes", ""), height=120)


# =============================================================================
# Tab 4: Scorecard
# =============================================================================

with tab_scorecard:
    st.header("Special Assessment Debt Scorecard")

    defaults = get_default_scorecard_inputs()

    if workflow_mode == "Manual Input Only":
        st.info("Manual mode: edit values directly below.")
    else:
        st.info("Integrated mode: values below may be prefilled from approved Reliability Review inputs.")

    with st.expander("A. Economic Fundamentals Assessment", expanded=True):
        col1, col2 = st.columns(2)

        with col1:
            median_household_ebi_percent_of_us = st.number_input(
                "Median Household EBI (% of U.S.)",
                min_value=0.0,
                max_value=500.0,
                value=float(defaults["median_household_ebi_percent_of_us"]),
                step=1.0,
            )
            unemployment_rate_difference_vs_us = st.number_input(
                "Unemployment Rate Difference vs U.S. (%)",
                value=float(defaults["unemployment_rate_difference_vs_us"]),
                step=0.1,
            )
            population_growth_difference_vs_us = st.number_input(
                "Population Growth Difference vs U.S. (%)",
                value=float(defaults["population_growth_difference_vs_us"]),
                step=0.1,
            )

        with col2:
            msa_options = ["Yes; Broad & Diverse", "Yes; Not Broad & Diverse", "No"]
            msa_default = defaults.get("msa_participation", msa_options[0])
            msa_index = msa_options.index(msa_default) if msa_default in msa_options else 0
            msa_participation = st.selectbox("MSA Participation", msa_options, index=msa_index)

            re_options = [
                "Low Volatility; Stable Prices; Low Distress",
                "Elevated Volatility; Stable Prices; Affordability Worse Than National Figures",
                "Falling Local Home Prices; High Price Volatility; Low Affordability; Rising Distress",
                "Falling Local Home Prices; High Price Volatility; Significantly Worse Affordability; Rising Distress",
            ]
            re_default = defaults.get("real_estate_market_volatility", re_options[0])
            re_index = re_options.index(re_default) if re_default in re_options else 0
            real_estate_market_volatility = st.selectbox("Real Estate Market Volatility", re_options, index=re_index)

    with st.expander("B. District Characteristics Assessment", expanded=True):
        col3, col4 = st.columns(2)

        with col3:
            top10_taxpayers_percent_of_total_levy = st.number_input(
                "Top 10 Taxpayers as % of Total Levy",
                min_value=0.0,
                max_value=100.0,
                value=float(defaults["top10_taxpayers_percent_of_total_levy"]),
                step=0.1,
            )
            largest_taxpayer_percent_of_total_levy = st.number_input(
                "Largest Taxpayer as % of Total Levy",
                min_value=0.0,
                max_value=100.0,
                value=float(defaults["largest_taxpayer_percent_of_total_levy"]),
                step=0.1,
            )
            district_size_parcels = st.number_input(
                "District Size (Parcels)",
                min_value=0,
                value=int(float(defaults["district_size_parcels"])),
                step=100,
            )

        with col4:
            conveyance_options = [
                "All or Nearly All Conveyed",
                "Most Conveyed",
                "Fairly Developed with Significant Conveyance (Some Developer Concentration)",
                "Developed; Significant Undeveloped Parcels Comprise Minority (Large Developer Concentration)",
                "Undeveloped with Limited Vertical Construction; High Concentration",
            ]
            conv_default = defaults.get("conveyance_to_homeowners", conveyance_options[2])
            conv_index = conveyance_options.index(conv_default) if conv_default in conveyance_options else 2
            conveyance_to_homeowners = st.selectbox("Conveyance to Homeowners", conveyance_options, index=conv_index)

            est_value_to_lien = st.number_input(
                "Est. Value-to-Lien",
                min_value=0.0,
                value=float(defaults["est_value_to_lien"]),
                step=0.1,
            )

    with st.expander("C. Financial Profile Assessment", expanded=True):
        maximum_loss_to_maturity_percent = st.number_input(
            "Maximum Loss-to-Maturity (MLTM) %",
            min_value=0.0,
            max_value=100.0,
            value=float(defaults["maximum_loss_to_maturity_percent"]),
            step=0.1,
        )

    with st.expander("D. Overriding Factors / Caps / Holistic Analysis", expanded=False):
        col5, col6, col7 = st.columns(3)
        with col5:
            negative_override_notches = st.number_input("Negative Overriding Factors (Notches)", min_value=0, max_value=5, value=0, step=1)
        with col6:
            holistic_adjustment_notches = st.number_input("Holistic Analysis Adjustment (Notches)", min_value=-1, max_value=1, value=0, step=1)
        with col7:
            rating_cap = st.selectbox("Rating Cap", ["None", "bbb", "bb", "b category"])

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
# Tab 5: Calculators
# =============================================================================

with tab_calcs:
    st.header("Analytical Calculators")

    calc_tab1, calc_tab2, calc_tab3 = st.tabs(
        ["Taxpayer Concentration", "Value-to-Lien", "MLTM Stress Test"]
    )

    with calc_tab1:
        st.subheader("Taxpayer Concentration Builder")
        default_taxpayers = pd.DataFrame(
            {
                "taxpayer_name": [
                    "Lennar Landbank", "Lennar", "Risewell Landbank", "Risewell",
                    "Beazer Landbank", "Beazer", "Dignity Community Care",
                    "Ridge EG West LP", "PF Portfolio 2 LP", "EGBL 15 LLC",
                ],
                "levy_percent": [6.1, 0.0, 4.0, 0.0, 1.5, 0.0, 1.5, 1.4, 0.9, 0.7],
            }
        )

        taxpayer_df = st.data_editor(default_taxpayers, num_rows="dynamic", use_container_width=True)

        if st.button("Calculate Taxpayer Concentration"):
            concentration = calculate_taxpayer_concentration(taxpayer_df)
            new_inputs = {
                "top10_taxpayers_percent_of_total_levy": concentration["top10_taxpayers_percent_of_total_levy"],
                "largest_taxpayer_percent_of_total_levy": concentration["largest_taxpayer_percent_of_total_levy"],
            }
            merge_approved_inputs(new_inputs)
            c1, c2 = st.columns(2)
            c1.metric("Top 10 Taxpayers %", concentration["top10_taxpayers_percent_of_total_levy"])
            c2.metric("Largest Taxpayer %", concentration["largest_taxpayer_percent_of_total_levy"])
            st.dataframe(concentration["taxpayer_table"], use_container_width=True)

    with calc_tab2:
        st.subheader("Value-to-Lien Calculator")
        col1, col2 = st.columns(2)

        with col1:
            assessed_value = st.number_input("Assessed Value", min_value=0.0, value=3454244692.0, step=1000000.0)
            direct_debt = st.number_input("Direct Debt", min_value=0.0, value=183240000.0, step=1000000.0)

        with col2:
            overlapping_debt = st.number_input("Overlapping Debt", min_value=0.0, value=38445099.0, step=1000000.0)
            include_overlapping_debt = st.checkbox("Include Overlapping Debt", value=True)

        if st.button("Calculate Value-to-Lien"):
            vtl_results = calculate_value_to_lien(assessed_value, direct_debt, overlapping_debt, include_overlapping_debt)
            merge_approved_inputs({"est_value_to_lien": vtl_results["estimated_value_to_lien"]})
            c1, c2 = st.columns(2)
            c1.metric("Debt Base", f"{vtl_results['debt_base_for_vtl']:,.0f}")
            c2.metric("Est. Value-to-Lien", vtl_results["estimated_value_to_lien"])
            st.json(vtl_results)

    with calc_tab3:
        st.subheader("Maximum Loss-to-Maturity Stress Test")
        initial_reserve_fund = st.number_input("Initial Reserve Fund", min_value=0.0, value=15439154.0, step=100000.0)

        default_cashflow = pd.DataFrame(
            {
                "year": list(range(2027, 2037)),
                "special_tax_levy": [12191803, 12460759, 12710019, 12959939, 13219518, 13492483, 13758628, 14025653, 14138513, 14239823],
                "annual_debt_service": [11108912, 11327963, 11554563, 11781763, 12017744, 12265894, 12507844, 12750594, 12853194, 12945294],
            }
        )

        cashflow_df = st.data_editor(default_cashflow, num_rows="dynamic", use_container_width=True)

        if st.button("Calculate MLTM"):
            mltm_results = calculate_mltm_from_cashflow(cashflow_df, initial_reserve_fund=initial_reserve_fund)
            merge_approved_inputs({"maximum_loss_to_maturity_percent": mltm_results["maximum_loss_to_maturity_percent"]})
            c1, c2, c3 = st.columns(3)
            c1.metric("Estimated MLTM %", mltm_results["maximum_loss_to_maturity_percent"])
            c2.metric("Total Revenue", f"{mltm_results['total_revenue']:,.0f}")
            c3.metric("Total Debt Service", f"{mltm_results['total_debt_service']:,.0f}")
            st.dataframe(mltm_results["mltm_cashflow_table"], use_container_width=True)


# =============================================================================
# Tab 6: Sources & Evidence
# =============================================================================

with tab_sources:
    st.header("Sources & Evidence")

    st.subheader("Source Priority Engine")
    st.dataframe(source_priority_table(), use_container_width=True)

    st.subheader("Missing Data Tracker")
    st.dataframe(missing_data_tracker(st.session_state.get("approved_inputs", {})), use_container_width=True)

    st.subheader("Approved Scorecard Inputs")
    approved = st.session_state.get("approved_inputs", {}) or {}
    approved_df = pd.DataFrame([{"scorecard_key": k, "value": v} for k, v in approved.items()])
    st.dataframe(approved_df, use_container_width=True)

    st.subheader("Candidate Evidence")
    candidates = normalize_candidate_dataframe(st.session_state.get("review_candidates", pd.DataFrame()))
    st.dataframe(candidates, use_container_width=True)

    st.subheader("Auto Data Results")
    if st.session_state.get("auto_data_results"):
        st.dataframe(auto_data_results_to_dataframe(st.session_state["auto_data_results"]), use_container_width=True)
    else:
        st.info("No auto data results yet.")

    if st.session_state.get("last_scorecard_results"):
        st.subheader("Latest Scorecard Explanation")
        st.markdown(st.session_state["last_scorecard_results"].get("scorecard_explanation", ""))
