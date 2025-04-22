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

# 네이버 API 키 설정
NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")

# 네이버 뉴스 API를 사용하여 정치 뉴스 가져오기
def get_naver_news():
    print("Fetching news from Naver News API...")
    
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        print("Naver API credentials not found. Skipping Naver News API.")
        return []
    
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
    }
    
    # 정치인 이름 목록
    politician_names = [
        "윤석열", "이재명", "홍준표", "한동훈", "유승민", "안철수", "조국", 
        "이낙연", "우상호", "이준석", "나경원", "김경수", "김동연"
    ]
    
    # 정치 관련 키워드
    politics_keywords = [
        "정치인 발언", "정치인 주장", "정치인 통계", "정치인 수치", "정치인 증가", 
        "정치인 감소", "정치인 비판", "국정 지적", "예산 낭비", "실패", "거짓말"
    ]
    
    # 팩트체크에 적합한 키워드
    factcheck_keywords = [
        "퍼센트", "증가율", "감소율", "배 증가", "배 감소", "통계 수치", 
        "사실 확인", "거짓 주장", "허위 발언", "오보", "팩트체크"
    ]
    
    all_news = []
    
    # 정치인 이름으로 검색
    for name in politician_names:
        try:
            url = f"https://openapi.naver.com/v1/search/news.json?query={name}+발언&display=50&sort=date"
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                result = response.json()
                news_items = result.get("items", [])
                print(f"Found {len(news_items)} news items for {name}")
                
                for item in news_items:
                    # HTML 태그 제거
                    title = re.sub('<[^<]+?>', '', item['title'])
                    description = re.sub('<[^<]+?>', '', item['description'])
                    
                    news_data = {
                        "title": title,
                        "url": item['link'],
                        "content": description,
                        "source": item['pubDate'],
                        "politician": name
                    }
                    all_news.append(news_data)
            else:
                print(f"Failed to fetch news for {name}: {response.status_code}")
                
            # API 호출 간격 (제한: 초당 1건)
            time.sleep(0.2)
            
        except Exception as e:
            print(f"Error fetching news for {name}: {e}")
    
    # 정치 키워드로 검색 (추가적인 다양성을 위해)
    for keyword in politics_keywords:
        try:
            url = f"https://openapi.naver.com/v1/search/news.json?query={keyword}&display=20&sort=date"
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                result = response.json()
                news_items = result.get("items", [])
                print(f"Found {len(news_items)} news items for keyword {keyword}")
                
                for item in news_items:
                    # 기존 정치인 발언 목록과 중복 방지
                    title = re.sub('<[^<]+?>', '', item['title'])
                    if not any(news["title"] == title for news in all_news):
                        description = re.sub('<[^<]+?>', '', item['description'])
                        news_data = {
                            "title": title,
                            "url": item['link'],
                            "content": description,
                            "source": item['pubDate']
                        }
                        all_news.append(news_data)
            else:
                print(f"Failed to fetch news for keyword {keyword}: {response.status_code}")
                
            # API 호출 간격
            time.sleep(0.2)
            
        except Exception as e:
            print(f"Error fetching news for keyword {keyword}: {e}")
    
    # 팩트체크 키워드로 검색 (더 정확한 주장 포착을 위해)
    for keyword in factcheck_keywords:
        try:
            url = f"https://openapi.naver.com/v1/search/news.json?query=정치인+{keyword}&display=20&sort=date"
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                result = response.json()
                news_items = result.get("items", [])
                print(f"Found {len(news_items)} news items for factcheck keyword {keyword}")
                
                for item in news_items:
                    # 기존 목록과 중복 방지
                    title = re.sub('<[^<]+?>', '', item['title'])
                    if not any(news["title"] == title for news in all_news):
                        description = re.sub('<[^<]+?>', '', item['description'])
                        news_data = {
                            "title": title,
                            "url": item['link'],
                            "content": description,
                            "source": item['pubDate']
                        }
                        all_news.append(news_data)
            else:
                print(f"Failed to fetch news for factcheck keyword {keyword}: {response.status_code}")
                
            # API 호출 간격
            time.sleep(0.2)
            
        except Exception as e:
            print(f"Error fetching news for factcheck keyword {keyword}: {e}")
    
    print(f"Total news items fetched from Naver: {len(all_news)}")
    return all_news

