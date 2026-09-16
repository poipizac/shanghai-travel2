@echo off
chcp 65001 >nul
title 出差津貼與交通費計算系統 - 啟動器
cd /d "%~dp0"

echo ===================================================
echo   出差津貼與交通費計算系統 - 啟動程式
echo ===================================================
echo.

:: 1. 檢查虛擬環境或可用 Python
echo [步驟 1/3] 檢查 Python 執行環境...

if exist ".venv\Scripts\python.exe" (
    set "PY_CMD=.venv\Scripts\python.exe"
    goto check_packages
)

python -c "import sys" >nul 2>&1
if %errorlevel% equ 0 (
    set "BOOT_PY=python"
    goto create_virtualenv
)

py -c "import sys" >nul 2>&1
if %errorlevel% equ 0 (
    set "BOOT_PY=py"
    goto create_virtualenv
)

goto python_not_found

:create_virtualenv
echo 正在為專案建立獨立虛擬環境 [.venv]...
echo (初次建立需耗時數秒，請稍候)
%BOOT_PY% -m venv .venv
if errorlevel 1 (
    echo [警告] 建立虛擬環境失敗，將直接使用全域 Python 環境。
    set "PY_CMD=%BOOT_PY%"
    goto check_packages
)
set "PY_CMD=.venv\Scripts\python.exe"
goto check_packages

:python_not_found
echo.
echo [錯誤] 系統未偵測到可用的 Python 環境！
echo.
echo 請依下列步驟安裝 Python:
echo 1. 前往官方網站下載: https://www.python.org/downloads/
echo 2. 安裝時務必勾選 "Add Python to PATH" (將 Python 加入環境變數)
echo 3. 安裝完成後，請重新雙擊執行 start_app.bat
echo.
pause
exit /b 1

:check_packages
echo.
echo [步驟 2/3] 檢查並安裝相依套件...
if not exist "requirements.txt" goto start_streamlit

echo 正在透過 pip 驗證並安裝套件...
"%PY_CMD%" -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [錯誤] 套件安裝失敗，請檢查網路連線或錯誤訊息。
    echo.
    pause
    exit /b 1
)

:start_streamlit
echo.
echo [步驟 3/3] 正在啟動 Streamlit 服務...
echo ===================================================
echo 系統已成功啟動！
echo 瀏覽器預設開啟網址: http://localhost:8501
echo 若要關閉服務，請直接關閉此視窗或按下 Ctrl+C。
echo ===================================================
echo.

"%PY_CMD%" -m streamlit run app.py

if errorlevel 1 (
    echo.
    echo [提示] 程式已停止執行。
    pause
)

