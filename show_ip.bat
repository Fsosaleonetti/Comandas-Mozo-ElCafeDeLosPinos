@echo off
REM Muestra las IPv4 locales para usar desde el celular (misma Wi-Fi)
echo Estas son tus IPv4 locales. Usalas como http://IP:8000/static/mozo.html
echo.
ipconfig | findstr /R /C:"IPv4.*"
echo.
pause