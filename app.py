import streamlit as st
import pandas as pd
import numpy as np
import requests
import io
from difflib import get_close_matches
import matplotlib.colors as mcolors

st.set_page_config(page_title="Trade KPIs Explorer", layout="wide")
st.title("🇨🇦 Trade KPIs Explorer")

# -------------------- Functions --------------------
@st.cache_data(show_spinner=False)
def load_csv(url):
    """Load small CSVs (cached)"""
    try:
        df = pd.read_csv(url)
        return df
    except Exception as e:
        st.error(f"Failed to load CSV: {e}")
        return pd.DataFrame()

def load_parquet(url):
    """Load large parquet dataset (no caching)"""
    try:
        response = requests.get(url, allow_redirects=True, timeout=60)
        response.raise_for_status()
        buffer = io.BytesIO(response.content)
        df = pd.read_parquet(buffer, engine="pyarrow")
        return df
    except Exception as e:
        st.error(f"Failed to load dataset: {e}")
        return pd.DataFrame()

def to_excel(df):
    """Export dataframe to Excel"""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='TradeData')
    return output.getvalue()

def color_scale(val, vmin, vmax):
    """Return HTML background color for IPTB matrix cell"""
    if pd.isna(val):
        return ''
    cmap = mcolors.LinearSegmentedColormap.from_list("", ["#f7fbff", "#08306b"])
    norm_val = (val - vmin) / (vmax - vmin) if vmax > vmin else 0
    hex_color = mcolors.to_hex(cmap(norm_val))
    fg = "white" if norm_val > 0.5 else "black"
    return f'background-color:{hex_color};color:{fg}'

# -------------------- Load GitHub CSVs --------------------
df_IPTB_url = "https://raw.githubusercontent.com/scswork/Trade/main/tauhat_nodist.csv"
concordance_url = "https://raw.githubusercontent.com/scswork/Trade/main/Concordance%20ioic-naics-hs-supc.csv"

df_IPTB = load_csv(df_IPTB_url)
concordance = load_csv(concordance_url)

# -------------------- Sidebar: Select Half-Year --------------------
st.sidebar.header("Select Half-Year Dataset")
parquet_urls = {
    "2023_H1": "https://raw.githubusercontent.com/scswork/Trade/main/trade_data_2023_H1.parquet",
    "2023_H2": "https://raw.githubusercontent.com/scswork/Trade/main/trade_data_2023_H2.parquet",
    "2024_H1": "https://raw.githubusercontent.com/scswork/Trade/main/trade_data_2024_H1.parquet",
    "2024_H2": "https://raw.githubusercontent.com/scswork/Trade/main/trade_data_2024_H2.parquet",
    "2025_H1": "https://raw.githubusercontent.com/scswork/Trade/main/trade_data_2024_H1.parquet",
    "2025_H2": "https://raw.githubusercontent.com/scswork/Trade/main/trade_data_2024_H2.parquet"
}
selected_file = st.sidebar.selectbox("Half-Year:", list(parquet_urls.keys()), index=3)

if st.sidebar.button("Load Dataset"):
    # Clear previous dataset to free memory
    if "df_loaded" in st.session_state:
        del st.session_state["df_loaded"]
    st.session_state["df_loaded"] = load_parquet(parquet_urls[selected_file])
    st.success(f"✅ Loaded {len(st.session_state['df_loaded']):,} rows from {selected_file}")

# -------------------- Main App --------------------
df_loaded = st.session_state.get("df_loaded", pd.DataFrame())
if df_loaded.empty:
    st.info("👈 Load a dataset first using the button above.")
