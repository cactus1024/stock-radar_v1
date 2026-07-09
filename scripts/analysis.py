# analysis.py — 분석 v3: ETF분리·위험필터·스윙/패턴·거래대금 배지·경고딱지·테마추적·시장온도계
import json, sys, time, ast
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
INPUT = DATA_DIR / "raw_market.json"
TOP30_OUT = DATA_DIR / "top30.json"
SECTOR_HISTORY = DATA_DIR / "sector_history.json"
KST = ZoneInfo("Asia/Seoul")

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0 Safari/537.36",
           "Referer": "https://m.stock.naver.com/"}

ETF_KEYWORDS = ["KODEX", "TIGER", "RISE", "KBSTAR", "ACE", "SOL", "PLUS", "ARIRANG",
                "HANARO", "KOSEF", "KIWOOM", "WON", "히어로즈", "마이다스", "TIMEFOLIO",
                "에셋플러스", "KoAct", "BNK", "UNICORN", "1Q", "FOCUS", "ETN", "레버리지",
                "인버스", "합성", "TRF", "TDF", "채권", "선물", "커버드콜", "액티브"]

SECTOR_KEYWORDS = {
    "반도체": ["반도체", "하이닉스", "삼성전자", "메모리", "실리콘", "웨이퍼", "칩스", "테크윙", "HPSP", "이오테크", "주성", "피에스케이"],
    "2차전지": ["배터리", "2차전지", "에코프로", "포스코퓨처", "양극재", "음극재", "리튬", "전해", "엘앤에프", "코스모신소재"],
    "바이오/제약": ["바이오", "제약", "셀트리온", "신약", "헬스", "의료", "진단", "팜", "메디", "테라퓨틱스", "사이언스", "펩트"],
    "자동차/부품": ["자동차", "현대차", "기아", "모비스", "부품", "모터"],
    "금융": ["은행", "증권", "보험", "캐피탈", "금융", "카드", "지주"],
    "건설/기계": ["건설", "기계", "중공업", "엔지니어링"],
    "IT/게임/엔터": ["소프트", "네이버", "카카오", "NHN", "게임", "엔터", "플랫폼", "위버스", "하이브", "JYP", "크래프톤"],
    "에너지/원전": ["에너지", "한전", "가스", "석유", "태양", "풍력", "원전", "원자력", "SMR", "두산에너"],
    "철강/화학": ["철강", "화학", "포스코", "LG화학", "롯데케미칼"],
    "조선/방산": ["조선", "방산", "한화에어로", "HD현대", "한화오션", "LIG", "풍산", "현대로템", "STX"],
    "로봇/AI": ["로봇", "로보", "AI", "인공지능", "레인보우", "두산로보", "딥노이드"],
    "우주/항공": ["우주", "항공", "위성", "에어로", "쎄트렉"],
}

def classify_sector(name):
    for sector, kws in SECTOR_KEYWORDS.items():
        if any(k.lower() in name.lower() for k in kws):
            return sector
    return "기타"

def is_etf(s):
    if str(s.get("stock_type", "")).lower() in ("etf", "etn"):
        return True
    return any(k.lower() in s["name"].lower() for k in ETF_KEYWORDS)

def is_risky(s):
    t = s.get("ticker", "")
    if t and t[-1] != "0": return True            # 우선주 계열
    if s.get("close", 0) < 1000: return True       # 동전주
    if "스팩" in s.get("name", ""): return True
    tv = s.get("value", 0) or s.get("close", 0) * s.get("volume", 0)
    if tv < 500_000_000: return True               # 거래대금 5억 미만
    return False

def calc_fibonacci(high, low):
    if not high or not low or high <= low: return {}
    d = high - low
    return {"저점": low, "38.2%": round(low + d * 0.382), "50.0%": round(low + d * 0.5),
            "61.8%": round(low + d * 0.618), "고점": high}

# ---------- 종목 심층 데이터 (히스토리·패턴·경고) ----------

def fetch_history(ticker, days=90):
    """네이버 일봉: [날짜,시가,고가,저가,종가,거래량,외국인소진율]"""
    end = datetime.now(KST).strftime("%Y%m%d")
    start = (datetime.now(KST) - timedelta(days=days)).strftime("%Y%m%d")
    url = (f"https://api.finance.naver.com/siseJson.naver?symbol={ticker}"
           f"&requestType=1&startTime={start}&endTime={end}&timeframe=day")
    r = requests.get(url, headers=HEADERS, timeout=12)
    r.raise_for_status()
    rows = ast.literal_eval(r.text.strip())
    out = []
    for row in rows[1:]:
        try:
            out.append({"date": str(row[0]), "open": float(row[1]), "high": float(row[2]),
                        "low": float(row[3]), "close": float(row[4]), "volume": float(row[5])})
        except Exception:
            continue
    return out

