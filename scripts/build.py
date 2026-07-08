"""
build.py — top30.json + feed.json → docs/index.html 생성
  - Top10: 메인 카드 (전체 분석 내용 바로 표시)
  - 11~30위: 아코디언 리스트 (클릭하면 상세 분석 펼침)
  - 섹터 흐름: 오늘 + 요일별 요약

실행: python scripts/build.py
"""
import json
import sys
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from jinja2 import Template

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DOCS_DIR = ROOT / "docs"
DOCS_DIR.mkdir(exist_ok=True)

TOP30_FILE = DATA_DIR / "top30.json"
FEED_FILE = DATA_DIR / "feed.json"
OUTPUT = DOCS_DIR / "index.html"

KST = ZoneInfo("Asia/Seoul")

# ────────────────────────────────────────
# HTML 템플릿 (인라인 — 별도 파일 관리 불필요)
# ────────────────────────────────────────
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>주식레이더</title>
<style>
  :root {
    --bg: #0f1117;
    --surface: #1a1d27;
    --surface2: #242836;
    --text: #e4e6f0;
    --text-dim: #8b8fa3;
    --accent: #6c9bff;
    --up: #ef4444;
    --down: #3b82f6;
    --border: #2d3143;
    --radius: 10px;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: -apple-system, 'Pretendard', sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
    min-height: 100vh;
  }
  .container { max-width: 720px; margin: 0 auto; padding: 20px 16px; }

  /* 헤더 */
  header {
    text-align: center;
    padding: 24px 0 16px;
    border-bottom: 1px solid var(--border);
    margin-bottom: 20px;
  }
  header h1 { font-size: 1.5rem; font-weight: 700; letter-spacing: -0.5px; }
  header .meta { color: var(--text-dim); font-size: 0.82rem; margin-top: 6px; }

  /* 탭 */
  .tabs {
    display: flex;
    gap: 4px;
    margin-bottom: 20px;
    border-bottom: 2px solid var(--border);
    overflow-x: auto;
  }
  .tab-btn {
    background: none; border: none; color: var(--text-dim);
    padding: 10px 16px; cursor: pointer; font-size: 0.9rem;
    border-bottom: 2px solid transparent;
    white-space: nowrap; transition: all 0.2s;
  }
  .tab-btn.active { color: var(--accent); border-bottom-color: var(--accent); }
  .tab-content { display: none; }
  .tab-content.active { display: block; }

  /* 종목 카드 (Top10) */
  .stock-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 16px;
    margin-bottom: 12px;
  }
  .stock-card .header-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 10px;
  }
  .stock-card .rank {
    background: var(--accent);
    color: #fff;
    width: 28px; height: 28px;
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 0.8rem; font-weight: 700;
    flex-shrink: 0;
  }
  .stock-card .name { font-weight: 600; font-size: 1rem; margin-left: 10px; flex: 1; }
  .stock-card .change { font-weight: 700; font-size: 1rem; }
  .stock-card .change.up { color: var(--up); }
  .stock-card .change.down { color: var(--down); }
  .stock-card .analysis {
    color: var(--text-dim);
    font-size: 0.85rem;
    line-height: 1.7;
    white-space: pre-wrap;
  }
  .stock-card .source {
    font-size: 0.75rem;
    color: var(--accent);
    margin-top: 8px;
    word-break: break-all;
  }

  /* 아코디언 (11~30위) */
  .accordion-item {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    margin-bottom: 6px;
    overflow: hidden;
  }
  .accordion-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 16px;
    cursor: pointer;
    transition: background 0.2s;
  }
  .accordion-header:hover { background: var(--surface2); }
  .accordion-header .left {
    display: flex; align-items: center; gap: 10px;
  }
  .accordion-header .rank-sm {
    color: var(--text-dim);
    font-size: 0.8rem;
    min-width: 24px;
  }
  .accordion-header .name { font-size: 0.9rem; }
  .accordion-header .arrow {
    color: var(--text-dim);
    transition: transform 0.2s;
    font-size: 0.8rem;
  }
  .accordion-item.open .arrow { transform: rotate(180deg); }
  .accordion-body {
    max-height: 0;
    overflow: hidden;
    transition: max-height 0.3s ease;
  }
  .accordion-item.open .accordion-body { max-height: 400px; }
  .accordion-body-inner {
    padding: 0 16px 16px;
    font-size: 0.85rem;
    color: var(--text-dim);
    line-height: 1.7;
    white-space: pre-wrap;
  }
  .accordion-body-inner .source {
    font-size: 0.75rem;
    color: var(--accent);
    margin-top: 8px;
    word-break: break-all;
  }

  /* 섹터 */
  .sector-block {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 16px;
    margin-bottom: 16px;
  }
  .sector-block h3 {
    font-size: 0.95rem;
    margin-bottom: 12px;
    color: var(--accent);
  }
  .sector-block p {
    font-size: 0.85rem;
    line-height: 1.8;
    color: var(--text-dim);
    white-space: pre-wrap;
  }

  /* 폴백 */
  .fallback-notice {
    text-align: center;
    padding: 40px 20px;
    color: var(--text-dim);
    font-size: 0.9rem;
  }

  /* 피보나치 */
  .fib-table {
    width: 100%;
    font-size: 0.78rem;
    margin-top: 10px;
    border-collapse: collapse;
  }
  .fib-table td {
    padding: 3px 8px;
    border-bottom: 1px solid var(--border);
    color: var(--text-dim);
  }
  .fib-table td:first-child { color: var(--text); }

  /* 푸터 */
  footer {
    text-align: center;
    padding: 30px 0;
    color: var(--text-dim);
    font-size: 0.75rem;
  }
