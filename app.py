"""
app.py
======
Antarmuka Web Streamlit untuk Scraper & Analisis Publikasi Dosen (Google Scholar).
Desain modern, minimalis, palet warna hijau emerald, tanpa sidebar, dan tanpa emotikon.
"""

import os
import re
from datetime import datetime
from typing import Optional, Dict, Any, List

import pandas as pd
import plotly.express as px
import streamlit as st

from scraper_engine import (
    ScrapingJob,
    extract_author_id,
    OUTPUT_DIR,
    open_output_folder
)

# ==============================================================================
# 1. KONFIGURASI HALAMAN & GAYA VISUAL (CSS)
# ==============================================================================

st.set_page_config(
    page_title="Scraper Publikasi Dosen",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="collapsed"
)


def apply_custom_styles() -> None:
    """Menerapkan gaya visual kustom minimalis bertema hijau emerald tanpa sidebar."""
    st.markdown("""
    <style>
        /* Hilangkan Sidebar Bawaan Streamlit */
        [data-testid="stSidebar"], [data-testid="stSidebarNav"], [data-testid="collapsedControl"] {
            display: none !important;
            visibility: hidden !important;
        }

        /* Hilangkan Toolbar, Header, Menu, dan Deploy Button */
        #MainMenu, header, footer, .stDeployButton, [data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stHeader"] {
            visibility: hidden !important;
            display: none !important;
        }

        .block-container {
            padding-top: 1.5rem !important;
            padding-bottom: 2rem !important;
            max-width: 1200px !important;
            margin: 0 auto !important;
        }

        /* Tipografi & Header */
        .header-box {
            margin-bottom: 1.25rem;
            padding-bottom: 0.75rem;
            border-bottom: 1px solid #E2E8F0;
        }
        .main-title {
            font-size: 1.75rem;
            font-weight: 700;
            color: #065F46;
            letter-spacing: -0.02em;
            margin-bottom: 0.25rem;
        }
        .subtitle {
            font-size: 0.92rem;
            color: #64748B;
            margin-bottom: 0;
            line-height: 1.4;
        }

        /* Tombol Primer (Hijau) & Sekunder (Netral/Abu-abu) */
        button[kind="primary"] {
            background-color: #059669 !important;
            border-color: #059669 !important;
            color: #FFFFFF !important;
            font-weight: 600 !important;
            border-radius: 6px !important;
            transition: all 0.2s ease;
        }
        button[kind="primary"]:hover {
            background-color: #047857 !important;
            border-color: #047857 !important;
        }
        button[kind="primary"]:active {
            background-color: #065F46 !important;
        }
        button[kind="secondary"] {
            background-color: #F8FAFC !important;
            border: 1px solid #CBD5E1 !important;
            color: #475569 !important;
            font-weight: 600 !important;
            border-radius: 6px !important;
            transition: all 0.2s ease;
        }
        button[kind="secondary"]:hover {
            background-color: #F1F5F9 !important;
            border-color: #94A3B8 !important;
            color: #1E293B !important;
        }

        /* Progress Bar Hijau */
        div[data-testid="stProgress"] > div > div > div > div {
            background-color: #059669 !important;
        }

        /* Tab Navigasi Hijau */
        button[data-baseweb="tab"] {
            font-size: 0.95rem !important;
            font-weight: 500 !important;
            color: #64748B !important;
        }
        button[data-baseweb="tab"][aria-selected="true"] {
            color: #059669 !important;
            border-bottom-color: #059669 !important;
            font-weight: 600 !important;
        }

        /* Notifikasi Verifikasi CAPTCHA */
        .captcha-box {
            background-color: #FEF3C7;
            border: 1px solid #F59E0B;
            border-radius: 8px;
            padding: 14px 18px;
            margin-bottom: 16px;
        }
        .captcha-title {
            color: #92400E;
            font-weight: 600;
            margin-bottom: 4px;
            font-size: 0.92rem;
        }
        .captcha-desc {
            color: #B45309;
            font-size: 0.86rem;
            margin: 0;
            line-height: 1.4;
        }

        /* Footer Copyright */
        .footer-box {
            margin-top: 2.5rem;
            padding-top: 1.25rem;
            border-top: 1px solid #E2E8F0;
            text-align: center;
            font-size: 0.85rem;
            color: #94A3B8;
            font-weight: 500;
        }
        .footer-highlight {
            color: #059669;
            font-weight: 600;
        }
    </style>
    """, unsafe_allow_html=True)


