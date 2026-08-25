@echo off
title PsychAid Setup
cd /d "%~dp0"
setlocal

set "ROOT=%~dp0"
set "PY_DIR=%ROOT%python"
set "PY_EXE=%PY_DIR%\python.exe"

echo ================================================
echo   PsychAid Setup
echo ================================================
echo.

:: ── If embedded Python already downloaded, skip straight to build ──
if exist "%PY_EXE%" goto :install_packages

echo Downloading Python runtime...
echo (This is a portable copy - no installation or admin needed)
echo.
powershell -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip' -OutFile '%ROOT%py_embed.zip' -UseBasicParsing" 2>nul
if errorlevel 1 (
    echo ERROR: Could not download Python. Check your internet connection.
    pause
    exit /b 1
)

echo Extracting Python...
powershell -Command "Expand-Archive -Path '%ROOT%py_embed.zip' -DestinationPath '%PY_DIR%' -Force"
del "%ROOT%py_embed.zip"

:: Enable site-packages (required for pip to work with embedded Python)
powershell -Command "(Get-Content '%PY_DIR%\python311._pth') -replace '#import site','import site' | Set-Content '%PY_DIR%\python311._pth'"

:: Install pip
echo Installing pip...
powershell -Command "Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile '%PY_DIR%\get-pip.py' -UseBasicParsing"
"%PY_EXE%" "%PY_DIR%\get-pip.py" --quiet --no-warn-script-location
del "%PY_DIR%\get-pip.py"

:install_packages
echo.
echo Installing packages (first run takes 2-3 minutes)...
"%PY_EXE%" -m pip install flask reportlab pypdf anthropic python-docx mammoth pywebview pyinstaller --quiet --no-warn-script-location
if errorlevel 1 (
    echo ERROR: Package installation failed. Check your internet connection.
    pause
    exit /b 1
)

echo.
echo Building PsychAid.exe...
cd /d "%ROOT%PsychAid"

"%PY_EXE%" -m PyInstaller ^
    --clean --noconfirm ^
    --onefile --windowed ^
    --name PsychAid ^
    --add-data "templates;templates" ^
    --add-data "static;static" ^
    --collect-all webview ^
    --hidden-import flask ^
    --hidden-import jinja2 ^
    --hidden-import jinja2.ext ^
    --hidden-import werkzeug ^
    --hidden-import werkzeug.serving ^
    --hidden-import werkzeug.routing ^
    --hidden-import werkzeug.exceptions ^
    --hidden-import click ^
    --hidden-import anthropic ^
    --hidden-import pypdf ^
    --hidden-import mammoth ^
    --hidden-import docx ^
    --hidden-import docx.oxml ^
    --hidden-import reportlab ^
    --hidden-import reportlab.pdfgen ^
    --hidden-import reportlab.pdfgen.canvas ^
    --hidden-import reportlab.lib ^
    --hidden-import reportlab.lib.pagesizes ^
    main.py

if exist "dist\PsychAid.exe" (
    copy "dist\PsychAid.exe" "%ROOT%PsychAid.exe" /y >nul
    echo.
    echo ================================================
    echo   Done! PsychAid.exe is ready.
    echo   Double-click PsychAid.exe to launch.
    echo ================================================
    start "" explorer "%ROOT%"
) else (
    echo.
    echo Build failed. See errors above.
)

pause