</style>
</head>
<body>
<div class="container">
  <header>
    <h1>📡 주식레이더</h1>
    <p class="meta">데이터 기준: {{ date }} {{ time }} {{ timezone }} (확정 종가)</p>
    {% if feed_status == 'failed' %}
    <p class="meta" style="color: var(--up);">⚠ AI 피드 생성 실패 — 시세 데이터만 표시</p>
    {% endif %}
  </header>

  <div class="tabs">
    <button class="tab-btn active" onclick="showTab('top10')">🏆 Top 10</button>
    <button class="tab-btn" onclick="showTab('remaining')">📋 11~30위</button>
    <button class="tab-btn" onclick="showTab('sector')">📊 섹터 흐름</button>
  </div>

  <!-- Top 10 -->
  <div id="tab-top10" class="tab-content active">
    {% for s in top10 %}
    <div class="stock-card">
      <div class="header-row">
        <div style="display:flex;align-items:center;">
          <span class="rank">{{ s.rank }}</span>
          <span class="name">{{ s.name }}</span>
        </div>
        <span class="change {{ 'up' if s.change_pct > 0 else 'down' }}">
          {{ '+' if s.change_pct > 0 else '' }}{{ s.change_pct }}%
        </span>
      </div>
      <div class="analysis">{{ s.analysis | default('분석 데이터 없음', true) }}</div>
      {% if s.news_source and s.news_source != '미확인' %}
      <div class="source">📰 {{ s.news_source }}</div>
      {% endif %}
      {% if s.fibonacci %}
      <table class="fib-table">
        {% for level, price in s.fibonacci.items() %}
        <tr><td>{{ level }}</td><td>{{ "{:,}".format(price) }}원</td></tr>
        {% endfor %}
      </table>
      {% endif %}
    </div>
    {% endfor %}
    {% if not top10 %}
    <div class="fallback-notice">데이터가 아직 준비되지 않았습니다.</div>
    {% endif %}
  </div>

  <!-- 11~30위 아코디언 -->
  <div id="tab-remaining" class="tab-content">
    {% for s in remaining20 %}
    <div class="accordion-item" onclick="this.classList.toggle('open')">
      <div class="accordion-header">
        <div class="left">
          <span class="rank-sm">{{ s.rank }}</span>
          <span class="name">{{ s.name }}</span>
          <span class="change {{ 'up' if s.change_pct > 0 else 'down' }}" style="font-size:0.85rem;font-weight:600;">
            {{ '+' if s.change_pct > 0 else '' }}{{ s.change_pct }}%
          </span>
        </div>
        <span class="arrow">▼</span>
      </div>
      <div class="accordion-body">
        <div class="accordion-body-inner">
          {{ s.analysis | default('분석 데이터 없음', true) }}
          {% if s.news_source and s.news_source != '미확인' %}
          <div class="source">📰 {{ s.news_source }}</div>
          {% endif %}
          {% if s.fibonacci %}
          <table class="fib-table">
            {% for level, price in s.fibonacci.items() %}
            <tr><td>{{ level }}</td><td>{{ "{:,}".format(price) }}원</td></tr>
            {% endfor %}
          </table>
          {% endif %}
        </div>
      </div>
    </div>
    {% endfor %}
    {% if not remaining20 %}
    <div class="fallback-notice">데이터가 아직 준비되지 않았습니다.</div>
    {% endif %}
  </div>

  <!-- 섹터 흐름 -->
  <div id="tab-sector" class="tab-content">
    <div class="sector-block">
      <h3>📌 오늘의 섹터 흐름</h3>
      <p>{{ today_sector | default('섹터 분석 데이터 없음', true) }}</p>
    </div>
    {% if weekly_sector %}
    <div class="sector-block">
      <h3>📈 요일별 섹터 흐름 요약</h3>
      <p>{{ weekly_sector }}</p>
    </div>
    {% endif %}
  </div>

  <footer>
    주식레이더 · 자동 생성 페이지 · 투자 참고용 (매매 추천 아님)<br>
    마지막 빌드: {{ build_time }}
  </footer>
