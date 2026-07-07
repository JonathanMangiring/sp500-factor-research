"""
Step 4: Visualisasi Hasil Factor Research
============================================
Input : data/ic_results.parquet, data/portfolio_returns.parquet
Output: charts/*.png

Bikin 3 chart utama per factor:
1. IC time series      -> lihat konsistensi sinyal dari waktu ke waktu
2. Cumulative return   -> lihat performa kumulatif long-short portfolio
3. Rolling 12-bulan IC -> lihat apakah sinyal menguat/melemah seiring waktu
   (berguna buat deteksi "factor decay" atau perubahan regime market)
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import os

IC_PATH = "data/ic_results.parquet"
PORTFOLIO_PATH = "data/portfolio_returns.parquet"
CHART_DIR = "charts"

ROLLING_WINDOW = 12  # bulan, untuk rolling IC


def load_data():
    ic_df = pd.read_parquet(IC_PATH)
    port_df = pd.read_parquet(PORTFOLIO_PATH)
    # year_month (Period) -> Timestamp biar gampang diplot
    ic_df["date"] = ic_df["year_month"].dt.to_timestamp()
    port_df["date"] = port_df["year_month"].dt.to_timestamp()
    return ic_df, port_df


def plot_ic_timeseries(ic_df: pd.DataFrame, factor: str, ax):
    sub = ic_df[ic_df["factor"] == factor].sort_values("date")
    colors = np.where(sub["ic"] >= 0, "#2E7D32", "#C62828")  # hijau positif, merah negatif
    ax.bar(sub["date"], sub["ic"], width=20, color=colors, alpha=0.7)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.axhline(0.05, color="gray", linestyle="--", linewidth=0.8, label="IC = 0.05 (threshold umum)")
    ax.axhline(-0.05, color="gray", linestyle="--", linewidth=0.8)
    ax.set_title(f"Information Coefficient (IC) per Bulan — Factor: {factor}")
    ax.set_ylabel("Spearman IC")
    ax.legend(loc="upper right", fontsize=8)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))


def plot_rolling_ic(ic_df: pd.DataFrame, factor: str, ax):
    sub = ic_df[ic_df["factor"] == factor].sort_values("date").copy()
    sub["rolling_ic"] = sub["ic"].rolling(ROLLING_WINDOW, min_periods=max(3, ROLLING_WINDOW // 2)).mean()
    ax.plot(sub["date"], sub["rolling_ic"], color="#1565C0", linewidth=1.8)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.fill_between(sub["date"], 0, sub["rolling_ic"], alpha=0.15, color="#1565C0")
    ax.set_title(f"Rolling {ROLLING_WINDOW}-Bulan IC — Factor: {factor}")
    ax.set_ylabel("Rolling Mean IC")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))


def plot_cumulative_return(port_df: pd.DataFrame, factor: str, ax):
    sub = port_df[port_df["factor"] == factor].sort_values("date").copy()
    sub = sub.dropna(subset=["long_short_return"])
    sub["cumulative"] = (1 + sub["long_short_return"]).cumprod() - 1

    ax.plot(sub["date"], sub["cumulative"] * 100, color="#4527A0", linewidth=2)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.fill_between(sub["date"], 0, sub["cumulative"] * 100,
                     where=(sub["cumulative"] >= 0), color="#4527A0", alpha=0.1)
    ax.fill_between(sub["date"], 0, sub["cumulative"] * 100,
                     where=(sub["cumulative"] < 0), color="#C62828", alpha=0.1)
    ax.set_title(f"Cumulative Return — Long-Short Portfolio: {factor}")
    ax.set_ylabel("Cumulative Return (%)")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))


def plot_quintile_spread(port_df: pd.DataFrame, factor: str, ax):
    """Bandingkan rata-rata return Q_top vs Q_bottom sepanjang periode -> lihat spread-nya jelas atau enggak."""
    sub = port_df[port_df["factor"] == factor]
    avg_top = sub["q_top_return"].mean()
    avg_bottom = sub["q_bottom_return"].mean()

    bars = ax.bar(
        ["Q_bottom\n(skor terendah)", "Q_top\n(skor tertinggi)"],
        [avg_bottom * 100, avg_top * 100],
        color=["#C62828", "#2E7D32"],
        alpha=0.8,
        width=0.5,
    )
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_title(f"Rata-rata Return Bulanan: Q_top vs Q_bottom — {factor}")
    ax.set_ylabel("Avg Monthly Return (%)")
    for bar in bars:
        height = bar.get_height()
        ax.annotate(f"{height:.2f}%", xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3 if height >= 0 else -12), textcoords="offset points",
                    ha="center", fontsize=9)


def main():
    os.makedirs(CHART_DIR, exist_ok=True)
    ic_df, port_df = load_data()

    factors = ic_df["factor"].unique()

    for factor in factors:
        print(f"Membuat chart untuk factor: {factor}")

        fig, axes = plt.subplots(2, 2, figsize=(14, 9))
        fig.suptitle(f"Factor Research Summary: {factor.upper()}", fontsize=14, fontweight="bold")

        plot_ic_timeseries(ic_df, factor, axes[0, 0])
        plot_rolling_ic(ic_df, factor, axes[0, 1])
        plot_cumulative_return(port_df, factor, axes[1, 0])
        plot_quintile_spread(port_df, factor, axes[1, 1])

        plt.tight_layout(rect=[0, 0, 1, 0.96])
        output_path = f"{CHART_DIR}/{factor}_summary.png"
        plt.savefig(output_path, dpi=150)
        plt.close(fig)
        print(f"  -> tersimpan di {output_path}")

    # Chart perbandingan cumulative return semua factor dalam 1 gambar
    print("\nMembuat chart perbandingan antar-factor...")
    fig, ax = plt.subplots(figsize=(12, 6))
    for factor in factors:
        sub = port_df[port_df["factor"] == factor].sort_values("date").dropna(subset=["long_short_return"])
        cumulative = (1 + sub["long_short_return"]).cumprod() - 1
        ax.plot(sub["date"], cumulative * 100, linewidth=2, label=factor)

    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_title("Perbandingan Cumulative Return: Semua Factor", fontsize=13, fontweight="bold")
    ax.set_ylabel("Cumulative Return (%)")
    ax.legend()
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    plt.tight_layout()
    plt.savefig(f"{CHART_DIR}/comparison_all_factors.png", dpi=150)
    plt.close(fig)
    print(f"  -> tersimpan di {CHART_DIR}/comparison_all_factors.png")

    print(f"\nSemua chart tersimpan di folder: {CHART_DIR}/")


if __name__ == "__main__":
    main()
