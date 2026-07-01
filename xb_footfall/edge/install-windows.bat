@echo off
REM ==========================================================================
REM  XB Aforo - edge one-click setup for Windows
REM  Double-click this file inside the xb-aforo-edge folder.
REM  It ensures Python is present, creates a virtual environment, installs the
REM  dependencies, and opens the desktop configurator.
REM ==========================================================================
setlocal
cd /d "%~dp0"
echo.
echo === XB Aforo - instalacion del contador (Windows) ===
echo.

REM --- 1. Find Python -------------------------------------------------------
set "PY="
where py >nul 2>nul && set "PY=py"
if not defined PY (
    where python >nul 2>nul && set "PY=python"
)

REM --- 1b. Try winget if Python is missing ---------------------------------
if not defined PY (
    echo Python no encontrado. Intentando instalar con winget...
    winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements >nul 2>nul
    where py >nul 2>nul && set "PY=py"
)

REM --- 1c. Still missing: open python.org and stop -------------------------
if not defined PY (
    echo.
    echo No se pudo preparar Python automaticamente en esta PC.
    echo Voy a abrir la pagina oficial de descarga...
    start "" https://www.python.org/downloads/
    echo.
    echo   1) Descarga e instala "Python 3.12" (boton amarillo).
    echo   2) MUY IMPORTANTE: marca la casilla  [x] Add python.exe to PATH
    echo   3) Cierra esta ventana y vuelve a dar doble clic a install-windows.bat
    echo.
    pause
    exit /b 1
)

REM --- 2. Virtual environment ----------------------------------------------
if not exist "venv\Scripts\python.exe" (
    echo Creando entorno virtual...
    %PY% -m venv venv
    if errorlevel 1 ( echo Fallo creando el entorno. & pause & exit /b 1 )
)

REM --- 3. Dependencies ------------------------------------------------------
echo Instalando dependencias (la primera vez tarda unos minutos)...
"venv\Scripts\python.exe" -m pip install --upgrade pip
"venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 ( echo Fallo instalando dependencias. & pause & exit /b 1 )

REM --- 4. First config from the template ------------------------------------
if not exist "config.yaml" copy /y "config.example.yaml" "config.yaml" >nul

REM --- 5. Open the configurator ---------------------------------------------
echo.
echo === Todo listo. Abriendo la ventana de configuracion... ===
"venv\Scripts\python.exe" configurator.py
endlocal
