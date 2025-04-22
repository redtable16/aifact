import os
import json
import random
import datetime
import requests
from bs4 import BeautifulSoup
import openai
import time
import re

# 최신 뉴스 기사에서 정치인 발언 추출
def collect_politician_statements():
    print("Starting to collect politician statements...")
    
    # 다양한 뉴스 사이트 목록 확장
    news_sites = [
        # 연합뉴스 - 정치 섹션
        "https://www.yna.co.kr/politics/all",
        # 네이버 뉴스 - 정치 섹션
        "https://news.naver.com/main/list.naver?mode=LS2D&mid=shm&sid1=100&sid2=269",
        # 중앙일보 - 정치 섹션
        "https://www.joongang.co.kr/politics",
        # 경향신문 - 정치 섹션
        "https://www.khan.co.kr/politics/politics-general/articles",
        # 동아일보 - 정치 섹션
        "https://www.donga.com/news/Politics/List"
    ]
    
    # 모바일 에이전트 추가
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (iPad; CPU OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
    ]
    
    statements = []
    
    # 웹에서 데이터 수집 시도
    for site in news_sites:
        try:
            # 랜덤 사용자 에이전트 선택
            headers = {"User-Agent": random.choice(user_agents)}
            print(f"Fetching {site} with headers: {headers}")
            
            # 요청 타임아웃 설정 및 리트라이 추가
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = requests.get(site, headers=headers, timeout=10)
                    break
                except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt  # 지수 백오프
                        print(f"Attempt {attempt+1} failed: {e}. Retrying in {wait_time} seconds...")
                        time.sleep(wait_time)
                    else:
                        print(f"Failed after {max_retries} attempts: {e}")
                        raise
            
            print(f"Status code: {response.status_code}")
            
            # 인코딩 문제 처리
            if "yna.co.kr" in site:
                response.encoding = 'utf-8'
            
            # 응답 내용 로깅
            content_preview = response.text[:200].replace('\n', ' ')
            print(f"Response preview: {content_preview}...")
            
            # HTML 파싱
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 사이트별 크롤링 로직
            if "yna.co.kr" in site:
                # 연합뉴스 파싱
                articles = soup.select(".list-type038 .item-box") or soup.select(".list-type038 li") or soup.select(".section-list-related li")
                print(f"Found {len(articles)} articles on YNA")
                
                for article in articles[:8]:
                    try:
                        title_elem = article.select_one(".tit-news") or article.select_one(".tit strong") or article.select_one("strong.tit-news")
                        if title_elem:
                            title = title_elem.text.strip()
                            link_elem = article.select_one("a[href]")
                            if link_elem:
                                link = link_elem["href"]
                                if not link.startswith("http"):
                                    link = "https://www.yna.co.kr" + link
                                if is_politician_statement(title):
                                    statements.append({"title": title, "url": link})
                                    print(f"YNA Added: {title}")
                    except Exception as e:
                        print(f"Error parsing YNA article: {e}")
                        continue
                        
            elif "news.naver.com" in site:
                # 네이버뉴스 파싱
                articles = soup.select("ul.type06_headline li") or soup.select("ul.type06 li")
                print(f"Found {len(articles)} articles on Naver")
                
                for article in articles[:8]:
                    try:
                        title_elem = article.select_one("dt:not(.photo) a") or article.select_one("a.nclicks\\(fls\\.list\\)")
                        if title_elem:
                            title = title_elem.text.strip()
                            link = title_elem["href"]
                            if is_politician_statement(title):
                                statements.append({"title": title, "url": link})
                                print(f"Naver Added: {title}")
                    except Exception as e:
                        print(f"Error parsing Naver article: {e}")
                        continue
                        
            elif "joongang.co.kr" in site:
                # 중앙일보 파싱
                articles = soup.select("h2.headline a") or soup.select(".card_body h2 a")
                print(f"Found {len(articles)} articles on Joongang")
                
                for article in articles[:8]:
                    try:
                        title = article.text.strip()
                        link = article["href"]
                        if not link.startswith("http"):
                            link = "https://www.joongang.co.kr" + link
                        if is_politician_statement(title):
                            statements.append({"title": title, "url": link})
                            print(f"Joongang Added: {title}")
                    except Exception as e:
                        print(f"Error parsing Joongang article: {e}")
                        continue
                        
            elif "khan.co.kr" in site:
                # 경향신문 파싱
                articles = soup.select(".box_list_c .cr_item_thumb") or soup.select(".news_list li") or soup.select(".art_list_all li")
                print(f"Found {len(articles)} articles on Khan")
                
                for article in articles[:8]:
                    try:
                        title_elem = article.select_one(".tit a") or article.select_one("h2 a") or article.select_one("h2.tit a")
                        if title_elem:
                            title = title_elem.text.strip()
                            link = title_elem["href"]
                            if not link.startswith("http"):
                                link = "https://www.khan.co.kr" + link
                            if is_politician_statement(title):
                                statements.append({"title": title, "url": link})
                                print(f"Khan Added: {title}")
                    except Exception as e:
                        print(f"Error parsing Khan article: {e}")
                        continue
                        
            elif "donga.com" in site:
                # 동아일보 파싱
                articles = soup.select(".articleList .tit a") or soup.select("#content .articleList li")
                print(f"Found {len(articles)} articles on Donga")
                
                for article in articles[:8]:
                    try:
                        title = article.text.strip()
                        link = article["href"]
                        if is_politician_statement(title):
                            statements.append({"title": title, "url": link})
                            print(f"Donga Added: {title}")
                    except Exception as e:
                        print(f"Error parsing Donga article: {e}")
                        continue
                        
            # 요청 간 간격 두기
            time.sleep(2)  # 크롤링 간 딜레이
            
        except Exception as e:
            print(f"Error scraping {site}: {str(e)}")
    
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
    
    # 만약 수집된 데이터가 없으면 백업 데이터 사용
    if not filtered_statements:
        print("Using backup data instead...")
        filtered_statements = get_backup_statements()
    
    return filtered_statements

