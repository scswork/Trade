st.set_option('client.showErrorDetails', True)

import streamlit as st
import pandas as pd
import requests
import io
import plotly.express as px
from difflib import get_close_matches

# -------------------- Page Setup --------------------
st.set_page_config(page_title="Trade Data Explorer", layout="wide")
st.title("🇨🇦 Trade Data Explorer")

# -------------------- Sidebar Filters --------------------
st.sidebar.header("Filters")
selected_years = st.sidebar.text_input("Year(s) (comma-separated):")
selected_country = st.sidebar.text_input("Country:")
selected_province = st.sidebar.text_input("Province:")
selected_state = st.sidebar.text_input("State:")
selected_hs10 = st.sidebar.text_input("HS10 Code:")
description_query = st.sidebar.text_input("Description (fuzzy match):")
load_data = st.sidebar.button("Load & Apply Filters")

# -------------------- GitHub Parquet URLs --------------------
parquet_urls = [
    "https://github.com/scswork/Trade/raw/refs/heads/main/trade_data_2023_H1.parquet",
    "https://github.com/scswork/Trade/raw/refs/heads/main/trade_data_2023_H2.parquet",
    "https://github.com/scswork/Trade/raw/refs/heads/main/trade_data_2024_H1.parquet",
    "https://github.com/scswork/Trade/raw/refs/heads/main/trade_data_2024_H2.parquet"
]

# -------------------- Load Parquet from GitHub --------------------
@st.cache_data
def load_parquet_from_github(urls):
    dfs = []
    for url in urls:
        response = requests.get(url)
        if response.status_code == 200:
            buffer = io.BytesIO(response.content)
            df = pd.read_parquet(buffer)
            dfs.append(df)
        else:
            st.warning(f"⚠️ Failed to load: {url}")
    return pd.concat(dfs, ignore_index=True)

# -------------------- Main Logic --------------------
if load_data:
    with st.spinner("🔄 Loading and filtering data..."):
        df = load_parquet_from_github(parquet_urls)

        # Apply filters
        if selected_years:
            try:
                years_list = [int(y.strip()) for y in selected_years.split(",") if y.strip().isdigit()]
                df = df[df["Year"].isin(years_list)]
            except Exception:
                st.warning("⚠️ Invalid year format. Use comma-separated numbers, e.g. 2023, 2024.")

        if selected_country:
            df = df[df["Country"] == selected_country]
        if selected_province:
            df = df[df["Province"] == selected_province]
        if selected_state:
            df = df[df["State"] == selected_state]
        if selected_hs10:
            df = df[df["HS10"].astype(str).str.contains(selected_hs10, case=False)]

        if description_query and "Description" in df.columns:
            matches = get_close_matches(description_query, df["Description"].dropna().unique(), n=10, cutoff=0.6)
            if matches:
                df = df[df["Description"].isin(matches)]

        if df.empty:
            st.warning("🚫 No data matches your filters.")
            st.stop()

        # -------------------- Summary --------------------
        st.subheader("📊 Summary Statistics")
        st.metric("Total Records", f"{len(df):,}")
        st.metric("Total Import Value", f"${df['Value'].sum():,.2f}")
        st.metric("Total Quantity", f"{df['Quantity'].sum():,.2f}")

        # -------------------- Visualizations --------------------
        st.subheader("📈 Visualizations")

        if "Year" in df.columns:
            yearly_trend = df.groupby("Year", as_index=False)["Value"].sum()
            st.plotly_chart(px.line(yearly_trend, x="Year", y="Value", title="Import Value by Year"), use_container_width=True)

        if "Country" in df.columns:
            top_countries = df.groupby("Country", as_index=False)["Value"].sum().nlargest(10, "Value")
            st.plotly_chart(px.bar(top_countries, x="Country", y="Value", title="Top 10 Countries"), use_container_width=True)

        if "Province" in df.columns:
            province_breakdown = df.groupby("Province", as_index=False)["Value"].sum().sort_values("Value", ascending=False)
            st.plotly_chart(px.bar(province_breakdown, x="Province", y="Value", title="Import Value by Province"), use_container_width=True)

        # -------------------- Data Preview --------------------
        st.subheader("🔍 Filtered Data Preview")
        st.dataframe(df.head(100))

        # -------------------- Download --------------------
        st.download_button(
            label="⬇️ Download Filtered Data as CSV",
            data=df.to_csv(index=False),
            file_name="filtered_trade_data.csv",
            mime="text/csv"
        )
else:
    st.info("👈 Click **Load & Apply Filters** to begin.")

