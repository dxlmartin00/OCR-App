@echo off
setlocal enabledelayedexpansion
title LIGER Setup

echo ===================================================
echo        LIGER OCR Application - Setup in Progress
echo ===================================================
echo.

:: === Step 1: Check for Python ===
echo [1/3] Checking for Python installation...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python not found.
    echo Downloading latest Python installer...

    curl -# -o python-installer.exe https://www.python.org/ftp/python/3.12.2/python-3.12.2-amd64.exe

    echo Installing Python silently...
    start /wait python-installer.exe /quiet InstallAllUsers=1 PrependPath=1 Include_pip=1

    echo Verifying Python installation...
    timeout /t 10 >nul
) else (
    echo Python is already installed.
)

:: Refresh PATH for this session
set "PATH=%PATH%;C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python312\Scripts"

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python still not found after installation.
    echo Please restart your PC or check your PATH environment variable.
    pause
    exit /b
)

:: === Step 2: Install Required Python Packages ===
echo.
echo [2/3] Installing required Python packages...

set PACKAGES=PyQt6 easyocr pillow piexif

for %%P in (%PACKAGES%) do (
    echo.
    echo Checking %%P...
    py -m pip show %%P >nul 2>&1
    if !errorlevel! neq 0 (
        echo Installing %%P...
        py -m pip install %%P
    ) else (
        echo %%P is already installed.
    )
)

:: === Step 3: Create LIGER.bat ===
echo.
echo [3/3] Creating launcher: LIGER.bat

(
    echo @echo off
    echo title LIGER OCR App
    echo echo Running LIGER OCR...
    echo py main.py
    echo pause
) > LIGER.bat

:: === Done ===
echo.
echo ===================================================
echo   Setup complete! Run LIGER.bat to start the app.
echo ===================================================
pause
exit /b
