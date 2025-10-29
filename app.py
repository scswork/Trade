
# trade_data_explorer.py

import streamlit as st
import pandas as pd
import gdown
import os

st.set_page_config(layout="wide")
st.title("Trade Data Explorer")

# Google Drive file ID (replace with your actual file ID)
file_id = "YOUR_FILE_ID_HERE"
download_url = f"https://drive.google.com/uc?id={file_id}"
local_filename = "df_imp_all.csv"

# Download the file if it doesn't exist locally
if not os.path.exists(local_filename):
    st.info("Downloading data from Google Drive...")
    gdown.download(download_url, local_filename, quiet=False)

# Load the CSV
df_imp_all = pd.read_csv(local_filename)

# Rename columns for consistency
df_imp_all = df_imp_all.rename(columns={
    "HS10": "HS10",
    "Country/Pays": "Country",
    "Province": "Province",
    "State/État": "State",
    "Unit of Measure/Unité de Mesure": "UoM",
    "YearMonth/AnnéeMois": "YearMonth",
    "Value/Valeur": "Value",
    "Quantity/Quantité": "Quantity"
})

# Extract Year and Month
df_imp_all["Year"] = df_imp_all["YearMonth"] // 100
df_imp_all["Month"] = df_imp_all["YearMonth"] % 100
df_imp_all["MonthName"] = pd.to_datetime(df_imp_all["Month"], format="%m").dt.strftime("%b")

# Sidebar filters
st.sidebar.header("Filters")
selected_years = st.sidebar.multiselect("Select Year(s):", sorted(df_imp_all["Year"].unique()), default=sorted(df_imp_all["Year"].unique())[-1:])
selected_country = st.sidebar.selectbox("Select Country:", ["All"] + sorted(df_imp_all["Country"].dropna().unique()))
selected_province = st.sidebar.selectbox("Select Province (Canada):", ["All"] + sorted(df_imp_all["Province"].dropna().unique()))
selected_state = st.sidebar.selectbox("Select State (US):", ["All"] + sorted(df_imp_all["State"].dropna().unique()))

# Apply filters
filtered_df = df_imp_all[df_imp_all["Year"].isin(selected_years)]
if selected_country != "All":
    filtered_df = filtered_df[filtered_df["Country"] == selected_country]
if selected_province != "All":
    filtered_df = filtered_df[filtered_df["Province"] == selected_province]
if selected_state != "All":
    filtered_df = filtered_df[filtered_df["State"] == selected_state]

# Display summary statistics
st.subheader("Summary Statistics")
st.write(f"Total Records: {len(filtered_df)}")
st.write(f"Total Import Value: {filtered_df['Value'].sum():,.2f}")
st.write(f"Total Quantity: {filtered_df['Quantity'].sum():,.2f}")

# Top countries by import value
st.subheader("Top 10 Countries by Import Value")
top_countries = filtered_df.groupby("Country", as_index=False)["Value"].sum()
top_countries = top_countries.sort_values("Value", ascending=False).head(10)
st.dataframe(top_countries)

# Show filtered data
st.subheader("Filtered Data Preview")
st.dataframe(filtered_df.head(100))
