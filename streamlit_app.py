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

st.subheader("Upload Financial Data")

uploaded_file = st.file_uploader(
    "Upload CSV File",
    type=["csv"],
)


def read_uploaded_csv(file):
    try:
        return pd.read_csv(file, encoding="utf-8")
    except UnicodeDecodeError:
        file.seek(0)
        try:
            return pd.read_csv(file, encoding="utf-8-sig")
        except UnicodeDecodeError:
            file.seek(0)
            return pd.read_csv(file, encoding="latin1")


if uploaded_file is not None:
    df = read_uploaded_csv(uploaded_file)

    st.subheader("Preview Data")
    st.dataframe(df)

    st.success("File uploaded successfully.")

    if criteria_type == "Special Assessment":
        inputs = df.iloc[0].to_dict()

        results = calculate_special_assessment_scorecard(inputs)

        st.subheader("Scorecard Results")
        st.write(results)

    else:
        st.info("Scoring engine for this criteria type has not been built yet.")
