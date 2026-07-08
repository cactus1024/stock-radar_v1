# analysis.py — raw_market.json → top30.json (순수종목/ETF 분리, 위험종목 필터, 간이 공포지수)
import json, sys
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
INPUT = DATA_DIR / "raw_market.json"
TOP30_OUT = DATA_DIR / "top30.json"
SECTOR_HISTORY = DATA_DIR / "sector_history.json"
KST = ZoneInfo("Asia/Seoul")

# ETF/ETN 판별 키워드 (운용사 브랜드 + 상품 유형)
ETF_KEYWORDS = ["KODEX", "TIGER", "RISE", "KBSTAR", "ACE", "SOL", "PLUS", "ARIRANG",
                "HANARO", "KOSEF", "KIWOOM", "WON", "히어로즈", "마이다스", "TIMEFOLIO",
                "에셋플러스", "KoAct", "BNK", "UNICORN", "1Q", "FOCUS", "ETN", "레버리지",
                "인버스", "합성", "TRF", "TDF", "채권", "선물", "커버드콜", "액티브"]

SECTOR_KEYWORDS = {
    "반도체": ["반도체", "하이닉스", "삼성전자", "메모리", "실리콘", "웨이퍼", "칩스", "테크윙", "HPSP", "이오테크"],
    "2차전지": ["배터리", "2차전지", "에코프로", "포스코퓨처", "양극재", "음극재", "리튬", "전해", "엘앤에프"],
    "바이오/제약": ["바이오", "제약", "셀트리온", "신약", "헬스", "의료", "진단", "팜", "메디", "젠", "테라퓨틱스", "사이언스"],
    "자동차/부품": ["자동차", "현대차", "기아", "모비스", "부품", "모터"],
    "금융": ["은행", "증권", "보험", "캐피탈", "금융", "카드", "지주"],
    "건설/기계": ["건설", "기계", "중공업", "엔지니어링", "산업"],
    "IT/게임/엔터": ["소프트", "네이버", "카카오", "NHN", "게임", "엔터", "플랫폼", "위버스", "하이브", "SM", "JYP"],
    "에너지/원전": ["에너지", "한전", "가스", "석유", "태양", "풍력", "원전", "원자력", "SMR", "두산에너"],
    "철강/화학": ["철강", "화학", "포스코", "LG화학", "한화", "롯데케미칼"],
    "조선/방산": ["조선", "방산", "한화에어로", "HD현대", "한화오션", "LIG", "풍산", "현대로템"],
    "로봇/AI": ["로봇", "로보", "AI", "인공지능", "레인보우", "두산로보"],
    "우주/항공": ["우주", "항공", "위성", "에어로"],
}

def classify_sector(name):
    for sector, kws in SECTOR_KEYWORDS.items():
        if any(k.lower() in name.lower() for k in kws):
            return sector
    return "기타"

def is_etf(s):
    if s.get("stock_type", "").lower() in ("etf", "etn"):
        return True
    return any(k.lower() in s["name"].lower() for k in ETF_KEYWORDS)

def is_risky(s):
    """위험종목 필터: 우선주(코드 끝자리≠0), 동전주(<1000원), 스팩, 거래대금 5억 미만"""
    t = s.get("ticker", "")
    if t and t[-1] != "0":
        return True                      # 우선주/전환주 계열
    if s.get("close", 0) < 1000:
        return True                      # 동전주
    if "스팩" in s.get("name", ""):
        return True
    if s.get("close", 0) * s.get("volume", 0) < 500_000_000:
        return True                      # 거래대금 5억 미만 (유동성 부족)
    return False

def calc_fibonacci(high, low):
    if not high or not low or high <= low:
        return {}
    d = high - low
    return {"저점": low, "38.2%": round(low + d * 0.382), "50.0%": round(low + d * 0.5),
            "61.8%": round(low + d * 0.618), "고점": high}

def calc_fear(indices, top30):
    """간이 시장 온도계 (자체 계산, 0~100): 지수 등락 + 상승 강도 기반"""
    kospi = indices.get("KOSPI", {}).get("change_pct")
    kosdaq = indices.get("KOSDAQ", {}).get("change_pct")
    if kospi is None and kosdaq is None:
        return None
    score = 50.0
    if kospi is not None:
        score += float(kospi) * 12
    if kosdaq is not None:
        score += float(kosdaq) * 8
    if top30:
        avg = sum(s["change_pct"] for s in top30) / len(top30)
        score += (avg - 15) * 0.5        # 상한가 러시 강도 반영
    score = max(0, min(100, round(score)))
    if score <= 25: label = "극단 공포"
    elif score <= 45: label = "공포"
    elif score <= 55: label = "중립"
    elif score <= 75: label = "탐욕"
    else: label = "극단 탐욕"
    parts = []
    if kospi is not None: parts.append(f"KOSPI {kospi:+.2f}%")
    if kosdaq is not None: parts.append(f"KOSDAQ {kosdaq:+.2f}%")
    return {"score": score, "label": label, "detail": " · ".join(parts)}

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

    etfs, pure, filtered_cnt = [], [], 0
    for s in stocks:
        if is_etf(s):
            etfs.append(s)
        elif is_risky(s):
            filtered_cnt += 1
        else:
            pure.append(s)

    pure.sort(key=lambda x: x.get("change_pct", 0), reverse=True)
    etfs.sort(key=lambda x: x.get("change_pct", 0), reverse=True)
    top30 = pure[:30]
    etf_top = etfs[:15]

    for s in top30:
        s["sector"] = classify_sector(s["name"])
        s["fibonacci"] = calc_fibonacci(s.get("high", 0), s.get("low", 0))

    # 섹터 집계 (순수종목 전체 기준)
    today_sectors = {}
    for s in pure:
        sec = classify_sector(s["name"])
        d = today_sectors.setdefault(sec, {"count": 0, "sum_pct": 0.0, "top_gainer": s["name"], "top_pct": s["change_pct"]})
        d["count"] += 1
        d["sum_pct"] += s["change_pct"]
        if s["change_pct"] > d["top_pct"]:
            d["top_gainer"], d["top_pct"] = s["name"], s["change_pct"]
    for sec, d in today_sectors.items():
        d["avg_change_pct"] = round(d.pop("sum_pct") / d["count"], 2)
        d.pop("top_pct", None)

    fear = calc_fear(raw.get("indices", {}), top30)

    result = {
        "date": date, "time": raw.get("time", ""), "timezone": "KST",
        "top30": top30, "etf_top": etf_top,
        "foreign_top": raw.get("foreign_top", []),
        "indices": raw.get("indices", {}),
        "fear": fear, "today_sectors": today_sectors,
        "filtered_risky": filtered_cnt,
    }
    with open(TOP30_OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"[OK] 순수 Top30 {len(top30)} / ETF {len(etf_top)} / 위험종목 제외 {filtered_cnt} → {TOP30_OUT}")

    # 섹터 히스토리 (최대 30거래일)
    history = []
    if SECTOR_HISTORY.exists():
        try:
            history = json.load(open(SECTOR_HISTORY, encoding="utf-8"))
        except Exception:
            history = []
    history = [h for h in history if h.get("date") != date]
    history.append({"date": date, "sectors": today_sectors})
    history = history[-30:]
    with open(SECTOR_HISTORY, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    print(f"[OK] 섹터 히스토리 {len(history)}일 보유")

if __name__ == "__main__":
    main()
