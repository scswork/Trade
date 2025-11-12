# trade_kpis_streamlit.py
import streamlit as st
import pandas as pd
import numpy as np
import io
import requests
from difflib import get_close_matches
from functools import partial

st.set_page_config(page_title="Trade KPIs Explorer (HHI & IPTB)", layout="wide")
st.title("🇨🇦 Trade KPIs Explorer — HHI / PCI / IPTB Matrix")

# -------------------- Utilities --------------------
@st.cache_data(show_spinner=False)
def load_parquet_from_url(url, timeout=60):
    try:
        resp = requests.get(url, allow_redirects=True, timeout=timeout)
        resp.raise_for_status()
        buffer = io.BytesIO(resp.content)
        df = pd.read_parquet(buffer, engine="pyarrow")
        return df
    except Exception as e:
        st.error(f"Failed to load parquet from URL: {e}")
        return pd.DataFrame()

@st.cache_data(show_spinner=False)
def load_csv_from_path_or_buffer(path_or_buffer):
    try:
        if isinstance(path_or_buffer, str) and (path_or_buffer.startswith("http://") or path_or_buffer.startswith("https://")):
            resp = requests.get(path_or_buffer, allow_redirects=True, timeout=60)
            resp.raise_for_status()
            return pd.read_csv(io.StringIO(resp.text), dtype=str)
        else:
            return pd.read_csv(path_or_buffer, dtype=str)
    except Exception as e:
        st.error(f"Failed to load CSV: {e}")
        return pd.DataFrame()

def to_excel_bytes(df: pd.DataFrame):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="TradeData")
    return output.getvalue()

# -------------------- Sidebar: dataset sources --------------------
st.sidebar.header("Dataset source / files")

st.sidebar.write("1) Load half-year parquet from URL (or use example URLs).")
parquet_urls = {
    "2023_H1": "https://raw.githubusercontent.com/scswork/Trade/main/trade_data_2023_H1.parquet",
    "2023_H2": "https://raw.githubusercontent.com/scswork/Trade/main/trade_data_2023_H2.parquet",
    "2024_H1": "https://raw.githubusercontent.com/scswork/Trade/main/trade_data_2024_H1.parquet",
    "2024_H2": "https://raw.githubusercontent.com/scswork/Trade/main/trade_data_2024_H2.parquet"
}
selected_parquet = st.sidebar.selectbox("Half-Year to load:", list(parquet_urls.keys()), index=3)
if st.sidebar.button("Load selected parquet"):
    df_loaded = load_parquet_from_url(parquet_urls[selected_parquet])
    st.session_state["df_loaded"] = df_loaded
    st.sidebar.success(f"Loaded {len(df_loaded):,} rows from {selected_parquet}")

st.sidebar.write("---")
st.sidebar.write("2) (Optional) Upload IPTB matrix CSV (tauhat_nodist.csv)")
ipbt_file = st.sidebar.file_uploader("Upload IPTB CSV", type=["csv"])
if ipbt_file is not None:
    st.session_state["df_IPTB"] = pd.read_csv(ipbt_file, dtype=str)
    st.sidebar.success("Loaded IPTB CSV")

st.sidebar.write("---")
st.sidebar.write("3) (Optional) Upload concordance (HS10 <-> SUPC <-> NAICS)")
concord_file = st.sidebar.file_uploader("Upload concordance CSV", type=["csv"])
if concord_file is not None:
    st.session_state["concord"] = pd.read_csv(concord_file, dtype=str)
    st.sidebar.success("Loaded concordance CSV")

# Allow user to load IPTB & concordance from example remote paths if not uploaded
use_example = st.sidebar.checkbox("Use example IPTB & concordance (if not uploaded)", value=True)
if "df_IPTB" not in st.session_state and use_example:
    # If the user didn't upload, attempt to load from repo/relative path (adjust as needed)
    try:
        st.session_state["df_IPTB"] = load_csv_from_path_or_buffer("https://raw.githubusercontent.com/scswork/Trade/main/tauhat_nodist.csv")
    except Exception:
        st.session_state["df_IPTB"] = pd.DataFrame()
