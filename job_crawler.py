#!/usr/bin/env python3
"""
채용공고 자동 수집 → 슬랙 발송
- 사이트: 사람인, 원티드, 점핏
- 경력: 0~2년 (신입 포함)
- 직종: 서버/백엔드, 안드로이드, 웹개발
- 지역: 서울/경기 수도권 OR 원격근무
"""

import requests
import os
import json
import re
import time
import random
from datetime import datetime
from bs4 import BeautifulSoup

SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")
JOBS_PER_DAY = 5

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# 검색 키워드
KEYWORDS = ["서버개발", "백엔드개발", "안드로이드개발", "웹개발"]

# 수도권 지역명
SEOUL_GYEONGGI = ["서울", "경기", "인천", "수원", "성남", "용인", "고양", "화성", "안양", "부천",
                   "남양주", "안산", "평택", "시흥", "파주", "의정부", "김포", "광주", "광명",
                   "군포", "하남", "오산", "이천", "양주", "구리", "안성", "포천", "의왕", "여주"]

# 원격근무 키워드
REMOTE_KEYWORDS = ["원격", "재택", "리모트", "remote", "work from home", "wfh"]

# 통과 경력 조건
VALID_CAREER = ["신입", "초급", "무관", "경력무관", "경력 무관", "0년", "1년", "2년", "신입·경력", "신입/경력"]

# 고경력 필터 (이 텍스트 있으면 제외)
HIGH_CAREER = ["경력3년", "경력 3년", "3년↑", "4년↑", "5년↑", "6년↑", "7년↑", "8년↑",
               "9년↑", "10년↑", "3년이상", "4년이상", "5년이상"]


def is_valid_location(location_text):
    """수도권 또는 원격근무 여부 확인"""
    text = location_text.lower()
    # 원격/재택이면 통과
    if any(kw in text for kw in REMOTE_KEYWORDS):
        return True
    # 수도권이면 통과
    if any(region in location_text for region in SEOUL_GYEONGGI):
        return True
    return False


def is_valid_career(career_text):
    """경력 조건 확인 (0~2년 이하 OR 경력무관)"""
    if not career_text:
        return True
    # 고경력 텍스트 있으면 제외
    if any(kw in career_text for kw in HIGH_CAREER):
        return False
    # 신입/초급/경력무관/0~2년이면 통과
    if any(kw in career_text for kw in VALID_CAREER):
        return True
    return True  # 기본값 통과


def send_to_slack(jobs):
    today = datetime.now().strftime("%Y년 %m월 %d일")
    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": f"📋 오늘의 채용공고 — {today}"}},
        {"type": "context", "elements": [{"type": "mrkdwn", "text": "🔍 서버/백엔드/안드로이드/웹 | 경력 0~2년 | 수도권/원격"}]},
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

    response = requests.post(SLACK_WEBHOOK_URL, json={"blocks": blocks})
    print(f"📤 슬랙 발송 {'완료' if response.status_code == 200 else '실패'} ({len(jobs)}개)")


