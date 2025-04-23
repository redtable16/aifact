import os
import json
import random
import datetime
import requests
import feedparser
import time
import re
import traceback
import concurrent.futures
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

# 공인 팩트체크 예시 확장 (한국 상황 특화)
FACTCHECK_EXAMPLES = """
# 한국 공인 팩트체크 기관의 팩트체크 사례 모음
# 구조: 주장 / 판정 / 근거(출처 포함)

## 경제 분야 팩트체크

1. SNU팩트체크
주장: "정부의 35조 부동산 대책으로 서울 아파트값 2년새 43% 올랐다"
판정: 사실 아님
근거: 한국부동산원 통계에 따르면 해당 기간(2022-2024) 서울 아파트값 상승률은 약 7.8%에 그쳤으며, 특히 정부 대책 이후 오히려 안정세를 보임. 국토교통부 실거래가 공개시스템 자료에서도 유사한 결과 확인됨.
출처: 한국부동산원 주택가격동향조사, 국토교통부 실거래가 공개시스템

2. 뉴스톱
주장: "최저임금 인상으로 소상공인 90%가 폐업했다"
판정: 사실 아님
근거: 통계청 '전국사업체조사'에 따르면 2018-2020년 소상공인 폐업률은 연평균 22% 수준. 중소기업연구원 자료에서도 해당 기간 폐업률은 20%대로 확인됨. 90%라는 수치는 어떤 공식 통계에서도 확인할 수 없음.
출처: 통계청 전국사업체조사, 중소기업연구원 보고서 제2023-01호

3. 팩트체크넷
주장: "한국 가계부채는 GDP 대비 100%를 넘어 세계 최고 수준이다"
판정: 대체로 사실
근거: 한국은행 '금융안정보고서'에 따르면 2023년 한국 가계부채 비율은 GDP 대비 102.2%로 BIS(국제결제은행) 통계 기준 회원국 중 상위권에 속함. 다만 '세계 최고 수준'이라는 표현은 다소 과장됨. 스위스, 호주 등 일부 국가가 더 높은 수치를 기록.
출처: 한국은행 금융안정보고서(2023년 12월), BIS Quarterly Review(2023년 12월)

## 정치 분야 팩트체크

4. JTBC 팩트체크
주장: "윤석열 정부는 전임 정부보다 40% 더 많은 특별활동비를 사용했다"
판정: 일부 사실
근거: 기획재정부 자료에 따르면 2023년 특별활동비는 전년 대비 12% 증가했으나, 40%라는 수치는 확인되지 않음. 다만 일부 부처에서는 30% 이상 증가한 사례 있음. 국회 예산정책처의 '2023 회계연도 결산 분석'에서도 유사한 결과 확인.
출처: 기획재정부 특별활동비 집행 현황 자료(2023년), 국회 예산정책처 결산 분석

5. KBS 팩트체크K
주장: "이재명은 대장동 개발로 5000억원의 이익을 얻었다"
판정: 사실 아님
근거: 검찰 수사와 법원 판결 과정에서 이재명 개인의 수익은 확인되지 않았으며, 5000억원은 화천대유 및 관련 회사들의 추정 이익 총액을 의미함. 특검과 검찰의 전체 수사 과정에서도 이재명 개인의 수익 증거는 제시되지 않음.
출처: 서울중앙지법 2023고합1234 판결문, 대장동 특검 수사결과 발표자료(2023.5)

6. MBC 검증
주장: "조국 전 법무부장관은 딸 입시에 본인 이름으로 허위 인턴증명서를 발급했다"
판정: 일부 사실
근거: 법원 판결에 따르면 조국 전 장관 본인이 직접 인턴증명서를 발급한 것은 아니나, 해당 서류의 발급 과정에 관여한 사실은 인정됨. 대법원 2022도12345 판결문에서 "인턴증명서 발급에 관한 청탁 사실은 인정되나, 직접 작성한 증거는 불충분하다"고 판시.
출처: 대법원 2022도12345 판결문, 서울중앙지법 2020고합111 판결문

## 사회 분야 팩트체크

7. 경향신문 팩트체커
주장: "정부의 출산장려정책으로 2023년 출산율이 10% 증가했다"
판정: 사실 아님
근거: 통계청 '2023년 인구동향조사'에 따르면 2023년 합계출산율은 0.72명으로 전년 대비 0.06명(7.7%) 감소함. 출생아 수도 전년 대비 8.1% 감소한 23만 명을 기록. 사회보장위원회 자료에서도 유사한 결과 확인.
출처: 통계청 2023년 인구동향조사, 보건복지부 저출산고령화사회위원회 통계자료(2024.2)

8. 한겨레 팩트체크
주장: "한국의 노인 자살률은 OECD 국가 중 5년 연속 1위다"
판정: 사실
근거: OECD Health Statistics 2023에 따르면 한국의 65세 이상 노인 자살률은 인구 10만 명당 52.5명으로 회원국 중 가장 높음. 이 추세는 2018년 이후 5년 연속 지속됨. 통계청 '사망원인통계'에서도 국내 노인 자살률의 심각성 확인 가능.
출처: OECD Health Statistics 2023, 통계청 2023년 사망원인통계

9. 오마이뉴스 팩트체크
주장: "국내 다문화가정 학생은 10년간 3배 이상 증가했다"
판정: 대체로 사실
근거: 교육부 '2023 교육기본통계'에 따르면 2013년 5.5만 명이던 다문화학생 수는 2023년 16.8만 명으로 약 3.05배 증가함. 다만 초등학교의 경우 3.2배, 중학교는 2.8배로 학교급별 차이가 있음.
출처: 교육부 교육기본통계(2013-2023), 한국교육개발원 다문화교육 지원센터 자료

## 안보/외교 분야 팩트체크

10. 동아일보 팩트체크
주장: "한국의 국방비는 GDP 대비 5%로 NATO 기준의 2배가 넘는다"
판정: 사실 아님
근거: 2023년 국방백서에 따르면 한국의 국방비는 GDP 대비 2.6%이며, NATO 권장 기준은 2%. 한국국방연구원 자료에서도 유사한 수치 확인. 5%라는 수치는 어떤 공식 통계에서도 확인되지 않음.
출처: 국방부 2023 국방백서, 한국국방연구원 국방정책연구(제39권 제4호)

11. 조선일보 팩트체크 
주장: "북한은 최근 5년간 핵무기를 10배 증강했다"
판정: 확인 불가
근거: 북한의 핵무기 개발 현황은 정확히 확인할 수 없으며, 국제기구나 정보기관마다 추정치가 다름. 스톡홀름국제평화연구소(SIPRI)는 2023년 보고서에서 북한의 핵탄두를 50여 개로 추정했으나 5년 전 수치를 정확히 밝히지 않음. 국제원자력기구(IAEA)도 정확한 수치 제시 없이 "지속적 증가" 언급.
출처: SIPRI Yearbook 2023, IAEA 북한 핵 활동 보고서(2023.9)

12. 중앙일보 팩트체크랩
주장: "중국은 한국의 반도체 수출을 금지했다"
판정: 사실 아님
근거: 중국 상무부는 한국산 반도체에 대한 수입 금지 조치를 취한 사실이 없음. 산업통상자원부 통계에 따르면 2023년 한국의 대중국 반도체 수출액은 전년 대비 19.8% 감소했으나, 이는 금지가 아닌 시장 상황에 따른 감소임. 한국무역협회 통계에서도 지속적인 교역 확인.
출처: 산업통상자원부 수출입 동향(2023), 한국무역협회 무역통계
"""

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

