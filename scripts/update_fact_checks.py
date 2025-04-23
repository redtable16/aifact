import os
import json
import random
import datetime
import requests
import feedparser
import time
import re
import traceback
from bs4 import BeautifulSoup
import openai

# 환경 변수에서 API 키 설정
NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
FORCE_UPDATE = os.getenv("FORCE_UPDATE", "false").lower() == "true"  # 강제 업데이트 옵션

# 임시 파일 경로
TEMP_FILE = 'temp_results.json'
SEARCH_CACHE_FILE = 'search_cache.json'

# 실행 시간 제한 설정 (18분)
MAX_RUNTIME_SECONDS = 18 * 60
start_time = time.time()

# OpenAI 클라이언트 설정
openai.api_key = OPENAI_API_KEY
client = openai.OpenAI(api_key=OPENAI_API_KEY)

# 블랙리스트 키워드 - 정치 관련 뉴스가 아닌 내용 필터링
BLACKLIST_KEYWORDS = [
    "날씨", "코로나", "스포츠", "연예", "드라마", "영화", "공연", 
    "예능", "신곡", "음원", "임신", "결혼", "이혼", "사고", "사망"
]

# 검색 결과 캐시
search_cache = {}

# 중복 방지를 위한 세트
processed_urls = set()
processed_titles = set()

# 진행 상황 출력 함수
def print_progress(message):
    """진행 상황을 시간과 함께 출력"""
    elapsed = time.time() - start_time
    print(f"[{elapsed:.1f}s] {message}")

# 초기 설정 함수
def initialize():
    """초기 설정 및 캐시 로드"""
    global search_cache
    try:
        # 검색 캐시 로드
        if os.path.exists(SEARCH_CACHE_FILE):
            with open(SEARCH_CACHE_FILE, 'r', encoding='utf-8') as f:
                search_cache = json.load(f)
            print_progress(f"Loaded {len(search_cache)} cached search results")
    except Exception as e:
        print_progress(f"Error loading cache: {e}")
        search_cache = {}

# 캐시 저장 함수
def save_cache():
    """검색 캐시 저장"""
    try:
        with open(SEARCH_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(search_cache, f, ensure_ascii=False)
        print_progress(f"Saved {len(search_cache)} search results to cache")
    except Exception as e:
        print_progress(f"Error saving cache: {e}")

# 네이버 뉴스 API를 사용하여 정치 뉴스 가져오기
def get_naver_news():
    print_progress("Fetching news from Naver News API...")
    
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        print_progress("Naver API credentials not found. Skipping Naver News API.")
        return []
    
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
    }
    
    # 정치인 이름 목록
    politician_names = [
        "윤석열", "이재명", "홍준표", "한동훈", "조국",
        "이낙연", "우상호", "이준석", "나경원", "박지현"
    ]
    
    # 정치 관련 키워드
    politics_keywords = [
        "정치인 발언", "정치인 주장", "정치인 통계", "팩트체크", 
        "정치 논란", "정치 공방", "정치 비판"
    ]
    
    all_news = []
    
    # 정치인 이름으로 검색
    for name in politician_names:
        try:
            url = f"https://openapi.naver.com/v1/search/news.json?query={name}+발언&display=15&sort=date"
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                result = response.json()
                news_items = result.get("items", [])
                print_progress(f"Found {len(news_items)} news items for {name}")
                
                for item in news_items:
                    # 중복 방지
                    if item['link'] in processed_urls:
                        continue
                        
                    # HTML 태그 제거
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
                        "source": item['pubDate'],
                        "politician": name
                    }
                    all_news.append(news_data)
                    processed_urls.add(item['link'])
                    processed_titles.add(title)
            else:
                print_progress(f"Failed to fetch news for {name}: {response.status_code}")
                
            # API 호출 간격
            time.sleep(0.1)
            
        except Exception as e:
            print_progress(f"Error fetching news for {name}: {e}")
    
    # 정치 키워드로 검색
    for keyword in politics_keywords:
        try:
            url = f"https://openapi.naver.com/v1/search/news.json?query=정치인+{keyword}&display=10&sort=date"
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                result = response.json()
                news_items = result.get("items", [])
                print_progress(f"Found {len(news_items)} news items for keyword {keyword}")
                
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
                print_progress(f"Failed to fetch news for keyword {keyword}: {response.status_code}")
                
            # API 호출 간격
            time.sleep(0.1)
            
        except Exception as e:
            print_progress(f"Error fetching news for keyword {keyword}: {e}")
    
    print_progress(f"Total news items fetched from Naver: {len(all_news)}")
    return all_news

# RSS 피드에서 뉴스 수집
def collect_rss_news():
    print_progress("Collecting news from RSS feeds...")
    
    # 주요 한국 뉴스 사이트의 정치 RSS 피드
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
            print_progress(f"Found {len(feed.entries)} entries in feed: {feed_url}")
            
            # 항목 수 제한 (20개)
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
                        # 간략 내용 추출
                        if hasattr(entry, 'summary'):
                            statement_data["content"] = entry.summary
                        elif hasattr(entry, 'description'):
                            statement_data["content"] = entry.description
                        else:
                            # URL에서 간략 내용 가져오기
                            article_content = get_article_summary(entry.link)
                            if article_content:
                                statement_data["content"] = article_content
                            else:
                                continue  # 내용이 없으면 건너뛰기
                    except Exception as e:
                        print_progress(f"Error fetching article content: {e}")
                        continue  # 내용 추출 실패 시 건너뛰기
                
                all_statements.append(statement_data)
                processed_urls.add(entry.link)
                processed_titles.add(entry.title)
        
        except Exception as e:
            print_progress(f"Error processing feed {feed_url}: {e}")
        
        # 실행 시간 체크 - 제한 시간의 1/3을 넘으면 중단
        if (time.time() - start_time) > (MAX_RUNTIME_SECONDS / 3):
            print_progress("Time limit approaching, skipping remaining RSS feeds")
            break
    
    print_progress(f"Total news items fetched from RSS: {len(all_statements)}")
    return all_statements

# 정치 관련 기사인지 빠르게 확인
def is_likely_political(title):
    political_keywords = [
        "대통령", "국회", "의원", "정부", "청와대", "여당", "야당", "정책", "장관",
        "민주당", "국민의힘", "위원장", "대표", "대선", "총선", "선거",
        "윤석열", "이재명", "홍준표", "한동훈", "조국"
    ]
    return any(keyword in title for keyword in political_keywords)

