import streamlit as st
import pandas as pd
import os
import subprocess
import plotly.express as px
import json
from difflib import get_close_matches

# -----------------------------------------------------------------------------
# ✅ Page setup
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Trade Data Explorer", layout="wide")
st.title("Trade Data Explorer")

# -----------------------------------------------------------------------------
# ✅ Sidebar filters
# -----------------------------------------------------------------------------
st.sidebar.header("Filters")
selected_years = st.sidebar.text_input("Year(s) (comma-separated):")
selected_country = st.sidebar.text_input("Country:")
selected_province = st.sidebar.text_input("Province:")
selected_state = st.sidebar.text_input("State:")
selected_hs10 = st.sidebar.text_input("HS10 Code:")
description_query = st.sidebar.text_input("Description (fuzzy match):")

load_data = st.sidebar.button("Load & Apply Filters")

# -----------------------------------------------------------------------------
# ✅ Dataset info
# -----------------------------------------------------------------------------
dataset_slug = "shevaserrattan/can-sut20232024"
local_filename = "df_imp_all.csv"
data_dir = "data"

# -----------------------------------------------------------------------------
# ✅ Detect Streamlit Cloud environment
# -----------------------------------------------------------------------------
def running_in_streamlit_cloud() -> bool:
    return "STREAMLIT_RUNTIME" in os.environ or "STREAMLIT_SERVER_ENABLED" in os.environ

# -----------------------------------------------------------------------------
# ✅ Write Kaggle credentials if available (local only)
# -----------------------------------------------------------------------------
def setup_kaggle_credentials():
    if "kaggle" in st.secrets:
        kaggle_dir = os.path.expanduser("~/.kaggle")
        os.makedirs(kaggle_dir, exist_ok=True)
        cred_path = os.path.join(kaggle_dir, "kaggle.json")
        with open(cred_path, "w") as f:
            json.dump({
                "username": st.secrets["kaggle"]["username"],
                "key": st.secrets["kaggle"]["key"]
            }, f)
        os.chmod(cred_path, 0o600)

# -----------------------------------------------------------------------------
# ✅ Cached data loader
# -----------------------------------------------------------------------------
@st.cache_data
def load_full_data(path: str) -> pd.DataFrame:
    try:
        df = pd.read_csv(path, encoding="utf-8")
    except FileNotFoundError:
        st.error("❌ Dataset file not found. Ensure 'df_imp_all.csv' is in the repository.")
        st.stop()

    rename_map = {
        "HS10": "HS10",
        "Description": "Description",
        "Country/Pays": "Country",
        "Province": "Province",
        "State/État": "State",
        "Unit of Measure/Unité de Mesure": "UoM",
        "YearMonth/AnnéeMois": "YearMonth",
        "Value/Valeur": "Value",
        "Quantity/Quantité": "Quantity",
    }
    df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns}, inplace=True)
    df["YearMonth"] = pd.to_numeric(df.get("YearMonth"), errors="coerce")
    df.dropna(subset=["YearMonth"], inplace=True)
    df["Year"] = (df["YearMonth"] // 100).astype(int)
    return df

# -----------------------------------------------------------------------------
# ✅ Main logic
# -----------------------------------------------------------------------------
if load_data:
    # If dataset missing, handle depending on environment
    if not os.path.exists(local_filename):
        if running_in_streamlit_cloud():
            st.error("Dataset missing in cloud. Please upload 'df_imp_all.csv' to the repository.")
            st.stop()
        else:
            setup_kaggle_credentials()
            st.info("Dataset not found locally. Downloading from Kaggle...")
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
        df = load_full_data(local_filename)

        # ------------------ Filters ------------------
        if selected_years:
            try:
                years_list = [int(y.strip()) for y in selected_years.split(",") if y.strip().isdigit()]
                df = df[df["Year"].isin(years_list)]
            except Exception:
                st.warning("Invalid year format. Use comma-separated numbers, e.g. 2023, 2024.")

        if selected_country and "Country" in df.columns:
            df = df[df["Country"] == selected_country]
        if selected_province and "Province" in df.columns:
            df = df[df["Province"] == selected_province]
        if selected_state and "State" in df.columns:
            df = df[df["State"] == selected_state]
        if selected_hs10 and "HS10" in df.columns:
            df = df[df["HS10"].astype(str).str.contains(selected_hs10, case=False)]

        if description_query and "Description" in df.columns:
            descriptions = df["Description"].dropna().unique()
            matches = get_close_matches(description_query, descriptions, n=10, cutoff=0.6)
            if matches:
                df = df[df["Description"].isin(matches)]

        if df.empty:
            st.warning("No data matches your filters.")
            st.stop()

        # ------------------ Summary ------------------
        st.subheader("Summary Statistics")
        st.write(f"**Total Records:** {len(df):,}")
        st.write(f"**Total Import Value:** {df['Value'].sum():,.2f}")
        st.write(f"**Total Quantity:** {df['Quantity'].sum():,.2f}")

        # ------------------ Visualizations ------------------
        yearly_trend = df.groupby("Year", as_index=False)["Value"].sum()
        st.plotly_chart(px.line(yearly_trend, x="Year", y="Value", title="Import Value by Year"), use_container_width=True)

        if "Country" in df.columns:
            top_countries = df.groupby("Country", as_index=False)["Value"].sum().sort_values("Value", ascending=False).head(10)
            st.plotly_chart(px.bar(top_countries, x="Country", y="Value", title="Top 10 Countries"), use_container_width=True)

        if "Province" in df.columns:
            province_breakdown = df.groupby("Province", as_index=False)["Value"].sum().sort_values("Value", ascending=False)
            st.plotly_chart(px.bar(province_breakdown, x="Province", y="Value", title="Import Value by Province"), use_container_width=True)

        # ------------------ Data Preview ------------------
        st.subheader("Filtered Data Preview")
        st.dataframe(df.head(100))

        # ------------------ Download Button ------------------
        st.download_button(
            label="Download Filtered Data as CSV",
            data=df.to_csv(index=False),
            file_name="filtered_trade_data.csv",
            mime="text/csv"
        )
else:
    st.info("Click **Load & Apply Filters** to start. No heavy processing until you click.")
