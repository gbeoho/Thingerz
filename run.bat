@echo off
chcp 65001 > nul
cd /d "C:\Users\G\Documents\testproject"
echo.
echo ========================================
echo   Thingerz Server - Starting...
echo   Open: http://127.0.0.1:5000
echo   Press Ctrl+C to stop
echo ========================================
echo.
python app.py