# 기사 URL에서 요약 내용만 추출
def get_article_summary(url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 메타 설명 추출
        meta_desc = soup.select_one('meta[name="description"]')
        if meta_desc and meta_desc.get('content'):
            return meta_desc.get('content')
            
        # 메타 설명이 없으면 첫 단락만 추출
        first_paragraph = soup.select_one('p')
        if first_paragraph:
            return first_paragraph.get_text(strip=True)
            
        return ""
    except Exception as e:
        print_progress(f"Error extracting article summary: {e}")
        return ""

# 기사 URL에서 전체 내용 추출
def get_full_article_content(url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(response.text, 'html.parser')
        
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
                return article_text
                
        # 선택자로 찾지 못한 경우 메타 설명 사용
        meta_desc = soup.select_one('meta[name="description"]')
        if meta_desc and meta_desc.get('content'):
            return meta_desc.get('content')
            
        # 그래도 없으면 제목 + 첫 단락
        title = soup.select_one('title')
        first_p = soup.select_one('p')
        
        content = ""
        if title:
            content += title.get_text(strip=True) + ". "
        if first_p:
            content += first_p.get_text(strip=True)
            
        return content
    except Exception as e:
        print_progress(f"Error extracting full article content: {e}")
        return ""

# 정치인 발언 수집 통합 함수
def collect_politician_statements():
    print_progress("Starting to collect politician statements...")
    
    # 네이버 뉴스 API에서 뉴스 수집
    naver_news = get_naver_news()
    
    # 실행 시간 확인
    if (time.time() - start_time) > (MAX_RUNTIME_SECONDS / 2):
        print_progress("Half of time limit reached, skipping RSS feeds")
        all_statements = naver_news
    else:
        # RSS 피드에서 뉴스 수집
        rss_news = collect_rss_news()
        # 모든 뉴스 통합
        all_statements = naver_news + rss_news
    
    # 빠른 필터링 - 규칙 기반
    all_statements = quick_filter_statements(all_statements)
    print_progress(f"After quick filtering: {len(all_statements)} articles")
    
    return all_statements

# 빠른 규칙 기반 필터링
def quick_filter_statements(statements):
    filtered = []
    
    # 정치인 이름 목록
    politicians = [
        "윤석열", "이재명", "홍준표", "한동훈", "조국",
        "이낙연", "우상호", "이준석", "나경원", "김경수"
    ]
    
    # 발언/팩트체크 관련 키워드
    keywords = [
        "발언", "주장", "말했", "밝혔", "반박", "비판", "지적",
        "퍼센트", "증가", "감소", "통계", "수치", "사실", "팩트"
    ]
    
    for article in statements:
        title = article.get('title', '')
        content = article.get('content', '') if 'content' in article else ''
        
        # 정치인 이름 + 발언 키워드 필터링
        if (any(politician in title + " " + content for politician in politicians) and 
            any(keyword in title + " " + content for keyword in keywords)):
            
            # 팩트체크에 부적합한 패턴 체크
            if not any(pattern in title.lower() for pattern in ["하겠다", "계획", "예정", "공약", "제안"]):
                filtered.append(article)
    
    # 최대 개수 제한 (효율성)
    return filtered[:30]

# GPT를 사용해 기사에서 팩트체크할 발언 추출 (1단계)
def extract_factcheckable_claim_using_gpt(article):
    title = article.get('title', '')
    content = article.get('content', '')
    url = article.get('url', '')
    
    # 내용이 부족하면 전체 기사 가져오기
    if len(content) < 300:
        try:
            print_progress(f"Article content is short, getting full content from: {url}")
            full_content = get_full_article_content(url)
            if full_content and len(full_content) > len(content):
                content = full_content
                print_progress(f"Retrieved full content: {len(content)} characters")
        except Exception as e:
            print_progress(f"Error getting full content: {e}")
    
    # 토큰 제한을 위해 내용 요약
    if len(content) > 1500:
        content = content[:1500] + "..."
    
    prompt = f"""다음 기사에서 팩트체크할 가치가 있는 정치인의 발언을 찾아주세요:

기사 제목: {title}
기사 내용: 
{content}

팩트체크할 만한 발언은 다음과 같은 특성을 가집니다:
1. 구체적인 수치나 통계를 포함한 주장
2. 과거 사실에 대한 주장
3. 현재 상황에 대한 주장
4. 인과관계에 대한 주장
5. 정치인들 간에 상반된 주장
6. 정치적으로 중요하거나 논란이 될 수 있는 주장

폭넓게 생각하여 팩트체크 가능성이 있는 발언을 찾아주세요.
발언을 찾지 못하면 "has_factcheckable_claim": false로 설정하세요.

다음 JSON 형식으로만 응답해주세요:
{{
    "has_factcheckable_claim": true/false,
    "speaker": "발언자 이름",
    "speaker_position": "발언자의 직위",
    "party": "소속 정당",
    "statement": "발언 내용",
    "context": "발언 상황/맥락"
}}
"""
    
    try:
        # GPT-3.5 사용 (비용 효율성)
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "당신은 정치 기사에서 팩트체크할 발언을 정확히 식별하는 전문가입니다."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=600  # 토큰 제한 완화
        )
        
        response_text = response.choices[0].message.content.strip()
        print_progress(f"GPT response for claim extraction: {response_text[:100]}...")
        
        # JSON 추출
        json_match = re.search(r'(\{.*\})', response_text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group(1))
            
            if result.get("has_factcheckable_claim", False):
                print_progress(f"Found claim by {result.get('speaker')}: {result.get('statement')[:50]}...")
                return result
            else:
                print_progress("No factcheckable claim found in this article")
                return None
        else:
            print_progress("Failed to extract JSON from GPT response")
            return None
            
    except Exception as e:
        print_progress(f"Error extracting claim: {e}")
        traceback.print_exc()
        return None

# 웹 검색을 통한 추가 정보 수집 (2단계-1)
def web_search_for_factcheck(query):
    """팩트체크를 위한 웹 검색 수행"""
    
    # 캐시 확인
    cache_key = query.strip().lower()
    if cache_key in search_cache:
        print_progress(f"Using cached search results for: {query}")
        return search_cache[cache_key]
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    # 검색 쿼리 인코딩
    encoded_query = requests.utils.quote(query)
    
    # 네이버 검색
    search_url = f"https://search.naver.com/search.naver?query={encoded_query}"
    
    try:
        response = requests.get(search_url, headers=headers, timeout=5)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 검색 결과 추출
        search_results = []
        
        # 뉴스 결과
        news_items = soup.select(".news_area")
        for item in news_items[:3]:  # 상위 3개만
            title_elem = item.select_one(".news_tit")
            desc_elem = item.select_one(".dsc_txt")
            link_elem = title_elem.get('href') if title_elem else None
            
            if title_elem and desc_elem and link_elem:
                result = {
                    "title": title_elem.text.strip(),
                    "description": desc_elem.text.strip(),
                    "url": link_elem
                }
                search_results.append(result)
        
        # 웹문서 결과
        web_items = soup.select(".total_area")
        for item in web_items[:2]:  # 상위 2개만
            title_elem = item.select_one(".total_tit")
            desc_elem = item.select_one(".total_dsc")
            link_elem = title_elem.find('a').get('href') if title_elem and title_elem.find('a') else None
            
            if title_elem and desc_elem and link_elem:
                result = {
                    "title": title_elem.text.strip(),
                    "description": desc_elem.text.strip(),
                    "url": link_elem
                }
                search_results.append(result)
                
        # 캐시에 저장
        search_cache[cache_key] = search_results
        
        # 캐시 크기 제한
        if len(search_cache) > 100:
            # 랜덤하게 20개 항목 제거
            keys_to_remove = random.sample(list(search_cache.keys()), 20)
            for key in keys_to_remove:
                search_cache.pop(key, None)
        
        return search_results
        
    except Exception as e:
        print_progress(f"Error in web search: {e}")
        return []

# 관련 있는 검색 결과만 필터링 (2단계-2)
def filter_relevant_results(search_results, statement):
    """발언과 관련 있는 검색 결과만 필터링"""
    
    # 검색 결과가 없으면 빈 리스트 반환
    if not search_results:
        return []
    
    # 관련성 판단을 위한 핵심 키워드 추출
    statement_words = set(re.findall(r'\w+', statement.lower()))
    
    relevant_results = []
    for result in search_results:
        title = result.get('title', '')
        description = result.get('description', '')
        
        # 제목과 설명에서 키워드 추출
        result_words = set(re.findall(r'\w+', (title + ' ' + description).lower()))
        
        # 키워드 겹침 정도 계산
        common_words = statement_words.intersection(result_words)
        
        # 최소 2개 이상의 키워드가 겹치면 관련 있는 것으로 판단
        if len(common_words) >= 2:
            relevant_results.append(result)
    
    # 최대 3개까지 제한
    return relevant_results[:3]

# 추가 정보를 바탕으로 발언 검증 (2단계-3)
def verify_claim_with_additional_info(claim_info, additional_info):
    """추가 정보를 바탕으로 발언 검증"""
    
    speaker = claim_info.get("speaker", "")
    statement = claim_info.get("statement", "")
    context = claim_info.get("context", "")
    speaker_position = claim_info.get("speaker_position", "")
    party = claim_info.get("party", "")
    
    print_progress(f"Verifying claim: '{statement[:50]}...' by {speaker}")
    
    # 추가 정보를 텍스트로 변환
    additional_info_text = ""
    for idx, info in enumerate(additional_info, 1):
        additional_info_text += f"정보 {idx}:\n제목: {info.get('title', '')}\n내용: {info.get('description', '')}\n출처: {info.get('url', '')}\n\n"
    
    # 추가 정보가 없는 경우
    if not additional_info_text:
        additional_info_text = "추가 정보가 없습니다. 기본 정보만으로 판단해주세요."
        print_progress("No additional information found for verification")
    else:
        print_progress(f"Found {len(additional_info)} additional information sources")
    
    prompt = f"""다음 정치인의 발언을 추가 정보를 바탕으로 팩트체크해주세요:

발언자: {speaker} ({speaker_position})
소속 정당: {party}
발언 내용: "{statement}"
발언 맥락: {context}

추가 정보:
{additional_info_text}

위 발언과 추가 정보를 바탕으로 발언의 사실 여부를 검증하고, 다음 중 하나로 판정해주세요:
- 사실: 발언이 완전히 사실임
- 대체로 사실: 발언이 대체로 사실이지만 약간의 과장이나 누락이 있음
- 일부 사실: 발언의 일부만 사실임
- 사실 아님: 발언이 사실과 다름
- 확인 불가: 현재 정보로는 사실 여부를 확인할 수 없음

다음 JSON 형식으로 응답해주세요:
{{
    "speaker": "{speaker}",
    "speaker_position": "{speaker_position}",
    "party": "{party}",
    "statement": "{statement}",
    "verification_result": "사실|대체로 사실|일부 사실|사실 아님|확인 불가",
    "explanation": "검증 결과에 대한 상세한 설명과 근거",
    "sources": ["참고한 출처 URL"]
}}
"""
    
    try:
        # GPT-4 사용 (팩트체크 정확도를 위해)
        print_progress("Sending verification request to GPT-4...")
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "당신은 객관적이고 정확한 팩트체크를 수행하는 전문가입니다."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=1000  # 토큰 제한 (충분한 설명 위해)
        )
        
        response_text = response.choices[0].message.content.strip()
        print_progress(f"Received verification response: {response_text[:100]}...")
        
        # JSON 추출
        json_match = re.search(r'(\{.*\})', response_text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group(1))
            
            # 날짜 추가
            result["date"] = datetime.datetime.now().strftime("%Y.%m.%d")
            result["context"] = context
            
            print_progress(f"Verification result: {result.get('verification_result', 'unknown')}")
            return result
        else:
            print_progress("Failed to extract JSON from verification response")
            return None
            
    except Exception as e:
        print_progress(f"Error in verification: {e}")
        traceback.print_exc()
        return None

