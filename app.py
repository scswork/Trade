import streamlit as st
import pandas as pd
import os
import subprocess
import plotly.express as px
from difflib import get_close_matches

st.set_page_config(layout="wide")
st.title("Trade Data Explorer")

# ✅ Sidebar filters
st.sidebar.header("Filters")
selected_years = st.sidebar.text_input("Year(s) (comma-separated):")
selected_country = st.sidebar.text_input("Country:")
selected_province = st.sidebar.text_input("Province:")
selected_state = st.sidebar.text_input("State:")
selected_hs10 = st.sidebar.text_input("HS10 Code:")
description_query = st.sidebar.text_input("Description (fuzzy match):")

load_data = st.sidebar.button("Load & Apply Filters")

# ✅ Dataset Info
dataset_slug = "shevaserrattan/can-sut20232024"
local_filename = "df_imp_all.csv"
data_dir = "data"

# ✅ Cache full dataset
@st.cache_data
def load_full_data():
    df = pd.read_csv(local_filename)
    rename_map = {
        "HS10": "HS10",
        "Description": "Description",
        "Country/Pays": "Country",
        "Province": "Province",
        "State/État": "State",
        "Unit of Measure/Unité de Mesure": "UoM",
        "YearMonth/AnnéeMois": "YearMonth",
        "Value/Valeur": "Value",
        "Quantity/Quantité": "Quantity"
    }
    df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns}, inplace=True)
    df["YearMonth"] = pd.to_numeric(df.get("YearMonth"), errors="coerce")
    df.dropna(subset=["YearMonth"], inplace=True)
    df["Year"] = (df["YearMonth"] // 100).astype(int)
    return df

if load_data:
    # ✅ Download dataset only when button clicked
    if not os.path.exists(local_filename):
        st.info("Dataset not found. Downloading from Kaggle...")
        with st.spinner("Downloading dataset..."):
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

    with st.spinner("Loading and filtering data..."):
        df = load_full_data()

        # ✅ Apply filters
        if selected_years:
            try:
                years_list = [int(y.strip()) for y in selected_years.split(",") if y.strip().isdigit()]
                df = df[df["Year"].isin(years_list)]
            except:
                st.warning("Invalid year format.")
        if selected_country:
            df = df[df.get("Country", "") == selected_country]
        if selected_province:
            df = df[df.get("Province", "") == selected_province]
        if selected_state:
            df = df[df.get("State", "") == selected_state]
        if selected_hs10:
            df = df[df.get("HS10", "").astype(str).str.contains(selected_hs10, case=False)]
        if description_query and "Description" in df.columns:
            descriptions = df["Description"].dropna().unique()
            matches = get_close_matches(description_query, descriptions, n=10, cutoff=0.6)
            if matches:
                df = df[df["Description"].isin(matches)]

        if df.empty:
            st.warning("No data matches your filters.")
            st.stop()

        # ✅ Summary
        st.subheader("Summary Statistics")
        st.write(f"Total Records: {len(df):,}")
        st.write(f"Total Import Value: {df['Value'].sum():,.2f}")
        st.write(f"Total Quantity: {df['Quantity'].sum():,.2f}")

        # ✅ Visualizations
        yearly_trend = df.groupby("Year", as_index=False)["Value"].sum()
        st.plotly_chart(px.line(yearly_trend, x="Year", y="Value", title="Import Value by Year"), width="stretch")

        top_countries = df.groupby("Country", as_index=False)["Value"].sum().sort_values("Value", ascending=False).head(10)
        st.plotly_chart(px.bar(top_countries, x="Country", y="Value", title="Top 10 Countries"), width="stretch")

        province_breakdown = df.groupby("Province", as_index=False)["Value"].sum().sort_values("Value", ascending=False)
        st.plotly_chart(px.bar(province_breakdown, x="Province", y="Value", title="Import Value by Province"), width="stretch")

        st.subheader("Filtered Data Preview")
        st.dataframe(df.head(100))

        # ✅ Download Button
        st.download_button(
            label="Download Filtered Data as CSV",
            data=df.to_csv(index=False),
            file_name="filtered_trade_data.csv",
            mime="text/csv"
        )
else:
