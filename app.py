import streamlit as st
import pandas as pd

# ---- Load your data ----
df_imp_all = pd.read_csv("df_imp_all.csv")  # combined 2023+2024
pci_lookup = pd.read_csv("pci_lookup.csv")  # optional PCI data

# Convert HS10 and SUPC to string to ensure correct filtering
df_imp_all['HS10'] = df_imp_all['HS10'].astype(str).str.zfill(10)
df_imp_all['SUPC'] = df_imp_all['SUPC'].astype(str)

# ---- Sidebar filters ----
st.sidebar.title("Filters")
years = sorted(df_imp_all['Year'].unique())
year_select = st.sidebar.multiselect("Select Year(s):", years, default=years[-1])
country_filter = st.sidebar.selectbox("Country:", ["All"] + sorted(df_imp_all['Country'].dropna().unique()))
province_filter = st.sidebar.selectbox("Province (Canada):", ["All"] + sorted(df_imp_all['Province'].dropna().unique()))
state_filter = st.sidebar.selectbox("State (US):", ["All"] + sorted(df_imp_all['State'].dropna().unique()))
hs_input = st.sidebar.text_input("HS10 Code")
supc_input = st.sidebar.text_input("SUPC Code")

# ---- Filter data ----
filtered = df_imp_all[df_imp_all['Year'].isin(year_select)]
if hs_input:
    filtered = filtered[filtered['HS10'].str.startswith(hs_input)]
if supc_input:
    filtered = filtered[filtered['SUPC'].str.startswith(supc_input)]
if country_filter != "All":
    filtered = filtered[filtered['Country'] == country_filter]
if province_filter != "All":
    filtered = filtered[filtered['Province'] == province_filter]
if state_filter != "All":
    filtered = filtered[filtered['State'] == state_filter]

if filtered.empty:
    st.warning("No data found for selected filters.")
else:
    # ---- Aggregate HHI ----
    country_sum = filtered.groupby('Country', as_index=False)['Value'].sum()
    country_sum['Share'] = country_sum['Value'] / country_sum['Value'].sum()
    HHI = (country_sum['Share'] ** 2).sum()
    
    st.subheader("Aggregate HHI")
    st.write(f"HHI: {HHI:.4f}")
    
    # ---- Top 10 countries ----
    top_countries = country_sum.sort_values('Share', ascending=False).head(10)
    top_countries['SharePercent'] = top_countries['Share'] * 100
    st.subheader("Top 10 Countries by Import Share")
    st.dataframe(top_countries[['Country','Value','SharePercent']])
    
    # ---- Example Product Info ----
    product_info = pci_lookup[
        (pci_lookup['HS10'].str.startswith(hs_input) if hs_input else True) &
        (pci_lookup['SUPC'].str.startswith(supc_input) if supc_input else True)
    ]
    if not product_info.empty:
        info = product_info.iloc[0]
        st.subheader("Product Info")
        st.write(f"HS10: {info['HS10']}")
        st.write(f"SUPC: {info['SUPC']}")
        st.write(f"Description: {info['Description']}")
        if 'pci' in info:
            st.write(f"PCI: {info['pci']}")
