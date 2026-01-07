from db import get_conn
from pprint import pprint
from utils import normalize_company_name, score_company_record
from datetime import datetime
import re


def preview(companies, n=10):
    print('\n== Preview (first {} items) =='.format(n))
    pprint(companies[:n])


def save_to_db(companies):
    conn = get_conn()
    cur = conn.cursor()

    # collect periods that were processed (if present on records)
    processed_periods = set()

    for c in companies:
        raw_name = c.get('name')
        norm = normalize_company_name(raw_name)
        if not norm or len(norm) < 2:
            print(f"스킵(이름불가): {raw_name}")
            continue

        cur.execute("SELECT id FROM raw_company_data WHERE lower(company_name) = ?", (norm,))
        if cur.fetchone():
            print(f"이미 존재(중복): {raw_name}")
            continue

        news_title = c.get('news_list')[0]['title'] if c.get('news_list') else None
        # job_roles can be list of strings or list of dicts {'title','team','link'}
        jobs = c.get('job_roles') or []
        jobs_summary = None
        required_roles = set()
        if jobs:
            if all(isinstance(j, dict) for j in jobs):
                parts = []
                for j in jobs:
                    team = j.get('team') or 'Other'
                    title = j.get('title') or ''
                    parts.append(f"{team}: {title}")
                    if team and team != 'Other':
                        required_roles.add(team)
                jobs_summary = ', '.join(parts)
            else:
                jobs_summary = ', '.join(jobs)
        required_roles_str = ', '.join(sorted(required_roles)) if required_roles else None

        # keywords from news
        keywords = set()
        for n in c.get('news_list') or []:
            text = (n.get('title') or '') + ' ' + (n.get('content') or '')
            # 간단 키워드 추출: 명사 추출 (간단히 단어 분리)
            words = re.findall(r'\b[가-힣]{2,}\b', text)
            for w in words:
                if len(w) > 1 and w not in ['있는', '하는', '된다', '했다']:  # 불용어
                    keywords.add(w)
        keywords_str = ', '.join(sorted(list(keywords)[:10])) if keywords else None  # 최대 10개

        cur.execute('''
        INSERT INTO raw_company_data (company_name, source, funding_stage, funding_round, funding_date, amount, investors, industry, keywords, required_roles, job_roles, news_title, founded_date, employee_count, last_enrich_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            raw_name,
            c.get('source'),
            c.get('funding_stage'),
            c.get('funding_round'),
            c.get('funding_date'),
            c.get('amount'),
            c.get('investors'),
            c.get('industry'),
            keywords_str,
            required_roles_str,
            jobs_summary,
            news_title,
            c.get('founded_date'),
            c.get('employee_count'),
            datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ))
        last_id = cur.lastrowid

        # persist structured news rows
        for n in c.get('news_list') or []:
            try:
                title = n.get('title')
                url = n.get('link')
                if title and url:
                    # 중복 체크: 같은 company_id, title, url
                    cur.execute("SELECT id FROM news WHERE company_id = ? AND title = ? AND url = ?", (last_id, title, url))
                    if not cur.fetchone():
                        cur.execute("INSERT INTO news (company_id, title, content, url, published_at, source_name, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                    (last_id, title, n.get('content'), url, n.get('published_at'), n.get('source_name'), datetime.now()))
            except Exception:
                pass

        # persist structured job rows
        for j in c.get('job_roles') or []:
            try:
                if isinstance(j, dict):
                    title = j.get('title')
                    if title:
                        print(f"Inserting job: {title}")  # Debug print
                        # 중복 체크: 같은 company_id, title
                        cur.execute("SELECT id FROM jobs WHERE company_id = ? AND title = ?", (last_id, title))
                        if not cur.fetchone():
                            cur.execute("INSERT INTO jobs (company_id, title, team, link, source, collected_at) VALUES (?, ?, ?, ?, ?, ?)",
                                        (last_id, title, j.get('team'), j.get('link'), j.get('source') or 'wanted', datetime.now()))
                            print(f"Inserted job: {title}")  # Debug print
                else:
                    # string job
                    cur.execute("INSERT INTO jobs (company_id, title, team, link, source, collected_at) VALUES (?, ?, ?, ?, ?, ?)",
                                (last_id, j, None, None, 'unknown', datetime.now()))
            except Exception as e:
                print(f"Error inserting job: {e}")  # Debug print

        scores = score_company_record(c)
        cur.execute("INSERT OR REPLACE INTO signal_scores (company_id, funding_score, hiring_score, recency_score, total_score) VALUES (?, ?, ?, ?, ?)",
                    (last_id, scores['funding_score'], scores['hiring_score'], scores['recency_score'], scores['total_score']))
        print(f"저장: {raw_name} (id={last_id}) score={scores['total_score']}")

        # collect processed period if funding_date present in YYYY-MM or YYYY-MM-DD
        fd = c.get('funding_date')
        if fd:
            m = None
            mobj = re.search(r'(\d{4}-\d{2})', fd)
            if mobj:
                m = mobj.group(1)
            elif re.match(r'^\d{4}-\d{2}-\d{2}$', fd):
                m = fd[:7]
            if m:
                processed_periods.add(m)

    # mark processed periods
    for p in processed_periods:
        try:
            cur.execute("INSERT OR IGNORE INTO processed_periods (period) VALUES (?)", (p,))
        except Exception:
            pass

    conn.commit()
    conn.close()
