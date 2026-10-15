"""
app.py
======
Antarmuka Web Streamlit untuk Scraper & Analisis Publikasi Dosen (Google Scholar).
Desain modern, minimalis, palet warna hijau emerald, tanpa sidebar, dan tanpa emotikon.
"""

import html
import io
import os
import re
import zipfile
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple

import pandas as pd
import plotly.express as px
import streamlit as st

from scraper_engine import (
    ScrapingJob,
    extract_author_id,
    OUTPUT_DIR,
    open_output_folder,
    PUBLICATION_CATEGORIES,
    classify_publication_category,
    standardize_author_name,
    clean_doi
)

from article_downloader import (
    ARTIKEL_DIR,
    DEFAULT_SCIHUB_MIRRORS,
    extract_dois_from_text,
    extract_dois_from_file,
    ArticleDownloaderJob,
    sanitize_filename
)

# ==============================================================================
# 1. KONFIGURASI HALAMAN & GAYA VISUAL (CSS)
# ==============================================================================

st.set_page_config(
    page_title="Scraper & Pengunduh Artikel Ilmiah",
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
        .footer-box a {
            color: #059669 !important;
            font-weight: 600 !important;
            text-decoration: none !important;
            transition: color 0.2s ease;
        }
        .footer-box a:hover {
            color: #047857 !important;
            text-decoration: underline !important;
        }
    </style>
    """, unsafe_allow_html=True)


def render_header() -> None:
    """Menampilkan header judul bersih aplikasi."""
    st.markdown("""
    <div class="header-box">
        <div class="main-title">Scraper & Pengunduh Artikel Ilmiah</div>
        <div class="subtitle">Ekstraksi publikasi Google Scholar, klasifikasi Scopus & SINTA, analisis sitasi, dan pengunduh PDF artikel via DOI.</div>
    </div>
    """, unsafe_allow_html=True)


def init_session_state() -> None:
    """Menginisialisasi variabel session state Streamlit."""
    defaults = {
        'job': None,
        'selected_history_df': None,
        'active_dataset_name': "",
        'job_was_running': False,
        'author_items': [{'id': 0, 'value': "K_X8HzoAAAAJ"}],
        'next_author_id': 1,
        'dl_job': None,
        'dl_was_running': False,
        'dl_extracted_dois': [],
        'dl_subfolder_name': ""
    }
    for key, default_val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_val


# ==============================================================================
# 2. TAB 1: SCRAPER PUBLIKASI
# ==============================================================================

def render_scraper_tab() -> None:
    """Merender tab formulir input dan monitor real-time scraping publikasi."""
    job: Optional[ScrapingJob] = st.session_state.job
    # Job dianggap aktif hanya jika thread berjalan dan tidak sedang diminta berhenti
    is_running = bool(job and job.is_running and not job.stop_requested)

    # Form Input
    with st.container():
        st.markdown("<label style='font-size: 0.95rem; font-weight: 600; color: #1E293B; margin-bottom: 6px; display: inline-block;'>ID Author atau URL Google Scholar</label>", unsafe_allow_html=True)

        if not st.session_state.get('author_items'):
            st.session_state.author_items = [{'id': 0, 'value': "K_X8HzoAAAAJ"}]
            st.session_state.next_author_id = 1

        is_multiple = len(st.session_state.author_items) > 1

        for i, item in enumerate(st.session_state.author_items):
            if is_multiple:
                c_num, c_field, c_del = st.columns([0.6, 8.4, 1.0])
                with c_num:
                    st.markdown(f"<div style='padding-top: 10px; font-weight: 600; color: #065F46;'>#{i+1}</div>", unsafe_allow_html=True)
                with c_field:
                    val = st.text_input(
                        f"ID Author / URL #{i+1}",
                        value=item.get('value', ''),
                        key=f"author_input_{item['id']}",
                        placeholder=f"Contoh ID atau URL profil dosen ke-{i+1}...",
                        disabled=is_running,
                        label_visibility="collapsed"
                    )
                    item['value'] = val
                with c_del:
                    if st.button("✕", key=f"btn_del_{item['id']}", disabled=is_running, help=f"Hapus slot dosen #{i+1}"):
                        st.session_state.author_items = [it for it in st.session_state.author_items if it['id'] != item['id']]
                        if not st.session_state.author_items:
                            st.session_state.author_items = [{'id': st.session_state.next_author_id, 'value': ''}]
                            st.session_state.next_author_id += 1
                        st.rerun()
            else:
                val = st.text_input(
                    "ID Author atau URL Google Scholar",
                    value=item.get('value', ''),
                    key=f"author_input_{item['id']}",
                    placeholder="Contoh: K_X8HzoAAAAJ atau link profil",
                    help="Masukkan ID author atau URL profil lengkap Google Scholar.",
                    disabled=is_running,
                    label_visibility="collapsed"
                )
                item['value'] = val

        # Tombol Tambah ID
        if st.button("+ Tambah ID / URL", disabled=is_running, help="Tambah slot profil dosen lain untuk scraping batch"):
            st.session_state.author_items.append({'id': st.session_state.next_author_id, 'value': ''})
            st.session_state.next_author_id += 1
            st.rerun()

        st.markdown("<div style='margin-bottom: 0.6rem;'></div>", unsafe_allow_html=True)

        col_y1, col_y2, col_lim = st.columns(3)
        with col_y1:
            start_year = st.number_input("Tahun Mulai", min_value=1990, max_value=2030, value=2023, step=1, disabled=is_running)
            speed_option = st.selectbox(
                "Jeda Scrapping",
                options=[
                    "Santai / Aman (2.0 - 3.5 detik)",
                    "Standar (1.5 - 2.5 detik)",
                    "Cepat (0.8 - 1.5 detik)"
                ],
                index=0,
                disabled=is_running
            )
        with col_y2:
            end_year = st.number_input("Tahun Akhir", min_value=1990, max_value=2030, value=2026, step=1, disabled=is_running)
        with col_lim:
            max_pubs = st.number_input(
                "Batas Artikel per Dosen (0 = Semua)",
                min_value=0,
                max_value=5000,
                value=0,
                step=5,
                help="Isi angka (misal 5 atau 10) untuk pengujian cepat per profil dosen.",
                disabled=is_running
            )

        if speed_option.startswith("Santai"):
            min_delay, max_delay = 2.0, 3.5
        elif speed_option.startswith("Standar"):
            min_delay, max_delay = 1.5, 2.5
        else:
            min_delay, max_delay = 0.8, 1.5

    # Tombol Aksi Tunggal (Mulai / Berhenti)
    if not is_running:
        active_inputs = [it.get('value', '').strip() for it in st.session_state.author_items if it.get('value', '').strip()]
        btn_label = f"Mulai Scraping Batch ({len(active_inputs)} Dosen)" if len(active_inputs) > 1 else "Mulai"
        if st.button(btn_label, type="primary", use_container_width=True):
            if start_year > end_year:
                st.error("Tahun mulai tidak boleh lebih besar dari tahun akhir.")
            else:
                gathered_ids = []
                for it in st.session_state.author_items:
                    raw_val = it.get('value', '').strip()
                    if not raw_val:
                        continue
                    for token in raw_val.replace(',', '\n').split('\n'):
                        clean = token.strip()
                        if clean:
                            aid = extract_author_id(clean)
                            if aid and aid not in gathered_ids:
                                gathered_ids.append(aid)

                if not gathered_ids:
                    st.error("Silakan masukkan minimal 1 ID Author atau URL Google Scholar yang valid.")
                else:
                    # Pastikan job sebelumnya berhenti sepenuhnya jika masih ada
                    if job and job.thread and job.thread.is_alive():
                        job.stop(wait=True, timeout=2.5)
                        job.is_running = False

                    new_job = ScrapingJob(
                        author_id=gathered_ids if len(gathered_ids) > 1 else gathered_ids[0],
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
                job.stop(wait=False)
                st.session_state.job_was_running = False
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
        if st.session_state.get('job_was_running', False) and (not current_job.is_running or current_job.stop_requested):
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

        is_batch = getattr(current_job, 'is_batch', False)

        # Kartu Metrik Ringkas
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        with col_m1:
            if current_job.stop_requested:
                status_text = "Berhenti"
            elif current_job.is_running:
                status_text = "Berjalan"
            else:
                status_text = "Selesai"
            st.metric("Status", status_text)
        with col_m2:
            if is_batch:
                st.metric("Dosen Diproses", f"{current_job.current_author_idx} / {current_job.total_authors}")
            else:
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
        if is_batch and current_job.total_authors > 0:
            a_done = max(0, current_job.current_author_idx - 1)
            pub_pct = (current_job.current_idx / max(1, current_job.total_pubs)) if current_job.total_pubs > 0 else 0
            total_pct = min(1.0, max(0.0, (a_done + pub_pct) / current_job.total_authors))
            curr_author_tag = getattr(current_job.active_scraper, 'author_name', current_job.author_id)
            title_snippet = f" — {current_job.current_title[:38]}..." if current_job.current_title else ""
            bar_text = f"{int(total_pct * 100)}% — Dosen {current_job.current_author_idx}/{current_job.total_authors} ({curr_author_tag}) | Artikel {current_job.current_idx}/{current_job.total_pubs or '-'}{title_snippet}"
            st.progress(total_pct, text=bar_text)
        elif current_job.total_pubs > 0:
            pct = min(1.0, current_job.current_idx / current_job.total_pubs)
            title_text = f" — {current_job.current_title[:55]}..." if current_job.current_title else ""
            st.progress(pct, text=f"{int(pct * 100)}% ({current_job.current_idx}/{current_job.total_pubs}){title_text}")
        elif current_job.is_running and not current_job.stop_requested:
            st.progress(0.0, text=current_job.status or "Memulai proses...")

        # Log Aktivitas
        with st.expander(f"Log Aktivitas ({len(current_job.logs)})", expanded=bool(current_job.is_running and not current_job.stop_requested)):
            log_text = "\n".join(current_job.logs[-80:]) if current_job.logs else "Belum ada aktivitas tercatat."
            st.text_area("Console", value=log_text, height=160, disabled=True, label_visibility="collapsed")
            st.components.v1.html(
                """
                <script>
                function scrollLogToBottom() {
                    try {
                        const doc = window.parent.document;
                        const textareas = doc.querySelectorAll('textarea');
                        textareas.forEach(t => {
                            t.scrollTop = t.scrollHeight;
                        });
                    } catch (e) {}
                }
                scrollLogToBottom();
                setTimeout(scrollLogToBottom, 50);
                setTimeout(scrollLogToBottom, 150);
                </script>
                """,
                height=0,
                width=0
            )

        # Preview Data & Aksi Berkas
        if current_job.records:
            if is_batch:
                # Mode Batch (Selalu Berkas Terpisah per Dosen)
                st.markdown(f"#### Hasil Scraping Batch ({len(current_job.batch_results)} Dosen — Berkas Terpisah)")
                summary_data = []
                for b in current_job.batch_results:
                    summary_data.append({
                        'No': b['index'],
                        'Nama Dosen': b['author_name'],
                        'ID Scholar': b['author_id'],
                        'Jumlah Artikel': b['total_pubs'],
                        'Nama Berkas': b['filename']
                    })
                if summary_data:
                    st.dataframe(pd.DataFrame(summary_data), use_container_width=True, hide_index=True)

                if current_job.batch_results:
                    author_names = [b['author_name'] for b in current_job.batch_results]
                    sel_author = st.selectbox("Pilih Dosen untuk Pratinjau Publikasi:", options=author_names)
                    sel_item = next((b for b in current_job.batch_results if b['author_name'] == sel_author), None)
                    if sel_item and sel_item.get('records'):
                        st.caption(f"Lokasi berkas: `{sel_item.get('xlsx_file')}`")
                        st.dataframe(pd.DataFrame(sel_item['records']), use_container_width=True, height=280, hide_index=True)

                if st.button("Buka Hasil", key="btn_open_batch_sep", use_container_width=True):
                    open_output_folder(OUTPUT_DIR)
                    st.toast("Folder 'hasil_scraping' telah dibuka.")

            else:
                # Mode Profil Tunggal
                author_display = getattr(current_job, 'author_name', current_job.author_id)
                fallback_name = f"{current_job.author_id}_{current_job.start_year}_{current_job.end_year}.xlsx".lower()
                filename_display = getattr(current_job, 'filename', fallback_name)
                file_path_display = getattr(current_job, 'xlsx_file', f"{OUTPUT_DIR}/{filename_display}")

                st.markdown(f"#### Data Publikasi: {author_display}")
                st.caption(f"Lokasi berkas: `{file_path_display}`")
                df = pd.DataFrame(current_job.records)
                st.dataframe(df, use_container_width=True, height=320, hide_index=True)

                if st.button("Buka Hasil", key="btn_open_single", use_container_width=True):
                    open_output_folder(OUTPUT_DIR)
                    st.toast("Folder 'hasil_scraping' telah dibuka.")

    render_live_monitor()


# ==============================================================================
# 3. TAB 2: ANALISIS PUBLIKASI & SITASI
# ==============================================================================

# Palet warna visual untuk 8 kategori baku publikasi
CATEGORY_COLORS: Dict[str, str] = {
    'Jurnal Nasional': '#10B981',                           # emerald
    'Jurnal Nasional Terakreditasi (Sinta)': '#047857',     # dark emerald
    'Jurnal Internasional': '#38BDF8',                      # light blue
    'Jurnal Internasional Bereputasi (Scopus)': '#1D4ED8',  # royal blue
    'Seminar Nasional': '#F59E0B',                          # amber
    'Seminar Internasional': '#D97706',                      # dark amber / orange
    'Buku': '#8B5CF6',                                      # purple
    'Paten': '#EC4899',                                     # rose
}


def build_summary_table(df: pd.DataFrame, years: List[int]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Menyusun matriks tabel standar akreditasi dan dataframe numerik untuk chart."""
    matrix = {cat: {y: 0 for y in years} for cat in PUBLICATION_CATEGORIES}

    for _, row in df.iterrows():
        cat = row.get('Kategori Publikasi')
        if cat not in matrix:
            cat = classify_publication_category(row)
        y = row.get('Clean_Year')
        if pd.notna(y) and int(y) in matrix.get(cat, {}):
            matrix[cat][int(y)] += 1

    display_rows = []
    numeric_rows = []
    col_totals = {y: 0 for y in years}
    grand_total = 0

    for cat in PUBLICATION_CATEGORIES:
        display_dict = {'Jenis Publikasi': cat}
        numeric_dict = {'Jenis Publikasi': cat}
        row_total = 0
        for y in years:
            val = matrix[cat][y]
            row_total += val
            col_totals[y] += val
            display_dict[str(y)] = val if val > 0 else '-'
            numeric_dict[str(y)] = val
        display_dict['Total'] = row_total
        numeric_dict['Total'] = row_total
        grand_total += row_total
        display_rows.append(display_dict)
        numeric_rows.append(numeric_dict)

    # Baris Total di baris paling bawah
    total_display_dict = {'Jenis Publikasi': 'Total'}
    total_numeric_dict = {'Jenis Publikasi': 'Total'}
    for y in years:
        total_display_dict[str(y)] = col_totals[y]
        total_numeric_dict[str(y)] = col_totals[y]
    total_display_dict['Total'] = grand_total
    total_numeric_dict['Total'] = grand_total
    display_rows.append(total_display_dict)
    numeric_rows.append(total_numeric_dict)

    return pd.DataFrame(display_rows), pd.DataFrame(numeric_rows)


def render_analytics_tab() -> None:
    """Merender tab analisis publikasi & sitasi dari berkas Excel di folder hasil dengan dukungan multi-file dan visualisasi rapi."""
    col_a_head, col_a_act = st.columns([2.7, 1.3])
    with col_a_head:
        st.markdown("### Analisis Publikasi & Sitasi")
        st.write("Analisis publikasi dosen langsung dari berkas Excel di folder hasil scraping. Anda dapat memilih beberapa berkas sekaligus.")
    with col_a_act:
        if st.button("Buka Folder Hasil", key="btn_open_folder_analytics", use_container_width=True, help="Buka folder hasil_scraping langsung di komputer"):
            open_output_folder(OUTPUT_DIR)
            st.toast("Folder 'hasil_scraping' telah dibuka.")
        btn_download_excel_placeholder = st.empty()

    # 1. Pindai seluruh berkas Excel di folder hasil
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

    file_items: List[Dict[str, Any]] = []
    for f_name, full_path in found_files.items():
        try:
            stat = os.stat(full_path)
            mod_time = datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M')
            size_kb = round(stat.st_size / 1024, 1)
            file_items.append({
                'filename': f_name,
                'path': full_path,
                'label': f"{f_name} ({size_kb} KB — {mod_time})",
                'mtime': stat.st_mtime
            })
        except Exception:
            pass
    file_items.sort(key=lambda x: x['mtime'], reverse=True)

    if not file_items:
        st.info("Belum ada berkas Excel di folder `hasil_scraping/`. Silakan jalankan penarikan publikasi pada tab Publikasi terlebih dahulu.")
        return

    # 2. Pilihan Multi-Excel
    all_file_labels = [item['label'] for item in file_items]
    label_to_item = {item['label']: item for item in file_items}

    def on_select_all_toggle():
        if st.session_state.get("analytics_select_all_files", False):
            st.session_state["analytics_multiselect_files"] = all_file_labels
        else:
            st.session_state["analytics_multiselect_files"] = [all_file_labels[0]] if all_file_labels else []

    col_ctrl1, col_ctrl2 = st.columns([3.8, 1.2])
    with col_ctrl2:
        st.markdown("<div style='padding-top: 28px;'></div>", unsafe_allow_html=True)
        st.checkbox("Pilih Semua", value=False, key="analytics_select_all_files", on_change=on_select_all_toggle)

    with col_ctrl1:
        selected_labels = st.multiselect(
            "Pilih Berkas Excel untuk Dianalisis (Bisa Lebih dari 1):",
            options=all_file_labels,
            default=[all_file_labels[0]],
            key="analytics_multiselect_files",
            help="Pilih satu atau beberapa berkas Excel hasil scraping untuk digabung dan dianalisis bersama."
        )

    if not selected_labels:
        st.warning("Silakan pilih minimal 1 berkas Excel untuk menampilkan analisis.")
        return

    # Baca seluruh berkas yang dipilih dan gabungkan
    dfs: List[pd.DataFrame] = []
    for lbl in selected_labels:
        f_info = label_to_item[lbl]
        f_path = f_info['path']
        try:
            xl = pd.ExcelFile(f_path)
            for s_name in xl.sheet_names:
                df_sub = pd.read_excel(f_path, sheet_name=s_name)
                if df_sub is not None and not df_sub.empty:
                    if 'Profil Dosen' in df_sub.columns and not df_sub['Profil Dosen'].isnull().all():
                        df_sub['Profil Dosen'] = df_sub['Profil Dosen'].apply(lambda x: standardize_author_name(str(x)) if pd.notna(x) else '-')
                    else:
                        raw_base = f_info['filename'].replace('scholar_', '').replace('.xlsx', '')
                        author_guess = s_name if len(xl.sheet_names) > 1 else raw_base.split('_')[0]
                        df_sub['Profil Dosen'] = standardize_author_name(author_guess)
                    if 'DOI' in df_sub.columns and not df_sub['DOI'].isnull().all():
                        df_sub['DOI'] = df_sub['DOI'].apply(lambda x: clean_doi(str(x)) if pd.notna(x) and str(x).strip() not in ['', '-'] else '-')
                    else:
                        df_sub['DOI'] = '-'
                    df_sub['Sumber Berkas'] = f_info['filename']
                    dfs.append(df_sub)
        except Exception as ex:
            st.error(f"Gagal membaca berkas `{f_info['filename']}`: {ex}")

    if not dfs:
        st.warning("Tidak ada data publikasi yang berhasil dimuat dari berkas yang dipilih.")
        return

    raw_df = pd.concat(dfs, ignore_index=True)

    # Buat satu file Excel gabungan dari seluruh berkas terpilih untuk tombol unduh di col_a_act
    merged_excel_buf = io.BytesIO()
    with pd.ExcelWriter(merged_excel_buf, engine='openpyxl') as writer:
        desired_order = [
            'No', 'Profil Dosen', 'Judul Publikasi', 'Penulis (Authors)', 'Status Penulis',
            'Nama Jurnal / Prosiding', 'Publisher', 'Jenis Jurnal', 'Terindeks',
            'Kategori Publikasi', 'Tanggal Terbit', 'Tahun', 'Vol/No/Hal'
        ]
        sitasi_cols = [c for c in raw_df.columns if re.match(r'^Sitasi\s+\d{4}$', c)]
        sitasi_cols = sorted(sitasi_cols, key=lambda x: int(re.search(r'\d{4}', x).group(0)))
        desired_order.extend(sitasi_cols)
        desired_order.extend(['Total Sitasi Periode', 'Total Sitasi (All)', 'Link Artikel', 'DOI'])

        export_df = raw_df.copy()
        ordered_cols = [c for c in desired_order if c in export_df.columns] + [c for c in export_df.columns if c not in desired_order and c != 'Sumber Berkas']
        export_df = export_df[ordered_cols]
        export_df['No'] = range(1, len(export_df) + 1)

        # Sheet utama gabungan
        export_df.to_excel(writer, sheet_name="Semua Publikasi", index=False)

        # Jika memuat lebih dari 1 dosen/berkas, sertakan sheet untuk masing-masing profil
        if 'Profil Dosen' in export_df.columns and export_df['Profil Dosen'].nunique() > 1:
            seen_sheets = {"semua publikasi"}
            for p_name, group in export_df.groupby('Profil Dosen', sort=False):
                sheet_clean = re.sub(r'[:\\/?*\[\]]', '', str(p_name)).strip()[:28] or "Dosen"
                counter = 1
                unique_s_name = sheet_clean
                while unique_s_name.lower() in seen_sheets:
                    unique_s_name = f"{sheet_clean[:25]}_{counter}"
                    counter += 1
                seen_sheets.add(unique_s_name.lower())
                group.to_excel(writer, sheet_name=unique_s_name, index=False)

    merged_excel_bytes = merged_excel_buf.getvalue()
    ts_now = datetime.now().strftime("%Y%m%d_%H%M%S")
    if len(selected_labels) > 1:
        merged_dl_name = f"gabungan_{len(selected_labels)}_berkas_{ts_now}.xlsx".lower()
        dl_btn_label = f"Unduh {len(selected_labels)} Berkas (.xlsx)"
    else:
        single_base = selected_labels[0].split(' (')[0].replace('.xlsx', '')
        merged_dl_name = f"{single_base}_{ts_now}.xlsx".lower()
        dl_btn_label = "Unduh Berkas (.xlsx)"

    btn_download_excel_placeholder.download_button(
        label=dl_btn_label,
        data=merged_excel_bytes,
        file_name=merged_dl_name,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
        type="primary",
        key="btn_download_selected_excel",
        help="Unduh data seluruh berkas Excel yang dipilih dalam satu file Excel (.xlsx)"
    )

    dataset_name = f"{len(selected_labels)} Berkas Excel" if len(selected_labels) > 1 else selected_labels[0].split(' (')[0]

    # Filter Dosen jika data memuat lebih dari 1 dosen
    analytics_df = raw_df.copy()
    if 'Profil Dosen' in analytics_df.columns and analytics_df['Profil Dosen'].nunique() > 1:
        dosen_opts = ["Semua Dosen (Gabungan)"] + sorted([str(x) for x in analytics_df['Profil Dosen'].dropna().unique()])
        selected_dosen_filter = st.selectbox("Filter Dosen untuk Analisis:", options=dosen_opts, key="analytics_dosen_filter")
        if selected_dosen_filter != "Semua Dosen (Gabungan)":
            analytics_df = analytics_df[analytics_df['Profil Dosen'] == selected_dosen_filter]
            dataset_name = f"{dataset_name} — {selected_dosen_filter}"

    # Pastikan Kategori Publikasi tersedia
    if 'Kategori Publikasi' not in analytics_df.columns or analytics_df['Kategori Publikasi'].isnull().any():
        analytics_df['Kategori Publikasi'] = analytics_df.apply(classify_publication_category, axis=1)

    # Ekstrak Tahun Publikasi Bersih
    year_col = 'Tahun' if 'Tahun' in analytics_df.columns else ('Tahun Terbit' if 'Tahun Terbit' in analytics_df.columns else None)
    if year_col:
        analytics_df['Clean_Year'] = pd.to_numeric(analytics_df[year_col], errors='coerce')
    else:
        if 'Tanggal Terbit' in analytics_df.columns:
            extracted_y = analytics_df['Tanggal Terbit'].astype(str).str.extract(r'\b(20\d{2}|19\d{2})\b')[0]
            analytics_df['Clean_Year'] = pd.to_numeric(extracted_y, errors='coerce')
        else:
            analytics_df['Clean_Year'] = None

    # Kolom sitasi per tahun jika ada
    year_cols = [c for c in analytics_df.columns if re.match(r'^Sitasi\s+\d{4}$', c)]
    year_cols = sorted(year_cols, key=lambda x: int(re.search(r'\d{4}', x).group(0)))

    # Kolom total periode & lifetime sitasi
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

    st.markdown("---")

    # 3. Ringkasan KPI
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

    # 4. TABEL STANDAR AKREDITASI (JENIS PUBLIKASI PER TAHUN)
    st.markdown("#### Tabel Ringkasan Jenis Publikasi")
    st.caption("Matriks baku publikasi berdasarkan klasifikasi akreditasi jurnal, seminar, buku, dan paten.")

    # Deteksi rentang tahun
    valid_years = sorted([int(y) for y in analytics_df['Clean_Year'].dropna().unique() if 1990 <= y <= 2035])
    cite_years = sorted([int(re.search(r'\d{4}', c).group(0)) for c in year_cols])

    if cite_years:
        target_year_range = list(range(min(cite_years), max(cite_years) + 1))
    elif valid_years:
        if any(2023 <= y <= 2026 for y in valid_years):
            target_year_range = [2023, 2024, 2025, 2026]
        else:
            target_year_range = valid_years[-4:]
    else:
        target_year_range = [2023, 2024, 2025, 2026]

    # Filter pilihan tahun untuk tabel
    col_yr_ctrl1, col_yr_ctrl2 = st.columns([2, 1])
    with col_yr_ctrl1:
        year_filter_mode = st.radio(
            "Pilihan Kolom Tahun:",
            options=[
                f"Tahun Target ({min(target_year_range)} - {max(target_year_range)})",
                f"Semua Tahun dalam Berkas ({min(valid_years)} - {max(valid_years)})" if valid_years and (min(valid_years) < min(target_year_range) or max(valid_years) > max(target_year_range)) else f"Semua Tahun ({min(target_year_range)} - {max(target_year_range)})"
            ],
            horizontal=True,
            key="analytics_year_filter_mode"
        )
    if "Semua Tahun dalam Berkas" in year_filter_mode and valid_years:
        selected_table_years = list(range(min(valid_years), max(valid_years) + 1))
    else:
        selected_table_years = target_year_range

    summary_display_df, summary_numeric_df = build_summary_table(analytics_df, selected_table_years)

    st.dataframe(summary_display_df, use_container_width=True, hide_index=True)

    # Tombol Ekspor Tabel Ringkasan
    col_exp1, col_exp2, col_exp3 = st.columns([1, 1, 2])
    with col_exp1:
        csv_data = summary_display_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Unduh Tabel (CSV)",
            data=csv_data,
            file_name=f"ringkasan_jenis_publikasi_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True
        )
    with col_exp2:
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            summary_display_df.to_excel(writer, index=False, sheet_name="Ringkasan Publikasi")
        st.download_button(
            label="Unduh Tabel (Excel)",
            data=excel_buffer.getvalue(),
            file_name=f"ringkasan_jenis_publikasi_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

    st.markdown("---")

    # 5. VISUALISASI GRAFIK (CHARTS)
    st.markdown("#### Visualisasi Grafik")

    col_chart_top1, col_chart_top2 = st.columns(2)
    with col_chart_top1:
        # Stacked Bar Chart: Distribusi Jenis Publikasi per Tahun
        chart_sub_df = summary_numeric_df[summary_numeric_df['Jenis Publikasi'] != 'Total'].copy()
        melted_df = chart_sub_df.melt(
            id_vars=['Jenis Publikasi'],
            value_vars=[str(y) for y in selected_table_years],
            var_name='Tahun',
            value_name='Jumlah'
        )
        fig_trend = px.bar(
            melted_df,
            x='Tahun',
            y='Jumlah',
            color='Jenis Publikasi',
            color_discrete_map=CATEGORY_COLORS,
            barmode='stack',
            text='Jumlah',
            title="Tren Jenis Publikasi per Tahun"
        )
        fig_trend.update_traces(textposition='inside', insidetextanchor='middle')
        fig_trend.for_each_trace(lambda t: t.update(text=[str(v) if v > 0 else "" for v in t.y]))
        fig_trend.update_layout(
            height=450,
            margin=dict(t=50, b=120, l=40, r=20),
            legend=dict(
                orientation="h",
                yanchor="top",
                y=-0.22,
                xanchor="center",
                x=0.5,
                font=dict(size=11)
            )
        )
        st.plotly_chart(fig_trend, use_container_width=True)

    with col_chart_top2:
        # Donut Chart: Proporsi Keseluruhan
        cat_totals = chart_sub_df[['Jenis Publikasi', 'Total']].copy()
        cat_totals = cat_totals[cat_totals['Total'] > 0]
        if not cat_totals.empty:
            fig_donut = px.pie(
                cat_totals,
                names='Jenis Publikasi',
                values='Total',
                color='Jenis Publikasi',
                color_discrete_map=CATEGORY_COLORS,
                hole=0.45,
                title="Proporsi Kategori Publikasi"
            )
            fig_donut.update_layout(
                height=420,
                margin=dict(t=50, b=30, l=20, r=140),
                legend=dict(
                    orientation="v",
                    yanchor="middle",
                    y=0.5,
                    xanchor="left",
                    x=1.02,
                    font=dict(size=11)
                )
            )
            st.plotly_chart(fig_donut, use_container_width=True)
        else:
            st.info("Belum ada publikasi pada rentang tahun ini.")

    # Grafik Sitasi & Peran Penulis jika datanya tersedia
    if year_cols:
        st.markdown("---")
        col_c_sit1, col_c_sit2 = st.columns(2)
        with col_c_sit1:
            st.markdown("##### Pertumbuhan Sitasi per Tahun")
            yearly_sums = {int(re.search(r'\d{4}', c).group(0)): int(analytics_df[c].sum()) for c in year_cols}
            trend_sit_df = pd.DataFrame(list(yearly_sums.items()), columns=['Tahun', 'Jumlah Sitasi'])
            fig_sit_trend = px.bar(
                trend_sit_df,
                x='Tahun',
                y='Jumlah Sitasi',
                text='Jumlah Sitasi',
                color='Jumlah Sitasi',
                color_continuous_scale='Greens'
            )
            fig_sit_trend.update_traces(textposition='outside')
            fig_sit_trend.update_layout(
                xaxis=dict(tickmode='linear'),
                height=360,
                margin=dict(t=30, b=30, l=30, r=20),
                coloraxis_showscale=False
            )
            st.plotly_chart(fig_sit_trend, use_container_width=True)

        with col_c_sit2:
            st.markdown("##### Top 10 Publikasi Terbanyak Disitasi")
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
            fig_top.update_layout(
                yaxis=dict(autorange="reversed"),
                height=360,
                margin=dict(t=30, b=30, l=20, r=20),
                coloraxis_showscale=False
            )
            st.plotly_chart(fig_top, use_container_width=True)

    if 'Status Penulis' in analytics_df.columns:
        st.markdown("---")
        st.markdown("##### Peran Penulis")
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
        fig_status.update_layout(
            height=320,
            margin=dict(t=30, b=40, l=20, r=20),
            legend=dict(
                orientation="h",
                yanchor="top",
                y=-0.15,
                xanchor="center",
                x=0.5
            )
        )
        st.plotly_chart(fig_status, use_container_width=True)

    # Pratinjau Data Lengkap
    with st.expander(f"Pratinjau Data Lengkap ({len(analytics_df)} Baris)"):
        st.dataframe(analytics_df, use_container_width=True, height=260, hide_index=True)


# ==============================================================================
# 4. TAB 3: UNDUH ARTIKEL ILMIAH (DOI)
# ==============================================================================

def render_downloader_tab() -> None:
    """Merender tab formulir ekstraksi DOI dan pengunduhan artikel PDF ilmiah via Open Access & Sci-Hub."""
    dl_job: Optional[ArticleDownloaderJob] = st.session_state.get('dl_job')
    is_running = bool(dl_job and dl_job.is_running and not dl_job.stop_requested)

    st.markdown("#### Pengunduh Artikel Ilmiah Berbasis DOI")
    st.caption("Pindai DOI otomatis dari berkas dokumen atau teks bebas, lalu unduh artikel PDF secara hybrid via Open Access & Sci-Hub.")

    col_in1, col_in2 = st.columns([1, 1], gap="medium")

    with col_in1:
        st.markdown("<label style='font-size: 0.95rem; font-weight: 600; color: #1E293B; margin-bottom: 6px; display: inline-block;'>Sumber Daftar DOI</label>", unsafe_allow_html=True)
        input_mode = st.radio(
            "Pilih Metode Input:",
            options=["Unggah Dokumen", "Tempel Teks DOI"],
            horizontal=True,
            disabled=is_running,
            label_visibility="collapsed"
        )

        extracted_dois: List[str] = []
        target_subfolder = ""

        if input_mode == "Unggah Dokumen":
            uploaded = st.file_uploader(
                "Unggah berkas yang memuat DOI:",
                type=["xlsx", "xls", "docx", "pdf", "txt", "csv"],
                disabled=is_running,
                help="Mendukung Excel (.xlsx, .xls), Word (.docx), PDF (.pdf), serta berkas Teks (.txt, .csv)."
            )
            if uploaded:
                base_name = os.path.splitext(uploaded.name)[0]
                target_subfolder = base_name
                extracted_dois = extract_dois_from_file(uploaded, uploaded.name)
                st.session_state.dl_extracted_dois = extracted_dois
                st.session_state.dl_subfolder_name = target_subfolder
            else:
                extracted_dois = st.session_state.get('dl_extracted_dois', [])
                target_subfolder = st.session_state.get('dl_subfolder_name', '')

        else:
            pasted_text = st.text_area(
                "Tempel teks atau daftar DOI:",
                placeholder="Contoh:\n10.1016/j.compedu.2020.103980\nhttps://doi.org/10.30762/ijise.v2i3.1887\natau paragraf artikel...",
                height=130,
                disabled=is_running
            )
            custom_subfolder = st.text_input(
                "Nama Subfolder Penyimpanan di 'artikel/':",
                value=st.session_state.get('dl_subfolder_name') or f"unduhan_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                disabled=is_running,
                help="Nama subfolder di dalam folder 'artikel/' tempat menyimpan berkas PDF."
            )
            if pasted_text:
                extracted_dois = extract_dois_from_text(pasted_text)
                target_subfolder = custom_subfolder.strip() or f"unduhan_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                st.session_state.dl_extracted_dois = extracted_dois
                st.session_state.dl_subfolder_name = target_subfolder
            else:
                extracted_dois = st.session_state.get('dl_extracted_dois', [])
                target_subfolder = custom_subfolder.strip()

    with col_in2:
        st.markdown("<label style='font-size: 0.95rem; font-weight: 600; color: #1E293B; margin-bottom: 6px; display: inline-block;'>Pratinjau & Pengaturan</label>", unsafe_allow_html=True)
        with st.expander("Pengaturan Mirror & Jeda Unduhan", expanded=False):
            sel_mirrors = st.multiselect(
                "Mirror Sci-Hub Aktif:",
                options=DEFAULT_SCIHUB_MIRRORS,
                default=DEFAULT_SCIHUB_MIRRORS,
                disabled=is_running,
                help="Daftar domain mirror Sci-Hub yang diakses via browser Chrome (Selenium) untuk mengatasi CAPTCHA. Domain sci-hub.box digunakan sebagai mirror default utama."
            )
            delay_val = st.number_input(
                "Jeda Antar Unduhan (Detik):",
                min_value=0.5,
                max_value=10.0,
                value=2.0,
                step=0.5,
                disabled=is_running,
                help="Jeda waktu aman antar artikel untuk menjaga stabilitas sesi."
            )

        total_found = len(extracted_dois)
        st.metric("Total DOI Terdeteksi", f"{total_found} Artikel")
        if target_subfolder:
            clean_sub = sanitize_filename(target_subfolder)
            st.caption(f"Folder Output: `{ARTIKEL_DIR}/{clean_sub}/`")

        if total_found > 0:
            preview_df = pd.DataFrame({
                'No': range(1, total_found + 1),
                'DOI': [f"https://doi.org/{d}" for d in extracted_dois]
            })
            st.dataframe(preview_df, height=130, use_container_width=True, hide_index=True)
        else:
            st.info("Belum ada DOI terdeteksi. Unggah berkas atau tempel teks DOI di sebelah kiri.")

    # Tombol Kontrol Mulai / Berhenti
    st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)
    if not is_running:
        can_start = len(extracted_dois) > 0
        if st.button("Mulai Unduh Artikel", type="primary", use_container_width=True, disabled=not can_start):
            new_dl_job = ArticleDownloaderJob(
                doi_list=extracted_dois,
                subfolder_name=target_subfolder,
                mirrors=sel_mirrors if sel_mirrors else DEFAULT_SCIHUB_MIRRORS,
                delay_sec=delay_val
            )
            st.session_state.dl_job = new_dl_job
            st.session_state.dl_was_running = True
            new_dl_job.start()
            st.rerun()
    else:
        if st.button("Hentikan Pengunduhan", type="secondary", use_container_width=True):
            if dl_job:
                dl_job.stop()
                st.session_state.dl_was_running = False
                st.rerun()

    st.markdown("---")

    # Monitor Real-Time Pengunduhan via Fragment
    @st.fragment(run_every="1s" if is_running else None)
    def render_dl_live_monitor() -> None:
        current_job: Optional[ArticleDownloaderJob] = st.session_state.get('dl_job')
        if not current_job:
            st.info("Pilih berkas atau tempel daftar DOI di atas, lalu klik Mulai Unduh Artikel.")
            return

        if st.session_state.get('dl_was_running', False) and (not current_job.is_running or current_job.stop_requested):
            st.session_state.dl_was_running = False
            st.rerun(scope="app")

        # Peringatan Verifikasi CAPTCHA di Sci-Hub (Bila muncul)
        if getattr(current_job, 'is_captcha', False):
            st.markdown("""
            <div class="captcha-box">
                <div class="captcha-title">Verifikasi Robot (CAPTCHA) Terdeteksi di Sci-Hub</div>
                <div class="captcha-desc">
                    Sci-Hub meminta verifikasi robot. Buka jendela Google Chrome di komputer Anda dan selesaikan verifikasi.<br/>
                    Sistem akan otomatis melanjutkan pengunduhan begitu verifikasi selesai.
                </div>
            </div>
            """, unsafe_allow_html=True)

        # Metrik Ringkas
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st_text = "Berhenti" if current_job.stop_requested else ("Berjalan" if current_job.is_running else "Selesai")
            st.metric("Status", st_text)
        with c2:
            st.metric("Progres", f"{current_job.current_idx} / {current_job.total_items}")
        with c3:
            succ = sum(1 for r in current_job.results if r['Status'] == 'Berhasil')
            st.metric("Berhasil Diunduh", succ)
        with c4:
            fail = sum(1 for r in current_job.results if r['Status'] != 'Berhasil')
            st.metric("Tidak Ditemukan", fail)

        # Progress Bar
        pct = (current_job.current_idx / max(1, current_job.total_items)) if current_job.total_items > 0 else 0.0
        pct = min(1.0, max(0.0, pct))
        bar_label = f"{int(pct * 100)}% ({current_job.current_idx}/{current_job.total_items}) — {current_job.status}"
        st.progress(pct, text=bar_label)

        # Log Aktivitas Pengunduhan
        with st.expander(f"Log Aktivitas Pengunduhan ({len(current_job.logs)})", expanded=bool(current_job.is_running and not current_job.stop_requested)):
            log_str = "\n".join(current_job.logs[-80:]) if current_job.logs else "Belum ada aktivitas."
            st.text_area("Console Unduhan", value=log_str, height=150, disabled=True, label_visibility="collapsed")
            st.components.v1.html(
                """
                <script>
                function scrollDlLog() {
                    try {
                        const doc = window.parent.document;
                        const textareas = doc.querySelectorAll('textarea');
                        textareas.forEach(t => {
                            t.scrollTop = t.scrollHeight;
                        });
                    } catch (e) {}
                }
                scrollDlLog();
                setTimeout(scrollDlLog, 50);
                setTimeout(scrollDlLog, 150);
                </script>
                """,
                height=0,
                width=0
            )

        # Tabel Hasil & Aksi Berkas
        if current_job.results:
            st.markdown(f"#### Hasil Pengunduhan Artikel ({len(current_job.results)} Item)")
            st.caption(f"Lokasi penyimpanan: `{current_job.output_dir}`")
            res_df = pd.DataFrame(current_job.results)
            display_cols = ['No', 'DOI', 'Judul Artikel', 'Sumber', 'Status', 'Ukuran', 'Nama File']
            st.dataframe(res_df[display_cols], height=280, use_container_width=True, hide_index=True)

            col_a1, col_a2 = st.columns(2)
            with col_a1:
                # Unduh ZIP seluruh file PDF yang berhasil
                downloaded_files = [r['Path'] for r in current_job.results if r.get('Path') and os.path.exists(r['Path'])]
                if downloaded_files:
                    zip_buf = io.BytesIO()
                    with zipfile.ZipFile(zip_buf, 'w', zipfile.ZIP_DEFLATED) as zf:
                        for pdf_file in downloaded_files:
                            zf.write(pdf_file, arcname=os.path.basename(pdf_file))
                    zip_buf.seek(0)
                    st.download_button(
                        label=f"Unduh {len(downloaded_files)} Artikel PDF (.zip)",
                        data=zip_buf,
                        file_name=f"{current_job.clean_folder_name}.zip",
                        mime="application/zip",
                        type="primary",
                        use_container_width=True,
                        key="btn_download_zip_articles"
                    )
            with col_a2:
                if st.button("Buka Folder Artikel", key="btn_open_article_dir", use_container_width=True):
                    open_output_folder(current_job.output_dir)
                    st.toast(f"Folder '{current_job.output_dir}' telah dibuka.")

    render_dl_live_monitor()


def render_footer() -> None:
    """Menampilkan footer copyright aplikasi dengan tautan repositori."""
    st.markdown("""
    <div class="footer-box">
        Ikhlas Beramal by <a href="https://github.com/ilyasbp/scraper_publikasi_dosen" target="_blank" rel="noopener noreferrer">@ilyasbp</a>
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

    tab_scraper, tab_analytics, tab_downloader = st.tabs([
        "Publikasi",
        "Analisis",
        "Unduh Artikel"
    ])

    with tab_scraper:
        render_scraper_tab()

    with tab_analytics:
        render_analytics_tab()

    with tab_downloader:
        render_downloader_tab()

    render_footer()


if __name__ == "__main__":
    main()
