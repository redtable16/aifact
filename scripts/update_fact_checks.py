import os
import json
import random
import datetime
import requests
import feedparser
import time
import re
import concurrent.futures
from bs4 import BeautifulSoup
import openai

# 환경 변수에서 API 키 설정
NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# 임시 파일 경로
TEMP_FILE = 'temp_results.json'

# 실행 시간 제한 설정 (15분)
MAX_RUNTIME_SECONDS = 15 * 60
start_time = time.time()

# OpenAI 클라이언트 설정
openai.api_key = OPENAI_API_KEY
client = openai.OpenAI(api_key=OPENAI_API_KEY)

# 블랙리스트 키워드 - 정치 관련 뉴스가 아닌 내용 필터링
BLACKLIST_KEYWORDS = [
    "오늘 날씨", "코로나19", "확진자", "날씨", "미세먼지", "교통상황",
    "주식시장", "프리뷰", "스포츠", "야구", "축구", "농구", "연예",
    "드라마", "예능", "신곡", "음원", "임신", "결혼", "이혼"
]

# 중복 방지를 위한 세트
processed_urls = set()
processed_titles = set()

# 네이버 뉴스 API를 사용하여 정치 뉴스 가져오기 (최적화)
def get_naver_news():
    print("Fetching news from Naver News API...")
    
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        print("Naver API credentials not found. Skipping Naver News API.")
        return []
    
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
    }
    
    # 핵심 정치인 이름만 사용 (최적화)
    politician_names = [
        "윤석열", "이재명", "홍준표", "한동훈", "조국"
    ]
    
    # 핵심 정치 관련 키워드만 사용 (최적화)
    politics_keywords = [
        "정치인 발언", "정치인 주장", "정치인 통계", "정치인 비판", "거짓말"
    ]
    
    # 팩트체크에 적합한 핵심 키워드만 사용 (최적화)
    factcheck_keywords = [
        "퍼센트", "증가율", "감소율", "사실 확인", "팩트체크"
    ]
    
    # 정치인 간 주장이 엇갈리는 핵심 키워드 (최적화)
    controversy_keywords = [
        "반박", "논쟁", "진실공방", "공방", "엇갈린 주장"
    ]
    
    all_news = []
    
    # 정치인 이름으로 검색 (출력 개수 축소)
    for name in politician_names:
        try:
            # 기사 수 감소 (50→20)
            url = f"https://openapi.naver.com/v1/search/news.json?query={name}+발언&display=20&sort=date"
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                result = response.json()
                news_items = result.get("items", [])
                print(f"Found {len(news_items)} news items for {name}")
                
                for item in news_items:
                    # 이미 처리된 URL인지 확인 (중복 방지)
                    if item['link'] in processed_urls:
                        continue
                        
                    # HTML 태그 제거
                    title = re.sub('<[^<]+?>', '', item['title'])
                    # 이미 처리된 제목인지 확인 (중복 방지)
                    if title in processed_titles:
                        continue
                        
                    # 블랙리스트 체크
                    if any(keyword in title.lower() for keyword in BLACKLIST_KEYWORDS):
                        continue
                        
                    description = re.sub('<[^<]+?>', '', item['description'])
                    
                    news_data = {
                        "title": title,
                        "url": item['link'],
                        "content": description,
                        "source": item['pubDate'],
                        "politician": name
                    }
                    all_news.append(news_data)
                    processed_urls.add(item['link'])
                    processed_titles.add(title)
            else:
                print(f"Failed to fetch news for {name}: {response.status_code}")
                
            # API 호출 간격 감소 (0.2→0.1초)
            time.sleep(0.1)
            
        except Exception as e:
            print(f"Error fetching news for {name}: {e}")
    
    # 정치/논쟁 키워드로 검색 (통합 및 축소)
    combined_keywords = politics_keywords + factcheck_keywords + controversy_keywords
    for keyword in combined_keywords[:10]:  # 상위 10개 키워드만 사용
        try:
            # 기사 수 감소 (20→10)
            url = f"https://openapi.naver.com/v1/search/news.json?query=정치인+{keyword}&display=10&sort=date"
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                result = response.json()
                news_items = result.get("items", [])
                print(f"Found {len(news_items)} news items for keyword {keyword}")
                
                for item in news_items:
                    # 중복 방지
                    if item['link'] in processed_urls:
                        continue
                        
                    title = re.sub('<[^<]+?>', '', item['title'])
                    if title in processed_titles:
                        continue
                        
                    # 블랙리스트 체크
                    if any(keyword in title.lower() for keyword in BLACKLIST_KEYWORDS):
                        continue
                        
                    description = re.sub('<[^<]+?>', '', item['description'])
                    news_data = {
                        "title": title,
                        "url": item['link'],
                        "content": description,
                        "source": item['pubDate']
                    }
                    all_news.append(news_data)
                    processed_urls.add(item['link'])
                    processed_titles.add(title)
            else:
                print(f"Failed to fetch news for keyword {keyword}: {response.status_code}")
                
            # API 호출 간격 감소
            time.sleep(0.1)
            
        except Exception as e:
            print(f"Error fetching news for keyword {keyword}: {e}")
    
    print(f"Total news items fetched from Naver: {len(all_news)}")
    return all_news

