# =========================================================================
# Task Manager Docker 容器化環境與健康檢查驗證腳本 (PowerShell)
# =========================================================================
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "=========================================================================" -ForegroundColor Cyan
Write-Host "  Task Manager Docker 容器化環境與健康檢查驗證腳本" -ForegroundColor Cyan
Write-Host "=========================================================================`n" -ForegroundColor Cyan

# 1. 檢查 Docker CLI
Write-Host "[*] 正在檢查 Docker CLI 指令..." -ForegroundColor Yellow
$dockerCmd = Get-Command docker -ErrorAction SilentlyContinue
if (-not $dockerCmd) {
    Write-Host "[ERROR] 找不到 'docker' 指令！" -ForegroundColor Red
    Write-Host "請先安裝 Docker Desktop 並確認已加入系統環境變數 PATH。" -ForegroundColor Red
    Write-Host "官方下載網址: https://www.docker.com/products/docker-desktop/`n" -ForegroundColor Gray
    exit 1
}
Write-Host "[OK] 偵測到 Docker CLI: $($dockerCmd.Source)" -ForegroundColor Green

# 2. 檢查 Docker Daemon
Write-Host "`n[*] 正在檢查 Docker Daemon 執行狀態..." -ForegroundColor Yellow
$daemonInfo = docker info 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Docker Daemon 服務尚未啟動！" -ForegroundColor Red
    Write-Host "請先啟動 Docker Desktop，待其右下角狀態顯示為 'Engine running' 後再次執行本腳本。`n" -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Docker Daemon 正常運行中" -ForegroundColor Green

# 3. 確保資料庫掛載目錄存在
$dataDir = Join-Path $PSScriptRoot "data"
if (-not (Test-Path $dataDir)) {
    Write-Host "`n[*] 建立資料庫持久化目錄: $dataDir" -ForegroundColor Yellow
    New-Item -ItemType Directory -Path $dataDir -Force | Out-Null
}

# 4. 建置 Docker 映像檔
Write-Host "`n[1/4] 開始建置 Docker 映像檔 (docker compose build)..." -ForegroundColor Yellow
docker compose build
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] 映像檔建置失敗，請檢查 Dockerfile 與網路連線。" -ForegroundColor Red
    exit 1
}

# 5. 背景啟動容器
Write-Host "`n[2/4] 啟動 Docker 容器服務 (docker compose up -d)..." -ForegroundColor Yellow
docker compose up -d
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] 容器啟動失敗！" -ForegroundColor Red
    exit 1
}

# 6. 健康檢查輪詢
Write-Host "`n[3/4] 正在等待服務就緒並驗證健康檢查端點 (http://localhost:8501/_stcore/health)..." -ForegroundColor Yellow
$maxAttempts = 15
$passed = $false
for ($i = 1; $i -le $maxAttempts; $i++) {
    try {
        $resp = Invoke-WebRequest -Uri "http://localhost:8501/_stcore/health" -UseBasicParsing -TimeoutSec 2
        if ($resp.StatusCode -eq 200) {
            Write-Host "[SUCCESS] 健康檢查驗證成功 (HTTP 200)！耗時約 $($i * 2) 秒。" -ForegroundColor Green
            $passed = $true
            break
        }
    } catch {
        Write-Host "  正在等待服務啟動 ($i/$maxAttempts)..." -ForegroundColor Gray
        Start-Sleep -Seconds 2
    }
}

if (-not $passed) {
    Write-Host "[WARNING] 健康檢查超時，請使用 'docker compose logs' 查看容器日誌。" -ForegroundColor Red
    exit 1
}

# 7. 檢查容器狀態與 Volume
Write-Host "`n[4/4] 檢查容器運行狀態與 Volume 掛載..." -ForegroundColor Yellow
docker compose ps

Write-Host "`n=========================================================================" -ForegroundColor Cyan
Write-Host "  [驗證完成] Streamlit 任務管理服務已於容器中就緒！" -ForegroundColor Green
Write-Host "  - 服務網址: http://localhost:8501" -ForegroundColor White
Write-Host "  - 資料庫掛載: .\data\app.db" -ForegroundColor White
Write-Host "  - 停止服務指令: docker compose down" -ForegroundColor White
Write-Host "  - 查看日誌指令: docker compose logs -f" -ForegroundColor White
Write-Host "=========================================================================`n" -ForegroundColor Cyan
