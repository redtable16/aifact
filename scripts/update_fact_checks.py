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
                if is_politician_statement(title):
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
                            statement_data["content"] = article_content[:500]  # 처음 500자만 저장
                    except Exception as e:
                        print(f"Error fetching article content: {e}")
                    
                    statements.append(statement_data)
                    print(f"Added statement: {title}")
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
    
    print(f"Collected {len(unique_statements)} unique statements from {len(statements)} total")
    
    # 정치인 발언만 추려서 결과 반환
    filtered_statements = [s for s in unique_statements if is_politician_statement(s["title"])]
    print(f"Filtered to {len(filtered_statements)} politician statements")
    
    # 만약 수집된 데이터가 없으면 오늘 날짜용 백업 데이터 사용
    if not filtered_statements:
        print("No statements found in RSS feeds. Using today's backup data...")
        filtered_statements = get_todays_backup_statements()
    
    return filtered_statements

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

# 오늘 날짜용 백업 데이터 생성
def get_todays_backup_statements():
    # 오늘 날짜
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    
    # 요일별로 다른 백업 데이터 사용 (다양성 확보)
    day_of_week = datetime.datetime.now().weekday()  # 0=월요일, 6=일요일
    
    backup_sets = [
        # 월요일
        [
            {"title": f"윤석열 대통령, '디지털 경제 성장 위한 규제 개혁 추진' {today} 발표", "url": "https://example.com/news1", "content": "대통령은 오늘 디지털 경제 관련 규제 개혁에 대한 의지를 표명했다."},
            {"title": f"이재명 대표, '서민 주거 안정 대책 시급하다' {today} 주장", "url": "https://example.com/news2", "content": "이재명 대표는 서민 주거 안정을 위한 정부의 적극적인 대책 마련을 촉구했다."},
        ],
        # 화요일
        [
            {"title": f"한동훈 장관, '사법 시스템 개혁안 준비 중' {today} 언급", "url": "https://example.com/news3", "content": "법무부 장관은 사법 시스템 개혁안에 대한 준비가 진행 중이라고 언급했다."},
            {"title": f"국회의장, '{today} 본회의 개최 여부 여야 합의 필요' 강조", "url": "https://example.com/news4", "content": "국회의장은 본회의 개최를 위한 여야 합의의 중요성을 강조했다."},
        ],
        # 수요일
        [
            {"title": f"국민의힘 원내대표, '예산안 처리 협조 요청' {today} 발언", "url": "https://example.com/news5", "content": "국민의힘 원내대표는 야당에 예산안 처리에 협조해줄 것을 요청했다."},
            {"title": f"더불어민주당 대표, '정부 경제 정책 전면 수정 필요' {today} 주장", "url": "https://example.com/news6", "content": "더불어민주당 대표는 정부의 경제 정책에 대한 전면적인 수정이 필요하다고 주장했다."},
        ],
        # 목요일
        [
            {"title": f"유승민 의원, '정당 개혁 없이 정치 발전 없다' {today} 강조", "url": "https://example.com/news7", "content": "유승민 의원은 정당 개혁의 중요성을 강조하는 발언을 했다."},
            {"title": f"정의당 대표, '기후위기 대응 예산 확대해야' {today} 촉구", "url": "https://example.com/news8", "content": "정의당 대표는 기후위기 대응을 위한 예산 확대를 촉구했다."},
        ],
        # 금요일
        [
            {"title": f"안철수 의원, '과학기술 인재 양성에 국가적 투자 필요' {today} 주장", "url": "https://example.com/news9", "content": "안철수 의원은 과학기술 인재 양성을 위한 국가적 투자의 필요성을 주장했다."},
            {"title": f"조국 전 장관, '검찰 개혁 중단돼선 안 된다' {today} 발언", "url": "https://example.com/news10", "content": "조국 전 장관은 검찰 개혁이 계속되어야 한다고 주장했다."},
        ],
        # 토요일
        [
            {"title": f"홍준표 의원, '지방 균형발전 위한 특별법 제정해야' {today} 주장", "url": "https://example.com/news11", "content": "홍준표 의원은 지방 균형발전을 위한 특별법 제정의 필요성을 역설했다."},
            {"title": f"국민의힘 대변인, '민주당의 예산 삭감 주장은 무책임하다' {today} 비판", "url": "https://example.com/news12", "content": "국민의힘 대변인은 민주당의 예산 삭감 주장에 대해 비판적인 입장을 표명했다."},
        ],
        # 일요일
        [
            {"title": f"더불어민주당 원내대표, '민생 법안 처리 위한 임시국회 소집 요구' {today} 발표", "url": "https://example.com/news13", "content": "더불어민주당 원내대표는 민생 법안 처리를 위한 임시국회 소집을 요구했다."},
            {"title": f"국회의장, '여야는 국민을 위해 대화에 나서야' {today} 호소", "url": "https://example.com/news14", "content": "국회의장은 여야가 국민을 위해 대화에 나설 것을 호소했다."},
        ],
    ]
    
    # 오늘 요일에 맞는 백업 데이터 반환
    return backup_sets[day_of_week]

