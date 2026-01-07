import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import quote_plus
from os import getenv
from pprint import pprint
import time

HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}


def _search_naver_news(company_name, max_items=3, from_date=None, to_date=None):
    # NewsAPI 우선 사용
    api_key = getenv('NEWSAPI_KEY')
    if api_key:
        try:
            params = {
                'q': quote_plus(company_name),
                'language': 'ko',
                'pageSize': max_items,
                'sortBy': 'publishedAt'
            }
            if from_date:
                params['from'] = from_date
            if to_date:
                params['to'] = to_date
            api_url = 'https://newsapi.org/v2/everything'
            r = requests.get(api_url, params={**params, 'apiKey': api_key}, timeout=10)
            if r.status_code == 200:
                j = r.json()
                res = []
                for art in j.get('articles', [])[:max_items]:
                    title = art.get('title', '')
                    url = art.get('url', '')
                    content = art.get('description', '') or art.get('content', '')
                    published_at = art.get('publishedAt', '')
                    source_name = art.get('source', {}).get('name', '')
                    res.append({
                        'title': title,
                        'link': url,
                        'content': content,
                        'published_at': published_at,
                        'source_name': source_name
                    })
                return res
        except Exception as e:
            print(f"NewsAPI error: {e}")

    # Naver 폴백
    q = quote_plus(company_name)
    url = f"https://search.naver.com/search.naver?where=news&query={q}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.text, 'html.parser')
        items = []
        selectors = ['.news_tit']
        for sel in selectors:
            for a in soup.select(sel)[:max_items]:
                title = a.get_text().strip()
                href = a.get('href')
                if title and href and 'news.naver.com' in href:
                    # published_at 추출 시도
                    published_at = ''
                    parent = a.find_parent('li') or a.find_parent('div')
                    if parent:
                        time_elem = parent.find('span', class_='info') or parent.find('time')
                        if time_elem:
                            published_at = time_elem.get_text(strip=True)
                    items.append({
                        'title': title,
                        'link': href,
                        'content': '',
                        'published_at': published_at,
                        'source_name': 'Naver'
                    })
            if items:
                return items[:max_items]
    except Exception as e:
        print(f"Naver news error: {e}")

    return []


def _search_naver_job_aggregates(company_name, max_items=5):
    """네이버에서 '회사명 + 채용' 검색으로 채용 공고를 직접 추출."""
    q = quote_plus(f"{company_name} 채용")
    url = f"https://search.naver.com/search.naver?where=web&query={q}"
    jobs = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.text, 'html.parser')
        # 검색 결과에서 채용 관련 제목 추출
        for a in soup.select('a[href]'):
            href = a.get('href')
            title = a.get_text(strip=True)
            if href and href.startswith('http') and ('채용' in title or '공고' in title or '모집' in title or 'recruit' in title.lower() or 'hiring' in title.lower()):
                jobs.append({
                    'title': title,
                    'team': classify_job_team(title),
                    'link': href,
                    'source': 'Naver Search'
                })
                if len(jobs) >= max_items:
                    break
    except Exception as e:
        print(f"Naver job aggregate error: {e}")
    return jobs

def _search_wanted_jobs(company_name, max_items=5):
    for attempt in range(3):
        try:
            q = quote_plus(company_name)
            url = f"https://www.wanted.co.kr/search?query={q}"
            resp = requests.get(url, headers=HEADERS, timeout=10)
            soup = BeautifulSoup(resp.text, 'html.parser')
            jobs = []
            cards = soup.find_all('div', class_=re.compile(r'JobCard'), limit=max_items)
            if not cards:
                cards = soup.select('.card-job, .job-card')[:max_items]
            for card in cards[:max_items]:
                title_elem = card.find(['a', 'h3', 'strong', 'h4'])
                team_elem = None
                for sel in ['.job-meta', '.JobCard_meta', '.meta', '.tags', '.job-tag']:
                    team_elem = card.select_one(sel)
                    if team_elem:
                        break
                title = title_elem.get_text().strip() if title_elem else None
                team = None
                if team_elem:
                    team = team_elem.get_text().strip()
                a = card.find('a', href=True)
                link = None
                if a:
                    link = a.get('href')
                    if link and link.startswith('/'):
                        link = 'https://www.wanted.co.kr' + link
                if title:
                    jobs.append({'title': title, 'team': classify_job_team(title if not team else team), 'link': link})
            return jobs
        except Exception as e:
            print(f"Wanted jobs error on attempt {attempt+1}: {e}")
            if attempt < 2:
                time.sleep(1)
    return []


