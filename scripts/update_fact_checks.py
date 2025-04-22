import os
import json
import random
import datetime
import requests
from bs4 import BeautifulSoup
import openai

# OpenAI API 설정
openai.api_key = os.getenv("OPENAI_API_KEY")

# 최신 뉴스 기사에서 정치인 발언 추출
def collect_politician_statements():
    # 주요 뉴스 사이트 목록
    news_sites = [
        "https://www.yna.co.kr/politics",
        "https://news.naver.com/main/main.naver?mode=LSD&mid=shm&sid1=100"
    ]
    
    statements = []
    
    for site in news_sites:
        try:
            response = requests.get(site, headers={"User-Agent": "Mozilla/5.0"})
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 각 뉴스 사이트에 맞는 선택자 사용 (예시)
            if "yna.co.kr" in site:
                articles = soup.select(".item-box")
                for article in articles[:5]:  # 상위 5개 기사만
                    title = article.select_one(".tit-news").text.strip()
                    link = article.select_one("a")["href"]
                    if "http" not in link:
                        link = "https://www.yna.co.kr" + link
                    statements.append({"title": title, "url": link})
            
            elif "naver.com" in site:
                articles = soup.select(".sh_item")
                for article in articles[:5]:
                    title = article.select_one(".sh_text_headline").text.strip()
                    link = article.select_one(".sh_text_headline")["href"]
                    statements.append({"title": title, "url": link})
        
        except Exception as e:
            print(f"Error scraping {site}: {e}")
    
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
        response = openai.ChatCompletion.create(
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
    
    # 새 카드를 추가할 위치 찾기 (<!-- FACT_CHECK_CARDS --> 주석 다음)
    insert_marker = "<!-- FACT_CHECK_CARDS -->"
    if insert_marker in content:
        new_content = content.replace(insert_marker, f"{insert_marker}\n{all_cards_html}")
        
        # 마지막 업데이트 날짜 갱신
        today = datetime.datetime.now().strftime("%Y.%m.%d")
        print(f"Added {processed_cards} new fact check cards on {today}")
        
        # 업데이트된 콘텐츠 저장
        with open('index.html', 'w', encoding='utf-8') as file:
            file.write(new_content)
    else:
        print("Could not find marker <!-- FACT_CHECK_CARDS --> in the HTML file")

if __name__ == "__main__":
    update_html_file()
