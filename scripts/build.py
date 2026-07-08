# build.py — top30.json + feed.json → docs/index.html (라이트 테마 v2)
import json, sys
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from jinja2 import Template

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DOCS = ROOT / "docs"
KST = ZoneInfo("Asia/Seoul")

TPL = Template(r"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>주식레이더 — {{ date }}</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css">
<style>
:root{
  --bg:#F4F6FA; --card:#FFFFFF; --ink:#1B2437; --sub:#69738C; --line:#E4E8F1;
  --up:#E5484D; --up-bg:#FDF0F0; --down:#2563EB; --accent:#4F46E5; --accent-bg:#EEF0FE;
  --gold:#B7791F; --gold-bg:#FdF6E9;
}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--bg);color:var(--ink);font-family:Pretendard,-apple-system,'Noto Sans KR',sans-serif;line-height:1.6}
.wrap{max-width:860px;margin:0 auto;padding:28px 16px 60px}
header{text-align:center;margin-bottom:22px}
h1{font-size:1.7rem;font-weight:800;letter-spacing:-.5px}
.meta{color:var(--sub);font-size:.9rem;margin-top:6px}
.badges{display:flex;gap:8px;justify-content:center;flex-wrap:wrap;margin-top:12px}
.chip{display:inline-flex;align-items:center;gap:6px;padding:5px 13px;border-radius:99px;font-size:.83rem;font-weight:600;background:var(--card);border:1px solid var(--line)}
.chip.warn{background:#FEF2F2;color:#B91C1C;border-color:#FBD5D5}
.fear-wrap{max-width:420px;margin:16px auto 0;background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 18px}
.fear-top{display:flex;justify-content:space-between;font-size:.85rem;font-weight:700}
.fear-bar{height:8px;border-radius:99px;margin-top:8px;background:linear-gradient(90deg,#2563EB,#94A3B8 50%,#E5484D);position:relative}
.fear-dot{position:absolute;top:-4px;width:16px;height:16px;border-radius:50%;background:#fff;border:3px solid var(--ink);transform:translateX(-8px)}
.fear-detail{color:var(--sub);font-size:.78rem;margin-top:8px;text-align:right}
.tabs{display:flex;gap:6px;overflow-x:auto;margin:24px 0 16px;padding-bottom:2px}
.tab-btn{flex-shrink:0;padding:9px 16px;border:1px solid var(--line);background:var(--card);border-radius:10px;font-size:.9rem;font-weight:600;color:var(--sub);cursor:pointer}
.tab-btn.active{background:var(--accent);border-color:var(--accent);color:#fff}
.tab-content{display:none}.tab-content.active{display:block}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px;margin-bottom:12px}
.s-head{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap}
.rank{font-weight:800;color:var(--accent);font-size:.95rem;min-width:26px}
.s-name{font-weight:700;font-size:1.05rem}
.pct{font-weight:800;color:var(--up)}
.s-sub{color:var(--sub);font-size:.82rem;margin-left:auto}
.sector-tag{font-size:.72rem;background:var(--accent-bg);color:var(--accent);padding:2px 9px;border-radius:99px;font-weight:600}
.analysis{margin-top:10px;font-size:.92rem;color:#333C52;background:#F8FAFD;border-radius:10px;padding:12px 14px}
.src{font-size:.78rem;margin-top:6px}
.src a{color:var(--accent)}
.fib{display:flex;gap:6px;flex-wrap:wrap;margin-top:10px}
.fib span{font-size:.74rem;background:var(--gold-bg);color:var(--gold);padding:3px 9px;border-radius:8px;font-weight:600}
details{background:var(--card);border:1px solid var(--line);border-radius:12px;margin-bottom:8px;overflow:hidden}
summary{padding:13px 16px;cursor:pointer;display:flex;align-items:center;gap:10px;font-weight:600;list-style:none}
summary::-webkit-details-marker{display:none}
summary::after{content:"▾";margin-left:auto;color:var(--sub);transition:.2s}
details[open] summary::after{transform:rotate(180deg)}
details .analysis{margin:0 16px 14px}
table{width:100%;border-collapse:collapse;font-size:.9rem}
th{color:var(--sub);font-weight:600;text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);font-size:.8rem}
td{padding:10px;border-bottom:1px solid var(--line)}
tr:last-child td{border-bottom:none}
.num{text-align:right;font-variant-numeric:tabular-nums}
.empty{color:var(--sub);text-align:center;padding:30px 10px;font-size:.9rem}
.summary-box{white-space:pre-line;font-size:.93rem}
.sec-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:8px;margin-top:12px}
.sec-item{background:#F8FAFD;border:1px solid var(--line);border-radius:10px;padding:10px 12px;font-size:.8rem}
.sec-item b{display:block;font-size:.86rem}
h3{font-size:1rem;margin-bottom:10px;display:flex;align-items:center;gap:6px}
footer{text-align:center;color:var(--sub);font-size:.78rem;margin-top:40px;line-height:1.9}
@media (max-width:520px){.wrap{padding:20px 10px 50px}.s-sub{margin-left:0;width:100%}}
</style>
</head>
<body>
<div class="wrap">
<header>
  <h1>📡 주식레이더</h1>
  <div class="meta">데이터 기준: {{ date }} {{ time }} KST (확정 종가){% if filtered_risky %} · 위험종목 {{ filtered_risky }}개 자동 제외{% endif %}</div>
  <div class="badges">
    {% if feed_status != 'ok' %}<span class="chip warn">⚠️ AI 피드 생성 실패 — 시세만 표시</span>
    {% else %}<span class="chip">🤖 AI 피드 {{ feed_generated_at }} 생성</span>{% endif %}
    {% for name, idx in indices.items() %}<span class="chip">{{ name }} {{ "%+.2f"|format(idx.change_pct) }}%</span>{% endfor %}
  </div>
  {% if fear %}
  <div class="fear-wrap">
    <div class="fear-top"><span>시장 온도계 (자체 간이지표)</span><span>{{ fear.score }} · {{ fear.label }}</span></div>
    <div class="fear-bar"><div class="fear-dot" style="left:{{ fear.score }}%"></div></div>
    <div class="fear-detail">{{ fear.detail }}</div>
  </div>
  {% endif %}
</header>

<div class="tabs">
  <button class="tab-btn active" onclick="show('top10',this)">🏆 Top 10</button>
  <button class="tab-btn" onclick="show('rest',this)">📋 11~30위</button>
  <button class="tab-btn" onclick="show('etf',this)">📦 ETF</button>
  <button class="tab-btn" onclick="show('foreign',this)">🌐 외국인</button>
  <button class="tab-btn" onclick="show('sector',this)">🗂 섹터 흐름</button>
</div>

<div id="tab-top10" class="tab-content active">
  {% for s in top10 %}
  <div class="card">
    <div class="s-head">
      <span class="rank">{{ s.rank }}</span><span class="s-name">{{ s.name }}</span>
      <span class="pct">+{{ s.change_pct }}%</span><span class="sector-tag">{{ s.sector }}</span>
      <span class="s-sub">{{ "{:,}".format(s.close) }}원 · 거래량 {{ "{:,}".format(s.volume) }}</span>
    </div>
    {% if s.analysis %}<div class="analysis">{{ s.analysis }}{% if s.news_source and s.news_source != '미확인' %}<div class="src">📎 <a href="{{ s.news_source }}" target="_blank" rel="noopener">뉴스 출처</a></div>{% endif %}</div>{% endif %}
    {% if s.fibonacci %}<div class="fib">{% for k, v in s.fibonacci.items() %}<span>{{ k }} {{ "{:,}".format(v) }}</span>{% endfor %}</div>{% endif %}
  </div>
  {% else %}<div class="empty">데이터 없음</div>{% endfor %}
</div>

<div id="tab-rest" class="tab-content">
  {% for s in rest %}
  <details>
    <summary><span class="rank">{{ s.rank }}</span><span>{{ s.name }}</span><span class="pct">+{{ s.change_pct }}%</span><span class="sector-tag">{{ s.sector }}</span></summary>
    <div class="analysis">{{ s.analysis or "AI 분석 없음" }}{% if s.news_source and s.news_source != '미확인' %}<div class="src">📎 <a href="{{ s.news_source }}" target="_blank" rel="noopener">뉴스 출처</a></div>{% endif %}
    {% if s.fibonacci %}<div class="fib">{% for k, v in s.fibonacci.items() %}<span>{{ k }} {{ "{:,}".format(v) }}</span>{% endfor %}</div>{% endif %}</div>
  </details>
  {% else %}<div class="empty">데이터 없음</div>{% endfor %}
</div>

<div id="tab-etf" class="tab-content">
  <div class="card">
    <h3>📦 오늘 상승 ETF/ETN Top {{ etf_top|length }}</h3>
    {% if etf_top %}
    <table><tr><th>#</th><th>이름</th><th class="num">종가</th><th class="num">등락률</th></tr>
    {% for e in etf_top %}<tr><td>{{ loop.index }}</td><td>{{ e.name }}</td><td class="num">{{ "{:,}".format(e.close) }}</td><td class="num pct">+{{ e.change_pct }}%</td></tr>{% endfor %}
    </table>
    {% else %}<div class="empty">오늘 상승 ETF 데이터 없음</div>{% endif %}
  </div>
</div>

<div id="tab-foreign" class="tab-content">
  <div class="card">
    <h3>🌐 외국인 매수 상위</h3>
    {% if foreign_top %}
    <table><tr><th>#</th><th>이름</th><th class="num">종가</th><th class="num">등락률</th></tr>
    {% for e in foreign_top %}<tr><td>{{ loop.index }}</td><td>{{ e.name }}</td><td class="num">{{ "{:,}".format(e.close) }}</td><td class="num">{{ "%+.2f"|format(e.change_pct) }}%</td></tr>{% endfor %}
    </table>
    {% else %}<div class="empty">외국인 데이터 수집 실패 — 다음 업데이트에서 재시도합니다</div>{% endif %}
  </div>
</div>

<div id="tab-sector" class="tab-content">
  <div class="card"><h3>📌 오늘의 섹터 흐름</h3><div class="summary-box">{{ today_sector_summary }}</div>
    {% if today_sectors %}<div class="sec-grid">
    {% for name, d in today_sectors.items() %}<div class="sec-item"><b>{{ name }}</b>{{ d.count }}종목 · 평균 +{{ d.avg_change_pct }}%<br>대장: {{ d.top_gainer }}</div>{% endfor %}
    </div>{% endif %}
  </div>
  {% if weekly_sector_summary %}<div class="card"><h3>📅 요일별 섹터 흐름</h3><div class="summary-box">{{ weekly_sector_summary }}</div></div>{% endif %}
</div>

<footer>주식레이더 · 자동 생성 페이지 · 투자 참고용 (매매 추천 아님)<br>마지막 빌드: {{ built_at }}</footer>
</div>
<script>
function show(id, btn){
  document.querySelectorAll('.tab-content').forEach(e=>e.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(e=>e.classList.remove('active'));
  document.getElementById('tab-'+id).classList.add('active');
  btn.classList.add('active');
}
</script>
</body>
</html>""")

def main():
    top30_path = DATA_DIR / "top30.json"
    if not top30_path.exists():
        print("[SKIP] top30.json 없음.")
        sys.exit(0)
    data = json.load(open(top30_path, encoding="utf-8"))

    feed = {}
    feed_path = DATA_DIR / "feed.json"
    if feed_path.exists():
        try:
            feed = json.load(open(feed_path, encoding="utf-8"))
        except Exception:
            feed = {}
    feed_stocks = {s.get("rank"): s for s in feed.get("stocks", []) if isinstance(s, dict)}

    merged = []
    for i, s in enumerate(data.get("top30", []), 1):
        f = feed_stocks.get(i, {})
        merged.append({**s, "rank": i,
                       "analysis": f.get("analysis", ""),
                       "news_source": f.get("news_source", "")})

    html = TPL.render(
        date=data.get("date", ""), time=data.get("time", ""),
        top10=merged[:10], rest=merged[10:30],
        etf_top=data.get("etf_top", []), foreign_top=data.get("foreign_top", []),
        indices=data.get("indices", {}), fear=data.get("fear"),
        filtered_risky=data.get("filtered_risky", 0),
        today_sectors=data.get("today_sectors", {}),
        feed_status=feed.get("status", "failed"),
        feed_generated_at=feed.get("generated_at", ""),
        today_sector_summary=feed.get("today_sector_summary", "AI 요약 없음"),
        weekly_sector_summary=feed.get("weekly_sector_summary", ""),
        built_at=datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"),
    )
    DOCS.mkdir(exist_ok=True)
    (DOCS / "index.html").write_text(html, encoding="utf-8")
    print(f"[OK] HTML 빌드 완료 → {DOCS/'index.html'}")

if __name__ == "__main__":
    main()
