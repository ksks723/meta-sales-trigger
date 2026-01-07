import requests
from bs4 import BeautifulSoup
import re
import time
from datetime import date, datetime, timedelta

HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}


def _months_back_dates(months=3):
    today = date.today()
    res = []
    y = today.year
    m = today.month
    for i in range(months):
        ym = m - i
        yy = y
        while ym <= 0:
            ym += 12
            yy -= 1
        res.append((yy, ym))
    return res


def scrape_startuprecipe_from_invest(months=3):
    """/invest?m_year=YYYY&m_month=MM 페이지를 지난 `months`개월분 가져와
    '핫딜(Top Deals)'과 'TOP' 표/목록을 우선 파싱하여 회사 목록을 반환합니다.
    반환: list of dict {name, source, funding_date, funding_stage, amount, investors, industry}
    최근 7일 이내 funding_date만 필터링.
    """
    base = "https://startuprecipe.co.kr/invest"
    companies = []
    seen_names = set()
    months_list = _months_back_dates(months)

           # check processed periods from DB to skip months already handled
    try:
        from db import get_conn
        conn = get_conn()
        cur = conn.cursor()
        done = set(r[0] for r in cur.execute("SELECT period FROM processed_periods").fetchall())
        conn.close()
    except Exception:
        done = set()

    for yy, mm in months_list:
        period_key = f"{yy}-{mm:02d}"
        if period_key in done:
            print(f"스킵(이미처리됨): {period_key}")
            continue
        params = f"?m_year={yy}&m_month={mm:02d}"
        url = base + params
        print(f"읽는 중(월별): {url}")
        try:
            resp = requests.get(url, headers=HEADERS, timeout=10)
            soup = BeautifulSoup(resp.text, 'html.parser')
            article = soup.find('article') or soup
            headings = article.find_all(['h2', 'h3', 'h4'])
            month_str = f"{yy}-{mm:02d}"

            for h in headings:
                htxt = h.get_text(strip=True)
                if any(k in htxt for k in ['핫 딜', 'Top Deals', 'Top deal', 'TOP DEALS', 'HOT DEAL', '이달의 핫 딜']):
                    container = h.find_next_sibling() or h.parent
                    # 테이블
                    for tr in container.find_all('tr'):
                        tds = tr.find_all(['td', 'th'])
                        if not tds:
                            continue
                        row_text = ' | '.join([td.get_text(' ', strip=True) for td in tds])
                        # 회사명 우선 추출(두번째 컬럼에 있는 경우가 많음)
                        cname = tds[1].get_text(strip=True) if len(tds) > 1 else tds[0].get_text(strip=True)
                        if not cname:
                            continue
                        if any(x in cname for x in ['회사', '기업', '회사명', '기업명', '업체']):
                            continue
                        if cname in seen_names:
                            continue
                        seen_names.add(cname)
                        meta = parse_invest_info(row_text)
                        companies.append({
                            'name': cname,
                            'source': '스타트업레시피',
                            'funding_date': meta.get('funding_date') or month_str,
                            'funding_stage': meta.get('funding_stage'),
                            'funding_round': meta.get('funding_round'),
                            'amount': meta.get('amount'),
                            'investors': meta.get('investors'),
                            'industry': meta.get('industry')
                        })
                    # 리스트
                    for li in container.find_all('li'):
                        text = li.get_text(separator=' ', strip=True)
                        text = re.sub(r'^\d{4}-\d{2}-\d{2}\s*[-–]?\s*', '', text)
                        parts = re.split(r'[\-–,|\(\)]', text)
                        cname = parts[0].strip() if parts else None
                        if not cname or len(cname) < 2:
                            m = re.search(r'([가-힣A-Za-z0-9&\-\.\s]{2,60})', text)
                            cname = m.group(1).strip() if m else None
                        if cname and cname not in seen_names:
                            seen_names.add(cname)
                            meta = parse_invest_info(text)
                            companies.append({
                                'name': cname,
                                'source': '스타트업레시피',
                                'funding_date': meta.get('funding_date') or month_str,
                                'funding_stage': meta.get('funding_stage'),
                                'funding_round': meta.get('funding_round'),
                                'amount': meta.get('amount'),
                                'investors': meta.get('investors'),
                                'industry': meta.get('industry')
                            })

            # 표 전반에서 회사명 추출 (TOP 15 등)
            for table in article.find_all('table'):
                # try to detect header mapping to identify company/date/amount columns
                colmap = detect_table_columns(table)
                for tr in table.find_all('tr'):
                    tds = tr.find_all(['td', 'th'])
                    if not tds:
                        continue
                    row_text = ' | '.join([td.get_text(' ', strip=True) for td in tds])
                    # pick company column based on detected mapping or fallback
                    cname = None
                    if colmap and colmap.get('company') is not None and len(tds) > colmap['company']:
                        cname = tds[colmap['company']].get_text(strip=True)
                    else:
                        cname = tds[1].get_text(strip=True) if len(tds) > 1 else tds[0].get_text(strip=True)
                    if not cname:
                        continue
                    if any(x in cname for x in ['회사', '기업', '회사명', '기업명', '업체']):
                        continue
                    if cname in seen_names:
                        continue
                    seen_names.add(cname)
                    meta = parse_invest_info(row_text)
                    # if we detected amount/investor columns, try to extract exact values
                    if colmap:
                        try:
                            if colmap.get('amount') is not None and len(tds) > colmap['amount']:
                                am = tds[colmap['amount']].get_text(' ', strip=True)
                                if am:
                                    meta['amount'] = meta.get('amount') or am
                            if colmap.get('investors') is not None and len(tds) > colmap['investors']:
                                iv = tds[colmap['investors']].get_text(' ', strip=True)
                                if iv:
                                    meta['investors'] = meta.get('investors') or iv
                            if colmap.get('industry') is not None and len(tds) > colmap['industry']:
                                ind = tds[colmap['industry']].get_text(' ', strip=True)
                                if ind:
                                    meta['industry'] = meta.get('industry') or ind
                            if colmap.get('date') is not None and len(tds) > colmap['date']:
                                fd = tds[colmap['date']].get_text(' ', strip=True)
                                if fd:
                                    meta['funding_date'] = meta.get('funding_date') or fd
                        except Exception:
                            pass

                    companies.append({
                        'name': cname,
                        'source': '스타트업레시피',
                        'funding_date': meta.get('funding_date') or month_str,
                        'funding_stage': meta.get('funding_stage'),
                        'funding_round': meta.get('funding_round'),
                        'amount': meta.get('amount'),
                        'investors': meta.get('investors'),
                        'industry': meta.get('industry')
                    })

            time.sleep(0.8)
        except Exception as e:
            print('에러:', e)
            continue

    print(f"월별 스캔 완료: {len(companies)}개 회사 수집")
    # 최근 7일 이내 funding_date만 필터링
    today = datetime.now().date()
    week_ago = today - timedelta(days=7)
    filtered = []
    for c in companies:
        fd_str = c.get('funding_date')
        if fd_str:
            try:
                fd = datetime.strptime(fd_str, '%Y-%m-%d').date()
                if fd >= week_ago:
                    filtered.append(c)
            except ValueError:
                # 날짜 파싱 실패 시 포함 (안전하게)
                filtered.append(c)
        else:
            filtered.append(c)
    print(f"최근 7일 필터링 후: {len(filtered)}개 회사")
    return filtered


