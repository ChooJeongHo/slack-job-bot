#!/usr/bin/env python3
"""
채용공고 자동 수집 → 슬랙 발송
- 사이트: 사람인, 원티드, 점핏
- 경력: 0~2년 (신입/무관 포함)
- 직종: 서버/백엔드, 안드로이드, 웹개발
- 지역: 서울/경기 수도권 OR 원격근무
"""

import requests
import os
import time
import random
from datetime import datetime
from bs4 import BeautifulSoup
from collections import defaultdict

SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")
JOBS_PER_DAY = 5

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

SEOUL_GYEONGGI = [
    "서울", "경기", "인천", "수원", "성남", "용인", "고양", "화성", "안양", "부천",
    "남양주", "안산", "평택", "시흥", "파주", "의정부", "김포", "광명", "군포",
    "하남", "오산", "이천", "양주", "구리", "의왕"
]
REMOTE_KEYWORDS = ["원격", "재택", "리모트", "remote", "wfh"]
HIGH_CAREER = [
    "3년↑", "4년↑", "5년↑", "6년↑", "7년↑", "8년↑", "9년↑", "10년↑",
    "경력3년", "경력 3년", "3년이상", "4년이상", "5년이상",
    "3~", "4~", "5~", "6~", "7~", "8~", "9~", "10~",
    "~5년", "~6년", "~7년", "~8년", "~9년", "~10년",
    "경력5", "경력6", "경력7", "경력8", "경력9", "경력10",
]
VALID_CAREER = ["신입", "초급", "무관", "0년", "1년", "2년", "인턴", "신입·경력", "신입/경력"]


def is_valid_location(text):
    t = (text or "").lower()
    if any(kw in t for kw in REMOTE_KEYWORDS):
        return True
    if any(r in (text or "") for r in SEOUL_GYEONGGI):
        return True
    return False


def is_valid_career(text):
    if not text:
        return True
    if any(kw in text for kw in HIGH_CAREER):
        return False
    if any(kw in text for kw in VALID_CAREER):
        return True
    return True


def send_to_slack(jobs):
    if not SLACK_WEBHOOK_URL or not SLACK_WEBHOOK_URL.startswith("https://"):
        print("❌ SLACK_WEBHOOK_URL이 올바르지 않아요!")
        return
    today = datetime.now().strftime("%Y년 %m월 %d일")
    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": f"📋 오늘의 채용공고 — {today}"}},
        {"type": "context", "elements": [{"type": "mrkdwn", "text": "🔍 서버/백엔드/안드로이드/웹 | 경력 0~2년/무관 | 수도권/원격"}]},
        {"type": "divider"}
    ]
    for i, job in enumerate(jobs, 1):
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": (
                f"*{i}. {job['title']}*\n"
                f"🏢 {job['company']}  |  📍 {job['location']}  |  💼 {job['level']}\n"
                f"🔗 <{job['url']}|공고 보기>"
            )}
        })
        blocks.append({"type": "divider"})
    res = requests.post(SLACK_WEBHOOK_URL, json={"blocks": blocks})
    print(f"📤 슬랙 발송 {'완료' if res.status_code == 200 else '실패'} ({len(jobs)}개)")


def crawl_saramin():
    jobs = []
    keywords = ["서버개발", "백엔드개발", "안드로이드개발", "웹개발"]
    loc_codes = {"서울": "101000", "경기": "102000"}

    for keyword in keywords:
        for loc_name, loc_code in loc_codes.items():
            try:
                url = (
                    f"https://www.saramin.co.kr/zf_user/search/recruit"
                    f"?searchType=search&searchword={keyword}"
                    f"&career_min=0&career_max=2&loc_mcd={loc_code}"
                    f"&recruitPage=1&recruitPageCount=10"
                )
                res = requests.get(url, headers=HEADERS, timeout=10)
                soup = BeautifulSoup(res.text, "html.parser")

                for item in soup.select(".item_recruit")[:5]:
                    try:
                        title_el = item.select_one(".job_tit a")
                        company_el = item.select_one(".corp_name a")
                        if not title_el:
                            continue

                        title = title_el.get_text(strip=True)
                        company = company_el.get_text(strip=True) if company_el else "미기재"
                        job_url = "https://www.saramin.co.kr" + title_el.get("href", "")

                        # 사람인 경력 파싱
                        # .career 클래스는 존재하지 않음!
                        # 실제 구조: .job_condition > span 들 중 경력 키워드 있는 것 추출
                        # ex) <span>서울 서초구</span><span>경력5년↑</span><span>학력무관</span>
                        cond_spans = item.select(".job_condition span")
                        career = next(
                            (s.get_text(strip=True) for s in cond_spans
                             if any(k in s.get_text() for k in ["경력", "신입", "무관"])),
                            "신입/초급"
                        )

                        if not is_valid_career(career):
                            continue

                        jobs.append({
                            "title": title, "company": company,
                            "location": loc_name, "level": career,
                            "url": job_url, "source": "사람인"
                        })
                    except:
                        continue
                time.sleep(random.uniform(0.5, 1))
            except Exception as e:
                print(f"  사람인 오류 ({keyword}/{loc_name}): {e}")

    return jobs


