import streamlit as st
import pandas as pd
import requests
import io
import plotly.express as px
from difflib import get_close_matches
import traceback

# -------------------- Safe Startup --------------------
st.write("✅ App imported successfully — starting Streamlit runtime...")

# -------------------- Main Function --------------------
def main():
    st.set_page_config(page_title="Trade Data Explorer", layout="wide")
    st.title("🇨🇦 Trade Data Explorer")

    st.sidebar.header("Filters")
    selected_years = st.sidebar.text_input("Year(s) (comma-separated):", help="e.g. 2023, 2024")
    selected_country = st.sidebar.text_input("Country:", help="Exact match required")
    selected_province = st.sidebar.text_input("Province:", help="Exact match required")
    selected_state = st.sidebar.text_input("State:", help="Exact match required")
    selected_hs10 = st.sidebar.text_input("HS10 Code:", help="Partial match allowed")
    description_query = st.sidebar.text_input("Description (fuzzy match):", help="Fuzzy match on product description")
    load_data = st.sidebar.button("Load & Apply Filters")

    # -------------------- Dataset Choices --------------------
    parquet_urls = {
        "2023_H1": "https://raw.githubusercontent.com/scswork/Trade/main/trade_data_2023_H1.parquet",
        "2023_H2": "https://raw.githubusercontent.com/scswork/Trade/main/trade_data_2023_H2.parquet",
        "2024_H1": "https://raw.githubusercontent.com/scswork/Trade/main/trade_data_2024_H1.parquet",
        "2024_H2": "https://raw.githubusercontent.com/scswork/Trade/main/trade_data_2024_H2.parquet"
    }

    selected_files = st.sidebar.multiselect(
        "Select dataset(s):", parquet_urls.keys(), default=["2024_H2"]
    )

    # -------------------- Cached Data Loader --------------------
    @st.cache_data(show_spinner=False)
    def load_parquet_from_github(selected_urls):
        dfs = []
        for name, url in selected_urls.items():
            st.write(f"🔗 Loading {name} from GitHub...")
            try:
                response = requests.get(url, allow_redirects=True, timeout=60)
                response.raise_for_status()
                buffer = io.BytesIO(response.content)
                df = pd.read_parquet(buffer, engine="pyarrow")
                df["SourceFile"] = name
                dfs.append(df)
                st.success(f"✅ Loaded {name}: {len(df):,} rows")
            except Exception as e:
                st.warning(f"⚠️ Failed to load {name}: {e}")
        if dfs:
            return pd.concat(dfs, ignore_index=True)
        else:
            return pd.DataFrame()

    # -------------------- Excel Export Helper --------------------
    def to_excel(df):
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='TradeData')
        return output.getvalue()

    # -------------------- Main Logic --------------------
    if load_data:
        with st.spinner("🔄 Loading and filtering data..."):
            df = load_parquet_from_github({k: parquet_urls[k] for k in selected_files})

            if df.empty:
                st.error("🚫 No data loaded — check your file selection.")
                st.stop()

            expected_columns = ["Year", "Country", "Province", "State", "HS10", "Description", "Value", "Quantity"]
            missing = [col for col in expected_columns if col not in df.columns]
            if missing:
                st.error(f"🚫 Missing expected columns: {', '.join(missing)}")
                st.stop()

            # -------------------- Filters --------------------
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
            if description_query:
                try:
                    descriptions = df["Description"].dropna().unique().tolist()
                    sample = descriptions if len(descriptions) < 5000 else descriptions[:5000]
                    matches = get_close_matches(description_query, sample, n=10, cutoff=0.6)
                    if matches:
                        st.write("🔍 Fuzzy matched descriptions:", matches)
                        df = df[df["Description"].isin(matches)]
                    else:
                        st.warning("❌ No close matches found for that description.")
                except Exception as e:
                    st.warning(f"⚠️ Fuzzy match failed: {e}")

            if df.empty:
                st.warning("🚫 No data matches your filters.")
                st.stop()

            # -------------------- Summary --------------------
            st.subheader("📊 Summary Statistics")
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Records", f"{len(df):,}")
            col2.metric("Total Import Value", f"${df['Value'].sum():,.2f}")
            col3.metric("Total Quantity", f"{df['Quantity'].sum():,.2f}")

            # -------------------- Visualizations --------------------
            st.subheader("📈 Visualizations")
            try:
                yearly_trend = df.groupby("Year", as_index=False)["Value"].sum()
                st.plotly_chart(px.line(yearly_trend, x="Year", y="Value", title="Import Value by Year"), use_container_width=True)
            except Exception as e:
                st.warning(f"Chart error (yearly trend): {e}")

            try:
                top_countries = df.groupby("Country", as_index=False)["Value"].sum().nlargest(10, "Value")
                st.plotly_chart(px.bar(top_countries, x="Country", y="Value", title="Top 10 Countries"), use_container_width=True)
            except Exception as e:
                st.warning(f"Chart error (top countries): {e}")

            try:
                province_breakdown = df.groupby("Province", as_index=False)["Value"].sum().sort_values("Value", ascending=False)
                st.plotly_chart(px.bar(province_breakdown, x="Province", y="Value", title="Import Value by Province"), use_container_width=True)
            except Exception as e:
                st.warning(f"Chart error (province breakdown): {e}")

            # -------------------- Data Preview --------------------
            st.subheader("🔍 Filtered Data Preview")
            st.dataframe(df.head(100))

            # -------------------- Download Buttons --------------------
            st.download_button(
                label="⬇️ Download Filtered Data as CSV",
                data=df.to_csv(index=False),
                file_name="filtered_trade_data.csv",
                mime="text/csv"
            )

            st.download_button(
                label="⬇️ Download Filtered Data as Excel",
                data=to_excel(df),
                file_name="filtered_trade_data.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    else:
        st.info("👈 Select filters and click **Load & Apply Filters** to begin.")

# -------------------- Run Safely --------------------
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        st.error("❌ Startup error — see below:")
        st.text(traceback.format_exc())
