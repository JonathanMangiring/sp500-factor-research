"""
Step 3: Portfolio Construction & Information Coefficient (IC)
================================================================
Input : data/prices_raw.parquet, data/factor_scores.parquet
Output: data/ic_results.parquet, data/portfolio_returns.parquet

Ini bagian INTI dari factor research. Dua hal yang dihitung:

1. INFORMATION COEFFICIENT (IC)
   Korelasi (Spearman) antara skor factor bulan ini dengan FORWARD RETURN
   (return bulan depan). Kalau factor punya predictive power, skor tinggi
   bulan ini harusnya berkorelasi dengan return tinggi bulan depan.
   Rule of thumb industri: |IC| > 0.05 dianggap ada signal yang berarti.

2. QUINTILE LONG-SHORT PORTFOLIO
   Tiap bulan, bagi saham jadi 5 kelompok (quintile) berdasarkan skor factor.
   Long quintile teratas (Q5), short quintile terbawah (Q1).
   Return portfolio = rata-rata return Q5 - rata-rata return Q1.
   Ini pendekatan standar akademik (mirip Fama-French).

PENTING: forward return dihitung dari bulan t ke bulan t+1, TIDAK BOLEH
pakai return yang sudah terjadi (look-ahead bias) -- skor factor bulan t
hanya boleh dipakai untuk prediksi return bulan t+1, bukan return bulan t.
"""

import pandas as pd
import numpy as np
from scipy import stats

PRICES_PATH = "data/prices_raw.parquet"
FACTORS_PATH = "data/factor_scores.parquet"
IC_OUTPUT_PATH = "data/ic_results.parquet"
PORTFOLIO_OUTPUT_PATH = "data/portfolio_returns.parquet"

N_QUINTILES = 5
FACTORS_TO_TEST = ["momentum", "low_vol"]


def load_data():
    prices = pd.read_parquet(PRICES_PATH)
    prices["date"] = pd.to_datetime(prices["date"])
    factors = pd.read_parquet(FACTORS_PATH)
    return prices, factors


def compute_forward_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """
    Hitung return dari bulan t ke bulan t+1 (forward return), per ticker.
    Forward return di-attach ke baris bulan t (bulan "sekarang"),
    supaya nanti tinggal di-join dengan skor factor bulan t.
    """
    prices = prices.copy()
    prices["year_month"] = prices["date"].dt.to_period("M")
    month_end = (
        prices.sort_values("date")
        .groupby(["ticker", "year_month"])
        .last()
        .reset_index()[["ticker", "year_month", "close"]]
    )

    month_end = month_end.sort_values(["ticker", "year_month"])
    month_end["next_month_close"] = month_end.groupby("ticker")["close"].shift(-1)
    month_end["forward_return"] = (month_end["next_month_close"] / month_end["close"]) - 1

    return month_end[["ticker", "year_month", "forward_return"]]


def compute_ic(merged: pd.DataFrame, factor_col: str) -> pd.DataFrame:
    """
    Hitung Spearman IC per bulan: korelasi antara skor factor
    dengan forward return, cross-sectional (antar saham di bulan yang sama).
    """
    ic_list = []
    for ym, group in merged.groupby("year_month"):
        group = group.dropna(subset=[factor_col, "forward_return"])
        if len(group) < 5:  # butuh minimal beberapa saham biar korelasi ada arti
            continue
        ic, pval = stats.spearmanr(group[factor_col], group["forward_return"])
        ic_list.append({
            "year_month": ym,
            "factor": factor_col,
            "ic": ic,
            "p_value": pval,
            "n_stocks": len(group),
        })
    return pd.DataFrame(ic_list)


def compute_quintile_portfolio(merged: pd.DataFrame, factor_col: str) -> pd.DataFrame:
    """
    Bagi saham jadi quintile berdasarkan skor factor tiap bulan,
    lalu hitung return Q5 (top), Q1 (bottom), dan long-short spread.
    """
    results = []
    for ym, group in merged.groupby("year_month"):
        group = group.dropna(subset=[factor_col, "forward_return"]).copy()
        if len(group) < N_QUINTILES * 2:  # minimal 2 saham per quintile
            continue

        group["quintile"] = pd.qcut(group[factor_col], N_QUINTILES, labels=False, duplicates="drop") + 1
        quintile_returns = group.groupby("quintile")["forward_return"].mean()

        q_top = quintile_returns.get(N_QUINTILES, np.nan)
        q_bottom = quintile_returns.get(1, np.nan)
        long_short = q_top - q_bottom

        results.append({
            "year_month": ym,
            "factor": factor_col,
            "q_top_return": q_top,
            "q_bottom_return": q_bottom,
            "long_short_return": long_short,
            "n_stocks": len(group),
        })
    return pd.DataFrame(results)


