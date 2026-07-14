# Riset Faktor Momentum dan Low-Volatility pada S&P 500 (2015–2026)

*Studi cross-sectional equity factor: konstruksi, validasi, dan pengujian ketahanan dari dua anomali klasik selama sampel 11,5 tahun.*

---

## Ringkasan Eksekutif

Proyek ini membangun dan menguji secara ketat dua faktor ekuitas yang terkenal - **momentum 12 bulan** dan **low-volatility** - pada keseluruhan *universe* S&P 500 (503 konstituen) dari Januari 2015 hingga Juli 2026. Tujuannya bukan sekadar untuk melakukan *backtest* strategi, melainkan untuk menerapkan disiplin statistik dari riset faktor: pemeringkatan *cross-sectional*, analisis *Information Coefficient* (IC), uji ketahanan sub-periode, dan estimasi biaya transaksi.

**Temuan Utama:**

- **Momentum tidak menunjukkan kekuatan prediktif yang dapat diandalkan** pada sampel ini. Rata-rata *Information Coefficient* pada dasarnya nol (IC = -0.003, t-stat = 0.34), dan kesimpulan ini semakin kuat - bukan melemah - ketika *universe* diperbesar dari subset kecil menjadi 503 saham penuh. Ini merupakan sinyal kuat bahwa "keuntungan" pada sampel kecil didorong oleh kebisingan idiosinkratik (*idiosyncratic noise*) daripada efek yang sebenarnya.
- **Low-volatility menunjukkan anomali terbalik (*reversed*) yang signifikan secara statistik.** Bertentangan dengan anomali *low-volatility* tradisional (yang memprediksi bahwa saham *low-vol* akan mengungguli pasar), saham-saham dengan volatilitas tinggi pada sampel ini justru **mengungguli** saham-saham dengan volatilitas rendah dengan margin yang lebar dan signifikan secara statistik (IC = -0.033, t-stat = -2.79). Hasil ini konsisten secara arah di seluruh ketiga rezim pasar yang diuji, dan paling kuat selama reli yang didorong oleh AI pada 2023–2026 (t-stat = -2.49).
- Setelah memperhitungkan biaya transaksi yang realistis, imbal hasil kotor (*gross return*) momentum yang sudah marjinal berkurang sekitar sepertiganya, sementara imbal hasil negatif *low-volatility* hampir tidak terpengaruh (biaya *turnover* hanyalah pembulatan angka dibandingkan dengan besarnya kerugian).

Bagian paling menarik dari proyek ini adalah metodologinya: versi awal *pipeline* menggunakan subset tetap 50 saham untuk iterasi cepat, yang - karena daftar *ticker* diurutkan berdasarkan alfabet - secara kebetulan terlalu banyak mengambil sampel nama-nama teknologi berkapitalisasi sangat besar (AAPL, ADBE, AMD, AMZN, ANET, GOOGL). Hal ini menghasilkan gambaran yang **sangat** terinflasi dan menyesatkan untuk kedua faktor. Menangkap, mendiagnosis, dan memperbaiki bias ini (pertama melalui sampel acak, kemudian melalui *universe* penuh) didokumentasikan di bawah ini, karena hal tersebut secara material mengubah kesimpulan dan bisa dibilang merupakan "temuan" terpenting dari keseluruhan latihan ini.

---

## 1. Motivasi

Berasal dari latar belakang *data science*, saya menginginkan proyek yang dapat diterjemahkan dengan jelas ke dalam bahasa *quantitative equity research* - proyek yang melatih inferensi statistik, analisis *cross-sectional*, dan pemikiran sadar risiko dibandingkan sekadar narasi "model saya memprediksi harga akan naik". Investasi faktor sangat cocok: ini adalah kosakata yang digunakan oleh *quant research desks* dan *asset managers*, ia menghargai validasi yang ketat dibandingkan sekadar angka imbal hasil utama (*headline returns*), dan memaksa adanya diskusi eksplisit tentang **mengapa** suatu sinyal mungkin berhasil atau tidak - bukan hanya sekadar apakah kurva ekuitas hasil *backtest* naik ke kanan atas.

Dua faktor dipilih karena karakternya yang kontras:

- **Momentum** - faktor perilaku/*trend-following*, secara historis merupakan salah satu anomali paling kuat dalam literatur akademis (Jegadeesh & Titman, 1993), tetapi juga diketahui sering mengalami *crash* tajam secara periodik.
- **Low-volatility** - faktor "defensif", didorong oleh pengamatan empiris bahwa saham berisiko rendah secara historis memberikan pengembalian yang disesuaikan dengan risiko (dan terkadang absolut) yang secara mengejutkan kompetitif, yang bertentangan dengan teori penetapan harga aset klasik (Ang et al., 2006; Frazzini & Pedersen, 2014).

---

## 2. Data & Metodologi

### 2.1 Universe dan Data

- **Universe:** Seluruh 503 konstituen S&P 500 saat ini (daftar *ticker* bersumber dari dataset GitHub yang diperbarui dari konstituen S&P 500).
- **Data Harga:** Harga penutupan yang disesuaikan (*adjusted close prices*) harian dari Yahoo Finance melalui `yfinance`, disesuaikan otomatis untuk *splits* dan dividen.
- **Periode:** 2 Januari 2015 – 2 Juli 2026 (~11,5 tahun), mencakup tiga rezim pasar yang berbeda: *bull market* pra-COVID (2015–2019), *crash* COVID dan siklus kenaikan suku bunga berikutnya (2020–2022), dan pemulihan/reli yang didorong oleh AI (2023–2026).
- **Cakupan:** 501 dari 503 *ticker* berhasil diunduh (2 gagal - `ADI` dan `ANET` - karena masalah penyedia data yang bersifat sementara pada saat diunduh; bukan dikecualikan karena alasan substantif). Setelah mensyaratkan riwayat masa lalu yang cukup untuk konstruksi faktor, rata-rata *universe* aktif adalah **~484 saham per bulan**.

### 2.2 Konstruksi Faktor

| Faktor | Definisi | Rasional |
|---|---|---|
| **Momentum (12-1)** | Imbal hasil kumulatif selama 12 bulan terakhir, **melewati bulan paling terakhir** | Melompati 1 bulan adalah praktik akademis standar (Jegadeesh & Titman, 1993) untuk menghindari kontaminasi sinyal dari efek pembalikan jangka pendek (*short-term reversal*) |
| **Low-Volatility** | Standar deviasi pergerakan harga 60 hari perdagangan terakhir, **dinegasikan** sehingga skor yang lebih tinggi selalu berarti "lebih baik" (yaitu, volatilitas yang direalisasikan lebih rendah) | Konvensi tanda yang konsisten membuat perbandingan antar faktor dan pemeringkatan menjadi mudah |

Kedua faktor dihitung pada setiap akhir bulan dan kemudian diubah menjadi **peringkat persentil cross-sectional** (0 = terlemah, 1 = terkuat) *di dalam bulan tersebut*, sehingga suatu saham hanya akan dibandingkan dengan rekan-rekannya pada titik waktu yang sama - tidak pernah dengan sejarahnya sendiri.

### 2.3 Konstruksi Portofolio & Validasi

Dua tes yang saling melengkapi digunakan, mencerminkan praktik standar akademis dan industri:

1. **Information Coefficient (IC):** Korelasi peringkat Spearman antara skor faktor suatu saham pada bulan *t* dan imbal hasil ke depannya pada bulan *t+1*, dihitung secara *cross-sectional* setiap bulan. Ini secara langsung mengukur kekuatan prediktif tanpa terikat pada aturan konstruksi portofolio tertentu. Aturan praktis industri yang umum menganggap |IC| > 0.05 sebagai sinyal yang bermakna.
2. **Portofolio kuantil long-short:** Setiap bulan, saham-saham diurutkan ke dalam 5 keranjang dengan ukuran yang sama berdasarkan skor faktor. Strategi ini melakukan *long* pada kuintil teratas (Q5) dan *short* pada kuintil terbawah (Q1), dalam bobot yang sama, diseimbangkan setiap bulan. Ini adalah konstruksi yang sama yang digunakan dalam literatur faktor Fama-French.

Signifikansi statistik dari seri imbal hasil *long-short* dinilai melalui t-statistik standar (rata-rata imbal hasil bulanan / (standar deviasi / √n)); ambang batas umum untuk signifikansi statistik adalah |t| > 2.

**Kontrol Look-ahead bias:** imbal hasil ke depan dihitung secara ketat dari bulan *t* hingga bulan *t+1*; skor faktor tidak pernah diperbolehkan untuk "melihat" pengembalian yang seharusnya diprediksinya.

### 2.4 Uji Ketahanan (Robustness Checks)

- **Stabilitas Sub-periode:** IC dan statistik portofolio *long-short* dihitung kembali secara terpisah di dalam masing-masing ketiga rezim pasar yang dijelaskan di atas, untuk memeriksa apakah keunggulan yang terlihat dari suatu faktor adalah nyata, bukan efek yang independen dari rezim atau sekadar artifak dari satu lingkungan pasar tertentu.
- **Turnover & Biaya Transaksi:** Setiap bulan, keanggotaan dalam posisi *long* dan *short* dibandingkan dengan bulan sebelumnya untuk mengestimasi perputaran (*turnover*) satu arah. Asumsi konservatif sebesar 10 bps untuk biaya setiap perdagangan (*round-trip*, kedua kaki perdagangan) kemudian diterapkan untuk menerjemahkan imbal hasil kotor menjadi estimasi pengembalian bersih (*net-of-cost*) yang lebih realistis.

---

## 3. Penyimpangan Metodologi: Mendiagnosis Bias Sampel

Sebelum menyajikan hasil akhir, perlu didokumentasikan masalah yang muncul selama pengembangan, karena masalah ini secara substansial mengubah kesimpulan dan merupakan ilustrasi yang baik dari jenis pengawasan yang dibutuhkan dalam riset faktor.

Untuk iterasi cepat, versi awal dari *pipeline* menggunakan subset 50 saham alih-alih seluruh *universe*. Subset dipilih sebagai `ticker_list[:50]` - 50 *ticker* pertama dari daftar yang **diurutkan berdasarkan alfabet**. Ini bukanlah sampel acak: karena nama perusahaan yang berawalan huruf "A" kebetulan mencakup beberapa pemenang teknologi/AI terbesar dari periode sampel (**AAPL, ADBE, AMD, AMZN, ANET, GOOGL/GOOG**), subset ini secara struktural kelebihan bobot pada saham-saham yang mendorong sebagian besar pengembalian pasar di 2023–2026.

Efeknya terhadap hasil sangat dramatis:

| Metrik | Alfabetis 50 (bias) | Acak 50 | **Penuh 503 (akhir)** |
|---|---:|---:|---:|
| Momentum IC | -0.001 | +0.009 | **-0.003** |
| Momentum t-stat | 1.04 | 0.73 | **0.34** |
| Pengembalian Kumulatif Momentum | +62.2% | +30.4% | **+4.5%** |
| Low-vol IC | -0.047 | -0.035 | **-0.033** |
| Low-vol t-stat | **-3.00** | -1.44 | **-2.79** |
| Pengembalian Kumulatif Low-vol | -93.2% | -79.5% | **-86.7%** |

Dua hal menonjol. Pertama, **keuntungan nyata momentum runtuh hampir seluruhnya** ketika sampel membesar dari 50 saham (bias alfabetis) ke seluruh 503 saham - pengembalian kumulatif *long-short* turun dari +62% menjadi +4.5%, dan nilai t-statistik turun ke sebagian kecil dari titik awal yang sudah tidak signifikan. Ini adalah ilustrasi buku teks tentang bagaimana kuintil kecil yang tidak acak (~10 saham per keranjang pada n=50) dapat menghasilkan pola pengembalian yang terlihat bermakna namun sebenarnya hanya didorong oleh segelintir pemenang idiosinkratik.

Kedua, dan yang lebih menarik: **pembalikan low-volatility bertahan dari koreksi tersebut.** Bahkan setelah beralih ke sampel acak yang asli dan kemudian ke *universe* penuh, saham dengan volatilitas tinggi terus mengungguli saham dengan volatilitas rendah dengan margin yang besar dan signifikan secara statistik. Hal ini memberikan kepercayaan yang jauh lebih besar bahwa ini adalah pola nyata dalam data untuk periode tersebut, bukan sekadar artifak dari 50 saham mana yang kebetulan diambil sebagai sampel.

---

## 4. Hasil

### 4.1 Momentum

![Momentum factor summary](charts/momentum_summary.png)

Di seluruh keseluruhan universe 503 saham:

| Metrik | Nilai |
|---|---:|
| Mean IC | -0.003 |
| IC Information Ratio (IC-IR) | -0.017 |
| % bulan dengan IC positif | 52.0% |
| Rata-rata pengembalian long-short / bulan | 0.14% |
| Annualized Sharpe ratio | 0.11 |
| t-statistic | 0.34 |
| Pengembalian Kumulatif (11.5 tahun) | +4.5% |

**Interpretasi:** berdasarkan setiap ukuran, kekuatan prediktif momentum pada sampel ini tidak dapat dibedakan dari *noise* (kebisingan). IC pada dasarnya nol, hanya sedikit lebih dari separuh bulan yang menunjukkan tanda yang "benar", dan nilai t-statistik (0.34) jauh di bawah ambang batas signifikansi konvensional yaitu 2. Grafik IC 12-bulan *rolling* menunjukkan sinyal berosilasi tak terduga di sekitar titik nol selama seluruh sampel, tanpa adanya periode berkelanjutan dari kekuatan prediktif positif yang konsisten. Pengembalian kumulatif yang hampir datar (+4.5% selama 11,5 tahun, pada dasarnya sama seperti melempar koin setelah dikurangi biaya) konsisten dengan temuan ini.

**Rincian sub-periode:**

| Periode | Mean IC | t-stat |
|---|---:|---:|
| 2015–2019 (Pre-COVID Bull) | -0.019 | -0.37 |
| 2020–2022 (COVID + Rate Hike) | -0.017 | -0.54 |
| 2023–2026 (Recovery/AI Rally) | +0.025 | 1.59 |

*Keputusan dari pipeline: tidak konsisten - tanda IC berbalik di antara rezim.* Periode terakhir menunjukkan sinyal terkuat (meskipun masih belum signifikan secara konvensional), yang mungkin patut ditinjau kembali dengan lebih banyak data seiring berjalannya rezim pasar saat ini, namun masih terlalu dini untuk menyebut ini sebagai keunggulan yang dapat diandalkan.

### 4.2 Low-Volatility

![Low-volatility factor summary](charts/low_vol_summary.png)

| Metrik | Nilai |
|---|---:|
| Mean IC | -0.033 |
| IC Information Ratio (IC-IR) | -0.143 |
| % bulan dengan IC positif | 44.8% |
| Rata-rata pengembalian long-short / bulan | -1.43% |
| Annualized Sharpe ratio | -0.87 |
| t-statistic | **-2.79** |
| Pengembalian Kumulatif (11.5 tahun) | -86.7% |

**Interpretasi:** ini adalah hasil yang lebih menarik secara statistik - dan lebih merupakan peringatan - dari kedua faktor tersebut. Tanda negatif berarti, pada sampel ini, memiliki posisi *long* di saham yang **paling volatil** dan *short* di saham yang **paling tidak volatil** menguntungkan; "premium low-vol" yang didokumentasikan dalam banyak literatur penetapan harga aset berbalik di sini. Sebuah t-statistik sebesar -2.79 dengan nyaman melewati batas signifikansi konvensional (sekitar p ≈ 0.006), dan 44.8% bulan menunjukkan IC positif (yaitu, mayoritas menunjukkan IC negatif dalam arah yang "diharapkan") memperkuat bahwa ini bukan kebetulan yang didorong oleh beberapa bulan ekstrem.

**Rincian sub-periode:**

| Periode | Mean IC | t-stat |
|---|---:|---:|
| 2015–2019 (Pre-COVID Bull) | -0.034 | -1.37 |
| 2020–2022 (COVID + Rate Hike) | -0.017 | -1.07 |
| 2023–2026 (Recovery/AI Rally) | -0.044 | **-2.49** |

*Keputusan dari pipeline: konsisten - tanda IC negatif di ketiga rezim.* Efeknya paling kuat pada periode terakhir, yang mana juga memiliki bukti statistik terkuat (n yang besar, |t-stat| terbesar).

**Narasi yang masuk akal, dengan asumsi longgar:** periode sampel ini didominasi oleh perpanjangan *bull market* yang dipimpin oleh pertumbuhan/teknologi, dan terutama oleh reli AI 2023–2026. Nama-nama *mega-cap growth* dan infrastruktur semikonduktor/AI - yang cenderung berjalan pada volatilitas yang direalisasikan lebih tinggi daripada sektor defensif seperti utilitas dan bahan pokok konsumen - memberikan pengembalian luar biasa selama jendela yang tepat ini. Sebuah strategi "long low-vol, short high-vol" berarti melakukan posisi *short* tepat pada saham-saham yang mendorong kenaikan pasar. Ini ditawarkan sebagai penjelasan logis yang spesifik untuk rezim ini, bukan klaim bahwa anomali *low-volatility* "mati" secara permanen - pada periode sampel yang berbeda, atau versi faktor yang menetralkan eksposur sektor dan beta, bisa saja menunjukkan gambaran yang berbeda.

### 4.3 Perbandingan Berdampingan

![Comparison of cumulative returns](charts/comparison_all_factors.png)

Perbedaan antara kedua faktor ini sangat mencolok di seluruh sampel: momentum berakhir hampir mendatar, sementara portofolio *long-short low-volatility* terus menerus kehilangan nilainya di hampir sepanjang jendela 11,5 tahun, dengan penurunan yang semakin cepat dalam periode reli AI terakhir.

---

## 5. Turnover dan Biaya Transaksi

Suatu faktor yang terlihat menarik di atas kertas bisa menjadi jauh kurang menarik begitu biaya perdagangan yang realistis dimasukkan. Dengan asumsi konservatif berupa biaya bolak-balik 10 bps untuk setiap nama yang diperdagangkan:

| Faktor | Rata-rata turnover bulanan | Est. biaya bulanan | Pengembalian kotor/bulan | Pengembalian bersih/bulan | % dari pengembalian kotor yang hilang karena biaya |
|---|---:|---:|---:|---:|---:|
| Momentum | 22.0% | 0.044% | 0.130% | 0.086% | 33.8% |
| Low-Vol | 21.5% | 0.043% | -1.418% | -1.461% | 3.0%\* |

\*Untuk *low-vol*, biaya membuat pengembalian yang sudah negatif menjadi sedikit *lebih* negatif; angka "% hilang karena biaya" tidak memiliki arti yang sama seperti pada strategi yang menguntungkan - disertakan hanya untuk kelengkapan.

**Interpretasi:** *turnover* momentum (22% dari buku yang di-*rebalance* setiap bulan) cukup tinggi sehingga biaya transaksi mengikis sekitar sepertiga dari pengembalian kotor marjinal yang sudah tidak signifikan secara statistik - ini menegaskan bahwa faktor ini bukan strategi *standalone* yang layak pada sampel ini. Untuk *low-volatility*, biaya transaksi hanyalah pembulatan angka dibandingkan dengan besarnya kerugian; biaya bukanlah alasan mengapa faktor ini berkinerja buruk.

---

## 6. Keterbatasan

Proyek ini adalah latihan yang cermat secara metodologis, tetapi bukanlah strategi perdagangan yang siap diproduksi, dan beberapa keterbatasan harus diingat:

- **Hanya portofolio berbobot sama (*Equal-weighted*).** Tidak ada pembobotan berbasis risiko, penargetan volatilitas, atau netralisasi beta yang diterapkan. Khususnya, hasil *low-volatility* kemungkinan sebagian merupakan taruhan terselubung terhadap beta pasar; versi yang netral beta atau netral industri dari faktor ini mungkin menceritakan kisah yang berbeda.
- **Tanpa penyesuaian survivorship-bias.** *Universe* ini merupakan daftar konstituen S&P 500 **saat ini** yang diterapkan secara retroaktif hingga tahun 2015; perusahaan yang dikeluarkan dari indeks (karena akuisisi, kebangkrutan, atau kinerja buruk) selama periode sampel tidak dimasukkan. Hal ini cenderung membesar-besarkan kualitas **rata-rata** saham dalam sampel dan dapat mempengaruhi pengembalian terukur dari kedua faktor.
- **Universe berkapitalisasi besar, satu negara.** Hasilnya mungkin tidak dapat digeneralisasi ke saham berkapitalisasi kecil, pasar lain, atau rezim likuiditas yang berbeda.
- **Model biaya transaksi adalah penyederhanaan.** Asumsi tetap sebesar 10 bps tidak menangkap dampak pasar (*market impact*), yang akan berskala dengan ukuran posisi, atau fakta bahwa biaya bervariasi secara bermakna berdasarkan likuiditas saham dan rezim pasar (misalnya, biaya melonjak selama jenis peristiwa volatilitas seperti *crash* COVID 2020, yang termasuk dalam sampel ini).
- **Dua faktor, satu dataset, tanpa data tahanan (*holdout*) out-of-sample.** Dengan hanya dua faktor yang diuji dan tidak ada data yang ditahan untuk pemeriksaan *out-of-sample* yang sebenarnya, ada risiko bahwa bahkan hasil *low-volatility* yang tampak lebih kuat ini mencerminkan sampel historis yang spesifik ini daripada hubungan struktural berwawasan ke depan.

---

## 7. Kesimpulan & Langkah Selanjutnya

Proyek ini bertujuan untuk membangun *pipeline* riset faktor dengan ketelitian statistik yang diharapkan dalam *quantitative equity research*, bukan hanya sekadar membuat satu buah *backtest* yang dioptimalkan agar terlihat bagus. Hasil paling berharganya mungkin bukan pada angka akhir masing-masing faktor, melainkan proses yang didemonstrasikan: membangun faktor dengan benar, memvalidasi dengan IC dan portofolio *long-short* alih-alih mengandalkan nilai *return* mentah saja, memeriksa stabilitas sub-periode, memperhitungkan biaya - dan, di sepanjang jalan, menangkap serta mengoreksi bias sampel yang jika tidak, akan menghasilkan kesimpulan yang sangat menyesatkan.

**Ekstensi alami yang dapat dilakukan:**

- Menambahkan faktor **value** dan/atau **quality** (memerlukan data fundamental, misalnya rasio *book-to-market*, ROE) untuk membangun model multi-faktor yang sejati.
- Membangun versi **beta-neutral** dari faktor *low-volatility* untuk menguji apakah pembalikan yang didokumentasikan di sini tetap ada ketika eksposur terhadap beta pasar dikendalikan.
- Memperpanjang *universe* mundur menggunakan keanggotaan indeks **point-in-time** untuk menghilangkan bias keberlangsungan hidup (*survivorship bias*).
- Menggabungkan momentum dan *low-volatility* menjadi satu skor gabungan dan menguji apakah kombinasinya menawarkan manfaat diversifikasi, mengingat aliran pengembaliannya tampaknya sangat tidak berkorelasi selama sampel ini.

---

## Lampiran: Keterulangan (Reproducibility)

Semua kode untuk proyek ini disertakan bersama laporan ini:

| File | Tujuan |
|---|---|
| `01_fetch_data.py` | Mengunduh daftar konstituen S&P 500 dan harga historis, dengan dukungan untuk melanjutkan dari titik periksa (*checkpoint/resume*) |
| `02_compute_factors.py` | Menghitung momentum (12-1) dan skor faktor *low-volatility* (60-hari) dengan peringkat *cross-sectional* |
| `03_portfolio_ic.py` | Menghitung imbal hasil ke depan, *Information Coefficient*, dan pengembalian portofolio *long-short* kuintil |
| `04_visualize.py` | Menghasilkan semua grafik yang direferensikan dalam laporan ini |
| `05_robustness_check.py` | Analisis stabilitas sub-periode dan perkiraan biaya *turnover*/transaksi |

Semua nilai acak (*random seeds*) dibuat tetap jika memungkinkan (`RANDOM_SEED = 42`) untuk keterulangan penelitian. Eksekusi *universe* penuh mengunduh dan memproses 503 *ticker* selama ~11,5 tahun data harian; total *runtime* adalah sekitar 3–5 menit untuk mengunduh data, ditambah beberapa detik untuk setiap langkah proses selanjutnya.

---

*Catatan penulis: proyek ini dibangun sebagai bagian dari transisi dari latar belakang data science ke quantitative finance/equity research, dengan penekanan yang disengaja pada validasi statistik dan pelaporan jujur dari hasil nol atau tidak sesuai harapan, dibandingkan memaksakan grafik (curve-fitting) hanya untuk mendapatkan hasil imbal hasil yang memukau namun menipu.*
