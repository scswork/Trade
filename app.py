import streamlit as st
import pandas as pd
import gdown
import os

st.set_page_config(layout="wide")
st.title("Trade Data Explorer")

# Google Drive file ID
file_id = "1ZWuhhnlmCLB66v5h3aQ9wE8o5WGNXLq6"
download_url = f"https://drive.google.com/uc?id={file_id}"
local_filename = "df_imp_all.csv"

# Download if not exists
if not os.path.exists(local_filename):
    st.info("Downloading large file from Google Drive...")
    gdown.download(download_url, local_filename, quiet=False)

# Sidebar filters
st.sidebar.header("Filters")
selected_years = st.sidebar.multiselect("Select Year(s):", [])
selected_country = st.sidebar.text_input("Country filter (optional):")
selected_province = st.sidebar.text_input("Province filter (optional):")
selected_state = st.sidebar.text_input("State filter (optional):")

# Chunked loading
chunksize = 100000
filtered_chunks = []

st.info("Loading data in chunks...")
try:
    for chunk in pd.read_csv(local_filename, chunksize=chunksize):
        # Dynamic rename
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
        chunk = chunk.rename(columns={k: v for k, v in rename_map.items() if k in chunk.columns})

        if "YearMonth" in chunk.columns:
            chunk["Year"] = chunk["YearMonth"] // 100
            chunk["Month"] = chunk["YearMonth"] % 100
            chunk["MonthName"] = pd.to_datetime(chunk["Month"], format="%m").dt.strftime("%b")
        else:
            continue

        # Apply filters
        if selected_years:
            chunk = chunk[chunk["Year"].isin(selected_years)]
        if selected_country:
            chunk = chunk[chunk["Country"] == selected_country]
        if selected_province:
            chunk = chunk[chunk["Province"] == selected_province]
        if selected_state:
            chunk = chunk[chunk["State"] == selected_state]

        if not chunk.empty:
            filtered_chunks.append(chunk)

    if filtered_chunks:
        filtered_df = pd.concat(filtered_chunks)
        st.success(f"Loaded {len(filtered_df)} rows after filtering.")

        # Summary stats
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
    else:
        st.warning("No data matches your filters.")

except Exception as e:
    st.error(f"Failed to load data: {e}")
    st.stop()
