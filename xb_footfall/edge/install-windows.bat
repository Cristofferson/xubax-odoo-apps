@echo off
REM ==========================================================================
REM  XB Aforo - edge one-click setup for Windows
REM  Double-click this file inside the xb_footfall\edge folder.
REM  It installs Python (if missing), creates a virtual environment, installs
REM  the dependencies, and opens the desktop configurator.
REM ==========================================================================
setlocal
cd /d "%~dp0"
echo.
echo === XB Aforo - instalacion del contador (Windows) ===
echo.

REM --- 1. Ensure Python -----------------------------------------------------
where py >nul 2>nul
if %errorlevel%==0 (
    set "PY=py"
) else (
    where python >nul 2>nul
    if %errorlevel%==0 (
        set "PY=python"
    ) else (
        echo Python no encontrado. Instalando con winget...
        winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
        if %errorlevel% neq 0 (
            echo.
            echo No se pudo instalar Python automaticamente.
            echo Instala Python 3.12 desde https://www.python.org/downloads/
            echo   [x] Add python.exe to PATH   y vuelve a correr este archivo.
            pause
            exit /b 1
        )
        set "PY=py"
    )
)

REM --- 2. Virtual environment ------------------------------------------------
if not exist "venv\Scripts\python.exe" (
    echo Creando entorno virtual...
    %PY% -m venv venv
    if %errorlevel% neq 0 ( echo Fallo creando venv. & pause & exit /b 1 )
)

REM --- 3. Dependencies ------------------------------------------------------
echo Instalando dependencias (puede tardar la primera vez)...
"venv\Scripts\python.exe" -m pip install --upgrade pip
"venv\Scripts\python.exe" -m pip install -r requirements.txt
if %errorlevel% neq 0 ( echo Fallo instalando dependencias. & pause & exit /b 1 )

REM --- 4. First config from the template ------------------------------------
if not exist "config.yaml" copy /y "config.example.yaml" "config.yaml" >nul

REM --- 5. Open the configurator ---------------------------------------------
echo.
echo === Todo listo. Abriendo la ventana de configuracion... ===
"venv\Scripts\python.exe" configurator.py
endlocal
