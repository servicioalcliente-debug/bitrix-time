@echo off
chcp 65001 > nul
set PYTHONIOENCODING=utf-8
title Bitrix24 - Dashboard de Control de Tiempos
echo ========================================================
echo    Iniciando Dashboard de Control de Tiempos Bitrix24
echo ========================================================
echo.
echo  Servidor local en ejecucion: http://localhost:5000
echo  Presiona CTRL + C en esta ventana para detenerlo.
echo.

:: Espera 2 segundos y abre el navegador por defecto
start "" http://localhost:5000

:: Ejecuta el servidor Flask
python app.py

pause
