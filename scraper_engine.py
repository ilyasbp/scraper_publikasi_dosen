"""
scraper_engine.py
=================
Modul inti mesin ekstraksi Google Scholar, akreditasi SCImagoJR (Scopus Q1-Q4),
dan pencarian akreditasi jurnal nasional (SINTA 1-6).
"""

import os
import re
import time
import random
import platform
import warnings
import threading
import subprocess
from datetime import datetime
from difflib import SequenceMatcher
from typing import Optional, Dict, Any, List, Set, Union

import requests
import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

warnings.filterwarnings('ignore')

# Direktori default output spreadsheet
OUTPUT_DIR = "hasil_scraping"

# ==============================================================================
# 1. UTILITAS SISTEM & DIREKTORI
# ==============================================================================

def open_output_folder(folder_path: str = OUTPUT_DIR) -> bool:
    """Membuka folder hasil di file manager sistem operasi (Finder di Mac, Explorer di Windows)."""
    abs_path = os.path.abspath(folder_path)
    os.makedirs(abs_path, exist_ok=True)
    sys_name = platform.system()
    try:
        if sys_name == "Darwin":
            subprocess.run(["open", abs_path], check=True)
            return True
        elif sys_name == "Windows":
            os.startfile(abs_path)
            return True
        else:
            subprocess.run(["xdg-open", abs_path], check=True)
            return True
    except Exception as err:
        print(f"Gagal membuka folder: {err}")
        return False


def extract_author_id(input_str: str) -> str:
    """Mengekstrak Author ID dari teks input mentah atau URL profil Scholar."""
    raw = str(input_str).strip()
    if not raw:
        return 'K_X8HzoAAAAJ'
    match = re.search(r'user=([a-zA-Z0-9_-]+)', raw)
    if match:
        return match.group(1)
    if 'citations?' in raw:
        parts = raw.split('user=')
        if len(parts) > 1:
            return parts[1].split('&')[0]
    cleaned = re.sub(r'[^a-zA-Z0-9_-]', '', raw)
    return cleaned or 'K_X8HzoAAAAJ'


def normalize_title_for_matching(text: str) -> str:
    """Normalisasi judul artikel untuk pencocokan toleran karakter."""
    clean = re.sub(r'[^a-zA-Z0-9\s]', ' ', str(text).lower())
    return ' '.join(clean.split())


# ==============================================================================
# 2. DATABASE SCIMAGOJR 2025 (OFFLINE SCOPUS QUARTILE ENGINE)
# ==============================================================================

SCIMAGO_CACHE: Dict[str, Dict[str, Any]] = {}
SCIMAGO_LOADED: bool = False
SCIMAGO_ACTIVE_PATH: str = ""


