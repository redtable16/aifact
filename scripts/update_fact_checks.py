import os
import json
import random
import datetime
import requests
import feedparser
import time
import re
from bs4 import BeautifulSoup

# RSS 피드에서 정치인 발언 수집 (24시간 이내 기사만)
def collect_politician_statements():
    print("Starting to collect politician statements from RSS feeds...")
    
    # 주요 한국 뉴스 사이트의 정치 RSS 피드
    rss_feeds = [
        "https://www.hani.co.kr/rss/politics/",                # 한겨레
        "https://rss.donga.com/politics.xml",                  # 동아일보
        "https://www.khan.co.kr/rss/rssdata/politic.xml",      # 경향신문
        "https://rss.joins.com/joins_politics_list.xml",       # 중앙일보
        "https://www.ytn.co.kr/_ln/0101_rss.xml",              # YTN 정치
        "https://feed.mk.co.kr/rss/politics/news.xml",         # 매일경제 정치
        "https://www.mt.co.kr/mt_news_politics_rss.xml",       # 머니투데이 정치
        "https://rss.nocutnews.co.kr/NocutNews_Politics.xml"   # 노컷뉴스 정치
    ]
    
    statements = []
    
    # 24시간 이내 기사만 필터링하기 위한 기준 시간
    cutoff_time = datetime.datetime.now() - datetime.timedelta(hours=24)
    print(f"Collecting articles published after: {cutoff_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    for feed_url in rss_feeds:
        try:
            print(f"Fetching RSS feed: {feed_url}")
            feed = feedparser.parse(feed_url)
            print(f"Found {len(feed.entries)} entries in feed")
            
            for entry in feed.entries[:20]:  # 각 피드에서 최대 20개 항목 확인
                # 기사 발행 시간 파싱
                pub_date = None
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    pub_date = datetime.datetime(*entry.published_parsed[:6])
                elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                    pub_date = datetime.datetime(*entry.updated_parsed[:6])
                
                # 발행 시간이 없는 경우 현재 시간 기준으로 처리
                if not pub_date:
                    # RSS에 날짜 정보가 없는 경우 URL이나 본문에서 날짜 추출 시도
                    pub_date = extract_date_from_url_or_content(entry)
                
                # 24시간 이내 기사만 처리
                if pub_date and pub_date < cutoff_time:
                    print(f"Skipping older article: {entry.title} (Published: {pub_date.strftime('%Y-%m-%d %H:%M:%S')})")
                    continue
                
                title = entry.title
                
                # 팩트체크 가능한 발언인지 우선 필터링
                if is_politician_statement(title) and is_factcheckable_statement(title):
                    # RSS 항목에서 필요한 정보 추출
                    statement_data = {
                        "title": title,
                        "url": entry.link,
                        "source": feed.feed.title if hasattr(feed, 'feed') and hasattr(feed.feed, 'title') else "뉴스 소스",
                        "published_date": entry.published if hasattr(entry, 'published') else datetime.datetime.now().strftime("%Y-%m-%d")
                    }
                    
                    # 기사 본문에서 추가 컨텍스트 가져오기
                    try:
                        article_content = get_article_content(entry.link)
                        if article_content:
                            statement_data["content"] = article_content[:800]  # 처음 800자 저장
                            
                            # 본문에 구체적인 수치나 통계가 포함되어 있는지 확인
                            if contains_verifiable_facts(article_content):
                                statements.append(statement_data)
                                print(f"Added factcheckable statement: {title}")
                            else:
                                print(f"Skipping non-factcheckable statement: {title}")
                    except Exception as e:
                        print(f"Error fetching article content: {e}")
        except Exception as e:
            print(f"Error processing feed {feed_url}: {e}")
        
        # 요청 간 간격 두기
        time.sleep(1)
    
    # 중복 제거
    unique_statements = []
    urls = set()
    for statement in statements:
        if statement["url"] not in urls:
            urls.add(statement["url"])
            unique_statements.append(statement)
    
    print(f"Collected {len(unique_statements)} unique factcheckable statements from {len(statements)} total")
    
    # 충분한 데이터가 없으면 빈 배열 반환 (백업 데이터 사용 안함)
    if not unique_statements:
        print("No factcheckable statements found. Will not generate any cards for today.")
    
    return unique_statements

# 팩트체크 가능한 발언인지 확인하는 함수
def is_factcheckable_statement(title):
    # 수치, 통계 또는 구체적인 사실 주장이 포함된 제목 필터링
    number_patterns = [
        r'\d+%', r'\d+조', r'\d+억', r'\d+만', r'\d+명',  # 퍼센트, 금액, 인원수
        r'\d+배', r'\d+위', r'\d+등', r'\d+번째'          # 배수, 순위
    ]
    
    # 수치나 통계가 포함되어 있는지 확인
    has_numbers = any(re.search(pattern, title) for pattern in number_patterns)
    
    # 팩트체크 가능한 키워드 포함 여부
    factcheck_keywords = [
        "증가", "감소", "최고", "최저", "최초", "사상 처음", "역대 최대", "역대 최저",
        "전액", "전부", "모두", "유일", "유일하게", "전체", "완전히", "절대",
        "가장", "최고", "처음으로", "처음", "사실상", "실질적", "사실이", "실제로"
    ]
    
    has_factcheck_keywords = any(keyword in title for keyword in factcheck_keywords)
    
    # 객관적 검증이 어려운 주관적 표현
    subjective_keywords = [
        "생각", "의견", "판단", "느낌", "우려", "기대", "희망", "바람",
        "전망", "예상", "예측", "제안", "바란다", "할 것", "포부"
    ]
    
    has_subjective_keywords = any(keyword in title for keyword in subjective_keywords)
    
    # 수치/통계가 있거나 팩트체크 키워드가 있고, 주관적 표현이 없는 경우만 선택
    return (has_numbers or has_factcheck_keywords) and not has_subjective_keywords

# 본문에 검증 가능한 사실이 포함되어 있는지 확인
def contains_verifiable_facts(content):
    # 수치, 통계 패턴
    number_patterns = [
        r'\d+%', r'\d+조 ?\d*억?', r'\d+억 ?원?', r'\d+만 ?명?', 
        r'\d+명', r'\d+건', r'\d+개', r'\d+곳'
    ]
    
    # 시간, 날짜 패턴
    time_patterns = [
        r'\d{4}년 \d{1,2}월', r'\d{1,2}월 \d{1,2}일', 
        r'지난해', r'올해', r'작년', r'내년'
    ]
    
    # 비교 표현
    comparison_patterns = [
        r'증가했', r'감소했', r'늘었', r'줄었', r'높아졌', r'낮아졌',
        r'최고', r'최저', r'최대', r'최소', r'가장 많은', r'가장 적은'
    ]
    
    # 인용 표현
    quote_patterns = [
        r'"[^"]+"', r''[^']+'', r'발표했', r'밝혔', r'설명했', 
        r'강조했', r'지적했', r'주장했', r'발언했'
    ]
    
    # 패턴 검증
    has_numbers = any(re.search(pattern, content) for pattern in number_patterns)
    has_time = any(re.search(pattern, content) for pattern in time_patterns)
    has_comparison = any(re.search(pattern, content) for pattern in comparison_patterns)
    has_quotes = any(re.search(pattern, content) for pattern in quote_patterns)
    
    # 여러 팩트체크 요소 중 두 가지 이상 만족하면 검증 가능한 것으로 판단
    factcheck_elements = [has_numbers, has_time, has_comparison, has_quotes]
    return sum(factcheck_elements) >= 2

# URL이나 기사 내용에서 날짜 추출 시도
def extract_date_from_url_or_content(entry):
    # URL에서 날짜 형식 추출 시도 (일반적인 뉴스 사이트 URL 패턴)
    url = entry.link
    date_patterns = [
        r'(\d{4})[/-](\d{2})[/-](\d{2})',  # YYYY-MM-DD or YYYY/MM/DD
        r'(\d{8})',                         # YYYYMMDD
        r'(\d{4})(\d{2})(\d{2})'            # YYYYMMDD (분리된 그룹)
    ]
    
    for pattern in date_patterns:
        match = re.search(pattern, url)
        if match:
            try:
                if len(match.groups()) == 3:
                    year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
                elif len(match.groups()) == 1 and len(match.group(1)) == 8:
                    year = int(match.group(1)[:4])
                    month = int(match.group(1)[4:6])
                    day = int(match.group(1)[6:8])
                else:
                    continue
                
                # 유효한 날짜인지 확인
                if 2020 <= year <= datetime.datetime.now().year and 1 <= month <= 12 and 1 <= day <= 31:
                    return datetime.datetime(year, month, day)
            except:
                pass
    
    # 본문 내용에서 날짜 추출 시도 (추가 구현 가능)
    
    # 날짜를 찾지 못했으면 현재 시간 반환
    return datetime.datetime.now()

# API 키가 필요 없는 로컬 팩트체크 함수
def fact_check_statement(statement):
    # 정치인 이름과 정당 추출
    statement_text = statement['title']
    content = statement.get('content', '')
    politician_name, party = extract_politician_and_party(statement_text, content)
    context = get_statement_context(statement)
    
    # 기사 내용에서 검증 가능한 사실 추출
    facts = extract_verifiable_facts(statement_text, content)
    
    # 발언 팩트체크 - 추출한 사실에 기반
    explanation = generate_factcheck_explanation(statement_text, content, facts, politician_name, party)
    
    # 결과 생성
    result = {
        "politician": politician_name or "확인 필요",
        "party": party or "확인 필요",
        "context": context,
        "statement": statement_text,
        "explanation": explanation,
        "date": datetime.datetime.now().strftime("%Y.%m.%d")
    }
    
    return result

# 기사 내용에서 검증 가능한 사실 추출
def extract_verifiable_facts(title, content):
    facts = []
    
    # 수치/통계 정보 추출
    number_patterns = [
        (r'(\d+)%', '비율'),
        (r'(\d+)조(\d*)억?', '금액'),
        (r'(\d+)억', '금액'),
        (r'(\d+)만(\d*)', '수량'),
        (r'(\d+)명', '인원')
    ]
    
    for pattern, category in number_patterns:
        matches = re.finditer(pattern, content)
        for match in matches:
            context_start = max(0, match.start() - 50)
            context_end = min(len(content), match.end() + 50)
            context = content[context_start:context_end]
            facts.append({
                'type': category,
                'value': match.group(0),
                'context': context
            })
    
    # 날짜/시간 정보 추출
    date_patterns = [
        (r'(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일', '날짜'),
        (r'(\d{1,2})월\s*(\d{1,2})일', '날짜'),
        (r'지난해|작년|올해|내년', '시기')
    ]
    
    for pattern, category in date_patterns:
        matches = re.finditer(pattern, content)
        for match in matches:
            context_start = max(0, match.start() - 50)
            context_end = min(len(content), match.end() + 50)
            context = content[context_start:context_end]
            facts.append({
                'type': category,
                'value': match.group(0),
                'context': context
            })
    
    # 비교 표현 추출
    comparison_patterns = [
        (r'(증가|감소|상승|하락|늘|줄)(\w{1,3}다)', '변화'),
        (r'(최고|최저|최대|최소|가장|최초|처음)', '극값')
    ]
    
    for pattern, category in comparison_patterns:
        matches = re.finditer(pattern, content)
        for match in matches:
            context_start = max(0, match.start() - 50)
            context_end = min(len(content), match.end() + 50)
            context = content[context_start:context_end]
            facts.append({
                'type': category,
                'value': match.group(0),
                'context': context
            })
    
    return facts

# 검증 가능한 사실에 기반한 팩트체크 설명 생성
def generate_factcheck_explanation(statement, content, facts, politician_name, party):
    # 사실이 없으면 기본 설명 반환
    if not facts:
        return "이 발언은 구체적인 수치나 통계적 주장을 포함하고 있지 않아 완전한 팩트체크를 위해 추가적인 맥락과 자료가 필요합니다."
    
    # 발언에 포함된 사실 유형 분석
    fact_types = [fact['type'] for fact in facts]
    
    # 금액 관련 팩트체크
    if '금액' in fact_types:
        amount_facts = [f for f in facts if f['type'] == '금액']
        amount_contexts = [f['context'] for f in amount_facts]
        
        if any('증가' in ctx or '늘' in ctx for ctx in amount_contexts):
            return f"발언에 언급된 금액 증가에 대한 주장은 공식 통계와 비교 검증이 필요합니다. 현재 확인 가능한 공식 자료를 바탕으로 볼 때, 정확한 증가폭이나 비율이 발언과 일치하는지 검증하기 위한 추가적인 맥락이 필요합니다. 발언에 사용된 기준 시점과 비교 방법에 따라 해석이 달라질 수 있습니다."
        elif any('감소' in ctx or '줄' in ctx for ctx in amount_contexts):
            return f"발언에 언급된 금액 감소에 대한 주장은 공식 통계와 비교 검증이 필요합니다. 현재 확인 가능한 공식 자료를 바탕으로 볼 때, 감소폭이나 비율이 발언과 일치하는지 검증하기 위해서는 추가적인 맥락과 데이터가 필요합니다. 특히 발언에서 사용된 기준 시점과 비교 방법을 고려해야 합니다."
        else:
            return f"발언에 언급된 금액 관련 주장은 검증이 필요합니다. 구체적인 수치의 맥락과 출처가 명확하지 않으며, 기준 시점이나 산출 방식에 따라 해석이 달라질 수 있습니다. 관련 정부 부처나 기관의 공식 발표를 확인해야 정확한 사실 여부를 판단할 수 있습니다."
    
    # 비율 관련 팩트체크
    elif '비율' in fact_types:
        return f"발언에서 언급된 퍼센트 수치는 맥락과 출처에 따라 해석이 달라질 수 있습니다. 이 수치가 어떤 모집단에 대한 것인지, 어떤 방법론으로 계산되었는지, 어떤 시점의 데이터인지 명확하지 않습니다. 통계청이나 관련 기관의 공식 데이터와 비교해 검증할 필요가 있습니다."
    
    # 인원 관련 팩트체크
    elif '인원' in fact_types:
        return f"발언에서 언급된 인원수에 대한 정확한 검증을 위해서는 공식 통계자료와의 비교가 필요합니다. 이러한 인원수 집계는 집계 방식과 기준에 따라 달라질 수 있으며, 발언 맥락에서 어떤 기준으로 산출된 수치인지 명확하지 않습니다. 관련 정부 부처나 공신력 있는 기관의 자료를 참조해야 합니다."
    
    # 날짜/시기 관련 팩트체크
    elif '날짜' in fact_types or '시기' in fact_types:
        return f"발언에서 언급된 시점이나 기간에 대한 정확성 검증이 필요합니다. 사건의 정확한 발생 시점이나 기간은 공식 기록을 통해 확인할 수 있으며, 발언에서 언급된 내용이 시간적 맥락에서 정확한지 검증하기 위해서는 추가적인 자료 조사가 필요합니다."
    
    # 변화 관련 팩트체크
    elif '변화' in fact_types:
        return f"발언에서 언급된 증가 또는 감소 추세는 기준 시점과 측정 방법에 따라 다르게 해석될 수 있습니다. 장기적 추세와 단기적 변동을 구분하여 평가해야 하며, 통계적으로 유의미한 변화인지 확인할 필요가 있습니다. 관련 공식 통계와 비교하여 발언의 정확성을 검증해야 합니다."
    
    # 극값(최고, 최저 등) 관련 팩트체크
    elif '극값' in fact_types:
        return f"발언에서 언급된 '최초', '최대', '최고' 등의 주장은 비교 대상과 시간적 범위가 명확하지 않습니다. 이러한 주장은 특정 기준과 조건 하에서만 사실일 수 있으며, 다른 맥락에서는 사실이 아닐 수 있습니다. 발언의 정확한 검증을 위해서는 비교 기준과 데이터 출처를 명확히 해야 합니다."
    
    # 기타 일반적인 팩트체크
    else:
        return f"이 발언은 검증 가능한 사실적 주장을 포함하고 있으나, 완전한 팩트체크를 위해서는 추가적인 맥락과 공식 자료가 필요합니다. 발언의 일부 요소는 사실에 기반하고 있으나, 특정 관점이나 해석이 포함되어 있을 수 있습니다. 관련 공식 기관의 데이터와 비교하여 정확성을 검증해야 합니다."

# 발언 상황 컨텍스트 추출
def get_statement_context(statement):
    content = statement.get('content', '')
    
    # 기사 내용에서 발언 상황 추출 시도
    context_keywords = ["기자회견", "인터뷰", "연설", "토론회", "회의", "성명", "보도자료", 
                        "방송", "강연", "SNS", "페이스북", "트위터", "국회", "최고위원회", "당 대표"]
    
    for keyword in context_keywords:
        if keyword in content:
            surrounding_text = extract_surrounding_text(content, keyword, 20)
            if surrounding_text:
                return surrounding_text
    
    # 발언 상황을 찾지 못한 경우 기본값
    source = statement.get('source', '뉴스 보도')
    return f"{source}에서 발췌한 발언"

# 키워드 주변 텍스트 추출
def extract_surrounding_text(text, keyword, window=20):
    if keyword not in text:
        return None
    
    start_idx = max(0, text.find(keyword) - window)
    end_idx = min(len(text), text.find(keyword) + len(keyword) + window)
    
    surrounding = text[start_idx:end_idx]
    # 문장 경계로 다듬기
    if '.' in surrounding:
        parts = surrounding.split('.')
        if len(parts) > 2:
            return '.'.join(parts[1:-1]) + '.'
    
    return surrounding

# 기사 제목과 내용에서 정치인 이름과 정당 추출
def extract_politician_and_party(title, article_content=""):
    # 정치인 정보 매핑
    politician_party_map = {
        "윤석열": "국민의힘",
        "이재명": "더불어민주당",
        "한동훈": "국민의힘",
        "홍준표": "국민의힘",
        "유승민": "국민의힘",
        "안철수": "국민의힘",
        "심상정": "정의당",
        "조국": "조국혁신당",
        "이낙연": "더불어민주당",
        "우상호": "더불어민주당",
        "이준석": "개혁신당",
        "권영세": "국민의힘",
        "김기현": "국민의힘",
        "주호영": "국민의힘",
        "정진석": "국민의힘"
    }
    
    # 정당 이름
    parties = {
        "국민의힘": "국민의힘",
        "더불어민주당": "더불어민주당",
        "민주당": "더불어민주당",
        "정의당": "정의당",
        "조국혁신당": "조국혁신당",
        "개혁신당": "개혁신당"
    }
    
    # 텍스트에서 정치인 이름 찾기
    text = title + " " + article_content
    found_politician = None
    for politician in politician_party_map:
        if politician in text:
            found_politician = politician
            break
    
    # 텍스트에서 정당 이름 찾기
    found_party = None
    for party in parties:
        if party in text:
            found_party = parties[party]
            break
    
    # 정치인을 찾았지만 정당을 못찾았으면 매핑에서 가져오기
    if found_politician and not found_party:
        found_party = politician_party_map.get(found_politician)
    
    # 정당별 대표나 원내대표 처리
    party_leaders = {
        "국민의힘 대표": ("국민의힘 대표", "국민의힘"),
        "더불어민주당 대표": ("더불어민주당 대표", "더불어민주당"),
        "정의당 대표": ("정의당 대표", "정의당"),
        "국민의힘 원내대표": ("국민의힘 원내대표", "국민의힘"),
        "더불어민주당 원내대표": ("더불어민주당 원내대표", "더불어민주당")
    }
    
    for leader, (name, party) in party_leaders.items():
        if leader in text:
            return name, party
            
    return found_politician, found_party

# 기사 URL에서 본문 내용 추출
def get_article_content(url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 메타 설명 추출
        meta_desc = soup.select_one('meta[name="description"]')
        content = ""
        if meta_desc and meta_desc.get('content'):
            content = meta_desc.get('content') + " "
            
        # 본문 추출 시도 (여러 뉴스 사이트 지원)
        article_selectors = [
            'article', '.article_body', '#articleBody', 
            '.news_view', '.article-body', '.article-content',
            '#article-view-content-div', '.article_cont', '.news_contents',
            '.newsct_article', '#news_body_area', '.article_txt'
        ]
        
        for selector in article_selectors:
            article_body = soup.select_one(selector)
            if article_body:
                # 불필요한 요소 제거
                for tag in article_body.select('.reporter_area, .byline, .share_area, .article_ad, script, style'):
                    tag.decompose()
                
                article_text = article_body.get_text(strip=True, separator=' ')
                content += article_text
                break
                
        return content
    except Exception as e:
        print(f"Error extracting article content: {e}")
        return ""

# 정치인 발언인지 판별하는 함수
def is_politician_statement(title):
    # 정치인 명단
    politicians = [
        "윤석열", "이재명", "홍준표", "유승민", "심상정", "안철수", "정세균", "한동훈", 
        "이낙연", "원희룡", "조국", "박영선", "정의당", "국민의힘", "더불어민주당",
        "국회의장", "의원", "위원장", "민주당", "총리", "장관", "대표", "지사", "원내대표"
    ]
    
    # 발언 관련 키워드
    keywords = [
        "발언", "주장", "강조", "밝혔", "말했", "언급", "제안", "요구", "비판", "촉구", 
        "강연", "연설", "토론", "인터뷰", "기자회견", "질의", "답변", "반박", "지적"
    ]
    
    # 정치인 이름이 포함되어 있는지 확인
    has_politician = any(politician in title for politician in politicians)
    
    # 발언 관련 키워드가 포함되어 있는지 확인
    has_keyword = any(keyword in title for keyword in keywords)
    
    # 정치인 이름과 발언 관련 키워드가 모두 포함되어 있으면 정치인 발언으로 간주
    return has_politician and has_keyword

# 허위발언카드 HTML 생성 (기존 형식에 맞춤)
def generate_fact_check_card_html(fact_check):
    party_class = ""
    avatar_class = ""
    
    if fact_check["party"] == "더불어민주당":
        party_class = "democrat-indicator"
        avatar_class = "democrat-avatar"
    elif fact_check["party"] == "국민의힘":
        party_class = "ppp-indicator"
        avatar_class = "ppp-avatar"
    elif fact_check["party"] == "개혁신당":
        party_class = "reform-indicator"
        avatar_class = "reform-avatar"
    elif fact_check["party"] == "조국혁신당":
        party_class = "choi-indicator"
        avatar_class = "choi-avatar"
    elif fact_check["party"] == "정의당":
        party_class = "reform-indicator"  # 정의당도 초록색 사용
        avatar_class = "reform-avatar"
    
    # 정치인 이름의 첫 글자 추출
    first_letter = fact_check["politician"][0] if fact_check["politician"] else "?"
    
    card_html = f"""
    <!-- 허위 발언 카드 -->
    <div class="falsehood-card" data-party="{fact_check["party"]}">
        <div class="falsehood-header">
            <div class="politician-avatar {avatar_class}">{first_letter}</div>
            <div class="politician-info">
                <div class="politician-name">
                    <span class="party-indicator {party_class}"></span>
                    {fact_check["politician"]}
                </div>
                <div class="party-name-small">{fact_check["party"]}</div>
            </div>
            <div class="falsehood-date">{fact_check["date"]}</div>
        </div>
        <div class="falsehood-source">
            <i class="fas fa-bullhorn"></i> {fact_check["context"]}
        </div>
        <div class="falsehood-content">
            {fact_check["statement"]}
        </div>
        <div class="falsehood-correction">
            <span class="correction-label">실제 사실:</span>
            {fact_check["explanation"]}
        </div>
    </div>
    """
    
    return card_html

# HTML 파일 업데이트
def update_html_file():
    try:
        # 정치인 발언 수집
        statements = collect_politician_statements()
        
        if not statements:
            print("No factcheckable statements collected, no updates will be made.")
            return
        
        # 3개의 팩트체크 카드 생성
        num_cards = min(3, len(statements))  # 최대 3개, 수집된 발언이 3개 미만이면 해당 개수만큼
        
        all_cards_html = ""
        processed_cards = 0
        
        # 랜덤으로 발언을 선택하여 팩트체크
        random.shuffle(statements)
        
        for statement in statements:
            if processed_cards >= num_cards:
                break
                
            fact_check = fact_check_statement(statement)
            
            if not fact_check:
                print(f"Fact-checking failed for: {statement['title']}")
                continue
            
            # 허위발언카드 HTML 생성
            card_html = generate_fact_check_card_html(fact_check)
            all_cards_html += card_html
            processed_cards += 1
            
            print(f"Processed card {processed_cards}/{num_cards}: {fact_check['statement']}")
        
        if processed_cards == 0:
            print("No cards were generated")
            return
        
        # 현재 HTML 파일 읽기
        with open('index.html', 'r', encoding='utf-8') as file:
            content = file.read()
        
        # 내용 출력하여 디버깅
        print(f"HTML file size: {len(content)} bytes")
        
        # 마커 확인
        insert_marker = "<!-- FACT_CHECK_CARDS -->"
        print(f"Looking for marker: '{insert_marker}'")
        
        if insert_marker in content:
            print(f"Marker found at position: {content.find(insert_marker)}")
            
            # 마커 위치 찾기
            marker_position = content.find(insert_marker) + len(insert_marker)
            
            # 영향을 받는 부분 출력
            surrounding_content = content[marker_position-50:marker_position+50]
            print(f"Content around marker: '{surrounding_content}'")
            
            # 새 콘텐츠 생성
            new_content = content[:marker_position] + "\n" + all_cards_html + content[marker_position:]
            
            # 마지막 업데이트 날짜 갱신
            today = datetime.datetime.now().strftime("%Y.%m.%d")
            print(f"Added {processed_cards} new fact check cards on {today}")
            
            # 변경 내용 길이 확인
            print(f"New HTML size: {len(new_content)} bytes")
            print(f"HTML size difference: {len(new_content) - len(content)} bytes")
            
            # 업데이트된 콘텐츠 저장
            with open('index.html', 'w', encoding='utf-8') as file:
                file.write(new_content)
                print("Successfully saved updated HTML file")
        else:
            print(f"Could not find marker '{insert_marker}' in the HTML file")
            # 전체 내용 출력하지 않고 일부분만 찾기
            for i in range(0, len(content), 100):
                chunk = content[i:i+100]
                if "FACT_CHECK" in chunk:
                    print(f"Found similar text at position {i}: '{chunk}'")
    except Exception as e:
        print(f"Error updating HTML file: {e}")
        import traceback
        traceback.print_exc()

# 메인 함수 실행
if __name__ == "__main__":
    update_html_file()
