import re
from datetime import datetime


def normalize_company_name(name: str) -> str:
    """간단한 회사명 정규화

    - 괄호/괄호 내 텍스트 제거
    - 앞뒤 공백 제거, 다중 공백 축소
    - 영문/특수문자 정리(대문자->소문자)
    - 일부 접미사/접두사 제거(예: 주식회사, (주))
    """
    if not name:
        return name
    s = name
    # 제거: 괄호 안 내용
    s = re.sub(r"\([^)]*\)", "", s)
    s = re.sub(r"\[[^]]*\]", "", s)
    # 회사 형태 표기 제거
    s = re.sub(r"\b(주식회사|주식회사\.|㈜|\(주\)|주)\b", "", s)
    # 특수문자 제거 (단, & . -는 유지)
    s = re.sub(r"[^\w\s\-\.&]", " ", s)
    # 공백 정리
    s = re.sub(r"\s+", " ", s).strip()
    # 소문자 변환(영문일 경우)
    s = s.lower()
    return s


def score_company_record(record: dict) -> dict:
    """간단 스코어 계산기

    반환 dict: {'funding_score', 'hiring_score', 'recency_score', 'total_score'}
    규칙(예시):
      - funding_score: inferred_event 기반 (growing:3, unknown:1, declining:0)
      - hiring_score: 채용건수 기반 (0:0, 1-2:1, >=3:2)
      - recency_score: funding_date 기준(월 단위)
    """
    funding_score = 0
    hiring_score = 0
    recency_score = 0

    ie = (record.get('inferred_event') or '').lower()
    if 'grow' in ie or 'growing' in ie or '투자' in ie:
        funding_score = 3
    elif 'declin' in ie or '감소' in ie:
        funding_score = 0
    else:
        funding_score = 1

    jobs = record.get('job_roles') or []
    if isinstance(jobs, (list, tuple)):
        jcount = len(jobs)
    elif isinstance(jobs, str):
        jcount = 1 if jobs.strip() else 0
    else:
        jcount = 0
    if jcount == 0:
        hiring_score = 0
    elif jcount <= 2:
        hiring_score = 1
    else:
        hiring_score = 2

    fd = record.get('funding_date')
    # funding_date expected 'YYYY-MM' or 'YYYY-MM-DD'
    if fd:
        try:
            if re.match(r'^\d{4}-\d{2}-\d{2}$', fd):
                dt = datetime.strptime(fd, '%Y-%m-%d')
            elif re.match(r'^\d{4}-\d{2}$', fd):
                dt = datetime.strptime(fd, '%Y-%m')
            else:
                dt = None
            if dt:
                delta_months = (datetime.now().year - dt.year) * 12 + (datetime.now().month - dt.month)
                if delta_months <= 1:
                    recency_score = 3
                elif delta_months <= 3:
                    recency_score = 2
                elif delta_months <= 6:
                    recency_score = 1
                else:
                    recency_score = 0
        except Exception:
            recency_score = 0
    else:
        recency_score = 0

    total = funding_score + hiring_score + recency_score
    return {
        'funding_score': funding_score,
        'hiring_score': hiring_score,
        'recency_score': recency_score,
        'total_score': total
    }
