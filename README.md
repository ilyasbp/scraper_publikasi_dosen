# 🎓 Scraper Publikasi Dosen & Akreditasi (Scholar + SCImagoJR)

Aplikasi web lokal interaktif berbasis **Streamlit** dan **Selenium** untuk mengekstrak data profil author Google Scholar secara instan, mencakup seluruh riwayat publikasi, metadata akreditasi (jurnal nasional/internasional, publisher resmi, indeksasi SINTA 1-6 & Scopus Q1-Q4 via database resmi SCImagoJR, tanggal terbit lengkap DD/MM/YYYY, volume/edisi/halaman), dan rincian sitasi tahunan langsung ke dalam berkas **Excel (.xlsx)** secara otomatis di folder **`hasil_scraping/`**.

> 📖 **Panduan Penggunaan:** Buka berkas [**tutorial_penggunaan.html**](tutorial_penggunaan.html) di browser Anda untuk petunjuk langkah demi langkah.

---

## ✨ Fitur Utama

1. **🚀 Scraper Interaktif & Real-Time:**
   - Cukup masukkan **Google Scholar Author ID** (contoh: `K_X8HzoAAAAJ`).
   - Tentukan rentang tahun (misal: `2023` hingga `2026`).
   - Opsi batas maksimal publikasi untuk uji coba cepat (misal: hanya 5 atau 10 artikel).
   - Pemantauan real-time: status scraper, progress bar, metrik publikasi & sitasi, dan live log terminal.
   - Tombol **Hentikan Proses (Stop)** yang aman menyimpan data yang sudah terkumpul.

2. **⚡ Integrasi Database SCImagoJR (100% Otomatis):**
   - **Database SCImagoJR (32.000+ Jurnal)**: Kuartil resmi Scopus (**`Scopus Q1`**, **`Scopus Q2`**, **`Scopus Q3`**, **`Scopus Q4`**, **`Prosiding Internasional (Scopus)`**) dicocokkan otomatis secara lokal dan instan (< 0.001 detik).
   - **Auto-Detect Versi Terbaru**: Sistem otomatis mendeteksi berkas database terbaru di folder `data/` (misalnya jika Anda menambahkan `scimagojr 2026.csv`, sistem akan otomatis memprioritaskan versi 2026 tanpa ubah kode).
   - **Auto-Lookup SINTA Jurnal Nasional**: Jurnal nasional otomatis dicari ke portal resmi SINTA Kemdiktisaintek untuk mendapatkan status akreditasi resmi (**`SINTA 1`** s/d **`SINTA 6`**).
   - **Ekstraksi Publisher Otomatis**: Dilengkapi kolom **`Publisher`** di sebelah kanan nama jurnal/prosiding (Elsevier, Springer, IEEE, Nature, ACM, dll.).

3. **🛡️ Penanganan CAPTCHA Google Otomatis:**
   - Menggunakan mode Chrome tampak (*visible*) secara default.
   - Jika Google mendeteksi bot dan memunculkan CAPTCHA (*"I am not a robot"*), aplikasi menampilkan peringatan animasi di layar dashboard.
   - Anda cukup menyelesaikan centang di jendela Chrome, dan scraper akan **otomatis melanjutkan proses** tanpa kehilangan data.

4. **📊 Analitik & Visualisasi Interaktif (Plotly):**
   - Komposisi peran penulis (Penulis Pertama vs Anggota).
   - Sebaran jenis publikasi (Nasional vs Internasional).
   - Tren pertumbuhan sitasi tahunan (grafik batang).
   - Top 10 publikasi dengan sitasi terbanyak.
   - Grafik produktivitas publikasi berdasarkan tahun terbit.

5. **📁 Folder Khusus & Format Excel Standar Akreditasi (`hasil_scraping/`):**
   - File otomatis disimpan ke dalam folder khusus **`hasil_scraping/`** agar folder utama tetap bersih.
   - Output eksklusif spreadsheet **`.xlsx` (Microsoft Excel)** tanpa file CSV.
   - Penamaan otomatis menggunakan **Nama Depan Author** (contoh: `scholar_Budi_2023_2026.xlsx`).
   - **Struktur Kolom Lengkap Standar Akreditasi:**
     `No` | `Judul Publikasi` | `Penulis (Authors)` | `Status Penulis` | `Nama Jurnal / Prosiding` | `Publisher` | `Jenis Jurnal` | `Terindeks` | `Tanggal Terbit` | `Tahun` | `Vol/No/Hal` | `Sitasi 2023...` | `Total Sitasi Periode` | `Total Sitasi (All)` | `Link Artikel`

5. **⚡ Fitur Lanjutkan (Resume Checkpoint):**
   - Jika proses pernah terhenti atau ditutup, saat Anda menjalankan ulang untuk author dan tahun yang sama, scraper akan otomatis mendeteksi file lama dan melewati artikel yang sudah tersimpan sebelumnya.

---

## 🚀 Cara Menjalankan Aplikasi

### Cara 1: Cukup Klik Dua Kali (Rekomendasi)
Tidak perlu menjalankan perintah di terminal. Script peluncur otomatis mendeteksi dan mengunduh Google Chrome, Python 3, serta semua pustaka yang dibutuhkan jika belum terpasang di komputer:
- **Di Mac:** Cukup klik 2x berkas `run_mac.command`
- **Di Windows:** Cukup klik 2x berkas `run_windows.bat`

### Cara 2: Lewat Terminal / Command Prompt
- **Di Mac / Linux:** `./run.sh`
- **Di Windows:** `run_windows.bat`

Aplikasi akan otomatis terbuka di browser Anda pada alamat:
👉 **`http://localhost:8501`**

---

## 📦 Struktur File Project

```
Google Scholar Scrapper/
├── hasil_scraping/            # Folder penyimpanan file Excel (.xlsx)
├── data/
│   └── scimagojr 2025.csv     # Database offline SCImagoJR 2025
├── app.py                     # Antarmuka Web Dashboard (Streamlit)
├── scraper_engine.py          # Modul mesin ekstraksi & klasifikasi akreditasi
├── run_mac.command            # Launcher double-click macOS
├── run_windows.bat            # Launcher double-click Windows
├── run.sh                     # Launcher bash satu klik
├── requirements.txt           # Daftar pustaka Python
├── tutorial_penggunaan.html   # Panduan interaktif visual
└── README.md                  # Dokumentasi ringkas project
```

---

<div align="center">

**Ikhlas Beramal by [@ilyasbp](https://github.com/ilyasbp/scraper_publikasi_dosen)**

</div>
