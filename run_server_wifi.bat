@echo off
REM Levanta el servidor FastAPI en LAN
REM Al iniciar: limpia comandas y fuerza actualización de cache PWA Mozo
echo Iniciando servidor en 0.0.0.0:8000 ...
python -m uvicorn app:app --reload --host 0.0.0.0 --port 8000
pause