def _search_saramin_jobs(company_name, max_items=5):
    """사람인에서 회사명으로 공고 검색해서 제목을 반환합니다(간단 시도)."""
    try:
        q = quote_plus(company_name)
        url = f'https://www.saramin.co.kr/zf_user/search?searchword={q}'
        resp = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.text, 'html.parser')
        jobs = []
        for li in soup.select('div.item_recruit, .recruit_item')[:max_items]:
            title = None
            link = None
            a = li.select_one('a[href]')
            if a:
                title = a.get_text(strip=True)
                link = a.get('href')
                if link and link.startswith('/'):
                    link = 'https://www.saramin.co.kr' + link
            if title:
                jobs.append({'title': title, 'team': classify_job_team(title), 'link': link, 'source': 'Saramin'})
        return jobs
    except Exception:
        return []


def _search_company_careers(company_name, max_items=5):
    """회사 도메인에 흔한 채용 경로(/career, /careers, /recruit, /jobs)를 시도해 채용 제목을 수집합니다."""
    trials = ['/career', '/careers', '/recruit', '/recruitment', '/jobs', '/채용']
    jobs = []
    # try to find company homepage via simple Google-free heuristic: company-name + .com (best-effort)
    # This is a light heuristic; real solution should use a proper lookup (whois, company profile)
    candidate_domains = [f'https://{company_name}.com', f'https://{company_name}.co.kr']
    for base in candidate_domains:
        for p in trials:
            try:
                url = base + p
                r = requests.get(url, headers=HEADERS, timeout=6)
                if r.status_code != 200:
                    continue
                s = BeautifulSoup(r.text, 'html.parser')
                # look for job listing anchors
                found = 0
                for a in s.select('a'):
                    txt = a.get_text(strip=True)
                    if re.search(r'채용|recruit|career|job', txt, re.IGNORECASE):
                        link = a.get('href')
                        if link and link.startswith('/'):
                            link = base + link
                        jobs.append({'title': txt, 'team': classify_job_team(txt), 'link': link})
                        found += 1
                        if found >= max_items:
                            break
                if jobs:
                    return jobs[:max_items]
            except Exception:
                continue
    return jobs


def classify_job_team(title: str) -> str:
    """직무 제목을 간단 키워드 매핑으로 팀(부서)으로 분류합니다."""
    if not title:
        return 'Other'
    t = title.lower()
    marketing_kw = ['마케', 'marketing', 'crm', '퍼포먼스', 'growth', '광고', '프로모션']
    product_kw = ['product', '프로덕트', '기획', 'pd']
    eng_kw = ['engineer', '개발', '프론트', '백엔드', 'dev', 'data', 'ai', 'ml', 'software']
    sales_kw = ['sales', '영업', 'biz', 'bd']
    design_kw = ['디자', 'ux', 'ui', 'designer']
    hr_kw = ['채용', '인사', 'hr', 'recruit']

    for kw in marketing_kw:
        if kw in t:
            return 'Marketing'
    for kw in product_kw:
        if kw in t:
            return 'Product'
    for kw in eng_kw:
        if kw in t:
            return 'Engineering'
    for kw in sales_kw:
        if kw in t:
            return 'Sales'
    for kw in design_kw:
        if kw in t:
            return 'Design'
    for kw in hr_kw:
        if kw in t:
            return 'HR'
    return 'Other'