# RSS 피드에서 뉴스 수집
def collect_rss_news():
    print("Collecting news from RSS feeds...")
    
    # 주요 한국 뉴스 사이트의 정치 RSS 피드
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
    
    # 수집된 기사 저장
    all_statements = []
    
    for feed_url in rss_feeds:
        try:
            print(f"\nFetching RSS feed: {feed_url}")
            feed = feedparser.parse(feed_url)
            print(f"Found {len(feed.entries)} entries in feed")
            
            for entry in feed.entries[:100]:  # 각 피드에서 최대 100개 항목 확인 (증가)
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
                        statement_data["content"] = article_content[:1500]  # 더 많은 컨텍스트 (800→1500)
                    else:
                        print(f"  No content extracted for: {entry.title}")
                        continue  # 내용이 없으면 건너뛰기
                except Exception as e:
                    print(f"  Error fetching article content: {e}")
                    continue  # 내용 추출 실패 시 건너뛰기
                
                all_statements.append(statement_data)
        
        except Exception as e:
            print(f"Error processing feed {feed_url}: {e}")
        
        # 요청 간 간격 두기
        time.sleep(0.5)
    
    print(f"Total news items fetched from RSS: {len(all_statements)}")
    return all_statements

# 정치인 발언 수집 통합 함수
def collect_politician_statements():
    print("Starting to collect politician statements...")
    
    # 네이버 뉴스 API에서 뉴스 수집
    naver_news = get_naver_news()
    
    # RSS 피드에서 뉴스 수집
    rss_news = collect_rss_news()
    
    # 모든 뉴스 통합
    all_statements = naver_news + rss_news
    
    # 중복 제거
    unique_statements = deduplicate_statements(all_statements)
    print(f"After deduplication: {len(unique_statements)} unique articles")
    
    # 정치인 발언 필터링
    politician_statements = filter_politician_statements(unique_statements)
    print(f"Filtered politician statements: {len(politician_statements)}")
    
    # 팩트체크 가능한 발언 필터링
    factcheckable_statements = filter_factcheckable_statements(politician_statements)
    print(f"Factcheckable statements: {len(factcheckable_statements)}")
    
    # 숫자 기반 주장을 우선하도록 정렬
    factcheckable_statements = prioritize_numeric_statements(factcheckable_statements)
    
    # 단계별 수집 결과 출력
    print("\nCollection Summary:")
    print(f"- All news articles: {len(unique_statements)}")
    print(f"- Politician statements: {len(politician_statements)}")
    print(f"- Factcheckable statements: {len(factcheckable_statements)}")
    
    # 단계별 필터링 적용 (가장 엄격한 것부터 시작)
    if len(factcheckable_statements) >= 3:
        print("Using factcheckable statements.")
        return factcheckable_statements
    elif len(politician_statements) >= 3:
        print("Not enough factcheckable statements. Using all politician statements.")
        return politician_statements
    elif len(unique_statements) >= 3:
        print("Not enough politician statements. Using all news articles.")
        return unique_statements
    else:
        print("No suitable articles found.")
        return []

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
        
        # 추가: 직접 인용구 추출 시도
        quotes = re.findall(r'"([^"]*)"', content)
        if quotes:
            content += "\n\n직접 인용구: " + " | ".join(quotes)
                
        return content
    except Exception as e:
        print(f"Error extracting article content: {e}")
        return ""

# 기사에서 팩트체크 가능한 주장 추출
def extract_factcheckable_claim(article):
    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    # 기사 제목과 내용 결합
    title = article.get('title', '')
    content = article.get('content', '')
    combined_text = f"제목: {title}\n\n내용: {content[:2000]}"  # 최대 2000자까지 사용
    
    # 주장 추출 프롬프트
    prompt = f"""아래 기사에서 팩트체크 가능한 주장을 추출해주세요:

{combined_text}

팩트체크 가능한 주장의 조건:
1. 구체적인 수치나 통계를 포함한 주장 (예: "물가가 20% 상승했다", "실업률이 5% 감소했다")
2. 인과관계에 대한 주장 (예: "A 정책으로 인해 B 결과가 발생했다")
3. 역사적 사실에 대한 주장 (예: "과거에 정부는 A라는 정책을 시행했다")

다음 형식으로 응답해주세요:
- 주장이 있다면: "주장: [구체적인 주장]"
- 주장이 없다면: "주장 없음"

주장이 여러 개라면 가장 팩트체크하기 좋은 하나만 선택해서 반환해주세요.
"""
    
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "당신은 기사에서 팩트체크 가능한 주장을 추출하는 전문가입니다."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2
        )
        
        extracted_text = response.choices[0].message.content.strip()
        
        # 결과 파싱
        if "주장 없음" in extracted_text:
            print(f"No factcheckable claim found in article: {title}")
            return None
        
        # "주장: " 이후의 텍스트 추출
        match = re.search(r'주장:\s*(.*)', extracted_text)
        if match:
            claim = match.group(1).strip()
            print(f"Extracted claim: {claim}")
            return claim
        else:
            print(f"Failed to extract claim properly from: {extracted_text}")
            return None
            
    except Exception as e:
        print(f"Error extracting claim: {e}")
        return None