# 정치인 발언인지 판별하는 함수
def is_politician_statement(title):
    # 정치인 명단
    politicians = [
        "윤석열", "이재명", "홍준표", "유승민", "심상정", "안철수", "정세균", "한동훈", 
        "이낙연", "원희룡", "안철수", "조국", "박영선", "정의당", "국민의힘", "더불어민주당",
        "국회의장", "의원", "위원장", "민주당", "총리", "장관", "대표", "지사", "민주당", "윤호중"
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

# 백업 정치인 발언 데이터
def get_backup_statements():
    return [
        {"title": "윤석열 대통령, '인공지능 경쟁력 확보 위해 5년간 10조원 투자' 발표", "url": "https://example.com/news1"},
        {"title": "이재명 대표 '물가안정 위한 민생안정법 처리 시급' 주장", "url": "https://example.com/news2"},
        {"title": "한동훈 장관, '검찰개혁 완수하겠다' 국회 답변서 밝혀", "url": "https://example.com/news3"},
        {"title": "국회의장 '여야 협치로 민생법안 처리해야' 강조", "url": "https://example.com/news4"},
        {"title": "더불어민주당, '반도체 특별법 국회 통과 방해' 국민의힘 비판", "url": "https://example.com/news5"},
        {"title": "국민의힘 대표 '민주당의 무책임한 법안 지연은 국민 무시' 발언 논란", "url": "https://example.com/news6"},
        {"title": "안철수 의원 '디지털 기반 행정 혁신으로 예산 10% 절감 가능' 주장", "url": "https://example.com/news7"},
        {"title": "홍준표 의원 '지방자치 강화 없이 국가 균형발전 없다' 지적", "url": "https://example.com/news8"}
    ]

# GPT-4를 사용하여 발언 팩트체크
def fact_check_statement(statement):
    prompt = f"""
    다음 정치 발언의 사실 여부를 검증해주세요. 결과는 JSON 형식으로 반환해주세요.
    
    발언: "{statement['title']}"
    출처: {statement['url']}
    
    다음 형식의 JSON으로 응답해주세요:
    {{
        "politician": "발언자 이름",
        "party": "소속 정당",
        "context": "발언 상황",
        "statement": "원본 발언",
        "explanation": "실제 사실에 대한 설명 (100-150자)"
    }}
    """
    
    try:
        # API 키 확인용 로그 출력
        api_key = os.getenv("OPENAI_API_KEY")
        print(f"API Key available: {api_key is not None and len(api_key) > 0}")
        
        # 기사 내용 크롤링 (추가 컨텍스트 위해)
        article_content = ""
        try:
            article_response = requests.get(statement['url'], 
                                           headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"},
                                           timeout=10)
            article_soup = BeautifulSoup(article_response.text, 'html.parser')
            
            # 메타 설명이나 본문 내용 추출 시도
            meta_desc = article_soup.select_one('meta[name="description"]')
            if meta_desc and meta_desc.get('content'):
                article_content = meta_desc.get('content')
            
            # 본문 추출 시도 (사이트별 다른 선택자)
            article_body = article_soup.select_one('article') or article_soup.select_one('.article_body') or article_soup.select_one('#articleBody')
            if article_body:
                article_content += " " + article_body.get_text(strip=True)
                
            # 너무 긴 경우 자르기
            article_content = article_content[:500] + "..." if len(article_content) > 500 else article_content
            print(f"Extracted article content: {article_content[:100]}...")
            
        except Exception as e:
            print(f"Error fetching article content: {e}")
            # 계속 진행
        
        # 발언자와 정당 추출 시도
        politician_name, party = extract_politician_and_party(statement['title'], article_content)
        
        # OpenAI API 호출
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # 크롤링한 내용 프롬프트에 추가
        if article_content:
            prompt += f"\n\n추가 기사 내용: {article_content}"
            
        # 발언자, 정당 정보 추가
        if politician_name and party:
            prompt += f"\n\n참고: 기사에서 추출한 발언자 이름: {politician_name}, 소속 정당: {party}"
        
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a fact-checking expert for Korean political statements. Respond in Korean."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
        
        # API 응답 디버깅
        print(f"API response content: {response.choices[0].message.content if hasattr(response, 'choices') and response.choices else 'No content'}")
        
        # 응답 파싱 및 예외 처리
        try:
            result = json.loads(response.choices[0].message.content)
            
            # 필요한 키가 있는지 검증
            required_keys = ["politician", "party", "context", "statement", "explanation"]
            missing_keys = [key for key in required_keys if key not in result]
            
            if missing_keys:
                print(f"Missing keys in API response: {missing_keys}")
                # 누락된 키 추가
                for key in missing_keys:
                    if key == "politician" and politician_name:
                        result[key] = politician_name
                    elif key == "party" and party:
                        result[key] = party
                    elif key == "context":
                        result[key] = "기사에서 발췌한 발언"
                    elif key == "statement":
                        result[key] = statement['title']
                    elif key == "explanation":
                        result[key] = "이 발언에 대한 팩트체크가 필요합니다. 현재 검증 중입니다."
            
            # 정당 정보가 비어있는 경우
            if not result.get("party") or result["party"] == "":
                result["party"] = party or determine_party(result["politician"])
                
            # 현재 날짜 추가
            result["date"] = datetime.datetime.now().strftime("%Y.%m.%d")
            return result
        except json.JSONDecodeError as e:
            print(f"Failed to parse JSON: {e}")
            # 응답 텍스트에서 JSON 추출 시도
            json_match = re.search(r'(\{.*\})', response.choices[0].message.content, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group(1))
                    result["date"] = datetime.datetime.now().strftime("%Y.%m.%d")
                    return result
                except:
                    pass
            
            # 가공 실패 시 기본 응답 생성
            return create_default_response(statement, politician_name, party)
    
    except Exception as e:
        print(f"Error fact-checking statement: {e}")
        # 예외 발생 시 기본 응답 생성
        politician_name, party = extract_politician_and_party(statement['title'], "")
        return create_default_response(statement, politician_name, party)

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

# 정치인 이름에 기반해 정당 추정
def determine_party(politician_name):
    # 기본 정당 매핑
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
    
    # 정당명 포함 여부 확인
    if "국민의힘" in politician_name:
        return "국민의힘"
    elif "더불어민주당" in politician_name or "민주당" in politician_name:
        return "더불어민주당"
    elif "정의당" in politician_name:
        return "정의당"
    elif "조국혁신당" in politician_name:
        return "조국혁신당"
    elif "개혁신당" in politician_name:
        return "개혁신당"
    
    # 정치인 이름으로 정당 추정
    for politician, party in politician_party_map.items():
        if politician in politician_name:
            return party
    
    return "무소속"  # 정당을 추정할 수 없는 경우

# 기본 응답 생성
def create_default_response(statement, politician_name=None, party=None):
    # 발언에서 정치인 추출
    if not politician_name:
        for name in ["윤석열", "이재명", "홍준표", "심상정", "안철수", "조국", "한동훈"]:
            if name in statement['title']:
                politician_name = name
                break
        
        if not politician_name:
            if "민주당" in statement['title']:
                politician_name = "더불어민주당 대표"
                party = "더불어민주당"
            elif "국민의힘" in statement['title']:
                politician_name = "국민의힘 대표"
                party = "국민의힘"
            elif "정의당" in statement['title']:
                politician_name = "정의당 대표"
                party = "정의당"
            else:
                politician_name = "정치인"
    
    # 정당 할당
    if not party:
        party = determine_party(politician_name)
    
    # 기본 응답 생성
    return {
        "politician": politician_name or "정치인",
        "party": party or "무소속",
        "context": "기사에서 발췌한 발언",
        "statement": statement['title'],
        "explanation": "이 발언은 완전한 팩트체크가 필요합니다. 해당 발언의 사실 관계를 검증하기 위해 추가적인 자료와 분석이 필요합니다.",
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

if __name__ == "__main__":
    update_html_file()
