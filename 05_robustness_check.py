"""
Step 5: Robustness Check — Sub-Period Analysis & Turnover Cost
==================================================================
Input : data/factor_scores.parquet, data/ic_results.parquet, data/portfolio_returns.parquet
Output: data/robustness_summary.parquet, dicetak ke terminal

Dua pertanyaan kritis yang dijawab di sini:

1. SUB-PERIOD STABILITY
   Apakah factor ini konsisten kerja di semua era, atau cuma "kebetulan bagus"
   di satu periode tertentu (misal cuma bagus pas bull market doang)?
   Ini penting karena banyak backtest yang keliatan bagus ternyata cuma
   overfit ke satu regime market spesifik.

2. TURNOVER & TRANSACTION COST
   Quintile portfolio yang di-rebalance tiap bulan itu nggak gratis —
   tiap kali ganti saham ada biaya transaksi (bid-ask spread, komisi, slippage).
   Kalau turnover-nya tinggi, return yang keliatan bagus di atas kertas
   bisa habis kena cost. Momentum biasanya punya turnover lebih tinggi
   daripada low-vol, jadi ini sering jadi pembeda penting.
"""

import pandas as pd
import numpy as np

FACTORS_PATH = "data/factor_scores.parquet"
IC_PATH = "data/ic_results.parquet"
PORTFOLIO_PATH = "data/portfolio_returns.parquet"
OUTPUT_PATH = "data/robustness_summary.parquet"

N_QUINTILES = 5

# Sesuaikan sub-periode ini dengan rentang data kamu (2015 - 2026).
# Silakan edit label/tanggal kalau mau breakdown yang beda.
SUB_PERIODS = [
    ("2015-01-01", "2019-12-31", "2015-2019 (Pre-COVID Bull)"),
    ("2020-01-01", "2022-12-31", "2020-2022 (COVID + Rate Hike)"),
    ("2023-01-01", "2026-12-31", "2023-2026 (Recovery/AI Rally)"),
]

# Asumsi biaya transaksi per one-way trade (dalam basis points).
# 10 bps = 0.10% adalah asumsi konservatif-realistis untuk saham likuid S&P 500.
COST_PER_TRADE_BPS = 10


def load_data():
    factors = pd.read_parquet(FACTORS_PATH)
    ic_df = pd.read_parquet(IC_PATH)
    port_df = pd.read_parquet(PORTFOLIO_PATH)
    ic_df["date"] = ic_df["year_month"].dt.to_timestamp()
    port_df["date"] = port_df["year_month"].dt.to_timestamp()
    return factors, ic_df, port_df


# ----------------------------------------------------------------
# BAGIAN 1: SUB-PERIOD STABILITY
# ----------------------------------------------------------------

def compute_period_stats(ic_sub: pd.DataFrame, port_sub: pd.DataFrame) -> dict:
    mean_ic = ic_sub["ic"].mean()
    std_ic = ic_sub["ic"].std()
    ic_ir = mean_ic / std_ic if std_ic > 0 else np.nan

    ls_returns = port_sub["long_short_return"].dropna()
    mean_monthly = ls_returns.mean()
    std_monthly = ls_returns.std()
    sharpe = (mean_monthly / std_monthly) * np.sqrt(12) if std_monthly > 0 else np.nan
    t_stat = mean_monthly / (std_monthly / np.sqrt(len(ls_returns))) if len(ls_returns) > 1 and std_monthly > 0 else np.nan

    return {
        "mean_ic": mean_ic,
        "ic_ir": ic_ir,
        "mean_monthly_return": mean_monthly,
        "sharpe_annualized": sharpe,
        "t_stat": t_stat,
        "n_months": len(ls_returns),
    }


def sub_period_analysis(ic_df: pd.DataFrame, port_df: pd.DataFrame) -> pd.DataFrame:
    results = []
    for factor in ic_df["factor"].unique():
        print(f"\n{'='*65}")
        print(f"SUB-PERIOD STABILITY — Factor: {factor}")
        print(f"{'='*65}")

        for start, end, label in SUB_PERIODS:
            ic_sub = ic_df[(ic_df["factor"] == factor) & (ic_df["date"] >= start) & (ic_df["date"] <= end)]
            port_sub = port_df[(port_df["factor"] == factor) & (port_df["date"] >= start) & (port_df["date"] <= end)]

            if len(ic_sub) == 0:
                continue

            stats = compute_period_stats(ic_sub, port_sub)
            stats.update({"factor": factor, "period": label})
            results.append(stats)

            print(f"\n  {label}  ({stats['n_months']} bulan)")
            print(f"    Mean IC        : {stats['mean_ic']:.4f}")
            print(f"    IC-IR          : {stats['ic_ir']:.4f}")
            print(f"    Sharpe (annual): {stats['sharpe_annualized']:.3f}")
            print(f"    t-stat         : {stats['t_stat']:.3f}")

        # Kesimpulan sederhana: konsisten atau enggak?
        factor_results = [r for r in results if r["factor"] == factor]
        ic_signs = [np.sign(r["mean_ic"]) for r in factor_results if not np.isnan(r["mean_ic"])]
        consistent = len(set(ic_signs)) == 1 if len(ic_signs) > 0 else False
        verdict = "KONSISTEN (arah IC sama di semua periode)" if consistent else "TIDAK KONSISTEN (arah IC berubah antar periode)"
        print(f"\n  >> Verdict: {verdict}")

    return pd.DataFrame(results)