def _infer_event_from_news(news_titles):
    growth_kw = ['투자', '유치', '상장', '확장', '합류', '인수', '시리즈']
    decline_kw = ['감원', '적자', '구조조정', '폐업', '축소']
    text = ' '.join(news_titles)
    for kw in growth_kw:
        if kw in text:
            return 'growing'
    for kw in decline_kw:
        if kw in text:
            return 'declining'
    return 'unknown'

def _search_company_info(company_name):
    """Naver 검색으로 회사 설립일과 직원수 추출."""
    q = quote_plus(f"{company_name} 설립일 직원수")
    url = f'https://search.naver.com/search.naver?query={q}'
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
    except Exception:
        return {'founded_date': None, 'employee_count': None}

    soup = BeautifulSoup(resp.text, 'html.parser')
    founded_date = None
    employee_count = None

    # 설립일 패턴: YYYY년 MM월 DD일 또는 YYYY년
    founded_pattern = re.compile(r'(\d{4})년(?:\s*(\d{1,2})월(?:\s*(\d{1,2})일)?)?')
    # 직원수 패턴: XXX명 또는 XXX명 이상
    employee_pattern = re.compile(r'(\d{1,4})명(?:\s*이상)?')

    text = soup.get_text()
    founded_match = founded_pattern.search(text)
    if founded_match:
        year = founded_match.group(1)
        month = founded_match.group(2) or '01'
        day = founded_match.group(3) or '01'
        founded_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"

    employee_match = employee_pattern.search(text)
    if employee_match:
        employee_count = employee_match.group(1)

    return {'founded_date': founded_date, 'employee_count': employee_count}

def enrich_companies(companies, max_news=3, max_jobs=5, show_sample=5):
    """각 회사에 대해 뉴스/채용 조회 및 이벤트 추론을 수행하고 결과 리스트 반환"""
    out = []
    for i, c in enumerate(companies):
        name = c.get('name')
        # 뉴스 검색 시 투자 날짜 기준으로 기간 설정
        funding_date = c.get('funding_date')
        if funding_date:
            try:
                from datetime import datetime, timedelta
                fd = datetime.fromisoformat(funding_date)
                from_date = (fd - timedelta(days=7)).strftime('%Y-%m-%d')
                to_date = (fd + timedelta(days=7)).strftime('%Y-%m-%d')
                news = _search_naver_news(name, max_items=max_news, from_date=from_date, to_date=to_date)
            except Exception:
                news = _search_naver_news(name, max_items=max_news)
        else:
            news = _search_naver_news(name, max_items=max_news)
        jobs = _search_wanted_jobs(name, max_items=max_jobs)
        # 추가 소스: 사람인, 회사 도메인, 네이버 집계
        try:
            saramin_jobs = _search_saramin_jobs(name, max_items=max_jobs)
            if saramin_jobs:
                jobs.extend(saramin_jobs)
        except Exception:
            pass
        try:
            company_jobs = _search_company_careers(name, max_items=max_jobs)
            if company_jobs:
                jobs.extend(company_jobs)
        except Exception:
            pass
        try:
            naver_jobs = _search_naver_job_aggregates(name, max_items=max_jobs)
            if naver_jobs:
                jobs.extend(naver_jobs)
        except Exception:
            pass
        # dedupe by title
        seen = set()
        dedup_jobs = []
        for j in jobs:
            key = (j.get('title') or '').strip()
            if not key or key in seen:
                continue
            seen.add(key)
            dedup_jobs.append(j)
        jobs = dedup_jobs[:max_jobs]
        event = _infer_event_from_news([n['title'] for n in news])
        company_info = _search_company_info(c['name'])
        nc = dict(c)
        nc['news_list'] = news
        nc['job_roles'] = jobs
        nc['inferred_event'] = event
        nc['founded_date'] = company_info['founded_date']
        nc['employee_count'] = company_info['employee_count']
        out.append(nc)

    print(f"엔리치 완료: {len(out)}개")
    print(f"샘플(처음 {show_sample}):")
    pprint(out[:show_sample])
    return out
