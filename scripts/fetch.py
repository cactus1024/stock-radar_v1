# fetch.py — 네이버 증권(1순위) + pykrx(예비)로 당일 상승 종목 수집 → data/raw_market.json
import json, sys, time
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
OUTPUT = DATA_DIR / "raw_market.json"
KST = ZoneInfo("Asia/Seoul")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://m.stock.naver.com/",
}

def _num(v):
    """'71,200' 같은 문자열 숫자를 안전하게 변환"""
    if v is None: return 0
    if isinstance(v, (int, float)): return v
    s = str(v).replace(",", "").replace("+", "").strip()
    try:
        return float(s) if "." in s else int(s)
    except ValueError:
        return 0

def _pick(d, *keys):
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return None

def fetch_naver(market):
    """네이버 모바일 증권 API: 당일 상승률 상위 종목"""
    stocks = []
    for page in (1, 2):
        url = f"https://m.stock.naver.com/api/stocks/up/{market}?page={page}&pageSize=60"
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            print(f"  [WARN] 네이버 {market} p{page} 요청 실패: {e}")
            return stocks
        items = data.get("stocks") if isinstance(data, dict) else None
        if items is None and isinstance(data, dict):
            for v in data.values():
                if isinstance(v, list) and v and isinstance(v[0], dict):
                    items = v
                    break
        if not items:
            print(f"  [WARN] {market} 응답 구조 인식 실패. 원문 일부: {str(data)[:300]}")
            return stocks
        for it in items:
            name = _pick(it, "stockName", "itemName", "name")
            code = _pick(it, "itemCode", "stockCode", "code")
            close = _num(_pick(it, "closePrice", "currentPrice", "now"))
            if not name or not code or close == 0 or "스팩" in str(name):
                continue
            stocks.append({
                "ticker": str(code), "name": str(name), "market": market,
                "open": _num(_pick(it, "openPrice", "open")),
                "high": _num(_pick(it, "highPrice", "high")),
                "low": _num(_pick(it, "lowPrice", "low")),
                "close": close,
                "change": _num(_pick(it, "compareToPreviousClosePrice", "change")),
                "change_pct": float(_num(_pick(it, "fluctuationsRatio", "changeRate"))),
                "volume": _num(_pick(it, "accumulatedTradingVolume", "volume")),
            })
        time.sleep(0.5)
    return stocks

def fetch_pykrx_backup(date_str):
    """예비: pykrx (KRX 서버 상태에 따라 실패 가능)"""
    try:
        from pykrx import stock
        recs = []
        for market in ("KOSPI", "KOSDAQ"):
            df = stock.get_market_ohlcv(date_str, market=market)
            if df is None or df.empty:
                continue
            for t, row in df.iterrows():
                close = int(row.get("종가", 0))
                if close == 0:
                    continue
                change = int(row.get("등락폭", 0))
                prev = close - change if close - change > 0 else close
                recs.append({
                    "ticker": str(t), "name": str(t), "market": market,
                    "open": int(row.get("시가", 0)), "high": int(row.get("고가", 0)),
                    "low": int(row.get("저가", 0)), "close": close, "change": change,
                    "change_pct": round(change / prev * 100, 2) if prev else 0.0,
                    "volume": int(row.get("거래량", 0)),
                })
        return recs
    except Exception as e:
        print(f"  [WARN] pykrx 예비 수집도 실패: {e}")
        return []

def main():
    now = datetime.now(KST)
    print(f"[fetch] 수집 시작: {now.strftime('%Y-%m-%d %H:%M')} KST")

    records = []
    for market in ("KOSPI", "KOSDAQ"):
        print(f"  네이버 {market} 수집 중...")
        records += fetch_naver(market)

    if len(records) < 30:
        print("  네이버 수집 부족 → pykrx 예비 시도")
        records = fetch_pykrx_backup(now.strftime("%Y%m%d"))

    if not records:
        print("[SKIP] 데이터 없음 — 휴장일 또는 소스 장애. 정상 종료.")
        if OUTPUT.exists():
            OUTPUT.unlink()
        sys.exit(0)

    DATA_DIR.mkdir(exist_ok=True)
    result = {
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M"),
        "timezone": "KST",
        "total_stocks": len(records),
        "stocks": records,
    }
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False)
    print(f"[OK] {len(records)}개 종목 저장 → {OUTPUT}")

if __name__ == "__main__":
    main()
