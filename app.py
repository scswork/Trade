import streamlit as st
import pandas as pd
import requests
import io
import plotly.express as px
from difflib import get_close_matches
import traceback

st.write("✅ App imported successfully — starting Streamlit runtime...")

# -------------------- Cached Parquet Loader --------------------
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

# -------------------- Excel Export --------------------
def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='TradeData')
    return output.getvalue()

# -------------------- Main Function --------------------
def main():
    st.set_page_config(page_title="Trade Data Explorer", layout="wide")
    st.title("🇨🇦 Trade Data Explorer")

    # -------------------- Dataset Selection --------------------
    st.sidebar.header("Select Dataset(s)")
    parquet_urls = {
        "2023_H1": "https://raw.githubusercontent.com/scswork/Trade/main/trade_data_2023_H1.parquet",
        "2023_H2": "https://raw.githubusercontent.com/scswork/Trade/main/trade_data_2023_H2.parquet",
        "2024_H1": "https://raw.githubusercontent.com/scswork/Trade/main/trade_data_2024_H1.parquet",
        "2024_H2": "https://raw.githubusercontent.com/scswork/Trade/main/trade_data_2024_H2.parquet"
    }
    selected_files = st.sidebar.multiselect(
        "Select dataset(s):", parquet_urls.keys(), default=["2024_H2"]
    )

    load_data = st.sidebar.button("Load Data")

    # -------------------- Load & Filter Data --------------------
    if load_data:
        df = load_parquet_from_github({k: parquet_urls[k] for k in selected_files})

        if df.empty:
            st.error("🚫 No data loaded — check your file selection.")
            st.stop()

        st.success(f"✅ Loaded {len(df):,} rows from selected datasets.")

        # -------------------- Flexible Column Mapping --------------------
        # Detect description column
        description_col = None
        for col in df.columns:
            if "desc" in col.lower():
                description_col = col
                break
        if description_col:
            df = df.rename(columns={description_col: "Description"})
        else:
            st.warning("⚠️ No column containing 'desc' found — Description filters disabled.")

        # -------------------- Dropdown Filters --------------------
        st.sidebar.header("Filters")

        # Year dropdown
        if "Year" in df.columns:
            years = sorted(df["Year"].dropna().unique().tolist())
            selected_years = st.sidebar.multiselect("Year(s):", years, default=years)
        else:
            selected_years = []

        # Country dropdown
        if "Country" in df.columns:
            countries = sorted(df["Country"].dropna().unique().tolist())
            selected_country = st.sidebar.multiselect("Country:", countries)
        else:
            selected_country = []

        # Province dropdown
        if "Province" in df.columns:
            provinces = sorted(df["Province"].dropna().unique().tolist())
            selected_province = st.sidebar.multiselect("Province:", provinces)
        else:
            selected_province = []

        # State dropdown
        if "State" in df.columns:
            states = sorted(df["State"].dropna().unique().tolist())
            selected_state = st.sidebar.multiselect("State:", states)
        else:
            selected_state = []

        # HS10 and Description remain text/fuzzy
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
        if description_query and "Description" in df_filtered.columns:
            try:
                descriptions = df_filtered["Description"].dropna().unique().tolist()
                sample = descriptions if len(descriptions) < 5000 else descriptions[:5000]
                matches = get_close_matches(description_query, sample, n=10, cutoff=0.6)
                if matches:
                    st.write("🔍 Fuzzy matched descriptions:", matches)
                    df_filtered = df_filtered[df_filtered["Description"].isin(matches)]
                else:
                    st.warning("❌ No close matches found for that description.")
            except Exception as e:
                st.warning(f"⚠️ Fuzzy match failed: {e}")

        if df_filtered.empty:
            st.warning("🚫 No data matches your filters.")
            st.stop()

        # -------------------- Summary --------------------
        st.subheader("📊 Summary Statistics")
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Records", f"{len(df_filtered):,}")
        col2.metric("Total Import Value", f"${df_filtered['Value'].sum():,.2f}")
        col3.metric("Total Quantity", f"{df_filtered['Quantity'].sum():,.2f}")

        # -------------------- Visualizations --------------------
        st.subheader("📈 Visualizations")
        try:
            yearly_trend = df_filtered.groupby("Year", as_index=False)["Value"].sum()
            st.plotly_chart(px.line(yearly_trend, x="Year", y="Value", title="Import Value by Year"), use_container_width=True)
        except Exception as e:
            st.warning(f"Chart error (yearly trend): {e}")

        try:
            top_countries = df_filtered.groupby("Country", as_index=False)["Value"].sum().nlargest(10, "Value")
            st.plotly_chart(px.bar(top_countries, x="Country", y="Value", title="Top 10 Countries"), use_container_width=True)
        except Exception as e:
            st.warning(f"Chart error (top countries): {e}")

        try:
            province_breakdown = df_filtered.groupby("Province", as_index=False)["Value"].sum().sort_values("Value", ascending=False)
            st.plotly_chart(px.bar(province_breakdown, x="Province", y="Value", title="Import Value by Province"), use_container_width=True)
        except Exception as e:
            st.warning(f"Chart error (province breakdown): {e}")

        # -------------------- Data Preview --------------------
        st.subheader("🔍 Filtered Data Preview")
        st.dataframe(df_filtered.head(100))

        # -------------------- Download Buttons --------------------
        st.download_button(
            label="⬇️ Download Filtered Data as CSV",
            data=df_filtered.to_csv(index=False),
            file_name="filtered_trade_data.csv",
            mime="text/csv"
        )

        st.download_button(
            label="⬇️ Download Filtered Data as Excel",
            data=to_excel(df_filtered),
            file_name="filtered_trade_data.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    else:
        st.info("👈 Select datasets and click **Load Data** to begin.")

# -------------------- Run Safely --------------------
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        st.error("❌ Startup error — see below:")
        st.text(traceback.format_exc())