def get_latest_scimago_csv_path() -> str:
    """Mencari berkas database SCImagoJR terbaru di folder data/ berdasarkan tahun atau modtime."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidates_dirs = [
        os.path.join(base_dir, "data"),
        "data",
        base_dir,
        "."
    ]

    csv_candidates = []
    seen_paths = set()
    for d in candidates_dirs:
        if os.path.isdir(d):
            for fname in os.listdir(d):
                if fname.lower().endswith('.csv') and 'scimago' in fname.lower():
                    full_p = os.path.abspath(os.path.join(d, fname))
                    if full_p not in seen_paths and os.path.isfile(full_p):
                        seen_paths.add(full_p)
                        m_year = re.search(r'\b(20\d{2})\b', fname)
                        year = int(m_year.group(1)) if m_year else 0
                        mtime = os.path.getmtime(full_p)
                        csv_candidates.append((year, mtime, full_p))

    if csv_candidates:
        # Urutkan prioritas: tahun tertinggi (misal 2026 > 2025), lalu waktu modifikasi file terbaru
        csv_candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
        return csv_candidates[0][2]

    default_p = os.path.join(base_dir, "data", "scimagojr 2025.csv")
    return default_p if os.path.exists(default_p) else "data/scimagojr 2025.csv"


def get_active_scimago_name() -> str:
    """Mengembalikan nama berkas database SCImagoJR yang aktif digunakan."""
    global SCIMAGO_ACTIVE_PATH
    if not SCIMAGO_ACTIVE_PATH:
        SCIMAGO_ACTIVE_PATH = get_latest_scimago_csv_path()
    return os.path.basename(SCIMAGO_ACTIVE_PATH)


SCIMAGO_CSV_PATH = get_latest_scimago_csv_path()

_STOPWORDS = {'on', 'of', 'and', 'the', 'in', 'for', 'a', 'an', 'to', 'with', 'at', 'by', 'part'}

_JOURNAL_ABBREVIATIONS = {
    'trans': 'transactions', 'proc': 'proceedings', 'j': 'journal',
    'int': 'international', 'conf': 'conference', 'lett': 'letters',
    'sci': 'science', 'comput': 'computer', 'res': 'research',
    'ann': 'annals', 'eng': 'engineering', 'knowl': 'knowledge',
    'inf': 'information', 'sys': 'systems', 'appl': 'applied',
    'electron': 'electronic', 'commun': 'communications', 'intell': 'intelligence',
    'mag': 'magazine', 'rev': 'review', 'bull': 'bulletin'
}


def clean_journal_name(name: str) -> str:
    """Membersihkan nama jurnal/prosiding dari nomor volume, nomor terbitan, dan halaman."""
    if not isinstance(name, str):
        return ''
    cleaned = name.lower().strip()
    cleaned = re.sub(r'\(.*?\)', '', cleaned)
    cleaned = re.sub(r'\b(vol|volume|no|issue|pp|hal|pages)\b.*', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\d+\s*\([\d\s-]+\).*', '', cleaned)
    cleaned = re.sub(r'\b\d{1,5}\s*,\s*\d+.*', '', cleaned)
    cleaned = re.sub(r'[^a-z0-9\s]', ' ', cleaned)
    return ' '.join(cleaned.split())


def to_token_key(name: str) -> str:
    """Menghasilkan token standar tanpa stopwords & ekspansi singkatan untuk pencocokan jurnal."""
    cleaned = clean_journal_name(name)
    words = [_JOURNAL_ABBREVIATIONS.get(w, w) for w in cleaned.split()]
    filtered = [w for w in words if w not in _STOPWORDS]
    return ' '.join(filtered)


def load_scimago_database(csv_path: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    """Memuat database SCImagoJR ke memori (otomatis memilih versi tahun terbaru)."""
    global SCIMAGO_CACHE, SCIMAGO_LOADED, SCIMAGO_ACTIVE_PATH
    if SCIMAGO_LOADED and SCIMAGO_CACHE:
        return SCIMAGO_CACHE

    target_path = csv_path or get_latest_scimago_csv_path()
    if not os.path.exists(target_path):
        return {}

    try:
        df = pd.read_csv(target_path, sep=';', low_memory=False)
        for _, row in df.iterrows():
            raw_title = str(row.get('Title', ''))
            q_val = str(row.get('SJR Best Quartile', '')).strip().upper()
            ptype = str(row.get('Type', '')).strip().lower()
            pub = str(row.get('Publisher', '')).strip()
            if pub.lower() in ['nan', 'none', '']:
                pub = str(row.get('Publisher.1', '')).strip()
            if pub.lower() in ['nan', 'none']:
                pub = ''

            if q_val in ['Q1', 'Q2', 'Q3', 'Q4']:
                status = f"Scopus {q_val}"
            elif 'conference' in ptype or 'proceeding' in ptype:
                status = "Scopus No-Q"
            elif 'journal' in ptype:
                status = "Scopus No-Q"
            else:
                status = "Scopus No-Q"

            info = {
                'title': raw_title,
                'status': status,
                'quartile': q_val if q_val in ['Q1', 'Q2', 'Q3', 'Q4'] else None,
                'type': ptype,
                'publisher': pub
            }

            clean_k = clean_journal_name(raw_title)
            if clean_k and clean_k not in SCIMAGO_CACHE:
                SCIMAGO_CACHE[clean_k] = info

            token_k = to_token_key(raw_title)
            if token_k and token_k not in SCIMAGO_CACHE:
                SCIMAGO_CACHE[token_k] = info

        SCIMAGO_LOADED = True
        SCIMAGO_ACTIVE_PATH = target_path
    except Exception as err:
        print(f"Peringatan saat memuat SCImagoJR database ({target_path}): {err}")

    return SCIMAGO_CACHE


def lookup_scimago(venue_name: str) -> Optional[Dict[str, Any]]:
    """Mencari akreditasi Scopus jurnal/prosiding di database SCImagoJR 2025."""
    if not venue_name or str(venue_name).strip() in ['-', '']:
        return None

    if not SCIMAGO_LOADED:
        load_scimago_database()

    if not SCIMAGO_CACHE:
        return None

    c_name = clean_journal_name(venue_name)
    if c_name in SCIMAGO_CACHE:
        return SCIMAGO_CACHE[c_name]

    t_name = to_token_key(venue_name)
    if t_name in SCIMAGO_CACHE:
        return SCIMAGO_CACHE[t_name]

    for sep in [':', '-', '–', ',']:
        if sep in venue_name:
            part = venue_name.split(sep)[0]
            cp = clean_journal_name(part)
            if cp in SCIMAGO_CACHE:
                return SCIMAGO_CACHE[cp]
            tp = to_token_key(part)
            if tp in SCIMAGO_CACHE:
                return SCIMAGO_CACHE[tp]

    return None


# ==============================================================================
# 3. FORMATTING TANGGAL & PARSING PENULIS
# ==============================================================================

MONTH_MAP = {
    'jan': '01', 'januari': '01', 'january': '01',
    'feb': '02', 'februari': '02', 'february': '02',
    'mar': '03', 'maret': '03', 'march': '03',
    'apr': '04', 'april': '04',
    'mei': '05', 'may': '05',
    'jun': '06', 'juni': '06', 'june': '06',
    'jul': '07', 'juli': '07', 'july': '07',
    'agu': '08', 'agust': '08', 'agustus': '08', 'aug': '08', 'august': '08',
    'sep': '09', 'sept': '09', 'september': '09',
    'okt': '10', 'oktober': '10', 'oct': '10', 'october': '10',
    'nov': '11', 'november': '11',
    'des': '12', 'desember': '12', 'dec': '12', 'december': '12'
}


def format_to_dd_mm_yyyy(raw_date: Any, fallback_year: Optional[Any] = None) -> str:
    """Mengubah format tanggal publikasi menjadi format konsisten DD/MM/YYYY."""
    s = '' if (raw_date is None or pd.isna(raw_date)) else str(raw_date).strip()

    if not s or s in ['-', 'nan', 'None']:
        if fallback_year and re.match(r'^(19|20)\d{2}$', str(fallback_year).strip()):
            return f'01/01/{str(fallback_year).strip()}'
        return '-'

    if re.match(r'^\d{2}/\d{2}/\d{4}$', s):
        return s

    m_ymd = re.match(r'^(\d{4})[/\-.](0?[1-9]|1[0-2])[/\-.](0?[1-9]|[12]\d|3[01])$', s)
    if m_ymd:
        y, m, d = m_ymd.groups()
        return f'{int(d):02d}/{int(m):02d}/{y}'

    m_dmy = re.match(r'^(0?[1-9]|[12]\d|3[01])[/\-.](0?[1-9]|1[0-2])[/\-.](\d{4})$', s)
    if m_dmy:
        d, m, y = m_dmy.groups()
        return f'{int(d):02d}/{int(m):02d}/{y}'

    m_ym = re.match(r'^(\d{4})[/\-.](0?[1-9]|1[0-2])$', s)
    if m_ym:
        y, m = m_ym.groups()
        return f'01/{int(m):02d}/{y}'

    m_y = re.match(r'^(\d{4})$', s)
    if m_y:
        return f'01/01/{m_y.group(1)}'

    m_yr = re.search(r'\b(19\d{2}|20\d{2})\b', s)
    y = m_yr.group(1) if m_yr else (str(fallback_year).strip() if fallback_year else None)

    found_m = None
    for k, v in MONTH_MAP.items():
        if re.search(rf'\b{k}\b', s, re.IGNORECASE):
            found_m = v
            break

    found_d = '01'
    if found_m:
        rem = re.sub(rf'\b({y})\b', ' ', s) if y else s
        rem = re.sub(r'[a-zA-Z]+', ' ', rem)
        d_candidates = re.findall(r'\b([0-2]?[0-9]|3[01])\b', rem)
        valid_days = [c for c in d_candidates if c not in ('0', '00')]
        if valid_days:
            found_d = f'{int(valid_days[0]):02d}'

    if y and found_m:
        return f'{found_d}/{found_m}/{y}'
    elif y and re.match(r'^(19|20)\d{2}$', str(y)):
        return f'01/01/{y}'

    return s


def extract_first_name(full_name: str) -> str:
    """Mengekstrak nama depan penulis tanpa gelar akademik."""
    if not full_name:
        return ""
    cleaned = re.sub(r'[\u202a-\u202e]', '', str(full_name)).strip()
    cleaned = re.sub(r'^[^\w]+|[^\w]+$', '', cleaned)
    words = cleaned.split()
    titles = {
        'prof', 'prof.', 'dr', 'dr.', 'ir', 'ir.', 'drs', 'drs.', 'dra', 'dra.',
        'h.', 'hj.', 'mr.', 'ms.', 'mrs.', 'ph.d', 'phd', 'm.sc', 'msc', 'st', 'st.', 'm.kom', 'm.ti'
    }
    for w in words:
        clean_w = re.sub(r'[^a-zA-Z0-9]', '', w)
        if clean_w.lower() not in titles and clean_w:
            return clean_w
    return words[0] if words else ""


def standardize_author_name(name: str) -> str:
    """
    Standarisasi penulisan nama profil author/dosen dari Google Scholar menjadi Title Case yang rapi.
    Contoh:
      - 'AGUS MIFTAKUS SURUR' -> 'Agus Miftakus Surur'
      - 'agus miftakus surur' -> 'Agus Miftakus Surur'
      - 'DR. AGUS MIFTAKUS SURUR, M.PD.' -> 'Dr. Agus Miftakus Surur, M.Pd.'
    """
    if not name or not str(name).strip():
        return "-"
    raw = re.sub(r'[\u202a-\u202e]', '', str(name)).strip()
    raw = re.sub(r'\s+', ' ', raw)
    if not raw:
        return "-"

    # Kamus umum gelar agar kapitalisasi gelar akademik Indonesia/Internasional tepat
    known_titles = {
        'dr': 'Dr.', 'dr.': 'Dr.', 'prof': 'Prof.', 'prof.': 'Prof.',
        'ir': 'Ir.', 'ir.': 'Ir.', 'drs': 'Drs.', 'drs.': 'Drs.',
        'dra': 'Dra.', 'dra.': 'Dra.', 'ph.d': 'Ph.D.', 'phd': 'Ph.D.',
        'ph.d.': 'Ph.D.', 'm.sc': 'M.Sc.', 'msc': 'M.Sc.', 'm.sc.': 'M.Sc.',
        'b.sc': 'B.Sc.', 'bsc': 'B.Sc.', 'm.pd': 'M.Pd.', 'mpd': 'M.Pd.',
        'm.pd.': 'M.Pd.', 's.pd': 'S.Pd.', 'spd': 'S.Pd.', 's.pd.': 'S.Pd.',
        'm.kom': 'M.Kom.', 'mkom': 'M.Kom.', 'm.kom.': 'M.Kom.',
        's.kom': 'S.Kom.', 'skom': 'S.Kom.', 's.kom.': 'S.Kom.',
        'm.t': 'M.T.', 'mt': 'M.T.', 'm.t.': 'M.T.', 's.t': 'S.T.',
        'st': 'S.T.', 's.t.': 'S.T.', 's.si': 'S.Si.', 'ssi': 'S.Si.',
        's.si.': 'S.Si.', 'm.si': 'M.Si.', 'msi': 'M.Si.', 'm.si.': 'M.Si.',
        's.e': 'S.E.', 'se': 'S.E.', 's.e.': 'S.E.', 'm.m': 'M.M.',
        'mm': 'M.M.', 'm.m.': 'M.M.', 's.h': 'S.H.', 'sh': 'S.H.',
        's.h.': 'S.H.', 'm.h': 'M.H.', 'mh': 'M.H.', 'm.h.': 'M.H.',
        's.sos': 'S.Sos.', 's.sos.': 'S.Sos.', 'm.sos': 'M.Sos.', 'm.sos.': 'M.Sos.',
        's.ked': 'S.Ked.', 'm.kes': 'M.Kes.', 'h.': 'H.', 'hj.': 'Hj.',
    }

    words = raw.split(' ')
    standardized_words = []
    for w in words:
        if not w:
            continue
        prefix, suffix = '', ''
        m_start = re.match(r'^([^a-zA-Z0-9]+)', w)
        if m_start:
            prefix = m_start.group(1)
            w = w[len(prefix):]
        m_end = re.search(r'([^a-zA-Z0-9]+)$', w)
        if m_end:
            suffix = m_end.group(1)
            w = w[:-len(suffix)]

        if not w:
            standardized_words.append(prefix + suffix)
            continue

        w_lower = w.lower()
        if w_lower in known_titles:
            title_formatted = known_titles[w_lower]
            if title_formatted.endswith('.') and suffix.startswith('.'):
                suffix = suffix[1:]
            standardized_words.append(prefix + title_formatted + suffix)
            continue

        if '.' in w:
            parts = [p.capitalize() for p in w.split('.')]
            clean_w = '.'.join(parts)
        elif '-' in w:
            parts = [p.capitalize() for p in w.split('-')]
            clean_w = '-'.join(parts)
        elif "'" in w:
            parts = [p.capitalize() for p in w.split("'")]
            clean_w = "'".join(parts)
        else:
            clean_w = w.capitalize()

        standardized_words.append(prefix + clean_w + suffix)

    result = ' '.join(standardized_words).strip()
    return result if result else "-"


def clean_doi(doi_str: str) -> str:
    """Membersihkan format DOI dan memastikan representasi standar 10.xxxx/..."""
    if not doi_str:
        return "-"
    cleaned = re.sub(r'^(https?://(dx\.)?doi\.org/|doi:\s*|doi/)+', '', str(doi_str).strip(), flags=re.IGNORECASE)
    m = re.search(r'(10\.\d{4,9}/[^\s"\'<>]+)', cleaned)
    if m:
        doi = m.group(1)
        doi = re.sub(r'[\.,;:\)\]>]+$', '', doi)
        return doi
    return "-"


def normalize_title_for_matching(title: str) -> str:
    """Normalisasi string judul publikasi untuk perbandingan kemiripan."""
    clean = re.sub(r'[^a-zA-Z0-9\s]', ' ', str(title).lower())
    return re.sub(r'\s+', ' ', clean).strip()


def calculate_title_similarity(title_a: str, title_b: str) -> float:
    """Menghitung rasio kemiripan (0.0 s.d 1.0) antara dua judul publikasi."""
    na = normalize_title_for_matching(title_a)
    nb = normalize_title_for_matching(title_b)
    if not na or not nb:
        return 0.0
    return SequenceMatcher(None, na, nb).ratio()


def lookup_crossref_doi(title: str, min_similarity: float = 0.95, timeout: float = 5.0) -> str:
    """
    Mencari DOI resmi artikel ilmiah via Crossref REST API.
    Hanya mengembalikan DOI jika kemiripan judul mencapai ambang batas min_similarity (default: 0.95 / 95%).
    """
    if not title or len(str(title).strip()) < 5:
        return "-"
    try:
        url = f"https://api.crossref.org/works?query.title={requests.utils.quote(str(title).strip())}&rows=3"
        headers = {
            'User-Agent': 'PublikasiDosenScraper/1.0 (mailto:scholar_scraper@dosen.ac.id)'
        }
        resp = requests.get(url, headers=headers, timeout=timeout)
        if resp.status_code == 200:
            data = resp.json()
            items = data.get('message', {}).get('items', [])
            for item in items:
                cr_titles = item.get('title', [])
                if not cr_titles:
                    continue
                cr_title = cr_titles[0]
                sim = calculate_title_similarity(title, cr_title)
                if sim >= min_similarity:
                    raw_doi = item.get('DOI', '')
                    cleaned = clean_doi(raw_doi)
                    if cleaned != "-":
                        return cleaned
    except Exception:
        pass
    return "-"


def extract_doi(
    fields_dict: Optional[Dict[str, str]] = None,
    soup: Any = None,
    raw_html: str = "",
    title: str = ""
) -> str:
    """
    Mengekstrak nomor DOI artikel dari metadata Google Scholar atau via Crossref REST API
    dengan ambang batas kemiripan judul 95%.
    """
    # 1. Cek langsung dari fields_dict Google Scholar
    if fields_dict:
        # Cek kunci spesifik 'doi'
        for k, v in fields_dict.items():
            if 'doi' in k.lower():
                cleaned = clean_doi(v)
                if cleaned != "-":
                    return cleaned

        # Cek pola 10.xxxx di values fields_dict (description, source, dsb)
        for k, v in fields_dict.items():
            if v and '10.' in v:
                cleaned = clean_doi(v)
                if cleaned != "-":
                    return cleaned

    # 2. Cek elemen <a> pada halaman detail Google Scholar (BeautifulSoup)
    if soup:
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            if 'doi.org/10.' in href or 'dx.doi.org/10.' in href or '/doi/10.' in href:
                cleaned = clean_doi(href)
                if cleaned != "-":
                    return cleaned

    # 3. Cek pola regex DOI pada raw_html halaman
    if raw_html and '10.' in raw_html:
        m = re.search(r'\b(10\.\d{4,9}/[^\s"\'<>&]+)', raw_html)
        if m:
            cleaned = clean_doi(m.group(1))
            if cleaned != "-":
                return cleaned

    # 4. Jika belum ada di Google Scholar, cari via Crossref REST API (Kemiripan >= 95%)
    if title:
        cr_doi = lookup_crossref_doi(title=title, min_similarity=0.95)
        if cr_doi != "-":
            return cr_doi

    return "-"


def extract_name_tokens(text: str) -> List[str]:
    """Ekstrak token alfabet nama tanpa gelar akademis umum."""
    academic_titles = {
        'prof', 'dr', 'ir', 'drs', 'dra', 'phd', 'msc', 'bsc', 'st', 'mt',
        'skom', 'mkom', 'mti', 'msi', 'ssi', 'spd', 'mpd', 'sked', 'drg',
        'apt', 'sh', 'mh', 'se', 'me', 'dea', 'kh', 'h', 'hj', 'mr', 'ms', 'mrs'
    }
    normalized = text.lower()
    normalized = re.sub(r'\(.*?\)', '', normalized)
    words = re.findall(r'[a-z]+', normalized)
    return [w for w in words if w not in academic_titles]


def is_same_author(candidate_str: str, profile_name_str: str) -> bool:
    """Mengecek apakah nama kandidat di artikel merujuk pada pemilik profil."""
    if not candidate_str or not profile_name_str:
        return False

    cand_tokens = extract_name_tokens(candidate_str)
    prof_tokens = extract_name_tokens(profile_name_str)

    if not cand_tokens or not prof_tokens:
        return False

    if cand_tokens == prof_tokens or sorted(cand_tokens) == sorted(prof_tokens):
        return True

    if len(prof_tokens) == 1:
        return prof_tokens[0] in cand_tokens

    prof_first = prof_tokens[0]
    prof_last = prof_tokens[-1]
    prof_initials_str = ''.join([t[0] for t in prof_tokens])

    valid_initial_combinations = {
        prof_initials_str,
        prof_initials_str[:2],
        prof_first[0] + prof_last[0],
        prof_first[0],
        prof_last[0] + prof_first[0],
        prof_last[0],
    }

    has_last = prof_last in cand_tokens
    has_first = prof_first in cand_tokens

    if has_first and has_last:
        return True

    if has_last:
        others = [t for t in cand_tokens if t != prof_last]
        if not others:
            return True
        combined = ''.join([t[0] for t in others])
        if combined in valid_initial_combinations or any(t in valid_initial_combinations for t in others):
            return True
        if prof_first in others:
            return True

    if has_first:
        others = [t for t in cand_tokens if t != prof_first]
        if not others:
            return True
        combined = ''.join([t[0] for t in others])
        if combined in valid_initial_combinations or any(t in valid_initial_combinations for t in others):
            return True

    return False


def determine_author_status(profile_author_name: str, authors_str: str) -> str:
    """Menentukan apakah profil author berperan sebagai Penulis Pertama atau Penulis Anggota."""
    if not authors_str or authors_str.strip() in ['-', '']:
        return "Penulis Pertama"
    author_list = [a.strip() for a in authors_str.split(',') if a.strip()]
    if not author_list:
        return "Penulis Pertama"

    first_author = author_list[0]
    if is_same_author(first_author, profile_author_name):
        return "Penulis Pertama"
    return "Penulis Anggota"


# ==============================================================================
# 4. KLASIFIKASI JENIS JURNAL & AKREDITASI
# ==============================================================================

def is_international_publisher(publisher: str) -> bool:
    """Mengecek apakah penerbit adalah publisher internasional bereputasi."""
    if not publisher or str(publisher).strip() in ['-', '']:
        return False
    intl_publishers = [
        'ieee', 'institute of electrical and electronics engineers',
        'elsevier', 'springer', 'acm', 'wiley', 'nature publishing',
        'taylor & francis', 'sage', 'hindawi', 'mdpi', 'emerald', 'oxford university',
        'cambridge university', 'frontiers', 'aip', 'iop', 'sciencedirect', 'plos',
        'world scientific', 'degruyter', 'inderscience', 'bentham', 'aaas'
    ]
    p_lower = str(publisher).lower().strip()
    return any(p in p_lower for p in intl_publishers)


def detect_is_book(
    title: str = "",
    venue_name: str = "",
    publisher: str = "",
    fields_dict: Optional[Dict[str, str]] = None
) -> bool:
    """Mendeteksi secara cerdas apakah sebuah publikasi bertipe Buku atau Bab Buku (Book Chapter)
    berdasarkan sinyal field Google Scholar, format judul bab/buku, nama venue, dan penerbit."""
    fields = fields_dict or {}
    t = str(title or '').strip()
    t_lower = t.lower()
    v = str(venue_name or '').strip()
    v_lower = v.lower()
    p = str(publisher or '').strip()
    p_lower = p.lower()
    desc = str(fields.get('description') or fields.get('deskripsi') or '').strip().lower()

    # 1. Field resmi Google Scholar secara eksplisit menyebut buku atau ISBN
    explicit_book_fields = ['book', 'buku', 'isbn']
    if any(k in fields for k in explicit_book_fields):
        return True

    # 2. Judul artikel memiliki pola bab buku (Book Chapter)
    if re.search(r'^\s*(bab|chapter|bagian)\s+\d+', t, re.IGNORECASE):
        return True

    # 3. Indikator kuat bahwa publikasi adalah jurnal atau konferensi
    journal_indicators = [
        'jurnal', 'journal', 'berkala', 'bulletin', 'buletin', 'warta',
        'conference', 'proceedings', 'prosiding', 'symposium', 'seminar',
        'workshop', 'trans.', 'transactions', 'letters'
    ]
    has_journal_or_conf = (
        'journal' in fields or 'jurnal' in fields or
        'conference' in fields or 'konferensi' in fields or
        any(ji in v_lower for ji in journal_indicators)
    )
    if has_journal_or_conf:
        return False

    # 4. Judul artikel memuat kata kunci buku yang jelas (dan bukan di jurnal/konferensi)
    explicit_book_title_patterns = [
        r'\bbuku\s+ajar\b', r'\bbuku\s+teks\b', r'\bbuku\s+referensi\b',
        r'\bbuku\s+panduan\b', r'\bbuku\s+pedoman\b', r'\bbuku\s+saku\b',
        r'\bmonograf\b', r'\bbook\s+chapter\b', r'\bbunga\s+rampai\b',
        r'\bantologi\b', r'\bkapita\s+selekta\b'
    ]
    if any(re.search(pat, t_lower) for pat in explicit_book_title_patterns):
        return True

    # 5. Venue secara eksplisit memuat kata buku / monograf
    if any(bk in v_lower for bk in ['buku ajar', 'buku referensi', 'buku teks', 'monograf']):
        return True

    # 6. Deskripsi / Abstrak menyebut 'buku ini', 'buku ajar', 'this book', atau nomor ISBN
    book_desc_patterns = [
        r'\bbuku\s+ini\b', r'\bdalam\s+buku\s+ini\b', r'\bhadirnya\s+buku\s+ini\b',
        r'\bpenulisan\s+buku\s+ini\b', r'\bpenerbitan\s+buku\s+ini\b',
        r'\bbuku\s+ajar\s+ini\b', r'\bbuku\s+referensi\s+ini\b',
        r'\bthis\s+book\b', r'\bin\s+this\s+book\b', r'\bthis\s+textbook\b',
        r'\bisbn\s*:\s*[0-9\-]{9,}\b'
    ]
    if any(re.search(pat, desc) for pat in book_desc_patterns):
        return True

    # 7. Indikator Penerbit Buku (CV., PT., Penerbit, Pustaka, Percetakan, dsb.)
    book_publisher_keywords = [
        'cv.', 'cv ', 'pt.', 'pt ', 'ud.', 'penerbit', 'pustaka', 'percetakan', 'deepublish',
        'erlangga', 'gramedia', 'getpress', 'cendekia muslim', 'imtiyaz',
        'mediakita', 'mizan', 'prenada', 'prenadamedia', 'rajawali pers',
        'rajagrafindo', 'raja grafindo', 'salemba', 'bumi aksara', 'sinar grafika',
        'alumni', 'rekayasa sains', 'kanisius', 'andi offset', 'widina',
        'lakeisha', 'tahta media', 'bintang surya madani', 'media akademia',
        'ahlimedia', 'eureka media', 'literasi nusantara', 'insan cendekia',
        'samudra biru', 'kencana', 'alfabeta', 'graha ilmu', 'zahir publishing',
        'kita menulis', 'bintang pustaka'
    ]

    is_pub_book = any(k in p_lower for k in book_publisher_keywords)
    is_venue_book = any(k in v_lower for k in book_publisher_keywords)

    if is_pub_book or is_venue_book:
        return True

    return False


def determine_journal_type(
    venue_name: str,
    publisher: str = "",
    indexation: str = "",
    is_book: bool = False,
    title: str = ""
) -> str:
    """Menentukan jenis publikasi (Internasional vs Nasional vs Buku)."""
    if is_book or indexation == "Buku" or detect_is_book(title=title, venue_name=venue_name, publisher=publisher):
        return "Buku"

    if is_international_publisher(publisher):
        return "Internasional"

    if venue_name and lookup_scimago(venue_name):
        return "Internasional"

    if indexation:
        idx_lower = str(indexation).lower()
        if any(sc in idx_lower for sc in ['scopus', 'wos', 'web of science', 'prosiding internasional']):
            return "Internasional"
        if 'sinta' in idx_lower:
            return "Nasional"

    if not venue_name or venue_name.strip() in ['-', '']:
        return "Nasional"

    v = str(venue_name).lower()
    intl_keywords = [
        'international', 'ieee', 'acm', 'springer', 'elsevier', 'wiley', 'nature',
        'taylor & francis', 'sage', 'hindawi', 'mdpi', 'emerald',
        'conference', 'proceedings', 'symposium', 'trans.', 'transactions',
        'letters', 'journal of', 'bulletin of', 'annals of', 'advances in',
        'frontiers in', 'applied', 'computational', 'electronic', 'communications',
        'sensors', 'materials'
    ]
    nasional_keywords = [
        'jurnal', 'berkala', 'warta', 'prosiding seminar nasional', 'seminar nasional',
        'indonesia', 'ilmiah', 'teknik', 'pendidikan', 'rekayasa', 'komputasi',
        'saintek', 'teknologi', 'informatika', 'penelitian', 'masyarakat', 'kemendikbud'
    ]
    has_intl = any(k in v for k in intl_keywords)
    has_nas = any(k in v for k in nasional_keywords)
    if has_intl and not has_nas:
        return "Internasional"
    elif has_nas:
        return "Nasional"
    elif any(w in v.split() for w in ['the', 'and', 'for', 'in', 'on', 'with', 'systems', 'research', 'studies']):
        return "Internasional"
    return "Nasional"


SINTA_CACHE: Dict[str, Optional[str]] = {}
_sinta_session = requests.Session()
_sinta_session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
})


def is_sinta_journal_match(venue_name: str, sinta_title: str) -> bool:
    """Memverifikasi secara ketat apakah nama jurnal di portal SINTA benar-benar cocok
    dengan nama venue pada artikel Google Scholar (mencegah salah sasaran/false positive)."""
    if not venue_name or not sinta_title:
        return False

    def norm(s: str) -> str:
        s = re.sub(r'[^a-zA-Z0-9\s]', ' ', str(s).lower())
        return ' '.join(s.split())

    v_norm = norm(venue_name)
    s_norm = norm(sinta_title)

    if not v_norm or not s_norm:
        return False

    # 1. Kecocokan persis
    if v_norm == s_norm:
        return True

    # 2. Ekstraksi komponen sub-judul / akronim
    # Contoh SINTA: 'BioLink (Jurnal Biologi Lingkungan, Industri, Kesehatan)'
    parts_paren = re.findall(r'\((.*?)\)', sinta_title)
    outside_paren = re.sub(r'\(.*?\)', '', sinta_title).strip()
    parts_colon = [p.strip() for p in re.split(r'[:\-–]', sinta_title) if p.strip()]

    v_parts_paren = re.findall(r'\((.*?)\)', venue_name)
    v_outside_paren = re.sub(r'\(.*?\)', '', venue_name).strip()
    v_parts_colon = [p.strip() for p in re.split(r'[:\-–]', venue_name) if p.strip()]

    candidates_s = [sinta_title, outside_paren] + parts_paren + parts_colon
    candidates_v = [venue_name, v_outside_paren] + v_parts_paren + v_parts_colon

    for v_c in candidates_v:
        v_c_norm = norm(v_c)
        if not v_c_norm or len(v_c_norm) < 3:
            continue
        for s_c in candidates_s:
            s_c_norm = norm(s_c)
            if not s_c_norm or len(s_c_norm) < 3:
                continue
            if v_c_norm == s_c_norm:
                return True
            # Hapus prefiks 'jurnal' / 'journal'
            v_no_j = re.sub(r'^(jurnal|journal)\s+', '', v_c_norm)
            s_no_j = re.sub(r'^(jurnal|journal)\s+', '', s_c_norm)
            if v_no_j and s_no_j and v_no_j == s_no_j:
                return True

    # 3. Analisis kecocokan token kata dengan toleransi singkatan / prefiks
    def clean_tokens(text: str) -> List[str]:
        clean = re.sub(r'[^a-zA-Z0-9\s]', ' ', text.lower())
        clean = re.sub(r'\b(jurnal|journal|of|the|dan|and|indonesian|indonesia|j|in|for|on)\b', ' ', clean)
        return [w for w in clean.split() if len(w) >= 2]

    v_toks = clean_tokens(venue_name)
    s_toks = clean_tokens(sinta_title)

    if len(v_toks) >= 2 and len(s_toks) >= 2:
        def token_match(vt: str, st: str) -> bool:
            return vt == st or (len(vt) >= 3 and len(st) >= 3 and (vt.startswith(st) or st.startswith(vt)))

        matched_v = sum(1 for vt in v_toks if any(token_match(vt, st) for st in s_toks))
        matched_s = sum(1 for st in s_toks if any(token_match(st, vt) for vt in v_toks))

        v_ratio = matched_v / len(v_toks)
        s_ratio = matched_s / len(s_toks)
        # Kedua nama harus memiliki cakupan kata yang dominan (>= 75% venue dan >= 60% SINTA)
        if v_ratio >= 0.75 and s_ratio >= 0.60:
            return True

    return False


def lookup_sinta_accreditation(venue_name: str, title: str = "") -> Optional[str]:
    """Melakukan pencarian akreditasi jurnal nasional resmi (SINTA 1-6) di portal SINTA.
    Dilengkapi verifikasi kecocokan judul jurnal untuk mencegah salah sasaran (false positive)."""
    if not venue_name or venue_name.strip() in ['-', '']:
        return None

    v_lower = venue_name.lower().strip()

    # Jangan lakukan pencarian SINTA jika publikasi jelas merupakan buku / bab buku:
    if detect_is_book(title=title, venue_name=venue_name):
        return None

    # 2. Venue adalah buku, prosiding, tesis, skripsi, universitas, dsb.
    non_journal_indicators = [
        'buku', 'book', 'monograf', 'skripsi', 'tesis', 'disertasi', 'thesis',
        'dissertation', 'prosiding', 'proceeding', 'conference', 'seminar',
        'symposium', 'workshop', 'repository', 'laporan penelitian'
    ]
    if any(ind in v_lower for ind in non_journal_indicators):
        return None

    cache_key = v_lower
    if cache_key in SINTA_CACHE:
        return SINTA_CACHE[cache_key]

    candidates = []

    # 1. Bagian nama utama sebelum titik dua (e.g. 'Realita: Jurnal Penelitian...')
    if ':' in venue_name:
        col_part = venue_name.split(':')[0].strip()
        col_clean = re.sub(r'[^\w\s]', '', col_part).strip()
        if len(col_clean) >= 3 and col_clean.lower() not in ['jurnal', 'journal']:
            candidates.append(col_clean)

    # 2. Akronim sebelum kurung (e.g. 'JIPI (Jurnal IPA...')
    m_paren = re.match(r'^([A-Za-z0-9\s]{2,15})\s*\(', venue_name)
    if m_paren:
        acr = m_paren.group(1).strip()
        if len(acr) >= 3 and acr.lower() not in ['jurnal', 'journal']:
            candidates.append(acr)

    # 3. Nama bersih lengkap tanpa vol/no/hal/tahun
    no_par = re.sub(r'\(.*?\)', '', venue_name)
    no_par = re.sub(r'\b(vol|no|pp|hal|issue)\b.*', '', no_par, flags=re.IGNORECASE)
    no_par = re.sub(r'[\d,\.:-]', ' ', no_par).strip()
    full_clean = ' '.join(no_par.split())
    if full_clean and full_clean not in candidates:
        candidates.append(full_clean)

    # 4. Bagian dalam kurung
    for ip in re.findall(r'\((.*?)\)', venue_name):
        ip_clean = ' '.join(re.sub(r'[^\w\s]', '', ip).split())
        if len(ip_clean) >= 4 and ip_clean not in candidates and ip_clean.lower() not in ['jurnal', 'journal']:
            candidates.append(ip_clean)

    # 5. Kata pertama jika unik (e.g. 'ORBITA' dari 'ORBITA J. Pendidik...')
    words = full_clean.split()
    if words and len(words[0]) >= 4 and words[0].lower() not in [
        'jurnal', 'journal', 'berkala', 'warta', 'the', 'indonesian', 'international'
    ]:
        if words[0] not in candidates:
            candidates.append(words[0])

    for q in candidates:
        q_norm = q.lower().strip()
        if len(q_norm) < 3 or q_norm in ['jurnal', 'journal', 'indonesian journal', 'jurnal pendidikan']:
            continue

        try:
            url = f'https://sinta.kemdiktisaintek.go.id/journals?q={requests.utils.quote(q)}'
            resp = _sinta_session.get(url, timeout=5)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                links = soup.find_all('a', href=lambda h: h and '/journals/profile/' in h)
                for link in links[:5]:
                    sinta_title = link.text.strip()
                    # VERIFIKASI KETAT: hanya terima jika judul di SINTA cocok dengan venue_name
                    if is_sinta_journal_match(venue_name, sinta_title):
                        card = link.find_parent('div', class_='col-md') or link.find_parent('div', class_='row')
                        if card:
                            accred = card.find('span', class_=lambda c: c and 'accredited' in c)
                            if accred:
                                m = re.search(r'S([1-6])', accred.text, re.IGNORECASE)
                                if m:
                                    res = f'SINTA {m.group(1)}'
                                    SINTA_CACHE[cache_key] = res
                                    return res
                            m2 = re.search(r'\b(S[1-6])\b', card.text)
                            if m2:
                                res = f'SINTA {m2.group(1)[1]}'
                                SINTA_CACHE[cache_key] = res
                                return res
        except Exception:
            pass

    SINTA_CACHE[cache_key] = None
    return None


def determine_indexation(
    venue_name: str,
    journal_type: str = "",
    publisher: str = "",
    title: str = "",
    is_book: bool = False
) -> str:
    """Menentukan tingkat indeksasi artikel (Scopus Q1-Q4, SINTA 1-6, Prosiding, Buku, atau Nasional)."""
    # 0. Deteksi Buku / Bab Buku
    if is_book or journal_type == "Buku" or detect_is_book(title=title, venue_name=venue_name, publisher=publisher):
        return "Buku"

    v = str(venue_name or '').lower()
    p = str(publisher or '').lower()

    # 1. SCImagoJR 2025 Offline Scopus Matching
    sjr_match = lookup_scimago(venue_name)
    if sjr_match and sjr_match.get('status'):
        return sjr_match['status']

    # 2. Publisher Internasional Bereputasi
    is_intl = is_international_publisher(publisher) or any(sc in v for sc in ['ieee', 'acm', 'springer', 'elsevier'])
    is_proceedings = any(pr in v for pr in ['conference', 'proceedings', 'symposium', 'seminar', 'prosiding', 'workshop', 'icts', 'isitia', 'ieee', 'acm'])

    if is_intl:
        return "Scopus No-Q" if is_proceedings else "Scopus / WoS"

    # 3. Deteksi Prosiding (Prosiding bukan jurnal SINTA)
    if is_proceedings:
        if any(sc in v or sc in p for sc in ['ieee', 'acm', 'springer', 'iop', 'aip', 'scopus', 'icts', 'isitia', 'elsevier']):
            return "Scopus No-Q"
        return "Prosiding Internasional" if journal_type == "Internasional" else "-"

    # 4. Lookup SINTA 1-6 untuk jurnal lokal (hanya jika lolos verifikasi nama jurnal)
    if venue_name and str(venue_name).strip() not in ['-', '']:
        sinta_status = lookup_sinta_accreditation(venue_name, title=title)
        if sinta_status:
            return sinta_status

    # 5. Fallback (Jurnal nasional tanpa akreditasi SINTA ditulis '-')
    if journal_type == "Internasional":
        return "Internasional"
    return "-"


def detect_is_patent(
    title: str = "",
    venue_name: str = "",
    publisher: str = "",
    fields_dict: Optional[Dict[str, str]] = None
) -> bool:
    """Mendeteksi apakah artikel merupakan Paten atau Hak Kekayaan Intelektual."""
    fields = fields_dict or {}
    t = str(title or '').lower()
    v = str(venue_name or '').lower()
    p = str(publisher or '').lower()
    desc = str(fields.get('description') or fields.get('deskripsi') or '').lower()

    if any(k in fields for k in ['patent', 'paten', 'patent office', 'nomor paten', 'patent number']):
        return True

    patent_patterns = [
        r'\b(paten|patent|patents)\b',
        r'\b(hak cipta|hki|ha-ki)\b',
        r'\b(idp\s*000\d+|ids\s*000\d+)\b',
        r'\b(us\s*patent|ep\s*patent|wo\s*patent)\b',
        r'\b(kemenkumham|kekayaan intelektual|dirjen ki)\b'
    ]
    if any(re.search(pat, v) for pat in patent_patterns):
        return True
    if any(re.search(pat, p) for pat in patent_patterns):
        return True
    if any(re.search(pat, desc) for pat in [r'\b(paten|patent)\b', r'\b(idp\s*000\d+|ids\s*000\d+)\b']):
        return True
    if any(re.search(pat, t) for pat in [
        r'\b(paten sederhana|paten granted|us patent|nomor paten)\b',
        r'\b(idp\s*000\d+|ids\s*000\d+)\b'
    ]):
        return True
    return False


PUBLICATION_CATEGORIES = [
    "Jurnal Nasional",
    "Jurnal Nasional Terakreditasi (Sinta)",
    "Jurnal Internasional",
    "Jurnal Internasional Bereputasi (Scopus)",
    "Seminar Nasional",
    "Seminar Internasional",
    "Buku",
    "Paten"
]


def classify_publication_category(row: Dict[str, Any]) -> str:
    """Mengklasifikasikan artikel/publikasi ke dalam 8 kategori baku standar akreditasi:
    1. Jurnal Nasional
    2. Jurnal Nasional Terakreditasi (Sinta)
    3. Jurnal Internasional
    4. Jurnal Internasional Bereputasi (Scopus)
    5. Seminar Nasional
    6. Seminar Internasional
    7. Buku
    8. Paten
    """
    title = str(row.get('Judul Publikasi') or row.get('Judul') or '').strip()
    venue = str(row.get('Nama Jurnal / Prosiding') or row.get('Venue') or '').strip()
    j_type = str(row.get('Jenis Jurnal') or '').strip()
    idx = str(row.get('Terindeks') or '').strip()
    pub = str(row.get('Publisher') or '').strip()

    t_lower = title.lower()
    v_lower = venue.lower()
    i_lower = idx.lower()

    # 1. Paten
    if detect_is_patent(title=title, venue_name=venue, publisher=pub):
        return "Paten"

    # 2. Buku
    if j_type == "Buku" or idx == "Buku" or "buku" in i_lower:
        return "Buku"
    if detect_is_book(title=title, venue_name=venue, publisher=pub):
        return "Buku"

    # 3. Seminar / Prosiding (Seminar Nasional & Seminar Internasional)
    conf_kws = [
        'conference', 'proceedings', 'prosiding', 'symposium', 'seminar',
        'workshop', 'kongres', 'kolokium', 'annual meeting', 'icts', 'isitia',
        'snati', 'semnas', 'sntki', 'semnastek', 'pertemuan ilmiah'
    ]
    is_conf = (
        any(k in v_lower for k in conf_kws) or
        'prosiding' in i_lower or
        'no-q' in i_lower or
        'no-q' in v_lower
    )

    if is_conf:
        is_intl_conf = (
            'internasional' in i_lower or
            'scopus' in i_lower or
            j_type == 'Internasional' or
            any(k in v_lower for k in ['international', 'ieee', 'acm', 'springer', 'iop', 'aip', 'elsevier']) or
            is_international_publisher(pub)
        )
        is_explicit_national = (
            'seminar nasional' in v_lower or
            'prosiding nasional' in v_lower or
            'semnas' in v_lower or
            'nasional' in i_lower or
            i_lower == 'prosiding nasional'
        )
        if is_intl_conf and not is_explicit_national:
            return "Seminar Internasional"
        return "Seminar Nasional"

    # 4. Jurnal Nasional Terakreditasi (SINTA 1-6)
    if 'sinta' in i_lower:
        return "Jurnal Nasional Terakreditasi (Sinta)"

    # 5. Jurnal Internasional Bereputasi (Scopus / WoS / Q1-Q4)
    if any(q in i_lower for q in ['scopus', 'q1', 'q2', 'q3', 'q4', 'wos', 'web of science']):
        return "Jurnal Internasional Bereputasi (Scopus)"

    # 6. Jurnal Internasional
    if j_type == 'Internasional' or 'internasional' in i_lower:
        return "Jurnal Internasional"

    # 7. Jurnal Nasional (Non-akreditasi)
    return "Jurnal Nasional"



# ==============================================================================
# 5. MESIN SCRAPER UTAMA (SELENIUM CORE)
# ==============================================================================

class GoogleScholarScraper:
    """Kelas otomasi browser Selenium untuk scraping profil & publikasi Google Scholar."""

    def __init__(
        self,
        author_id: str,
        start_year: int = 2023,
        end_year: int = 2026,
        headless: bool = False,
        min_delay: float = 1.5,
        max_delay: float = 3.0,
        max_pubs: Optional[int] = None,
        on_log=None,
        on_progress=None,
        on_status=None,
        on_captcha=None,
        on_data_updated=None,
        on_author_found=None,
        stop_check=None
    ):
        self.author_id = extract_author_id(author_id)
        self.start_year = int(start_year)
        self.end_year = int(end_year)
        self.target_years = list(range(self.start_year, self.end_year + 1))
        self.headless = bool(headless)
        self.min_delay = float(min_delay)
        self.max_delay = float(max_delay)
        self.max_pubs = int(max_pubs) if (max_pubs and int(max_pubs) > 0) else None

        self.on_log = on_log or (lambda msg: print(f"[LOG] {msg}"))
        self.on_progress = on_progress or (lambda cur, tot, title: None)
        self.on_status = on_status or (lambda status: None)
        self.on_captcha = on_captcha or (lambda active: None)
        self.on_data_updated = on_data_updated or (lambda recs: None)
        self.on_author_found = on_author_found or (lambda full, first, path: None)
        self.stop_check = stop_check or (lambda: False)

        self.output_dir = OUTPUT_DIR
        os.makedirs(self.output_dir, exist_ok=True)

        self.author_name = self.author_id
        self.clean_first_name = self.author_id.lower()
        self.filename = f"{self.clean_first_name}_{self.start_year}_{self.end_year}.xlsx".lower()
        self.xlsx_file = os.path.join(self.output_dir, self.filename)

        self.driver: Optional[webdriver.Chrome] = None
        self.records: List[Dict[str, Any]] = []
        self.processed_titles: Set[str] = set()

    def log(self, msg: str):
        self.on_log(msg)

    def is_stopped(self) -> bool:
        return bool(self.stop_check and self.stop_check())

    def _interruptible_sleep(self, duration: float) -> bool:
        """Tidur dengan pengecekan status stop berkala setiap 0.1 detik agar responsif seketika."""
        step = 0.1
        elapsed = 0.0
        while elapsed < duration:
            if self.is_stopped():
                return False
            time.sleep(min(step, duration - elapsed))
            elapsed += step
        return not self.is_stopped()

    def save_data(self):
        """Menyimpan seluruh data yang telah diekstrak ke dalam berkas Excel terstruktur."""
        if not self.records:
            return
        try:
            os.makedirs(self.output_dir, exist_ok=True)
            df = pd.DataFrame(self.records)

            desired_order = [
                'No', 'Profil Dosen', 'Judul Publikasi', 'Penulis (Authors)', 'Status Penulis',
                'Nama Jurnal / Prosiding', 'Publisher', 'Jenis Jurnal', 'Terindeks',
                'Kategori Publikasi', 'Tanggal Terbit', 'Tahun', 'Vol/No/Hal'
            ]
            for yr in self.target_years:
                desired_order.append(f'Sitasi {yr}')
            desired_order.extend(['Total Sitasi Periode', 'Total Sitasi (All)', 'Link Artikel', 'DOI'])

            ordered_cols = [c for c in desired_order if c in df.columns] + [c for c in df.columns if c not in desired_order]
            df = df[ordered_cols]
            df.to_excel(self.xlsx_file, index=False)

            if self.on_data_updated:
                self.on_data_updated(list(self.records))
        except Exception as err:
            self.log(f"Peringatan: Gagal menyimpan berkas Excel: {err}")

    def load_checkpoint(self):
        """Mengecek berkas progres sebelumnya agar proses scraping bisa dilanjutkan (resume)."""
        candidates = [
            self.xlsx_file,
            os.path.join(self.output_dir, f"{self.clean_first_name}_{self.start_year}_{self.end_year}.xlsx".lower()),
            os.path.join(self.output_dir, f"{self.author_id}_{self.start_year}_{self.end_year}.xlsx".lower()),
            os.path.join(self.output_dir, f"scholar_{self.clean_first_name}_{self.start_year}_{self.end_year}.xlsx"),
            os.path.join(self.output_dir, f"scholar_{self.author_id}_{self.start_year}_{self.end_year}.xlsx")
        ]
        target_path = next((p for p in candidates if os.path.exists(p)), None)

        if target_path:
            try:
                existing_df = pd.read_excel(target_path)
                if 'Publisher' not in existing_df.columns:
                    existing_df['Publisher'] = '-'
                if 'Profil Dosen' not in existing_df.columns:
                    existing_df['Profil Dosen'] = self.author_name
                else:
                    existing_df['Profil Dosen'] = existing_df['Profil Dosen'].apply(
                        lambda x: standardize_author_name(str(x)) if pd.notna(x) else self.author_name
                    )
                if 'DOI' not in existing_df.columns:
                    existing_df['DOI'] = '-'

                self.records = existing_df.to_dict('records')
                for r in self.records:
                    title_val = r.get('Judul Publikasi') or r.get('Judul')
                    if title_val and pd.notna(title_val):
                        self.processed_titles.add(str(title_val).strip().lower())
                self.log(f"Checkpoint aktif: {len(self.records)} publikasi termuat dari {os.path.basename(target_path)}.")
                if self.on_data_updated:
                    self.on_data_updated(list(self.records))
            except Exception as err:
                self.log(f"Gagal membaca checkpoint ({err}). Memulai data baru.")

    def init_driver(self):
        """Menginisialisasi browser Chrome dengan Selenium WebDriver."""
        mode_str = 'Headless' if self.headless else 'Tampak'
        self.log(f"Mempersiapkan Chrome (Mode: {mode_str})...")

        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument('--headless=new')
            chrome_options.add_argument('--disable-gpu')
        else:
            chrome_options.add_argument('--start-maximized')

        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument(
            'user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        )

        self.driver = webdriver.Chrome(options=chrome_options)

    def wait_for_captcha_if_needed(self):
        """Mendeteksi apakah halaman Google Scholar menampilkan verifikasi robot CAPTCHA."""
        if not self.driver:
            return

        cur_url = self.driver.current_url.lower()
        src = self.driver.page_source.lower()
        is_captcha = (
            any(marker in cur_url for marker in ['sorry/index', 'recaptcha']) or
            ('recaptcha' in src and 'google.com' in cur_url)
        )

        if is_captcha:
            self.log("CAPTCHA terdeteksi di Google Scholar! Menunggu verifikasi...")
            self.on_captcha(True)
            self.on_status("Menunggu verifikasi robot di Chrome...")

            while True:
                if self.is_stopped():
                    break
                if not self._interruptible_sleep(2.0):
                    break
                cur_url = self.driver.current_url.lower()
                src = self.driver.page_source.lower()
                if 'sorry/index' not in cur_url and not ('recaptcha' in src and 'google.com/sorry' in cur_url):
                    self.log("CAPTCHA berhasil diverifikasi! Melanjutkan scraping...")
                    self.on_captcha(False)
                    self.on_status("Melanjutkan proses...")
                    self._interruptible_sleep(1.0)
                    break
        else:
            self.on_captcha(False)

    def _build_article_record(
        self,
        title: str,
        authors_str: str,
        venue_name: str,
        publisher_name: str,
        pub_year: str,
        pub_date: str,
        vol_no_hal: str,
        pub_url: str,
        total_cites: int,
        cites_per_year: Dict[int, int],
        fields_dict: Optional[Dict[str, str]] = None,
        doi: str = "-"
    ) -> Dict[str, Any]:
        """Helper terpadu untuk menyusun dictionary baris metadata artikel secara konsisten."""
        author_status = determine_author_status(self.author_name, authors_str)

        is_book = detect_is_book(
            title=title,
            venue_name=venue_name,
            publisher=publisher_name,
            fields_dict=fields_dict
        )

        if publisher_name in ['-', ''] and not is_book:
            scimago_info = lookup_scimago(venue_name)
            if scimago_info and scimago_info.get('publisher'):
                publisher_name = scimago_info['publisher']

        if is_book:
            journal_type = "Buku"
            indexation = "Buku"
        else:
            indexation = determine_indexation(
                venue_name,
                journal_type="",
                publisher=publisher_name,
                title=title,
                is_book=False
            )
            journal_type = determine_journal_type(
                venue_name,
                publisher=publisher_name,
                indexation=indexation,
                is_book=False,
                title=title
            )

            if journal_type == "Internasional" and indexation == "-":
                indexation = determine_indexation(
                    venue_name,
                    journal_type="Internasional",
                    publisher=publisher_name,
                    title=title,
                    is_book=False
                )

        total_range = sum(cites_per_year.get(yr, 0) for yr in self.target_years)

        pub_category = classify_publication_category({
            'Judul Publikasi': title,
            'Nama Jurnal / Prosiding': venue_name,
            'Jenis Jurnal': journal_type,
            'Terindeks': indexation,
            'Publisher': publisher_name
        })

        record = {
            'No': len(self.records) + 1,
            'Profil Dosen': self.author_name,
            'Judul Publikasi': title,
            'Penulis (Authors)': authors_str,
            'Status Penulis': author_status,
            'Nama Jurnal / Prosiding': venue_name,
            'Publisher': publisher_name,
            'Jenis Jurnal': journal_type,
            'Terindeks': indexation,
            'Kategori Publikasi': pub_category,
            'Tanggal Terbit': pub_date,
            'Tahun': pub_year,
            'Vol/No/Hal': vol_no_hal
        }

        for yr in self.target_years:
            record[f'Sitasi {yr}'] = cites_per_year.get(yr, 0)

        record['Total Sitasi Periode'] = total_range
        record['Total Sitasi (All)'] = total_cites
        record['Link Artikel'] = pub_url
        record['DOI'] = doi

        return record

    def run(self) -> List[Dict[str, Any]]:
        """Menjalankan seluruh alur kerja scraping profil Google Scholar dari awal hingga selesai."""
        self.init_driver()
        try:
            active_db_name = get_active_scimago_name()
            self.log(f"Menyiapkan database SCImagoJR ({active_db_name}) untuk deteksi Scopus Q1-Q4...")
            self.on_status(f"Memuat database SCImagoJR ({active_db_name})...")
            load_scimago_database()

            profile_url = f"https://scholar.google.com/citations?user={self.author_id}&hl=en&view_op=list_works&sortby=pubdate&pagesize=100"
            self.log(f"Membuka profil author (Urut pubdate terbaru): {profile_url}")
            self.on_status("Memuat halaman profil author...")
            self.driver.get(profile_url)
            self.wait_for_captcha_if_needed()

            if self.is_stopped():
                self.log("Proses dibatalkan sebelum memuat publikasi.")
                return self.records

            # Ekstrak Nama Author
            detected_name = ""
            try:
                name_elem = self.driver.find_element(By.ID, 'gsc_prf_in')
                detected_name = name_elem.text.strip()
            except Exception:
                pass

            if not detected_name and self.driver.title:
                raw_title = self.driver.title
                if '-' in raw_title:
                    detected_name = raw_title.split('-')[0].strip()
                elif 'Google' in raw_title:
                    detected_name = raw_title.replace('Google Scholar', '').replace('Google Cendekia', '').strip()

            if detected_name:
                self.author_name = standardize_author_name(detected_name)
            else:
                self.author_name = self.author_id
            first = extract_first_name(self.author_name)
            self.clean_first_name = re.sub(r'[^a-zA-Z0-9_-]', '', first).lower() if first else self.author_id.lower()
            if not self.clean_first_name:
                self.clean_first_name = self.author_id.lower()

            self.filename = f"{self.clean_first_name}_{self.start_year}_{self.end_year}.xlsx".lower()
            self.xlsx_file = os.path.join(self.output_dir, self.filename)

            self.log(f"Author: {self.author_name} (Nama File: {self.filename})")
            self.on_author_found(self.author_name, self.clean_first_name, self.xlsx_file)

            # Cek Checkpoint
            self.load_checkpoint()

            # Tunggu tabel publikasi termuat
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.ID, 'gsc_a_b'))
            )

            # Ekstrak publikasi halaman awal dari DOM Selenium
            self.on_status("Mengekstrak daftar publikasi profil...")
            pub_items = []
            rows = self.driver.find_elements(By.CSS_SELECTOR, 'tr.gsc_a_tr')
            for r in rows:
                try:
                    title_elem = r.find_element(By.CSS_SELECTOR, 'a.gsc_a_at')
                    title = title_elem.text.strip()
                    href = title_elem.get_attribute('href') or title_elem.get_attribute('data-href') or ''
                    if href.startswith('/'):
                        href = 'https://scholar.google.com' + href

                    gray_divs = r.find_elements(By.CSS_SELECTOR, 'div.gs_gray')
                    row_authors = gray_divs[0].text.strip() if len(gray_divs) > 0 else ''
                    row_venue = gray_divs[1].text.strip() if len(gray_divs) > 1 else ''

                    try:
                        year_elem = r.find_element(By.CSS_SELECTOR, 'span.gsc_a_h')
                        pub_year = year_elem.text.strip() or '-'
                    except Exception:
                        pub_year = '-'

                    try:
                        cites_elem = r.find_element(By.CSS_SELECTOR, 'a.gsc_a_ac')
                        cites_text = cites_elem.text.strip()
                        total_cites = int(cites_text) if cites_text.isdigit() else 0
                    except Exception:
                        total_cites = 0

                    pub_items.append({
                        'title': title,
                        'url': href,
                        'year': pub_year,
                        'total_cites': total_cites,
                        'row_authors': row_authors,
                        'row_venue': row_venue
                    })
                except Exception:
                    continue

            # Jika artikel mencapai 100 dan ada kemungkinan halaman lanjutan, lakukan paginasi cstart
            if len(pub_items) >= 100 and (not self.max_pubs or self.max_pubs > len(pub_items)):
                self.log(f"Ditemukan {len(pub_items)} publikasi di halaman pertama. Memeriksa halaman lanjutan...")
                
                # Gunakan requests.Session dengan cookies Selenium untuk paginasi cepat dan aman
                req_session = requests.Session()
                try:
                    for cookie in self.driver.get_cookies():
                        req_session.cookies.set(cookie['name'], cookie['value'])
                    ua = self.driver.execute_script("return navigator.userAgent;")
                    req_session.headers.update({
                        'User-Agent': ua or "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                        'Accept-Language': 'en-US,en;q=0.9',
                    })
                except Exception:
                    pass

                cstart = len(pub_items)
                while True:
                    if self.is_stopped():
                        break
                    if self.max_pubs and len(pub_items) >= self.max_pubs:
                        break

                    self.on_status(f"Memuat daftar publikasi lanjutan ({cstart + 1}+)...")
                    next_url = f"https://scholar.google.com/citations?user={self.author_id}&hl=en&sortby=pubdate&cstart={cstart}&pagesize=100"
                    
                    fetched_batch = 0
                    try:
                        resp = req_session.get(next_url, timeout=15)
                        if resp.status_code == 200:
                            soup = BeautifulSoup(resp.text, 'html.parser')
                            next_rows = soup.select('tr.gsc_a_tr')
                            fetched_batch = len(next_rows)
                            for r in next_rows:
                                title_elem = r.select_one('a.gsc_a_at')
                                if not title_elem:
                                    continue
                                title = title_elem.get_text(strip=True)
                                href = title_elem.get('href', '') or title_elem.get('data-href', '')
                                if href.startswith('/'):
                                    href = 'https://scholar.google.com' + href

                                gray_divs = r.select('div.gs_gray')
                                row_authors = gray_divs[0].get_text(strip=True) if len(gray_divs) > 0 else ''
                                row_venue = gray_divs[1].get_text(strip=True) if len(gray_divs) > 1 else ''

                                year_elem = r.select_one('span.gsc_a_h')
                                pub_year = year_elem.get_text(strip=True) if year_elem else '-'

                                cites_elem = r.select_one('a.gsc_a_ac')
                                cites_text = cites_elem.get_text(strip=True) if cites_elem else ''
                                total_cites = int(cites_text) if cites_text.isdigit() else 0

                                pub_items.append({
                                    'title': title,
                                    'url': href,
                                    'year': pub_year,
                                    'total_cites': total_cites,
                                    'row_authors': row_authors,
                                    'row_venue': row_venue
                                })
                                if self.max_pubs and len(pub_items) >= self.max_pubs:
                                    break
                    except Exception as http_err:
                        self.log(f"Paginasi HTTP ({http_err}), mencoba via browser...")
                        try:
                            self.driver.get(next_url)
                            self.wait_for_captcha_if_needed()
                            br_rows = self.driver.find_elements(By.CSS_SELECTOR, 'tr.gsc_a_tr')
                            fetched_batch = len(br_rows)
                            for r in br_rows:
                                try:
                                    title_elem = r.find_element(By.CSS_SELECTOR, 'a.gsc_a_at')
                                    title = title_elem.text.strip()
                                    href = title_elem.get_attribute('href') or title_elem.get_attribute('data-href') or ''
                                    if href.startswith('/'):
                                        href = 'https://scholar.google.com' + href

                                    gray_divs = r.find_elements(By.CSS_SELECTOR, 'div.gs_gray')
                                    row_authors = gray_divs[0].text.strip() if len(gray_divs) > 0 else ''
                                    row_venue = gray_divs[1].text.strip() if len(gray_divs) > 1 else ''

                                    try:
                                        year_elem = r.find_element(By.CSS_SELECTOR, 'span.gsc_a_h')
                                        pub_year = year_elem.text.strip() or '-'
                                    except Exception:
                                        pub_year = '-'

                                    try:
                                        cites_elem = r.find_element(By.CSS_SELECTOR, 'a.gsc_a_ac')
                                        cites_text = cites_elem.text.strip()
                                        total_cites = int(cites_text) if cites_text.isdigit() else 0
                                    except Exception:
                                        total_cites = 0

                                    pub_items.append({
                                        'title': title,
                                        'url': href,
                                        'year': pub_year,
                                        'total_cites': total_cites,
                                        'row_authors': row_authors,
                                        'row_venue': row_venue
                                    })
                                    if self.max_pubs and len(pub_items) >= self.max_pubs:
                                        break
                                except Exception:
                                    continue
                        except Exception as br_err:
                            self.log(f"Paginasi browser gagal: {br_err}")
                            break

                    self.log(f"Paginasi lanjutan (cstart={cstart}): berhasil membaca {fetched_batch} publikasi.")
                    if fetched_batch < 100:
                        break
                    cstart += fetched_batch
                    if not self._interruptible_sleep(1.0):
                        break

            # Deduplikasi artikel (menjaga urutan waktu)
            seen_identifiers = set()
            dedup_items = []
            for item in pub_items:
                ident = item['url'] if item['url'] else item['title'].lower()
                if ident not in seen_identifiers:
                    seen_identifiers.add(ident)
                    dedup_items.append(item)
            pub_items = dedup_items

            total_pubs_found = len(pub_items)
            self.log(f"Berhasil menemukan total {total_pubs_found} publikasi di profil.")

            if self.max_pubs and self.max_pubs < len(pub_items):
                pub_items = pub_items[:self.max_pubs]
                self.log(f"Batas artikel aktif: memproses {len(pub_items)} artikel.")

            total_to_process = len(pub_items)
            self.log(f"Memproses rincian sitasi {self.start_year} - {self.end_year} ({total_to_process} artikel)...")

            for idx, item in enumerate(pub_items, 1):
                if self.is_stopped():
                    self.log(f"Pengguna menghentikan proses pada artikel #{idx}.")
                    self.on_status("Proses dihentikan.")
                    break

                title = item['title']
                total_cites = item['total_cites']
                pub_year = item['year']
                pub_url = item['url']
                row_authors = item['row_authors']
                row_venue = item['row_venue']

                self.on_progress(idx, total_to_process, title)
                self.on_status(f"Memproses ({idx}/{total_to_process}): {title[:40]}...")

                if title.lower() in self.processed_titles:
                    self.log(f"[{idx}/{total_to_process}] [SUDAH ADA] Dilewati: {title[:45]}...")
                    continue

                cites_per_year: Dict[int, int] = {yr: 0 for yr in self.target_years}
                authors_str = row_authors or '-'
                venue_name = row_venue or '-'
                publisher_name = '-'
                pub_date = format_to_dd_mm_yyyy(pub_year, fallback_year=pub_year)
                vol_no_hal = '-'

                try:
                    self.driver.get(pub_url)
                    self.wait_for_captcha_if_needed()
                    if self.is_stopped():
                        break

                    if not self._interruptible_sleep(random.uniform(self.min_delay, self.max_delay)):
                        break
                    soup = BeautifulSoup(self.driver.page_source, 'html.parser')

                    t_elem = soup.find('div', id='gsc_oci_title')
                    if t_elem:
                        title = t_elem.text.strip()

                    fields_dict = {}
                    for scl in soup.find_all('div', class_='gs_scl'):
                        f_el = scl.find('div', class_='gsc_oci_field')
                        v_el = scl.find('div', class_='gsc_oci_value')
                        if f_el and v_el:
                            fields_dict[f_el.text.strip().lower()] = v_el.text.strip()

                    authors_str = fields_dict.get('authors') or fields_dict.get('penulis') or authors_str
                    publisher_name = fields_dict.get('publisher') or fields_dict.get('penerbit') or '-'

                    venue_detail = (
                        fields_dict.get('journal') or fields_dict.get('jurnal') or
                        fields_dict.get('conference') or fields_dict.get('konferensi') or
                        fields_dict.get('source') or fields_dict.get('sumber') or
                        fields_dict.get('book') or fields_dict.get('buku')
                    )
                    if venue_detail:
                        venue_name = venue_detail
                    elif publisher_name != '-' and venue_name in ['-', '']:
                        venue_name = publisher_name

                    raw_pub_date = (
                        fields_dict.get('publication date') or fields_dict.get('tanggal publikasi') or
                        fields_dict.get('tanggal terbit') or fields_dict.get('date') or
                        fields_dict.get('tanggal') or ''
                    )
                    if raw_pub_date:
                        m_yr = re.search(r'\b(19\d{2}|20\d{2})\b', raw_pub_date)
                        if m_yr:
                            pub_year = m_yr.group(1)

                    pub_date = format_to_dd_mm_yyyy(raw_pub_date or pub_year, fallback_year=pub_year)

                    vol = fields_dict.get('volume', '') or fields_dict.get('jilid', '')
                    iss = fields_dict.get('issue', '') or fields_dict.get('edisi', '') or fields_dict.get('terbitan', '')
                    pages = fields_dict.get('pages', '') or fields_dict.get('halaman', '')
                    vol_parts = []
                    if vol:
                        vol_parts.append(f"Vol. {vol}")
                    if iss:
                        vol_parts.append(f"No. {iss}")
                    if pages:
                        vol_parts.append(f"pp. {pages}")
                    if vol_parts:
                        vol_no_hal = ", ".join(vol_parts)

                    if total_cites > 0:
                        years = [int(y.text) for y in soup.find_all(class_='gsc_oci_g_t') if y.text.strip().isdigit()]
                        cites = [int(c.text) for c in soup.find_all(class_='gsc_oci_g_al') if c.text.strip().isdigit()]
                        cites_year = []
                        for c in soup.find_all(class_='gsc_oci_g_a'):
                            h = c.get('href', '')
                            m = re.search(r'cit_year=(\d{4})', h) or re.search(r'(\d{4})$', h)
                            if m:
                                cites_year.append(int(m.group(1)))

                        nonzero = dict(zip(cites_year, cites))
                        for y in years:
                            if y in cites_per_year:
                                cites_per_year[y] = nonzero.get(y, 0)

                    doi_val = extract_doi(
                        fields_dict=fields_dict,
                        soup=soup,
                        raw_html=self.driver.page_source if self.driver else "",
                        title=title
                    )

                    record = self._build_article_record(
                        title=title,
                        authors_str=authors_str,
                        venue_name=venue_name,
                        publisher_name=publisher_name,
                        pub_year=pub_year,
                        pub_date=pub_date,
                        vol_no_hal=vol_no_hal,
                        pub_url=pub_url,
                        total_cites=total_cites,
                        cites_per_year=cites_per_year,
                        fields_dict=fields_dict,
                        doi=doi_val
                    )
                    self.records.append(record)
                    self.processed_titles.add(title.strip().lower())
                    self.save_data()

                    tag = "0 SITASI" if total_cites == 0 else "BERHASIL"
                    doi_info = f" | DOI: {record['DOI']}" if record['DOI'] != '-' else ""
                    self.log(
                        f"[{idx}/{total_to_process}] [{tag}] {title[:35]}... "
                        f"({record['Status Penulis']} | {record['Jenis Jurnal']} | {record['Terindeks']}{doi_info} | "
                        f"Sitasi {self.start_year}-{self.end_year}: {record['Total Sitasi Periode']})"
                    )
                    if not self._interruptible_sleep(random.uniform(self.min_delay, self.max_delay)):
                        break

                except Exception as ex:
                    self.log(f"Gagal memuat detail {title[:30]}... ({ex}). Menyimpan metadata dasar.")
                    fallback_doi = lookup_crossref_doi(title=title, min_similarity=0.95)
                    fallback_record = self._build_article_record(
                        title=title,
                        authors_str=authors_str,
                        venue_name=venue_name,
                        publisher_name=publisher_name,
                        pub_year=pub_year,
                        pub_date=pub_date,
                        vol_no_hal=vol_no_hal,
                        pub_url=pub_url,
                        total_cites=total_cites,
                        cites_per_year=cites_per_year,
                        fields_dict=None,
                        doi=fallback_doi
                    )
                    self.records.append(fallback_record)
                    self.processed_titles.add(title.strip().lower())
                    self.save_data()
                    if not self._interruptible_sleep(1.0):
                        break

        except Exception as e:
            self.log(f"Error saat scraping: {e}")
        finally:
            self.save_data()
            if self.driver:
                try:
                    self.driver.quit()
                except Exception:
                    pass
                self.driver = None

        if self.is_stopped():
            self.on_status("Proses dihentikan. Data tersimpan.")
        else:
            self.on_status(f"Selesai! {len(self.records)} publikasi berhasil direkap.")
            self.log(f"Scraping selesai. Total {len(self.records)} publikasi tersimpan di {self.xlsx_file}.")

        return self.records


# ==============================================================================
# 6. PENGELOLA BACKGROUND THREAD (JOB MANAGER UNTUK STREAMLIT)
# ==============================================================================

class ScrapingJob:
    """Mengelola thread eksekusi scraper dan sinkronisasi status UI,
    mendukung scraping profil tunggal maupun batch (banyak ID/URL)."""

    def __init__(
        self,
        author_id: Union[str, List[str]],
        start_year: int = 2023,
        end_year: int = 2026,
        headless: bool = False,
        min_delay: float = 1.5,
        max_delay: float = 3.0,
        max_pubs: Optional[int] = None
    ):
        if isinstance(author_id, list):
            raw_ids = [extract_author_id(a) for a in author_id if a and extract_author_id(a)]
            # Buat unik berurutan
            seen = set()
            self.author_ids = []
            for rid in raw_ids:
                if rid not in seen:
                    seen.add(rid)
                    self.author_ids.append(rid)
        else:
            extracted = extract_author_id(author_id)
            self.author_ids = [extracted] if extracted else []

        self.is_batch = len(self.author_ids) > 1
        self.total_authors = len(self.author_ids)
        self.current_author_idx = 0

        self.author_id = self.author_ids[0] if self.author_ids else ""
        self.start_year = start_year
        self.end_year = end_year
        self.headless = headless
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.max_pubs = max_pubs

        self.output_dir = OUTPUT_DIR
        self.author_name = self.author_id
        self.clean_first_name = self.author_id.lower()
        self.filename = f"{self.clean_first_name}_{self.start_year}_{self.end_year}.xlsx".lower()
        self.xlsx_file = os.path.join(self.output_dir, self.filename)

        self.is_running = False
        self.stop_requested = False
        self.is_captcha = False
        self.status = "Siap dimulai..."
        self.current_idx = 0
        self.total_pubs = 0
        self.current_title = ""
        self.logs: List[str] = []
        self.records: List[Dict[str, Any]] = []
        self.batch_results: List[Dict[str, Any]] = []
        self.active_scraper: Optional[GoogleScholarScraper] = None
        self.error_message: Optional[str] = None
        self.thread: Optional[threading.Thread] = None

    def add_log(self, msg: str):
        time_str = datetime.now().strftime("%H:%M:%S")
        self.logs.append(f"[{time_str}] {msg}")
        if len(self.logs) > 300:
            self.logs = self.logs[-300:]

    def _on_author_found_batch(self, a_idx: int, full_name: str, first_name: str, path: str):
        if not self.is_batch:
            self.author_name = full_name
            self.clean_first_name = first_name
            self.filename = os.path.basename(path)
            self.xlsx_file = path

    def _update_progress(self, cur: int, tot: int, title: str):
        self.current_idx = cur
        self.total_pubs = tot
        self.current_title = title

    def _on_current_data_updated(
        self,
        a_idx: int,
        aid: str,
        current_author_records: List[Dict[str, Any]],
        all_accumulated: List[Dict[str, Any]]
    ):
        if self.is_batch:
            a_name = getattr(self.active_scraper, 'author_name', aid)
            cur_labeled = []
            for r in current_author_records:
                rc = dict(r)
                if 'Profil Dosen' not in rc:
                    rc['Profil Dosen'] = a_name
                cur_labeled.append(rc)
            self.records = list(all_accumulated) + cur_labeled
        else:
            self.records = list(current_author_records)

    def _worker(self):
        self.is_running = True
        self.stop_requested = False
        self.batch_results = []
        self.records = []
        all_accumulated_records = []

        total_authors = len(self.author_ids)
        if total_authors == 0:
            self.status = "Tidak ada ID author valid yang diberikan."
            self.is_running = False
            return

        self.add_log(f"Memulai tugas scraping ({total_authors} profil dosen, Periode {self.start_year}-{self.end_year}).")

        try:
            for a_idx, aid in enumerate(self.author_ids, 1):
                if self.stop_requested:
                    break

                self.current_author_idx = a_idx
                self.author_id = aid
                self.current_idx = 0
                self.total_pubs = 0
                self.current_title = ""

                tag_prefix = f"[Dosen {a_idx}/{total_authors}] " if self.is_batch else ""
                self.status = f"{tag_prefix}Menghubungkan ke profil Google Scholar ({aid})..."
                self.add_log(f"{tag_prefix}Memulai proses untuk Author ID: {aid}")

                scraper = GoogleScholarScraper(
                    author_id=aid,
                    start_year=self.start_year,
                    end_year=self.end_year,
                    headless=self.headless,
                    min_delay=self.min_delay,
                    max_delay=self.max_delay,
                    max_pubs=self.max_pubs,
                    on_log=lambda m: self.add_log(f"{tag_prefix}{m}"),
                    on_progress=lambda cur, tot, title: self._update_progress(cur, tot, title),
                    on_status=lambda s: setattr(self, 'status', f"{tag_prefix}{s}"),
                    on_captcha=lambda c: setattr(self, 'is_captcha', c),
                    on_data_updated=lambda r: self._on_current_data_updated(a_idx, aid, r, all_accumulated_records),
                    on_author_found=lambda full, first, path: self._on_author_found_batch(a_idx, full, first, path),
                    stop_check=lambda: self.stop_requested
                )
                self.active_scraper = scraper
                author_records = scraper.run()
                self.active_scraper = None

                author_info = {
                    'index': a_idx,
                    'author_id': aid,
                    'author_name': scraper.author_name,
                    'clean_first_name': scraper.clean_first_name,
                    'total_pubs': len(author_records),
                    'xlsx_file': scraper.xlsx_file,
                    'filename': scraper.filename,
                    'records': list(author_records)
                }
                self.batch_results.append(author_info)

                labeled_records = []
                for rec in author_records:
                    rec_copy = dict(rec)
                    if 'Profil Dosen' not in rec_copy:
                        rec_copy['Profil Dosen'] = scraper.author_name
                    labeled_records.append(rec_copy)
                all_accumulated_records.extend(labeled_records)

                if self.is_batch:
                    self.records = list(all_accumulated_records)
                else:
                    self.records = list(author_records)
                    self.xlsx_file = scraper.xlsx_file
                    self.filename = scraper.filename
                    self.author_name = scraper.author_name
                    self.clean_first_name = scraper.clean_first_name

                self.add_log(f"{tag_prefix}Selesai: {len(author_records)} publikasi dari {scraper.author_name} berhasil direkap.")

                if self.stop_requested:
                    break

        except Exception as e:
            self.error_message = str(e)
            self.add_log(f"Error tidak terduga: {e}")
            self.status = f"Terjadi kesalahan: {e}"
        finally:
            self.is_running = False
            self.is_captcha = False
            self.active_scraper = None
            if self.stop_requested:
                self.status = "Proses dihentikan oleh pengguna. Data yang telah diproses tersimpan."
            else:
                if self.is_batch:
                    done_count = len(self.batch_results)
                    total_p = len(self.records)
                    self.status = f"Selesai! {done_count} dosen ({total_p} publikasi) tersimpan di berkas masing-masing."
                else:
                    self.status = f"Selesai! {len(self.records)} publikasi tersimpan di {self.filename}."

    def start(self):
        if self.is_running:
            return
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()

    def stop(self, wait: bool = False, timeout: float = 2.0):
        self.stop_requested = True
        self.add_log("Permintaan stop diterima. Menyimpan data Excel dan menutup browser...")
        if wait and self.thread and self.thread.is_alive():
            self.thread.join(timeout=timeout)
            if not self.thread.is_alive():
                self.is_running = False
