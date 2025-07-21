import pandas as pd
from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
import sys
import json
import unicodedata
import time
import traceback
import psycopg2
from psycopg2 import sql
from contextlib import contextmanager
import io
import google.auth

from google.cloud import firestore
try:
    from 情感top3提出_dandadan_fast_json import get_top3_emotions_fast, get_top5_density_moments
except ImportError:
    print("ERROR: 無法導入 '情感top3提出_dandadan_fast_json' 模組中的函式。")
    sys.exit(1)
credentials, project_id = google.auth.default()
db = firestore.Client(
    credentials=credentials,
    project=animetext,
    database="anime-label"  # <== 如果你確定有這個 database，就寫上它
)
app = FastAPI()

# ====== CORS 配置 ======
origins = ["http://localhost", "http://127.0.0.1", "http://127.0.0.1:5000"]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# templates = Jinja2Templates(directory=".")
templates = Jinja2Templates(directory="templates")

# ====== PostgreSQL 資料庫配置 ======
DB_HOST = "35.223.124.201"
DB_PORT = "5432"
DB_NAME = "anime1si2sun"
DB_USER = "postgres"
DB_PASSWORD = "lty890509"
DATABASE_URL = f"dbname={DB_NAME} user={DB_USER} password={DB_PASSWORD} host={DB_HOST} port={DB_PORT}"

@contextmanager
def get_db_connection():
    conn = None
    try:
        conn = psycopg2.connect(DATABASE_URL)
        yield conn
    except psycopg2.Error as e:
        print(f"資料庫連線錯誤: {e}")
        raise HTTPException(status_code=500, detail="資料庫連線錯誤")
    finally:
        if conn: conn.close()

# 全域變數
AVAILABLE_ANIME_NAMES, YOUTUBE_ANIME_EPISODE_URLS, BAHAMUT_ANIME_EPISODE_URLS, ANIME_COVER_IMAGE_URLS, ANIME_TAGS_DB = [], {}, {}, {}, {}
TAG_COMBINATION_MAPPING, EMOTION_CATEGORY_MAPPING = {}, {}
db = None

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "animetext-anime1si2sun.json"

def load_anime_data_from_db():
    print("\n--- 開始從 PostgreSQL 載入動漫數據 ---")
    start_time = time.time()
    global AVAILABLE_ANIME_NAMES, YOUTUBE_ANIME_EPISODE_URLS, BAHAMUT_ANIME_EPISODE_URLS, ANIME_COVER_IMAGE_URLS, ANIME_TAGS_DB
    
    # 彻底移除 "ED開始秒數" 的查询
    query = 'SELECT "作品名", "集數", "巴哈動畫瘋網址", "YT網址", "封面圖", "作品分類" FROM anime_url ORDER BY "作品名", "集數";'
    
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(query)
        rows = cur.fetchall()

    if not rows:
        print("⚠️ 警告：資料庫的 'anime_url' 表中沒有找到任何數據。")
        return

    for row in rows:
        anime_original, episode, bahamut_url, youtube_url, cover_image_val, tags_json = row
        
        anime_normalized = unicodedata.normalize('NFC', str(anime_original).strip())
        AVAILABLE_ANIME_NAMES.append(anime_normalized)
        ep_key = str(episode).strip()

        YOUTUBE_ANIME_EPISODE_URLS.setdefault(anime_normalized, {})
        BAHAMUT_ANIME_EPISODE_URLS.setdefault(anime_normalized, {})
        ANIME_TAGS_DB.setdefault(anime_normalized, [])

        if youtube_url:
            yt_url_str = str(youtube_url).strip()
            video_id = None
            if "youtube.com/watch?v=" in yt_url_str: video_id = yt_url_str.split("v=")[-1].split("&")[0]
            elif "youtu.be/" in yt_url_str: video_id = yt_url_str.split("youtu.be/")[-1].split("?")[0]
            if video_id: YOUTUBE_ANIME_EPISODE_URLS[anime_normalized][ep_key] = video_id
        
        if bahamut_url: BAHAMUT_ANIME_EPISODE_URLS[anime_normalized][ep_key] = str(bahamut_url).strip()
        if cover_image_val: ANIME_COVER_IMAGE_URLS[anime_normalized] = str(cover_image_val).strip()
        if tags_json:
            try:
                tags = json.loads(str(tags_json).replace("'", '"'))
                if isinstance(tags, list): ANIME_TAGS_DB[anime_normalized] = tags
            except (json.JSONDecodeError, TypeError): pass

    AVAILABLE_ANIME_NAMES = sorted(list(set(AVAILABLE_ANIME_NAMES)))
    print(f"--- PostgreSQL 數據載入完成，耗時 {time.time() - start_time:.2f} 秒 ---")

