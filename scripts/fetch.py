# fetch.py — 네이버 증권 API 수집: 상승종목 + 지수 + 외국인 순매수 → data/raw_market.json
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

def _get_json(url):
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    return r.json()

def _find_list(data):
    """응답에서 종목 리스트를 방어적으로 탐색"""
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return data
    if isinstance(data, dict):
        for key in ("stocks", "items", "result", "datas", "list"):
            v = data.get(key)
            if isinstance(v, list) and v and isinstance(v[0], dict):
                return v
        for v in data.values():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                return v
    return None

def _parse_stock(it, market):
    name = _pick(it, "stockName", "itemName", "name")
    code = _pick(it, "itemCode", "stockCode", "code")
    close = _num(_pick(it, "closePrice", "currentPrice", "now", "tradePrice"))
    if not name or not code or close == 0:
        return None
    return {
        "ticker": str(code), "name": str(name), "market": market,
        "open": _num(_pick(it, "openPrice", "open")),
        "high": _num(_pick(it, "highPrice", "high")),
        "low": _num(_pick(it, "lowPrice", "low")),
        "close": close,
        "change": _num(_pick(it, "compareToPreviousClosePrice", "change")),
        "change_pct": float(_num(_pick(it, "fluctuationsRatio", "changeRate", "fluctuationRatio"))),
        "volume": _num(_pick(it, "accumulatedTradingVolume", "volume", "tradingVolume")),
        "stock_type": str(_pick(it, "stockType", "stockTypeCode") or ""),
    }

def fetch_risers(market):
    stocks = []
    for page in (1, 2):
        try:
            data = _get_json(f"https://m.stock.naver.com/api/stocks/up/{market}?page={page}&pageSize=60")
        except Exception as e:
            print(f"  [WARN] {market} 상승종목 p{page} 실패: {e}")
            break
        items = _find_list(data)
        if not items:
            print(f"  [WARN] {market} 응답 구조 인식 실패. 원문: {str(data)[:300]}")
            break
        for it in items:
            s = _parse_stock(it, market)
            if s:
                stocks.append(s)
        time.sleep(0.4)
    return stocks

def fetch_indices():
    """코스피/코스닥 지수 (간이 공포지수 계산용)"""
    out = {}
    for code in ("KOSPI", "KOSDAQ"):
        try:
            data = _get_json(f"https://m.stock.naver.com/api/index/{code}/basic")
            if isinstance(data, dict):
                out[code] = {
                    "close": _num(_pick(data, "closePrice", "currentPrice", "now")),
                    "change_pct": float(_num(_pick(data, "fluctuationsRatio", "changeRate"))),
                }
        except Exception as e:
            print(f"  [WARN] {code} 지수 수집 실패: {e}")
    return out

def fetch_foreign():
    """외국인 순매수 상위 — 엔드포인트 후보를 순차 시도 (실패해도 파이프라인 계속)"""
    candidates = [
        "https://m.stock.naver.com/api/stocks/foreign/KOSPI?page=1&pageSize=15",
        "https://m.stock.naver.com/api/stocks/foreigner/KOSPI?page=1&pageSize=15",
        "https://m.stock.naver.com/api/stocks/investorTrend/foreign?page=1&pageSize=15",
    ]
    for url in candidates:
        try:
            data = _get_json(url)
            items = _find_list(data)
            if items:
                parsed = [s for s in (_parse_stock(it, "KOSPI") for it in items) if s]
                if parsed:
                    print(f"  [OK] 외국인 데이터 확보 ({url.split('/api/')[1].split('?')[0]})")
                    return parsed[:15]
            print(f"  [WARN] 외국인 후보 구조 불일치: {str(data)[:200]}")
        except Exception as e:
            print(f"  [WARN] 외국인 후보 실패({url.split('?')[0][-30:]}): {e}")
    return []

def main():
    now = datetime.now(KST)
    print(f"[fetch] 수집 시작: {now.strftime('%Y-%m-%d %H:%M')} KST")

    records = []
    for market in ("KOSPI", "KOSDAQ"):
        print(f"  네이버 {market} 상승종목 수집...")
        records += fetch_risers(market)

    if not records:
        print("[SKIP] 데이터 없음 — 휴장일 또는 소스 장애. 정상 종료.")
        if OUTPUT.exists():
            OUTPUT.unlink()
        sys.exit(0)

    indices = fetch_indices()
    foreign = fetch_foreign()

    DATA_DIR.mkdir(exist_ok=True)
    result = {
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M"),
        "timezone": "KST",
        "total_stocks": len(records),
        "stocks": records,
        "indices": indices,
        "foreign_top": foreign,
    }
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False)
    print(f"[OK] 종목 {len(records)}개 / 지수 {len(indices)}개 / 외국인 {len(foreign)}개 저장")

if __name__ == "__main__":
    main()
