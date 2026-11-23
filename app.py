import os
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="Dashboard Penjualan ATASI",
    page_icon="📊",
    layout="wide"
)

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"

st.title("📊 Dashboard Penjualan ATASI")
st.caption("Monitoring target, realisasi penjualan, performa wilayah, dan kanal.")

# MEMUAT DATA HASIL NOTEBOOK
@st.cache_data
def load_data():
    required_files = {
        "transaksi": OUTPUT_DIR / "transaksi_bersih.csv",
        "target": OUTPUT_DIR / "target_bersih.csv",
    }

    missing = [str(path) for path in required_files.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "File hasil pembersihan belum ditemukan: "
            + ", ".join(missing)
            + ". Jalankan notebook sampai bagian 'Menyimpan hasil pembersihan' terlebih dahulu."
        )

    transaksi = pd.read_csv(required_files["transaksi"])
    target = pd.read_csv(required_files["target"])

    stok_path = OUTPUT_DIR / "stok_bersih.csv"
    stok = pd.read_csv(stok_path) if stok_path.exists() else pd.DataFrame()

    transaksi["Tanggal Pesanan"] = pd.to_datetime(
        transaksi["Tanggal Pesanan"], errors="coerce"
    )
    transaksi["Bulan"] = pd.to_datetime(
        transaksi["Bulan"], errors="coerce"
    )
    target["Bulan"] = pd.to_datetime(target["Bulan"], errors="coerce")

    if not stok.empty:
        stok["Bulan"] = pd.to_datetime(stok["Bulan"], errors="coerce")

    transaksi["Penjualan Bersih (Rp)"] = pd.to_numeric(
        transaksi["Penjualan Bersih (Rp)"], errors="coerce"
    ).fillna(0)
    target["Target Bersih (Rp)"] = pd.to_numeric(
        target["Target Bersih (Rp)"], errors="coerce"
    ).fillna(0)

    return transaksi, target, stok


def rupiah(value):
    return f"Rp{value:,.0f}".replace(",", ".")


try:
    df, target, stok = load_data()
except Exception as error:
    st.error(str(error))
    st.stop()

if df.empty or target.empty:
    st.warning("Data transaksi atau target belum tersedia.")
    st.stop()

# FILTER DASHBOARD
st.sidebar.header("Filter Dashboard")

months = sorted(
    pd.concat([df["Bulan"], target["Bulan"]]).dropna().unique()
)
if not months:
    st.warning("Tidak ditemukan periode bulan yang valid.")
    st.stop()

month_labels = {pd.Timestamp(m): pd.Timestamp(m).strftime("%B %Y") for m in months}
selected_month = st.sidebar.selectbox(
    "Bulan Analisis",
    options=[pd.Timestamp(m) for m in months],
    format_func=lambda x: month_labels[x],
    index=len(months) - 1
)

regions = sorted(
    set(df["Wilayah"].dropna().astype(str))
    | set(target["Wilayah"].dropna().astype(str))
)
channels = sorted(
    set(df["Kanal"].dropna().astype(str))
    | set(target["Kanal"].dropna().astype(str))
)

selected_regions = st.sidebar.multiselect(
    "Wilayah",
    options=regions,
    default=regions
)
selected_channels = st.sidebar.multiselect(
    "Kanal",
    options=channels,
    default=channels
)

# Filter transaksi dan target berdasarkan bulan/wilayah/kanal
transaksi_bulan = df[df["Bulan"] == selected_month].copy()
target_bulan = target[target["Bulan"] == selected_month].copy()

transaksi_filter = transaksi_bulan[
    transaksi_bulan["Wilayah"].astype(str).isin(selected_regions)
    & transaksi_bulan["Kanal"].astype(str).isin(selected_channels)
].copy()

target_filter = target_bulan[
    target_bulan["Wilayah"].astype(str).isin(selected_regions)
    & target_bulan["Kanal"].astype(str).isin(selected_channels)
].copy()

# KPI UTAMA
total_realisasi = transaksi_filter["Penjualan Bersih (Rp)"].sum()
total_target = target_filter["Target Bersih (Rp)"].sum()
gap = total_realisasi - total_target
capaian = (total_realisasi / total_target * 100) if total_target > 0 else 0
jumlah_transaksi = len(transaksi_filter)

st.subheader(f"Ringkasan {selected_month.strftime('%B %Y')}")
k1, k2, k3, k4 = st.columns(4)
k1.metric("Penjualan Bersih", rupiah(total_realisasi))
k2.metric("Target Penjualan", rupiah(total_target))
k3.metric("Selisih Target", rupiah(gap), delta=f"{gap / total_target * 100:.2f}%" if total_target else None)
k4.metric("Capaian Target", f"{capaian:.2f}%")
st.caption(f"Jumlah baris transaksi pada filter aktif: {jumlah_transaksi:,}")

# RINGKASAN BULANAN
st.divider()
st.subheader("Tren Target dan Realisasi Penjualan")

monthly_actual = (
    df.groupby("Bulan", as_index=False)["Penjualan Bersih (Rp)"]
    .sum()
    .rename(columns={"Penjualan Bersih (Rp)": "Realisasi"})
)
monthly_target = (
    target.groupby("Bulan", as_index=False)["Target Bersih (Rp)"]
    .sum()
    .rename(columns={"Target Bersih (Rp)": "Target"})
)
monthly = monthly_target.merge(monthly_actual, on="Bulan", how="outer").fillna(0)
monthly = monthly.sort_values("Bulan")
monthly_long = monthly.melt(
    id_vars="Bulan",
    value_vars=["Target", "Realisasi"],
    var_name="Jenis",
    value_name="Nilai Penjualan (Rp)"
)
monthly_long["Bulan"] = monthly_long["Bulan"].dt.strftime("%b %Y")

fig_monthly = px.bar(
    monthly_long,
    x="Bulan",
    y="Nilai Penjualan (Rp)",
    color="Jenis",
    barmode="group",
    labels={"Nilai Penjualan (Rp)": "Penjualan (Rp)", "Bulan": "Bulan"},
    text_auto=".2s"
)
fig_monthly.update_layout(legend_title_text="", xaxis_title="", yaxis_title="Rupiah")
st.plotly_chart(fig_monthly, use_container_width=True)

# ANALISIS WILAYAH DAN KANAL
st.divider()
st.subheader("Analisis Penjualan per Wilayah dan Kanal")

actual_detail = (
    transaksi_filter.groupby(["Wilayah", "Kanal"], as_index=False)
    ["Penjualan Bersih (Rp)"].sum()
)
target_detail = (
    target_filter.groupby(["Wilayah", "Kanal"], as_index=False)
    ["Target Bersih (Rp)"].sum()
)

detail = target_detail.merge(
    actual_detail, on=["Wilayah", "Kanal"], how="outer"
).fillna(0)

detail["Selisih (Rp)"] = (
    detail["Penjualan Bersih (Rp)"] - detail["Target Bersih (Rp)"]
)
detail["Capaian (%)"] = np.where(
    detail["Target Bersih (Rp)"] > 0,
    detail["Penjualan Bersih (Rp)"] / detail["Target Bersih (Rp)"] * 100,
    0
)
detail = detail.sort_values("Selisih (Rp)")

left, right = st.columns(2)
with left:
    fig_gap = px.bar(
        detail,
        x="Selisih (Rp)",
        y="Wilayah",
        color="Kanal",
        orientation="h",
        barmode="group",
        title="Selisih Target dan Realisasi",
        labels={"Selisih (Rp)": "Selisih (Rp)", "Wilayah": "Wilayah"}
    )
    st.plotly_chart(fig_gap, use_container_width=True)

with right:
    fig_achievement = px.bar(
        detail,
        x="Capaian (%)",
        y="Wilayah",
        color="Kanal",
        orientation="h",
        barmode="group",
        title="Persentase Capaian Target",
        labels={"Capaian (%)": "Capaian (%)", "Wilayah": "Wilayah"}
    )
    fig_achievement.add_vline(x=100, line_dash="dash", line_color="red")
    st.plotly_chart(fig_achievement, use_container_width=True)

display_detail = detail.copy()
for col in ["Target Bersih (Rp)", "Penjualan Bersih (Rp)", "Selisih (Rp)"]:
    display_detail[col] = display_detail[col].map(rupiah)
display_detail["Capaian (%)"] = display_detail["Capaian (%)"].map(lambda x: f"{x:.2f}%")
st.dataframe(display_detail, use_container_width=True, hide_index=True)

# STOK DAN TEMUAN UTAMA
st.divider()
st.subheader("Indikasi Ketersediaan Stok")

if not stok.empty and "Hari Stok Kosong" in stok.columns:
    stok_bulan = stok[stok["Bulan"] == selected_month].copy()
    if selected_regions:
        stok_bulan = stok_bulan[stok_bulan["Wilayah"].astype(str).isin(selected_regions)]
    stok_summary = (
        stok_bulan.groupby("Wilayah", as_index=False)["Hari Stok Kosong"].sum()
        .sort_values("Hari Stok Kosong", ascending=False)
    )
    if not stok_summary.empty:
        fig_stock = px.bar(
            stok_summary,
            x="Wilayah",
            y="Hari Stok Kosong",
            title="Total Hari Stok Kosong per Wilayah",
            labels={"Hari Stok Kosong": "Hari Stok Kosong"}
        )
        st.plotly_chart(fig_stock, use_container_width=True)
        st.dataframe(stok_summary, use_container_width=True, hide_index=True)
    else:
        st.info("Tidak ada data stok untuk filter bulan/wilayah yang dipilih.")
else:
    st.info("Data stok tidak tersedia atau kolom 'Hari Stok Kosong' tidak ditemukan.")

# Tiga kombinasi dengan gap terbesar pada bulan yang sedang dipilih
st.subheader("Prioritas Perhatian")
prioritas = detail.nsmallest(3, "Selisih (Rp)")
if prioritas.empty:
    st.info("Tidak ada data prioritas pada filter yang dipilih.")
else:
    for _, row in prioritas.iterrows():
        with st.container(border=True):
            st.markdown(f"**{row['Wilayah']} — {row['Kanal']}**")
            st.write(f"Gap: {rupiah(row['Selisih (Rp)'])}")
            st.write(f"Capaian target: {row['Capaian (%)']:.2f}%")
            if row["Selisih (Rp)"] < 0:
                st.warning("Realisasi masih berada di bawah target.")
            else:
                st.success("Realisasi telah mencapai atau melampaui target.")

# UNDUH DATA HASIL FILTER
st.divider()
st.subheader("Unduh Data")
csv_data = detail.to_csv(index=False).encode("utf-8-sig")
st.download_button(
    "Unduh Detail Capaian (CSV)",
    data=csv_data,
    file_name=f"detail_capaian_{selected_month:%Y_%m}.csv",
    mime="text/csv"
)

st.caption("Sumber: file hasil pembersihan dan analisis pada notebook TEST_KOMPETENSI_ATASI.")
