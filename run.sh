#!/usr/bin/env bash
# ==============================================================================
# Script Peluncur Otomatis Google Scholar Scraper (macOS & Linux)
# Otomatis mendeteksi, mengunduh, dan memasang Google Chrome, Python, serta pustaka.
# ==============================================================================

cd "$(dirname "$0")"

echo "=========================================================="
echo "    SCRAPER PUBLIKASI & AKREDITASI DOSEN (SCHOLAR)        "
echo "=========================================================="
echo "Memeriksa kelengkapan sistem di komputer Anda..."

# 1. Pengecekan Google Chrome
CHROME_APP="/Applications/Google Chrome.app"
CHROME_USER_APP="$HOME/Applications/Google Chrome.app"

if [ ! -d "$CHROME_APP" ] && [ ! -d "$CHROME_USER_APP" ]; then
    echo ""
    echo "[INFO] Google Chrome belum ditemukan di komputer Anda."
    echo "[INFO] Mengunduh Google Chrome resmi untuk macOS..."
    TEMP_DMG="/tmp/googlechrome.dmg"
    MOUNT_DIR="/tmp/chrome_mount"

    if curl -L -f -o "$TEMP_DMG" "https://dl.google.com/chrome/mac/universal/stable/GGRO/googlechrome.dmg"; then
        echo "[INFO] Memasang Google Chrome ke folder Applications..."
        mkdir -p "$MOUNT_DIR"
        hdiutil attach "$TEMP_DMG" -mountpoint "$MOUNT_DIR" -nobrowse -quiet
        
        if [ -d "$MOUNT_DIR/Google Chrome.app" ]; then
            cp -R "$MOUNT_DIR/Google Chrome.app" /Applications/ 2>/dev/null || {
                mkdir -p "$HOME/Applications"
                cp -R "$MOUNT_DIR/Google Chrome.app" "$HOME/Applications/"
            }
            echo "[OK] Google Chrome berhasil dipasang."
        fi
        
        hdiutil detach "$MOUNT_DIR" -quiet 2>/dev/null
        rm -rf "$TEMP_DMG" "$MOUNT_DIR"
    else
        echo "[WARN] Gagal mengunduh Chrome otomatis. Pastikan Google Chrome terpasang di komputer Anda."
    fi
else
    echo "[OK] Google Chrome sudah terpasang."
fi

# 2. Pengecekan Python 3
PYTHON_CMD="python3"
if ! command -v "$PYTHON_CMD" &> /dev/null || ! "$PYTHON_CMD" -c "import sys" &> /dev/null; then
    echo ""
    echo "[INFO] Python 3 belum ditemukan di sistem."
    echo "[INFO] Mengunduh installer resmi Python 3 untuk macOS..."
    PKG_PATH="/tmp/python_installer.pkg"
    
    if curl -L -f -o "$PKG_PATH" "https://www.python.org/ftp/python/3.11.9/python-3.11.9-macos11.pkg"; then
        echo "[INFO] Membuka wizard installer Python. Silakan ikuti instruksi di layar komputer Anda..."
        open "$PKG_PATH"
        read -p "Tekan [Enter] di sini setelah Anda selesai menginstal Python..."
        
        if command -v python3 &> /dev/null; then
            PYTHON_CMD="python3"
        elif [ -x "/usr/local/bin/python3" ]; then
            PYTHON_CMD="/usr/local/bin/python3"
        elif [ -x "/Library/Frameworks/Python.framework/Versions/3.11/bin/python3" ]; then
            PYTHON_CMD="/Library/Frameworks/Python.framework/Versions/3.11/bin/python3"
        fi
    else
        echo "[WARN] Gagal mengunduh installer Python otomatis. Silakan unduh di https://www.python.org/downloads/"
    fi
else
    echo "[OK] Python 3 sudah terpasang ($($PYTHON_CMD --version))."
fi

# 3. Pengecekan dan Instalasi Pustaka (requirements.txt)
echo "Memeriksa kelengkapan dependensi pustaka Python..."
"$PYTHON_CMD" -c "import streamlit, selenium, pandas, openpyxl, bs4, plotly" &> /dev/null

if [ $? -ne 0 ]; then
    echo "[INFO] Mengunduh dan menginstal pustaka yang dibutuhkan dari requirements.txt..."
    "$PYTHON_CMD" -m pip install --upgrade pip &> /dev/null
    "$PYTHON_CMD" -m pip install -r requirements.txt || pip3 install -r requirements.txt || pip install -r requirements.txt
    echo "[OK] Seluruh pustaka berhasil diinstal."
else
    echo "[OK] Seluruh pustaka sudah lengkap dan siap digunakan."
fi

# 4. Konfigurasi Streamlit (Nonaktifkan prompt email)
mkdir -p ~/.streamlit 2>/dev/null
if [ ! -f ~/.streamlit/credentials.toml ]; then
    printf '[general]\nemail = ""\n' > ~/.streamlit/credentials.toml 2>/dev/null
fi

# 5. Jalankan Aplikasi Web
echo ""
echo "Membuka aplikasi web di browser (http://localhost:8501)..."
"$PYTHON_CMD" -m streamlit run app.py --server.headless=false --server.showEmailPrompt=false --browser.gatherUsageStats=false