def crawl_saramin():
    """사람인 크롤링 - 서울/경기 + 원격"""
    jobs = []
    keywords = ["서버개발", "백엔드개발", "안드로이드개발", "웹개발"]

    for keyword in keywords:
        try:
            # 서울/경기 검색
            for loc_mcd in ["101000", "102000"]:  # 서울, 경기
                url = (
                    f"https://www.saramin.co.kr/zf_user/search/recruit"
                    f"?searchType=search&searchword={keyword}"
                    f"&career_min=0&career_max=2"
                    f"&loc_mcd={loc_mcd}"
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

                        # span에서 지역/경력 파싱
                        spans = [s.get_text(strip=True) for s in item.select("span")]
                        location = next((s for s in spans if any(r in s for r in SEOUL_GYEONGGI)), "서울/경기")
                        career = next((s for s in spans if "경력" in s or "신입" in s or "무관" in s), "신입/초급")

                        # 경력 필터
                        if not is_valid_career(career):
                            continue

                        jobs.append({
                            "title": title,
                            "company": company,
                            "location": location,
                            "level": career,
                            "url": job_url,
                            "source": "사람인"
                        })
                    except:
                        continue

                time.sleep(random.uniform(0.5, 1))

            # 원격근무 검색
            url = (
                f"https://www.saramin.co.kr/zf_user/search/recruit"
                f"?searchType=search&searchword={keyword}"
                f"&career_min=0&career_max=2"
                f"&loc_mcd=107010"  # 재택/원격 코드
                f"&recruitPage=1&recruitPageCount=10"
            )
            res = requests.get(url, headers=HEADERS, timeout=10)
            soup = BeautifulSoup(res.text, "html.parser")

            for item in soup.select(".item_recruit")[:3]:
                try:
                    title_el = item.select_one(".job_tit a")
                    company_el = item.select_one(".corp_name a")
                    if not title_el:
                        continue

                    title = title_el.get_text(strip=True)
                    company = company_el.get_text(strip=True) if company_el else "미기재"
                    job_url = "https://www.saramin.co.kr" + title_el.get("href", "")
                    spans = [s.get_text(strip=True) for s in item.select("span")]
                    career = next((s for s in spans if "경력" in s or "신입" in s or "무관" in s), "신입/초급")

                    if not is_valid_career(career):
                        continue

                    jobs.append({
                        "title": title,
                        "company": company,
                        "location": "원격/재택",
                        "level": career,
                        "url": job_url,
                        "source": "사람인"
                    })
                except:
                    continue

            time.sleep(random.uniform(1, 2))

        except Exception as e:
            print(f"  사람인 오류 ({keyword}): {e}")

    return jobs


def crawl_wanted():
    """원티드 API - 수도권/원격"""
    jobs = []
    searches = [
        {"keyword": "서버 개발자", "tag_type_ids": "518"},
        {"keyword": "백엔드 개발자", "tag_type_ids": "518"},
        {"keyword": "안드로이드 개발자", "tag_type_ids": "518"},
        {"keyword": "웹 개발자", "tag_type_ids": "518"},
    ]

    for search in searches:
        for years in [0, 1, 2]:  # 신입, 1년, 2년
            try:
                params = {
                    "job_sort": "job.latest_order",
                    "years": str(years),
                    "locations": "seoul,gyeonggi,incheon,all",
                    "country": "kr",
                    "tag_type_ids": search["tag_type_ids"],
                    "keyword": search["keyword"],
                    "limit": 5,
                    "offset": 0
                }
                headers = {**HEADERS, "Accept": "application/json"}
                res = requests.get("https://www.wanted.co.kr/api/v4/jobs", params=params, headers=headers, timeout=10)
                data = res.json()

                for item in data.get("data", [])[:3]:
                    try:
                        location = item.get("address", {}).get("location", "")
                        # 수도권 또는 원격 체크
                        if not is_valid_location(location) and location:
                            continue

                        year_label = ["신입", "경력 1년", "경력 2년"][years]
                        jobs.append({
                            "title": item.get("position", ""),
                            "company": item.get("company", {}).get("name", "미기재"),
                            "location": location or "서울/경기",
                            "level": year_label,
                            "url": f"https://www.wanted.co.kr/wd/{item.get('id', '')}",
                            "source": "원티드"
                        })
                    except:
                        continue

                time.sleep(random.uniform(0.5, 1))

            except Exception as e:
                print(f"  원티드 오류 ({search['keyword']}, {years}년): {e}")

    return jobs


def crawl_jumpit():
    """점핏 API - 수도권/원격"""
    jobs = []
    # 점핏 직종 코드
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
                f"?highlight=false&sort=latest"
                f"&minCareer=0&maxCareer=2"
                f"&occupationCode={code}"
                f"&page=1"
            )
            res = requests.get(url, headers=HEADERS, timeout=10)

            # XML 파싱
            from xml.etree import ElementTree as ET
            root = ET.fromstring(res.text)

            for pos in root.findall(".//positions"):
                try:
                    title = pos.findtext("title", "")
                    company = pos.findtext("companyName", "")
                    location = pos.findtext("address", "")
                    min_c = pos.findtext("minCareer", "0")
                    max_c = pos.findtext("maxCareer", "2")
                    pos_id = pos.findtext("id", "")
                    work_type = pos.findtext("workType", "")

                    # 지역 체크
                    is_remote = "재택" in work_type or "원격" in work_type or "remote" in work_type.lower()
                    if not is_remote and not is_valid_location(location):
                        continue

                    # 경력 체크
                    try:
                        if int(max_c) > 2:
                            continue
                    except:
                        pass

                    career_text = f"신입~경력 {max_c}년" if max_c != "0" else "신입"
                    loc_text = "원격/재택" if is_remote else location

                    jobs.append({
                        "title": title,
                        "company": company,
                        "location": loc_text,
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
    print("조건: 경력 0~2년 | 서버/백엔드/안드로이드/웹 | 수도권/원격")

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

    # 중복 제거 (제목+회사 기준)
    seen = set()
    unique_jobs = []
    for job in all_jobs:
        key = f"{job['title']}_{job['company']}"
        if key not in seen:
            seen.add(key)
            unique_jobs.append(job)

    print(f"🔄 중복 제거 후 {len(unique_jobs)}개")

    # 사이트별 균형 선택 (최대 2개씩)
    from collections import defaultdict
    by_source = defaultdict(list)
    for job in unique_jobs:
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
