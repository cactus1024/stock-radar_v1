"""
analysis.py — raw_market.json → top30.json + sector_history.json 업데이트
실행: python scripts/analysis.py
"""
import json
import sys
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
INPUT = DATA_DIR / "raw_market.json"
TOP30_OUT = DATA_DIR / "top30.json"
SECTOR_HISTORY = DATA_DIR / "sector_history.json"

KST = ZoneInfo("Asia/Seoul")

# 간이 섹터 분류 (종목명 키워드 기반)
# 완벽하지 않지만 v1에서는 충분. 추후 OpenDart 업종 코드로 교체 가능.
SECTOR_KEYWORDS = {
    "반도체": ["반도체", "SK하이닉스", "삼성전자", "메모리", "실리콘", "웨이퍼"],
    "2차전지": ["배터리", "2차전지", "에코프로", "포스코퓨처", "양극재", "음극재", "리튬", "전해질"],
    "바이오/제약": ["바이오", "제약", "셀트리온", "삼성바이오", "신약", "헬스", "의료", "진단"],
    "자동차": ["자동차", "현대차", "기아", "모비스", "부품"],
    "금융": ["은행", "증권", "보험", "캐피탈", "금융", "카드"],
    "건설": ["건설", "대우", "현대건설", "GS건설", "포스코건설"],
    "IT/소프트웨어": ["소프트", "네이버", "카카오", "NHN", "게임", "엔터", "플랫폼"],
    "에너지": ["에너지", "한전", "가스", "석유", "태양광", "풍력", "원전", "원자력", "SMR"],
    "철강/화학": ["철강", "화학", "포스코", "LG화학", "한화", "석유화학"],
    "유통/소비재": ["유통", "마트", "쇼핑", "식품", "음료", "화장품", "의류"],
}


def classify_sector(name: str) -> str:
    """종목명으로 간이 섹터 분류"""
    for sector, keywords in SECTOR_KEYWORDS.items():
        if any(kw in name for kw in keywords):
            return sector
    return "기타"


def calc_fibonacci(high: int, low: int) -> dict:
    """피보나치 되돌림 레벨 계산"""
    if high <= low or high == 0:
        return {}
    diff = high - low
    return {
        "0.0%_저점": low,
        "23.6%": round(low + diff * 0.236),
        "38.2%": round(low + diff * 0.382),
        "50.0%": round(low + diff * 0.5),
        "61.8%": round(low + diff * 0.618),
        "100.0%_고점": high,
    }


def main():
    if not INPUT.exists():
        print("[SKIP] raw_market.json 없음. 휴장일 추정.")
        sys.exit(0)

    with open(INPUT, encoding="utf-8") as f:
        raw = json.load(f)

    stocks = raw.get("stocks", [])
    if not stocks:
        print("[SKIP] 종목 데이터 비어 있음.")
        sys.exit(0)

    date = raw.get("date", datetime.now(KST).strftime("%Y-%m-%d"))
    time_str = raw.get("time", "16:00")

    # 등락률 정렬 → Top 30
    sorted_stocks = sorted(stocks, key=lambda x: x.get("change_pct", 0), reverse=True)
    top30 = sorted_stocks[:30]

    # 각 종목에 섹터 + 피보나치 추가
    for s in top30:
        s["sector"] = classify_sector(s.get("name", ""))
        s["fibonacci"] = calc_fibonacci(s.get("high", 0), s.get("low", 0))

    # 오늘 섹터별 종목 수 집계 (전체 시장 기준)
    sector_count = {}
    sector_avg_change = {}
    for s in stocks:
        sec = classify_sector(s.get("name", ""))
        sector_count[sec] = sector_count.get(sec, 0) + 1
        if sec not in sector_avg_change:
            sector_avg_change[sec] = []
        sector_avg_change[sec].append(s.get("change_pct", 0))

    today_sectors = {}
    for sec in sector_count:
        changes = sector_avg_change[sec]
        avg = round(sum(changes) / len(changes), 2) if changes else 0
        today_sectors[sec] = {
            "count": sector_count[sec],
            "avg_change_pct": avg,
            "top_gainer": max(
                [s for s in stocks if classify_sector(s.get("name", "")) == sec],
                key=lambda x: x.get("change_pct", 0),
                default={}
            ).get("name", "N/A"),
        }

    # top30.json 저장
    top30_result = {
        "date": date,
        "time": time_str,
        "timezone": "KST",
        "top30": top30,
        "today_sectors": today_sectors,
    }
    with open(TOP30_OUT, "w", encoding="utf-8") as f:
        json.dump(top30_result, f, ensure_ascii=False, indent=2)
    print(f"[OK] Top30 저장 → {TOP30_OUT}")

    # 섹터 히스토리 누적 (최대 30일 보관)
    history = []
    if SECTOR_HISTORY.exists():
        try:
            with open(SECTOR_HISTORY, encoding="utf-8") as f:
                history = json.load(f)
        except (json.JSONDecodeError, TypeError):
            history = []

    # 같은 날짜 중복 방지
    history = [h for h in history if h.get("date") != date]
    history.append({
        "date": date,
        "sectors": today_sectors,
    })
    # 최근 30일만 유지
    history = history[-30:]

    with open(SECTOR_HISTORY, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    print(f"[OK] 섹터 히스토리 업데이트 → {SECTOR_HISTORY} ({len(history)}일 보유)")


if __name__ == "__main__":
    main()
