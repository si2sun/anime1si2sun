# 1. 使用官方提供的、輕量級的 Python 3.11 映像檔作為基礎
FROM python:3.11-slim

# 2. 設定環境變數，讓 Python 的輸出更即時
ENV PYTHONUNBUFFERED True

# 3. 設定工作目錄
WORKDIR /app

# 4. 將 requirements.txt 複製到映像檔中
COPY requirements.txt requirements.txt

# 5. 安裝所有需要的 Python 套件
# --no-cache-dir 參數可以讓映像檔更小
RUN pip install --no-cache-dir --upgrade pip -r requirements.txt

# 6. 將您專案的所有程式碼複製到映像檔中
COPY main.py .
COPY 情感top3提出_dandadan_fast_json.py .
COPY templates/ templates/


# 7. Cloud Run 會自動提供 PORT 環境變數，預設為 8080
EXPOSE 8080

# 8. 設定部署時需要提供的環境變數 (僅為標示，實際值在部署時設定)
ENV DB_HOST="35.223.124.201"
ENV DB_PORT="5432"
ENV DB_NAME="anime1si2sun"
ENV DB_USER="postgres"
ENV DB_PASSWORD="lty890509"

# 9. 健康檢查 (可選，但建議修正)
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s \
  CMD curl -f "http://localhost:${PORT}/" || exit 1

# 10. 最終的啟動指令 (關鍵修正)
# 使用 --bind 綁定到 0.0.0.0:$PORT
# 建議先從 1 或 2 個 worker 開始 (-w 2)
# 增加 --timeout 以應對可能較長的分析時間
CMD gunicorn -w 2 -k uvicorn.workers.UvicornWorker --bind "0.0.0.0:$PORT" main:app