# 2단계 팩트체크 수행 - 통합 함수
def two_stage_factcheck(article):
    """2단계 팩트체크 수행 - 발언 추출 후 검증"""
    
    # 1단계: 발언 추출
    print_progress(f"Extracting claim from article: {article.get('title', '')[:50]}...")
    claim_info = extract_factcheckable_claim_using_gpt(article)
    
    if not claim_info:
        print_progress("No factcheckable claim found in this article")
        return None  # 팩트체크할 발언 없음
    
    print_progress(f"Found claim: {claim_info.get('statement', '')[:50]}... by {claim_info.get('speaker', '')}")
    
    # 2단계: 추가 정보 수집 및 검증
    print_progress("Collecting additional information for verification...")
    speaker = claim_info.get("speaker", "")
    statement = claim_info.get("statement", "")
    
    # 추가 정보 수집을 위한 검색 쿼리 구성
    search_queries = [
        f"{speaker} {statement[:30]}",  # 발언자와 발언 내용 앞부분
        f"{statement[:40]} 사실"  # 발언 내용과 사실
    ]
    
    additional_info = []
    
    # 각 쿼리로 검색하여 추가 정보 수집
    for query in search_queries:
        try:
            # 웹 검색 수행
            print_progress(f"Searching with query: {query}")
            search_results = web_search_for_factcheck(query)
            
            # 관련 있는 정보만 필터링
            relevant_results = filter_relevant_results(search_results, statement)
            print_progress(f"Found {len(relevant_results)} relevant results")
            
            additional_info.extend(relevant_results)
            
            # 충분한 정보를 얻었으면 중단
            if len(additional_info) >= 3:
                break
                
        except Exception as e:
            print_progress(f"Error searching for additional info: {e}")
    
    # 추가 정보를 포함하여 팩트체크 수행
    print_progress("Performing factcheck with additional information...")
    factcheck_result = verify_claim_with_additional_info(claim_info, additional_info)
    
    if factcheck_result:
        print_progress(f"Factcheck completed: {factcheck_result.get('verification_result', '')}")
    else:
        print_progress("Factcheck failed to produce a result")
        
    return factcheck_result

