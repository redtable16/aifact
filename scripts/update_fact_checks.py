import os
import json
import random
import datetime
import requests
import feedparser
import time
import re
from bs4 import BeautifulSoup
import openai

# 기존 발언 카드에서 이미 처리된 발언을 추출하는 함수
def extract_existing_statements(html_content):
    existing_statements = []
    existing_politicians_with_statements = []
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 모든 발언 카드 찾기
    cards = soup.select('.falsehood-card')
    
    for card in cards:
        # 발언 내용 추출
        statement_content = card.select_one('.falsehood-content')
        politician_name_elem = card.select_one('.politician-name')
        
        if statement_content and politician_name_elem:
            statement_text = statement_content.get_text(strip=True)
            politician_name = politician_name_elem.get_text(strip=True)
            
            # 발언 내용만 저장
            existing_statements.append(statement_text)
            
            # 정치인+발언 조합도 저장 (더 엄격한 중복 체크)
            politician_statement = f"{politician_name}:{statement_text}"
            existing_politicians_with_statements.append(politician_statement)
            
            # 유사 발언 감지를 위한 키워드 추출 (더 유연한 중복 체크)
            words = re.findall(r'\w+', statement_text)
            for i in range(len(words) - 2):
                if i + 2 < len(words):
                    keyword_triplet = f"{words[i]} {words[i+1]} {words[i+2]}"
                    existing_statements.append(keyword_triplet)
    
    return existing_statements, existing_politicians_with_statements

# 팩트체크 가능한 발언인지 판단하는 함수
def is_factcheckable_statement(title, content=""):
    # 즉시 제외할 패턴 - 확실하게 팩트체크 불가능한 것들
    immediate_exclude_patterns = [
        r'.*하겠다.*', r'.*할 것.*', r'.*추진.*', r'.*계획.*', r'.*공약.*', 
        r'.*육성.*', r'.*설립.*', r'.*제안.*'
    ]
    
    full_text = title + " " + content
    
    # 확실히 팩트체크 불가능한 패턴이 있다면 즉시 제외
    for pattern in immediate_exclude_patterns:
        if re.search(pattern, full_text):
            print(f"Statement immediately excluded due to pattern: {pattern}")
            return False
    
    # 확실한 주장 패턴 - 팩트체크 가능성 높음
    strong_factcheckable_patterns = [
        # 숫자 + 단위 패턴
        r'\d+\.?\d*\s*%', r'\d+\.?\d*\s*배', r'\d+\.?\d*\s*조원', r'\d+\.?\d*\s*억원', 
        r'\d+\.?\d*\s*만원', r'\d+\s*명', r'\d+\s*인', r'\d+\s*건',
        
        # 비교 표현
        r'최대', r'최소', r'사상 최고', r'사상 최저', r'역대 최고',
        
        # 객관적 주장 표현
        r'사실[은는이가]', r'실제로[는은]', r'통계[에에서는은상]', r'데이터[에에서는은상]'
    ]
    
    # 확실한 팩트체크 가능 패턴이 있는지 확인
    for pattern in strong_factcheckable_patterns:
        if re.search(pattern, full_text):
            print(f"Statement has strong factcheckable pattern: {pattern}")
            return True
    
    # 명확한 주장 키워드
    assertion_keywords = ["주장", "지적", "비판", "발표", "밝혔", "확인", "증명", "입증"]
    has_assertion = any(keyword in full_text for keyword in assertion_keywords)
    
    # 수치 관련 키워드
    number_keywords = ["증가", "감소", "상승", "하락", "늘었", "줄었", "확대", "축소"]
    has_number_keyword = any(keyword in full_text for keyword in number_keywords)
    
    # 둘 다 있어야 팩트체크 가능성 높음
    if has_assertion and has_number_keyword:
        print("Statement has both assertion and number keywords")
        return True
    
    # 그 외에는 기본적으로 팩트체크 대상이 아님
    print("Statement doesn't meet factcheck criteria")
    return False

