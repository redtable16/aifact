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
                    print(f"  Skipping older article: {entry.title}")
                    continue
                
                title = entry.title
                
                # 기본 정보 추출
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
                        statement_data["content"] = article_content[:800]  # 처음 800자만 저장
                    else:
                        print(f"  No content extracted for: {title}")
                        continue  # 내용이 없으면 건너뛰기
                except Exception as e:
                    print(f"  Error fetching article content: {e}")
                    continue  # 내용 추출 실패 시 건너뛰기
                
                # 1단계: 모든 정치 관련 기사 수집
                all_statements.append(statement_data)
                
                # 2단계: 정치인 발언 필터링
                if is_politician_statement(title, article_content):
                    # 중복 발언 검사
                    is_duplicate = False
                    for existing_statement in politician_statements:
                        if is_similar_statement(statement_data, existing_statement):
                            print(f"  Skipping duplicate politician statement: {title}")
                            is_duplicate = True
                            break
                    
                    if not is_duplicate:
                        politician_statements.append(statement_data)
                        print(f"  Found politician statement: {title}")
                        
                        # 3단계: 팩트체크 가능한 발언 필터링
                        if is_factcheckable_statement(title, article_content):
                            # 중복 팩트체크 발언 검사
                            is_factcheck_duplicate = False
                            for existing_statement in factcheckable_statements:
                                if is_similar_statement(statement_data, existing_statement):
                                    print(f"  Skipping duplicate factcheckable statement: {title}")
                                    is_factcheck_duplicate = True
                                    break
                                
                            if not is_factcheck_duplicate:
                                factcheckable_statements.append(statement_data)
                                print(f"  Found factcheckable statement: {title}")
        
        except Exception as e:
            print(f"Error processing feed {feed_url}: {e}")
        
        # 요청 간 간격 두기
        time.sleep(1)
    
    # 중복 제거 함수
    def deduplicate(statements):
        unique_statements = []
        urls = set()
        for statement in statements:
            if statement["url"] not in urls:
                urls.add(statement["url"])
                unique_statements.append(statement)
        return unique_statements
    
    # URL 기반 중복 제거 적용
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
        print("Not enough factcheckable statements. Using general politician statements.")
        return politician_statements
    elif len(all_statements) >= 2:
        print("Not enough politician statements. Using all political articles.")
        return all_statements
    else:
        print("No suitable articles found in the last 24 hours.")
        return []

