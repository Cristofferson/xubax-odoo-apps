@echo off
REM Re-open the XB Aforo configurator window (after install-windows.bat has run).
setlocal
cd /d "%~dp0"
if not exist "venv\Scripts\python.exe" (
    echo Primero corre install-windows.bat
    pause
    exit /b 1
)
"venv\Scripts\python.exe" configurator.py
endlocal