if "concord" not in st.session_state and use_example:
    try:
        st.session_state["concord"] = load_csv_from_path_or_buffer("https://raw.githubusercontent.com/scswork/Trade/main/Concordance_ioic-naics-hs-supc.csv")
    except Exception:
        st.session_state["concord"] = pd.DataFrame()

# -------------------- Main UI: check dataset loaded --------------------
df_loaded = st.session_state.get("df_loaded", pd.DataFrame())
if df_loaded.empty:
    st.info("👈 Load a half-year parquet dataset from the sidebar (or upload one).")
    st.stop()

# Coerce expected columns to correct dtypes/columns; normalize column names
expected_cols = [
    "YearMonth","HS10","Country","Province","State","Value","Quantity","UoM",
    "Year","Month","MonthName","Description","SUPC","SUPC_Desc",
    "naics","naics_mod","naics_desc","ioic","HS4","pci_2023"
]
# if dataset is missing Year column but has YearMonth, derive Year, Month
if "Year" not in df_loaded.columns and "YearMonth" in df_loaded.columns:
    # YearMonth like 202301
    df_loaded["YearMonth"] = df_loaded["YearMonth"].astype(str)
    df_loaded["Year"] = df_loaded["YearMonth"].str.slice(0,4).astype(int)
    df_loaded["Month"] = df_loaded["YearMonth"].str.slice(4,6).astype(int)
    df_loaded["MonthName"] = pd.to_datetime(df_loaded["Month"], format="%m").dt.month_name().str.slice(0,3)

# ensure HS10 and SUPC are strings and padded to 10 as in the R app
df_loaded["HS10"] = df_loaded["HS10"].astype(str).str.zfill(10)
if "SUPC" in df_loaded.columns:
    df_loaded["SUPC"] = df_loaded["SUPC"].astype(str)

# Numeric conversions
for col in ["Value","Quantity","pci_2023"]:
    if col in df_loaded.columns:
        df_loaded[col] = pd.to_numeric(df_loaded[col], errors="coerce")

# -------------------- Precompute HHI table similar to R --------------------
@st.cache_data(show_spinner=True)
def compute_hhi_table(df: pd.DataFrame):
    # df: cleaned trade rows
    dfc = df.dropna(subset=["Value"]).copy()
    # total per product-year
    product_totals = dfc.groupby(["Year","HS10","SUPC"], dropna=False, as_index=False)["Value"].sum().rename(columns={"Value":"total_value"})
    # shares per country
    shares = (dfc.groupby(["Year","HS10","SUPC","Country"], dropna=False, as_index=False)["Value"]
              .sum()
              .rename(columns={"Value":"Value"}))
    merged = shares.merge(product_totals, on=["Year","HS10","SUPC"], how="left")
    merged["share_sq"] = (merged["Value"] / merged["total_value"]).fillna(0)**2
    hhi = (merged.groupby(["Year","HS10","SUPC"], as_index=False)["share_sq"]
           .sum()
           .rename(columns={"share_sq":"HHI"}))
    # add example description, SUPC_Desc if present
    extra_cols = []
    for col in ["Description","SUPC_Desc"]:
        if col in dfc.columns:
            extra_cols.append(col)
    if extra_cols:
        distincts = (dfc[["Year","HS10","SUPC"] + extra_cols]
                     .drop_duplicates(subset=["Year","HS10","SUPC"]))
        hhi = hhi.merge(distincts, on=["Year","HS10","SUPC"], how="left")
    # add rank per year
    hhi = hhi.sort_values(["Year","HHI"], ascending=[True, False])
    hhi["Rank"] = hhi.groupby("Year")["HHI"].rank(method="first", ascending=False).astype(int)
    return hhi, merged  # return merged for possible share calculations

