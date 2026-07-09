# feed.py — Gemini 피드 v3: 모델체인(3.5-flash 우선) + 실전 인사이트 프롬프트 + 요일별 요약 보정
import json, os, sys
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
TOP30_FILE = DATA_DIR / "top30.json"
SECTOR_HISTORY_FILE = DATA_DIR / "sector_history.json"
FEED_OUT = DATA_DIR / "feed.json"
KST = ZoneInfo("Asia/Seoul")

MODEL_CHAIN = ["gemini-3.5-flash", "gemini-3.1-pro-preview", "gemini-2.5-flash"]

def write_fallback(reason):
    today = datetime.now(KST).strftime("%Y-%m-%d")
    json.dump({"date": today, "status": "failed", "reason": str(reason)[:300], "stocks": [],
               "today_sector_summary": "피드 생성 실패. 시세 데이터는 정상입니다.",
               "weekly_sector_summary": ""},
              open(FEED_OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

def build_prompt(top30, history):
    return f"""너는 10년차 한국 단타/스윙 트레이더 출신 애널리스트다. 뜬구름 없는 실전 브리핑만 쓴다.

[입력 1: 오늘 상승률 Top30 — 정량 데이터 포함]
각 종목에 이미 계산된 필드: swing_high/swing_low(최근 20일 스윙 고/저점), patterns(양음양·트랩 감지),
trading_value(당일 거래대금), big_money(대금 1000억+), theme_streak(테마 연속 부각일), theme_leader(섹터 대장주), alerts(투자경고 등)
{json.dumps(top30, ensure_ascii=False)}

[입력 2: 최근 거래일 섹터 히스토리]
{json.dumps(history, ensure_ascii=False)}

[작업] 순수 JSON만 응답 (코드블록 금지):
{{
  "stocks": [
    {{"rank": 1, "ticker": "코드", "name": "종목명", "change_pct": 5.2,
      "headline": "오늘자 핵심 뉴스 헤드라인 1줄 (검색 필수, 미발견 시 '뉴스 미확인')",
      "analysis": "4~6줄. ①급등 사유(뉴스 근거) ②수급 해석(거래대금·회전율·패턴 필드 활용: '대금 1500억 실림 = 세력 개입 흔적' 식) ③테마 맥락(대장주 대비 위치, 연속 D+n일차)",
      "insight": "실전 코멘트 2~3줄. 예: '추격 금지, 스윙로우 {{swing_low}}원 지지 확인 후 눌림목 대기. 이탈 시 손절 엄수.' / '3일차 순환 막바지 — 대장주 꺾이면 동반 급락 주의.' 구체적 가격 레벨(스윙/피보나치)을 반드시 언급.",
      "news_source": "URL 또는 '미확인'"}}
  ],
  "today_sector_summary": "오늘의 섹터 흐름 5줄: 주도 섹터, 자금 이동, 대장주 동향",
  "weekly_sector_summary": "입력2의 날짜별 데이터를 비교해 순환매 패턴 분석. 오늘 요약과 다른 관점(여러 날의 흐름)이어야 함."
}}

[규칙] 1)30종목 전부 2)입력 수치만 인용 3)매수/매도 직접 추천 금지, '~시나리오/주의' 화법 4)추측은 '추정' 표기 5)alerts 있는 종목은 insight에 경고 리스크 반드시 언급.
"""

def main():
    if not TOP30_FILE.exists():
        print("[SKIP] top30.json 없음."); sys.exit(0)
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        write_fallback("API 키 미설정"); sys.exit(0)

    data = json.load(open(TOP30_FILE, encoding="utf-8"))
    top30 = data.get("top30", [])
    keep = ("ticker", "name", "market", "close", "change_pct", "volume", "sector",
            "swing_high", "swing_low", "patterns", "trading_value", "big_money",
            "turnover_pct", "theme_streak", "theme_leader", "alerts", "fibonacci")
    slim = [{k: s[k] for k in keep if k in s} for s in top30]
    history_days = data.get("history_days", 1)
    history = []
    if SECTOR_HISTORY_FILE.exists():
        try: history = json.load(open(SECTOR_HISTORY_FILE, encoding="utf-8"))[-5:]
        except Exception: history = []

    from google import genai
    from google.genai import types
    client = genai.Client(api_key=api_key)

    raw_text, last_err = None, None
    for model in MODEL_CHAIN:
        try:
            print(f"[TRY] 모델: {model}")
            resp = client.models.generate_content(
                model=model, contents=build_prompt(slim, history),
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                    temperature=0.3,
                ),
            )
            raw_text = resp.text
            if not raw_text or len(raw_text) < 100:
                raise ValueError("응답이 비정상적으로 짧음")
            cleaned = raw_text.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            feed = json.loads(cleaned.strip())
            if not isinstance(feed.get("stocks"), list):
                raise ValueError("stocks 배열 없음")

            # 히스토리 3일 미만이면 요일별 요약은 축적 안내로 강제 교체 (중복 방지)
            if history_days < 3:
                feed["weekly_sector_summary"] = (
                    f"📊 섹터 히스토리 축적 중 (현재 {history_days}일차). "
                    f"3거래일치가 쌓이는 시점부터 요일별 순환매 흐름 분석이 자동으로 시작됩니다.")

            feed.update({"date": datetime.now(KST).strftime("%Y-%m-%d"), "status": "ok",
                         "model": model, "generated_at": datetime.now(KST).strftime("%H:%M KST")})
            json.dump(feed, open(FEED_OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
            print(f"[OK] feed.json — {len(feed['stocks'])}종목, 모델={model}")
            return
        except Exception as e:
            last_err = e
            print(f"[FAIL] {model}: {type(e).__name__}: {e}", file=sys.stderr)
            if raw_text:
                (DATA_DIR / "feed_debug_raw.txt").write_text(raw_text[:5000], encoding="utf-8")

    write_fallback(f"{type(last_err).__name__}: {last_err}")
    sys.exit(0)

if __name__ == "__main__":
    main()