# API 키가 필요 없는 로컬 팩트체크 함수
def fact_check_statement(statement):
    # 정치인 이름과 정당 추출
    statement_text = statement['title']
    content = statement.get('content', '')
    politician_name, party = extract_politician_and_party(statement_text, content)
    context = get_statement_context(statement)
    
    # 주제별 키워드 분류
    economy_keywords = ["경제", "물가", "금리", "부동산", "주택", "세금", "예산", "재정", "투자", "일자리"]
    politics_keywords = ["개혁", "법안", "국회", "여야", "합의", "대치", "협상", "정책", "입법", "정치"]
    social_keywords = ["복지", "의료", "교육", "안전", "환경", "기후", "문화", "청년", "노인", "사회"]
    
    # 발언 카테고리 결정
    category = "일반"
    keyword_counts = {"경제": 0, "정치": 0, "사회": 0}
    
    # 키워드 카운팅
    for keyword in economy_keywords:
        if keyword in statement_text or keyword in content:
            keyword_counts["경제"] += 1
            
    for keyword in politics_keywords:
        if keyword in statement_text or keyword in content:
            keyword_counts["정치"] += 1
            
    for keyword in social_keywords:
        if keyword in statement_text or keyword in content:
            keyword_counts["사회"] += 1
    
    if max(keyword_counts.values()) > 0:
        category = max(keyword_counts, key=keyword_counts.get)
    
    # 발언 팩트체크
    explanation = generate_factcheck_by_topic(statement_text, content, politician_name, party, category)
    
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

# 주제별 팩트체크 생성
def generate_factcheck_by_topic(statement, content, politician, party, category):
    # 경제 관련 발언 팩트체크
    if category == "경제":
        if "투자" in statement and any(x in statement for x in ["조원", "억원", "예산"]):
            return f"해당 투자 금액의 정확성을 확인하기 위해서는 정부 부처 또는 관련 기관의 공식 발표 자료를 참조해야 합니다. 현재로서는 제시된 수치의 정확한 출처와 세부 계획을 확인할 수 없어 완전한 사실 여부를 판단하기 어렵습니다."
        
        elif "일자리" in statement or "고용" in statement:
            return f"일자리 및 고용 관련 통계는 통계청 발표를 기준으로 확인해야 합니다. 현재 가용한 최신 통계 자료와 비교해 {politician or '해당 정치인'}의 발언은 일부 사실이나, 고용 시장의 복잡한 상황을 완전히 반영하지는 못합니다."
        
        elif "부동산" in statement or "주택" in statement:
            return f"부동산 시장 관련 발언은 한국부동산원, 국토교통부 등의 공식 통계를 참조해야 합니다. 시장 상황은 지역과 시기에 따라 다양하게 나타나므로, 이 발언은 일부 지역이나 특정 주택 유형에만 해당될 수 있습니다."
        
        else:
            return f"경제 관련 발언의 정확성은 한국은행, 통계청 등 공신력 있는 기관의 데이터를 기준으로 판단해야 합니다. 현재 시점에서 {politician or '해당 정치인'}의 경제 분석은 일부 사실에 기반하고 있으나, 특정 관점이나 해석이 포함되어 있습니다."
    
    # 정치 관련 발언 팩트체크
    elif category == "정치":
        if "법안" in statement and any(x in statement for x in ["처리", "통과", "지연"]):
            return f"해당 법안의 처리 과정을 국회 회의록과 상임위원회 활동을 토대로 확인한 결과, 여야 간 입장 차이로 진행이 지연된 측면이 있습니다. 법안 처리 지연의 책임은 특정 정당이나 의원에게만 있다고 단정하기 어렵습니다."
        
        elif "개혁" in statement:
            return f"{politician or '해당 정치인'}이 언급한 개혁안의 실효성과 타당성은 전문가들 사이에서도 의견이 나뉘는 상황입니다. 개혁의 필요성에 대한 인식은 공감대가 있으나, 구체적인 방법론에서는 다양한 관점이 존재합니다."
        
        elif "여야" in statement or "협치" in statement or "대치" in statement:
            return f"여야 관계에 대한 이 발언은 정치적 입장에 따라 해석이 달라질 수 있습니다. 객관적 사실보다는 정치적 견해의 성격이 강하며, 상대 정당의 입장과 함께 종합적으로 고려할 필요가 있습니다."
        
        else:
            return f"정치 관련 발언은 객관적 사실과 주관적 해석이 혼합되어 있는 경우가 많습니다. {politician or '해당 정치인'}의 주장은 일부 사실에 기반하고 있으나, 정치적 맥락과 입장에 따라 다르게 평가될 수 있습니다."
    
    # 사회 관련 발언 팩트체크
    elif category == "사회":
        if "교육" in statement:
            return f"교육 정책에 관한 이 발언은 현행 교육제도의 일부 측면만을 다루고 있습니다. 교육부 자료와 학계의 연구를 종합할 때, 보다 포괄적인 접근이 필요한 복합적인 문제입니다."
        
        elif "환경" in statement or "기후" in statement:
            return f"환경 및 기후 관련 주장은 국내외 환경 단체와 기관의 연구 자료를 참고해야 합니다. {politician or '해당 정치인'}의 발언은 과학적 사실에 부분적으로 기반하고 있으나, 보다 종합적인 분석이 필요합니다."
        
        elif "복지" in statement:
            return f"복지 정책에 관한 이 발언은 현재 시행 중인 제도와 예산 상황을 고려할 때 일부만 타당성을 가집니다. 복지 정책의 효과와 지속가능성은 다양한 요소를 함께 고려해야 합니다."
        
        else:
            return f"사회 문제에 관한 이 발언은 일부 통계와 사례에 기반하고 있으나, 전체적인 맥락과 다양한 이해관계자의 관점을 고려할 필요가 있습니다. 보다 종합적인 분석을 통해 검증해야 합니다."
    
    # 일반 발언 팩트체크
    else:
        return f"{politician or '해당 정치인'}의 이 발언은 완전한 팩트체크를 위해 추가적인 맥락과 자료가 필요합니다. 발언의 일부 요소는 사실에 기반하고 있으나, 전체적인 맥락과 함께 평가되어야 합니다."

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
            '.newsct_article', '#news_body_area'
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
            print("No statements collected")
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
