import streamlit as st
import pandas as pd
import os
import subprocess
import plotly.express as px
import sys
import traceback

def show_error(e):
    st.error(f"An error occurred: {e}")
    st.text("Traceback:")
    st.text("".join(traceback.format_exception(*sys.exc_info())))

st.set_page_config(layout="wide")
st.title("Trade Data Explorer")

try:
    st.sidebar.header("Filters")
    st.info("Initializing app...")

    # Kaggle credentials
    try:
        os.environ['KAGGLE_USERNAME'] = st.secrets["KAGGLE_USERNAME"]
        os.environ['KAGGLE_KEY'] = st.secrets["KAGGLE_KEY"]
    except KeyError:
        st.error("Missing Kaggle credentials.")
        st.stop()

    dataset_slug = "shevaserrattan/can-sut20232024"
    local_filename = "df_imp_all.csv"
    data_dir = "data"

    if not os.path.exists(local_filename):
        with st.spinner("Downloading dataset from Kaggle..."):
            os.makedirs(data_dir, exist_ok=True)
            result = subprocess.run([
                "kaggle", "datasets", "download",
                "-d", dataset_slug,
                "--unzip", "-p", data_dir
            ], capture_output=True, text=True)
            if result.returncode != 0:
                st.error(f"Download failed: {result.stderr}")
                st.stop()
            for file in os.listdir(data_dir):
                if file.endswith(".csv"):
                    os.rename(os.path.join(data_dir, file), local_filename)

    rename_map = {
        "HS10": "HS10",
        "Country/Pays": "Country",
        "Province": "Province",
        "State/État": "State",
        "Unit of Measure/Unité de Mesure": "UoM",
        "YearMonth/AnnéeMois": "YearMonth",
        "Value/Valeur": "Value",
        "Quantity/Quantité": "Quantity"
    }

    # Load sample for filters
    try:
        sample = pd.read_csv(local_filename, nrows=50000)
        sample.rename(columns={k: v for k, v in rename_map.items() if k in sample.columns}, inplace=True)
        if "YearMonth" not in sample.columns:
            st.error("Column 'YearMonth' missing in sample.")
            st.stop()
        sample["YearMonth"] = pd.to_numeric(sample["YearMonth"], errors="coerce")
        sample.dropna(subset=["YearMonth"], inplace=True)
        years = sorted((sample["YearMonth"] // 100).astype(int).unique())
        countries = sorted(sample.get("Country", pd.Series()).dropna().unique())
        provinces = sorted(sample.get("Province", pd.Series()).dropna().unique())
        states = sorted(sample.get("State", pd.Series()).dropna().unique())
    except Exception as e:
        show_error(e)
        st.stop()

    selected_years = st.sidebar.multiselect("Select Year(s):", years)
    selected_country = st.sidebar.selectbox("Country:", ["All"] + countries)
    selected_province = st.sidebar.selectbox("Province:", ["All"] + provinces)
    selected_state = st.sidebar.selectbox("State:", ["All"] + states)

    # Load filtered data
    filtered_chunks = []
    try:
        for chunk in pd.read_csv(local_filename, chunksize=100000):
            chunk.rename(columns={k: v for k, v in rename_map.items() if k in chunk.columns}, inplace=True)
            if "YearMonth" not in chunk.columns:
                st.error("Column 'YearMonth' missing in chunk.")
                st.stop()
            chunk["YearMonth"] = pd.to_numeric(chunk["YearMonth"], errors="coerce")
            chunk.dropna(subset=["YearMonth"], inplace=True)
            chunk["Year"] = (chunk["YearMonth"] // 100).astype(int)

            if selected_years:
                chunk = chunk[chunk["Year"].isin(selected_years)]
            if selected_country != "All":
                chunk = chunk[chunk.get("Country", "") == selected_country]
            if selected_province != "All":
                chunk = chunk[chunk.get("Province", "") == selected_province]
            if selected_state != "All":
                chunk = chunk[chunk.get("State", "") == selected_state]

            if not chunk.empty:
                filtered_chunks.append(chunk)
    except Exception as e:
        show_error(e)
        st.stop()

    if not filtered_chunks:
        st.warning("No data matches your filters.")
        st.stop()

    filtered_df = pd.concat(filtered_chunks)

    # Summary
    st.subheader("Summary Statistics")
    st.write(f"Total Records: {len(filtered_df):,}")
    st.write(f"Total Import Value: {filtered_df['Value'].sum():,.2f}")
    st.write(f"Total Quantity: {filtered_df['Quantity'].sum():,.2f}")

    # Visualizations
    yearly_trend = filtered_df.groupby("Year", as_index=False)["Value"].sum()
    st.plotly_chart(px.line(yearly_trend, x="Year", y="Value", title="Import Value by Year"), width="stretch")

    top_countries = filtered_df.groupby("Country", as_index=False)["Value"].sum().sort_values("Value", ascending=False).head(10)
    st.plotly_chart(px.bar(top_countries, x="Country", y="Value", title="Top 10 Countries"), width="stretch")

    province_breakdown = filtered_df.groupby("Province", as_index=False)["Value"].sum().sort_values("Value", ascending=False)
    st.plotly_chart(px.bar(province_breakdown, x="Province", y="Value", title="Import Value by Province"), width="stretch")

    st.subheader("Filtered Data Preview")
    st.dataframe(filtered_df.head(100))

except Exception as e:
    show_error(e)