def analyze_history(s, hist):
    """스윙 고/저점, 양음양·트랩 패턴"""
    today_str = datetime.now(KST).strftime("%Y%m%d")
    completed = [h for h in hist if h["date"] != today_str]
    if len(completed) < 5:
        return
    recent = completed[-20:]
    s["swing_high"] = round(max(h["high"] for h in recent))
    s["swing_low"] = round(min(h["low"] for h in recent))
    prev = completed[-1]
    o, c, lo = s.get("open", 0), s.get("close", 0), s.get("low", 0)
    patterns = []
    if prev["close"] < prev["open"] and c > o and c > prev["open"]:
        patterns.append("양음양(음봉 장악)")
    if lo and lo < prev["low"] and c > prev["close"]:
        patterns.append("트랩 반등(전저 이탈 후 회복)")
    if patterns:
        s["patterns"] = patterns

def _find_shares(obj):
    """응답 JSON에서 상장주식수로 추정되는 키 탐색"""
    if isinstance(obj, dict):
        for k, v in obj.items():
            kl = k.lower()
            if any(x in kl for x in ("listedshare", "totalshare", "sharesoutstanding", "listedstockcount")):
                try:
                    n = float(str(v).replace(",", ""))
                    if n > 100_000: return n
                except Exception: pass
            r = _find_shares(v)
            if r: return r
    elif isinstance(obj, list):
        for v in obj:
            r = _find_shares(v)
            if r: return r
    return None

def fetch_alerts_and_shares(ticker):
    """경고 딱지(키워드 스캔) + 상장주식수 탐색"""
    tags, shares = [], None
    for endpoint in ("basic", "integration"):
        try:
            r = requests.get(f"https://m.stock.naver.com/api/stock/{ticker}/{endpoint}",
                             headers=HEADERS, timeout=10)
            text = r.text
            for kw in ("투자위험", "투자경고", "투자주의", "단기과열", "거래정지", "관리종목"):
                if kw in text and kw not in tags:
                    tags.append(kw)
            if shares is None:
                try: shares = _find_shares(r.json())
                except Exception: pass
        except Exception as e:
            print(f"  [WARN] {ticker} {endpoint} 조회 실패: {e}")
    return tags, shares

def enrich_top30(top30):
    import os
    if os.environ.get("SKIP_ENRICH"):
        print("[enrich] SKIP_ENRICH 설정 — 심층 수집 생략")
        return
    print(f"[enrich] Top30 심층 데이터 수집 (히스토리/경고/회전율)...")
    for s in top30:
        t = s["ticker"]
        try:
            hist = fetch_history(t)
            analyze_history(s, hist)
        except Exception as e:
            print(f"  [WARN] {t} 히스토리 실패: {e}")
        tags, shares = fetch_alerts_and_shares(t)
        if tags: s["alerts"] = tags
        tv = s.get("value", 0) or s.get("close", 0) * s.get("volume", 0)
        s["trading_value"] = int(tv)
        s["big_money"] = tv >= 100_000_000_000        # 거래대금 1,000억+
        if shares:
            s["turnover_pct"] = round(s.get("volume", 0) / shares * 100, 1)
            s["high_turnover"] = s["turnover_pct"] >= 100
        time.sleep(0.3)

# ---------- 시장 온도계 v2 (다요인) ----------

def calc_fear(indices, top30, pure_all):
    kospi = indices.get("KOSPI", {}).get("change_pct")
    kosdaq = indices.get("KOSDAQ", {}).get("change_pct")
    if kospi is None and kosdaq is None:
        return None
    score, parts = 50.0, []
    if kospi is not None:
        score += float(kospi) * 8; parts.append(f"KOSPI {float(kospi):+.2f}%")
    if kosdaq is not None:
        score += float(kosdaq) * 5; parts.append(f"KOSDAQ {float(kosdaq):+.2f}%")
    limit_up = sum(1 for s in pure_all if s.get("change_pct", 0) >= 29.0)
    score += min(limit_up * 1.5, 9)
    parts.append(f"상한가 {limit_up}개")
    big = sum(1 for s in top30 if (s.get("value", 0) or s.get("close",0)*s.get("volume",0)) >= 100_000_000_000)
    score += min(big * 1.0, 6)
    parts.append(f"대금1000억+ {big}개")
    score = max(0, min(100, round(score)))
    label = ("극단 공포" if score <= 20 else "공포" if score <= 40 else
             "중립" if score <= 60 else "탐욕" if score <= 80 else "극단 탐욕")
    return {"score": score, "label": label, "detail": " · ".join(parts)}