def crawl_wanted():
    jobs = []
    keywords = ["서버 개발자", "백엔드 개발자", "안드로이드 개발자", "웹 개발자"]

    for keyword in keywords:
        for years in [0, 1, 2]:
            try:
                params = {
                    "job_sort": "job.latest_order",
                    "years": str(years),
                    "locations": "all",
                    "country": "kr",
                    "tag_type_ids": "518",
                    "keyword": keyword,
                    "limit": 10,
                    "offset": 0
                }
                res = requests.get(
                    "https://www.wanted.co.kr/api/v4/jobs",
                    params=params,
                    headers={**HEADERS, "Accept": "application/json"},
                    timeout=10
                )
                data = res.json()
                items = data.get("data") or []

                for item in items[:5]:
                    try:
                        addr = item.get("address") or {}
                        location = addr.get("location") or ""
                        full_loc = addr.get("full_location") or ""
                        is_remote = any(kw in (location + full_loc).lower() for kw in REMOTE_KEYWORDS)

                        if not is_remote and not is_valid_location(location):
                            continue

                        year_label = ["신입", "경력 1년", "경력 2년"][years]
                        jobs.append({
                            "title": item.get("position") or "",
                            "company": (item.get("company") or {}).get("name") or "미기재",
                            "location": "원격/재택" if is_remote else (location or "서울/경기"),
                            "level": year_label,
                            "url": f"https://www.wanted.co.kr/wd/{item.get('id', '')}",
                            "source": "원티드"
                        })
                    except:
                        continue
                time.sleep(random.uniform(0.5, 1))
            except Exception as e:
                print(f"  원티드 오류 ({keyword}, {years}년): {e}")

    return jobs


def crawl_jumpit():
    jobs = []
    occupation_codes = {
        "서버/백엔드": "16",
        "안드로이드": "8",
        "웹프론트엔드": "17",
        "웹풀스택": "18",
    }

    for job_type, code in occupation_codes.items():
        try:
            url = (
                f"https://jumpit-api.saramin.co.kr/api/positions"
                f"?highlight=false&sort=latest&occupationCode={code}&page=1"
            )
            res = requests.get(url, headers={**HEADERS, "Accept": "application/json"}, timeout=10)
            data = res.json()
            positions = (data.get("result") or {}).get("positions") or []

            for pos in positions:
                try:
                    min_c = pos.get("minCareer") or 0
                    max_c = pos.get("maxCareer") or 0

                    # 경력 필터: 최소 경력이 3년 이상이면 제외
                    if min_c > 2:
                        continue

                    locations = pos.get("locations") or []
                    loc_str = ", ".join(locations) if locations else ""
                    is_remote = any(kw in loc_str.lower() for kw in REMOTE_KEYWORDS)

                    if not is_remote and not is_valid_location(loc_str):
                        continue

                    pos_id = pos.get("id") or ""
                    career_text = "신입" if min_c == 0 and max_c == 0 else f"경력 {min_c}~{max_c}년"
                    jobs.append({
                        "title": pos.get("title") or "",
                        "company": pos.get("companyName") or "",
                        "location": "원격/재택" if is_remote else (loc_str or "서울"),
                        "level": career_text,
                        "url": f"https://www.jumpit.co.kr/position/{pos_id}",
                        "source": "점핏"
                    })
                except:
                    continue
            time.sleep(random.uniform(1, 1.5))
        except Exception as e:
            print(f"  점핏 오류 ({job_type}): {e}")

    return jobs


def main():
    print(f"🔍 채용공고 수집 시작 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("조건: 경력 0~2년/무관 | 서버/백엔드/안드로이드/웹 | 수도권/원격")

    all_jobs = []

    print("📌 사람인 수집 중...")
    saramin = crawl_saramin()
    all_jobs += saramin
    print(f"  → {len(saramin)}개")

    print("📌 원티드 수집 중...")
    wanted = crawl_wanted()
    all_jobs += wanted
    print(f"  → {len(wanted)}개")

    print("📌 점핏 수집 중...")
    jumpit = crawl_jumpit()
    all_jobs += jumpit
    print(f"  → {len(jumpit)}개")

    print(f"✅ 총 {len(all_jobs)}개 수집 완료")

    if not all_jobs:
        print("❌ 수집된 공고 없음")
        return

    seen, unique = set(), []
    for job in all_jobs:
        key = f"{job['title']}_{job['company']}"
        if key not in seen:
            seen.add(key)
            unique.append(job)
    print(f"🔄 중복 제거 후 {len(unique)}개")

    by_source = defaultdict(list)
    for job in unique:
        by_source[job["source"]].append(job)

    selected = []
    sources = list(by_source.keys())
    random.shuffle(sources)
    for source in sources:
        picks = random.sample(by_source[source], min(2, len(by_source[source])))
        selected.extend(picks)
        if len(selected) >= JOBS_PER_DAY:
            break
    selected = selected[:JOBS_PER_DAY]

    print(f"📤 슬랙 발송: {len(selected)}개")
    for job in selected:
        print(f"  [{job['source']}] {job['company']} - {job['title'][:40]} | {job['location']} | {job['level']}")

    send_to_slack(selected)


if __name__ == "__main__":
    main()
