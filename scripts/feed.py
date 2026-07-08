# feed.py — Gemini API로 Top30 전체 상세 피드 생성 (모델 자동 폴백 체인 내장)
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

# 1순위 실패 시 자동으로 다음 모델 시도 (권한/한도 문제 자가 복구)
MODEL_CHAIN = ["gemini-3.1-pro-preview", "gemini-3-pro-preview", "gemini-2.5-flash"]

def write_fallback(reason):
    today = datetime.now(KST).strftime("%Y-%m-%d")
    json.dump({"date": today, "status": "failed", "reason": str(reason)[:300], "stocks": [],
               "today_sector_summary": "피드 생성 실패. 시세 데이터는 정상입니다.",
               "weekly_sector_summary": ""},
              open(FEED_OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

def build_prompt(top30_list, sector_history):
    return f"""너는 한국 주식 데일리 브리핑 전문 분석가다.

[입력 1: 오늘 상승률 Top30 — 확정 종가 기준]
{json.dumps(top30_list, ensure_ascii=False)}

[입력 2: 최근 거래일 섹터별 흐름 히스토리]
{json.dumps(sector_history, ensure_ascii=False)}

[작업] 아래 JSON 형식으로만 응답. 다른 텍스트/코드블록 없이 순수 JSON만.
{{
  "stocks": [
    {{"rank": 1, "ticker": "코드", "name": "종목명", "change_pct": 5.2,
      "analysis": "3~5줄 상세 분석. 오늘 움직임 요약 + 급등 사유(오늘자 뉴스를 검색해 근거·출처 기재). 뉴스 미발견 시 '사유 미확인(수급 추정)' 명시.",
      "news_source": "출처 URL 또는 '미확인'"}}
  ],
  "today_sector_summary": "오늘의 섹터 흐름 5줄 요약",
  "weekly_sector_summary": "입력2 기반 최근 거래일별 섹터 순환 흐름 요약"
}}

[필수 규칙]
1. stocks는 반드시 30개 전부(rank 1~30) 상세 분석.
2. 입력 JSON의 수치만 인용, 수치 창작 금지.
3. 매수/매도 추천 금지. 추측은 "추정" 표기.
"""

def main():
    if not TOP30_FILE.exists():
        print("[SKIP] top30.json 없음 — 휴장일 추정. 피드 생략.")
        sys.exit(0)
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        print("[ERROR] GEMINI_API_KEY 환경변수 없음.", file=sys.stderr)
        write_fallback("API 키 미설정")
        sys.exit(0)

    data = json.load(open(TOP30_FILE, encoding="utf-8"))
    top30 = data.get("top30", [])
    slim = [{k: s.get(k) for k in ("ticker", "name", "market", "close", "change_pct", "volume", "sector")} for s in top30]
    history = []
    if SECTOR_HISTORY_FILE.exists():
        try:
            history = json.load(open(SECTOR_HISTORY_FILE, encoding="utf-8"))[-5:]
        except Exception:
            history = []

    prompt = build_prompt(slim, history)
    raw_text = None

    from google import genai
    from google.genai import types
    client = genai.Client(api_key=api_key)

    last_err = None
    for model in MODEL_CHAIN:
        try:
            print(f"[TRY] 모델: {model}")
            resp = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                    temperature=0.3,
                ),
            )
            raw_text = resp.text
            if not raw_text or len(raw_text) < 100:
                raise ValueError(f"응답이 비정상적으로 짧음 ({len(raw_text or '')}자)")

            cleaned = raw_text.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            feed = json.loads(cleaned.strip())
            if "stocks" not in feed or not isinstance(feed["stocks"], list):
                raise ValueError("응답에 stocks 배열 없음")

            feed["date"] = datetime.now(KST).strftime("%Y-%m-%d")
            feed["status"] = "ok"
            feed["model"] = model
            feed["generated_at"] = datetime.now(KST).strftime("%H:%M KST")
            json.dump(feed, open(FEED_OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
            print(f"[OK] feed.json 생성 — {len(feed['stocks'])}종목, 모델={model}")
            return
        except Exception as e:
            last_err = e
            print(f"[FAIL] {model}: {type(e).__name__}: {e}", file=sys.stderr)
            if raw_text:
                (DATA_DIR / "feed_debug_raw.txt").write_text(raw_text[:5000], encoding="utf-8")

    print(f"[ERROR] 전 모델 실패. 마지막 오류: {last_err}", file=sys.stderr)
    write_fallback(f"{type(last_err).__name__}: {last_err}")
    sys.exit(0)  # 실패해도 파이프라인 계속

if __name__ == "__main__":
    main()
