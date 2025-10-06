@echo off
cd /d "C:\Users\Fabri\OneDrive\Desktop\Comandas-Mozo-ElCafeDeLosPinos 2"
python -m uvicorn app:app --reload --host 0.0.0.0 --port 8000
pause