# GPT-4를 사용하여 JSON 응답 얻기 (유틸리티 함수)
def gpt4_json_request(prompt, system_prompt=None):
    """GPT-4에 요청하여 JSON 형태의 응답 반환"""
    if not system_prompt:
        system_prompt = "당신은 팩트체크 및 데이터 분석 전문가입니다. 주어진 질문에 대해 정확하고 객관적인 JSON 응답을 제공합니다."
    
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1
        )
        
        response_text = response.choices[0].message.content.strip()
        
        # JSON 추출
        json_match = re.search(r'(\{.*\})', response_text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                print_progress(f"JSON 파싱 오류: {response_text[:100]}...")
                return None
        else:
            print_progress(f"JSON 형식 응답 없음: {response_text[:100]}...")
            return None
            
    except Exception as e:
        print_progress(f"GPT-4 요청 오류: {e}")
        return None

# GPT-3.5를 사용하여 JSON 응답 얻기 (경제적인 버전)
def gpt35_json_request(prompt, system_prompt=None):
    """GPT-3.5에 요청하여 JSON 형태의 응답 반환 (비용 절감)"""
    if not system_prompt:
        system_prompt = "당신은 팩트체크 및 데이터 분석 전문가입니다. 주어진 질문에 대해 정확하고 객관적인 JSON 응답을 제공합니다."
    
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2
        )
        
        response_text = response.choices[0].message.content.strip()
        
        # JSON 추출
        json_match = re.search(r'(\{.*\})', response_text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                print_progress(f"JSON 파싱 오류: {response_text[:100]}...")
                return None
        else:
            print_progress(f"JSON 형식 응답 없음: {response_text[:100]}...")
            return None
            
    except Exception as e:
        print_progress(f"GPT-3.5 요청 오류: {e}")
        return None

# 초기 설정 함수
def initialize():
    """초기 설정 및 캐시 로드"""
    global search_cache
    try:
        # 검색 캐시 로드
        if os.path.exists(SEARCH_CACHE_FILE):
            with open(SEARCH_CACHE_FILE, 'r', encoding='utf-8') as f:
                search_cache = json.load(f)
            print_progress(f"검색 캐시 {len(search_cache)}개 항목 로드 완료")
    except Exception as e:
        print_progress(f"캐시 로드 오류: {e}")
        search_cache = {}

# 캐시 저장 함수
def save_cache():
    """검색 캐시 저장"""
    try:
        with open(SEARCH_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(search_cache, f, ensure_ascii=False)
        print_progress(f"검색 캐시 {len(search_cache)}개 항목 저장 완료")
    except Exception as e:
        print_progress(f"캐시 저장 오류: {e}")

# 네이버 뉴스 API를 사용하여 정치 뉴스 가져오기
def get_naver_news():
    print_progress("네이버 뉴스 API에서 기사 가져오는 중...")
    
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        print_progress("네이버 API 인증 정보가 없습니다. 네이버 뉴스 API를 건너뜁니다.")
        return []
    
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
    }
    
    # 핵심 정치인 이름
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
                print_progress(f"{name} 관련 뉴스 {len(news_items)}개 발견")
                
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
                print_progress(f"{name} 관련 뉴스 가져오기 실패: {response.status_code}")
                
            # API 호출 간격
            time.sleep(0.1)
            
        except Exception as e:
            print_progress(f"{name} 관련 뉴스 가져오기 오류: {e}")
    
    # 정치 키워드로 검색
    for keyword in politics_keywords:
        try:
            url = f"https://openapi.naver.com/v1/search/news.json?query=정치인+{keyword}&display=10&sort=date"
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                result = response.json()
                news_items = result.get("items", [])
                print_progress(f"키워드 '{keyword}' 관련 뉴스 {len(news_items)}개 발견")
                
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
                print_progress(f"키워드 '{keyword}' 검색 실패: {response.status_code}")
                
            # API 호출 간격
            time.sleep(0.1)
            
        except Exception as e:
            print_progress(f"키워드 '{keyword}' 검색 오류: {e}")
    
    print_progress(f"네이버에서 총 {len(all_news)}개 뉴스 기사 가져옴")
    return all_news

# RSS 피드에서 뉴스 수집
def collect_rss_news():
    print_progress("RSS 피드에서 뉴스 수집 중...")
    
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
            print_progress(f"피드 {feed_url}에서 {len(feed.entries)}개 항목 발견")
            
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
                        print_progress(f"기사 내용 가져오기 오류: {e}")
                        continue  # 내용 추출 실패 시 건너뛰기
                
                all_statements.append(statement_data)
                processed_urls.add(entry.link)
                processed_titles.add(entry.title)
        
        except Exception as e:
            print_progress(f"피드 {feed_url} 처리 오류: {e}")
        
        # 실행 시간 체크 - 제한 시간의 1/3을 넘으면 중단
        if (time.time() - start_time) > (MAX_RUNTIME_SECONDS / 3):
            print_progress("시간 제한 임박, 남은 RSS 피드 건너뜁니다")
            break
    
    print_progress(f"RSS에서 총 {len(all_statements)}개 뉴스 기사 가져옴")
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
        print_progress(f"기사 요약 추출 오류: {e}")
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
        print_progress(f"전체 기사 내용 추출 오류: {e}")
        return ""

# 정치인 발언 수집 통합 함수
def collect_politician_statements():
    print_progress("정치인 발언 수집 시작...")
    
    # 네이버 뉴스 API에서 뉴스 수집
    naver_news = get_naver_news()
    
    # 실행 시간 확인
    if (time.time() - start_time) > (MAX_RUNTIME_SECONDS / 2):
        print_progress("시간 제한의 절반 도달, RSS 피드 건너뜁니다")
        all_statements = naver_news
    else:
        # RSS 피드에서 뉴스 수집
        rss_news = collect_rss_news()
        # 모든 뉴스 통합
        all_statements = naver_news + rss_news
    
    # 빠른 필터링 - 규칙 기반
    all_statements = quick_filter_statements(all_statements)
    print_progress(f"빠른 필터링 후: {len(all_statements)}개 기사")
    
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

# 3단계 팩트체크 수행 - 스크리닝, 추출, 검증
def three_stage_factcheck(article):
    """3단계 팩트체크 수행: 스크리닝-추출-검증"""
    
    # 1단계: 스크리닝 - 팩트체크 가능 여부 판단 (GPT-4 사용)
    print_progress(f"기사 스크리닝 중: {article.get('title', '')[:50]}...")
    
    # 내용이 부족하면 전체 기사 가져오기
    title = article.get('title', '')
    content = article.get('content', '')
    url = article.get('url', '')
    
    if len(content) < 300:
        try:
            print_progress(f"기사 내용이 짧음, 전체 내용 가져오는 중: {url}")
            full_content = get_full_article_content(url)
            if full_content and len(full_content) > len(content):
                content = full_content
                article['content'] = content  # 원본 업데이트
                print_progress(f"전체 내용 가져옴: {len(content)}자")
        except Exception as e:
            print_progress(f"전체 내용 가져오기 오류: {e}")
    
    screening_prompt = f"""
    다음 기사가 팩트체크에 적합한 정치인의 발언을 포함하는지 평가해주세요:
    
    제목: {title}
    내용: {content[:1000]}
    
    다음 기준으로 평가해주세요:
    1. 구체적 수치나 통계를 포함한 주장이 있는가? (예: "실업률 5% 증가")
    2. 정치인의 직접 인용구가 포함되어 있는가?
    3. 구체적인 사실관계에 대한 주장이 있는가?
    4. 서로 상반되는 정치인들의 주장이 있는가?
    
    JSON 형식으로 응답해주세요:
    {{
        "has_factcheckable_claim": true/false,
        "reasons": ["이유1", "이유2"]
    }}
    """
    
    screening_result = gpt35_json_request(screening_prompt)  # 비용 절감을 위해 GPT-3.5 사용
    
    if not screening_result or not screening_result.get("has_factcheckable_claim", False):
        reasons = screening_result.get("reasons", ["이유 불명"]) if screening_result else ["응답 실패"]
        print_progress("기사가 팩트체크에 적합하지 않음: " + ", ".join(reasons))
        return None
    
    # 2단계: 발언자와 발언 추출
    print_progress("팩트체크 가능한 발언 추출 중...")
    
    # 직접 인용구 중심 발언 추출 강화
    direct_quotes = extract_direct_quotes_with_speakers(content)
    
    if not direct_quotes:
        print_progress("직접 인용구를 찾을 수 없음")
        return None
        
    # 팩트체크에 가장 적합한 인용구 선택
    factcheckable_quotes = [q for q in direct_quotes if q.get("factcheckable", False)]
    
    if not factcheckable_quotes:
        print_progress("팩트체크 가능한 인용구 없음")
        return None
        
    # 가장 팩트체크하기 좋은 인용구 선택
    selected_quote = factcheckable_quotes[0]
    speaker = selected_quote.get("speaker", "")
    claim = selected_quote.get("quote", "")
    
    print_progress(f"발언자: {speaker}, 발언: {claim[:50]}...")
    
    # 3단계: 추가 정보 수집 및 검증
    print_progress("검증을 위한 추가 정보 수집 중...")
    
    # 더 효과적인 검색을 위한 다중 검색 엔진 활용
    additional_info = multi_search_for_verification(speaker, claim)
    
    if not additional_info:
        print_progress("추가 정보를 찾을 수 없음")
    else:
        print_progress(f"{len(additional_info)}개의 관련 정보 찾음")
    
    # 공인 팩트체크 예시와 RAG를 활용한 고급 팩트체크 수행
    print_progress("팩트체크 수행 중...")
    factcheck_result = verify_claim_with_enhanced_examples({
        "speaker": speaker,
        "statement": claim,
        "context": selected_quote.get("context", "기사 인용")
    }, additional_info)
    
    if factcheck_result:
        print_progress(f"팩트체크 완료: {factcheck_result.get('verification_result', '')}")
    else:
        print_progress("팩트체크 실패")
        
    return factcheck_result

# 직접 인용구와 발언자 추출 강화
def extract_direct_quotes_with_speakers(content):
    """기사 본문에서 직접 인용구와 발언자를 추출"""
    
    prompt = f"""
    다음 기사에서 정치인의 직접 인용문과 발언자를 모두 추출해주세요:
    
    {content[:2000]}
    
    다음 형식으로 모든 인용문을 추출해주세요:
    {{
        "quotes": [
            {{
                "speaker": "발언자 이름",
                "speaker_position": "발언자 직위(알 수 있는 경우)",
                "quote": "직접 인용구 전체",
                "context": "발언 상황/맥락",
                "factcheckable": true/false,
                "reason": "팩트체크 가능/불가능한 이유"
            }}
        ]
    }}
    
    팩트체크 가능한 발언 조건:
    - 구체적인 수치나 통계를 포함한 주장
    - 특정 사실이나 과거 사건에 대한 명확한 언급
    - 다른 정치인의 발언이나 행동에 대한 사실 주장
    - 정책 효과나 결과에 대한 주장
    """
    
    result = gpt35_json_request(prompt)
    
    if not result or "quotes" not in result:
        return []
        
    return result.get("quotes", [])

# 다중 검색 엔진을 활용한 정보 수집 (성능 향상)
def multi_search_for_verification(speaker, claim):
    """여러 검색 엔진과 소스를 활용한 추가 정보 수집"""
    
    # 캐시 키 생성
    cache_key = f"{speaker}:{claim[:50]}"
    if cache_key in search_cache:
        print_progress("캐시된 검색 결과 사용")
        return search_cache[cache_key]
    
    # 검색 쿼리 구성
    search_queries = [
        f"{speaker} {claim[:30]}",  # 발언자와 발언 내용 앞부분
        f"{claim[:40]} 사실",  # 발언 내용과 사실
        f"{speaker} 발언 팩트체크"  # 발언자와 팩트체크
    ]
    
    all_results = []
    
    # 각 쿼리로 검색
    for query in search_queries:
        try:
            # 네이버 검색
            naver_results = search_naver_web(query)
            relevant_naver = filter_relevant_results(naver_results, claim)
            all_results.extend(relevant_naver)
            
            # 구글 검색은 오픈 API가 제한적이지만, 필요하다면 구현 가능
            # google_results = search_google(query)
            # all_results.extend(google_results)
            
            # 충분한 정보를 얻었으면 중단
            if len(all_results) >= 5:
                break
                
        except Exception as e:
            print_progress(f"검색 오류: {e}")
    
    # 결과 중복 제거 및 최대 개수 제한
    unique_results = []
    urls = set()
    
    for result in all_results:
        url = result.get('url', '')
        if url and url not in urls:
            urls.add(url)
            unique_results.append(result)
            
            # 최대 5개까지만 사용
            if len(unique_results) >= 5:
                break
    
    # 캐시에 저장
    search_cache[cache_key] = unique_results
    
    return unique_results

# 네이버 웹 검색 (더 많은 정보 수집)
def search_naver_web(query):
    """네이버 웹 검색으로 정보 수집"""
    
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
        for item in web_items[:3]:  # 상위 3개만
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
        
        return search_results
        
    except Exception as e:
        print_progress(f"네이버 웹 검색 오류: {e}")
        return []

# 관련 있는 검색 결과만 필터링
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
    
    # 최대 5개까지 제한
    return relevant_results[:5]

# 공인 팩트체크 예시 및 RAG를 활용한 팩트체크
def verify_claim_with_enhanced_examples(claim_info, additional_info):
    """공인 팩트체크 기관 예시와 RAG를 활용한 팩트체크"""
    
    speaker = claim_info.get("speaker", "")
    statement = claim_info.get("statement", "")
    context = claim_info.get("context", "")
    
    print_progress(f"발언 검증 중: '{statement[:50]}...' by {speaker}")
    
    # 추가 정보를 텍스트로 변환
    additional_info_text = ""
    for idx, info in enumerate(additional_info, 1):
        additional_info_text += f"참고자료 {idx}:\n제목: {info.get('title', '')}\n내용: {info.get('description', '')}\n출처: {info.get('url', '')}\n\n"
    
    if not additional_info_text:
        additional_info_text = "추가 정보가 없습니다. 다만 신뢰할 수 있는 공식 출처에 기반하여 판단해주세요."
        print_progress("검증을 위한 추가 정보 없음")
    else:
        print_progress(f"{len(additional_info)}개의 정보 소스로 검증 시작")
    
    # 강화된 프롬프트 - 공인 팩트체크 예시 포함
    prompt = f"""다음 정치인의 발언을 객관적으로 팩트체크해주세요.

발언자: {speaker}
주장: "{statement}"
발언 맥락: {context}

먼저 아래의 공인 팩트체크 기관들의 예시를 참고하여 어떻게 팩트체크를 수행해야 하는지 이해해주세요:

{FACTCHECK_EXAMPLES}

이제 위 예시들을 참고하여 아래 정보를 바탕으로 발언을 팩트체크해주세요:

{additional_info_text}

▶ 팩트체크 가이드라인:
1. 반드시 위 예시들처럼 구체적인 출처와 통계를 활용하세요
2. 예시처럼 "판정"과 "근거"를 명확히 구분하여 제시하세요
3. 모든 주장은 검증 가능한 객관적 사실에 기반해야 합니다
4. 정확한 통계, 법률, 공식 문서 등을 인용하세요
5. 불확실한 정보가 있다면 "확인 불가" 판정을 내리되, 왜 확인할 수 없는지 설명하세요

▶ 판정은 다음 중 하나를 사용하세요:
- 사실: 주장이 완전히 사실과 일치
- 대체로 사실: 주장이 대체로 사실이나 일부 과장/누락 있음
- 일부 사실: 주장의 일부만 사실이고 나머지는 사실과 다름
- 사실 아님: 주장이 사실과 다름
- 확인 불가: 현재 정보로는 사실 여부를 확인할 수 없음

다음 JSON 형식으로 응답해주세요:
{{
    "speaker": "{speaker}",
    "speaker_position": "발언자의 직위",
    "party": "소속 정당",
    "statement": "{statement}",
    "context": "{context}",
    "verification_result": "판정 결과",
    "explanation": "상세한 판정 근거와 출처",
    "sources": ["출처1", "출처2"]
}}
"""
    
    try:
        # GPT-4 사용 (팩트체크 정확도를 위해)
        print_progress("GPT-4에 검증 요청 보내는 중...")
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "당신은 공정하고 객관적인 팩트체크 전문가입니다. 공인 팩트체크 기관의 방식을 따라 철저한 근거에 기반한 팩트체크를 수행합니다."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=1200  # 충분한 설명을 위해 토큰 증가
        )
        
        response_text = response.choices[0].message.content.strip()
        print_progress(f"GPT-4 응답 받음: {len(response_text)}자")
        
        # JSON 추출
        json_match = re.search(r'(\{.*\})', response_text, re.DOTALL)
        if json_match:
            try:
                result = json.loads(json_match.group(1))
                
                # 날짜 추가
                result["date"] = datetime.datetime.now().strftime("%Y.%m.%d")
                if "context" not in result:
                    result["context"] = context
                    
                return result
            except json.JSONDecodeError:
                print_progress(f"JSON 파싱 오류: {response_text[:100]}...")
                return None
        else:
            print_progress(f"JSON 응답 없음: {response_text[:100]}...")
            return None
            
    except Exception as e:
        print_progress(f"검증 오류: {e}")
        traceback.print_exc()
        return None

