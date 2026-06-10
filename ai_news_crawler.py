#!/usr/bin/env python3
"""
AI 최신 뉴스 크롤러 → Claude 요약 → 슬랙 발송
- Google News RSS에서 AI/Claude/LLM/Agent 관련 최신 뉴스 수집
- Claude API로 한국어 요약 생성
- 매일 아침 슬랙 업무지원 채널에 자동 발송
"""

import json, os, re, time, urllib.request, urllib.parse
from datetime import datetime

SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

# 검색 키워드
SEARCH_QUERIES = [
    "Claude AI Anthropic",
    "LLM AI agent 2025",
    "AI 개발 도구 에이전트",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
}


def fetch_google_news(query):
    """Google News RSS에서 뉴스 가져오기"""
    encoded = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded}&hl=ko&gl=KR&ceid=KR:ko"
    
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10) as r:
            xml = r.read().decode("utf-8")
        
        items = []
        # RSS 아이템 파싱
        item_blocks = re.findall(r'<item>(.*?)</item>', xml, re.DOTALL)
        
        for block in item_blocks[:5]:
            title_m = re.search(r'<title>(.*?)</title>', block, re.DOTALL)
            link_m = re.search(r'<link>(.*?)</link>', block, re.DOTALL)
            date_m = re.search(r'<pubDate>(.*?)</pubDate>', block, re.DOTALL)
            source_m = re.search(r'<source[^>]*>(.*?)</source>', block, re.DOTALL)
            
            if title_m and link_m:
                title = re.sub(r'<[^>]+>', '', title_m.group(1)).strip()
                title = title.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&quot;', '"')
                link = link_m.group(1).strip()
                date = date_m.group(1).strip() if date_m else ""
                source = re.sub(r'<[^>]+>', '', source_m.group(1)).strip() if source_m else ""
                
                items.append({
                    "title": title,
                    "url": link,
                    "date": date,
                    "source": source,
                    "query": query
                })
        
        return items
    except Exception as e:
        print(f"뉴스 수집 오류 ({query}): {e}")
        return []


def summarize_with_claude(title, url):
    """Claude API로 뉴스 요약"""
    if not ANTHROPIC_API_KEY:
        return "Claude API 키가 없어서 요약 불가"
    
    prompt = f"""다음 뉴스 제목을 보고 AI 개발자 관점에서 핵심 내용을 2-3문장으로 한국어로 요약해주세요.
왜 중요한지, 어떤 점이 주목할만한지 간략히 설명해주세요.

제목: {title}
URL: {url}

요약만 출력하세요. 다른 설명 없이."""

    try:
        payload = json.dumps({
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 300,
            "messages": [{"role": "user", "content": prompt}]
        }).encode("utf-8")
        
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01"
            }
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
            return data["content"][0]["text"].strip()
    except Exception as e:
        print(f"Claude 요약 오류: {e}")
        return "요약 생성 실패"


def send_to_slack(news_items):
    """슬랙에 뉴스 발송"""
    today = datetime.now().strftime("%Y년 %m월 %d일")
    
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"🤖 AI 최신 뉴스 — {today}"}
        },
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": "Claude, LLM, AI 에이전트 관련 최신 소식"}]
        },
        {"type": "divider"}
    ]
    
    for i, item in enumerate(news_items, 1):
        summary = item.get("summary", "")
        source = item.get("source", "")
        
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*{i}. {item['title']}*\n"
                    f"📰 {source}\n"
                    f"💡 {summary}\n"
                    f"🔗 <{item['url']}|기사 보기>"
                )
            }
        })
        blocks.append({"type": "divider"})
    
    payload = json.dumps({"blocks": blocks}).encode("utf-8")
    req = urllib.request.Request(
        SLACK_WEBHOOK_URL,
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as r:
        return r.status


def main():
    print(f"🔍 AI 뉴스 수집 시작 — {datetime.now()}")
    
    all_news = []
    
    for query in SEARCH_QUERIES:
        print(f"📡 검색: {query}")
        items = fetch_google_news(query)
        all_news.extend(items)
        print(f"  → {len(items)}개 수집")
        time.sleep(1)
    
    # 중복 제거 (제목 기준)
    seen, unique = set(), []
    for item in all_news:
        if item["title"] not in seen:
            seen.add(item["title"])
            unique.append(item)
    
    print(f"✅ 총 {len(unique)}개 수집 (중복 제거 후)")
    
    if not unique:
        print("수집된 뉴스 없음")
        return
    
    # 최신 2개 선택
    selected = unique[:2]
    
    # Claude로 요약
    for item in selected:
        print(f"💡 요약 중: {item['title'][:50]}...")
        item["summary"] = summarize_with_claude(item["title"], item["url"])
        print(f"  → {item['summary'][:80]}...")
        time.sleep(1)
    
    # 슬랙 발송
    status = send_to_slack(selected)
    print(f"📤 슬랙 발송 완료 (status: {status})")
    
    for item in selected:
        print(f"  ✓ {item['title'][:60]}")


if __name__ == "__main__":
    main()
