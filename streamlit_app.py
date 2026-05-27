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