# Fallback 팩트체크 - 기사 내용 전체를 GPT에게 전달
def fallback_direct_factcheck(article):
    """백업 팩트체크 전략: 기사 내용 전체를 GPT에게 전달"""
    print_progress("Using fallback direct factcheck approach...")
    
    title = article.get('title', '')
    content = article.get('content', '')
    url = article.get('url', '')
    
    # 내용이 부족하면 전체 기사 가져오기
    if len(content) < 300:
        try:
            print_progress(f"Article content is short, getting full content from: {url}")
            full_content = get_full_article_content(url)
            if full_content and len(full_content) > len(content):
                content = full_content
                print_progress(f"Retrieved full content: {len(content)} characters")
        except Exception as e:
            print_progress(f"Error getting full content: {e}")
    
    if len(content) > 1500:
        content = content[:1500] + "..."
    
    prompt = f"""이 기사를 바탕으로 가능한 팩트체크를 수행해주세요:

기사 제목: {title}
기사 내용: {content}
기사 URL: {url}

이 기사에 관련된 정치인의 주장이나 논쟁점을 식별하고, 이를 검증해주세요.
직접적인 인용문이 없더라도, 기사에서 언급된 주요 사실 주장을 팩트체크해주세요.

다음 JSON 형식으로 응답해주세요:
{{
    "speaker": "관련 정치인 이름",
    "speaker_position": "정치인의 직위",
    "party": "소속 정당",
    "statement": "검증할 내용/주장",
    "context": "기사 맥락",
    "verification_result": "사실|대체로 사실|일부 사실|사실 아님|확인 불가",
    "explanation": "검증 결과에 대한 상세한 설명",
    "sources": ["참고한 출처"]
}}
"""
    
    try:
        print_progress("Sending fallback request to GPT-4...")
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "당신은 최고의 팩트체크 전문가입니다. 기사에서 검증 가능한 내용을 식별하고 이를 객관적으로 검증하세요."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1
        )
        
        response_text = response.choices[0].message.content.strip()
        print_progress(f"Received fallback response: {response_text[:100]}...")
        
        # JSON 추출
        json_match = re.search(r'(\{.*\})', response_text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group(1))
            
            # 날짜 추가
            result["date"] = datetime.datetime.now().strftime("%Y.%m.%d")
            
            print_progress(f"Fallback verification result: {result.get('verification_result', 'unknown')}")
            return result
        else:
            print_progress("Failed to extract JSON from fallback response")
            return None
            
    except Exception as e:
        print_progress(f"Error in fallback factcheck: {e}")
        traceback.print_exc()
        return None

