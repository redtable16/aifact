import os
import json
import random
import datetime
import requests
from bs4 import BeautifulSoup
import openai

# 최신 뉴스 기사에서 정치인 발언 추출
def collect_politician_statements():
    # 주요 뉴스 사이트 목록
    news_sites = [
        "https://www.yna.co.kr/politics",
        "https://news.naver.com/main/main.naver?mode=LSD&mid=shm&sid1=100",
        "https://news.naver.com/main/politics/index.naver"
    ]
    
    statements = []
    
    # 웹에서 데이터 수집 시도
    for site in news_sites:
        try:
            response = requests.get(site, headers={"User-Agent": "Mozilla/5.0"})
            print(f"Fetching {site}, status code: {response.status_code}")
            # 응답 일부 출력하여 확인
            print(f"Response preview: {response.text[:200]}...")
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 각 뉴스 사이트에 맞는 선택자 사용 (예시)
            if "yna.co.kr" in site:
                # 여러 가능한 선택자 시도
                articles = soup.select(".item-box") or soup.select("div.item") or soup.select("div.news-item")
                print(f"Found {len(articles)} articles on YNA")
                
                for article in articles[:5]:  # 상위 5개 기사만
                    title_elem = article.select_one(".tit-news") or article.select_one("strong.title") or article.select_one("h2")
                    if title_elem:
                        title = title_elem.text.strip()
                        link_elem = article.select_one("a")
                        if link_elem and "href" in link_elem.attrs:
                            link = link_elem["href"]
                            if "http" not in link:
                                link = "https://www.yna.co.kr" + link
                            statements.append({"title": title, "url": link})
            
            elif "naver.com" in site:
                # 여러 가능한 선택자 시도
                articles = soup.select(".sh_item") or soup.select(".news_wrap") or soup.select("ul.type06_headline li")
                print(f"Found {len(articles)} articles on Naver")
                
                for article in articles[:5]:
                    title_elem = article.select_one(".sh_text_headline") or article.select_one("a.news_tit") or article.select_one("dt a")
                    if title_elem:
                        title = title_elem.text.strip()
                        link = title_elem["href"] if "href" in title_elem.attrs else None
                        if link:
                            statements.append({"title": title, "url": link})
        
        except Exception as e:
            print(f"Error scraping {site}: {e}")
    
    # 수집된 데이터가 없으면 테스트 데이터 사용
    if not statements:
        print("Using test data instead...")
        statements = [
            {"title": "윤석열 대통령, 인공지능 산업 육성 위해 5조원 투자 발표", "url": "https://example.com/news1"},
            {"title": "이재명 대표, 경제 위기 극복 위한 10대 정책 제안", "url": "https://example.com/news2"},
            {"title": "홍준표 의원, 지방 분권 확대 주장하며 개헌 필요성 강조", "url": "https://example.com/news3"},
            {"title": "국회의장, 여야 대치 상황 중재 나서", "url": "https://example.com/news4"},
            {"title": "더불어민주당, 민생 법안 처리 촉구 기자회견 개최", "url": "https://example.com/news5"},
            {"title": "국민의힘 대표, 민주당의 법안 지연 전략 비판", "url": "https://example.com/news6"}
        ]
    
    print(f"Total statements collected: {len(statements)}")
    return statements

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
        # 새로운 버전 코드:
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a fact-checking expert for Korean political statements."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
        
        result = json.loads(response.choices[0].message.content)
        result["date"] = datetime.datetime.now().strftime("%Y.%m.%d")
        return result
    
    except Exception as e:
        print(f"Error fact-checking statement: {e}")
        return None

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

if __name__ == "__main__":
    update_html_file()
