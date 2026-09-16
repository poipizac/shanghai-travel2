@echo off
chcp 65001 >nul
title 建立桌面捷徑 - 任務管理系統
cd /d "%~dp0"

echo ===================================================
echo   正在建立「任務管理系統」桌面捷徑...
echo ===================================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws = New-Object -ComObject WScript.Shell; $desktop = $ws.SpecialFolders('Desktop'); $shortcutPath = Join-Path $desktop '任務管理系統.lnk'; $target = Join-Path (Get-Location) 'start_app.bat'; $shortcut = $ws.CreateShortcut($shortcutPath); $shortcut.TargetPath = $target; $shortcut.WorkingDirectory = (Get-Location).Path; $shortcut.Description = '啟動出差津貼與任務管理系統'; $shortcut.IconLocation = 'shell32.dll,220'; $shortcut.Save(); Write-Host '捷徑已成功建立至桌面:' $shortcutPath -ForegroundColor Green"

if errorlevel 1 (
    echo.
    echo [錯誤] 捷徑建立失敗，請確認是否具備檔案存取權限。
    echo.
) else (
    echo.
    echo [完成] 您現在可以直接至桌面雙擊「任務管理系統」圖示啟動服務！
    echo.
)

pause
