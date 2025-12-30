import sqlite3

# DB 파일 생성 (없으면 자동 생성)
conn = sqlite3.connect('../data/meta_sales_trigger.db')
cursor = conn.cursor()

# 1. Raw Layer: 수집된 원본 데이터
cursor.execute('''
CREATE TABLE IF NOT EXISTS raw_company_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_name TEXT NOT NULL,
    source TEXT,
    funding_stage TEXT,
    funding_date TEXT,
    job_roles TEXT,
    news_title TEXT,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
''')

# 2. Signal Layer: 점수화된 데이터
cursor.execute('''
CREATE TABLE IF NOT EXISTS signal_scores (
    company_id INTEGER,
    funding_score INTEGER,
    hiring_score INTEGER,
    recency_score INTEGER,
    total_score INTEGER,
    FOREIGN KEY(company_id) REFERENCES raw_company_data(id)
)
''')

# 3. Mart Layer: 최종 영업 리포트용
cursor.execute('''
CREATE TABLE IF NOT EXISTS sales_mart (
    company_id INTEGER,
    priority TEXT,
    sales_hook TEXT,
    is_sent BOOLEAN DEFAULT 0,
    FOREIGN KEY(company_id) REFERENCES raw_company_data(id)
)
''')

conn.commit()
conn.close()
print("✅ DB 스키마 생성 완료: meta_sales_trigger.db")