def render_header() -> None:
    """Menampilkan header judul bersih aplikasi."""
    st.markdown("""
    <div class="header-box">
        <div class="main-title">Scraper Publikasi Dosen</div>
        <div class="subtitle">Ekstraksi data profil Google Scholar, klasifikasi Scopus & SINTA, serta analisis riwayat sitasi.</div>
    </div>
    """, unsafe_allow_html=True)


def init_session_state() -> None:
    """Menginisialisasi variabel session state Streamlit."""
    defaults = {
        'job': None,
        'selected_history_df': None,
        'active_dataset_name': "",
        'job_was_running': False
    }
    for key, default_val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_val


# ==============================================================================
# 2. TAB 1: SCRAPER PUBLIKASI
# ==============================================================================

def render_scraper_tab() -> None:
    """Merender tab formulir input dan monitor real-time scraping publikasi."""
    # Form Input
    with st.container():
        input_author = st.text_input(
            "ID Author atau URL Google Scholar",
            value="K_X8HzoAAAAJ",
            placeholder="Contoh: K_X8HzoAAAAJ atau link profil",
            help="Masukkan ID author atau URL profil lengkap Google Scholar."
        )

        col_y1, col_y2, col_lim = st.columns(3)
        with col_y1:
            start_year = st.number_input("Tahun Mulai", min_value=1990, max_value=2030, value=2023, step=1)
            speed_option = st.selectbox(
                "Kecepatan Scraping",
                options=[
                    "Santai / Aman (2.0 - 3.5 detik)",
                    "Standar (1.5 - 2.5 detik)",
                    "Cepat (0.8 - 1.5 detik)"
                ],
                index=0
            )
        with col_y2:
            end_year = st.number_input("Tahun Akhir", min_value=1990, max_value=2030, value=2026, step=1)
        with col_lim:
            max_pubs = st.number_input(
                "Batas Artikel (0 = Semua)",
                min_value=0,
                max_value=5000,
                value=0,
                step=5,
                help="Isi angka (misal 5 atau 10) untuk pengujian cepat."
            )

        if speed_option.startswith("Santai"):
            min_delay, max_delay = 2.0, 3.5
        elif speed_option.startswith("Standar"):
            min_delay, max_delay = 1.5, 2.5
        else:
            min_delay, max_delay = 0.8, 1.5

    job: Optional[ScrapingJob] = st.session_state.job
    is_running = bool(job and job.is_running)

    # Tombol Aksi Tunggal (Mulai / Berhenti)
    if not is_running:
        if st.button("Mulai", type="primary", use_container_width=True):
            if start_year > end_year:
                st.error("Tahun mulai tidak boleh lebih besar dari tahun akhir.")
            else:
                extracted_id = extract_author_id(input_author)
                new_job = ScrapingJob(
                    author_id=extracted_id,
                    start_year=int(start_year),
                    end_year=int(end_year),
                    headless=False,
                    min_delay=min_delay,
                    max_delay=max_delay,
                    max_pubs=int(max_pubs) if max_pubs > 0 else None
                )
                st.session_state.job = new_job
                st.session_state.job_was_running = True
                new_job.start()
                st.rerun()
    else:
        if st.button("Berhenti", type="secondary", use_container_width=True):
            if job:
                job.stop()
                st.session_state.job_was_running = False
                st.warning("Mengirim instruksi berhenti...")
                st.rerun()

    st.markdown("---")

    # Monitor Real-Time via Streamlit Fragment
    @st.fragment(run_every="1s" if is_running else None)
    def render_live_monitor() -> None:
        current_job: Optional[ScrapingJob] = st.session_state.job

        if not current_job:
            st.info("Masukkan ID Author dan tentukan parameter di atas, lalu klik Mulai.")
            return

        # Deteksi otomatis penyelesaian pekerjaan untuk sinkronisasi tombol
        if st.session_state.get('job_was_running', False) and not current_job.is_running:
            st.session_state.job_was_running = False
            st.rerun(scope="app")

        # Peringatan CAPTCHA (Bila muncul)
        if current_job.is_captcha:
            st.markdown("""
            <div class="captcha-box">
                <div class="captcha-title">Verifikasi Robot Terdeteksi di Google Chrome</div>
                <div class="captcha-desc">
                    Google meminta verifikasi CAPTCHA. Buka jendela Google Chrome di komputer Anda dan selesaikan verifikasi.
                    Sistem akan otomatis melanjutkan proses begitu verifikasi selesai.
                </div>
            </div>
            """, unsafe_allow_html=True)

        # Kartu Metrik Ringkas
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        with col_m1:
            status_text = "Berjalan" if current_job.is_running else ("Berhenti" if current_job.stop_requested else "Selesai")
            st.metric("Status", status_text)
        with col_m2:
            st.metric("Artikel Diproses", f"{current_job.current_idx} / {current_job.total_pubs or '-'}")
        with col_m3:
            st.metric("Data Tersimpan", len(current_job.records))
        with col_m4:
            range_key = 'Total Sitasi Periode'
            total_range_cites = sum(r.get(range_key, 0) for r in current_job.records if range_key in r)
            if total_range_cites == 0:
                range_key_alt = f"Total Sitasi ({current_job.start_year}-{current_job.end_year})"
                total_range_cites = sum(r.get(range_key_alt, 0) for r in current_job.records if range_key_alt in r)
            st.metric(f"Sitasi ({current_job.start_year}–{current_job.end_year})", total_range_cites)

        # Indikator Progres
        if current_job.total_pubs > 0:
            pct = min(1.0, current_job.current_idx / current_job.total_pubs)
            title_text = f" — {current_job.current_title[:55]}..." if current_job.current_title else ""
            st.progress(pct, text=f"{int(pct * 100)}% ({current_job.current_idx}/{current_job.total_pubs}){title_text}")
        elif current_job.is_running:
            st.progress(0.0, text=current_job.status or "Memulai proses...")

        # Log Aktivitas
        with st.expander(f"Log Aktivitas ({len(current_job.logs)})", expanded=current_job.is_running):
            log_text = "\n".join(current_job.logs[-50:]) if current_job.logs else "Belum ada aktivitas tercatat."
            st.text_area("Console", value=log_text, height=160, disabled=True, label_visibility="collapsed")

        # Preview Data & Aksi Berkas
        if current_job.records:
            author_display = getattr(current_job, 'author_name', current_job.author_id)
            filename_display = getattr(current_job, 'filename', f"scholar_{current_job.author_id}.xlsx")
            file_path_display = getattr(current_job, 'xlsx_file', f"{OUTPUT_DIR}/{filename_display}")

            st.markdown(f"#### Data Publikasi: {author_display}")
            st.caption(f"Lokasi berkas: `{file_path_display}`")
            df = pd.DataFrame(current_job.records)
            st.dataframe(df, use_container_width=True, height=320, hide_index=True)

            if st.button("Buka Hasil", type="primary", use_container_width=True, help="Buka folder hasil_scraping langsung di komputer Anda"):
                open_output_folder(OUTPUT_DIR)
                st.toast("Folder 'hasil_scraping' telah dibuka.")

    render_live_monitor()


