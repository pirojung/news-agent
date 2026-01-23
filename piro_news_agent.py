import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta, timezone
import difflib

# ================= 1. 설정값 (직접 수정 필요) =================
NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID") 
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")
KEYWORD = "kt" 

EMAIL_SENDER = "pirojung@gmail.com"  
EMAIL_APP_PWD = os.getenv("EMAIL_APP_PWD") 
EMAIL_RECEIVER = "po.jung@kt.com"

# [추가] 제외하고 싶은 스포츠/연예 관련 키워드 목록
# 1. 제목에 포함되면 무조건 제외할 단어들 (스포츠, 게임, 연예 일반 용어 추가)
EXCLUDE_KEYWORDS = [
    "위즈", "소닉붐", "롤스터", "LCK", "e스포츠", "T1", "젠지", "디플러스", # KT 스포츠단 및 e스포츠
    "야구", "농구", "축구", "프로농구", "KBO", "KBL", # 종목
    "연승", "연패", "감독", "선수", "득점", "홈런", "역전", "더비", # 스포츠 용어
    "연예", "방송", "드라마", "예능", "시청률", "출연", "가수", "배우", "아이돌", "Genie" # 연예 용어
]

# 2. URL에 포함되면 무조건 제외할 도메인 (스포츠/연예/게임 전문 매체)
EXCLUDE_SITES = [
    "sports", "entertain", "basketkorea", "jumpball", "rookie", # 스포츠/농구
    "inven", "fomos", "game", "thisisgame", # 게임/e스포츠
    "spotv", "xports", "osen", "stardaily", "joynews", "tvreport" # 스포츠/연예 전문지
]

# ============================================================

def is_similar(title1, title2):
    return difflib.SequenceMatcher(None, title1, title2).ratio()

def get_filtered_news():
    url = "https://openapi.naver.com/v1/search/news.json"
    headers = {"X-Naver-Client-Id": NAVER_CLIENT_ID, "X-Naver-Client-Secret": NAVER_CLIENT_SECRET}
    params = {'query': KEYWORD, 'display': 100, 'sort': 'date'} 
    
    response = requests.get(url, headers=headers, params=params, verify=False)
    
    if response.status_code != 200:
        return []

    data = response.json()
    now = datetime.now(timezone(timedelta(hours=9)))
    time_limit = now - timedelta(hours=24)
    
    recent_news = []
    accepted_titles = []

    for item in data['items']:
        pub_date = datetime.strptime(item['pubDate'], "%a, %d %b %Y %H:%M:%S %z")
        if pub_date < time_limit:
            continue

        clean_title = item['title'].replace('<b>', '').replace('</b>', '').replace('&quot;', '"').strip()
        link = item['originallink'] or item['link']

        # [수정 2] URL 도메인 및 강화된 키워드 필터링 동시 적용
        is_unwanted = False
        
        # 1. 사이트 검사: EXCLUDE_SITES 목록에 있는 단어가 URL에 포함되어 있는가?
        if any(site in link.lower() for site in EXCLUDE_SITES):
            is_unwanted = True
        # 2. 제목 검사: EXCLUDE_KEYWORDS 목록의 단어가 제목에 포함되어 있는가?
        elif any(kw in clean_title for kw in EXCLUDE_KEYWORDS):
            is_unwanted = True
            
        if is_unwanted:
            continue # 스포츠/연예 기사 패스
        
        # 중복 기사 제외
        is_duplicate = False
        for existing_title in accepted_titles:
            if is_similar(clean_title, existing_title) > 0.65:
                is_duplicate = True
                break
        
        if not is_duplicate:
            item['clean_title'] = clean_title 
            recent_news.append(item)
            accepted_titles.append(clean_title)

    return recent_news

def send_email(news_list):
    if not news_list:
        print("새로운 뉴스가 없어 메일을 발송하지 않습니다.")
        return

    subject = f"[NewsAgent] 오늘의 '{KEYWORD}' IT/비즈 핵심 뉴스 ({len(news_list)}건)"
    html_content = f"""
    <html>
    <body>
        <h2>📰 [{KEYWORD}] 24시간 IT/비즈 핵심 뉴스 브리핑</h2>
        <p style="color:gray;">스포츠 및 연예 기사와 중복이 제거된 최신 뉴스 {len(news_list)}건입니다.</p>
        <hr>
        <ul>
    """
    
    for item in news_list[:len(news_list)]: 
        link = item['originallink'] or item['link']
        desc = item['description'].replace('<b>', '').replace('</b>', '')
        html_content += f"<li><b><a href='{link}' target='_blank' style='text-decoration:none; color:#1a0dab; font-size:16px;'>{item['clean_title']}</a></b><br>"
        html_content += f"<span style='font-size:13px; color:#555;'>{desc}...</span><br><br></li>"

    html_content += "</ul></body></html>"

    msg = MIMEMultipart()
    msg['From'] = EMAIL_SENDER
    msg['To'] = EMAIL_RECEIVER
    msg['Subject'] = subject
    msg.attach(MIMEText(html_content, 'html'))

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(EMAIL_SENDER, EMAIL_APP_PWD)
            server.send_message(msg)
        print("✅ 이메일 발송 성공! 메일함을 확인해주세요.")
    except Exception as e:
        print(f"❌ 이메일 발송 실패: {e}")

if __name__ == "__main__":
    print("뉴스 수집 및 필터링 중...")
    news = get_filtered_news()
    send_email(news)
