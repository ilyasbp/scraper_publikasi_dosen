# Scraper & Pengunduh Artikel Ilmiah

Aplikasi web berbasis **Streamlit** dan **Selenium** untuk ekstraksi data publikasi Google Scholar, klasifikasi akreditasi Scopus (Q1–Q4) & SINTA (1–6), analisis riwayat sitasi, serta **pengunduh otomatis berkas PDF artikel ilmiah berbasis DOI** secara hybrid melalui Open Access (Unpaywall) dan multi-mirror Sci-Hub.

> Buka berkas [**tutorial_penggunaan.html**](tutorial_penggunaan.html) di browser untuk petunjuk langkah demi langkah.

---

## Fitur Utama

1. **Ekstraksi Data Publikasi Google Scholar:**
   - Input Author ID atau URL profil Google Scholar.
   - **Batch ID Scraping**: Mendukung banyak ID profil sekaligus.
   - Penentuan rentang tahun publikasi dan sitasi.
   - Ekstraksi DOI otomatis dengan verifikasi kemiripan Crossref API (95%).
   - Struktur berkas Excel terstandarisasi dengan nama profil rapi (*Title Case*) dan tautan DOI lengkap (`https://doi.org/...`).

2. **Klasifikasi Akreditasi & Indeksasi:**
   - **Database SCImagoJR**: Kuartil Scopus (Q1–Q4) dicocokkan secara lokal.
   - **Pencarian SINTA**: Jurnal nasional dicari ke portal SINTA untuk akreditasi SINTA 1–6.
   - **Deteksi Publisher & Buku**: Mengidentifikasi penerbit dan mendeteksi kategori buku/prosiding/jurnal.

3. **Pengunduh Artikel Ilmiah Berbasis DOI (Tab 'Unduh Artikel'):**
   - **Input Fleksibel**: Mendukung unggah dokumen (**Excel, Word, PDF, TXT, CSV**) atau tempel teks daftar DOI langsung.
   - **Deteksi Otomatis**: Memindai dan mengekstrak seluruh DOI unik secara otomatis.
   - **Strategi Unduh Hybrid**:
     - *Tingkat 1*: Cek akses legal **Open Access (Unpaywall API)** untuk unduhan langsung tanpa blokir.
     - *Tingkat 2*: *Fallback* ke jaringan **Sci-Hub Multi-Mirror** (`.ru`, `.su`, `.st`, `.red`, `.box`).
   - **Penyimpanan Terstruktur**: Disimpan di folder `artikel/{nama_dokumen}/` dengan nama berkas sesuai judul artikel.
   - **Aksi Cepat**: Dilengkapi tombol *Buka Folder Artikel* dan *Unduh Semua PDF (.zip)*.

4. **Visualisasi & Analisis Sitasi:**
   - Komposisi kategori publikasi (8 kategori baku).
   - Tren pertumbuhan sitasi tahunan per dosen atau gabungan.
   - Ekspor berkas gabungan multi-profil dalam satu file Excel.

5. **Format Penyimpanan Excel:**
   - Berkas otomatis tersimpan di folder `hasil_scraping/` dalam format `.xlsx`.
   - Penamaan berkas otomatis menggunakan huruf kecil berdasarkan nama author dan rentang tahun (contoh: `budi_2023_2026.xlsx`).
   - Struktur kolom:
     `No` | `Profil Dosen` | `Judul Publikasi` | `Penulis (Authors)` | `Status Penulis` | `Nama Jurnal / Prosiding` | `Publisher` | `Jenis Jurnal` | `Terindeks` | `Kategori Publikasi` | `Tanggal Terbit` | `Tahun` | `Vol/No/Hal` | `Sitasi [Tahun]...` | `Total Sitasi Periode` | `Total Sitasi (All)` | `Link Artikel` | `DOI`

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
