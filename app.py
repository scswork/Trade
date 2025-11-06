import streamlit as st
import pandas as pd
import requests
import io
import plotly.express as px
from difflib import get_close_matches
import traceback

st.set_page_config(page_title="Trade Data Explorer", layout="wide")
st.set_option('client.showErrorDetails', True)
st.title("🇨🇦 Trade Data Explorer")

# -------------------- Load Parquet --------------------
@st.cache_data(show_spinner=False)
def load_parquet_from_github(url):
    try:
        response = requests.get(url, allow_redirects=True, timeout=60)
        response.raise_for_status()
        buffer = io.BytesIO(response.content)
        # Only load needed columns to save memory
        df = pd.read_parquet(buffer, engine="pyarrow", columns=["Year","Country","Province","State","HS10","Description","Value","Quantity"])
        return df
    except Exception as e:
        st.error(f"Failed to load dataset: {e}")
        return pd.DataFrame()

# -------------------- Excel Export --------------------
def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='TradeData')
    return output.getvalue()

# -------------------- Main --------------------
def main():
    try:
        st.sidebar.header("Select Dataset (Half-Year)")

        parquet_urls = {
            "2023_H1": "https://raw.githubusercontent.com/scswork/Trade/main/trade_data_2023_H1.parquet",
            "2023_H2": "https://raw.githubusercontent.com/scswork/Trade/main/trade_data_2023_H2.parquet",
            "2024_H1": "https://raw.githubusercontent.com/scswork/Trade/main/trade_data_2024_H1.parquet",
            "2024_H2": "https://raw.githubusercontent.com/scswork/Trade/main/trade_data_2024_H2.parquet"
        }

        selected_file = st.sidebar.selectbox("Half-Year:", list(parquet_urls.keys()), index=3)

        load_data = st.sidebar.button("Load Data")

        if load_data:
            df = load_parquet_from_github(parquet_urls[selected_file])

            if df.empty:
                st.error("No data loaded.")
                st.stop()

            # -------------------- Dropdown Filters --------------------
            st.sidebar.header("Filters")

            # Year
            years = sorted(df["Year"].dropna().unique().tolist())
            selected_years = st.sidebar.multiselect("Year(s):", years, default=years)

            # Country
            countries = sorted(df["Country"].dropna().unique().tolist())
            selected_country = st.sidebar.multiselect("Country:", countries)

            # Province
            provinces = sorted(df["Province"].dropna().unique().tolist())
            selected_province = st.sidebar.multiselect("Province:", provinces)

            # State
            states = sorted(df["State"].dropna().unique().tolist())
            selected_state = st.sidebar.multiselect("State:", states)

            # HS10 and Description
            selected_hs10 = st.sidebar.text_input("HS10 Code:", help="Partial match allowed")
            description_query = st.sidebar.text_input("Description (fuzzy match):", help="Fuzzy match on product description")

            # -------------------- Apply Filters --------------------
            df_filtered = df.copy()
            if selected_years:
                df_filtered = df_filtered[df_filtered["Year"].isin(selected_years)]
            if selected_country:
                df_filtered = df_filtered[df_filtered["Country"].isin(selected_country)]
            if selected_province:
                df_filtered = df_filtered[df_filtered["Province"].isin(selected_province)]
            if selected_state:
                df_filtered = df_filtered[df_filtered["State"].isin(selected_state)]
            if selected_hs10:
                df_filtered = df_filtered[df_filtered["HS10"].astype(str).str.contains(selected_hs10, case=False)]
            if description_query:
                try:
                    sample = df_filtered["Description"].dropna().unique().tolist()
                    if len(sample) > 5000:
                        sample = sample[:5000]
                    matches = get_close_matches(description_query, sample, n=10, cutoff=0.6)
                    if matches:
                        st.write("🔍 Fuzzy matched descriptions:", matches)
                        df_filtered = df_filtered[df_filtered["Description"].isin(matches)]
                    else:
                        st.warning("No close matches found.")
                except Exception as e:
                    st.warning(f"Fuzzy match failed: {e}")

            if df_filtered.empty:
                st.warning("No data matches your filters.")
                st.stop()

            # -------------------- Summary --------------------
            st.subheader("📊 Summary Statistics")
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Records", f"{len(df_filtered):,}")
            col2.metric("Total Import Value", f"${df_filtered['Value'].sum():,.2f}")
            col3.metric("Total Quantity", f"{df_filtered['Quantity'].sum():,.2f}")

            # -------------------- Visualizations --------------------
            st.subheader("📈 Visualizations")
            df_viz = df_filtered.head(10000)  # memory-safe sample

            try:
                yearly_trend = df_viz.groupby("Year", as_index=False)["Value"].sum()
                st.plotly_chart(px.line(yearly_trend, x="Year", y="Value", title="Import Value by Year"), width="stretch")
            except Exception as e:
                st.warning(f"Chart error (yearly trend): {e}")

            try:
                top_countries = df_viz.groupby("Country", as_index=False)["Value"].sum().nlargest(10, "Value")
                st.plotly_chart(px.bar(top_countries, x="Country", y="Value", title="Top 10 Countries"), width="stretch")
            except Exception as e:
                st.warning(f"Chart error (top countries): {e}")

            try:
                province_breakdown = df_viz.groupby("Province", as_index=False)["Value"].sum().sort_values("Value", ascending=False)
                st.plotly_chart(px.bar(province_breakdown, x="Province", y="Value", title="Import Value by Province"), width="stretch")
            except Exception as e:
                st.warning(f"Chart error (province breakdown): {e}")

            # -------------------- Preview --------------------
            st.subheader("🔍 Filtered Data Preview")
            st.dataframe(df_filtered.head(100))

            # -------------------- Downloads --------------------
            st.download_button("⬇️ Download CSV", df_filtered.to_csv(index=False), "filtered_trade_data.csv", "text/csv")
            st.download_button("⬇️ Download Excel", to_excel(df_filtered), "filtered_trade_data.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        else:
            st.info("👈 Select a half-year and click **Load Data**.")

    except Exception as e:
        st.error("Unexpected error:")
        st.text(traceback.format_exc())

if __name__ == "__main__":
    main()
