import streamlit as st
import pandas as pd
import requests
import io
import plotly.express as px
from difflib import get_close_matches

st.set_option('client.showErrorDetails', True)

# -------------------- Page Setup --------------------
st.set_page_config(page_title="Trade Data Explorer", layout="wide")
st.title("🇨🇦 Trade Data Explorer")

# -------------------- Sidebar Filters --------------------
st.sidebar.header("Filters")
selected_years = st.sidebar.text_input("Year(s) (comma-separated):", help="e.g. 2023, 2024")
selected_country = st.sidebar.text_input("Country:", help="Exact match required")
selected_province = st.sidebar.text_input("Province:", help="Exact match required")
selected_state = st.sidebar.text_input("State:", help="Exact match required")
selected_hs10 = st.sidebar.text_input("HS10 Code:", help="Partial match allowed")
description_query = st.sidebar.text_input("Description (fuzzy match):", help="Fuzzy match on product description")
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
            try:
                buffer = io.BytesIO(response.content)
                df = pd.read_parquet(buffer)
                dfs.append(df)
            except Exception as e:
                st.warning(f"⚠️ Error reading parquet file: {url} — {e}")
        else:
            st.warning(f"⚠️ Failed to load: {url}")
    return pd.concat(dfs, ignore_index=True)
