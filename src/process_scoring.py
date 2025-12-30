import sqlite3

def calculate_score(row):
    # row: (id, company_name, funding_stage, funding_date, job_roles)
    score = 0
    
    # 1. 투자 점수 (Rule)
    if "Series A" in row[2]:
        score += 30
    elif "Seed" in row[2]:
        score += 10
        
    # 2. 채용 점수 (Rule)
    jobs = row[4]
    if "세일즈" in jobs or "영업" in jobs:
        score += 25
    if "마케터" in jobs or "마케팅" in jobs:
        score += 20
        
    # 3. 최신성 점수 (간단 로직)
    if "2024-11" in row[3] or "2024-12" in row[3]:
        score += 10
        
    return score

conn = sqlite3.connect('../data/meta_sales_trigger.db')
cursor = conn.cursor()

# Raw 데이터 가져오기
cursor.execute("SELECT id, company_name, funding_stage, funding_date, job_roles FROM raw_company_data")
rows = cursor.fetchall()

print("🧮 스코어링 분석 시작...")

for row in rows:
    company_id = row[0]
    company_name = row[1]
    
    # 점수 계산 함수 호출
    total_score = calculate_score(row)
    
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