def summarize_ic(ic_df: pd.DataFrame) -> None:
    for factor in ic_df["factor"].unique():
        sub = ic_df[ic_df["factor"] == factor]
        mean_ic = sub["ic"].mean()
        std_ic = sub["ic"].std()
        ir = mean_ic / std_ic if std_ic > 0 else np.nan  # Information Ratio dari IC
        pct_positive = (sub["ic"] > 0).mean()

        print(f"\n--- Factor: {factor} ---")
        print(f"  Mean IC       : {mean_ic:.4f}")
        print(f"  Std IC        : {std_ic:.4f}")
        print(f"  IC-IR         : {ir:.4f}  (>0.5 dianggap bagus di industri)")
        print(f"  % bulan IC>0  : {pct_positive:.1%}")
        print(f"  Jumlah bulan  : {len(sub)}")


def summarize_portfolio(port_df: pd.DataFrame) -> None:
    for factor in port_df["factor"].unique():
        sub = port_df[port_df["factor"] == factor]
        ls_returns = sub["long_short_return"].dropna()

        mean_monthly = ls_returns.mean()
        std_monthly = ls_returns.std()
        sharpe_annualized = (mean_monthly / std_monthly) * np.sqrt(12) if std_monthly > 0 else np.nan
        t_stat = mean_monthly / (std_monthly / np.sqrt(len(ls_returns))) if std_monthly > 0 else np.nan

        cumulative = (1 + ls_returns).cumprod().iloc[-1] - 1 if len(ls_returns) > 0 else np.nan

        print(f"\n--- Long-Short Portfolio: {factor} ---")
        print(f"  Mean return/bulan : {mean_monthly:.4%}")
        print(f"  Sharpe (annualized): {sharpe_annualized:.3f}")
        print(f"  t-stat            : {t_stat:.3f}  (|t|>2 dianggap signifikan)")
        print(f"  Cumulative return : {cumulative:.2%}")
        print(f"  Jumlah bulan      : {len(ls_returns)}")


def main():
    print("=== Load data ===")
    prices, factors = load_data()

    print("\n=== Hitung forward return (bulan t -> t+1) ===")
    fwd_returns = compute_forward_returns(prices)

    print("\n=== Gabungkan factor scores dengan forward return ===")
    merged = factors.merge(fwd_returns, on=["ticker", "year_month"], how="left")
    print(f"Total baris setelah merge: {len(merged)}")

    all_ic = []
    all_portfolio = []

    for factor_col in FACTORS_TO_TEST:
        print(f"\n{'='*60}")
        print(f"ANALISIS FACTOR: {factor_col}")
        print(f"{'='*60}")

        ic_df = compute_ic(merged, factor_col)
        all_ic.append(ic_df)

        port_df = compute_quintile_portfolio(merged, factor_col)
        all_portfolio.append(port_df)

    ic_combined = pd.concat(all_ic, ignore_index=True)
    portfolio_combined = pd.concat(all_portfolio, ignore_index=True)

    print(f"\n\n{'='*60}")
    print("RINGKASAN INFORMATION COEFFICIENT (IC)")
    print(f"{'='*60}")
    summarize_ic(ic_combined)

    print(f"\n\n{'='*60}")
    print("RINGKASAN LONG-SHORT PORTFOLIO RETURN")
    print(f"{'='*60}")
    summarize_portfolio(portfolio_combined)

    ic_combined.to_parquet(IC_OUTPUT_PATH, index=False)
    portfolio_combined.to_parquet(PORTFOLIO_OUTPUT_PATH, index=False)
    print(f"\n\nHasil tersimpan di:\n  {IC_OUTPUT_PATH}\n  {PORTFOLIO_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
