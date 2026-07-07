"""
Step 1: Fetch Data untuk Factor Model Project (v2 — full universe + checkpoint)
=================================================================================
Script ini melakukan 2 hal:
1. Ambil daftar ticker S&P 500 (dari GitHub dataset yang selalu ter-update)
2. Download data harga historis (2015 - hari ini) untuk semua ticker via yfinance

Jalankan di komputer lokal kamu (bukan di sandbox), karena butuh akses
ke Yahoo Finance yang biasanya diblokir di lingkungan sandbox/cloud.

Install dulu: pip install yfinance pandas pyarrow

FITUR BARU di versi ini (dibanding v1):
- Progress tracking: tau lagi di batch keberapa, berapa lama estimasi sisa waktu
- Checkpoint/resume: kalau script ke-interupt (Ctrl+C, koneksi putus, laptop mati),
  jalankan lagi scriptnya dan otomatis lanjut dari batch terakhir yang belum selesai,
  TIDAK perlu download ulang dari awal. Penting untuk full run 500+ ticker yang
  bisa makan waktu belasan menit.
- Ringkasan ticker yang gagal di-download di akhir (biar kamu tau saham mana
  yang bermasalah, misal delisted atau baru IPO setelah 2015).
"""


import pandas as pd
import yfinance as yf
import time
import os
import random
from datetime import date, timedelta

# ============================================================
# KONFIGURASI
# ============================================================
START_DATE = "2015-01-01"
END_DATE = date.today().strftime("%Y-%m-%d")  # otomatis narik sampai data paling baru saat script dijalankan
OUTPUT_DIR = "data"
BATCH_SIZE = 50          # download per batch biar nggak kena rate limit
SLEEP_BETWEEN_BATCH = 2  # detik, jeda antar batch

CHECKPOINT_PATH = f"{OUTPUT_DIR}/_checkpoint_prices.parquet"
FINAL_OUTPUT_PATH = f"{OUTPUT_DIR}/prices_raw.parquet"

# Set False untuk full universe (503 ticker) -- ini yang dipakai untuk hasil final.
# Set True kalau cuma mau quick-test pipeline (subset random, bukan alfabetis,
# biar tidak oversample nama-nama berawalan huruf tertentu).
USE_SUBSET_FOR_TESTING = False
SUBSET_SIZE = 50
RANDOM_SEED = 42


def get_sp500_tickers() -> pd.DataFrame:
    """Ambil daftar konstituen S&P 500 terbaru dari GitHub."""
    url = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv"
    df = pd.read_csv(url)
    df = df.rename(columns={"Symbol": "ticker", "Security": "name", "GICS Sector": "sector"})
    df["ticker"] = df["ticker"].str.replace(".", "-", regex=False)
    return df[["ticker", "name", "sector"]]


def load_checkpoint() -> pd.DataFrame | None:
    """Load data yang sudah ter-download dari run sebelumnya, kalau ada."""
    if os.path.exists(CHECKPOINT_PATH):
        df = pd.read_parquet(CHECKPOINT_PATH)
        print(f"[CHECKPOINT DITEMUKAN] {df['ticker'].nunique()} ticker sudah ter-download dari run sebelumnya.")
        return df
    return None


def save_checkpoint(df: pd.DataFrame) -> None:
    df.to_parquet(CHECKPOINT_PATH, index=False)


def format_eta(seconds: float) -> str:
    return str(timedelta(seconds=int(seconds)))