hhi_table_all, merged_shares_df = compute_hhi_table(df_loaded)

# PCI lookup (if pci_2023 available)
pci_lookup = None
if "pci_2023" in df_loaded.columns:
    pci_lookup = (df_loaded.dropna(subset=["pci_2023"])
                  .loc[:, ["HS10","SUPC","Description","SUPC_Desc","pci_2023"]]
                  .drop_duplicates(subset=["HS10","SUPC"])
                  .rename(columns={"pci_2023":"pci"}))

# -------------------- Sidebar: Filters (main) --------------------
st.sidebar.header("Filters (for HHI & IPTB)")

years = sorted(hhi_table_all["Year"].dropna().unique())
selected_years = st.sidebar.multiselect("Select Year(s):", years, default=max(years))

# country/province/state as single-select or "All" (to mirror R app)
country_options = ["All"] + sorted(df_loaded["Country"].dropna().unique().tolist())
province_options = ["All"] + sorted(df_loaded["Province"].dropna().unique().tolist()) if "Province" in df_loaded.columns else ["All"]
state_options = ["All"] + sorted(df_loaded["State"].dropna().unique().tolist()) if "State" in df_loaded.columns else ["All"]

selected_country = st.sidebar.selectbox("Select Country:", country_options, index=0)
selected_province = st.sidebar.selectbox("Select Province (Canada):", province_options, index=0)
selected_state = st.sidebar.selectbox("Select State (US):", state_options, index=0)

industry_search = st.sidebar.text_input("Industry Prefix (NAICS/IOIC):", value="BS")
supc_matrix_input = st.sidebar.text_input("SUPC Code for IPTB Matrix (optional):", value="")
hs_input = st.sidebar.text_input("Enter HS10 Code (prefix allowed):", value="")
supc_input = st.sidebar.text_input("Enter SUPC Code for HHI/PCI (prefix allowed):", value="")

run_btn = st.sidebar.button("Get Product HHI/PCI Info")

# -------------------- IPTB Matrix generation --------------------
st.subheader("Industry Description")
df_IPTB = st.session_state.get("df_IPTB", pd.DataFrame())
if df_IPTB.empty:
    st.markdown("<span style='color:red;'>IPTB matrix (tauhat_nodist.csv) not loaded — IPTB matrix unavailable.</span>", unsafe_allow_html=True)
else:
    # find description
    industry_description = ""
    if industry_search:
        mask = df_IPTB["IndustryCode"].astype(str).str.lower().str.startswith(str(industry_search).lower())
        descs = df_IPTB.loc[mask, "Desc"].dropna().unique().tolist() if "Desc" in df_IPTB.columns else []
        industry_description = descs[0] if descs else None
    if industry_description:
        st.markdown(f"**{industry_description}**")
    else:
        st.markdown("<span style='color:gray;'>No description found for given industry prefix.</span>", unsafe_allow_html=True)

    # Filter matrix rows by industry_search OR by mapping from concordance when supc_matrix_input is provided
    matrix_data = df_IPTB.copy()
    if industry_search:
        matrix_data = matrix_data[matrix_data["IndustryCode"].astype(str).str.lower().str.startswith(industry_search.lower())]
    # If user supplied a SUPC for matrix input and concordance is available, try to restrict IPTB to those industry codes
    concord = st.session_state.get("concord", pd.DataFrame())
    if supc_matrix_input and not concord.empty:
        # find naics_mod or ioic for that SUPC, then filter IPTB
        supc_match = concord[concord["SUPC"].astype(str) == supc_matrix_input]
        if not supc_match.empty:
            naics_mod_vals = supc_match["naics_mod"].dropna().astype(str).str.lower().unique().tolist() if "naics_mod" in supc_match.columns else []
            ioic_vals = supc_match["ioic"].dropna().astype(str).str.lower().unique().tolist() if "ioic" in supc_match.columns else []
            matrix_data = matrix_data[matrix_data["IndustryCode"].astype(str).str.lower().isin(naics_mod_vals + ioic_vals)]

    if matrix_data.empty:
        st.markdown("<span style='color:orange;'>No IPTB matrix rows matched your filters.</span>", unsafe_allow_html=True)
    else:
        # Build pivot: Origin x Dest average TEC (TEC likely numeric in df_IPTB column TEC)
        matrix_display = matrix_data.copy()
        if "TEC" in matrix_display.columns:
            try:
                matrix_display["TEC"] = pd.to_numeric(matrix_display["TEC"].astype(str).str.replace("%","",regex=False), errors="coerce")
            except Exception:
                matrix_display["TEC"] = pd.to_numeric(matrix_display["TEC"], errors="coerce")
        # pivot
        pivot = (matrix_display.groupby(["Origin","Dest"], as_index=False)["TEC"]
                 .mean()
                 .pivot(index="Origin", columns="Dest", values="TEC")
                 .fillna(0))
        # style and show
        st.subheader("IPTB Matrix (average TEC)")
        try:
            st.dataframe(pivot.style.background_gradient(axis=None, cmap="Blues").format("{:.2f}"))
        except Exception:
            st.dataframe(pivot)

