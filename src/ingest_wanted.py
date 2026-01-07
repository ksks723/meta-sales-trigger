import sqlite3
import requests
from bs4 import BeautifulSoup
import re
from db import get_conn

def scrape_wanted_real():
    """원티드 세일즈/마케팅 채용 실제 크롤링"""
    url = "https://www.wanted.co.kr/wdlist/518"  # 세일즈 직무
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
    
    try:
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 실제 원티드 클래스명으로 회사명/직무 추출
        job_cards = soup.find_all('div', class_=re.compile(r'JobCard'))
        companies = []
        
        for card in job_cards[:8]:
            company_elem = card.find(['a', 'span'], string=re.compile(r'[가-힣]{2,}'))
            role_elem = card.find(['span', 'div'], string=re.compile(r'영업|세일즈|마케팅|BD'))
            
            if company_elem:
                company_name = re.findall(r'[가-힣]{2,6}', company_elem.get_text())[0]
                role = role_elem.get_text()[:20] if role_elem else "영업/마케팅"
                
                companies.append({
                    'name': company_name,
                    'source': '원티드',
                    'funding_stage': '채용확장',
                    'funding_date': '2025-12',
                    'job_roles': role,
                    'news_title': f"{company_name} {role} 채용중"
                })
        
        return companies
    except Exception as e:
        print(f"원티드 크롤링 에러: {e}")
        return []

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
        print(f"✅ {company['name']} ({company['job_roles']}) 저장!")
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    companies = scrape_wanted_real()
    save_to_db(companies)
    print(f"🎉 원티드 {len(companies)}개 완료!")