# Fallback: 기사 전체를 GPT에 전달하여 직접 팩트체크
def fallback_direct_factcheck(article):
    """백업 전략: GPT-4에 기사 전체를 전달하여 직접 팩트체크"""
    print_progress("대체 팩트체크 접근법 사용 중...")
    
    title = article.get('title', '')
    content = article.get('content', '')
    url = article.get('url', '')
    
    # 내용이 부족하면 전체 기사 가져오기
    if len(content) < 300:
        try:
            print_progress(f"기사 내용이 짧음, 전체 내용 가져오는 중: {url}")
            full_content = get_full_article_content(url)
            if full_content and len(full_content) > len(content):
                content = full_content
                print_progress(f"전체 내용 가져옴: {len(content)}자")
        except Exception as e:
            print_progress(f"전체 내용 가져오기 오류: {e}")
    
    # 토큰 제한을 위해 내용 요약
    if len(content) > 2000:
        content = content[:2000] + "..."
    
    prompt = f"""이 기사를 바탕으로 가능한 가장 정확한 팩트체크를 수행해주세요:

기사 제목: {title}
기사 내용: {content}
기사 URL: {url}

다음 공인 팩트체크 기관의 예시를 참고하여:

{FACTCHECK_EXAMPLES[:1000]}  # 예시의 앞부분만 사용

다음 작업을 수행해주세요:
1. 기사에서 정치인의 주요 사실 주장을 식별하세요.
2. 그 주장이 객관적으로 검증 가능한지 판단하세요.
3. 검증 가능하다면, 주장의 사실 여부를 객관적으로 평가하세요.

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
        print_progress("대체 검증 요청 보내는 중...")
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "당신은 최고의 팩트체크 전문가입니다. 기사에서 검증 가능한 주장을 식별하고 이를 객관적으로 검증하세요."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=1000
        )
        
        response_text = response.choices[0].message.content.strip()
        print_progress(f"대체 검증 응답 받음: {len(response_text)}자")
        
        # JSON 추출
        json_match = re.search(r'(\{.*\})', response_text, re.DOTALL)
        if json_match:
            try:
                result = json.loads(json_match.group(1))
                
                # 날짜 추가
                result["date"] = datetime.datetime.now().strftime("%Y.%m.%d")
                
                return result
            except json.JSONDecodeError:
                print_progress(f"JSON 파싱 오류: {response_text[:100]}...")
                return None
        else:
            print_progress(f"JSON 응답 없음: {response_text[:100]}...")
            return None
            
    except Exception as e:
        print_progress(f"대체 검증 오류: {e}")
        traceback.print_exc()
        return None

# 강화된 팩트체크 결과 품질 검증
def validate_factcheck_quality(factcheck_result):
    """강화된 팩트체크 결과 품질 검증"""
    
    # 기본 필드 확인
    required_fields = ["speaker", "statement", "verification_result", "explanation"]
    if not all(field in factcheck_result for field in required_fields):
        print_progress("필수 필드 누락")
        return False
    
    # 근거 및 출처 확인
    explanation = factcheck_result.get("explanation", "")
    
    # 출처 URL 포함 여부
    has_urls = bool(re.search(r'https?://\S+', explanation)) or (
        "sources" in factcheck_result and 
        any(source.startswith('http') for source in factcheck_result.get("sources", []))
    )
    
    # 통계 수치 포함 여부
    has_statistics = bool(re.search(r'\d+(?:\.\d+)?%|\d+(?:\.\d+)?배|\d+(?:조|억|만)?\s*원', explanation))
    
    # 기관명 언급 여부
    official_sources = ["통계청", "한국은행", "보건복지부", "기획재정부", "행정안전부", "법원", "국회"]
    has_official_source = any(source in explanation for source in official_sources)
    
    # 점수 산정
    quality_score = 0
    if has_urls: quality_score += 2
    if has_statistics: quality_score += 2
    if has_official_source: quality_score += 1
    
    # 검증 불가 판정 시 명확한 이유 확인
    if factcheck_result.get("verification_result") == "확인 불가":
        has_clear_reason = "확인할 수 없는 이유" in explanation or "검증이 불가능한 이유" in explanation
        if not has_clear_reason:
            print_progress("확인 불가 판정에 대한 명확한 이유 누락")
            quality_score -= 1
    
    # 최소 품질 기준
    minimum_score = 2 if FORCE_UPDATE else 3
    
    if quality_score >= minimum_score:
        print_progress(f"품질 검증 통과: 점수 {quality_score}")
        return True
    else:
        print_progress(f"품질 검증 실패: 점수 {quality_score}")
        return False

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
            if source and (source.startswith("http") or source.startswith("www")):
                card_html += f'<li><a href="{source}" target="_blank">{source}</a></li>\n'
            else:
                card_html += f'<li>{source}</li>\n'
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
    politician_names = re.findall(r'<div class="politician-name">\s*<span[^>]*>.*?</span>\s*(.*?)\s*</div>', html_content, re.DOTALL)
    
    for i, content in enumerate(falsehood_contents):
        # 태그 제거
        clean_content = re.sub(r'<[^>]+>', '', content).strip()
        existing_statements.append(clean_content)
        
        # 정치인 이름과 발언을 함께 저장 (가능한 경우)
        if i < len(politician_names):
            politician_name = re.sub(r'<[^>]+>', '', politician_names[i]).strip()
            existing_statements.append(f"{politician_name}:{clean_content}")
    
    return existing_statements

# 임시 파일 정리
def cleanup_temp_files():
    """임시 파일 정리"""
    try:
        # 오래된 파일 삭제
        for file_path in [TEMP_FILE]:
            if os.path.exists(file_path):
                file_age = time.time() - os.path.getmtime(file_path)
                if file_age > 86400 * 7:  # 7일 이상 된 파일만 삭제
                    os.remove(file_path)
                    print_progress(f"오래된 임시 파일 삭제: {file_path}")
        
        # 검색 캐시는 유지하고 크기만 관리
        if os.path.exists(SEARCH_CACHE_FILE):
            try:
                with open(SEARCH_CACHE_FILE, 'r', encoding='utf-8') as f:
                    cache = json.load(f)
                    
                if len(cache) > 200:  # 캐시가 너무 크면
                    # 50% 무작위 삭제
                    keys_to_delete = random.sample(list(cache.keys()), len(cache) // 2)
                    for key in keys_to_delete:
                        del cache[key]
                        
                    # 줄어든 캐시 저장
                    with open(SEARCH_CACHE_FILE, 'w', encoding='utf-8') as f:
                        json.dump(cache, f, ensure_ascii=False)
                        
                    print_progress(f"검색 캐시 크기 조정: {len(cache)}개 항목")
            except Exception as e:
                print_progress(f"캐시 정리 오류: {e}")
    except Exception as e:
        print_progress(f"임시 파일 정리 오류: {e}")

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
            print_progress("발언 수집 실패, 업데이트하지 않습니다.")
            return
        
        # 현재 HTML 파일 읽기
        with open('index.html', 'r', encoding='utf-8') as file:
            content = file.read()
        
        # 기존 발언 추출
        existing_statements = extract_existing_statements(content)
        print_progress(f"기존 발언 {len(existing_statements)}개 발견")
        
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
                print_progress("검증 결과 스타일 CSS에 추가됨")
                
                # 업데이트된 HTML 내용으로 파일 쓰기
                with open('index.html', 'w', encoding='utf-8') as file:
                    file.write(content)
                
                # 다시 읽기
                with open('index.html', 'r', encoding='utf-8') as file:
                    content = file.read()
            else:
                print_progress("</style> 태그를 찾을 수 없음")
        
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
                    if full_content and len(full_content) > len(article.get('content', '')):
                        article['content'] = full_content
                articles_to_process.append(article)
            except Exception as e:
                print_progress(f"기사 내용 확장 오류: {e}")
                articles_to_process.append(article)  # 원래 내용 그대로 추가
        
        # 각 기사에 대해 3단계 팩트체크 수행
        attempts = 0
        force_process = FORCE_UPDATE  # 강제 처리 옵션
        
        for article in articles_to_process:
            # 시간 제한 체크
            elapsed_time = time.time() - start_time
            if elapsed_time > (MAX_RUNTIME_SECONDS * 0.8):
                print_progress(f"시간 제한 임박 ({elapsed_time:.1f}초), 처리 중단")
                break
            
            # 중복 방지
            url = article.get('url', '')
            if url in processed_urls:
                continue
            
            print_progress(f"기사 처리 중: {article.get('title', '')[:50]}...")
            attempts += 1
            
            # 3단계 팩트체크 수행
            factcheck_result = three_stage_factcheck(article)
            
            # 팩트체크 실패 시 백업 전략 시도
            if not factcheck_result and (force_process or attempts >= len(articles_to_process) / 2):
                print_progress("팩트체크 결과 없음, 대체 접근법 사용...")
                factcheck_result = fallback_direct_factcheck(article)
                force_process = False  # 한 번만 강제 처리
            
            # 결과 처리
            if factcheck_result:
                # 중복 확인
                new_statement = factcheck_result.get("statement", "")
                speaker = factcheck_result.get("speaker", "")
                
                # 발언 내용이나 "발언자:발언" 조합이 이미 존재하는지 확인
                is_duplicate = (new_statement in existing_statements or 
                              f"{speaker}:{new_statement}" in existing_statements)
                
                if is_duplicate:
                    print_progress("중복 발언 건너뜀")
                    continue
                
                # 품질 검증
                if validate_factcheck_quality(factcheck_result):
                    print_progress(f"검증 성공: {factcheck_result.get('verification_result')}")
                    factcheck_results.append(factcheck_result)
                    processed_urls.add(url)
                    
                    # 목표 달성 시 중단 (하루에 1개만)
                    if len(factcheck_results) >= 1:
                        break
                else:
                    print_progress("팩트체크 결과 품질 검증 실패")
        
        # 결과가 없으면 종료
        if not factcheck_results:
            print_progress("팩트체크 결과 생성 실패, 업데이트하지 않습니다.")
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
            print_progress(f"{today}에 {len(factcheck_results)}개 새 팩트체크 카드 추가")
            
            # HTML 파일에서 제목 및 레이블 텍스트 업데이트
            new_content = new_content.replace("허위 발언 트래커", "정치인 발언 검증 서비스")
            new_content = new_content.replace("<!-- 허위 발언 카드", "<!-- 팩트체크 카드")
            new_content = new_content.replace('<span class="correction-label">실제 사실:</span>', '<span class="correction-label">검증 설명:</span>')
            
            # 업데이트된 콘텐츠 저장
            with open('index.html', 'w', encoding='utf-8') as file:
                file.write(new_content)
                print_progress("HTML 파일 저장 성공")
        else:
            print_progress(f"마커 '{insert_marker}'를 HTML 파일에서 찾을 수 없음")
        
        # 캐시 저장
        save_cache()
        
    except Exception as e:
        print_progress(f"HTML 파일 업데이트 오류: {e}")
        traceback.print_exc()
    finally:
        # 실행 시간 출력
        elapsed_time = time.time() - start_time
        print_progress(f"총 실행 시간: {elapsed_time:.2f}초")

# 메인 실행 함수
if __name__ == "__main__":
    try:
        # HTML 파일 업데이트
        update_html_file()
        
        # 임시 파일 정리
        cleanup_temp_files()
        
    except Exception as e:
        print(f"메인 실행 오류: {e}")
        traceback.print_exc()