# -------------------- Filtered HHI table (like R's full_hhi_table) --------------------
def matched_by_industry(df, industry_prefix):
    if not industry_prefix or industry_prefix.strip() == "":
        return df
    mask_naics = df["naics"].astype(str).str.lower().str.startswith(industry_prefix.lower()) if "naics" in df.columns else False
    mask_ioic = df["ioic"].astype(str).str.lower().str.startswith(industry_prefix.lower()) if "ioic" in df.columns else False
    return df[mask_naics | mask_ioic]

# Create matched (HS10,SUPC) set from df_loaded filtered by country/province/state and industry
def get_matched_products(df, industry_search, country, province, state):
    dfc = df.copy()
    if country and country != "All":
        dfc = dfc[dfc["Country"] == country]
    if province and province != "All" and "Province" in dfc.columns:
        dfc = dfc[dfc["Province"] == province]
    if state and state != "All" and "State" in dfc.columns:
        dfc = dfc[dfc["State"] == state]
    dfc = matched_by_industry(dfc, industry_search)
    if dfc.empty:
        return pd.DataFrame(columns=["HS10","SUPC"])
    return dfc[["HS10","SUPC"]].drop_duplicates()

matched_products = get_matched_products(df_loaded, industry_search, selected_country, selected_province, selected_state)

# Filter HHI table by selected years and matched products (if any)
hhi_filtered = hhi_table_all[hhi_table_all["Year"].isin(selected_years)]
if not matched_products.empty:
    hhi_filtered = hhi_filtered.merge(matched_products, on=["HS10","SUPC"], how="inner")

st.subheader("All Products Ranked by HHI (Filtered by Industry + Year)")
st.dataframe(hhi_filtered.sort_values(["Year","HHI"], ascending=[True, False]).loc[:, ["Year","Rank","HS10","SUPC","Description","SUPC_Desc","HHI"]].reset_index(drop=True))

