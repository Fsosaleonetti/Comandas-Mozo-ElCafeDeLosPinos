@echo off
color 0A
title El Cafe de los Pinos - Servidor

echo.
echo ========================================
echo   EL CAFE DE LOS PINOS - Servidor v3.0
echo ========================================
echo.

REM Verificar Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python no esta instalado o no esta en el PATH
    echo.
    echo Instala Python desde: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [OK] Python detectado
echo.

REM Mostrar IPs locales
echo TUS IPs LOCALES (para celulares en la misma WiFi):
echo --------------------------------------------------------
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /C:"IPv4"') do (
    set IP=%%a
    setlocal enabledelayedexpansion
    set IP=!IP:~1!
    echo   http://!IP!:8000/static/index.html
    endlocal
)
echo --------------------------------------------------------
echo.

echo [*] Iniciando servidor en http://0.0.0.0:8000
echo [*] Abriendo navegador en 3 segundos...
echo.
echo Presiona Ctrl+C para detener el servidor
echo.

REM Abrir navegador después de 3 segundos
start "" cmd /c "timeout /t 3 /nobreak >nul && start http://localhost:8000/static/index.html"

REM Iniciar servidor
python -m uvicorn app:app --reload --host 0.0.0.0 --port 8000

pause