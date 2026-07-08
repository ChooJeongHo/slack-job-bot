#!/usr/bin/env python3
"""
THE VC 지원사업 크롤러 → 슬랙 발송
"""

import json, os, re, time, urllib.request
from datetime import datetime, date

SLACK_WEBHOOK_URL = os.environ.get("JOB_NEWS_WEBHOOK_URL")  # 채용공고-뉴스 채널

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Accept": "text/html,application/xhtml+xml",
}

DOMAIN_KEYWORDS = ["AI", "AX", "인공지능", "서비스", "SaaS", "플랫폼", "IT", "ICT", "디지털", "데이터", "스타트업", "창업기업", "벤처", "기술창업", "소프트웨어"]
SAFETY_KEYWORDS = ["안전", "보안", "방산", "국방"]

SENT_FILE = "/tmp/sent_grants.json"

def load_sent():
    try:
        with open(SENT_FILE) as f: return set(json.load(f))
    except: return set()

def save_sent(ids):
    with open(SENT_FILE, "w") as f: json.dump(list(ids), f)

def fetch_page(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read().decode("utf-8")

def strip_tags(html):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', html)).strip()

def parse_grants(html):
    grants = []
    today = date.today()

    # SSR HTML 실제 구조:
    # <a href="/grants?id={id}" class="... py-20 px-16 block ..." data-v-c0ca1eb2>
    #   <div class="text-16 text-bold text-truncate" ...><!--[-->제목</div>
    #   <time datetime="YYYY-MM-DDT...">날짜</time>
    # </a>

    card_pattern = re.compile(
        r'<a[^>]+href="/grants\?id=([a-f0-9]{20,})"[^>]*class="[^"]*py-20 px-16 block[^"]*"[^>]*>(.*?)</a>',
        re.DOTALL
    )

    for m in card_pattern.finditer(html):
        grant_id = m.group(1)
        card = m.group(2)

        # 제목: text-truncate 클래스 div
        title_match = re.search(r'class="[^"]*text-truncate[^"]*"[^>]*>(.*?)</div>', card, re.DOTALL)
        if not title_match:
            continue
        title = strip_tags(title_match.group(1))
        # Vue SSR 주석 제거
        title = re.sub(r'<!--.*?-->', '', title).strip()
        if len(title) < 5:
            continue

        # 날짜: datetime 속성에서 YYYY-MM-DD 추출
        times = re.findall(r'datetime="(\d{4}-\d{2}-\d{2})', card)
        if len(times) < 2:
            continue

        reg_date = times[0]
        deadline = times[1]

        # 마감 공고 제외
        try:
            if datetime.strptime(deadline, "%Y-%m-%d").date() < today:
                continue
        except:
            continue

        # D-day 계산
        try:
            dday = (datetime.strptime(deadline, "%Y-%m-%d").date() - today).days
        except:
            dday = 999

        # 카테고리
        cat_match = re.search(
            r'(사업화|자금지원|해외마케팅|수출지원|교육|컨설팅|R&D|공간|사무실|대출|투자|IR|국내마케팅|내수지원|행사|대회|시제품|고용)',
            card
        )
        category = cat_match.group(0) if cat_match else ""

        # 기관명
        org_patterns = [
            r'class="[^"]*text-truncate[^"]*"[^>]*>.*?</div>[^<]*<[^>]+>[^<]*</[^>]+>[^<]*<[^>]+>([^<]{2,30})</[^>]+>',
        ]
        organization = ""
        org_match = re.search(r'(?:정부|연구기관|민간|교육기관|인큐베이터)[^<]*</[^>]+>[^<]*<[^>]+>([^<]{2,30})</[^>]+>|([가-힣A-Za-z·\s]+(?:청|원|부|위|회|관|단|협|대학교|센터|공단|재단|기업|사))\s*(?:<!--.*?-->)?\s*</[^>]+>', card, re.DOTALL)

        grants.append({
            "id": grant_id,
            "title": title,
            "deadline": deadline,
            "reg_date": reg_date,
            "category": category,
            "organization": organization,
            "dday": dday,
            "url": f"https://thevc.kr/grants/{grant_id}",
        })

    return grants

def filter_grants(grants):
    filtered = []
    for g in grants:
        text = f"{g['title']} {g['category']}"
        domain = any(kw.lower() in text.lower() for kw in DOMAIN_KEYWORDS)
        safety = any(kw.lower() in text.lower() for kw in SAFETY_KEYWORDS)
        if domain or safety:
            matched = [kw for kw in DOMAIN_KEYWORDS + SAFETY_KEYWORDS if kw.lower() in text.lower()]
            g["keywords"] = list(set(matched))[:3]
            filtered.append(g)
    return sorted(filtered, key=lambda x: x.get("dday", 999))

def send_to_slack(grants):
    today = datetime.now().strftime("%Y년 %m월 %d일")
    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": f"📢 지원사업 공고 — {today}"}},
        {"type": "context", "elements": [{"type": "mrkdwn", "text": "🎯 AI/서비스/안전 키워드 | THE VC"}]},
        {"type": "divider"}
    ]
    for i, g in enumerate(grants, 1):
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": (
                f"*{i}. {g['title'][:60]}*\n"
                f"🏷 {g['category']}  |  📅 {g['deadline']} D-{g['dday']}\n"
                f"🔑 {', '.join(g.get('keywords', []))}\n"
                f"🔗 <{g['url']}|공고 보기>"
            )}
        })
        blocks.append({"type": "divider"})
    payload = json.dumps({"blocks": blocks}).encode("utf-8")
    req = urllib.request.Request(SLACK_WEBHOOK_URL, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return r.status

def main():
    print(f"🔍 THE VC 크롤링 시작 — {datetime.now()}")
    sent_ids = load_sent()
    all_grants = []

    for page in range(1, 4):
        url = "https://thevc.kr/grants" if page == 1 else f"https://thevc.kr/grants?page={page}"
        try:
            print(f"📡 {url}")
            html = fetch_page(url)
            grants = parse_grants(html)
            all_grants.extend(grants)
            print(f"  → {len(grants)}개 파싱")
            for g in grants[:3]:
                print(f"    ✓ {g['title'][:50]}")
            time.sleep(1.5)
        except Exception as e:
            print(f"  오류: {e}")

    seen, unique = set(), []
    for g in all_grants:
        if g["id"] not in seen:
            seen.add(g["id"]); unique.append(g)

    print(f"✅ 총 {len(unique)}개 수집")

    filtered = filter_grants(unique)
    print(f"🎯 필터 후 {len(filtered)}개")
    for g in filtered:
        print(f"  [{', '.join(g.get('keywords',[]))}] {g['title'][:50]}")

    if not filtered:
        print("조건에 맞는 공고 없음"); return

    new_grants = [g for g in filtered if g["id"] not in sent_ids]
    print(f"🆕 새 공고 {len(new_grants)}개")

    if not new_grants:
        print("새로운 공고 없음"); return

    to_send = new_grants[:5]
    status = send_to_slack(to_send)
    print(f"📤 슬랙 발송 완료 ({len(to_send)}개)")
    save_sent(sent_ids | {g["id"] for g in to_send})

if __name__ == "__main__":
    main()