# RSS 피드에서 뉴스 수집 (최적화)
def collect_rss_news():
    print("Collecting news from RSS feeds...")
    
    # 주요 한국 뉴스 사이트의 정치 RSS 피드 (수 축소)
    rss_feeds = [
        "https://www.hani.co.kr/rss/politics/",                # 한겨레
        "https://rss.donga.com/politics.xml",                  # 동아일보
        "https://www.khan.co.kr/rss/rssdata/politic.xml",      # 경향신문
        "https://rss.joins.com/joins_politics_list.xml",       # 중앙일보
        "https://www.ytn.co.kr/_ln/0101_rss.xml"               # YTN 정치
    ]
    
    # 수집된 기사 저장
    all_statements = []
    
    for feed_url in rss_feeds:
        try:
            feed = feedparser.parse(feed_url)
            print(f"Found {len(feed.entries)} entries in feed: {feed_url}")
            
            # 항목 수 축소 (100→20)
            for entry in feed.entries[:20]:
                # 중복 방지
                if entry.link in processed_urls:
                    continue
                    
                if hasattr(entry, 'title') and entry.title in processed_titles:
                    continue
                    
                # 블랙리스트 체크
                if any(keyword in entry.title.lower() for keyword in BLACKLIST_KEYWORDS):
                    continue
                    
                # 기본 정보 추출
                statement_data = {
                    "title": entry.title,
                    "url": entry.link,
                    "source": feed.feed.title if hasattr(feed, 'feed') and hasattr(feed.feed, 'title') else "뉴스 소스"
                }
                
                # 기사 본문 추출은 필요한 경우에만 수행
                if is_likely_political(entry.title):
                    try:
                        # 간략 내용만 추출 (전체 내용 대신)
                        if hasattr(entry, 'summary'):
                            statement_data["content"] = entry.summary
                        elif hasattr(entry, 'description'):
                            statement_data["content"] = entry.description
                        else:
                            article_content = get_article_summary(entry.link)
                            if article_content:
                                statement_data["content"] = article_content
                            else:
                                continue  # 내용이 없으면 건너뛰기
                    except Exception as e:
                        print(f"  Error fetching article content: {e}")
                        continue  # 내용 추출 실패 시 건너뛰기
                
                all_statements.append(statement_data)
                processed_urls.add(entry.link)
                processed_titles.add(entry.title)
        
        except Exception as e:
            print(f"Error processing feed {feed_url}: {e}")
        
        # 실행 시간 체크 - 제한 시간의 2/3를 넘으면 중단
        if (time.time() - start_time) > (MAX_RUNTIME_SECONDS * 2/3):
            print("Time limit approaching, skipping remaining RSS feeds")
            break
    
    print(f"Total news items fetched from RSS: {len(all_statements)}")
    return all_statements