# 중복 제거
def deduplicate_statements(statements):
    unique_statements = []
    urls = set()
    titles = set()
    
    for statement in statements:
        url = statement.get("url", "")
        title = statement.get("title", "")
        
        # URL과 제목이 모두 중복이 아닌 경우만 추가
        if url not in urls and title not in titles:
            urls.add(url)
            titles.add(title)
            unique_statements.append(statement)
    
    return unique_statements

# 정치인 발언 필터링
def filter_politician_statements(articles):
    politician_statements = []
    
    # 정치인 이름 목록
    politicians = [
        "윤석열", "이재명", "홍준표", "유승민", "심상정", "안철수", "정세균", "한동훈", 
        "이낙연", "원희룡", "조국", "박영선", "이준석", "나경원", "김경수", "김동연"
    ]
    
    # 발언 관련 키워드
    keywords = [
        "발언", "주장", "강조", "밝혔", "말했", "언급", "제안", "요구", "비판", "촉구", 
        "강연", "연설", "토론", "인터뷰", "기자회견", "질의", "답변", "반박", "지적"
    ]
    
    for article in articles:
        title = article.get('title', '')
        content = article.get('content', '')
        full_text = title + " " + content
        
        # 정치인 이름이 포함되어 있는지 확인
        has_politician = any(politician in full_text for politician in politicians)
        
        # 발언 관련 키워드가 포함되어 있는지 확인
        has_keyword = any(keyword in full_text for keyword in keywords)
        
        # 이미 특정 정치인 이름이 저장된 경우
        if "politician" in article and article["politician"] in politicians:
            has_politician = True
        
        # 정치인 이름과 발언 관련 키워드가 모두 포함되어 있으면 정치인 발언으로 간주
        if has_politician and has_keyword:
            politician_statements.append(article)
    
    return politician_statements

# 팩트체크 가능한 기사 필터링
def filter_factcheckable_statements(articles):
    factcheckable = []
    
    for article in articles:
        title = article.get('title', '')
        content = article.get('content', '')
        
        # 팩트체크에 부적합한 패턴 체크
        if any(pattern in title.lower() for pattern in ["하겠다", "계획", "예정", "공약", "제안"]):
            continue
            
        # 숫자 포함 여부 체크 (우선순위 높음)
        has_numbers = bool(re.search(r'\d+\.?\d*\s*%|\d+\.?\d*\s*배|\d+\s*명|\d+\s*인|\d+\s*건', title + content))
        
        # 주장 관련 키워드 체크
        has_claim_keywords = any(keyword in (title + content) for keyword in 
                             ["주장", "지적", "비판", "논란", "통계", "수치", "실증", "발표", "밝혔"])
        
        # 숫자가 있거나 주장 키워드가 있으면 추가 처리
        if has_numbers or has_claim_keywords:
            # GPT로 주장 추출 시도
            claim = extract_factcheckable_claim(article)
            if claim:
                article["claim"] = claim
                factcheckable.append(article)
    
    return factcheckable

# 숫자 기반 주장을 우선하도록 정렬
def prioritize_numeric_statements(statements):
    def has_numbers(statement):
        title = statement.get('title', '')
        content = statement.get('content', '')
        claim = statement.get('claim', '')
        combined = title + ' ' + content + ' ' + claim
        return bool(re.search(r'\d+', combined))
    
    numeric_statements = [s for s in statements if has_numbers(s)]
    other_statements = [s for s in statements if not has_numbers(s)]
    
    return numeric_statements + other_statements

# 정치인 이름과 정당 추출
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
        "나경원": "국민의힘",
        "김경수": "더불어민주당",
        "김동연": "더불어시민당"
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

