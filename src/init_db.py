import os
from db import get_conn, DB_PATH

conn = get_conn()          # 🔥 반드시 () 붙이기
cursor = conn.cursor()

# 기존 테이블 삭제
cursor.execute("DROP TABLE IF EXISTS raw_company_data")
cursor.execute("DROP TABLE IF EXISTS signal_scores")
cursor.execute("DROP TABLE IF EXISTS sales_mart")
cursor.execute("DROP TABLE IF EXISTS news")
cursor.execute("DROP TABLE IF EXISTS jobs")
cursor.execute("DROP TABLE IF EXISTS processed_periods")

# 1. Raw Layer
cursor.execute('''
CREATE TABLE raw_company_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_name TEXT NOT NULL,
    source TEXT,
    funding_stage TEXT,
    funding_round TEXT,
    funding_date TEXT,
    amount TEXT,
    investors TEXT,
    industry TEXT,
    keywords TEXT,
    required_roles TEXT,
    job_roles TEXT,
    news_title TEXT,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
''')

# 2. Signal Layer
cursor.execute('''
CREATE TABLE signal_scores (
    company_id INTEGER PRIMARY KEY,
    funding_score INTEGER DEFAULT 0,
    hiring_score INTEGER DEFAULT 0,
    recency_score INTEGER DEFAULT 0,
    total_score INTEGER DEFAULT 0,
    FOREIGN KEY(company_id) REFERENCES raw_company_data(id)
)
''')

# 3. Mart Layer
cursor.execute('''
CREATE TABLE sales_mart (
    company_id INTEGER PRIMARY KEY,
    priority TEXT DEFAULT 'Low',
    sales_hook TEXT,
    is_sent BOOLEAN DEFAULT 0,
    FOREIGN KEY(company_id) REFERENCES raw_company_data(id)
)
''')

# 4. News table (structured storage)
cursor.execute('''
CREATE TABLE IF NOT EXISTS news (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER,
    title TEXT,
    content TEXT,
    url TEXT,
    published_at TEXT,
    source_name TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(company_id) REFERENCES raw_company_data(id)
)
''')

# 5. Jobs table (structured storage)
cursor.execute('''
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER,
    title TEXT,
    team TEXT,
    link TEXT,
    source TEXT,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(company_id) REFERENCES raw_company_data(id)
)
''')

# 6. Processed periods to avoid re-processing same month
cursor.execute('''
CREATE TABLE IF NOT EXISTS processed_periods (
    period TEXT PRIMARY KEY,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
''')

conn.commit()
conn.close()

print("✅ DB 스키마 완전 새로 생성 완료!")
print(f"📊 파일 확인: {os.path.getsize(DB_PATH)} bytes")
