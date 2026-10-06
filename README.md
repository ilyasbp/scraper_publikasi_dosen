# Scraper Publikasi Dosen (Google Scholar & SCImagoJR)

Aplikasi web berbasis **Streamlit** dan **Selenium** untuk mengekstrak data profil Google Scholar, meliputi riwayat publikasi, status penulis, klasifikasi jurnal (nasional/internasional), publisher, indeksasi (Scopus Q1–Q4 & SINTA 1–6), tanggal terbit, serta rincian sitasi tahunan ke dalam format **Excel (.xlsx)** di folder **`hasil_scraping/`**.

> Buka berkas [**tutorial_penggunaan.html**](tutorial_penggunaan.html) di browser untuk petunjuk langkah demi langkah.

---

## Fitur Utama

1. **Ekstraksi Data Publikasi:**
   - Input Author ID atau URL profil Google Scholar.
   - Penentuan rentang tahun publikasi dan sitasi.
   - Opsi batas jumlah publikasi untuk pengujian cepat.
   - Pemantauan progres, metrik artikel dan sitasi, serta log aktivitas.
   - Tombol Mulai/Berhenti untuk mengontrol proses.

2. **Klasifikasi Akreditasi & Indeksasi:**
   - **Database SCImagoJR**: Kuartil Scopus (Q1–Q4 dan prosiding) dicocokkan secara lokal.
   - **Auto-Detect Versi Database**: Otomatis mendeteksi berkas database terbaru di folder `data/` (misalnya `scimagojr 2026.csv`).
   - **Pencarian SINTA**: Jurnal nasional dicari ke portal SINTA untuk akreditasi SINTA 1–6.
   - **Deteksi Publisher**: Mengidentifikasi penerbit jurnal/prosiding (Elsevier, Springer, IEEE, ACM, dll.).

3. **Dukungan Verifikasi CAPTCHA:**
   - Menggunakan mode Chrome tampak (*visible*) secara default.
   - Jika Google menampilkan verifikasi robot (CAPTCHA), dashboard akan menampilkan notifikasi. Cukup selesaikan verifikasi di jendela Chrome, dan proses akan berlanjut secara otomatis.

4. **Visualisasi & Analisis Data:**
   - Komposisi peran penulis (penulis pertama vs anggota).
   - Sebaran jenis publikasi (nasional vs internasional).
   - Tren pertumbuhan sitasi tahunan.
   - Top 10 publikasi dengan sitasi terbanyak.
   - Distribusi publikasi berdasarkan tahun terbit.

5. **Format Penyimpanan Excel:**
   - Berkas otomatis tersimpan di folder `hasil_scraping/` dalam format `.xlsx`.
   - Penamaan berkas otomatis berdasarkan nama author dan rentang tahun (contoh: `scholar_Budi_2023_2026.xlsx`).
   - Struktur kolom:
     `No` | `Judul Publikasi` | `Penulis (Authors)` | `Status Penulis` | `Nama Jurnal / Prosiding` | `Publisher` | `Jenis Jurnal` | `Terindeks` | `Tanggal Terbit` | `Tahun` | `Vol/No/Hal` | `Sitasi [Tahun]...` | `Total Sitasi Periode` | `Total Sitasi (All)` | `Link Artikel`

6. **Fitur Resume (Checkpoint):**
   - Jika proses terhenti, menjalankan ulang untuk author dan tahun yang sama akan otomatis melanjutkan dari artikel yang belum tersimpan.

---

## Cara Menjalankan Aplikasi

### Cara 1: Peluncur Langsung (Double-Click)
Script peluncur otomatis mendeteksi dan mengunduh Google Chrome, Python 3, serta dependensi pustaka yang dibutuhkan jika belum terpasang di komputer:
- **Di Mac:** Klik 2x berkas `run_mac.command`
- **Di Windows:** Klik 2x berkas `run_windows.bat`

### Cara 2: Lewat Terminal / Command Prompt
- **Di Mac / Linux:** `./run.sh`
- **Di Windows:** `run_windows.bat`

Aplikasi akan otomatis terbuka di browser pada alamat:
`http://localhost:8501`

---

## Struktur File Project

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
├── tutorial_penggunaan.html   # Panduan penggunaan
└── README.md                  # Dokumentasi project
```

---

<div align="center">

**Ikhlas Beramal by [@ilyasbp](https://github.com/ilyasbp/scraper_publikasi_dosen)**

</div>