# GPT를 사용한 팩트체크 (구조화된 응답 요구)
def fact_check_with_structured_output(article):
    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    # 주장이 있는지 확인
    claim = article.get('claim')
    if not claim:
        # 주장이 없으면 추출 시도
        claim = extract_factcheckable_claim(article)
        if not claim:
            return None  # 주장을 추출할 수 없으면 스킵
    
    # 발언자와 정당 추출
    politician = article.get('politician')
    if not politician:
        politician, party = extract_politician_and_party(article.get('title', ''), article.get('content', ''))
    else:
        _, party = extract_politician_and_party("", "")  # 정당만 찾기
    
    # 발언 상황 컨텍스트 추출
    context = get_statement_context(article)
    
    # 팩트체크 프롬프트
    prompt = f"""다음 주장의 사실 여부를 객관적으로 검증해주세요:

주장: "{claim}"
기사 제목: "{article.get('title', '')}"
추가 컨텍스트: {article.get('content', '')[:800]}

발언자: {politician if politician else '확인 필요'}
정당: {party if party else '확인 필요'}
발언 상황: {context}

지침:
1. 객관적인 팩트체크를 수행하고 검증 결과를 아래 항목 중 하나로 표시:
   - "사실": 주장이 완전히 사실임
   - "대체로 사실": 주장이 기본적으로 사실이지만 약간의 과장이나 누락이 있음
   - "일부 사실": 주장의 일부만 사실임
   - "사실 아님": 주장이 명백히 거짓임

2. 검증 설명에는 반드시 다음을 포함하세요:
   - 주장이 참조한 통계나 사실의 실제 수치
   - 주장의 정확성이나 오류를 보여주는 구체적 증거
   - 가능한 경우, 출처나 증거자료 언급

아래 JSON 형식으로만 응답해주세요:
{{
    "politician": "발언자 이름",
    "party": "소속 정당",
    "context": "발언 상황",
    "statement": "검증할 주장",
    "is_factcheckable": true,
    "verification_result": "사실|대체로 사실|일부 사실|사실 아님",
    "explanation": "검증 결과 상세 설명"
}}

중요: 추가 텍스트나 설명 없이 위 JSON 형식만 응답해주세요.
"""
    
    try:
        # 첫 번째 시도: 완전한 프롬프트
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
                print(f"Missing required fields in response: {result}")
                # 두 번째 시도는 아래에서 실행됨
                
        except json.JSONDecodeError:
            print(f"Failed to parse JSON from response: {response_text}")
            # 두 번째 시도는 아래에서 실행됨
            
        # 두 번째 시도: 더 엄격한 포맷 요구
        strict_prompt = prompt + "\n\n중요: 응답은 반드시 유효한 JSON 형식이어야 합니다. 다른 어떤 텍스트도 포함하지 마세요."
        
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "당신은 팩트체크 전문가입니다. 오직 유효한 JSON 형식으로만 응답하세요."},
                {"role": "user", "content": strict_prompt}
            ],
            temperature=0.1
        )
        
        response_text = response.choices[0].message.content.strip()
        
        # 두 번째 JSON 추출 시도
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
                print(f"Missing required fields in second attempt: {result}")
                # 최후의 수단: 수동 구성
                return create_fallback_factcheck_result(article, claim, politician, party, context)
                
        except json.JSONDecodeError:
            print(f"Failed to parse JSON from second response: {response_text}")
            # 최후의 수단: 수동 구성
            return create_fallback_factcheck_result(article, claim, politician, party, context)
            
    except Exception as e:
        print(f"Error during fact-checking: {e}")
        # 오류 발생 시 기본 응답
        return create_fallback_factcheck_result(article, claim, politician, party, context)

# 팩트체크 실패 시 기본 결과 생성
def create_fallback_factcheck_result(article, claim, politician, party, context):
    # 최소한의 정보로 기본 결과 구성
    return {
        "politician": politician if politician else "확인 필요",
        "party": party if party else "확인 필요",
        "context": context,
        "statement": claim,
        "is_factcheckable": True,
        "verification_result": "확인 불가",
        "explanation": "현재 이 주장을 검증하기 위한 충분한 정보가 확인되지 않았습니다. 추가적인 자료가 필요합니다.",
        "date": datetime.datetime.now().strftime("%Y.%m.%d")
    }

# 팩트체크 결과 품질 검증
def validate_factcheck_quality(factcheck_result):
    # 검증 결과가 "확인 불가"이면 낮은 품질로 판단
    if factcheck_result.get("verification_result") == "확인 불가":
        return False
        
    # 설명 길이가 너무 짧으면 낮은 품질로 판단
    explanation = factcheck_result.get("explanation", "")
    if len(explanation) < 50:
        return False
        
    # 구체적 증거나 숫자가 포함되어 있는지 확인
    has_evidence = bool(re.search(r'\d+\.?\d*\s*%|\d+\.?\d*\s*배|\d+\s*명|\d+\s*건', explanation))
    if not has_evidence:
        return False
        
    return True

# 팩트체크 카드 HTML 생성
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
            if statement.get('title', '') in existing_statements:
                print(f"Skipping duplicate statement: {statement.get('title', '')}")
                continue
                
            # 추가 중복 체크 - 이번 실행에서 처리한 발언인지 확인
            if statement.get('title', '') in processed_statements:
                print(f"Skipping statement already processed in this run: {statement.get('title', '')}")
                continue
            
            # 팩트체크 수행
            fact_check = fact_check_with_structured_output(statement)
            
            # 팩트체크 실패 시 스킵
            if not fact_check:
                print(f"Skipping statement due to fact check failure: {statement.get('title', '')}")
                continue
                
            # 팩트체크 품질 검증
            if not validate_factcheck_quality(fact_check):
                print(f"Skipping low-quality fact check: {statement.get('title', '')}")
                continue
                
            # 팩트체크 카드 HTML 생성
            card_html = generate_fact_check_card_html(fact_check)
            all_cards_html += card_html
            
            # 이번에 처리한 발언 기록
            processed_statements.add(statement.get('title', ''))
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
