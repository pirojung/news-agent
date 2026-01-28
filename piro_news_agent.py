import os
import requests
import smtplib
import feedparser
import urllib.parse
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta, timezone
import difflib

# ================= 1. 설정값 (구글 뉴스용으로 변경) =================
# 구글 뉴스는 API 키가 필요 없습니다.
KEYWORD = "kt" 

EMAIL_SENDER = "pirojung@gmail.com"  
EMAIL_APP_PWD = os.getenv("EMAIL_APP_PWD") 
EMAIL_RECEIVER = "po.jung@kt.com"

# 제외 키워드 및 사이트 (기존 유지)
EXCLUDE_KEYWORDS = [
    "위즈", "소닉붐", "롤스터", "LCK", "e스포츠", "T1", "젠지", "디플러스",
    "야구", "농구", "축구", "프로농구", "KBO", "KBL",
    "연승", "연패", "감독", "선수", "득점", "홈런", "역전", "더비",
    "연예", "방송", "드라마", "예능", "시청률", "출연", "가수", "배우", "아이돌", "Genie"
]

EXCLUDE_SITES = [
    "sports", "entertain", "basketkorea", "jumpball", "rookie",
    "inven", "fomos", "game", "thisisgame",
    "spotv", "xports", "osen", "stardaily", "joynews", "tvreport"
]

CATEGORY_KEYWORDS = {
    "1. IT/AI 동향 기사": ["AI", "인공지능", "LLM", "AX", "클라우드", "Cloud", "빅데이터", "IDC", "5G", "6G", "로봇", "자율주행", "디지털 전환", "DX", "양자암호", "초거대"],
    "2. CEO/경영/인사 관련 기사": ["박윤영", "김영섭", "대표", "CEO", "사장", "임원", "인사", "조직개편", "경영", "주주", "배당", "실적", "영업이익", "이사회", "노조", "단체협약"],
    "3. 신상품/서비스 출시 기사": ["출시", "신상품", "요금제", "프로모션", "신규", "서비스", "오픈", "이벤트", "가입자", "OTT", "스마트폰", "갤럭시", "아이폰"],
    "4. 정부규제/컴플라이언스 기사": ["방통위", "방송통신위원회", "공정위", "과기정통부", "국감", "국정감사", "규제", "과징금", "소송", "재판", "조사", "단통법", "망사용료", "통신비", "위반"]
}

# ============================================================

def is_similar(title1, title2):
    return difflib.SequenceMatcher(None, title1, title2).ratio()

def get_filtered_news():
    # 1. 구글 뉴스 RSS URL 설정 (한글 뉴스, 대한민국 지역 설정)
    encoded_keyword = urllib.parse.quote(KEYWORD)
    rss_url = f"https://news.google.com/rss/search?q={encoded_keyword}+when:1d&hl=ko&gl=KR&ceid=KR:ko"
    
    # 2. RSS 피드 파싱
    feed = feedparser.parse(rss_url)
    
    now = datetime.now(timezone(timedelta(hours=9)))
    time_limit = now - timedelta(hours=24)
    
    accepted_titles = []
    grouped_news = {
        "1. IT/AI 동향 기사": [],
        "2. CEO/경영/인사 관련 기사": [],
        "3. 신상품/서비스 출시 기사": [],
        "4. 정부규제/컴플라이언스 기사": [],
        "5. 기타 KT 관련 기사": []
    }

    for entry in feed.entries:
        # 발행 시간 파싱 (구글 뉴스는 구조가 다름)
        # 구글 RSS 날짜 포맷: 'Tue, 28 Jan 2026 07:00:00 GMT'
        published_parsed = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        if published_parsed < time_limit:
            continue

        clean_title = entry.title.split(" - ")[0] # 구글 뉴스는 제목 뒤에 언론사가 붙음 (예: 제목 - 언론사)
        link = entry.link

        # 1. 제외 필터링
        if any(site in link.lower() for site in EXCLUDE_SITES):
            continue
        if any(kw in clean_title for kw in EXCLUDE_KEYWORDS):
            continue
        
        # 2. 중복 기사 제외
        is_duplicate = False
        for existing_title in accepted_titles:
            if is_similar(clean_title, existing_title) > 0.65:
                is_duplicate = True
                break
        
        if not is_duplicate:
            accepted_titles.append(clean_title)
            
            # 구글 뉴스 RSS는 요약 정보가 적을 수 있어 제목 위주로 분류하되 summary 참고
            summary = entry.get('summary', '')
            search_text = clean_title + " " + summary
            
            assigned_category = "5. 기타 KT 관련 기사"
            for category, keywords in CATEGORY_KEYWORDS.items():
                if any(kw in search_text for kw in keywords):
                    assigned_category = category
                    break
            
            news_item = {
                'clean_title': clean_title,
                'link': link,
                'description': summary[:150], # 요약문 길이 조절
                'source': entry.get('source', {}).get('title', 'Google News')
            }
            grouped_news[assigned_category].append(news_item)

    return grouped_news

def send_email(grouped_news):
    total_news_count = sum(len(news_list) for news_list in grouped_news.values())
    
    if total_news_count == 0:
        print("새로운 뉴스가 없어 메일을 발송하지 않습니다.")
        return

    subject = f"[NewsAgent-Google] 오늘의 '{KEYWORD}' 핵심 뉴스 브리핑 ({total_news_count}건)"
    
    html_content = f"""
    <html>
    <body style="font-family: sans-serif; line-height: 1.6; max-width: 800px; margin: 0 auto;">
        <h2 style="color: #003366;">📰 [{KEYWORD}] 구글 뉴스 24시간 브리핑</h2>
        <p style="color:gray;">분류된 최신 뉴스 총 <b>{total_news_count}건</b>입니다.</p>
        <hr style="border: 1px solid #ddd;">
    """
    
    for category, news_list in grouped_news.items():
        if not news_list:
            continue
            
        html_content += f"<h3 style='color: #008080; margin-top: 25px;'>📌 {category} ({len(news_list)}건)</h3>"
        html_content += "<ul style='margin-bottom: 20px;'>"
        
        for item in news_list: 
            html_content += f"<li style='margin-bottom: 15px;'><b><a href='{item['link']}' target='_blank' style='text-decoration:none; color:#1a0dab; font-size:16px;'>{item['clean_title']}</a></b><br>"
            html_content += f"<span style='font-size:13px; color:#555;'>[{item['source']}] {item['description']}...</span></li>"
        
        html_content += "</ul>"

    html_content += "</body></html>"

    msg = MIMEMultipart()
    msg['From'] = EMAIL_SENDER
    msg['To'] = EMAIL_RECEIVER
    msg['Subject'] = subject
    msg.attach(MIMEText(html_content, 'html'))

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(EMAIL_SENDER, EMAIL_APP_PWD)
            server.send_message(msg)
        print("✅ 구글 뉴스 메일 발송 성공!")
    except Exception as e:
        print(f"❌ 이메일 발송 실패: {e}")

if __name__ == "__main__":
    print("구글 뉴스 수집 및 분류 중...")
    grouped_news = get_filtered_news()
    send_email(grouped_news)
