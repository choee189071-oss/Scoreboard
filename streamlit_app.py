import streamlit as st
import pandas as pd

from modules.scoring_special_assessment import (
    calculate_special_assessment_scorecard,
    calculate_taxpayer_concentration,
    calculate_value_to_lien,
    calculate_mltm_from_cashflow,
)

from modules.document_ai_extraction import (
    DEFAULT_TARGETS,
    read_uploaded_file_to_context,
    run_document_ai_extraction,
    build_mock_document_ai_result,
    extracted_fields_to_dataframe,
    derived_calculations_to_dataframe,
    approved_fields_to_scorecard_inputs,
)

st.set_page_config(page_title="Municipal Credit Analytics Platform", layout="wide")

st.title("Municipal Credit Analytics Platform")
st.caption("Document-first scorecard workflow: upload source files → parse → AI extract → analyst review → scorecard.")


# =============================================================================
# Session State Defaults
# =============================================================================

defaults = {
    "top10_taxpayers_percent_of_total_levy": 16.1,
    "largest_taxpayer_percent_of_total_levy": 6.1,
    "est_value_to_lien": 15.5,
    "maximum_loss_to_maturity_percent": 13.9,
    "last_scorecard_results": None,
    "approved_ai_inputs": {},
    "parsed_documents": [],
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


# =============================================================================
# Sidebar
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

st.sidebar.header("2. Workflow Mode")

workflow_mode = st.sidebar.radio(
    "Select Mode",
    [
        "Manual Input",
        "Document-First AI Extraction",
        "Upload Scorecard CSV",
    ],
)

st.sidebar.header("3. Analytical Workspace")

workspace = st.sidebar.selectbox(
    "Select Workspace",
    [
        "Main Scorecard",
        "Document Retrieval / Upload",
        "AI Extraction Review",
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
# Helper Functions
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

    factor_df = pd.DataFrame(
        [
            ["Economic Fundamentals Assessment", "15%", results.get("economic_fundamentals_assessment"), results.get("economic_fundamentals_assessment_category")],
            ["District Characteristics Assessment", "35%", results.get("district_characteristics_assessment"), results.get("district_characteristics_assessment_category")],
            ["Financial Profile Assessment", "50%", results.get("financial_profile_assessment"), results.get("financial_profile_assessment_category")],
        ],
        columns=["Key Credit Factor", "Weight", "Numeric Assessment", "Assessment Category"],
    )

    st.markdown("### Key Credit Factor Assessments")
    st.dataframe(factor_df, use_container_width=True)

    st.markdown("### Explanation")
    st.markdown(results.get("scorecard_explanation", ""))

    with st.expander("Raw Results JSON"):
        st.json(results)


def calculate_current_scorecard(inputs: dict):
    results = calculate_special_assessment_scorecard(inputs)
    st.session_state["last_scorecard_results"] = results
    return results


def get_default_scorecard_inputs():
    approved = st.session_state.get("approved_ai_inputs", {}) or {}

    inputs = {
        "median_household_ebi_percent_of_us": approved.get("median_household_ebi_percent_of_us", 144.0),
        "unemployment_rate_difference_vs_us": approved.get("unemployment_rate_difference_vs_us", -0.3),
        "msa_participation": approved.get("msa_participation", "Yes; Broad & Diverse"),
        "real_estate_market_volatility": approved.get("real_estate_market_volatility", "Low Volatility; Stable Prices; Low Distress"),
        "population_growth_difference_vs_us": approved.get("population_growth_difference_vs_us", 0.5),
        "top10_taxpayers_percent_of_total_levy": approved.get(
            "top10_taxpayers_percent_of_total_levy",
            st.session_state.get("top10_taxpayers_percent_of_total_levy", 16.1),
        ),
        "largest_taxpayer_percent_of_total_levy": approved.get(
            "largest_taxpayer_percent_of_total_levy",
            st.session_state.get("largest_taxpayer_percent_of_total_levy", 6.1),
        ),
        "district_size_parcels": approved.get("district_size_parcels", 5900),
        "conveyance_to_homeowners": approved.get(
            "conveyance_to_homeowners",
            "Fairly Developed with Significant Conveyance (Some Developer Concentration)",
        ),
        "est_value_to_lien": approved.get("est_value_to_lien", st.session_state.get("est_value_to_lien", 15.5)),
        "maximum_loss_to_maturity_percent": approved.get(
            "maximum_loss_to_maturity_percent",
            st.session_state.get("maximum_loss_to_maturity_percent", 13.9),
        ),
        "negative_override_notches": 0,
        "holistic_adjustment_notches": 0,
        "rating_cap": "None",
    }

    return inputs


# =============================================================================
# Placeholder for other scoreboard types
# =============================================================================

if scoreboard_type != "Special Assessment Debt":
    st.header(scoreboard_type)
    st.info("This scoreboard type is reserved for the next build. The platform structure is ready.")
    st.stop()


# =============================================================================
# Workspace: Document Retrieval / Upload
# =============================================================================

if workspace == "Document Retrieval / Upload":
    st.header("Document Retrieval / Upload Layer")

    st.write(
        "Upload the actual source documents first. The platform parses them locally into structured context. "
        "AI extraction will only use this uploaded context."
    )

    uploaded_files = st.file_uploader(
        "Upload OS / Appendix / Debt Service Table / Taxpayer Table / VTL Table / MLTM Table",
        type=["pdf", "csv", "xlsx", "xls", "txt"],
        accept_multiple_files=True,
    )

    if uploaded_files:
        parsed_docs = []

        with st.spinner("Parsing uploaded documents..."):
            for uploaded_file in uploaded_files:
                parsed = read_uploaded_file_to_context(uploaded_file)
                parsed_docs.append(parsed)

        st.session_state["parsed_documents"] = parsed_docs

        st.success(f"Parsed {len(parsed_docs)} document(s).")

        for doc in parsed_docs:
            with st.expander(f"{doc.get('file_name')}"):
                if doc.get("warnings"):
                    for warning in doc.get("warnings"):
                        st.warning(warning)

                preview_text = doc.get("text", "")[:5000]
                st.text_area("Parsed Text Preview", preview_text, height=250)

                if doc.get("tables"):
                    st.markdown("Detected Tables / Sheet Previews")
                    for table in doc.get("tables", []):
                        st.write(table.get("table_name"))
                        st.dataframe(pd.DataFrame(table.get("preview", [])), use_container_width=True)

    else:
        st.info("Upload source files to begin.")

    st.stop()


# =============================================================================
# Workflow: Document-first AI Extraction
# =============================================================================

if workflow_mode == "Document-First AI Extraction" or workspace == "AI Extraction Review":
    st.header("Document-First AI Extraction")

    st.write(
        "This mode extracts scorecard inputs from uploaded documents only. "
        "It is safer than asking AI to search the web because every value must trace back to a provided source."
    )

    parsed_docs = st.session_state.get("parsed_documents", [])

    if not parsed_docs:
        st.warning("No parsed documents found. Go to 'Document Retrieval / Upload' first.")
    else:
        st.success(f"{len(parsed_docs)} parsed document(s) available.")

    try:
        default_api_key = st.secrets.get("OPENAI_API_KEY", "")
    except Exception:
        default_api_key = ""

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
        model = st.selectbox("OpenAI Model", ["gpt-4.1-mini", "gpt-4.1", "gpt-4o-mini"], index=0)
        api_key_input = st.text_input(
            "OpenAI API Key Override",
            type="password",
            value="",
            help="Optional. Prefer Streamlit secrets: OPENAI_API_KEY.",
        )
        use_mock_mode = st.checkbox("Use Mock Mode for Debugging", value=not bool(parsed_docs))

    selected_targets = st.multiselect(
        "Fields to Extract",
        DEFAULT_TARGETS,
        default=DEFAULT_TARGETS,
    )

    if st.button("Run Document AI Extraction", type="primary"):
        with st.spinner("Extracting scorecard candidates from uploaded documents..."):
            if use_mock_mode:
                result = build_mock_document_ai_result(issuer_name, selected_targets)
            else:
                result = run_document_ai_extraction(
                    issuer_name=issuer_name,
                    state=state,
                    county_or_region=county,
                    bond_type=bond_type,
                    selected_targets=selected_targets,
                    parsed_docs=parsed_docs,
                    api_key=api_key_input or default_api_key,
                    model=model,
                )

        st.session_state["last_document_ai_result"] = result

    if "last_document_ai_result" in st.session_state:
        result = st.session_state["last_document_ai_result"]

        if not result.get("ok", False):
            st.error(result.get("error", "Document AI extraction failed."))
            if "raw_response" in result:
                with st.expander("Raw AI Response"):
                    st.write(result["raw_response"])
        else:
            st.success("Extraction completed.")

        st.markdown("### Summary")
        st.write(result.get("summary", ""))

        warnings = result.get("warnings", [])
        if warnings:
            with st.expander("Warnings"):
                for warning in warnings:
                    st.warning(warning)

        st.markdown("### Candidate Values for Analyst Review")
        extracted_df = extracted_fields_to_dataframe(result)

        reviewed_df = st.data_editor(
            extracted_df,
            use_container_width=True,
            num_rows="dynamic",
            key="document_ai_review_table",
        )

        st.markdown("### Derived Calculations")
        calculations_df = derived_calculations_to_dataframe(result)
        st.dataframe(calculations_df, use_container_width=True)

        if st.button("Approve Selected Values and Save to Scorecard"):
            approved_inputs = approved_fields_to_scorecard_inputs(reviewed_df)

            st.session_state["approved_ai_inputs"] = approved_inputs

            for key, value in approved_inputs.items():
                st.session_state[key] = value

            for scorecard_key in [
                "top10_taxpayers_percent_of_total_levy",
                "largest_taxpayer_percent_of_total_levy",
                "est_value_to_lien",
                "maximum_loss_to_maturity_percent",
            ]:
                if scorecard_key in approved_inputs:
                    st.session_state[scorecard_key] = approved_inputs[scorecard_key]

            st.success("Approved values saved. Switch to Main Scorecard to review and calculate.")

        if st.button("Run Scorecard Using Approved Values"):
            inputs = get_default_scorecard_inputs()
            inputs.update(st.session_state.get("approved_ai_inputs", {}))
            results = calculate_current_scorecard(inputs)
            render_scorecard_results(results)

    if workspace == "AI Extraction Review":
        st.stop()


# =============================================================================
# Workspace: Main Scorecard
# =============================================================================

if workspace == "Main Scorecard":
    st.header("Special Assessment Debt Scorecard")

    if workflow_mode == "Upload Scorecard CSV":
        st.subheader("Upload Scorecard Inputs")
        uploaded_file = st.file_uploader("Upload CSV File", type=["csv"])

        if uploaded_file is not None:
            df = read_uploaded_csv(uploaded_file)
            st.dataframe(df, use_container_width=True)

            if not df.empty:
                inputs = df.iloc[0].to_dict()
                results = calculate_current_scorecard(inputs)
                render_scorecard_results(results)
        st.stop()

    defaults = get_default_scorecard_inputs()

    st.subheader("A. Economic Fundamentals Assessment")

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
            help="Local unemployment rate minus national unemployment rate.",
        )

        population_growth_difference_vs_us = st.number_input(
            "Population Growth Difference vs U.S. (%)",
            value=float(defaults["population_growth_difference_vs_us"]),
            step=0.1,
        )

    with col2:
        msa_options = ["Yes; Broad & Diverse", "Yes; Not Broad & Diverse", "No"]
        msa_default = defaults.get("msa_participation", "Yes; Broad & Diverse")
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

    st.subheader("B. District Characteristics Assessment")

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

    st.subheader("C. Financial Profile Assessment")

    maximum_loss_to_maturity_percent = st.number_input(
        "Maximum Loss-to-Maturity (MLTM) %",
        min_value=0.0,
        max_value=100.0,
        value=float(defaults["maximum_loss_to_maturity_percent"]),
        step=0.1,
    )

    st.subheader("D. Overriding Factors / Caps / Holistic Analysis")

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
# Workspace: Taxpayer Concentration Builder
# =============================================================================

elif workspace == "Taxpayer Concentration Builder":
    st.header("Taxpayer Concentration Builder")

    mode = st.radio("Input Mode", ["Manual Table", "Upload CSV"])

    if mode == "Manual Table":
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

    else:
        uploaded = st.file_uploader("Upload taxpayer CSV", type=["csv"])
        taxpayer_df = read_uploaded_csv(uploaded) if uploaded is not None else pd.DataFrame()
        if uploaded is not None:
            st.dataframe(taxpayer_df, use_container_width=True)

    if st.button("Calculate Concentration"):
        concentration = calculate_taxpayer_concentration(taxpayer_df)

        st.session_state["top10_taxpayers_percent_of_total_levy"] = concentration["top10_taxpayers_percent_of_total_levy"]
        st.session_state["largest_taxpayer_percent_of_total_levy"] = concentration["largest_taxpayer_percent_of_total_levy"]

        c1, c2 = st.columns(2)
        c1.metric("Top 10 Taxpayers as % of Total Levy", concentration["top10_taxpayers_percent_of_total_levy"])
        c2.metric("Largest Taxpayer as % of Total Levy", concentration["largest_taxpayer_percent_of_total_levy"])

        st.dataframe(concentration["taxpayer_table"], use_container_width=True)


# =============================================================================
# Workspace: Value-to-Lien Calculator
# =============================================================================

elif workspace == "Value-to-Lien Calculator":
    st.header("Value-to-Lien Calculator")

    col1, col2 = st.columns(2)

    with col1:
        assessed_value = st.number_input("Assessed Value", min_value=0.0, value=3454244692.0, step=1000000.0)
        direct_debt = st.number_input("Direct Debt", min_value=0.0, value=183240000.0, step=1000000.0)

    with col2:
        overlapping_debt = st.number_input("Overlapping Debt", min_value=0.0, value=38445099.0, step=1000000.0)
        include_overlapping_debt = st.checkbox("Include Overlapping Debt", value=True)

    if st.button("Calculate Value-to-Lien"):
        vtl_results = calculate_value_to_lien(assessed_value, direct_debt, overlapping_debt, include_overlapping_debt)

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

    initial_reserve_fund = st.number_input("Initial Reserve Fund", min_value=0.0, value=15439154.0, step=100000.0)
    mode = st.radio("Input Mode", ["Manual Table", "Upload CSV"])

    if mode == "Manual Table":
        default_cashflow = pd.DataFrame(
            {
                "year": list(range(2027, 2037)),
                "special_tax_levy": [12191803, 12460759, 12710019, 12959939, 13219518, 13492483, 13758628, 14025653, 14138513, 14239823],
                "annual_debt_service": [11108912, 11327963, 11554563, 11781763, 12017744, 12265894, 12507844, 12750594, 12853194, 12945294],
            }
        )
        cashflow_df = st.data_editor(default_cashflow, num_rows="dynamic", use_container_width=True)
    else:
        uploaded = st.file_uploader("Upload MLTM cashflow CSV", type=["csv"])
        cashflow_df = read_uploaded_csv(uploaded) if uploaded is not None else pd.DataFrame()
        if uploaded is not None:
            st.dataframe(cashflow_df, use_container_width=True)

    if st.button("Calculate MLTM"):
        mltm_results = calculate_mltm_from_cashflow(cashflow_df, initial_reserve_fund=initial_reserve_fund)

        st.session_state["maximum_loss_to_maturity_percent"] = mltm_results["maximum_loss_to_maturity_percent"]

        c1, c2, c3 = st.columns(3)
        c1.metric("Estimated MLTM %", mltm_results["maximum_loss_to_maturity_percent"])
        c2.metric("Total Revenue", f"{mltm_results['total_revenue']:,.0f}")
        c3.metric("Total Debt Service", f"{mltm_results['total_debt_service']:,.0f}")

        st.dataframe(mltm_results["mltm_cashflow_table"], use_container_width=True)


# =============================================================================
# Workspace: Source / Evidence Manager
# =============================================================================

elif workspace == "Source / Evidence Manager":
    st.header("Source / Evidence Manager")

    if "last_document_ai_result" in st.session_state:
        result = st.session_state["last_document_ai_result"]
        extracted_df = extracted_fields_to_dataframe(result)
        st.dataframe(extracted_df, use_container_width=True)
    else:
        st.info("Run Document-First AI Extraction first to populate source evidence.")


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
