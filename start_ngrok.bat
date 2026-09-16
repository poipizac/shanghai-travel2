@echo off
chcp 65001 >nul
title ngrok 外網通道啟動器 - 端口 8501
cd /d "%~dp0"

echo ===================================================
echo   ngrok 外網穿透通道啟動器 (Port 8501)
echo ===================================================
echo.

if not exist "ngrok.exe" (
    echo [錯誤] 找不到 ngrok.exe，請確認檔案位於專案目錄。
    pause
    exit /b 1
)

:: 測試 ngrok 是否已經設定 authtoken
.\ngrok.exe http 8501 --dry-run >nul 2>&1
if errorlevel 1 (
    echo [提示] 偵測到尚未設定 ngrok Authtoken！
    echo.
    echo 請依下列步驟免費取得 Token:
    echo 1. 前往官網註冊/登入: https://dashboard.ngrok.com/signup
    echo 2. 複製您的 Authtoken: https://dashboard.ngrok.com/get-started/your-authtoken
    echo.
    set /p "USER_TOKEN=請在此貼上您的 ngrok Authtoken 並按 Enter: "
    if defined USER_TOKEN (
        .\ngrok.exe config add-authtoken %USER_TOKEN%
        echo.
        echo [成功] Authtoken 設定完成！正在為您建立外網通道...
        echo.
    ) else (
        echo [警告] 未輸入 Token，可能無法成功啟動。
    )
)

echo 正在啟動 ngrok 穿透端口 8501...
echo 啟動成功後，畫面上會顯示 Forwarding 網址 (https://xxxx.ngrok-free.app)
echo 複製該網址即可在手機行動網路上暢快存取！
echo ===================================================
echo.

.\ngrok.exe http 8501