# 텍스트 유사도를 확인하는 함수
def is_similar_statement(statement1, statement2, threshold=0.6):
    # 실제 발언자 추출
    real_speaker1 = extract_real_speaker(statement1['title'], statement1.get('content', ''))
    real_speaker2 = extract_real_speaker(statement2['title'], statement2.get('content', ''))
    
    # 다른 사람의 발언이면 유사하지 않음
    if real_speaker1 and real_speaker2 and real_speaker1 != real_speaker2:
        return False
    
    # 제목 비교
    title1 = statement1['title']
    title2 = statement2['title']
    
    # 간단한 텍스트 유사도 확인 (공통 단어 비율)
    words1 = set(title1.split())
    words2 = set(title2.split())
    
    if not words1 or not words2:
        return False
    
    # 교집합 크기 / 합집합 크기 = 자카드 유사도
    similarity = len(words1.intersection(words2)) / len(words1.union(words2))
    
    return similarity >= threshold

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
    
    # 인용부호 확인 (인용부호가 있으면 발언일 가능성 높음)
    has_quote = '"' in title or "'" in title or """ in title or "'" in title
    
    # 정치인 이름이 포함되어 있는지 확인
    has_politician = any(politician in full_text for politician in politicians)
    
    # 발언 관련 키워드가 포함되어 있는지 확인
    has_keyword = any(keyword in full_text for keyword in keywords)
    
    # 정치인 이름과 발언 관련 키워드가 모두 포함되어 있거나, 인용부호가 있으면 정치인 발언으로 간주
    return (has_politician and has_keyword) or (has_politician and has_quote)

# 팩트체크 가능한 발언인지 확인
def is_factcheckable_statement(title, content=""):
    # 수치, 통계 또는 구체적인 사실 주장이 포함된 제목 필터링
    number_patterns = [
        r'\d+%', r'\d+조', r'\d+억', r'\d+만', r'\d+명',  # 퍼센트, 금액, 인원수
        r'\d+배', r'\d+위', r'\d+등', r'\d+번째'          # 배수, 순위
    ]
    
    # 전체 텍스트 검색
    full_text = title + " " + content
    
    # 수치나 통계가 포함되어 있는지 확인
    has_numbers = any(re.search(pattern, full_text) for pattern in number_patterns)
    
    # 팩트체크 가능한 키워드 포함 여부
    factcheck_keywords = [
        "증가", "감소", "최고", "최저", "최초", "사상 처음", "역대 최대", "역대 최저",
        "전액", "전부", "모두", "유일", "유일하게", "전체", "완전히", "절대",
        "가장", "최고", "처음으로", "처음", "사실상", "실질적", "사실이", "실제로"
    ]
    
    has_factcheck_keywords = any(keyword in full_text for keyword in factcheck_keywords)
    
    # 객관적 검증이 어려운 주관적 표현
    subjective_keywords = [
        "생각", "의견", "판단", "느낌", "우려", "기대", "희망", "바람",
        "전망", "예상", "예측", "제안", "바란다", "할 것", "포부"
    ]
    
    has_subjective_keywords = any(keyword in title for keyword in subjective_keywords)
    
    # 수치/통계가 있거나 팩트체크 키워드가 있고, 주관적 표현이 없는 경우만 선택
    return (has_numbers or has_factcheck_keywords) and not has_subjective_keywords

# 제목과 내용에서 실제 발언자 추출
def extract_real_speaker(title, content=""):
    # 인용 패턴 찾기 (예: "김영선 비서 "이준석, 명태균에 쇼 프랑스대사 보내자고 제안"")
    # 패턴1: A "B가 말했다"
    quote_pattern1 = r'([가-힣]+)([\s]*)(?:비서|의원|대표|장관|총리|대통령|위원장|후보)?(?:[\s,]*)["\']([^"\']+)["\'](고|라고|며)'
    match = re.search(quote_pattern1, title)
    if match:
        # 첫 번째 그룹이 발언자
        return match.group(1)
    
    # 패턴2: "A가 말했다"고 B가 전했다
    quote_pattern2 = r'["\'](.*?)(?:라고|고)[\s]*([가-힣]+)(?:[\s]*)(?:비서|의원|대표|장관|총리|대통령|위원장|후보)?(?:가|이)[\s]*(?:전했|밝혔|말했)'
    match = re.search(quote_pattern2, title)
    if match and match.group(2):
        # 두 번째 그룹이 발언자
        return match.group(2)
    
    # 패턴3: A "B" 발언
    quote_pattern3 = r'([가-힣]+)(?:[\s]*)(?:비서|의원|대표|장관|총리|대통령|위원장|후보)?(?:[\s,]*)["\']([^"\']+)["\'](?:[\s]*)(?:발언|주장|언급)'
    match = re.search(quote_pattern3, title)
    if match:
        # 첫 번째 그룹이 발언자
        return match.group(1)
    
    # 패턴4: 기본 패턴 - 제목 시작 부분에 이름이 있으면 발언자로 간주
    basic_pattern = r'^([가-힣]{2,4})(?:[\s]*)(?:비서|의원|대표|장관|총리|대통령|위원장|후보)?(?:[\s,]*)["\']'
    match = re.search(basic_pattern, title)
    if match:
        return match.group(1)
    
    # 패턴이 매치되지 않으면 본문에서 추가 검색 시도
    if content:
        # 첫 문장에서 발언자 찾기 시도
        first_sentence_end = content.find(".")
        if first_sentence_end > 0:
            first_sentence = content[:first_sentence_end]
            for pattern in [quote_pattern1, quote_pattern2, quote_pattern3]:
                match = re.search(pattern, first_sentence)
                if match and (pattern == quote_pattern2):
                    return match.group(2)
                elif match:
                    return match.group(1)
    
    # 발언자를 찾지 못한 경우
    return None

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
    
    # 날짜를 찾지 못했으면 현재 시간 반환
    return datetime.datetime.now()

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

# GPT-4를 사용하여 발언 팩트체크
def fact_check_statement(statement):
    # 정치인 이름과 정당 추출
    statement_text = statement['title']
    content = statement.get('content', '')
    
    # 실제 발언자 추출 시도
    real_speaker = extract_real_speaker(statement_text, content)
    
    # 실제 발언자가 있으면 이를 우선 사용, 없으면 기존 방식 사용
    if real_speaker:
        politician_name = real_speaker
        _, party = extract_politician_and_party(politician_name, content)
    else:
        politician_name, party = extract_politician_and_party(statement_text, content)
    
    context = get_statement_context(statement)
    
    # 발언자 이름 개선
    improved_name = improve_politician_name(politician_name, party)
    
    # 삼중 따옴표 방식으로 prompt 작성
prompt = "다음 정치인 발언의 사실 여부를 검증해주세요. 결과는 JSON 형식으로 반환해주세요.\n\n"
prompt += f"발언: \"{statement_text}\"\n"
prompt += f"출처: {statement.get('url', '확인 필요')}\n\n"
prompt += "추가 컨텍스트:\n"
prompt += f"{content[:500] if content else '추가 정보 없음'}\n\n"
prompt += "발언자와 정당 정보:\n"
prompt += f"발언자: {improved_name if improved_name else '확인 필요'}\n"
prompt += f"정당: {party if party else '확인 필요'}\n\n"
prompt += "다음 형식의 JSON으로 응답해주세요:\n"
prompt += "{\n"
prompt += '    "politician": "발언자 이름",\n'
prompt += '    "party": "소속 정당",\n'
prompt += '    "context": "발언 상황",\n'
prompt += '    "statement": "원본 발언",\n'
prompt += '    "explanation": "실제 사실에 대한 설명"\n'
prompt += "}\n\n"
prompt += "설명은 간결하게 작성해주세요. 발언의 사실 관계를 객관적으로 검증하고, 필요한 경우 맥락을 제공해주세요.".format(
        statement_text,
        real_speaker if real_speaker else "확인 필요", 
        statement.get('url', '확인 필요'),
        content[:500] if content else '추가 정보 없음'
    )
    
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
            required_keys = ["politician", "party", "context", "statement", "explanation"]
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
            
            # 정당 정보가 비어있거나 확인 필요인 경우
            if not result.get("party") or result["party"] == "확인 필요":
                result["party"] = party or "무소속"
                
            # 현재 날짜 추가
            result["date"] = datetime.datetime.now().strftime("%Y.%m.%d")
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
            "date": datetime.datetime.now().strftime("%Y.%m.%d")
        }

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
            surrounding_text = extract_surrounding_text(content, keyword, 20)
            if surrounding_text:
                # 너무 긴 출처 정리
                if len(surrounding_text) > 30:
                    return keyword
                return surrounding_text
    
    # 발언 상황을 찾지 못한 경우 기본값
    return "언론 보도"

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
            print("No statements collected, no updates will be made.")
            return
        
        # 3개의 팩트체크 카드 생성
        num_cards = min(3, len(statements))  # 최대 3개, 수집된 발언이 3개 미만이면 해당 개수만큼
        
        all_cards_html = ""
        processed_cards = 0
        processed_statements = []  # 이미 처리된 발언 저장
        
        # 랜덤으로 발언을 선택하여 팩트체크
        random.shuffle(statements)
        
        for statement in statements:
            # 이미 유사한 발언이 처리되었는지 확인
            is_duplicate = False
            for processed in processed_statements:
                if is_similar_statement(statement, processed):
                    print(f"Skipping similar statement: {statement['title']}")
                    is_duplicate = True
                    break
                    
            if is_duplicate:
                continue
                
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
            processed_statements.append(statement)  # 처리된 발언 저장
            
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