# ---------- 테마 연속성 ----------

def theme_streaks(history, today_sectors):
    """섹터별 연속 부각 일수 (부각 = 그날 3종목 이상 상승권 진입)"""
    streaks = {}
    for sec in today_sectors:
        n = 0
        for day in reversed(history):
            if day.get("sectors", {}).get(sec, {}).get("count", 0) >= 3:
                n += 1
            else:
                break
        streaks[sec] = max(n, 1)
    return streaks

def main():
    if not INPUT.exists():
        print("[SKIP] raw_market.json 없음. 휴장일 추정."); sys.exit(0)
    raw = json.load(open(INPUT, encoding="utf-8"))
    stocks = raw.get("stocks", [])
    if not stocks:
        print("[SKIP] 종목 데이터 비어 있음."); sys.exit(0)

    date = raw.get("date", datetime.now(KST).strftime("%Y-%m-%d"))

    etfs, pure, filtered_cnt = [], [], 0
    for s in stocks:
        if is_etf(s): etfs.append(s)
        elif is_risky(s): filtered_cnt += 1
        else: pure.append(s)

    pure.sort(key=lambda x: x.get("change_pct", 0), reverse=True)
    etfs.sort(key=lambda x: x.get("change_pct", 0), reverse=True)
    top30, etf_top = pure[:30], etfs[:15]

    for s in top30:
        s["sector"] = classify_sector(s["name"])
        s["fibonacci"] = calc_fibonacci(s.get("high", 0), s.get("low", 0))

    # 섹터 집계 + 대장주(섹터 내 거래대금 1위)
    today_sectors, leaders = {}, {}
    for s in pure:
        sec = classify_sector(s["name"])
        tv = s.get("value", 0) or s.get("close", 0) * s.get("volume", 0)
        d = today_sectors.setdefault(sec, {"count": 0, "sum": 0.0, "top_gainer": s["name"], "tp": s["change_pct"]})
        d["count"] += 1; d["sum"] += s["change_pct"]
        if s["change_pct"] > d["tp"]: d["top_gainer"], d["tp"] = s["name"], s["change_pct"]
        if sec not in leaders or tv > leaders[sec][1]:
            leaders[sec] = (s["name"], tv)
    for sec, d in today_sectors.items():
        d["avg_change_pct"] = round(d.pop("sum") / d["count"], 2); d.pop("tp", None)
        d["leader"] = leaders.get(sec, ("", 0))[0]

    # 히스토리 로드 → 테마 지속일
    history = []
    if SECTOR_HISTORY.exists():
        try: history = json.load(open(SECTOR_HISTORY, encoding="utf-8"))
        except Exception: history = []
    history = [h for h in history if h.get("date") != date]
    streaks = theme_streaks(history + [{"date": date, "sectors": today_sectors}], today_sectors)
    for sec, d in today_sectors.items():
        d["streak_days"] = streaks.get(sec, 1)
    for s in top30:
        sec = s["sector"]
        s["theme_streak"] = streaks.get(sec, 1)
        s["theme_leader"] = leaders.get(sec, ("", 0))[0]

    # 심층 수집 (실패해도 진행)
    enrich_top30(top30)

    fear = calc_fear(raw.get("indices", {}), top30, pure)

    result = {"date": date, "time": raw.get("time", ""), "timezone": "KST",
              "top30": top30, "etf_top": etf_top,
              "foreign_top": raw.get("foreign_top", []),
              "indices": raw.get("indices", {}), "fear": fear,
              "today_sectors": today_sectors, "filtered_risky": filtered_cnt,
              "history_days": len(history) + 1}
    json.dump(result, open(TOP30_OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"[OK] Top30 {len(top30)} / ETF {len(etf_top)} / 제외 {filtered_cnt} / 히스토리 {len(history)+1}일")

    history.append({"date": date, "sectors": today_sectors})
    json.dump(history[-30:], open(SECTOR_HISTORY, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
