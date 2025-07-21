# 1. 使用官方提供的、輕量級的 Python 3.11 映像檔作為基礎
FROM python:3.11-slim

# 2. 設定工作目錄
WORKDIR /app

# 3. 將 requirements.txt 複製到映像檔中
COPY requirements.txt requirements.txt

# 4. 安裝所有需要的 Python 套件
# --no-cache-dir 參數可以讓映像檔更小
RUN pip install --no-cache-dir --upgrade pip -r requirements.txt

# 5. 將您專案的所有程式碼複製到映像檔中
COPY . .

# 6. 設定環境變數，告訴 Cloud Run 應用程式應該在哪個 Port 監聽
ENV PORT 8080

# 7. 最終的啟動指令
# 使用 gunicorn 作為生產級伺服器來啟動您的 FastAPI 應用
# -w 4: 啟動 4 個 worker process 來處理請求 (可依需求調整)
# -k uvicorn.workers.UvicornWorker: 告訴 gunicorn 使用 uvicorn 來執行 ASGI 應用
# main:app: 指向 main.py 檔案中的 app 物件
CMD ["gunicorn", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "main:app"]