# RSS 피드에서 정치인 발언 수집 (24시간 이내 기사만)
def collect_politician_statements():
    print("Starting to collect politician statements from RSS feeds...")
    
    # 주요 한국 뉴스 사이트의 정치 RSS 피드 - 확장된 목록
    rss_feeds = [
        "https://www.hani.co.kr/rss/politics/",                # 한겨레
        "https://rss.donga.com/politics.xml",                  # 동아일보
        "https://www.khan.co.kr/rss/rssdata/politic.xml",      # 경향신문
        "https://rss.joins.com/joins_politics_list.xml",       # 중앙일보
        "https://www.ytn.co.kr/_ln/0101_rss.xml",              # YTN 정치
        "https://feed.mk.co.kr/rss/politics/news.xml",         # 매일경제 정치
        "https://www.mt.co.kr/mt_news_politics_rss.xml",       # 머니투데이 정치
        "https://rss.nocutnews.co.kr/NocutNews_Politics.xml",  # 노컷뉴스 정치
        "https://rss.hankyung.com/feed/politics.xml",          # 한국경제
        "https://news.sbs.co.kr/news/SectionRssFeed.do?sectionId=01&plink=RSSREADER", # SBS 정치
        "https://rss.kmib.co.kr/data/kmibPolRss.xml",          # 국민일보 정치
        "https://www.huffingtonpost.kr/feeds/index.xml",        # 허핑턴포스트
        "https://www.chosun.com/arc/outboundfeeds/rss/category/politics/?outputType=xml" # 조선일보 정치
    ]
    
    # 단계별 필터링을 위한 수집 컨테이너
    all_statements = []         # 모든 정치 관련 기사
    politician_statements = []  # 정치인 발언 기사
    factcheckable_statements = [] # 팩트체크 가능한 발언
    
    # 24시간 이내 기사만 필터링하기 위한 기준 시간
    cutoff_time = datetime.datetime.now() - datetime.timedelta(hours=24)
    print(f"Collecting articles published after: {cutoff_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    for feed_url in rss_feeds:
        try:
            print(f"\nFetching RSS feed: {feed_url}")
            feed = feedparser.parse(feed_url)
            print(f"Found {len(feed.entries)} entries in feed")
            
            for entry in feed.entries[:50]:  # 각 피드에서 최대 50개 항목 확인 (증가)
                # 기본 정보 추출
                statement_data = {
                    "title": entry.title,
                    "url": entry.link,
                    "source": feed.feed.title if hasattr(feed, 'feed') and hasattr(feed.feed, 'title') else "뉴스 소스"
                }
                
                # 기사 본문에서 추가 컨텍스트 가져오기
                try:
                    article_content = get_article_content(entry.link)
                    if article_content:
                        statement_data["content"] = article_content[:800]  # 처음 800자만 저장
                    else:
                        print(f"  No content extracted for: {entry.title}")
                        continue  # 내용이 없으면 건너뛰기
                except Exception as e:
                    print(f"  Error fetching article content: {e}")
                    continue  # 내용 추출 실패 시 건너뛰기
                
                # 1단계: 모든 정치 관련 기사 수집
                all_statements.append(statement_data)
                
                # 2단계: 정치인 발언 필터링
                if is_politician_statement(entry.title, article_content):
                    politician_statements.append(statement_data)
                    
                    # 3단계: 팩트체크 가능한 발언인지 확인
                    if is_factcheckable_statement(entry.title, article_content):
                        factcheckable_statements.append(statement_data)
                        print(f"  Found factcheckable statement: {entry.title}")
                    else:
                        print(f"  Found politician statement but not factcheckable: {entry.title}")
        
        except Exception as e:
            print(f"Error processing feed {feed_url}: {e}")
        
        # 요청 간 간격 두기
        time.sleep(1)
    
    # 중복 제거
    def deduplicate(statements):
        unique_statements = []
        urls = set()
        for statement in statements:
            if statement["url"] not in urls:
                urls.add(statement["url"])
                unique_statements.append(statement)
        return unique_statements
    
    # 중복 제거 적용
    all_statements = deduplicate(all_statements)
    politician_statements = deduplicate(politician_statements)
    factcheckable_statements = deduplicate(factcheckable_statements)
    
    # 수집된 발언 중 숫자 기반 주장을 우선순위로 정렬
    def prioritize_numeric_statements(statements):
        numeric_statements = []
        other_statements = []
        
        # 숫자 패턴 정규식
        number_patterns = [
            r'\d+\.?\d*\s*%', r'\d+\.?\d*\s*배', r'\d+\.?\d*\s*조', r'\d+\.?\d*\s*억', 
            r'\d+\.?\d*\s*만', r'\d+\.?\d*\s*천', r'수\s*[십백천만억조]+', r'\d+\s*년'
        ]
        
        # 숫자 관련 키워드
        number_keywords = [
            "증가", "감소", "상승", "하락", "배", "퍼센트", "%", "억", "조", "만", 
            "천", "수치", "통계", "지수"
        ]
        
        for statement in statements:
            title = statement.get('title', '')
            content = statement.get('content', '')
            full_text = title + " " + content
            
            # 숫자 패턴이나 키워드가 있으면 우선순위 높게
            if any(re.search(pattern, full_text) for pattern in number_patterns) or \
               any(keyword in full_text for keyword in number_keywords):
                numeric_statements.append(statement)
            else:
                other_statements.append(statement)
        
        # 숫자 기반 주장을 앞에 배치
        return numeric_statements + other_statements
    
    # 숫자 기반 주장을 우선하도록 정렬
    factcheckable_statements = prioritize_numeric_statements(factcheckable_statements)
    politician_statements = prioritize_numeric_statements(politician_statements)
    all_statements = prioritize_numeric_statements(all_statements)
    
    # 단계별 수집 결과 출력
    print("\nCollection Summary:")
    print(f"- All political articles: {len(all_statements)}")
    print(f"- Politician statements: {len(politician_statements)}")
    print(f"- Factcheckable statements: {len(factcheckable_statements)}")
    
    # 단계별 필터링 적용 (가장 엄격한 것부터 시작)
    if len(factcheckable_statements) >= 2:
        print("Using factcheckable statements.")
        return factcheckable_statements
    elif len(politician_statements) >= 2:
        print("Not enough factcheckable statements. Using all politician statements.")
        return politician_statements
    elif len(all_statements) >= 2:
        print("Not enough politician statements. Using all political articles.")
        return all_statements
    else:
        print("No suitable articles found in the last 24 hours.")
        return []

# 정치인 발언인지 확인 (본문 내용도 함께 검사)
def is_politician_statement(title, content=""):
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
    
    # 제목과 내용 모두 검색
    full_text = title + " " + content
    
    # 정치인 이름이 포함되어 있는지 확인
    has_politician = any(politician in full_text for politician in politicians)
    
    # 발언 관련 키워드가 포함되어 있는지 확인
    has_keyword = any(keyword in full_text for keyword in keywords)
    
    # 정치인 이름과 발언 관련 키워드가 모두 포함되어 있으면 정치인 발언으로 간주
    return has_politician and has_keyword

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
        "정진석": "국민의힘",
        "나경원": "국민의힘"
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
            
    return found_politician, found_party

# 발언 상황 컨텍스트 추출
def get_statement_context(statement):
    content = statement.get('content', '')
    source = statement.get('source', '뉴스 보도')
    
    # SNS 관련 출처 통일
    if any(term in content.lower() for term in ["sns", "페이스북", "트위터", "인스타그램", "공유하기", "퍼가기"]):
        return "SNS 발언"
    
    # 기사 내용에서 발언 상황 추출 시도
    context_keywords = ["기자회견", "인터뷰", "연설", "토론회", "회의", "성명", "보도자료", 
                        "방송", "강연", "국회", "최고위원회", "당 대표"]
    
    for keyword in context_keywords:
        if keyword in content:
            start_idx = max(0, content.find(keyword) - 20)
            end_idx = min(len(content), content.find(keyword) + len(keyword) + 20)
            surrounding = content[start_idx:end_idx]
            if len(surrounding) > 30:
                return keyword
            return surrounding
    
    # 발언 상황을 찾지 못한 경우 기본값
    return "언론 보도"

# 정치인 이름 처리 개선
def improve_politician_name(politician_name, party):
    # 발언자가 불명확할 경우 정당 정보 활용
    if not politician_name or politician_name == "확인 필요":
        if party and party != "확인 필요":
            # 정당명 + 관계자 형태로 반환
            if "민주당" in party:
                return "더불어민주당 관계자"
            elif "국민의힘" in party:
                return "국민의힘 관계자"
            elif "정의당" in party:
                return "정의당 관계자"
            elif "개혁신당" in party:
                return "개혁신당 관계자"
            elif "조국혁신당" in party:
                return "조국혁신당 관계자"
            else:
                return f"{party} 관계자"
        else:
            return "정치권 관계자"
    return politician_name

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
            '.newsct_article', '#news_body_area', '.article_txt', '#article'
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

# GPT-4를 사용하여 발언 팩트체크 (개선된 프롬프트)
def fact_check_statement(statement):
    # 정치인 이름과 정당 추출
    statement_text = statement['title']
    content = statement.get('content', '')
    politician_name, party = extract_politician_and_party(statement_text, content)
    context = get_statement_context(statement)
    
    # 발언자 이름 개선
    improved_name = improve_politician_name(politician_name, party)
    
    # 개선된 프롬프트
    prompt = """다음 정치인 주장의 팩트체크를 엄격하게 수행해주세요.

중요 지침:
1. 검증 가능한 객관적 사실 주장만 팩트체크 대상입니다. 검증이 어려운 발언은 반드시 제외하세요.
   - 미래 계획, 공약, 의견, 가치 판단은 절대 팩트체크 대상이 아닙니다.
   - 구체적인 수치나 통계, 날짜, 사건에 대한 명확한 주장만 검증하세요.

2. 구체적인 검증 기준:
   - 수치 주장 (예: "실업률 20% 증가", "2배 상승" 등): 정확한 통계로 검증
   - 인과관계 주장 (예: "A 정책으로 B 결과 초래"): 실제 인과관계 검증
   - 과거 사건 주장 (예: "과거에 A가 B를 했다"): 사실 여부 검증

3. 명확한 검증 결과를 제시할 수 없는 경우에는 반드시 is_factcheckable을 false로 설정하세요.
   - 주장에 대한 확인 가능한 통계나 자료가 없다면 검증 불가
   - 명확한 사실 확인이 어려운 정치적 해석이나 주장은 검증 불가
   - '확인 불가' 결과는 사용자에게 가치가 없으므로, 확실히 검증할 수 없다면 팩트체크 자체를 하지 마세요.

4. 팩트체크 결과는 다음 중 하나여야 합니다:
   - "사실": 주장이 증거와 완전히 일치
   - "대체로 사실": 주장이 기본적으로 사실이나 약간의 과장이나 누락이 있음
   - "일부 사실": 주장의 일부만 사실
   - "사실 아님": 주장이 명백히 거짓

주장: "{statement_text}"
출처: {statement.get('url', '확인 필요')}

추가 컨텍스트:
{content[:500] if content else '추가 정보 없음'}

발언자: {improved_name if improved_name else '확인 필요'}
정당: {party if party else '확인 필요'}

다음 형식의 JSON으로 응답해주세요:
{{
    "politician": "발언자 이름",
    "party": "소속 정당",
    "context": "발언 상황",
    "statement": "원본 주장",
    "is_factcheckable": true/false,  # 팩트체크 대상인지 여부
    "verification_result": "사실|대체로 사실|일부 사실|사실 아님",  # 팩트체크 결과
    "explanation": "검증 결과에 대한 상세 설명"
}}

중요: 검증이 어려운 주장은 반드시 is_factcheckable을 false로 설정하세요. 확인 불가 판정이 나올 것 같으면 애초에 팩트체크 대상이 아니라고 판단하는 것이 좋습니다.
"""
    
    try:
        # API 키 확인용 로그 출력
        api_key = os.getenv("OPENAI_API_KEY")
        print(f"API Key available: {api_key is not None and len(api_key) > 0}")
        
        # OpenAI API 호출
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model="gpt-4",  # GPT-4 사용
            messages=[
                {"role": "system", "content": "당신은 정치인 발언의 사실 관계를 객관적으로 검증하는 팩트체크 전문가입니다. 항상 한국어로 응답하세요."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2  # 더 일관되고 정확한 응답을 위해
        )
        
        # API 응답 디버깅
        print(f"API response content: {response.choices[0].message.content if hasattr(response, 'choices') and response.choices else 'No content'}")
        
        # 응답 파싱 및 예외 처리
        try:
            # 정규식을 사용하여 JSON 블록 추출
            json_match = re.search(r'(\{.*\})', response.choices[0].message.content, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(1))
            else:
                # JSON 형식이 아니면 직접 파싱 시도
                result = json.loads(response.choices[0].message.content)
            
            # 필요한 키 확인 및 보완
            required_keys = ["politician", "party", "context", "statement", "explanation", "is_factcheckable", "verification_result"]
            for key in required_keys:
                if key not in result:
                    if key == "politician":
                        result[key] = improved_name
                    elif key == "party":
                        result[key] = party or "확인 필요"
                    elif key == "context":
                        result[key] = context
                    elif key == "statement":
                        result[key] = statement_text
                    elif key == "explanation":
                        result[key] = "이 주장의 사실 관계를 검증하기 위해서는 추가적인 자료와 맥락이 필요합니다."
                    elif key == "is_factcheckable":
                        result[key] = True  # 기본값은 팩트체크 가능으로 설정
                    elif key == "verification_result":
                        result[key] = "사실 아님"  # 기본값은 사실 아님
            
            # 정당 정보가 비어있거나 확인 필요인 경우
            if not result.get("party") or result["party"] == "확인 필요":
                result["party"] = party or "무소속"
                
            # 현재 날짜 추가
            result["date"] = datetime.datetime.now().strftime("%Y.%m.%d")
            
            # 팩트체크 가능 여부가 명시적으로 false인 경우
            if "is_factcheckable" in result and result["is_factcheckable"] == False:
                print(f"GPT determined statement is not factcheckable: {statement_text}")
                return None
                
            # 검증 결과가 확인 불가인 경우 - 추가
            if "verification_result" in result and result["verification_result"] == "확인 불가":
                print(f"GPT returned 'unverifiable' result: {statement_text}")
                return None
                
            return result
        except json.JSONDecodeError as e:
            print(f"Failed to parse JSON: {e}")
            print(f"Raw response: {response.choices[0].message.content}")
            
            # JSON 파싱 실패 시 기본 응답 생성
            return None
    except Exception as e:
        print(f"Error fact-checking statement: {e}")
        # 예외 발생 시 기본 응답 생성
        return None

# 팩트체크 카드 HTML 생성 (개선된 형식)
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
    else:
        party_class = "ppp-indicator"  # 기본값
        avatar_class = "ppp-avatar"
    
    # 정치인 이름의 첫 글자 추출
    first_letter = fact_check["politician"][0] if fact_check["politician"] else "?"
    
    # 검증 결과에 따른 스타일 적용
    verification_result = fact_check.get("verification_result", "사실 아님")
    result_class = ""
    
    if verification_result == "사실":
        result_class = "result-true"
    elif verification_result == "대체로 사실":
        result_class = "result-mostly-true"
    elif verification_result == "일부 사실":
        result_class = "result-partially-true"
    elif verification_result == "사실 아님":
        result_class = "result-false"
    else:
        result_class = "result-unverifiable"
    
    # HTML 카드 생성
    card_html = "<!-- 팩트체크 카드 -->\n"
    card_html += f'<div class="falsehood-card" data-party="{fact_check["party"]}">\n'
    card_html += '<div class="falsehood-header">\n'
    card_html += f'<div class="politician-avatar {avatar_class}">{first_letter}</div>\n'
    card_html += '<div class="politician-info">\n'
    card_html += '<div class="politician-name">\n'
    card_html += f'<span class="party-indicator {party_class}"></span>\n'
    card_html += f'{fact_check["politician"]}\n'
    card_html += '</div>\n'
    card_html += f'<div class="party-name-small">{fact_check["party"]}</div>\n'
    card_html += '</div>\n'
    card_html += f'<div class="falsehood-date">{fact_check["date"]}</div>\n'
    card_html += '</div>\n'
    
    # 발언 출처 표시
    card_html += '<div class="falsehood-source">\n'
    card_html += f'<i class="fas fa-bullhorn"></i> {fact_check["context"]}\n'
    card_html += '</div>\n'
    
    # 검증 결과 표시
    card_html += f'<div class="verification-result {result_class}">\n'
    card_html += f'<span class="result-label">검증 결과:</span> {verification_result}\n'
    card_html += '</div>\n'
    
    # 발언 내용 표시
    card_html += '<div class="falsehood-content">\n'
    card_html += f'{fact_check["statement"]}\n'
    card_html += '</div>\n'
    
    # 검증 설명 표시
    card_html += '<div class="falsehood-correction">\n'
    card_html += '<span class="correction-label">검증 설명:</span>\n'
    card_html += f'{fact_check["explanation"]}\n'
    card_html += '</div>\n'
    card_html += '</div>\n'
    
    return card_html

# HTML 파일 업데이트 - 중복 방지 및 팩트체크 품질 개선 로직 추가
def update_html_file():
    try:
        # 정치인 발언 수집
        statements = collect_politician_statements()
        
        if not statements:
            print("No statements collected, no updates will be made.")
            return
        
        # 현재 HTML 파일 읽기
        with open('index.html', 'r', encoding='utf-8') as file:
            content = file.read()
        
        # 기존 발언 추출
        existing_statements, existing_politicians_with_statements = extract_existing_statements(content)
        print(f"Found {len(existing_statements)} existing statements")
        
        # CSS 스타일 추가 (검증 결과 표시용)
        if '.verification-result' not in content:
            style_addition = """
        .verification-result {
            padding: 0.5rem 1rem;
            font-weight: bold;
            text-align: center;
            border-bottom: 1px solid #f0f0f0;
        }
        
        .result-true {
            background-color: #D4EDDA;
            color: #155724;
        }
        
        .result-mostly-true {
            background-color: #D1ECF1;
            color: #0C5460;
        }
        
        .result-partially-true {
            background-color: #FFF3CD;
            color: #856404;
        }
        
        .result-false {
            background-color: #F8D7DA;
            color: #721C24;
        }
        
        .result-unverifiable {
            background-color: #E2E3E5;
            color: #383D41;
        }
        """
            # </style> 태그를 찾아서 그 앞에 스타일 추가
            style_end_pos = content.find('</style>')
            if style_end_pos > 0:
                content = content[:style_end_pos] + style_addition + content[style_end_pos:]
                print("Added verification result styles to CSS")
                
                # 업데이트된 HTML 내용으로 파일 쓰기
                with open('index.html', 'w', encoding='utf-8') as file:
                    file.write(content)
                
                # 다시 읽기
                with open('index.html', 'r', encoding='utf-8') as file:
                    content = file.read()
            else:
                print("Could not find </style> tag to add new styles")
        
        # 처리된 카드 수와 HTML 저장
        all_cards_html = ""
        processed_cards = 0
        
        # 중복 방지를 위한 임시 저장소
        processed_statements = set()
        
        # 스크립트가 최소 3개 또는 가능한 최대 카드를 생성하도록 보장
        target_cards = 3  # 목표 카드 수
        max_attempts = 20  # 최대 시도 횟수 (충분한 카드를 얻기 위해)
        
        # 랜덤으로 발언을 선택하여 팩트체크
        statements_copy = statements.copy()  # 원본 리스트 보존
        random.shuffle(statements_copy)
        attempts = 0
        
        for statement in statements_copy:
            if processed_cards >= target_cards or attempts >= max_attempts:
                break  # 목표 카드 수 달성 또는 최대 시도 횟수 도달 시 종료
            
            attempts += 1
            
            # 중복 체크 - 이미 HTML에 있는 발언인지 확인
            if statement['title'] in existing_statements:
                print(f"Skipping duplicate statement: {statement['title']}")
                continue
                
            # 추가 중복 체크 - 이번 실행에서 처리한 발언인지 확인
            if statement['title'] in processed_statements:
                print(f"Skipping statement already processed in this run: {statement['title']}")
                continue
            
            # 팩트체크 대상인지 한번 더 확인
            if not is_factcheckable_statement(statement['title'], statement.get('content', '')):
                print(f"Skipping non-factcheckable statement: {statement['title']}")
                continue
                
            # 발언 팩트체크
            fact_check = fact_check_statement(statement)
            
            # GPT가 팩트체크 불가능하다고 판단했거나 오류가 발생한 경우
            if not fact_check:
                print(f"Skipping statement due to fact check failure or unverifiable result: {statement['title']}")
                continue
                
            # 팩트체크 카드 HTML 생성
            card_html = generate_fact_check_card_html(fact_check)
            all_cards_html += card_html
            
            # 이번에 처리한 발언 기록
            processed_statements.add(statement['title'])
            processed_cards += 1
            
            print(f"Processed card {processed_cards}/{target_cards}: {fact_check['statement']}")
        
        # 목표 카드 수에 도달하지 못한 경우 경고 출력
        if processed_cards < target_cards:
            print(f"Warning: Could only generate {processed_cards} cards out of {target_cards} target cards")
            if processed_cards == 0:
                print("No cards were generated. No updates will be made.")
                return
        
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
            
            # HTML 파일에서 제목 및 레이블 텍스트 업데이트
            new_content = new_content.replace("허위 발언 트래커", "정치인 발언 검증 서비스")
            new_content = new_content.replace("<!-- 허위 발언 카드", "<!-- 팩트체크 카드")
            new_content = new_content.replace('<span class="correction-label">실제 사실:</span>', '<span class="correction-label">검증 설명:</span>')
            
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