@app.on_event("startup")
async def startup_event():
    # ... (此函式保持不變) ...
    print(f"伺服器啟動中...")
    load_anime_data_from_db()
    
    global db, TAG_COMBINATION_MAPPING, EMOTION_CATEGORY_MAPPING
    try:
        db = firestore.Client(database="anime-label")
        print("INFO: Firestore 客戶端初始化成功。")
    except Exception as e:
        print(f"ERROR: Firestore 客戶端初始化失敗: {e}"); sys.exit(1)

    print("\n--- 開始從 Firestore 載入情感映射檔案 ---")
    start_time = time.time()
    try:
        anime_label_docs = db.collection('anime_label').stream()
        for doc in anime_label_docs:
            data = doc.to_dict()
            if '作品分類' in data and '情感分類' in data and isinstance(data['情感分類'], list):
                TAG_COMBINATION_MAPPING[data['作品分類']] = list(set(data['情感分類']))
        
        emotion_label_docs = db.collection('emotion_label').stream()
        for doc in emotion_label_docs:
            data = doc.to_dict()
            if '情感分類' in data and '情緒' in data and isinstance(data['情緒'], list):
                EMOTION_CATEGORY_MAPPING[data['情感分類']] = list(set(data['情緒']))
        
        print("INFO: 情感映射從 Firestore 載入成功。")
    except Exception as e:
        print(f"ERROR: 從 Firestore 載入映射失敗: {e}"); traceback.print_exc(); sys.exit(1)
    print(f"--- 情感映射載入完成，耗時 {time.time() - start_time:.2f} 秒 ---\n")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request): return templates.TemplateResponse("animetop.html", {"request": request})

@app.get("/search_anime_names")
async def search_anime_names(query: str = ""):
    if not query: return []
    return sorted([name for name in AVAILABLE_ANIME_NAMES if query.lower() in name.lower()])

@app.get("/get_emotion_categories")
async def get_emotion_categories():
    if not EMOTION_CATEGORY_MAPPING: raise HTTPException(500, "情感分類映射未成功載入。")
    return sorted(list(EMOTION_CATEGORY_MAPPING.keys()))


