"""
Step 2: Hitung Momentum & Low-Volatility Factor
=================================================
Input : data/prices_raw.parquet (hasil dari 01_fetch_data.py)
Output: data/factor_scores.parquet

Factor yang dihitung:
1. Momentum (12-1)   -> return 12 bulan terakhir, TAPI skip bulan paling akhir.
                         Ini standar akademik (Jegadeesh & Titman) karena return
                         1 bulan terakhir sering kena short-term reversal effect,
                         bukan representasi murni "momentum".
2. Low Volatility     -> std dev return harian 60 hari terakhir, dinegasikan.
                         Dinegasikan supaya "skor tinggi = bagus" (konsisten
                         dengan momentum, biar gampang di-rank bareng nanti).

Kedua factor dihitung di akhir tiap bulan (month-end), lalu di-rank secara
cross-sectional (dibandingkan antar saham di bulan yang sama, bukan antar waktu).
"""

import pandas as pd
import numpy as np

INPUT_PATH = "data/prices_raw.parquet"
OUTPUT_PATH = "data/factor_scores.parquet"

MOMENTUM_LOOKBACK_MONTHS = 12
MOMENTUM_SKIP_MONTHS = 1        # skip 1 bulan terakhir (short-term reversal)
LOWVOL_LOOKBACK_DAYS = 60
MIN_HISTORY_DAYS = 252          # minimal 1 tahun data biar factor valid


def load_prices(path: str) -> pd.DataFrame:
    df = pd.read_parquet(path)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["ticker", "date"])
    return df


def compute_daily_returns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["daily_return"] = df.groupby("ticker")["close"].pct_change()
    return df


def get_month_end_prices(df: pd.DataFrame) -> pd.DataFrame:
    """Ambil harga di hari terakhir tiap bulan, per ticker."""
    df = df.copy()
    df["year_month"] = df["date"].dt.to_period("M")
    month_end = (
        df.sort_values("date")
        .groupby(["ticker", "year_month"])
        .last()
        .reset_index()
    )
    return month_end[["ticker", "year_month", "date", "close"]]


def compute_momentum(month_end: pd.DataFrame) -> pd.DataFrame:
    """
    Momentum 12-1: return dari t-12 ke t-1 (skip bulan terakhir).
    Dihitung per ticker, di-sort by year_month.
    """
    result = []
    for ticker, group in month_end.groupby("ticker"):
        group = group.sort_values("year_month").reset_index(drop=True)
        prices = group["close"].values
        n = len(prices)

        for i in range(n):
            lookback_idx = i - MOMENTUM_SKIP_MONTHS - MOMENTUM_LOOKBACK_MONTHS
            skip_idx = i - MOMENTUM_SKIP_MONTHS
            if lookback_idx < 0:
                mom = np.nan
            else:
                mom = (prices[skip_idx] / prices[lookback_idx]) - 1
            result.append({
                "ticker": ticker,
                "year_month": group.loc[i, "year_month"],
                "date": group.loc[i, "date"],
                "momentum": mom,
            })
    return pd.DataFrame(result)


def compute_low_vol(daily_df: pd.DataFrame, month_end: pd.DataFrame) -> pd.DataFrame:
    """
    Low-vol factor: rolling std dev return harian 60 hari, dinegasikan,
    diambil nilainya persis di tanggal month-end.
    """
    daily_df = daily_df.copy()
    daily_df["rolling_vol"] = (
        daily_df.groupby("ticker")["daily_return"]
        .transform(lambda x: x.rolling(LOWVOL_LOOKBACK_DAYS, min_periods=LOWVOL_LOOKBACK_DAYS // 2).std())
    )

    merged = month_end.merge(
        daily_df[["ticker", "date", "rolling_vol"]],
        on=["ticker", "date"],
        how="left",
    )
    merged["low_vol"] = -merged["rolling_vol"]  # negasikan: vol rendah -> skor tinggi
    return merged[["ticker", "year_month", "low_vol"]]


def cross_sectional_rank(df: pd.DataFrame, col: str) -> pd.Series:
    """Rank tiap saham dibanding saham lain di BULAN YANG SAMA (0 = terendah, 1 = tertinggi)."""
    return df.groupby("year_month")[col].rank(pct=True)


def main():
    print("=== Load data harga ===")
    prices = load_prices(INPUT_PATH)
    print(f"Total baris: {len(prices)}, ticker: {prices['ticker'].nunique()}")

    print("\n=== Hitung daily return ===")
    prices = compute_daily_returns(prices)

    print("\n=== Ambil harga month-end ===")
    month_end = get_month_end_prices(prices)
    print(f"Total observasi bulanan: {len(month_end)}")

    print("\n=== Hitung momentum factor ===")
    momentum_df = compute_momentum(month_end)

    print("\n=== Hitung low-volatility factor ===")
    lowvol_df = compute_low_vol(prices, month_end)

    print("\n=== Gabungkan & ranking cross-sectional ===")
    factors = momentum_df.merge(lowvol_df, on=["ticker", "year_month"], how="left")
    factors["momentum_rank"] = cross_sectional_rank(factors, "momentum")
    factors["low_vol_rank"] = cross_sectional_rank(factors, "low_vol")

    # Buang baris yang belum punya cukup history (awal periode)
    factors_clean = factors.dropna(subset=["momentum", "low_vol"])
    print(f"\nTotal baris sebelum drop NaN: {len(factors)}")
    print(f"Total baris setelah drop NaN (cukup history): {len(factors_clean)}")

    factors_clean.to_parquet(OUTPUT_PATH, index=False)
    print(f"\nData factor tersimpan di: {OUTPUT_PATH}")

    print("\nPreview:")
    print(factors_clean.sort_values(["year_month", "ticker"]).head(10))

    print("\nRingkasan statistik momentum & low_vol:")
    print(factors_clean[["momentum", "low_vol"]].describe())


if __name__ == "__main__":
    main()