# ----------------------------------------------------------------
# BAGIAN 2: TURNOVER & TRANSACTION COST
# ----------------------------------------------------------------

def compute_quintile_membership(factors: pd.DataFrame, factor_col: str) -> pd.DataFrame:
    """Assign tiap saham ke quintile per bulan (sama seperti step 3), untuk lacak siapa masuk/keluar Long & Short book."""
    result = []
    for ym, group in factors.groupby("year_month"):
        group = group.dropna(subset=[factor_col]).copy()
        if len(group) < N_QUINTILES * 2:
            continue
        group["quintile"] = pd.qcut(group[factor_col], N_QUINTILES, labels=False, duplicates="drop") + 1
        group["position"] = np.select(
            [group["quintile"] == N_QUINTILES, group["quintile"] == 1],
            ["long", "short"],
            default="neutral",
        )
        result.append(group[["ticker", "year_month", "position"]])
    return pd.concat(result, ignore_index=True)


def compute_turnover(membership: pd.DataFrame) -> pd.DataFrame:
    """
    Turnover = fraksi anggota Long/Short book yang berubah dari bulan sebelumnya.
    one_way_turnover_leg = (jumlah nama yang keluar + masuk) / (2 x rata-rata ukuran book)
    """
    months = sorted(membership["year_month"].unique())
    results = []

    prev_long, prev_short = set(), set()

    for ym in months:
        cur = membership[membership["year_month"] == ym]
        cur_long = set(cur[cur["position"] == "long"]["ticker"])
        cur_short = set(cur[cur["position"] == "short"]["ticker"])

        if prev_long or prev_short:  # skip bulan pertama (belum ada pembanding)
            long_changed = len(cur_long.symmetric_difference(prev_long))
            short_changed = len(cur_short.symmetric_difference(prev_short))
            avg_long_size = (len(cur_long) + len(prev_long)) / 2
            avg_short_size = (len(cur_short) + len(prev_short)) / 2

            long_turnover = long_changed / (2 * avg_long_size) if avg_long_size > 0 else np.nan
            short_turnover = short_changed / (2 * avg_short_size) if avg_short_size > 0 else np.nan
            total_turnover = (long_turnover + short_turnover) / 2

            results.append({
                "year_month": ym,
                "long_turnover": long_turnover,
                "short_turnover": short_turnover,
                "total_turnover": total_turnover,
            })

        prev_long, prev_short = cur_long, cur_short

    return pd.DataFrame(results)


def turnover_cost_analysis(factors: pd.DataFrame, port_df: pd.DataFrame) -> None:
    for factor_col in factors.columns:
        if factor_col not in ["momentum", "low_vol"]:
            continue

        print(f"\n{'='*65}")
        print(f"TURNOVER & TRANSACTION COST — Factor: {factor_col}")
        print(f"{'='*65}")

        membership = compute_quintile_membership(factors, factor_col)
        turnover_df = compute_turnover(membership)

        avg_turnover = turnover_df["total_turnover"].mean()
        print(f"\n  Rata-rata turnover per bulan : {avg_turnover:.1%}")
        print(f"  (Artinya rata-rata {avg_turnover:.1%} dari isi portfolio diganti tiap bulan)")

        # Estimasi cost: tiap rebalance kena cost masuk + keluar (round trip), 2 kaki (long & short)
        monthly_cost = avg_turnover * (COST_PER_TRADE_BPS / 10000) * 2
        print(f"  Asumsi cost per trade        : {COST_PER_TRADE_BPS} bps")
        print(f"  Estimasi cost per bulan       : {monthly_cost:.4%}")

        port_sub = port_df[port_df["factor"] == factor_col]
        gross_return = port_sub["long_short_return"].mean()
        net_return = gross_return - monthly_cost

        print(f"\n  Gross mean return/bulan       : {gross_return:.4%}")
        print(f"  Net mean return/bulan (est.)  : {net_return:.4%}")

        if gross_return != 0:
            pct_eaten = (monthly_cost / abs(gross_return)) * 100
            print(f"  % return yang 'habis' kena cost: {pct_eaten:.1f}%")

        if net_return <= 0 < gross_return:
            print("\n  ⚠ PERINGATAN: Return positif di gross, tapi jadi NEGATIF setelah cost.")
            print("    Strategi ini mungkin tidak feasible untuk dieksekusi secara real.")


def main():
    print("=== Load data ===")
    factors, ic_df, port_df = load_data()

    print("\n\n" + "#" * 65)
    print("# BAGIAN 1: SUB-PERIOD STABILITY ANALYSIS")
    print("#" * 65)
    sub_period_results = sub_period_analysis(ic_df, port_df)

    print("\n\n" + "#" * 65)
    print("# BAGIAN 2: TURNOVER & TRANSACTION COST ANALYSIS")
    print("#" * 65)
    turnover_cost_analysis(factors, port_df)

    sub_period_results.to_parquet(OUTPUT_PATH, index=False)
    print(f"\n\nRingkasan sub-period tersimpan di: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