def scrape_startuprecipe_for_period(year, start_month, end_month):
    """/invest?m_year=YYYY&m_month=MM 페이지를 지정된 기간의 월별로 가져와
    '핫딜(Top Deals)'과 'TOP' 표/목록을 우선 파싱하여 회사 목록을 반환합니다.
    반환: list of dict {name, source, funding_date, funding_stage, amount, investors, industry}
    필터링 없이 전체 데이터.
    """
    base = "https://startuprecipe.co.kr/invest"
    companies = []
    seen_names = set()

    for mm in range(start_month, end_month + 1):
        yy = year
        period_key = f"{yy}-{mm:02d}"
        params = f"?m_year={yy}&m_month={mm:02d}"
        url = base + params
        print(f"읽는 중(월별): {url}")
        try:
            resp = requests.get(url, headers=HEADERS, timeout=10)
            soup = BeautifulSoup(resp.text, 'html.parser')
            article = soup.find('article') or soup
            headings = article.find_all(['h2', 'h3', 'h4'])
            month_str = f"{yy}-{mm:02d}"

            # 모든 테이블을 찾아서 투자 데이터 파싱 (헤딩 의존성 제거)
            for table in article.find_all('table'):
                for tr in table.find_all('tr'):
                    tds = tr.find_all(['td', 'th'])
                    if len(tds) < 5:  # 최소 5개 컬럼: 날짜, 회사, 산업, 금액, 단계, 투자자
                        continue
                    row_text = ' | '.join([td.get_text(' ', strip=True) for td in tds])
                    # 첫 번째 컬럼이 날짜인지 확인 (YYYY-MM-DD 형식)
                    date_str = tds[0].get_text(strip=True)
                    if not re.match(r'\d{4}-\d{2}-\d{2}', date_str):
                        continue
                    # 회사명은 두 번째 컬럼
                    cname = tds[1].get_text(strip=True) if len(tds) > 1 else None
                    if not cname or len(cname) < 2:
                        continue
                    if any(x in cname for x in ['회사', '기업', '회사명', '기업명', '업체']):
                        continue
                    if cname in seen_names:
                        continue
                    seen_names.add(cname)
                    meta = parse_invest_info(row_text)
                    # 컬럼 매핑: 0:날짜, 1:회사, 2:산업, 3:금액, 4:단계, 5:투자자
                    if len(tds) > 2:
                        industry = tds[2].get_text(strip=True)
                        if industry:
                            meta['industry'] = meta.get('industry') or industry
                    if len(tds) > 3:
                        amount = tds[3].get_text(strip=True)
                        if amount:
                            meta['amount'] = meta.get('amount') or amount
                    if len(tds) > 4:
                        stage = tds[4].get_text(strip=True)
                        if stage:
                            meta['funding_stage'] = meta.get('funding_stage') or stage
                    if len(tds) > 5:
                        investors = tds[5].get_text(strip=True)
                        if investors:
                            meta['investors'] = meta.get('investors') or investors
                    companies.append({
                        'name': cname,
                        'source': '스타트업레시피',
                        'funding_date': date_str,
                        'funding_stage': meta.get('funding_stage'),
                        'funding_round': meta.get('funding_round'),
                        'amount': meta.get('amount'),
                        'investors': meta.get('investors'),
                        'industry': meta.get('industry')
                    })
        except Exception as e:
            print(f"월별 파싱 오류 {period_key}: {e}")
    print(f"지정 기간 스캔 완료: {len(companies)}개 회사 수집")
    return companies