# 팩트체크 결과 품질 검증
def validate_factcheck_quality(factcheck_result):
    """팩트체크 결과의 품질 검증"""
    
    # 필수 필드 확인
    required_fields = ["speaker", "statement", "verification_result", "explanation"]
    if not all(field in factcheck_result for field in required_fields):
        print_progress("Missing required fields in factcheck result")
        return False
    
    # 검증 결과가 확인 불가인 경우 낮은 품질로 간주 (FORCE_UPDATE가 켜져 있으면 허용)
    if factcheck_result.get("verification_result") == "확인 불가" and not FORCE_UPDATE:
        print_progress("Factcheck result is 'unverifiable' and FORCE_UPDATE is not enabled")
        return False
    
    # 설명이 너무 짧은 경우 낮은 품질로 간주
    explanation = factcheck_result.get("explanation", "")
    if len(explanation) < 50:
        print_progress(f"Explanation is too short: {len(explanation)} characters")
        return False
    
    print_progress("Factcheck result passed quality validation")
    return True

# 팩트체크 카드 HTML 생성
def generate_fact_check_card_html(fact_check):
    """팩트체크 결과를 HTML 카드로 변환"""
    
    party_class = ""
    avatar_class = ""
    
    # 정당에 따른 스타일 클래스 설정
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
    first_letter = fact_check["speaker"][0] if fact_check["speaker"] else "?"
    
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
    
    # 정치인 직위 표시 추가
    speaker_position = fact_check.get("speaker_position", "")
    politician_display = f'{fact_check["speaker"]} {speaker_position}'.strip()
    
    # HTML 카드 생성
    card_html = "<!-- 팩트체크 카드 -->\n"
    card_html += f'<div class="falsehood-card" data-party="{fact_check["party"]}">\n'
    card_html += '<div class="falsehood-header">\n'
    card_html += f'<div class="politician-avatar {avatar_class}">{first_letter}</div>\n'
    card_html += '<div class="politician-info">\n'
    card_html += '<div class="politician-name">\n'
    card_html += f'<span class="party-indicator {party_class}"></span>\n'
    card_html += f'{politician_display}\n'
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
    
    # 출처 표시
    if "sources" in fact_check and fact_check["sources"]:
        card_html += '<div class="falsehood-sources">\n'
        card_html += '<span class="sources-label">참고 출처:</span>\n'
        card_html += '<ul>\n'
        for source in fact_check["sources"]:
            if source and source.startswith("http"):
                card_html += f'<li><a href="{source}" target="_blank">{source}</a></li>\n'
        card_html += '</ul>\n'
        card_html += '</div>\n'
    
    card_html += '</div>\n'
    
    return card_html

