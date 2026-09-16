# =========================================================================
# Production Dockerfile for Streamlit Task Management Application
# =========================================================================
FROM python:3.12-slim AS base

# 設定環境變數
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8501 \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    DB_PATH=/app/data/app.db

# 安裝系統層級依賴 (curl 用於容器健康檢查)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 建立非 root 執行使用者 (安全性最佳實踐)
RUN groupadd -g 1000 appuser && \
    useradd -u 1000 -g appuser -m -s /bin/bash appuser

WORKDIR /app

# 預先建立資料庫 Volume 掛載目錄並賦予非 root 使用者權限
RUN mkdir -p /app/data && chown -R appuser:appuser /app

# 複製依賴檔案並安裝 Python 套件
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 複製應用程式原始碼
COPY database.py app.py ./
RUN chown -R appuser:appuser /app

# 切換為非 root 使用者
USER appuser

# 開放 Streamlit 服務埠
EXPOSE 8501

# 定義容器健康檢查
HEALTHCHECK --interval=20s --timeout=5s --start-period=10s --retries=3 \
    CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# 啟動命令
ENTRYPOINT ["streamlit", "run", "app.py"]
