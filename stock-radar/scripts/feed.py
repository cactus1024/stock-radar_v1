"""
feed.py — Gemini 3.1 Pro API로 Top30 전체 상세 피드 + 섹터 요약 생성
  - 전 30개 종목 상세 분석 (뉴스 검색 그라운딩 포함)
  - 오늘의 섹터 흐름 5줄
  - 요일별 섹터 흐름 요약
  - 실패 시 폴백 파일 생성 (파이프라인은 절대 안 깨짐)

실행: python scripts/feed.py
환경변수: GEMINI_API_KEY
"""
import json
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
TOP30_FILE = DATA_DIR / "top30.json"
SECTOR_HISTORY_FILE = DATA_DIR / "sector_history.json"
FEED_OUT = DATA_DIR / "feed.json"

KST = ZoneInfo("Asia/Seoul")


def write_fallback(reason: str):
    """피드 생성 실패 시 폴백 — 페이지는 정상 빌드됨"""
    today = datetime.now(KST).strftime("%Y-%m-%d")
    fallback = {
        "date": today,
        "status": "failed",
        "reason": reason[:200],
        "stocks": [],
        "today_sector_summary": "피드 생성 실패. 시세 데이터는 정상입니다.",
        "weekly_sector_summary": "",
    }
    with open(FEED_OUT, "w", encoding="utf-8") as f:
        json.dump(fallback, f, ensure_ascii=False, indent=2)


def build_prompt(top30_json: str, sector_history_json: str) -> str:
    """Gemini에 보낼 프롬프트 조립"""
    return f"""너는 한국 주식 데일리 브리핑 전문 분석가다.

[입력 1: 오늘 상승률 Top30 — 확정 종가 기준]
{top30_json}

[입력 2: 최근 거래일 섹터별 흐름 히스토리]
{sector_history_json}

[작업]
아래 JSON 형식으로만 응답해. 다른 텍스트 없이 순수 JSON만 출력해.

{{
  "stocks": [
    {{
      "rank": 1,
      "ticker": "종목코드",
      "name": "종목명",
      "change_pct": 5.2,
      "analysis": "3~5줄 상세 분석. 오늘 움직임 요약 + 급등 사유(반드시 오늘자 뉴스를 검색해서 근거·출처 기재). 뉴스를 못 찾으면 '사유 미확인(수급 추정)'이라고 명시.",
      "news_source": "출처 URL 또는 '미확인'"
    }}
  ],
  "today_sector_summary": "오늘의 섹터 흐름 5줄 요약. 어떤 섹터가 강했고 약했는지, 자금 흐름 추정.",
  "weekly_sector_summary": "최근 거래일(입력2 기반) 요일별 섹터 흐름 요약. 어떤 섹터가 주 초반/후반에 강세·약세였는지 트렌드 분석."
}}

[필수 규칙]
1. stocks 배열은 반드시 30개 (rank 1~30). 모든 종목을 상세 분석해.
2. analysis에 JSON의 수치를 그대로 인용해. 수치를 창작하지 마.
3. 매수/매도 추천 표현 금지. 사실과 근거만.
4. 추측은 반드시 "~추정", "~가능성"으로 표기.
5. 출력은 순수 JSON만. 마크다운 코드블록(```)으로 감싸지 마.
"""


def main():
    # 입력 파일 확인
    if not TOP30_FILE.exists():
        print("[SKIP] top30.json 없음 — 휴장일 추정. 피드 생략.")
        sys.exit(0)

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        print("[ERROR] GEMINI_API_KEY 환경변수 없음.", file=sys.stderr)
        write_fallback("API 키 미설정")
        sys.exit(0)

    # 입력 데이터 읽기
    with open(TOP30_FILE, encoding="utf-8") as f:
        top30_data = f.read()

    sector_history = "[]"
    if SECTOR_HISTORY_FILE.exists():
        with open(SECTOR_HISTORY_FILE, encoding="utf-8") as f:
            sector_history = f.read()

    prompt = build_prompt(top30_data, sector_history)

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)

        response = client.models.generate_content(
            model="gemini-3.1-pro-preview",
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=0.3,  # 낮은 온도 = 안정적 출력
            ),
        )

        raw_text = response.text
        if not raw_text or len(raw_text) < 100:
            raise ValueError(f"응답이 비정상적으로 짧음 ({len(raw_text or '')}자)")

        # JSON 파싱 (마크다운 코드블록 제거)
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        feed_data = json.loads(cleaned)

        # 최소 검증: stocks 배열이 있는지
        if "stocks" not in feed_data or not isinstance(feed_data["stocks"], list):
            raise ValueError("응답에 stocks 배열 없음")

        # 날짜 메타데이터 추가
        feed_data["date"] = datetime.now(KST).strftime("%Y-%m-%d")
        feed_data["status"] = "ok"
        feed_data["generated_at"] = datetime.now(KST).strftime("%H:%M KST")

        with open(FEED_OUT, "w", encoding="utf-8") as f:
            json.dump(feed_data, f, ensure_ascii=False, indent=2)

        stock_count = len(feed_data["stocks"])
        print(f"[OK] feed.json 생성 완료 — {stock_count}개 종목 분석")

    except json.JSONDecodeError as e:
        print(f"[ERROR] JSON 파싱 실패: {e}", file=sys.stderr)
        # 원문 저장 (디버깅용)
        debug_path = DATA_DIR / "feed_debug_raw.txt"
        with open(debug_path, "w", encoding="utf-8") as f:
            f.write(raw_text if 'raw_text' in dir() else "응답 없음")
        write_fallback(f"JSON 파싱 실패: {str(e)[:100]}")
        sys.exit(0)

    except Exception as e:
        print(f"[ERROR] 피드 생성 실패: {e}", file=sys.stderr)
        write_fallback(str(e)[:200])
        sys.exit(0)  # 실패해도 파이프라인은 계속!


if __name__ == "__main__":
    main()
