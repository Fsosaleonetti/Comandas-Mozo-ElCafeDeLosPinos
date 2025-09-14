@echo off
cd /d "C:\Users\Fabri\OneDrive\Desktop\El_De_Los_Pinos v6"
python -m uvicorn app:app --reload --host 0.0.0.0 --port 8000
pause
