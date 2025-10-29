
# trade_data_explorer.py

import streamlit as st
import pandas as pd

st.set_page_config(layout="wide")
st.title("Trade Data Explorer")

# Direct download link
file_id = "1ZWuhhnlmCLB66v5h3aQ9wE8o5WGNXLq6"
download_url = f"https://drive.google.com/uc?id={file_id}"

# Load the CSV directly
df_imp_all = pd.read_csv(download_url)


try:
    st.write("Attempting to load data...")
    df_imp_all = pd.read_csv(download_url)
    st.success("Data loaded successfully!")
    st.write("Columns in CSV:", df_imp_all.columns.tolist())
except Exception as e:
    st.error(f"Failed to load data: {e}")
    st.stop()


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



