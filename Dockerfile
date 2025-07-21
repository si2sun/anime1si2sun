# 使用輕量級的 Python 映像
FROM python:3.10-slim

# 設定工作目錄
WORKDIR /app

# 複製 requirements 並安裝
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 複製程式碼
COPY main.py .
COPY 情感top3提出_dandadan_fast_json.py .

# Firestore 認證檔案 (你部署時要自己 mount 上去)
# COPY animetext-anime1si2sun.json .

# 若有 template 檔案夾，記得加這行
COPY templates/ templates/

# 設定環境變數給 Firestore 使用（或用 volume 掛載）
ENV GOOGLE_APPLICATION_CREDENTIALS="animetext-anime1si2sun.json"

# 開放 port 8080
EXPOSE 8080

# 啟動 FastAPI 伺服器（非開發模式）
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
