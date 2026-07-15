# fetch.py — 네이버 수집: 상승종목 + 지수 + 인기(거래량상위) + 외국인 순매수 → data/raw_market.json
import io, json, re, sys, time
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
    "Accept": "application/json, text/html;q=0.9",
    "Referer": "https://finance.naver.com/",
}

def _num(v):
    if v is None: return 0
    if isinstance(v, (int, float)): return v
    s = re.sub(r"[,%+\s원]", "", str(v))
    if s.startswith("상승") or s.startswith("하락"):
        s = s[2:]
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
        "value": _num(_pick(it, "accumulatedTradingValue", "tradingValue", "accTradingValue")),
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
            print(f"  [WARN] {market} 응답 구조 인식 실패: {str(data)[:200]}")
            break
        for it in items:
            s = _parse_stock(it, market)
            if s:
                stocks.append(s)
        time.sleep(0.4)
    return stocks

def fetch_indices():
    """지수: API 값과 자체 계산값을 대조해 신뢰도 높은 쪽 사용"""
    import ast
    out = {}
    for code in ("KOSPI", "KOSDAQ"):
        api_pct, close = None, 0
        try:
            data = _get_json(f"https://m.stock.naver.com/api/index/{code}/basic")
            if isinstance(data, dict):
                close = _num(_pick(data, "closePrice", "currentPrice", "now"))
                api_pct = float(_num(_pick(data, "fluctuationsRatio", "changeRate")))
        except Exception as e:
            print(f"  [WARN] {code} 지수 API 실패: {e}")
        calc_pct = None
        try:
            r = requests.get(f"https://api.finance.naver.com/siseJson.naver?symbol={code}"
                             f"&requestType=1&startTime=20200101&endTime=20991231&timeframe=day&count=10",
                             headers=HEADERS, timeout=12)
            rows = [x for x in ast.literal_eval(r.text.strip()) if isinstance(x, list) and len(x) >= 5
                    and not isinstance(x[1], str)]
            if len(rows) >= 2 and rows[-2][4]:
                calc_pct = round((rows[-1][4] - rows[-2][4]) / rows[-2][4] * 100, 2)
                if not close:
                    close = rows[-1][4]
        except Exception as e:
            print(f"  [WARN] {code} 지수 검산 실패: {e}")
        pct = calc_pct if calc_pct is not None else api_pct
        print(f"  [지수] {code}: API {api_pct}% / 자체계산 {calc_pct}% → 채택 {pct}%")
        if pct is not None:
            out[code] = {"close": close, "change_pct": pct}
    return out

def fetch_popular(sosok, market_name, top_n=40):
    """인기 = 거래량 상위 (finance.naver.com 고전 페이지, 안정적)"""
    try:
        tables = _read_tables(f"https://finance.naver.com/sise/sise_quant.naver?sosok={sosok}")
        for t in tables:
            cols = [str(c) for c in t.columns]
            if "종목명" in cols:
                t = t.dropna(subset=["종목명"])
                out = []
                for _, row in t.head(top_n).iterrows():
                    out.append({
                        "name": str(row["종목명"]),
                        "close": _num(row.get("현재가")),
                        "change_pct": float(_num(row.get("등락률"))),
                        "volume": _num(row.get("거래량")),
                        "value": _num(row.get("거래대금")),
                    })
                print(f"  [OK] 인기({market_name}) {len(out)}종목")
                return out
        print(f"  [WARN] 인기({market_name}) 표에 종목명 없음. 표 헤더들: {[list(map(str,t.columns))[:8] for t in tables[:4]]}")
    except Exception as e:
        print(f"  [WARN] 인기({market_name}) 실패: {e}")
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

    result = {
        "date": now.strftime("%Y-%m-%d"), "time": now.strftime("%H:%M"), "timezone": "KST",
        "total_stocks": len(records), "stocks": records,
        "indices": fetch_indices(),
        "popular": {
            "KOSPI": fetch_popular(0, "KOSPI"),
            "KOSDAQ": fetch_popular(1, "KOSDAQ"),
        },
    }
    DATA_DIR.mkdir(exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False)
    print(f"[OK] 종목 {len(records)} / 인기 KOSPI {len(result['popular']['KOSPI'])}·KOSDAQ {len(result['popular']['KOSDAQ'])}")

if __name__ == "__main__":
    main()
