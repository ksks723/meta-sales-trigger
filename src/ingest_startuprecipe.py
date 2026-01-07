# 파일 최상단에 추가
import warnings
from urllib3.exceptions import NotOpenSSLWarning
warnings.filterwarnings("ignore", category=NotOpenSSLWarning)
import requests
from bs4 import BeautifulSoup
import re
import time
from urllib.parse import quote_plus
from pprint import pprint
from db import get_conn
from datetime import date
from os import getenv
import argparse

from utils import normalize_company_name, score_company_record


HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}


def _search_naver_news(company_name, max_items=3):
    """네이버 뉴스 검색에서 상위 기사 제목과 링크를 가져옵니다."""
    q = quote_plus(company_name)
    url = f'https://search.naver.com/search.naver?where=news&query={q}'
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
    except Exception:
        return []

    soup = BeautifulSoup(resp.text, 'html.parser')
    results = []
    # 여러 선택자 시도: 네이버 구조가 바뀔 수 있어 여유있게 탐색
    for a in soup.select('a._sp_each_title, a.news_tit, a.tit'):
        title = a.get_text(strip=True)
        href = a.get('href')
        if title and href:
            results.append({'title': title, 'link': href})
            if len(results) >= max_items:
                break
    return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='StartupRecipe ingestion pipeline')
    parser.add_argument('--only-enrich', action='store_true', help='Skip collection, only enrich existing data')
    parser.add_argument('--skip-enrich', action='store_true', help='Skip enrichment, only collect and save')
    parser.add_argument('--batch-size', type=int, default=50, help='Batch size for processing')
    parser.add_argument('--year', type=int, help='Year for period collection (e.g., 2025)')
    parser.add_argument('--start-month', type=int, help='Start month for period collection (1-12)')
    parser.add_argument('--end-month', type=int, help='End month for period collection (1-12)')
    parser.add_argument('--filter-company', type=str, help='Comma-separated list of company names to filter')
    parser.add_argument('--filter-industry', type=str, help='Comma-separated list of industries to filter')
    parser.add_argument('--update-old', action='store_true', help='Update companies not enriched in last 7 days')
    args = parser.parse_args()

    # 전체 파이프라인 실행: 수집 -> 엔리치 -> 미리보기 -> 저장
    from collect import scrape_startuprecipe_from_invest, scrape_startuprecipe_for_period
    from enrich import enrich_companies
    from store import preview, save_to_db

    if args.only_enrich:
        # DB에서 기존 회사 가져와 enrich만
        conn = get_conn()
        cur = conn.cursor()
        query = "SELECT id, company_name FROM raw_company_data WHERE 1=1"
        params = []
        if args.filter_company:
            companies = [c.strip() for c in args.filter_company.split(',')]
            query += " AND company_name IN ({})".format(','.join('?' * len(companies)))
            params.extend(companies)
        if args.filter_industry:
            industries = [i.strip() for i in args.filter_industry.split(',')]
            query += " AND industry IN ({})".format(','.join('?' * len(industries)))
            params.extend(industries)
        if args.update_old:
            query += " AND (last_enrich_date IS NULL OR last_enrich_date < date('now', '-7 days'))"
        rows = cur.execute(query, params).fetchall()
        collected = [{'name': r[1], 'id': r[0]} for r in rows]
        conn.close()
        enriched = enrich_companies(collected, max_news=3, max_jobs=5, show_sample=10)
        preview(enriched, n=10)
        save_to_db(enriched)
    elif args.skip_enrich:
        if args.year and args.start_month and args.end_month:
            collected = scrape_startuprecipe_for_period(args.year, args.start_month, args.end_month)
        else:
            collected = scrape_startuprecipe_from_invest(months=1)
        # enrich 없이 바로 save (기존 데이터 사용)
        enriched = collected  # job_roles, news_list 빈 리스트로
        for c in enriched:
            c['job_roles'] = []
            c['news_list'] = []
            c['inferred_event'] = 'unknown'
        preview(enriched, n=10)
        save_to_db(enriched)
    else:
        if args.year and args.start_month and args.end_month:
            collected = scrape_startuprecipe_for_period(args.year, args.start_month, args.end_month)
        else:
            collected = scrape_startuprecipe_from_invest(months=1)
        enriched = enrich_companies(collected, max_news=3, max_jobs=5, show_sample=10)
        preview(enriched, n=10)
        save_to_db(enriched)
    print('완료!')