</div>

<script>
function showTab(id) {
  document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('tab-' + id).classList.add('active');
  event.target.classList.add('active');
}
</script>
</body>
</html>"""


def main():
    now = datetime.now(KST)

    # top30.json 읽기
    if not TOP30_FILE.exists():
        print("[SKIP] top30.json 없음.")
        sys.exit(0)

    with open(TOP30_FILE, encoding="utf-8") as f:
        top30_data = json.load(f)

    date = top30_data.get("date", "N/A")
    time_str = top30_data.get("time", "N/A")
    timezone = top30_data.get("timezone", "KST")
    top30_stocks = top30_data.get("top30", [])

    # feed.json 읽기 (없으면 폴백)
    feed_data = {}
    feed_status = "no_feed"
    if FEED_FILE.exists():
        try:
            with open(FEED_FILE, encoding="utf-8") as f:
                feed_data = json.load(f)
            feed_status = feed_data.get("status", "unknown")
        except (json.JSONDecodeError, TypeError):
            feed_status = "failed"

    # AI 피드와 시세 데이터 병합
    feed_stocks = {s.get("rank"): s for s in feed_data.get("stocks", []) if "rank" in s}

    merged = []
    for i, stock in enumerate(top30_stocks):
        rank = i + 1
        feed_info = feed_stocks.get(rank, {})
        merged.append({
            "rank": rank,
            "ticker": stock.get("ticker", ""),
            "name": stock.get("name", "알수없음"),
            "change_pct": stock.get("change_pct", 0),
            "close": stock.get("close", 0),
            "volume": stock.get("volume", 0),
            "analysis": feed_info.get("analysis", ""),
            "news_source": feed_info.get("news_source", ""),
            "fibonacci": stock.get("fibonacci", {}),
        })

    top10 = merged[:10]
    remaining20 = merged[10:]

    today_sector = feed_data.get("today_sector_summary", "")
    weekly_sector = feed_data.get("weekly_sector_summary", "")

    # HTML 렌더링
    template = Template(HTML_TEMPLATE)
    html = template.render(
        date=date,
        time=time_str,
        timezone=timezone,
        feed_status=feed_status,
        top10=top10,
        remaining20=remaining20,
        today_sector=today_sector,
        weekly_sector=weekly_sector,
        build_time=now.strftime("%Y-%m-%d %H:%M KST"),
    )

    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"[OK] HTML 빌드 완료 → {OUTPUT}")


if __name__ == "__main__":
    main()
