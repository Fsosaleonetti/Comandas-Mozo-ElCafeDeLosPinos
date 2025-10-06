@echo off
REM Levanta el servidor FastAPI en LAN y abre el navegador
REM Al iniciar: limpia comandas y fuerza actualización de cache PWA Mozo

echo.
echo ========================================
echo   El Cafe de los Pinos - Servidor
echo ========================================
echo.
echo Iniciando servidor en 0.0.0.0:8000 ...
echo.

REM Esperar 2 segundos y abrir navegador en segundo plano
start "" cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:8000/static/index.html"

REM Iniciar servidor (esto bloqueará la terminal)
python -m uvicorn app:app --reload --host 0.0.0.0 --port 8000