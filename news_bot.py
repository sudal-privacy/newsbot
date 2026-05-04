import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

# --- 설정 ---
URL = "https://www.boannews.com/media/t_list.asp" # 보안뉴스 전체기사 목록
BASE_URL = "https://www.boannews.com"
# 1순위: 개인정보, 2순위: AI, 3순위: 클라우드
KEYWORDS = ["개인정보", "AI", "클라우드"]

def get_news():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
    }
    try:
        response = requests.get(URL, headers=headers, timeout=30)
        response.encoding = 'euc-kr' # 보안뉴스는 euc-kr 인코딩을 사용함
        soup = BeautifulSoup(response.text, 'html.parser')
        
        news_list = []
        now = datetime.now()
        # 기준 시간 설정: 어제 오전 08:31부터 오늘 오전 08:30까지
        # GitHub Actions가 8:30에 실행되므로, 실행 시점 기준 약 24시간 전부터 필터링
        start_time = now - timedelta(days=1, minutes=1)

        articles = soup.select('.news_list')
        
        for article in articles:
            title_elem = article.select_one('.news_txt')
            if not title_elem: continue
            
            title = title_elem.get_text(strip=True)
            link = BASE_URL + article.find('a')['href']
            
            # 날짜 및 시간 추출
            date_elem = article.select_one('.news_writer')
            date_str = date_elem.get_text().split('|')[-1].strip()
            # 예: 2024년 05월 20일 14:30
            article_date = datetime.strptime(date_str, '%Y년 %m월 %d일 %H:%M')

            # 시간 필터링
            if article_date > start_time:
                # 기사 내용 요약 (첫 100자 정도 가져오기)
                content_elem = article.select_one('.news_content')
                summary = content_elem.get_text(strip=True)[:120] + "..." if content_elem else "요약 내용 없음"
                
                # 우선순위 결정 (낮을수록 높은 순위)
                priority = 99
                for i, kw in enumerate(KEYWORDS):
                    if kw in title or kw in summary:
                        priority = i
                        break
                
                news_list.append({
                    'priority': priority,
                    'title': title,
                    'summary': summary,
                    'link': link,
                    'date': date_str
                })

        # 우선순위로 정렬 후, 같은 우선순위면 최신순 정렬
        news_list.sort(key=lambda x: x['priority'])
        return news_list
    except Exception as e:
        print(f"기사 수집 중 에러 발생: {e}")
        return []

def send_email(news_list):
    if not news_list:
        print("해당 시간 범위 내에 수집된 새로운 기사가 없습니다.")
        return

    sender = os.environ.get("EMAIL_SENDER")
    password = os.environ.get("EMAIL_PASSWORD")
    receiver = os.environ.get("EMAIL_RECEIVER")

    msg = MIMEMultipart()
    msg['Subject'] = f"[{datetime.now().strftime('%m/%d')}] 보안뉴스 주요 기사 요약 브리핑"
    msg['From'] = sender
    msg['To'] = receiver

    # 메일 본문 구성 (HTML 형식)
    body = """
    <html>
    <body>
        <h2 style='color: #2e6c80;'>📢 보안뉴스 주요 기사 브리핑</h2>
        <p style='color: #777;'>기준: 전일 08:31 ~ 금일 08:30</p>
        <hr>
    """
    
    for news in news_list:
        priority_label = f"[{KEYWORDS[news['priority']]}]" if news['priority'] < 10 else "[기타]"
        body += f"""
        <div style='margin-bottom: 20px;'>
            <h3 style='margin-bottom: 5px;'>{priority_label} {news['title']}</h3>
            <p style='color: #555; font-size: 0.9em; margin-bottom: 5px;'>{news['summary']}</p>
            <a href='{news['link']}' style='color: #1a73e8; text-decoration: none;'>기사 읽기 →</a>
            <p style='color: #999; font-size: 0.8em;'>작성시간: {news['date']}</p>
        </div>
        """
    
    body += "</body></html>"
    msg.attach(MIMEText(body, 'html'))

    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(sender, password)
            server.sendmail(sender, receiver, msg.as_string())
            print("이메일 발송 성공!")
    except Exception as e:
        print(f"이메일 발송 실패: {e}")

if __name__ == "__main__":
    news = get_news()
    send_email(news)