def download_price_data(tickers: list, start: str, end: str, already_done: set) -> pd.DataFrame:
    """
    Download adjusted close price untuk list ticker, dalam batch.
    Skip ticker yang sudah ada di checkpoint (`already_done`).
    """
    remaining = [t for t in tickers if t not in already_done]
    if not remaining:
        print("Semua ticker sudah ter-download sebelumnya, tidak ada yang perlu di-fetch lagi.")
        return pd.DataFrame()

    print(f"Ticker yang perlu di-download: {len(remaining)} (dari total {len(tickers)}, "
          f"{len(already_done)} sudah selesai sebelumnya)")

    all_data = []
    failed_tickers = []
    n_batches = (len(remaining) + BATCH_SIZE - 1) // BATCH_SIZE
    batch_durations = []

    for batch_idx in range(n_batches):
        batch_start_time = time.time()
        i = batch_idx * BATCH_SIZE
        batch = remaining[i : i + BATCH_SIZE]

        # --- progress & ETA ---
        elapsed = sum(batch_durations)
        avg_batch_time = elapsed / len(batch_durations) if batch_durations else None
        eta_str = format_eta(avg_batch_time * (n_batches - batch_idx)) if avg_batch_time else "menghitung..."
        print(f"\n[Batch {batch_idx + 1}/{n_batches}] {len(batch)} ticker | "
              f"elapsed: {format_eta(elapsed)} | estimasi sisa: {eta_str}")
        print(f"  Ticker: {batch[:5]}{'...' if len(batch) > 5 else ''}")

        try:
            data = yf.download(
                batch,
                start=start,
                end=end,
                auto_adjust=True,
                progress=False,
                group_by="ticker",
                threads=True,
            )

            batch_success = 0
            for ticker in batch:
                try:
                    if len(batch) == 1:
                        sub = data[["Close", "Volume"]].copy()
                    else:
                        sub = data[ticker][["Close", "Volume"]].copy()
                    sub = sub.dropna(subset=["Close"])
                    if sub.empty:
                        failed_tickers.append(ticker)
                        continue
                    sub["ticker"] = ticker
                    sub.index.name = "date"  # paksa nama index, jangan asumsikan nama asli "Date"
                    sub = sub.reset_index().rename(columns={"Close": "close", "Volume": "volume"})
                    all_data.append(sub)
                    batch_success += 1
                except (KeyError, TypeError):
                    failed_tickers.append(ticker)

            print(f"  -> berhasil: {batch_success}/{len(batch)}")

        except Exception as e:
            print(f"  [ERROR] batch gagal total: {e}")
            failed_tickers.extend(batch)

        # simpan checkpoint tiap selesai 1 batch, biar kalau crash di batch berikutnya
        # progress yang sudah didapat tidak hilang
        if all_data:
            combined_so_far = pd.concat(all_data, ignore_index=True)
            if already_done:
                # gabung dengan data checkpoint lama juga
                old = pd.read_parquet(CHECKPOINT_PATH) if os.path.exists(CHECKPOINT_PATH) else pd.DataFrame()
                combined_so_far = pd.concat([old, combined_so_far], ignore_index=True).drop_duplicates(
                    subset=["ticker", "date"]
                )
            save_checkpoint(combined_so_far)

        batch_durations.append(time.time() - batch_start_time)
        if batch_idx < n_batches - 1:
            time.sleep(SLEEP_BETWEEN_BATCH)

    if failed_tickers:
        print(f"\n[PERINGATAN] {len(failed_tickers)} ticker gagal di-download:")
        print(f"  {failed_tickers}")
        print("  (Biasanya karena delisted, baru IPO, atau salah format ticker)")

    result = pd.concat(all_data, ignore_index=True) if all_data else pd.DataFrame()
    return result


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    overall_start = time.time()

    print("=== Step 1: Ambil daftar ticker S&P 500 ===")
    tickers_df = get_sp500_tickers()
    print(f"Total ticker: {len(tickers_df)}")
    tickers_df.to_csv(f"{OUTPUT_DIR}/sp500_tickers.csv", index=False)

    ticker_list = tickers_df["ticker"].tolist()
    if USE_SUBSET_FOR_TESTING:
        rng = random.Random(RANDOM_SEED)
        ticker_list = rng.sample(ticker_list, SUBSET_SIZE)
        print(f"[MODE TEST] Random sample {SUBSET_SIZE} ticker (seed={RANDOM_SEED}), bukan alfabetis.")
    else:
        print(f"[MODE FULL] Semua {len(ticker_list)} ticker S&P 500 akan di-download.")

    print("\n=== Step 2: Download data harga historis ===")

    checkpoint_df = load_checkpoint()
    already_done = set(checkpoint_df["ticker"].unique()) if checkpoint_df is not None else set()

    new_data = download_price_data(ticker_list, START_DATE, END_DATE, already_done)

    # Gabungkan checkpoint lama + data baru
    if checkpoint_df is not None and not new_data.empty:
        price_data = pd.concat([checkpoint_df, new_data], ignore_index=True).drop_duplicates(subset=["ticker", "date"])
    elif checkpoint_df is not None:
        price_data = checkpoint_df
    else:
        price_data = new_data

    price_data = price_data.dropna(subset=["close"])

    total_elapsed = time.time() - overall_start
    print(f"\n=== SELESAI (total waktu: {format_eta(total_elapsed)}) ===")
    print(f"Total baris data: {len(price_data)}")
    print(f"Jumlah ticker berhasil: {price_data['ticker'].nunique()} / {len(ticker_list)}")
    print(f"Rentang tanggal: {price_data['date'].min()} - {price_data['date'].max()}")

    price_data.to_parquet(FINAL_OUTPUT_PATH, index=False)
    print(f"\nData final tersimpan di: {FINAL_OUTPUT_PATH}")

    # Bersihkan checkpoint setelah berhasil selesai total
    if os.path.exists(CHECKPOINT_PATH):
        os.remove(CHECKPOINT_PATH)
        print("Checkpoint dibersihkan (run sudah selesai penuh).")

    print("\nPreview data:")
    print(price_data.head(10))


if __name__ == "__main__":
    main()