# ==============================================================================
# 3. TAB 2: ANALISIS PUBLIKASI & SITASI
# ==============================================================================

def render_analytics_tab() -> None:
    """Merender tab visualisasi statistik dan grafik performa publikasi dosen."""
    st.markdown("### Statistik Publikasi & Sitasi")

    analytics_df = None
    analytics_source_name = ""

    if st.session_state.job and st.session_state.job.records:
        analytics_df = pd.DataFrame(st.session_state.job.records)
        analytics_source_name = f"Sesi Aktif ({st.session_state.job.author_id})"
    elif st.session_state.selected_history_df is not None:
        analytics_df = st.session_state.selected_history_df
        analytics_source_name = st.session_state.active_dataset_name

    if analytics_df is None or analytics_df.empty:
        st.info("Belum ada data untuk dianalisis. Silakan mulai proses di tab Publikasi atau pilih berkas di tab Riwayat Berkas.")
        return

    st.caption(f"Sumber: {analytics_source_name} ({len(analytics_df)} publikasi)")

    # Kolom sitasi per tahun
    year_cols = [c for c in analytics_df.columns if re.match(r'^Sitasi\s+\d{4}$', c)]
    year_cols = sorted(year_cols, key=lambda x: int(re.search(r'\d{4}', x).group(0)))

    # Kolom total periode & lifetime
    if 'Total Sitasi Periode' in analytics_df.columns:
        range_col = 'Total Sitasi Periode'
    else:
        range_cols = [c for c in analytics_df.columns if 'Total Sitasi (' in c]
        range_col = range_cols[0] if range_cols else None

    if 'Total Sitasi (All)' in analytics_df.columns:
        lifetime_col = 'Total Sitasi (All)'
    else:
        lifetime_col = 'Total Sitasi (Sepanjang Masa)' if 'Total Sitasi (Sepanjang Masa)' in analytics_df.columns else None

    title_col = 'Judul Publikasi' if 'Judul Publikasi' in analytics_df.columns else 'Judul'
    year_col = 'Tahun' if 'Tahun' in analytics_df.columns else ('Tahun Terbit' if 'Tahun Terbit' in analytics_df.columns else None)

    # Ringkasan KPI
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    with kpi1:
        st.metric("Total Publikasi", len(analytics_df))
    with kpi2:
        tot_range = int(analytics_df[range_col].sum()) if range_col else 0
        st.metric("Total Sitasi Periode", tot_range)
    with kpi3:
        tot_life = int(analytics_df[lifetime_col].sum()) if lifetime_col else 0
        st.metric("Total Sitasi Keseluruhan", tot_life)
    with kpi4:
        avg_cites = round(tot_range / len(analytics_df), 1) if len(analytics_df) > 0 else 0
        st.metric("Rata-rata Sitasi/Publikasi", avg_cites)

    st.markdown("---")

    # Komposisi Status Penulis & Jenis Jurnal
    if 'Status Penulis' in analytics_df.columns or 'Jenis Jurnal' in analytics_df.columns:
        col_akred1, col_akred2 = st.columns(2)
        with col_akred1:
            if 'Status Penulis' in analytics_df.columns:
                st.markdown("#### Peran Penulis")
                status_counts = analytics_df['Status Penulis'].value_counts().reset_index()
                status_counts.columns = ['Status Penulis', 'Jumlah']
                fig_status = px.pie(
                    status_counts,
                    names='Status Penulis',
                    values='Jumlah',
                    color='Status Penulis',
                    color_discrete_map={'Penulis Pertama': '#059669', 'Penulis Anggota': '#A7F3D0'},
                    hole=0.45
                )
                fig_status.update_layout(height=300, margin=dict(t=20, b=20, l=20, r=20))
                st.plotly_chart(fig_status, use_container_width=True)

        with col_akred2:
            if 'Jenis Jurnal' in analytics_df.columns:
                st.markdown("#### Jenis Publikasi")
                type_counts = analytics_df['Jenis Jurnal'].value_counts().reset_index()
                type_counts.columns = ['Jenis Jurnal', 'Jumlah']
                fig_type = px.pie(
                    type_counts,
                    names='Jenis Jurnal',
                    values='Jumlah',
                    color='Jenis Jurnal',
                    color_discrete_map={'Internasional': '#059669', 'Nasional': '#F59E0B'},
                    hole=0.45
                )
                fig_type.update_layout(height=300, margin=dict(t=20, b=20, l=20, r=20))
                st.plotly_chart(fig_type, use_container_width=True)

        st.markdown("---")

    # Visualisasi Tren Sitasi & Top Publikasi
    if year_cols:
        col_chart1, col_chart2 = st.columns([1, 1])
        with col_chart1:
            st.markdown("#### Pertumbuhan Sitasi per Tahun")
            yearly_sums = {int(re.search(r'\d{4}', c).group(0)): int(analytics_df[c].sum()) for c in year_cols}
            trend_df = pd.DataFrame(list(yearly_sums.items()), columns=['Tahun', 'Jumlah Sitasi'])
            fig_trend = px.bar(
                trend_df,
                x='Tahun',
                y='Jumlah Sitasi',
                text='Jumlah Sitasi',
                color='Jumlah Sitasi',
                color_continuous_scale='Greens'
            )
            fig_trend.update_traces(textposition='outside')
            fig_trend.update_layout(xaxis=dict(tickmode='linear'), height=350, margin=dict(t=20, b=20, l=20, r=20))
            st.plotly_chart(fig_trend, use_container_width=True)

        with col_chart2:
            st.markdown("#### Top 10 Publikasi Terbanyak Disitasi")
            sort_col = range_col or lifetime_col or year_cols[-1]
            top_df = analytics_df.sort_values(by=sort_col, ascending=False).head(10).copy()
            top_df['Judul_Short'] = top_df[title_col].apply(lambda x: str(x)[:40] + '...' if len(str(x)) > 40 else str(x))

            fig_top = px.bar(
                top_df,
                x=sort_col,
                y='Judul_Short',
                orientation='h',
                text=sort_col,
                color=sort_col,
                color_continuous_scale='Greens'
            )
            fig_top.update_layout(yaxis=dict(autorange="reversed"), height=350, margin=dict(t=20, b=20, l=20, r=20))
            st.plotly_chart(fig_top, use_container_width=True)

    # Distribusi Publikasi Berdasarkan Tahun Terbit
    if year_col and year_col in analytics_df.columns:
        st.markdown("#### Distribusi Publikasi per Tahun Terbit")
        pub_year_counts = analytics_df[year_col].value_counts().reset_index()
        pub_year_counts.columns = [year_col, 'Jumlah Publikasi']
        pub_year_counts = pub_year_counts[pub_year_counts[year_col] != '-']
        pub_year_counts[year_col] = pd.to_numeric(pub_year_counts[year_col], errors='coerce')
        pub_year_counts = pub_year_counts.dropna().sort_values(by=year_col)

        fig_dist = px.line(
            pub_year_counts,
            x=year_col,
            y='Jumlah Publikasi',
            markers=True
        )
        fig_dist.update_traces(line_color='#059669')
        fig_dist.update_layout(height=300, margin=dict(t=20, b=20, l=20, r=20))
        st.plotly_chart(fig_dist, use_container_width=True)


