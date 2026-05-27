import streamlit as st
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

import pandas as pd
st.subheader("Upload Financial Data")
uploaded_file = st.file_uploader(
    "Upload CSV File",
    type=["csv"]
)
if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    st.subheader("Preview Data")
    st.dataframe(df)
    st.success("File uploaded successfully.")
