import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from openai import OpenAI # OpenAI 라이브러리 추가

# --- 설정 ---
URL = "https://www.boannews.com/media/t_list.asp"
BASE_URL = "https://www.boannews.com"
KEYWORDS = ["개인정보", "AI", "클라우드"]

# OpenAI 클라이언트 설정
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

def get_full_content(link):
    """기사 링크에서 본문 전체를 가져오는 함수"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(link, headers=headers, timeout=10)
        res.encoding = 'euc-kr'
        soup = BeautifulSoup(res.text, 'html.parser')
        # 보안뉴스 본문 영역 선택
        content = soup.select_one('#news_content')
        return content.get_text(strip=True) if content else ""
    except:
        return ""

def summarize_with_gpt(content):
    """GPT를 사용하여 본문을 2줄로 요약하는 함수"""
    if not content or len(content) < 100:
        return "본문 내용이 부족하여 요약할 수 없습니다."
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini", # 가성비 좋은 모델 사용
            messages=[
                {"role": "system", "content": "너는 보안 전문 뉴스 요약가야. 제공된 기사 내용을 일반인이 이해하기 쉽게 핵심만 딱 2줄로 요약해줘. 문장 끝은 '~음', '~함' 보다는 '~입니다.' 처럼 정중하게 끝내줘."},
                {"role": "user", "content": content[:2000]} # 토큰 절약을 위해 앞부분 2000자만 사용
            ],
            max_tokens=200,
            temperature=0.5
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"GPT 요약 에러: {e}")
        return content[:100] + "..." # 에러 시 기존 방식 유지

def get_news():
    headers = {'User-Agent': 'Mozilla/5.0'}
    response = requests.get(URL, headers=headers)
    response.encoding = 'euc-kr'
    soup = BeautifulSoup(response.text, 'html.parser')
    
    news_list = []
    now = datetime.now()
    start_time = now - timedelta(days=1, minutes=1)

    articles = soup.select('.news_list')
    
    for article in articles:
        title_elem = article.select_one('.news_txt')
        if not title_elem: continue
        
        title = title_elem.get_text(strip=True)
        link = BASE_URL + article.find('a')['href']
        
        date_elem = article.select_one('.news_writer')
        date_str = date_elem.get_text().split('|')[-1].strip()
        article_date = datetime.strptime(date_str, '%Y년 %m월 %d일 %H:%M')

        if article_date > start_time:
            print(f"요약 중: {title}")
            # 본문 가져오기 및 GPT 요약 실행
            full_content = get_full_content(link)
            summary = summarize_with_gpt(full_content)
            
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

    news_list.sort(key=lambda x: x['priority'])
    return news_list

# ... send_email 함수는 기존과 동일하게 유지 ...
def send_email(news_list):
    if not news_list:
        print("수집된 기사가 없습니다.")
        return

    sender = os.environ.get("EMAIL_SENDER")
    password = os.environ.get("EMAIL_PASSWORD")
    receiver = os.environ.get("EMAIL_RECEIVER")

    msg = MIMEMultipart()
    msg['Subject'] = f"[{datetime.now().strftime('%m/%d')}] AI 보안뉴스 브리핑 (GPT 요약)"
    msg['From'] = sender
    msg['To'] = receiver

    body = "<html><body><h2 style='color: #2e6c80;'>🤖 AI가 요약한 오늘의 보안 뉴스</h2><hr>"
    for news in news_list:
        priority_label = f"[{KEYWORDS[news['priority']]}]" if news['priority'] < 10 else "[기타]"
        body += f"""
        <div style='margin-bottom: 25px;'>
            <h3 style='margin-bottom: 5px;'>{priority_label} {news['title']}</h3>
            <p style='background-color: #f9f9f9; padding: 10px; border-left: 4px solid #1a73e8; color: #333;'>{news['summary']}</p>
            <a href='{news['link']}'>기사 원문 보기</a>
        </div>
        """
    body += "</body></html>"
    msg.attach(MIMEText(body, 'html'))

    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        server.starttls()
        server.login(sender, password)
        server.sendmail(sender, receiver, msg.as_string())
        print("메일 발송 완료!")

if __name__ == "__main__":
    news = get_news()
    send_email(news)
