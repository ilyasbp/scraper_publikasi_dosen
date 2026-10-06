@echo off
title Scraper Publikasi Dosen (Google Scholar)
cd /d "%~dp0"

echo ==========================================================
echo    SCRAPER PUBLIKASI & AKREDITASI DOSEN (SCHOLAR)
echo ==========================================================
echo Memeriksa kelengkapan sistem di komputer Anda...
echo.

:: 1. Pengecekan Google Chrome
set CHROME_FOUND=0
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" set CHROME_FOUND=1
if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" set CHROME_FOUND=1
if exist "%LocalAppData%\Google\Chrome\Application\chrome.exe" set CHROME_FOUND=1

if "%CHROME_FOUND%"=="0" (
    echo [INFO] Google Chrome belum ditemukan di komputer Anda.
    echo [INFO] Mengunduh dan memasang Google Chrome otomatis...
    where winget >nul 2>&1
    if %errorlevel% equ 0 (
        winget install --id Google.Chrome -e --silent --accept-source-agreements --accept-package-agreements
    ) else (
        powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; (New-Object Net.WebClient).DownloadFile('https://dl.google.com/chrome/install/latest/chrome_installer.exe', '%TEMP%\chrome_setup.exe'); Start-Process -FilePath '%TEMP%\chrome_setup.exe' -ArgumentList '/silent /install' -Wait; Remove-Item '%TEMP%\chrome_setup.exe' -Force"
    )
    echo [OK] Selesai memproses instalasi Google Chrome.
) else (
    echo [OK] Google Chrome sudah terpasang.
)

:: 2. Pengecekan Python
set PYTHON_CMD=python
python -c "import sys" >nul 2>&1
if %errorlevel% neq 0 (
    py -c "import sys" >nul 2>&1
    if %errorlevel% equ 0 (
        set PYTHON_CMD=py
    ) else (
        echo [INFO] Python belum ditemukan di sistem Anda.
        echo [INFO] Mengunduh dan memasang Python 3 resmi otomatis...
        where winget >nul 2>&1
        if %errorlevel% equ 0 (
            winget install --id Python.Python.3.11 -e --silent --accept-source-agreements --accept-package-agreements
        ) else (
            powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; (New-Object Net.WebClient).DownloadFile('https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe', '%TEMP%\python_setup.exe'); Start-Process -FilePath '%TEMP%\python_setup.exe' -ArgumentList '/quiet InstallAllUsers=0 PrependPath=1 Include_test=0' -Wait; Remove-Item '%TEMP%\python_setup.exe' -Force"
        )
        :: Refresh PATH di sesi Command Prompt saat ini
        set "PATH=%LOCALAPPDATA%\Programs\Python\Python311;%LOCALAPPDATA%\Programs\Python\Python311\Scripts;%PATH%"
        set PYTHON_CMD=python
        echo [OK] Selesai memasang Python.
    )
)

if "%PYTHON_CMD%"=="" set PYTHON_CMD=python
echo [OK] Python siap digunakan.

:: 3. Pengecekan dan Instalasi Pustaka (requirements.txt)
echo Memeriksa kelengkapan dependensi pustaka Python...
%PYTHON_CMD% -c "import streamlit, selenium, pandas, openpyxl, bs4, plotly" >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Mengunduh dan menginstal pustaka dari requirements.txt...
    %PYTHON_CMD% -m pip install --upgrade pip >nul 2>&1
    %PYTHON_CMD% -m pip install -r requirements.txt
    echo [OK] Semua paket berhasil dipasang!
) else (
    echo [OK] Semua paket pustaka sudah lengkap.
)

:: 4. Nonaktifkan Prompt Email Streamlit
if not exist "%USERPROFILE%\.streamlit" mkdir "%USERPROFILE%\.streamlit" >nul 2>&1
if not exist "%USERPROFILE%\.streamlit\credentials.toml" (
    (
        echo [general]
        echo email = ""
    ) > "%USERPROFILE%\.streamlit\credentials.toml"
)

:: 5. Jalankan Aplikasi Web
echo.
echo Membuka aplikasi web di browser (http://localhost:8501)...
%PYTHON_CMD% -m streamlit run app.py --server.showEmailPrompt=false --browser.gatherUsageStats=false
pause
