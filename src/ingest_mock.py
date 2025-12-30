import sqlite3

# 샘플 데이터 (슬기님이 분석한 내용)
sample_data = [
    ("드래프타입", "혁신의숲", "Series A", "2024-10", "비주얼 콘텐츠 디자이너", "AI 콘텐츠 솔루션 수요 급증"),
    ("무촌", "혁신의숲", "Series A", "2024-11", "세일즈 매니저, 콘텐츠 마케터", "전국 단위 서비스 확장"),
    ("세라트젠", "원티드", "Seed", "2024-12", "의료미용성형 사업기획", "바이오 소재 사업 확장")
]

conn = sqlite3.connect('../data/meta_sales_trigger.db')
cursor = conn.cursor()

print("🔄 데이터 수집(Mocking) 시작...")

for data in sample_data:
    # 중복 방지 로직 (이미 있으면 건너뜀)
    cursor.execute("SELECT id FROM raw_company_data WHERE company_name = ?", (data[0],))
    if cursor.fetchone():
        print(f"⚠️ {data[0]}: 이미 존재하는 데이터입니다.")
        continue
        
    cursor.execute('''
    INSERT INTO raw_company_data (company_name, source, funding_stage, funding_date, job_roles, news_title)
    VALUES (?, ?, ?, ?, ?, ?)
    ''', data)
    print(f"✅ {data[0]}: Raw 데이터 저장 완료")

conn.commit()
conn.close()