@echo off
echo ========================================
echo   ScreenViewer Pro - Instalador
echo ========================================
echo.

REM Verificar si Python está instalado
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python no está instalado.
    echo Descárgalo de https://python.org
    pause
    exit /b 1
)

echo [1/3] Instalando dependencias...
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo Error instalando dependencias
    pause
    exit /b 1
)

echo [2/3] Creando ejecutable...
pyinstaller --onefile --windowed --name="ScreenViewerPro" --icon=NONE main.py --quiet

if exist "dist\ScreenViewerPro.exe" (
    echo [3/3] ¡Éxito!
    echo.
    echo El ejecutable está en: dist\ScreenViewerPro.exe
    echo.
    echo ¿Quieres abrirlo ahora? (S/N)
    set /p open_now=
    if /i "%open_now%"=="S" (
        start dist\ScreenViewerPro.exe
    )
) else (
    echo Error creando el ejecutable
    pause
    exit /b 1
)

echo.
echo ========================================
echo   ¡Instalación completada!
echo ========================================
pause
