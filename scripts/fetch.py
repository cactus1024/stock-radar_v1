"""
fetch.py — KRX 전 종목 시세 수집 → data/raw_market.json
실행: python scripts/fetch.py
의존성: pykrx, pandas
"""
import json
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

# 프로젝트 루트 기준 경로
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
OUTPUT = DATA_DIR / "raw_market.json"

KST = ZoneInfo("Asia/Seoul")
MAX_RETRIES = 3
RETRY_DELAY = 10  # 초


def fetch_with_retry(func, *args, retries=MAX_RETRIES, **kwargs):
    """네트워크 오류 시 재시도"""
    for attempt in range(1, retries + 1):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            print(f"  [시도 {attempt}/{retries}] 오류: {e}", file=sys.stderr)
            if attempt < retries:
                time.sleep(RETRY_DELAY)
    return None


def get_ticker_name_map(date_str, market):
    """종목코드 → 종목명 매핑"""
    from pykrx import stock
    tickers = stock.get_market_ticker_list(date_str, market=market)
    return {t: stock.get_market_ticker_name(t) for t in tickers}


def main():
    from pykrx import stock

    now = datetime.now(KST)
    today_str = now.strftime("%Y%m%d")
    print(f"[fetch] 수집 시작: {now.strftime('%Y-%m-%d %H:%M KST')}")

    # KOSPI 수집
    print("  KOSPI 수집 중...")
    df_kospi = fetch_with_retry(stock.get_market_ohlcv, today_str, market="KOSPI")
    if df_kospi is None or df_kospi.empty:
        # KOSDAQ도 시도해서 둘 다 비면 휴장일
        df_kosdaq = fetch_with_retry(stock.get_market_ohlcv, today_str, market="KOSDAQ")
        if df_kosdaq is None or df_kosdaq.empty:
            print("[SKIP] 데이터 없음 — 휴장일 가능성. 정상 종료.")
            sys.exit(0)
    else:
        print("  KOSDAQ 수집 중...")
        df_kosdaq = fetch_with_retry(stock.get_market_ohlcv, today_str, market="KOSDAQ")

    # 종목명 매핑
    print("  종목명 매핑 중...")
    names_kospi = fetch_with_retry(get_ticker_name_map, today_str, "KOSPI") or {}
    names_kosdaq = fetch_with_retry(get_ticker_name_map, today_str, "KOSDAQ") or {}
    all_names = {**names_kospi, **names_kosdaq}

    # 데이터 합치기
    records = []
    for market_name, df in [("KOSPI", df_kospi), ("KOSDAQ", df_kosdaq)]:
        if df is None or df.empty:
            continue
        for ticker, row in df.iterrows():
            close = int(row.get("종가", 0))
            if close == 0:
                continue  # 거래정지 등 제외
            change = int(row.get("등락폭", 0))
            volume = int(row.get("거래량", 0))
            open_p = int(row.get("시가", 0))
            high = int(row.get("고가", 0))
            low = int(row.get("저가", 0))
            prev_close = close - change if close - change > 0 else close
            change_pct = round((change / prev_close) * 100, 2) if prev_close > 0 else 0.0

            records.append({
                "ticker": ticker,
                "name": all_names.get(ticker, "알수없음"),
                "market": market_name,
                "open": open_p,
                "high": high,
                "low": low,
                "close": close,
                "change": change,
                "change_pct": change_pct,
                "volume": volume,
            })

    if not records:
        print("[SKIP] 유효한 종목 데이터 없음. 정상 종료.")
        sys.exit(0)

    result = {
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M"),
        "timezone": "KST",
        "total_stocks": len(records),
        "stocks": records,
    }

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"[OK] {len(records)}개 종목 저장 → {OUTPUT}")


if __name__ == "__main__":
    main()