def parse_invest_info(text: str) -> dict:
    """간단한 규칙으로 텍스트에서 funding metadata를 추출합니다."""
    res = {'funding_stage': None, 'funding_round': None, 'amount': None, 'investors': None, 'industry': None, 'funding_date': None}
    if not text:
        return res
    t = text
    # funding round
    rr = re.search(r'(Series\s*[ABCD]|Series\s*\w+|시리즈\s*[A-Za-z0-9]+|Seed|Pre[- ]?A|Pre[- ]?Seed|A\s*라운드|B\s*라운드)', t, re.IGNORECASE)
    if rr:
        res['funding_round'] = rr.group(0)
    if re.search(r'(Series|시리즈|Seed|Pre[- ]?A|VC|투자유치|투자)', t, re.IGNORECASE):
        res['funding_stage'] = 'funding'
    # amount
    am = re.search(r'([\d,\.]+\s*(억|만원|원|KRW|USD|\$|M|B))', t)
    if am:
        res['amount'] = am.group(0)
    else:
        am2 = re.search(r'(\d+[\d,]*\s*원|\d+[\d,]*\s*억)', t)
        if am2:
            res['amount'] = am2.group(0)
    # investors
    iv = re.search(r'(투자사[:\s]*|투자[:\s]*|by\s*)([가-힣A-Za-z0-9,·&\s]+)', t)
    if iv:
        res['investors'] = iv.group(2).strip().strip(',')
    # industry: short parentheses
    par = re.search(r'\(([^)]+)\)', t)
    if par:
        inside = par.group(1).strip()
        if len(inside) <= 40 and not re.search(r'\d', inside):
            res['industry'] = inside
    # funding_date
    fd = re.search(r'(\d{4}-\d{2}-\d{2}|\d{4}\.\d{2}\.\d{2}|\d{4}-\d{2})', t)
    if fd:
        res['funding_date'] = fd.group(0).replace('.', '-')
    return res


def detect_table_columns(table):
    """테이블 헤더를 분석해 어느 컬럼이 회사명/날짜/금액/투자사/산업인지 추정합니다.
    반환: dict e.g. {'company':1,'date':0,'amount':3,'investors':4,'industry':2}
    """
    headers = []
    # look for header row
    thead = table.find('thead')
    if thead:
        header_cells = thead.find_all(['th', 'td'])
        headers = [c.get_text(' ', strip=True).lower() for c in header_cells]
    else:
        # fallback: first row if it looks like header (contains non-numeric words)
        first_row = table.find('tr')
        if first_row:
            cells = first_row.find_all(['th', 'td'])
            txts = [c.get_text(' ', strip=True) for c in cells]
            # heuristics: if many cells contain words like '회사' or '기업' treat as header
            if any(re.search(r'회사|기업|업종|투자|금액|라운드|날짜|invest', t, re.IGNORECASE) for t in txts):
                headers = [t.lower() for t in txts]

    mapping = {}
    if not headers:
        return None

    for i, h in enumerate(headers):
        if re.search(r'회사|기업|회사명|기업명|company', h):
            mapping['company'] = i
        if re.search(r'날짜|일자|date|년|월', h):
            mapping['date'] = i
        if re.search(r'금액|amount|원|억|krw|usd|m|b', h):
            mapping['amount'] = i
        if re.search(r'투자사|투자자|investor|invest', h):
            mapping['investors'] = i
        if re.search(r'업종|산업|industry|category', h):
            mapping['industry'] = i
        if re.search(r'라운드|round|series', h):
            mapping['funding_round'] = i

    return mapping if mapping else None
