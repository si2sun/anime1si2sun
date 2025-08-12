# 1. 使用官方提供的、輕量級的 Python 3.11 映像檔作為基礎
FROM python:3.11-slim

# 2. 設定環境變數，讓 Python 的輸出更即時
ENV PYTHONUNBUFFERED True

# 3. 設定工作目錄
WORKDIR /app

# 4. 將 requirements.txt 複製到映像檔中並安裝依賴
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir --upgrade pip -r requirements.txt

# 5. 將您專案的所有程式碼複製到映像檔中 (優化點)
COPY . .

# 6. Cloud Run 會自動提供 PORT 環境變數，預設為 8080
EXPOSE 8080

# 7. 健康檢查 (保留，這是好的實踐)
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s \
  CMD curl -f "http://localhost:${PORT}/" || exit 1

# 8. 最終的啟動指令 (保留 gunicorn，這是更穩健的作法)
# 使用 exec 形式可以讓 gunicorn 作為容器的 PID 1 進程，是稍微更好的實踐
CMD exec gunicorn -w 2 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:${PORT:-8080} --timeout 60 main:app