# 기존 발언 카드에서 이미 처리된 발언을 추출하는 함수
def extract_existing_statements(html_content):
    """HTML에서 기존 팩트체크 발언 추출"""
    
    existing_statements = []
    
    # 정규식으로 기존 발언 추출
    falsehood_contents = re.findall(r'<div class="falsehood-content">\s*(.*?)\s*</div>', html_content, re.DOTALL)
    
    for content in falsehood_contents:
        # 태그 제거
        clean_content = re.sub(r'<[^>]+>', '', content).strip()
        existing_statements.append(clean_content)
    
    return existing_statements

# 임시 파일 정리
def cleanup_temp_files():
    """임시 파일 정리"""
    try:
        # 오래된 파일 삭제
        for file_path in [TEMP_FILE, SEARCH_CACHE_FILE]:
            if os.path.exists(file_path):
                file_age = time.time() - os.path.getmtime(file_path)
                if file_age > 86400 * 7:  # 7일 이상 된 파일만 삭제
                    os.remove(file_path)
                    print_progress(f"Removed old temporary file: {file_path}")
    except Exception as e:
        print_progress(f"Error cleaning up temporary files: {e}")

# HTML 파일 업데이트 메인 함수
def update_html_file():
    """HTML 파일 업데이트 메인 함수"""
    
    global start_time
    start_time = time.time()
    
    try:
        # 초기 설정
        initialize()
        
        # 정치인 발언 수집
        statements = collect_politician_statements()
        
        if not statements:
            print_progress("No statements collected, no updates will be made.")
            return
        
        # 현재 HTML 파일 읽기
        with open('index.html', 'r', encoding='utf-8') as file:
            content = file.read()
        
        # 기존 발언 추출
        existing_statements = extract_existing_statements(content)
        print_progress(f"Found {len(existing_statements)} existing statements")
        
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
        
        .falsehood-sources {
            margin-top: 0.5rem;
            font-size: 0.8rem;
            color: #6c757d;
        }
        
        .sources-label {
            font-weight: bold;
        }
        
        .falsehood-sources ul {
            margin-top: 0.25rem;
            padding-left: 1.5rem;
        }
        
        .falsehood-sources a {
            color: #007bff;
            text-decoration: none;
            word-break: break-all;
        }
        """
            # </style> 태그를 찾아서 그 앞에 스타일 추가
            style_end_pos = content.find('</style>')
            if style_end_pos > 0:
                content = content[:style_end_pos] + style_addition + content[style_end_pos:]
                print_progress("Added verification result styles to CSS")
                
                # 업데이트된 HTML 내용으로 파일 쓰기
                with open('index.html', 'w', encoding='utf-8') as file:
                    file.write(content)
                
                # 다시 읽기
                with open('index.html', 'r', encoding='utf-8') as file:
                    content = file.read()
            else:
                print_progress("Could not find </style> tag to add new styles")
        
        # 팩트체크 결과 저장
        factcheck_results = []
        
        # 효율적 팩트체크를 위해 기사 수 제한
        max_articles_to_process = 15
        
        # 처리할 기사 선택적 확장 및 임의 선택
        articles_to_process = []
        selected_articles = random.sample(statements, min(max_articles_to_process, len(statements)))
        
        for article in selected_articles:
            try:
                # 내용이 짧으면 전체 기사 내용 가져오기
                if len(article.get('content', '')) < 300:
                    url = article.get('url', '')
                    full_content = get_full_article_content(url)
                    if full_content:
                        article['content'] = full_content
                articles_to_process.append(article)
            except Exception as e:
                print_progress(f"Error expanding article content: {e}")
                articles_to_process.append(article)  # 원래 내용 그대로 추가
        
        # 각 기사에 대해 2단계 팩트체크 수행
        attempts = 0
        force_process = FORCE_UPDATE  # 강제 처리 옵션
        
        for article in articles_to_process:
            # 시간 제한 체크
            elapsed_time = time.time() - start_time
            if elapsed_time > (MAX_RUNTIME_SECONDS * 0.8):
                print_progress(f"Time limit approaching ({elapsed_time:.1f}s), stopping processing")
                break
            
            # 중복 방지
            url = article.get('url', '')
            if url in processed_urls:
                continue
            
            print_progress(f"Processing article: {article.get('title', '')[:50]}...")
            attempts += 1
            
            # 2단계 팩트체크 수행
            factcheck_result = two_stage_factcheck(article)
            
            # 팩트체크 실패 시 백업 전략 시도
            if not factcheck_result and (force_process or attempts >= len(articles_to_process) / 2):
                print_progress("No factcheck result found, using fallback approach...")
                # 기사를 직접 GPT에게 전달하여 팩트체크 시도
                factcheck_result = fallback_direct_factcheck(article)
                force_process = False  # 한 번만 강제 처리
            
            # 결과 처리
            if factcheck_result:
                # 중복 확인
                new_statement = factcheck_result.get("statement", "")
                if any(existing in new_statement or new_statement in existing for existing in existing_statements):
                    print_progress("Skipping duplicate statement")
                    continue
                
                # 품질 검증
                if validate_factcheck_quality(factcheck_result):
                    print_progress(f"Successfully verified claim: {factcheck_result.get('verification_result')}")
                    factcheck_results.append(factcheck_result)
                    processed_urls.add(url)
                    
                    # 목표 달성 시 중단 (하루에 1개만)
                    if len(factcheck_results) >= 1:
                        break
                else:
                    print_progress("Factcheck result failed quality validation")
        
        # 결과가 없으면 종료
        if not factcheck_results:
            print_progress("No factcheck results generated, no updates will be made.")
            return
        
        # 팩트체크 카드 HTML 생성
        all_cards_html = ""
        for result in factcheck_results:
            card_html = generate_fact_check_card_html(result)
            all_cards_html += card_html
        
        # 마커 확인
        insert_marker = "<!-- FACT_CHECK_CARDS -->"
        
        if insert_marker in content:
            # 마커 위치 찾기
            marker_position = content.find(insert_marker) + len(insert_marker)
            
            # 새 콘텐츠 생성
            new_content = content[:marker_position] + "\n" + all_cards_html + content[marker_position:]
            
            # 마지막 업데이트 날짜 갱신
            today = datetime.datetime.now().strftime("%Y.%m.%d")
            print_progress(f"Added {len(factcheck_results)} new fact check cards on {today}")
            
            # HTML 파일에서 제목 및 레이블 텍스트 업데이트
            new_content = new_content.replace("허위 발언 트래커", "정치인 발언 검증 서비스")
            new_content = new_content.replace("<!-- 허위 발언 카드", "<!-- 팩트체크 카드")
            new_content = new_content.replace('<span class="correction-label">실제 사실:</span>', '<span class="correction-label">검증 설명:</span>')
            
            # 업데이트된 콘텐츠 저장
            with open('index.html', 'w', encoding='utf-8') as file:
                file.write(new_content)
                print_progress("Successfully saved updated HTML file")
        else:
            print_progress(f"Could not find marker '{insert_marker}' in the HTML file")
        
        # 캐시 저장
        save_cache()
        
    except Exception as e:
        print_progress(f"Error updating HTML file: {e}")
        traceback.print_exc()
    finally:
        # 실행 시간 출력
        elapsed_time = time.time() - start_time
        print_progress(f"Total execution time: {elapsed_time:.2f} seconds")

# 메인 실행 함수
if __name__ == "__main__":
    try:
        # HTML 파일 업데이트
        update_html_file()
        
        # 임시 파일 정리
        cleanup_temp_files()
        
    except Exception as e:
        print(f"Error in main execution: {e}")
        traceback.print_exc()
