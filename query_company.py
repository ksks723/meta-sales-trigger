import sys
from src.utils import normalize_company_name
from src.db import get_conn
from src.enrich import _search_naver_news, _search_wanted_jobs, _search_saramin_jobs, _search_naver_job_aggregates

# 감정 분석 함수 (간단 키워드 기반)
def analyze_sentiment(content):
    if not content:
        return '중립'
    positive_words = ['성장', '투자', '확장', '성공', '파트너십', '혁신', '상장', 'M&A', '증원', '채용']
    negative_words = ['부도', '폐업', '소송', '손실', '감원', '위기', '파산', '부정', '문제']
    pos_count = sum(1 for w in positive_words if w in content.lower())
    neg_count = sum(1 for w in negative_words if w in content.lower())
    if pos_count > neg_count:
        return '긍정'
    elif neg_count > pos_count:
        return '부정'
    else:
        return '중립'

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python query_company.py <회사명>")
        sys.exit(1)
    
    company_name = sys.argv[1]
    norm = normalize_company_name(company_name)
    
    conn = get_conn()
    cur = conn.cursor()
    
    # 투자 정보 조회
    cur.execute("SELECT * FROM raw_company_data WHERE lower(company_name) = ?", (norm,))
    row = cur.fetchone()
    
    print(f"\n=== {company_name} 회사 정보 ===\n")
    
    if row:
        print("📈 투자 정보:")
        print(f"  회사명: {row[1]}")
        print(f"  펀딩 단계: {row[3] or 'N/A'}")
        print(f"  펀딩 라운드: {row[4] or 'N/A'}")
        print(f"  펀딩 날짜: {row[5] or 'N/A'}")
        print(f"  금액: {row[6] or 'N/A'}")
        print(f"  투자자: {row[7] or 'N/A'}")
        print(f"  산업: {row[8] or 'N/A'}")
    else:
        print("📈 투자 정보: DB에 해당 회사의 투자 정보가 없습니다.")
    
    # 뉴스 조회 또는 검색
    if row:
        company_id = row[0]
        cur.execute("SELECT title, content, published_at, source_name FROM news WHERE company_id = ?", (company_id,))
        news_rows = cur.fetchall()
    else:
        # enrich로 뉴스 검색
        news_list = _search_naver_news(company_name)
        news_rows = [(n['title'], n['content'], n['published_at'], n['source_name']) for n in news_list]
    
    print("\n📰 뉴스 및 이슈 분석:")
    if news_rows:
        for n in news_rows[:5]:  # 최대 5개
            sentiment = analyze_sentiment(n[1] or n[0])
            print(f"  - {n[0]} ({n[2] or 'N/A'}) - 감정: {sentiment}")
            if n[1]:
                print(f"    내용 요약: {n[1][:200]}...")
    else:
        print("  뉴스 정보가 없습니다.")
    
    # 채용 조회 또는 검색
    if row:
        company_id = row[0]
        cur.execute("SELECT title, team, link, source FROM jobs WHERE company_id = ?", (company_id,))
        job_rows = cur.fetchall()
    else:
        # enrich로 채용 검색
        jobs = []
        jobs += _search_wanted_jobs(company_name)
        jobs += _search_saramin_jobs(company_name)
        jobs += _search_naver_job_aggregates(company_name)
        job_rows = [(j.get('title'), j.get('team'), j.get('link'), j.get('source')) for j in jobs if j.get('title')]
    
    print("\n💼 채용 정보:")
    if job_rows:
        for j in job_rows[:5]:  # 최대 5개
            print(f"  - {j[0]} (팀: {j[1] or 'N/A'}, 출처: {j[3] or 'N/A'})")
            if j[2]:
                print(f"    링크: {j[2]}")
    else:
        print("  채용 정보가 없습니다.")
    
    conn.close()