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
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 모든 발언 카드 찾기
    cards = soup.select('.falsehood-card')
    
    for card in cards:
        # 발언 내용 추출
        statement_content = card.select_one('.falsehood-content')
        if statement_content:
            statement_text = statement_content.get_text(strip=True)
            existing_statements.append(statement_text)
            
        # 발언자 이름 추출 (선택적)
        politician_name_elem = card.select_one('.politician-name')
        if politician_name_elem:
            politician_name = politician_name_elem.get_text(strip=True)
            # politician_statement 형식으로 저장하여 동일 발언자의 다른 발언은 허용
            politician_statement = f"{politician_name}:{statement_text}"
            existing_statements.append(politician_statement)
    
    return existing_statements

# 팩트체크 가능한 발언인지 판단하는 함수
def is_factcheckable_statement(title, content=""):
    # 팩트체크가 어려운 유형의 발언 키워드
    non_factcheckable = [
        "공약", "추진", "계획", "예정", "방침", "의견", "생각", "제안", "구상", 
        "육성", "메가시티", "허브", "하겠다", "예정", "추진할", "추진하겠"
    ]
    
    # 사실 주장에 가까운 키워드
    factcheckable = [
        "통계", "수치", "증가", "감소", "상승", "하락", "확인", "발표", "보고", 
        "조사", "결과", "사실", "주장", "밝혔", "입증", "지적"
    ]
    
    full_text = title + " " + content
    
    # 팩트체크가 어려운 내용 포함 여부
    for term in non_factcheckable:
        if term in full_text:
            print(f"Statement contains non-factcheckable term: {term}")
            return False
    
    # 사실 주장 키워드가 하나라도 있는지 확인
    has_factcheckable = any(term in full_text for term in factcheckable)
    
    if not has_factcheckable:
        print(f"Statement lacks factcheckable keywords")
        return False
    
    return True

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
            
            for entry in feed.entries[:30]:  # 각 피드에서 최대 30개 항목 확인
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
    prompt = """다음 정치인 발언의 사실 여부를 검증해주세요.

    중요 지침:
    1. 이 발언이 팩트체크 대상인지 먼저 판단하세요. 다음은 팩트체크 대상이 아닙니다:
       - 미래 계획/공약/정책 제안 ("5대 권역 메가시티를 육성하겠다" 등)
       - 주관적 의견이나 가치 판단
       - "하겠다", "추진할 것" 등 미래형 서술
    
    2. 팩트체크 대상이 아니면 반드시 is_factcheckable을 false로 설정하고 설명에 그 이유를 밝혀주세요.
    
    3. 팩트체크 대상인 경우에만:
       - 객관적인 사실과 통계를 바탕으로 검증하세요
       - 가능한 구체적인 수치와 출처를 포함하세요
    
    발언: "{statement_text}"
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
        "statement": "원본 발언",
        "is_factcheckable": true/false,
        "explanation": "실제 사실에 대한 설명"
    }}
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
            required_keys = ["politician", "party", "context", "statement", "explanation", "is_factcheckable"]
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
                        result[key] = "이 발언의 사실 관계를 검증하기 위해서는 추가적인 자료와 맥락이 필요합니다."
                    elif key == "is_factcheckable":
                        result[key] = True  # 기본값은 팩트체크 가능으로 설정
            
            # 정당 정보가 비어있거나 확인 필요인 경우
            if not result.get("party") or result["party"] == "확인 필요":
                result["party"] = party or "무소속"
                
            # 현재 날짜 추가
            result["date"] = datetime.datetime.now().strftime("%Y.%m.%d")
            
            # 팩트체크 가능 여부가 명시적으로 false인 경우
            if "is_factcheckable" in result and result["is_factcheckable"] == False:
                print(f"GPT determined statement is not factcheckable: {statement_text}")
                return None
                
            return result
        except json.JSONDecodeError as e:
            print(f"Failed to parse JSON: {e}")
            print(f"Raw response: {response.choices[0].message.content}")
            
            # JSON 파싱 실패 시 기본 응답 생성
            return {
                "politician": improved_name,
                "party": party or "무소속",
                "context": context,
                "statement": statement_text,
                "explanation": "이 발언의 사실 관계를 검증하기 위해서는 추가적인 자료와 맥락이 필요합니다.",
                "is_factcheckable": True,
                "date": datetime.datetime.now().strftime("%Y.%m.%d")
            }
    except Exception as e:
        print(f"Error fact-checking statement: {e}")
        # 예외 발생 시 기본 응답 생성
        return {
            "politician": improved_name,
            "party": party or "무소속",
            "context": context,
            "statement": statement_text,
            "explanation": "이 발언의 사실 관계를 검증하기 위해서는 추가적인 자료와 맥락이 필요합니다.",
            "is_factcheckable": True,
            "date": datetime.datetime.now().strftime("%Y.%m.%d")
        }

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
    else:
        party_class = "ppp-indicator"  # 기본값
        avatar_class = "ppp-avatar"
    
    # 정치인 이름의 첫 글자 추출
    first_letter = fact_check["politician"][0] if fact_check["politician"] else "?"
    
    # HTML 카드 생성 (문자열 처리 단순화)
    card_html = "<!-- 허위 발언 카드 -->\n"
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
    card_html += '<div class="falsehood-source">\n'
    card_html += f'<i class="fas fa-bullhorn"></i> {fact_check["context"]}\n'
    card_html += '</div>\n'
    card_html += '<div class="falsehood-content">\n'
    card_html += f'{fact_check["statement"]}\n'
    card_html += '</div>\n'
    card_html += '<div class="falsehood-correction">\n'
    card_html += '<span class="correction-label">실제 사실:</span>\n'
    card_html += f'{fact_check["explanation"]}\n'
    card_html += '</div>\n'
    card_html += '</div>\n'
    
    return card_html

# HTML 파일 업데이트 - 중복 방지 로직 추가
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
        existing_statements = extract_existing_statements(content)
        print(f"Found {len(existing_statements)} existing statements")
        
        # 처리된 카드 수와 HTML 저장
        all_cards_html = ""
        processed_cards = 0
        
        # 중복 방지를 위한 임시 저장소
        processed_statements = set()
        
        # 랜덤으로 발언을 선택하여 팩트체크
        random.shuffle(statements)
        max_cards = min(3, len(statements))  # 최대 3개, 수집된 발언이 3개 미만이면 해당 개수만큼
        
        for statement in statements:
            if processed_cards >= max_cards:
                break
            
            # 중복 체크 - 이미 HTML에 있는 발언인지 확인
            if statement['title'] in existing_statements:
                print(f"Skipping duplicate statement: {statement['title']}")
                continue
                
            # 추가 중복 체크 - 이미 이번 실행에서 처리한 발언인지 확인
            if statement['title'] in processed_statements:
                print(f"Skipping statement already processed in this run: {statement['title']}")
                continue
            
            # 팩트체크 대상인지 한번 더 확인 (이미 collect_politician_statements()에서 필터링했지만 안전을 위해)
            if not is_factcheckable_statement(statement['title'], statement.get('content', '')):
                print(f"Skipping non-factcheckable statement: {statement['title']}")
                continue
                
            # 발언 팩트체크
            fact_check = fact_check_statement(statement)
            
            # GPT가 팩트체크 불가능하다고 판단했거나 오류가 발생한 경우
            if not fact_check:
                print(f"Skipping statement due to fact check failure: {statement['title']}")
                continue
                
            # 허위발언카드 HTML 생성
            card_html = generate_fact_check_card_html(fact_check)
            all_cards_html += card_html
            
            # 이번에 처리한 발언 기록
            processed_statements.add(statement['title'])
            processed_cards += 1
            
            print(f"Processed card {processed_cards}/{max_cards}: {fact_check['statement']}")
        
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
