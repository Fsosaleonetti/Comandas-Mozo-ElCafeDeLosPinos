@echo off
echo Cerrando servidores en puertos 8000 y 8001 (si existen)...
for %%P in (8000 8001) do (
  for /f "tokens=5" %%a in ('netstat -ano ^| findstr /R /C:":%%P .*LISTENING"') do (
    echo Matando PID %%a en puerto %%P...
    taskkill /F /PID %%a >nul 2>&1
  )
)
echo Listo.
pause