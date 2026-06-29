#!/usr/bin/env python3
"""
채용공고 자동 수집 → 슬랙 발송 스크립트
- 사람인, 원티드, 잡코리아에서 서버/안드로이드 초급 공고 수집
- 하루 5개씩 슬랙 채널에 자동 업로드
- cron으로 매일 실행 권장
"""

import requests
import json
import time
import random
from datetime import datetime
from bs4 import BeautifulSoup

SLACK_WEBHOOK_URL = "https://hooks.slack.com/services/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"
JOBS_PER_DAY = 5

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

KEYWORDS = ["서버개발자", "안드로이드개발자", "백엔드개발자"]
LEVELS = ["신입", "초급", "경력 1년", "경력 2년"]

def send_to_slack(jobs):
    """슬랙에 채용공고 발송"""
    today = datetime.now().strftime("%Y년 %m월 %d일")
    
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"📋 오늘의 채용공고 — {today}"
            }
        },
        {"type": "divider"}
    ]

    for i, job in enumerate(jobs, 1):
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*{i}. {job['title']}*\n"
                    f"🏢 {job['company']}  |  📍 {job['location']}  |  💼 {job['level']}\n"
                    f"🔗 <{job['url']}|공고 보기>"
                )
            }
        })
        blocks.append({"type": "divider"})

    payload = {"blocks": blocks}
    response = requests.post(SLACK_WEBHOOK_URL, json=payload)
    
    if response.status_code == 200:
        print(f"✅ 슬랙 발송 완료 ({len(jobs)}개)")
    else:
        print(f"❌ 슬랙 발송 실패: {response.status_code} {response.text}")


def crawl_saramin():
    """사람인 크롤링"""
    jobs = []
    keywords = ["서버개발", "안드로이드개발"]
    
    for keyword in keywords:
        try:
            url = f"https://www.saramin.co.kr/zf_user/search/recruit?searchType=search&searchword={keyword}&recruitPage=1&recruitSort=relation&recruitPageCount=10&career_min=0&career_max=2"
            res = requests.get(url, headers=HEADERS, timeout=10)
            soup = BeautifulSoup(res.text, "html.parser")
            
            items = soup.select(".item_recruit")[:5]
            for item in items:
                try:
                    title_el = item.select_one(".job_tit a")
                    company_el = item.select_one(".corp_name a")
                    location_el = item.select_one(".work_place")
                    career_el = item.select_one(".career")
                    
                    if not title_el:
                        continue
                    
                    title = title_el.get_text(strip=True)
                    company = company_el.get_text(strip=True) if company_el else "미기재"
                    location = location_el.get_text(strip=True) if location_el else "미기재"
                    level = career_el.get_text(strip=True) if career_el else "신입/초급"
                    job_url = "https://www.saramin.co.kr" + title_el.get("href", "")
                    
                    jobs.append({
                        "title": title,
                        "company": company,
                        "location": location,
                        "level": level,
                        "url": job_url,
                        "source": "사람인"
                    })
                except Exception as e:
                    continue
            
            time.sleep(random.uniform(1, 2))
        except Exception as e:
            print(f"사람인 크롤링 오류: {e}")
    
    return jobs


def crawl_wanted():
    """원티드 API 크롤링"""
    jobs = []
    
    # 원티드 공식 API 사용
    searches = [
        {"query": "서버 개발자", "job_sort": "job.latest_order"},
        {"query": "안드로이드 개발자", "job_sort": "job.latest_order"}
    ]
    
    for search in searches:
        try:
            url = "https://www.wanted.co.kr/api/v4/jobs"
            params = {
                "job_sort": search["job_sort"],
                "years": "0",  # 신입
                "locations": "all",
                "tag_type_ids": "",
                "keyword": search["query"],
                "limit": 10,
                "offset": 0
            }
            headers = {**HEADERS, "Accept": "application/json, text/plain, */*"}
            
            res = requests.get(url, params=params, headers=headers, timeout=10)
            data = res.json()
            
            for item in data.get("data", [])[:5]:
                try:
                    jobs.append({
                        "title": item.get("position", ""),
                        "company": item.get("company", {}).get("name", "미기재"),
                        "location": item.get("address", {}).get("location", "미기재"),
                        "level": "신입/초급",
                        "url": f"https://www.wanted.co.kr/wd/{item.get('id', '')}",
                        "source": "원티드"
                    })
                except Exception:
                    continue
            
            time.sleep(random.uniform(1, 2))
        except Exception as e:
            print(f"원티드 크롤링 오류: {e}")
    
    return jobs


def crawl_jobkorea():
    """잡코리아 크롤링"""
    jobs = []
    keywords = ["서버개발", "안드로이드"]
    
    for keyword in keywords:
        try:
            url = f"https://www.jobkorea.co.kr/Search/?stext={keyword}&tabType=recruit&careerType=1"
            res = requests.get(url, headers=HEADERS, timeout=10)
            soup = BeautifulSoup(res.text, "html.parser")
            
            items = soup.select(".list-post .information-title")[:5]
            for item in items:
                try:
                    title_el = item.select_one(".title")
                    company_el = item.select_one(".name")
                    
                    if not title_el:
                        continue
                    
                    title = title_el.get_text(strip=True)
                    company = company_el.get_text(strip=True) if company_el else "미기재"
                    href = title_el.get("href", "")
                    job_url = f"https://www.jobkorea.co.kr{href}" if href.startswith("/") else href
                    
                    jobs.append({
                        "title": title,
                        "company": company,
                        "location": "미기재",
                        "level": "신입/초급",
                        "url": job_url,
                        "source": "잡코리아"
                    })
                except Exception:
                    continue
            
            time.sleep(random.uniform(1, 2))
        except Exception as e:
            print(f"잡코리아 크롤링 오류: {e}")
    
    return jobs


def main():
    print(f"🔍 채용공고 수집 시작 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    
    all_jobs = []
    
    print("📌 사람인 수집 중...")
    all_jobs += crawl_saramin()
    
    print("📌 원티드 수집 중...")
    all_jobs += crawl_wanted()
    
    print("📌 잡코리아 수집 중...")
    all_jobs += crawl_jobkorea()
    
    print(f"✅ 총 {len(all_jobs)}개 수집 완료")
    
    if not all_jobs:
        print("❌ 수집된 공고 없음")
        return
    
    # 중복 제거 (제목 기준)
    seen = set()
    unique_jobs = []
    for job in all_jobs:
        if job["title"] not in seen:
            seen.add(job["title"])
            unique_jobs.append(job)
    
    # 랜덤으로 5개 선택
    selected = random.sample(unique_jobs, min(JOBS_PER_DAY, len(unique_jobs)))
    
    print(f"📤 슬랙 발송: {len(selected)}개")
    for job in selected:
        print(f"  [{job['source']}] {job['company']} - {job['title']}")
    
    send_to_slack(selected)


if __name__ == "__main__":
    main()