# ==============================================================================
# 4. TAB 3: RIWAYAT BERKAS TERSIMPAN
# ==============================================================================

def render_history_tab() -> None:
    """Merender tab daftar berkas hasil scraping tersimpan dan pratinjau."""
    col_h_head, col_h_act = st.columns([3, 1])
    with col_h_head:
        st.markdown("### Riwayat Berkas")
        st.write("Daftar berkas Excel hasil scraping yang tersimpan di direktori `hasil_scraping/`:")
    with col_h_act:
        if st.button("Buka Hasil", key="btn_open_folder_tab3", use_container_width=True, help="Buka folder hasil_scraping langsung di komputer Anda"):
            open_output_folder(OUTPUT_DIR)
            st.toast("Folder 'hasil_scraping' telah dibuka.")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    found_files: Dict[str, str] = {}
    if os.path.exists(OUTPUT_DIR):
        for f in os.listdir(OUTPUT_DIR):
            if f.endswith('.xlsx') and not f.startswith('~$'):
                found_files[f] = os.path.join(OUTPUT_DIR, f)
    if os.path.exists("hasil_sitasi"):
        for f in os.listdir("hasil_sitasi"):
            if f.endswith('.xlsx') and not f.startswith('~$') and f not in found_files:
                found_files[f] = os.path.join("hasil_sitasi", f)

    if not found_files:
        st.info("Belum ditemukan berkas di folder hasil_scraping.")
        return

    file_details: List[Dict[str, Any]] = []
    for f_name, full_path in found_files.items():
        stat = os.stat(full_path)
        mod_time = datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
        size_kb = round(stat.st_size / 1024, 1)
        file_details.append({
            'Nama Berkas': f_name,
            'Ukuran': f"{size_kb} KB",
            'Terakhir Dimodifikasi': mod_time,
            'path': full_path
        })

    file_details.sort(key=lambda x: x['Terakhir Dimodifikasi'], reverse=True)
    history_meta_df = pd.DataFrame(file_details)
    st.dataframe(history_meta_df[['Nama Berkas', 'Ukuran', 'Terakhir Dimodifikasi']], use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown("#### Pratinjau Berkas")

    selected_file = st.selectbox(
        "Pilih berkas Excel:",
        options=[d['Nama Berkas'] for d in file_details]
    )

    if selected_file:
        chosen_item = next(d for d in file_details if d['Nama Berkas'] == selected_file)
        target_path = chosen_item['path']
        try:
            preview_df = pd.read_excel(target_path)
            st.write(f"Menampilkan isi **{selected_file}** ({len(preview_df)} publikasi):")
            st.dataframe(preview_df, use_container_width=True, height=280, hide_index=True)

            if st.button("Buka di Tab Analisis", use_container_width=True):
                st.session_state.selected_history_df = preview_df
                st.session_state.active_dataset_name = selected_file
                st.success(f"Berkas '{selected_file}' berhasil dimuat ke Tab Analisis.")

        except Exception as ex:
            st.error(f"Gagal memuat berkas {selected_file}: {ex}")


def render_footer() -> None:
    """Menampilkan footer copyright aplikasi."""
    st.markdown("""
    <div class="footer-box">
        Ikhlas Beramal by <span class="footer-highlight">@ilyasbp</span>
    </div>
    """, unsafe_allow_html=True)


# ==============================================================================
# 5. TITIK MASUK UTAMA APLIKASI
# ==============================================================================

def main() -> None:
    """Fungsi utama bootstrap antarmuka aplikasi Streamlit."""
    init_session_state()
    apply_custom_styles()
    render_header()

    tab_scraper, tab_analytics, tab_history = st.tabs([
        "Publikasi",
        "Analisis",
        "Riwayat Berkas"
    ])

    with tab_scraper:
        render_scraper_tab()

    with tab_analytics:
        render_analytics_tab()

    with tab_history:
        render_history_tab()

    render_footer()


if __name__ == "__main__":
    main()