@app.get("/get_emotions")
async def get_emotions_api(anime_name: str, custom_emotions: list[str] = Query(None)):
    t_start = time.time()
    print(f"\n--- 收到搜尋請求: '{anime_name}' (時間: {t_start}) ---")
    normalized_name = unicodedata.normalize('NFC', anime_name.strip())
    if normalized_name not in AVAILABLE_ANIME_NAMES: raise HTTPException(404, f"找不到 '{anime_name}' 的數據。")

    t_db_start = time.time()
    copy_sql_query = sql.SQL('COPY (SELECT "彈幕", "label", "label2", "作品名", "集數", "時間", "情緒" FROM anime_danmaku WHERE "作品名" = {anime_name}) TO STDOUT WITH CSV HEADER DELIMITER \',\'').format(anime_name=sql.Literal(normalized_name))
    try:
        buffer = io.StringIO()
        with get_db_connection() as conn, conn.cursor() as cur:
            cur.copy_expert(copy_sql_query, buffer, size=8192)
        buffer.seek(0)
        df_danmaku = pd.read_csv(buffer)
        if df_danmaku.empty: raise HTTPException(404, f"資料庫中沒有找到 '{normalized_name}' 的彈幕數據。")
        df_danmaku['集數'] = df_danmaku['集數'].astype(str)
    except HTTPException as e: raise e
    except Exception as e: raise HTTPException(500, f"讀取彈幕數據時發生錯誤: {e}")
    t_db_end = time.time()
    print(f"  [計時] 資料庫彈幕讀取 (高效模式): {t_db_end - t_db_start:.4f} 秒")

    t_map_start = time.time()
    dynamic_emotion_mapping = {}
    if custom_emotions:
        print(f"INFO: 使用者自訂模式: {custom_emotions}")
        for category in custom_emotions:
            if category in EMOTION_CATEGORY_MAPPING:
                dynamic_emotion_mapping[category] = EMOTION_CATEGORY_MAPPING[category]
    else:
        print("INFO: 使用預設模式 (最佳完全匹配)")
        tags = ANIME_TAGS_DB.get(normalized_name)
        if not tags: raise HTTPException(404, f"找不到 '{anime_name}' 的分類數據 (tags)。")
        
        anime_tags_set = set(tags)
        best_match_key, max_match_length = None, -1
        for rule_key in TAG_COMBINATION_MAPPING.keys():
            rule_tags_set = set(rule_key.split('|'))
            if rule_tags_set.issubset(anime_tags_set) and len(rule_tags_set) > max_match_length:
                max_match_length = len(rule_tags_set)
                best_match_key = rule_key

        if best_match_key:
            print(f"  -> 最佳完全匹配規則: '{best_match_key}'")
            categories_from_tags = TAG_COMBINATION_MAPPING.get(best_match_key, [])
            for category in categories_from_tags:
                if category in EMOTION_CATEGORY_MAPPING:
                    dynamic_emotion_mapping[category] = EMOTION_CATEGORY_MAPPING[category]
        if not dynamic_emotion_mapping:
            raise HTTPException(404, f"無法為 '{anime_name}' (Tags: {tags}) 找到任何完全匹配的情感分類定義。")
    t_map_end = time.time()
    print(f"  [計時] 動態情感映射生成: {t_map_end - t_map_start:.4f} 秒")
    print(f"INFO: 動態情感映射生成完成: {list(dynamic_emotion_mapping.keys())}")
    
    t_core_start = time.time()
    try:
        # <<<<<<< 关键修改：呼叫函式时不再传递任何 op/ed 参数 >>>>>>>
        result = get_top3_emotions_fast(
            df=df_danmaku, 
            anime_name=normalized_name, 
            emotion_mapping=dynamic_emotion_mapping
        )
    except Exception as e:
        print(f"ERROR: 核心分析失敗: {e}"); traceback.print_exc(); raise HTTPException(500, "伺服器內部錯誤，情緒分析失敗。")
    t_core_end = time.time()
    print(f"  [計時] 核心情绪分析 (get_top3_emotions_fast): {t_core_end - t_core_start:.4f} 秒")

    if not result: raise HTTPException(404, f"找不到 '{anime_name}' 符合條件的情緒熱點數據。")

    t_sort_start = time.time()
    ordered_final_result = {}
    if not custom_emotions:
        t_top5_start = time.time()
        top_5_moments = get_top5_density_moments(
            df=df_danmaku,
            anime_name=normalized_name
        )
        t_top5_end = time.time()
        print(f"  [計時] TOP 10 弹幕时段计算: {t_top5_end - t_top5_start:.4f} 秒")

        priority_top = ["最精采/激烈的時刻", "LIVE/配樂", "虐點/感動"]
        priority_bottom_key = "彈幕最密集 TOP10"
        
        final_ordered_keys = [key for key in priority_top if key in result]
        other_categories = sorted([key for key in result if key not in priority_top])
        final_ordered_keys.extend(other_categories)
        if top_5_moments:
            final_ordered_keys.append(priority_bottom_key)

        for key in final_ordered_keys:
            if key == priority_bottom_key:
                ordered_final_result[key] = top_5_moments
            elif key in result:
                ordered_final_result[key] = result[key]
    else:
        ordered_final_result = dict(sorted(result.items()))
    t_sort_end = time.time()
    print(f"  [計時] 最终结果排序: {t_sort_end - t_sort_start:.4f} 秒")

    final_output = {
        "youtube_episode_urls": YOUTUBE_ANIME_EPISODE_URLS.get(normalized_name),
        "bahamut_episode_urls": BAHAMUT_ANIME_EPISODE_URLS.get(normalized_name),
        "cover_image_url": ANIME_COVER_IMAGE_URLS.get(normalized_name, ""),
        **ordered_final_result
    }
    
    t_end = time.time()
    print(f"--- 搜尋請求 '{anime_name}' 處理完成，總耗時 {t_end - t_start:.4f} 秒 ---\n")
    return final_output

if __name__ == '__main__':
    uvicorn.run("main:app", host="0.0.0.0", port=8080)