# 정치 관련 기사인지 빠르게 확인 (새 함수)
def is_likely_political(title):
    political_keywords = [
        "대통령", "국회", "의원", "정부", "청와대", "여당", "야당", "정책", "장관",
        "민주당", "국민의힘", "위원장", "대표", "대선", "총선", "선거", "투표",
        "윤석열", "이재명", "홍준표", "한동훈", "조국"
    ]
    return any(keyword in title for keyword in political_keywords)

# 기사 URL에서 요약 내용만 추출 (최적화)
def get_article_summary(url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=5)  # 타임아웃 감소 (10→5초)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 메타 설명만 추출 (전체 기사 내용 대신)
        meta_desc = soup.select_one('meta[name="description"]')
        if meta_desc and meta_desc.get('content'):
            return meta_desc.get('content')
            
        # 메타 설명이 없으면 첫 단락만 추출
        first_paragraph = soup.select_one('p')
        if first_paragraph:
            return first_paragraph.get_text(strip=True)
            
        return ""
    except Exception as e:
        print(f"Error extracting article summary: {e}")
        return ""

# 정치인 발언 수집 통합 함수 (최적화)
def collect_politician_statements():
    print("Starting to collect politician statements...")
    
    # 임시 저장 파일 확인
    cached_results = load_temp_results()
    if cached_results:
        print(f"Found cached results with {len(cached_results)} statements")
        return cached_results
    
    # 네이버 뉴스 API에서 뉴스 수집
    naver_news = get_naver_news()
    
    # 시간 체크 - 네이버 API만으로 충분한지 확인
    if len(naver_news) >= 20:  # 충분한 기사가 있으면 RSS 생략
        print(f"Found {len(naver_news)} articles from Naver API, skipping RSS feeds")
        all_statements = naver_news
    else:
        # RSS 피드에서 뉴스 수집
        rss_news = collect_rss_news()
        # 모든 뉴스 통합
        all_statements = naver_news + rss_news
    
    # 빠른 필터링 - 규칙 기반 (최적화)
    all_statements = quick_filter_statements(all_statements)
    print(f"After quick filtering: {len(all_statements)} articles")
    
    # 임시 저장
    save_temp_results(all_statements)
    
    return all_statements

# 빠른 규칙 기반 필터링 (새 함수)
def quick_filter_statements(statements):
    filtered = []
    
    # 정치인 이름 목록
    politicians = [
        "윤석열", "이재명", "홍준표", "한동훈", "조국",
        "이낙연", "우상호", "이준석", "나경원", "김경수"
    ]
    
    # 발언/팩트체크 관련 키워드
    keywords = [
        "발언", "주장", "강조", "밝혔", "말했", "반박", "비판", "지적",
        "퍼센트", "증가", "감소", "통계", "수치", "사실", "팩트"
    ]
    
    for article in statements:
        title = article.get('title', '')
        content = article.get('content', '') if 'content' in article else ''
        
        # 정치인 이름 + 발언 키워드 필터링
        if (any(politician in title for politician in politicians) and 
            any(keyword in title + " " + content for keyword in keywords)):
            
            # 팩트체크에 부적합한 패턴 체크
            if not any(pattern in title.lower() for pattern in ["하겠다", "계획", "예정", "공약", "제안"]):
                filtered.append(article)
                continue
        
        # 이미 정치인 필드가 있는 경우
        if "politician" in article and article["politician"] in politicians:
            filtered.append(article)
    
    # 최대 30개로 제한 (GPT 호출 최소화)
    return filtered[:30]

# 임시 결과 저장 (새 함수)
def save_temp_results(statements):
    with open(TEMP_FILE, 'w', encoding='utf-8') as f:
        json.dump(statements, f, ensure_ascii=False)

