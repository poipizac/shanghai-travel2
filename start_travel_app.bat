@echo off
chcp 65001 >nul
title 上海旅遊行程與記帳系統 - 啟動器
cd /d "%~dp0"

echo ===================================================
echo   上海旅遊行程與記帳系統 (travel_app.py) 啟動程式
echo ===================================================
echo.

set "PY_CMD=.venv\Scripts\python.exe"

if not exist "%PY_CMD%" (
    echo [提示] 未在 .venv 找到虛擬環境，使用系統 python...
    set "PY_CMD=python"
)

echo [1/2] 正在啟動 Streamlit 服務...
echo 預設本機網址: http://localhost:8501
echo ===================================================
echo.

"%PY_CMD%" -m streamlit run travel_app.py
pause
