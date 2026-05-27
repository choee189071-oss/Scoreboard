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
