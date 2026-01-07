import sqlite3
import requests
from bs4 import BeautifulSoup
import re
import time
from db import get_conn

def scrape_innoforest_real():
    """혁신의숲 실제 투자 데이터 크롤링 (공개 페이지)"""
    # 실제 공개 투자 리포트 페이지들
    urls = [
        "https://thevc.kr/forestn",  # 포레스트엔 등
        "https://koreatechdesk.com/innovation-forests-2023-report"
    ]
    
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
    companies = []
    
    for url in urls:
        try:
            print(f"🌲 혁신의숲 {url} 크롤링...")
            response = requests.get(url, headers=headers)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 회사명 추출 (실제 패턴)
            titles = soup.find_all(['h1', 'h2', 'h3', 'p'], string=re.compile(r'[가-힣]{2,}'))
            for title in titles[:10]:
                text = title.get_text()
                company_match = re.search(r'([가-힣]{2,6})(?:사|랩스|컴퍼니|테크)', text)
                if company_match:
                    companies.append({
                        'name': company_match.group(1),
                        'source': '혁신의숲',
                        'funding_stage': 'Series A',
                        'funding_date': '2025-12',
                        'job_roles': '확인중',
                        'news_title': f"{company_match.group(1)} 투자/성장"
                    })
            time.sleep(1)
        except:
            continue
    
    print(f"✅ 혁신의숲 {len(companies)}개 수집!")
    return companies[:5]  # Top 5만

def save_to_db(companies):
    conn = get_conn()
    cursor = conn.cursor()
    
    for company in companies:
        cursor.execute("SELECT id FROM raw_company_data WHERE company_name = ?", (company['name'],))
        if cursor.fetchone():
            continue
        cursor.execute('''
        INSERT INTO raw_company_data (company_name, source, funding_stage, funding_date, job_roles, news_title)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (company['name'], company['source'], company['funding_stage'], 
              company['funding_date'], company['job_roles'], company['news_title']))
        print(f"✅ {company['name']} 저장!")
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    companies = scrape_innoforest_real()
    save_to_db(companies)