# -------------------- Product-specific HHI + PCI (on button press) --------------------
if run_btn:
    if (not hs_input) and (not supc_input):
        st.warning("Please enter at least an HS10 or SUPC code to fetch product HHI/PCI info.")
    else:
        # filter raw df_loaded for product and selected years and country/province/state
        dfp = df_loaded.copy()
        dfp = dfp[dfp["Year"].isin(selected_years)]
        if selected_country and selected_country != "All":
            dfp = dfp[dfp["Country"] == selected_country]
        if selected_province and selected_province != "All" and "Province" in dfp.columns:
            dfp = dfp[dfp["Province"] == selected_province]
        if selected_state and selected_state != "All" and "State" in dfp.columns:
            dfp = dfp[dfp["State"] == selected_state]
        if hs_input:
            dfp = dfp[dfp["HS10"].astype(str).str.contains(hs_input, case=False, na=False)]
        if supc_input:
            dfp = dfp[dfp["SUPC"].astype(str).str.contains(supc_input, case=False, na=False)]

        if dfp.empty:
            st.error("No data found for that product + filter combination.")
        else:
            # Product info: first match as example (like R app)
            prod = dfp.iloc[0]
            pci_value = prod.get("pci_2023", "Not available")
            st.subheader("Selected Product Summary")
            st.write({
                "HS10": prod.get("HS10"),
                "Description": prod.get("Description","N/A"),
                "SUPC": prod.get("SUPC"),
                "SUPC Desc": prod.get("SUPC_Desc","N/A"),
                "PCI (2023)": pci_value
            })

            # Compute shares by Year & Country for that product
            top_countries_by_year = (dfp.groupby(["Year","Country","UoM"], as_index=False)
                                      .agg(CountryValue=("Value","sum"), CountryQuantity=("Quantity","sum")))
            # compute share percent per year
            top_countries_by_year["SharePercent"] = top_countries_by_year.groupby("Year")["CountryValue"].apply(lambda x: (x / x.sum() * 100).round(2))
            # We'll show Top 10 countries overall (across years) and per year possibility
            # show combined top 10 by CountryValue
            show_top = top_countries_by_year.sort_values("CountryValue", ascending=False).groupby("Year").head(10).reset_index(drop=True)
            st.subheader("Top 10 Countries by Import Share (Product / filtered)")
            st.dataframe(show_top.loc[:, ["Year","Country","CountryValue","CountryQuantity","UoM","SharePercent"]])

            # Aggregate HHI on filtered product rows (overall)
            agg = top_countries_by_year.groupby("Year").apply(lambda d: ((d["CountryValue"]/d["CountryValue"].sum())**2).sum()).rename("HHI").reset_index()
            agg["HHI"] = agg["HHI"].round(4)
            st.write("Aggregate HHI by Year for selected product (filtered):")
            st.table(agg)

# -------------------- Data preview and downloads --------------------
st.subheader("🔍 Filtered Data Preview (for your filters)")
# Build a preview using the same filter logic as matched_products logic + year selection
df_preview = df_loaded.copy()
# Apply main filters
if selected_years:
    df_preview = df_preview[df_preview["Year"].isin(selected_years)]
if selected_country and selected_country != "All":
    df_preview = df_preview[df_preview["Country"] == selected_country]
if selected_province and selected_province != "All" and "Province" in df_preview.columns:
    df_preview = df_preview[df_preview["Province"] == selected_province]
if selected_state and selected_state != "All" and "State" in df_preview.columns:
    df_preview = df_preview[df_preview["State"] == selected_state]
if hs_input:
    df_preview = df_preview[df_preview["HS10"].astype(str).str.contains(hs_input, case=False, na=False)]
if supc_input:
    df_preview = df_preview[df_preview["SUPC"].astype(str).str.contains(supc_input, case=False, na=False)]
# industry filter (if provided)
df_preview = matched_by_industry(df_preview, industry_search)

st.dataframe(df_preview.head(200))

col1, col2 = st.columns(2)
col1.download_button("⬇️ Download CSV (filtered)", df_preview.to_csv(index=False).encode("utf-8"), "filtered_trade_data.csv", "text/csv")
col2.download_button("⬇️ Download Excel (filtered)", to_excel_bytes(df_preview), "filtered_trade_data.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

st.caption("Note: This app attempts to replicate the R Shiny app features: IPTB matrix, product HHI/PCI summary, Top 10 countries by share, and full HHI table. If you uploaded IPTB or concordance they were used; otherwise example remote files were attempted.")