else:
    st.sidebar.header("Filters")

    # Sidebar filters
    years = sorted(df_loaded["Year"].dropna().unique())
    selected_years = st.sidebar.multiselect("Year(s):", years, default=years)

    countries = sorted(df_loaded["Country"].dropna().unique())
    selected_country = st.sidebar.multiselect("Country:", countries)

    provinces = sorted(df_loaded["Province"].dropna().unique())
    selected_province = st.sidebar.multiselect("Province:", provinces)

    states = sorted(df_loaded["State"].dropna().unique())
    selected_state = st.sidebar.multiselect("State:", states)

    hs_input = st.sidebar.text_input("HS10 Code:")
    supc_input = st.sidebar.text_input("SUPC Code:")
    desc_input = st.sidebar.text_input("Product Description:")
    industry_input = st.sidebar.text_input("Industry Prefix (NAICS/IOIC):", "BS")

    if st.sidebar.button("Apply Filters"):
        # -------------------- Filter dataset --------------------
        df_filtered = df_loaded.copy()
        if selected_years:
            df_filtered = df_filtered[df_filtered['Year'].isin(selected_years)]
        if selected_country:
            df_filtered = df_filtered[df_filtered['Country'].isin(selected_country)]
        if selected_province:
            df_filtered = df_filtered[df_filtered['Province'].isin(selected_province)]
        if selected_state:
            df_filtered = df_filtered[df_filtered['State'].isin(selected_state)]
        if hs_input:
            df_filtered = df_filtered[df_filtered['HS10'].astype(str).str.contains(hs_input, case=False)]
        if supc_input:
            df_filtered = df_filtered[df_filtered['SUPC'].astype(str).str.contains(supc_input, case=False)]
        if desc_input:
            try:
                sample = df_filtered['Description'].dropna().unique().tolist()
                if len(sample) > 5000:
                    sample = sample[:5000]
                matches = get_close_matches(desc_input, sample, n=10, cutoff=0.6)
                if matches:
                    st.write("🔍 Fuzzy matched descriptions:", matches)
                    df_filtered = df_filtered[df_filtered['Description'].isin(matches)]
                else:
                    st.warning("No close matches found for description.")
            except Exception as e:
                st.warning(f"Fuzzy match failed: {e}")

        if df_filtered.empty:
            st.warning("No data matches your filters.")
        else:
            # -------------------- Summary Metrics --------------------
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Records", f"{len(df_filtered):,}")
            col2.metric("Total Import Value", f"${df_filtered['Value'].sum():,.2f}")
            col3.metric("Total Quantity", f"{df_filtered['Quantity'].sum():,.2f}")

            # -------------------- IPTB Matrix --------------------
            st.subheader("📊 IPTB Matrix")

            matrix_data = df_IPTB.copy()

            # Only filter by SUPC if provided
            if supc_input:
                # Find NAICS/IOIC linked to this SUPC in loaded dataset
                supc_match = df_loaded[df_loaded['SUPC'].astype(str).str.contains(supc_input, case=False)]
                matched_codes = pd.concat([supc_match['naics_mod'], supc_match['ioic']]).dropna().unique()
                # Filter matrix by matching IndustryCode
                matrix_data = matrix_data[matrix_data['IndustryCode'].isin(matched_codes)]
    
            # Default: show full IPTB dataset if no SUPC filter
            if not matrix_data.empty:
                all_origins = sorted(matrix_data['Origin'].dropna().unique())
                all_dests = sorted(matrix_data['Dest'].dropna().unique())
                matrix_complete = pd.DataFrame(0, index=all_origins, columns=all_dests)

                for _, row in matrix_data.iterrows():
                    if pd.notna(row['Origin']) and pd.notna(row['Dest']) and pd.notna(row['TEC']):
                        matrix_complete.at[row['Origin'], row['Dest']] = row['TEC']

                # Display numeric matrix
                st.dataframe(matrix_complete.fillna(0), use_container_width=True)
            else:
                st.info("No IPTB data matches the selected SUPC code.")

            # -------------------- Aggregate HHI --------------------
            agg_hhi_df = df_filtered.groupby('Country', as_index=False)['Value'].sum()
            agg_hhi_df['Share'] = agg_hhi_df['Value'] / agg_hhi_df['Value'].sum()
            aggregate_hhi = (agg_hhi_df['Share'] ** 2).sum()

            # -------------------- Single Product Summary --------------------
            st.subheader("🔹 Selected Product Summary (with Aggregate HHI)")
            product_info = df_filtered.copy()
            if hs_input:
                product_info = product_info[product_info['HS10'].astype(str).str.contains(hs_input, case=False)]
            if supc_input:
                product_info = product_info[product_info['SUPC'].astype(str).str.contains(supc_input, case=False)]

            if not product_info.empty:
                prod = product_info.iloc[0]
                pci_value = prod.get('pci_2023', 'Not available')
                summary_text = f"""
HS10: {prod['HS10']}
Description: {prod.get('Description','N/A')}
SUPC: {prod['SUPC']}
SUPC Desc: {prod.get('SUPC_Desc','N/A')}
PCI (2023): {pci_value}
Aggregate HHI (filtered data): {aggregate_hhi:.4f}
"""
                st.text(summary_text)

                # -------------------- Top 10 Countries --------------------
                top_countries = (
                    df_filtered[(df_filtered['HS10']==prod['HS10']) & (df_filtered['SUPC']==prod['SUPC'])]
                    .groupby(['Year','Country','UoM'], as_index=False)
                    .agg(
                        CountryValue=('Value','sum'),
                        CountryQuantity=('Quantity','sum')
                    )
                )
                top_countries['SharePercent'] = round(top_countries['CountryValue'] / top_countries['CountryValue'].sum() * 100, 2)
                top_countries = top_countries.sort_values('CountryValue', ascending=False).head(10)
                st.subheader("🌎 Top 10 Countries by Import Share")
                st.dataframe(top_countries[['Year','Country','CountryValue','CountryQuantity','UoM','SharePercent']])

            # -------------------- Filtered Data Preview --------------------
            st.subheader("🔍 Filtered Data Preview")
            st.dataframe(df_filtered.head(100))

            # -------------------- Downloads --------------------
            st.download_button("⬇️ Download CSV", df_filtered.to_csv(index=False), "filtered_trade_data.csv", "text/csv")
            st.download_button("⬇️ Download Excel", to_excel(df_filtered), "filtered_trade_data.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")