# 임시 결과 로드 (새 함수)
def load_temp_results():
    try:
        # 24시간 이상 지난 임시 파일은 무시
        if os.path.exists(TEMP_FILE):
            file_age = time.time() - os.path.getmtime(TEMP_FILE)
            if file_age > 86400:  # 24시간
                return None
                
        with open(TEMP_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return None

# 기사에서 팩트체크 가능한 주장 추출 (최적화: GPT-3.5 사용)
def extract_factcheckable_claim(article):
    # 빠른 규칙 기반 체크 먼저 수행
    if not is_factcheckable_by_rules(article):
        return None
        
    title = article.get('title', '')
    content = article.get('content', '')
    combined_text = f"제목: {title}\n\n내용: {content[:1000]}"  # 최대 1000자로 제한 (2000→1000)
    
    # 팩트체크 예시 (간소화)
    examples = """
예시 1: "윤석열의 핵무장론 때문에 대한민국이 민감 국가로 분류되었다"
예시 2: "특활비는 1원도 횡령한 사실이 없다"
예시 3: "핵무장론은 국제 핵 비확산체제 NPT를 정면으로 위배하는 행위이다"
"""
    
    # 간소화된 프롬프트
    prompt = f"""아래 기사에서 팩트체크 가능한 주장을 한 문장으로 추출하세요:

{combined_text}

팩트체크 가능한 주장 조건:
1. 수치/통계 포함 주장 (예: "물가 20% 상승")
2. 인과관계 주장 (예: "A정책으로 B결과 발생")
3. 사실관계 주장 (예: "특활비 횡령 없다")
4. 정치인들 간 주장이 상충하는 경우

팩트체크하기 좋은 주장 예시: {examples}

다음 형식으로만 응답: "주장: [구체적인 주장]" 또는 "주장 없음"
"""
    
    try:
        # GPT-3.5-turbo 사용 (GPT-4 대신)
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",  # GPT-4 대신 더 경제적인 모델 사용
            messages=[
                {"role": "system", "content": "당신은 기사에서 팩트체크 가능한 주장을 추출하는 전문가입니다."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=100  # 토큰 수 제한 (비용 절감)
        )
        
        extracted_text = response.choices[0].message.content.strip()
        
        # 결과 파싱
        if "주장 없음" in extracted_text:
            return None
        
        # "주장: " 이후의 텍스트 추출
        match = re.search(r'주장:\s*(.*)', extracted_text)
        if match:
            claim = match.group(1).strip()
            print(f"Extracted claim: {claim}")
            return claim
        else:
            return None
            
    except Exception as e:
        print(f"Error extracting claim: {e}")
        return None

# 규칙 기반으로 팩트체크 가능성 확인 (새 함수)
def is_factcheckable_by_rules(article):
    title = article.get('title', '')
    content = article.get('content', '')
    combined = title + " " + content
    
    # 수치 관련 패턴
    if re.search(r'\d+\.?\d*\s*%|\d+\.?\d*\s*배|\d+\s*조|\d+\s*억', combined):
        return True
        
    # 인용구 패턴
    quotes = re.findall(r'"([^"]*)"', combined)
    if any(re.search(r'\d+|증가|감소|상승|하락|실패|성공', quote) for quote in quotes):
        return True
        
    # 논쟁/반박 패턴
    if re.search(r'반박|논쟁|공방|엇갈린|다르다고|아니라고', combined):
        return True
        
    # 사실 관계 패턴
    if re.search(r'사실[은는이가]|거짓|허위|틀렸|잘못|오류|착각', combined):
        return True
    
    return False

# GPT를 사용한 팩트체크 (최적화: 핵심 기능만 GPT-4 유지)
def fact_check_with_structured_output(article):
    # 주장이 있는지 확인
    claim = article.get('claim')
    if not claim:
        # 주장이 없으면 추출 시도 (GPT-3.5 사용)
        claim = extract_factcheckable_claim(article)
        if not claim:
            return None  # 주장을 추출할 수 없으면 스킵
    
    # 발언자와 정당 추출 (규칙 기반으로 변경)
    politician, party = extract_politician_and_party_by_rules(article)
    
    # 발언 상황 컨텍스트 추출 (간소화)
    context = get_simplified_context(article)
    
    # 팩트체크 프롬프트 (간소화)
    prompt = f"""다음 주장의 사실 여부를 객관적으로 검증해주세요:

주장: "{claim}"
제목: "{article.get('title', '')}"

발언자: {politician if politician else '확인 필요'}
정당: {party if party else '확인 필요'}
발언 상황: {context}

검증 결과는 다음 중 하나로 표시하세요:
"사실" / "대체로 사실" / "일부 사실" / "사실 아님"

검증 설명에는 다음을 포함하세요:
- 주장 관련 실제 통계/수치
- 주장의 정확성 또는 오류 증거
- 가능한 경우 출처/증거 언급

아래 JSON 형식으로만 응답해주세요:
{{
    "politician": "발언자 이름",
    "party": "소속 정당",
    "context": "발언 상황",
    "statement": "검증할 주장",
    "verification_result": "사실|대체로 사실|일부 사실|사실 아님",
    "explanation": "검증 결과 상세 설명"
}}
"""
    
    try:
        # 최종 팩트체크는 GPT-4 사용 (핵심 품질 유지)
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "당신은 정치인 발언의 사실 관계를 객관적으로 검증하는 팩트체크 전문가입니다."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2
        )
        
        response_text = response.choices[0].message.content.strip()
        
        # JSON 추출 시도
        try:
            # 정규식으로 JSON 블록 찾기
            json_match = re.search(r'(\{.*\})', response_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(1))
            else:
                # JSON 구조가 완전하지 않은 경우, 전체 응답을 파싱 시도
                result = json.loads(response_text)
                
            # 필수 필드 검증
            required_fields = ["politician", "party", "statement", "verification_result", "explanation"]
            if all(field in result for field in required_fields):
                # 날짜 추가
                result["date"] = datetime.datetime.now().strftime("%Y.%m.%d")
                # 컨텍스트 추가 (없는 경우)
                if "context" not in result:
                    result["context"] = context
                return result
            else:
                # 필드 누락 시 기본값 사용
                return create_fallback_factcheck_result(article, claim, politician, party, context)
                
        except json.JSONDecodeError:
            # JSON 파싱 실패 시 기본값 사용
            return create_fallback_factcheck_result(article, claim, politician, party, context)
            
    except Exception as e:
        print(f"Error during fact-checking: {e}")
        # 오류 발생 시 기본 응답
        return create_fallback_factcheck_result(article, claim, politician, party, context)

# 규칙 기반 정치인/정당 추출 (최적화)
def extract_politician_and_party_by_rules(article):
    title = article.get('title', '')
    content = article.get('content', '')
    
    # 정치인 정보 매핑
    politician_party_map = {
        "윤석열": "국민의힘",
        "이재명": "더불어민주당",
        "한동훈": "국민의힘",
        "홍준표": "국민의힘",
        "유승민": "국민의힘",
        "안철수": "국민의힘",
        "조국": "조국혁신당",
        "이낙연": "더불어민주당",
        "우상호": "더불어민주당",
        "이준석": "개혁신당"
    }
    
    # 텍스트에서 정치인 이름 찾기
    text = title + " " + content
    for politician in politician_party_map:
        if politician in text:
            return politician, politician_party_map[politician]
            
    # 이미 article에 정치인 필드가 있는 경우
    if "politician" in article:
        politician = article["politician"]
        if politician in politician_party_map:
            return politician, politician_party_map[politician]
            
    return None, None

# 간소화된 컨텍스트 추출 (최적화)
def get_simplified_context(statement):
    content = statement.get('content', '')
    
    # 가장 흔한 컨텍스트만 체크
    if "SNS" in content or "페이스북" in content or "트위터" in content:
        return "SNS 발언"
    elif "국회" in content:
        return "국회 발언"
    elif "기자회견" in content:
        return "기자회견"
    elif "인터뷰" in content:
        return "인터뷰"
    
    # 기본값
    return "언론 보도"

# 팩트체크 실패 시 기본 결과 생성 (간소화)
def create_fallback_factcheck_result(article, claim, politician, party, context):
    return {
        "politician": politician if politician else "확인 필요",
        "party": party if party else "확인 필요",
        "context": context,
        "statement": claim,
        "verification_result": "확인 불가",
        "explanation": "현재 이 주장을 검증하기 위한 충분한 정보가 확인되지 않았습니다. 추가적인 자료가 필요합니다.",
        "date": datetime.datetime.now().strftime("%Y.%m.%d")
    }

# 팩트체크 결과 품질 검증 (간소화)
def validate_factcheck_quality(factcheck_result):
    # 간단한 품질 체크만 수행
    if factcheck_result.get("verification_result") == "확인 불가":
        return False
        
    explanation = factcheck_result.get("explanation", "")
    if len(explanation) < 50:
        return False
        
    return True

# 팩트체크 카드 HTML 생성 (유지)
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
        party_class = "reform-indicator"
        avatar_class = "reform-avatar"
    else:
        party_class = "ppp-indicator"
        avatar_class = "ppp-avatar"
    
    # 정치인 이름의 첫 글자 추출
    first_letter = fact_check["politician"][0] if fact_check["politician"] else "?"
    
    # 검증 결과에 따른 스타일 적용
    verification_result = fact_check.get("verification_result", "확인 불가")
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

# 기존 발언 카드에서 이미 처리된 발언을 추출하는 함수 (최적화)
def extract_existing_statements(html_content):
    existing_statements = []
    
    # 정규식으로 간단히 처리 (BeautifulSoup 대신)
    falsehood_contents = re.findall(r'<div class="falsehood-content">\s*(.*?)\s*</div>', html_content, re.DOTALL)
    
    for content in falsehood_contents:
        # 태그 제거
        clean_content = re.sub(r'<[^>]+>', '', content).strip()
        existing_statements.append(clean_content)
    
    return existing_statements

# HTML 파일 업데이트 - 최적화
def update_html_file():
    try:
        # 실행 시간 체크 시작
        start_time = time.time()
        
        # 정치인 발언 수집
        statements = collect_politician_statements()
        
        if not statements:
            print("No statements collected, no updates will be made.")
            return
        
        # 현재 HTML 파일 읽기
        with open('index.html', 'r', encoding='utf-8') as file:
            content = file.read()
        
        # 기존 발언 추출 (최적화된 함수 사용)
        existing_statements = extract_existing_statements(content)
        print(f"Found {len(existing_statements)} existing statements")
        
        # CSS 스타일 추가 (검증 결과 표시용) - 필요한 경우에만
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
        
        # 목표: 하루에 카드 1개만 생성
        target_cards = 1
        max_attempts = 10  # 최대 시도 횟수 감소 (20→10)
        
        # 효율적인 팩트체크를 위해 사전 정렬
        statements = prioritize_statements(statements)
        
        attempts = 0
        
        for statement in statements:
            # 시간 제한 체크 - 너무 오래 걸리면 중단
            if (time.time() - start_time) > (MAX_RUNTIME_SECONDS * 0.8):  # 80% 시간 사용 시 중단
                print("Time limit approaching, stopping processing")
                break
                
            if processed_cards >= target_cards or attempts >= max_attempts:
                break
            
            attempts += 1
            
            # 이미 HTML에 있는 발언인지 빠르게 확인
            statement_content = statement.get('claim', statement.get('title', ''))
            if any(statement_content in existing for existing in existing_statements):
                print(f"Skipping duplicate statement: {statement_content[:30]}...")
                continue
                
            # 이번 실행에서 처리한 발언인지 확인
            if statement_content in processed_statements:
                continue
            
            # 주장 추출 (없으면)
            if 'claim' not in statement:
                claim = extract_factcheckable_claim(statement)
                if claim:
                    statement['claim'] = claim
                else:
                    print(f"Skipping - no factcheckable claim: {statement.get('title', '')[:30]}...")
                    continue
            
            # 팩트체크 수행
            fact_check = fact_check_with_structured_output(statement)
            
            # 팩트체크 실패 시 스킵
            if not fact_check:
                print(f"Skipping - fact check failed: {statement.get('title', '')[:30]}...")
                continue
                
            # 팩트체크 품질 검증
            if not validate_factcheck_quality(fact_check):
                print(f"Skipping - low quality fact check: {statement.get('title', '')[:30]}...")
                continue
                
            # 팩트체크 카드 HTML 생성
            card_html = generate_fact_check_card_html(fact_check)
            all_cards_html += card_html
            
            # 이번에 처리한 발언 기록
            processed_statements.add(statement_content)
            processed_cards += 1
            
            print(f"Successfully processed card: {fact_check['statement'][:50]}...")
        
        # 카드 없으면 종료
        if processed_cards == 0:
            print("No cards were generated. No updates will be made.")
            return
        
        # 마커 확인
        insert_marker = "<!-- FACT_CHECK_CARDS -->"
        
        if insert_marker in content:
            # 마커 위치 찾기
            marker_position = content.find(insert_marker) + len(insert_marker)
            
            # 새 콘텐츠 생성
            new_content = content[:marker_position] + "\n" + all_cards_html + content[marker_position:]
            
            # 마지막 업데이트 날짜 갱신
            today = datetime.datetime.now().strftime("%Y.%m.%d")
            print(f"Added {processed_cards} new fact check cards on {today}")
            
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
    except Exception as e:
        print(f"Error updating HTML file: {e}")
        import traceback
        traceback.print_exc()

# 팩트체크할 기사 우선순위 지정 (최적화)
def prioritize_statements(statements):
    def score_statement(statement):
        score = 0
        title = statement.get('title', '')
        content = statement.get('content', '')
        
        # 숫자 포함 여부
        if re.search(r'\d+', title + ' ' + content):
            score += 3
            
        # 핵심 정치인 언급 여부
        core_politicians = ["윤석열", "이재명", "한동훈", "홍준표", "조국"]
        if any(politician in title for politician in core_politicians):
            score += 4
            
        # 인용구 포함 여부
        if '"' in title or '"' in content:
            score += 2
            
        # 논쟁적 주제 포함 여부
        hot_topics = ["핵무장", "특활비", "민감 국가", "NPT", "탄핵", "계엄"]
        if any(topic in title + ' ' + content for topic in hot_topics):
            score += 5
            
        return score
    
    # 점수 기준으로 정렬
    return sorted(statements, key=score_statement, reverse=True)

# 임시 파일 정리 (새 함수)
def cleanup_temp_files():
    try:
        if os.path.exists(TEMP_FILE):
            os.remove(TEMP_FILE)
            print(f"Removed temporary file: {TEMP_FILE}")
    except Exception as e:
        print(f"Error cleaning up temporary files: {e}")

# 메인 함수 실행
if __name__ == "__main__":
    try:
        # 시간 제한 설정
        start_execution_time = time.time()
        
        # 메인 업데이트 실행
        update_html_file()
        
        # 임시 파일 정리
        cleanup_temp_files()
        
        # 총 실행 시간 출력
        total_time = time.time() - start_execution_time
        print(f"Total execution time: {total_time:.2f} seconds")
        
    except Exception as e:
        print(f"Error in main execution: {e}")
        import traceback
        traceback.print_exc()
