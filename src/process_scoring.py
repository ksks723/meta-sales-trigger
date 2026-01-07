import sqlite3
from db import get_conn
import json
import os

# 설정 파일 경로
CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'scoring_config.json')

def load_scoring_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        "funding_weights": {"Series A": 30, "Seed": 10},
        "job_keywords": {"세일즈": 25, "영업": 25, "마케터": 20, "마케팅": 20},
        "recency_days": 30,
        "recency_score": 10
    }

def calculate_score(row, config):
    # row: (id, company_name, funding_stage, funding_date, job_roles)
    score = 0
    
    # 투자 점수
    funding_stage = row[2] or ""
    score += config["funding_weights"].get(funding_stage, 0)
        
    # 채용 점수
    jobs = row[4] or ""
    for keyword, points in config["job_keywords"].items():
        if keyword in jobs:
            score += points
        
    # 최신성 점수
    if row[3] and f"2025-{config['recency_days']//30:02d}" in row[3]:
        score += config["recency_score"]
        
    return score

conn = get_conn()
cursor = conn.cursor()

config = load_scoring_config()

# Raw 데이터 가져오기
cursor.execute("SELECT id, company_name, funding_stage, funding_date, job_roles FROM raw_company_data")
rows = cursor.fetchall()

print("🧮 스코어링 분석 시작...")

for row in rows:
    company_id = row[0]
    company_name = row[1]
    
    # 점수 계산 함수 호출
    total_score = calculate_score(row, config)
    
    # Signal 테이블에 저장 (이미 있으면 업데이트 로직 필요하나 여기선 생략)
    # 간단하게 삭제 후 재입력 방식 사용
    cursor.execute("DELETE FROM signal_scores WHERE company_id = ?", (company_id,))
    cursor.execute('''
    INSERT INTO signal_scores (company_id, total_score)
    VALUES (?, ?)
    ''', (company_id, total_score))
    
    # Mart(타겟팅) 조건: 50점 이상이면 High Priority
    priority = "Low"
    if total_score >= 50:
        priority = "High"
        print(f"🎯 [TARGET] {company_name} (점수: {total_score}) -> 영업팀 전달 대상!")
        
        # Mart 테이블에 적재
        cursor.execute("INSERT OR IGNORE INTO sales_mart (company_id, priority) VALUES (?, ?)", (company_id, priority))

conn.commit()
conn.close()