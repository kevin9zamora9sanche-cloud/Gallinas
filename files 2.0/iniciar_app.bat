@echo off
REM ============================================================
REM  Iniciar Sistema de Control Avicola
REM  Doble clic en este archivo para abrir la aplicacion.
REM ============================================================
setlocal

REM Ubicarse en la carpeta donde esta este .bat (funciona sin importar
REM desde donde se ejecute el acceso directo del escritorio)
cd /d "%~dp0"

title Sistema de Control Avicola

REM --- Verificar que Python este instalado ---
where python >nul 2>nul
if errorlevel 1 (
    echo.
    echo [ERROR] No se encontro Python instalado o no esta en el PATH.
    echo Instala Python desde https://www.python.org/downloads/
    echo y marca la opcion "Add Python to PATH" durante la instalacion.
    echo.
    pause
    exit /b 1
)

REM --- Crear entorno virtual la primera vez ---
if not exist "venv\Scripts\activate.bat" (
    echo Primera ejecucion: creando entorno virtual...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] No se pudo crear el entorno virtual.
        pause
        exit /b 1
    )
)

call "venv\Scripts\activate.bat"

REM --- Instalar/actualizar dependencias (rapido si ya estan instaladas) ---
echo Verificando dependencias...
pip install -r requirements.txt --quiet --disable-pip-version-check

if errorlevel 1 (
    echo [ERROR] Fallo la instalacion de dependencias. Revisa tu conexion a internet.
    pause
    exit /b 1
)

REM --- Iniciar la aplicacion ---
echo.
echo Iniciando el Sistema de Control Avicola...
echo Se abrira automaticamente en tu navegador.
echo NO CIERRES esta ventana mientras uses la aplicacion.
echo Para salir: cierra esta ventana o presiona Ctrl+C.
echo.

streamlit run app.py

pause
