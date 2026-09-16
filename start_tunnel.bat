@echo off
chcp 65001 >nul
title Cloudflare 外網穿透通道啟動器 - 端口 8501
cd /d "%~dp0"

echo ===================================================
echo   Cloudflare 免費高速穿透通道 (Port 8501)
echo ===================================================
echo.

if not exist "cloudflared.exe" (
    echo [錯誤] 找不到 cloudflared.exe，請確認檔案位於專案目錄。
    pause
    exit /b 1
)

echo 正在建立外網安全通道...
echo 成功建立後，將會顯示 https://xxxx.trycloudflare.com 網址
echo.
.\cloudflared.exe tunnel --url http://localhost:8501
pause
