import streamlit as st
import pandas as pd
import os
import subprocess
import plotly.express as px
import sys
import traceback

# ✅ Error handler
def show_error(e):
    st.error(f"An error occurred: {e}")
    st.text("Traceback:")
    st.text("".join(traceback.format_exception(*sys.exc_info())))

# ✅ Page Config
st.set_page_config(layout="wide")
st.title("Trade Data Explorer")

try:
    # ✅ Sidebar first (UI loads immediately)
    st.sidebar.header("Filters")
    st.info("Initializing app...")

    # ✅ Kaggle Credentials Check
    try:
        os.environ['KAGGLE_USERNAME'] = st.secrets["KAGGLE_USERNAME"]
        os.environ['KAGGLE_KEY'] = st.secrets["KAGGLE_KEY"]
    except KeyError:
        st.error("Missing Kaggle credentials in Streamlit secrets.")
        st.stop()

    # ✅ Dataset Info
    dataset_slug = "shevaserrattan/can-sut20232024"
    local_filename = "df_imp_all.csv"
    data_dir = "data"

    # ✅ Show spinner for download (non-blocking UI)
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

    # ✅ Dynamic Filters
    @st.cache_data
    def load_unique_values():
        sample = pd.read_csv(local_filename, nrows=50000)
        years = sorted(sample["YearMonth"] // 100)
        countries = sorted(sample["Country"].dropna().unique())
        provinces = sorted(sample["Province"].dropna().unique())
        states = sorted(sample["State"].dropna().unique())
        return years, countries, provinces, states

    years, countries, provinces, states = load_unique_values()

    selected_years = st.sidebar.multiselect("Select Year(s):", years)
    selected_country = st.sidebar.selectbox("Country:", ["All"] + countries)
    selected_province = st.sidebar.selectbox("Province:", ["All"] + provinces)
    selected_state = st.sidebar.selectbox("State:", ["All"] + states)

    chunksize = 100000

    @st.cache_data
    def load_filtered_data(selected_years, selected_country, selected_province, selected_state):
        filtered_chunks = []
        for chunk in pd.read_csv(local_filename, chunksize=chunksize):
            chunk["Year"] = chunk["YearMonth"] // 100
            chunk["Month"] = chunk["YearMonth"] % 100

            if selected_years:
                chunk = chunk[chunk["Year"].isin(selected_years)]
            if selected_country != "All":
                chunk = chunk[chunk["Country"] == selected_country]
            if selected_province != "All":
                chunk = chunk[chunk["Province"] == selected_province]
            if selected_state != "All":
                chunk = chunk[chunk["State"] == selected_state]

            if not chunk.empty:
                filtered_chunks.append(chunk)

        return pd.concat(filtered_chunks) if filtered_chunks else pd.DataFrame()

    filtered_df = load_filtered_data(selected_years, selected_country, selected_province, selected_state)

    if filtered_df.empty:
        st.warning("No data matches your filters.")
        st.stop()

    # ✅ Summary Stats
    st.subheader("Summary Statistics")
    st.write(f"Total Records: {len(filtered_df):,}")
    st.write(f"Total Import Value: {filtered_df['Value'].sum():,.2f}")
    st.write(f"Total Quantity: {filtered_df['Quantity'].sum():,.2f}")

    # ✅ Visualizations
    st.subheader("Visualizations")

    # Yearly Trend
    yearly_trend = filtered_df.groupby("Year", as_index=False)["Value"].sum()
    fig_year = px.line(yearly_trend, x="Year", y="Value", title="Import Value by Year")
    st.plotly_chart(fig_year, use_container_width=True)

    # Top Countries
    top_countries = filtered_df.groupby("Country", as_index=False)["Value"].sum().sort_values("Value", ascending=False).head(10)
    fig_countries = px.bar(top_countries, x="Country", y="Value", title="Top 10 Countries by Import Value")
    st.plotly_chart(fig_countries, use_container_width=True)

    # Province Breakdown
    province_breakdown = filtered_df.groupby("Province", as_index=False)["Value"].sum().sort_values("Value", ascending=False)
    fig_province = px.bar(province_breakdown, x="Province", y="Value", title="Import Value by Province")
    st.plotly_chart(fig_province, use_container_width=True)

    # ✅ Data Preview
    st.subheader("Filtered Data Preview")
    st.dataframe(filtered_df.head(100))

    # ✅ Download Button
    st.download_button(
        label="Download Filtered Data as CSV",
        data=filtered_df.to_csv(index=False),
        file_name="filtered_trade_data.csv",
        mime="text/csv"
    )

except Exception as e:
    show_error(e)
