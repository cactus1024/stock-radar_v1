# build.py — v3: 배지(대금/회전율/경고/패턴), 스윙 레벨, 테마 D+n, 대장주, 헤드라인/인사이트
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
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>주식레이더 — {{ date }}</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css">
<style>
:root{--bg:#F4F6FA;--card:#FFF;--ink:#1B2437;--sub:#69738C;--line:#E4E8F1;
--up:#E5484D;--down:#2563EB;--accent:#4F46E5;--accent-bg:#EEF0FE;--gold:#B7791F;--gold-bg:#FDF6E9}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--bg);color:var(--ink);font-family:Pretendard,-apple-system,'Noto Sans KR',sans-serif;line-height:1.6}
.wrap{max-width:880px;margin:0 auto;padding:28px 16px 60px}
header{text-align:center;margin-bottom:20px}
h1{font-size:1.7rem;font-weight:800;letter-spacing:-.5px}
.meta{color:var(--sub);font-size:.88rem;margin-top:6px}
.badges{display:flex;gap:8px;justify-content:center;flex-wrap:wrap;margin-top:12px}
.chip{display:inline-flex;align-items:center;gap:5px;padding:5px 13px;border-radius:99px;font-size:.82rem;font-weight:600;background:var(--card);border:1px solid var(--line)}
.chip.warn{background:#FEF2F2;color:#B91C1C;border-color:#FBD5D5}
.fear-wrap{max-width:440px;margin:16px auto 0;background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 18px}
.fear-top{display:flex;justify-content:space-between;font-size:.85rem;font-weight:700}
.fear-bar{height:8px;border-radius:99px;margin-top:8px;background:linear-gradient(90deg,#2563EB,#94A3B8 50%,#E5484D);position:relative}
.fear-dot{position:absolute;top:-4px;width:16px;height:16px;border-radius:50%;background:#fff;border:3px solid var(--ink);transform:translateX(-8px)}
.fear-detail{color:var(--sub);font-size:.76rem;margin-top:8px;text-align:right}
.tabs{display:flex;gap:6px;overflow-x:auto;margin:22px 0 16px}
.tab-btn{flex-shrink:0;padding:9px 16px;border:1px solid var(--line);background:var(--card);border-radius:10px;font-size:.9rem;font-weight:600;color:var(--sub);cursor:pointer}
.tab-btn.active{background:var(--accent);border-color:var(--accent);color:#fff}
.tab-content{display:none}.tab-content.active{display:block}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px;margin-bottom:12px}
.card.hot{border:2px solid #F59E0B;box-shadow:0 2px 12px rgba(245,158,11,.15)}
.s-head{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.rank{font-weight:800;color:var(--accent);font-size:.95rem;min-width:24px}
.s-name{font-weight:700;font-size:1.05rem}
.pct{font-weight:800;color:var(--up)}
.s-sub{color:var(--sub);font-size:.8rem;width:100%;margin-top:2px}
.tag{font-size:.7rem;padding:2px 9px;border-radius:99px;font-weight:700}
.t-sector{background:var(--accent-bg);color:var(--accent)}
.t-money{background:#FFF7E6;color:#B45309;border:1px solid #FDE68A}
.t-turn{background:#FEF2F2;color:#DC2626;border:1px solid #FECACA}
.t-alert{background:#7F1D1D;color:#fff}
.t-pattern{background:#ECFDF5;color:#047857;border:1px solid #A7F3D0}
.t-theme{background:#F1F5F9;color:#475569}
.headline{margin-top:10px;font-size:.86rem;font-weight:700;color:#334155;background:#F1F5F9;border-left:3px solid var(--accent);padding:8px 12px;border-radius:0 8px 8px 0}
.analysis{margin-top:8px;font-size:.9rem;color:#333C52;background:#F8FAFD;border-radius:10px;padding:12px 14px;white-space:pre-line}
.insight{margin-top:8px;font-size:.88rem;background:var(--gold-bg);border:1px solid #F3E3C3;border-radius:10px;padding:11px 14px;color:#7C5A11;white-space:pre-line}
.insight b{color:#92610A}
.src{font-size:.76rem;margin-top:6px}.src a{color:var(--accent)}
.levels{display:flex;gap:6px;flex-wrap:wrap;margin-top:10px}
.levels span{font-size:.72rem;background:#F8FAFD;border:1px solid var(--line);color:var(--sub);padding:3px 9px;border-radius:8px;font-weight:600}
.levels span.sw{background:var(--gold-bg);color:var(--gold);border-color:#F3E3C3}
details{background:var(--card);border:1px solid var(--line);border-radius:12px;margin-bottom:8px;overflow:hidden}
details.hot{border:2px solid #F59E0B}
summary{padding:13px 16px;cursor:pointer;display:flex;align-items:center;gap:8px;font-weight:600;list-style:none;flex-wrap:wrap}
summary::-webkit-details-marker{display:none}
summary::after{content:"▾";margin-left:auto;color:var(--sub)}
details[open] summary::after{transform:rotate(180deg)}
details .inner{padding:0 16px 14px}
table{width:100%;border-collapse:collapse;font-size:.9rem}
th{color:var(--sub);font-weight:600;text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);font-size:.8rem}
td{padding:10px;border-bottom:1px solid var(--line)}
tr:last-child td{border-bottom:none}
.num{text-align:right;font-variant-numeric:tabular-nums}
.empty{color:var(--sub);text-align:center;padding:30px;font-size:.9rem}
.summary-box{white-space:pre-line;font-size:.93rem}
.sec-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:8px;margin-top:12px}
.sec-item{background:#F8FAFD;border:1px solid var(--line);border-radius:10px;padding:10px 12px;font-size:.78rem}
.sec-item b{display:block;font-size:.85rem}
h3{font-size:1rem;margin-bottom:10px}
footer{text-align:center;color:var(--sub);font-size:.78rem;margin-top:40px;line-height:1.9}
@media(max-width:520px){.wrap{padding:20px 10px 50px}}
</style>
</head>
<body><div class="wrap">
<header>
  <h1>📡 주식레이더</h1>
  <div class="meta">데이터 기준: {{ date }} {{ time }} KST (확정 종가){% if filtered_risky %} · 위험종목 {{ filtered_risky }}개 자동 제외{% endif %}</div>
  <div class="badges">
    {% if feed_status != 'ok' %}<span class="chip warn">⚠️ AI 피드 생성 실패 — 시세만 표시</span>
    {% else %}<span class="chip">🤖 {{ feed_model }} · {{ feed_generated_at }}</span>{% endif %}
    {% for name, idx in indices.items() %}<span class="chip">{{ name }} {{ "%+.2f"|format(idx.change_pct) }}%</span>{% endfor %}
  </div>
  {% if fear %}
  <div class="fear-wrap">
    <div class="fear-top"><span>시장 온도계 (자체 간이지표)</span><span>{{ fear.score }} · {{ fear.label }}</span></div>
    <div class="fear-bar"><div class="fear-dot" style="left:{{ fear.score }}%"></div></div>
    <div class="fear-detail">{{ fear.detail }}</div>
  </div>{% endif %}
</header>

<div class="tabs">
  <button class="tab-btn active" onclick="show('top10',this)">🏆 Top 10</button>
  <button class="tab-btn" onclick="show('rest',this)">📋 11~30위</button>
  <button class="tab-btn" onclick="show('etf',this)">📦 ETF</button>
  <button class="tab-btn" onclick="show('foreign',this)">🌐 외국인</button>
  <button class="tab-btn" onclick="show('sector',this)">🗂 섹터 흐름</button>
</div>

{% macro tags(s) %}
  <span class="tag t-sector">{{ s.sector }}</span>
  {% if s.theme_streak and s.theme_streak > 1 %}<span class="tag t-theme">테마 D+{{ s.theme_streak }}</span>{% endif %}
  {% if s.big_money %}<span class="tag t-money">💰 대금 {{ (s.trading_value // 100000000) }}억</span>{% endif %}
  {% if s.high_turnover %}<span class="tag t-turn">🔥 회전율 {{ s.turnover_pct }}%</span>{% endif %}
  {% for p in s.patterns or [] %}<span class="tag t-pattern">📐 {{ p }}</span>{% endfor %}
  {% for a in s.alerts or [] %}<span class="tag t-alert">⚠️ {{ a }}</span>{% endfor %}
{% endmacro %}

{% macro levels(s) %}
  <div class="levels">
    {% if s.swing_low %}<span class="sw">스윙저점 {{ "{:,}".format(s.swing_low) }}</span>{% endif %}
    {% if s.swing_high %}<span class="sw">스윙고점 {{ "{:,}".format(s.swing_high) }}</span>{% endif %}
    {% for k, v in (s.fibonacci or {}).items() %}<span>피보 {{ k }} {{ "{:,}".format(v) }}</span>{% endfor %}
    {% if s.theme_leader and s.theme_leader != s.name %}<span>👑 대장주: {{ s.theme_leader }}</span>{% endif %}
  </div>
{% endmacro %}

{% macro body(s) %}
  {% if s.headline %}<div class="headline">📰 {{ s.headline }}</div>{% endif %}
  {% if s.analysis %}<div class="analysis">{{ s.analysis }}</div>{% endif %}
  {% if s.insight %}<div class="insight"><b>🎯 실전 포인트</b><br>{{ s.insight }}</div>{% endif %}
  {{ levels(s) }}
  {% if s.news_source and s.news_source != '미확인' %}<div class="src">📎 <a href="{{ s.news_source }}" target="_blank" rel="noopener">뉴스 출처</a></div>{% endif %}
{% endmacro %}

<div id="tab-top10" class="tab-content active">
  {% for s in top10 %}
  <div class="card{% if s.big_money %} hot{% endif %}">
    <div class="s-head">
      <span class="rank">{{ s.rank }}</span><span class="s-name">{{ s.name }}</span>
      <span class="pct">+{{ s.change_pct }}%</span>{{ tags(s) }}
      <span class="s-sub">종가 {{ "{:,}".format(s.close) }}원 · 거래량 {{ "{:,}".format(s.volume) }} · 거래대금 {{ "{:,}".format((s.trading_value or 0) // 100000000) }}억</span>
    </div>
    {{ body(s) }}
  </div>
  {% else %}<div class="empty">데이터 없음</div>{% endfor %}
</div>

<div id="tab-rest" class="tab-content">
  {% for s in rest %}
  <details{% if s.big_money %} class="hot"{% endif %}>
    <summary><span class="rank">{{ s.rank }}</span><span>{{ s.name }}</span><span class="pct">+{{ s.change_pct }}%</span>{{ tags(s) }}</summary>
    <div class="inner">{{ body(s) }}</div>
  </details>
  {% else %}<div class="empty">데이터 없음</div>{% endfor %}
</div>

<div id="tab-etf" class="tab-content">
  <div class="card"><h3>📦 오늘 상승 ETF/ETN Top {{ etf_top|length }}</h3>
  {% if etf_top %}<table><tr><th>#</th><th>이름</th><th class="num">종가</th><th class="num">등락률</th></tr>
  {% for e in etf_top %}<tr><td>{{ loop.index }}</td><td>{{ e.name }}</td><td class="num">{{ "{:,}".format(e.close) }}</td><td class="num pct">+{{ e.change_pct }}%</td></tr>{% endfor %}</table>
  {% else %}<div class="empty">오늘 상승 ETF 데이터 없음</div>{% endif %}</div>
</div>

<div id="tab-foreign" class="tab-content">
  <div class="card"><h3>🌐 외국인 매수 상위</h3>
  {% if foreign_top %}<table><tr><th>#</th><th>이름</th><th class="num">순매수금액</th></tr>
  {% for e in foreign_top %}<tr><td>{{ loop.index }}</td><td>{{ e.name }}</td><td class="num">{{ "{:,}".format(e.net_buy or e.close or 0) }}</td></tr>{% endfor %}</table>
  {% else %}<div class="empty">외국인 데이터 수집 실패 — 소스 보정 작업 중</div>{% endif %}</div>
</div>

<div id="tab-sector" class="tab-content">
  <div class="card"><h3>📌 오늘의 섹터 흐름</h3><div class="summary-box">{{ today_sector_summary }}</div>
    {% if today_sectors %}<div class="sec-grid">
    {% for name, d in today_sectors.items() %}<div class="sec-item"><b>{{ name }}{% if d.streak_days and d.streak_days > 1 %} · D+{{ d.streak_days }}{% endif %}</b>{{ d.count }}종목 · 평균 +{{ d.avg_change_pct }}%<br>👑 {{ d.leader or d.top_gainer }}</div>{% endfor %}
    </div>{% endif %}
  </div>
  {% if weekly_sector_summary %}<div class="card"><h3>📅 요일별 섹터 흐름</h3><div class="summary-box">{{ weekly_sector_summary }}</div></div>{% endif %}
</div>

<footer>주식레이더 · 자동 생성 페이지 · 투자 참고용 (매매 추천 아님)<br>마지막 빌드: {{ built_at }}</footer>
</div>
<script>
function show(id,btn){document.querySelectorAll('.tab-content').forEach(e=>e.classList.remove('active'));
document.querySelectorAll('.tab-btn').forEach(e=>e.classList.remove('active'));
document.getElementById('tab-'+id).classList.add('active');btn.classList.add('active');}
</script>
</body></html>""")

def main():
    p = DATA_DIR / "top30.json"
    if not p.exists():
        print("[SKIP] top30.json 없음."); sys.exit(0)
    data = json.load(open(p, encoding="utf-8"))

    feed = {}
    fp = DATA_DIR / "feed.json"
    if fp.exists():
        try: feed = json.load(open(fp, encoding="utf-8"))
        except Exception: feed = {}
    fmap = {s.get("rank"): s for s in feed.get("stocks", []) if isinstance(s, dict)}

    merged = []
    for i, s in enumerate(data.get("top30", []), 1):
        f = fmap.get(i, {})
        merged.append({**s, "rank": i, "headline": f.get("headline", ""),
                       "analysis": f.get("analysis", ""), "insight": f.get("insight", ""),
                       "news_source": f.get("news_source", "")})

    html = TPL.render(
        date=data.get("date", ""), time=data.get("time", ""),
        top10=merged[:10], rest=merged[10:30],
        etf_top=data.get("etf_top", []), foreign_top=data.get("foreign_top", []),
        indices=data.get("indices", {}), fear=data.get("fear"),
        filtered_risky=data.get("filtered_risky", 0),
        today_sectors=data.get("today_sectors", {}),
        feed_status=feed.get("status", "failed"), feed_model=feed.get("model", ""),
        feed_generated_at=feed.get("generated_at", ""),
        today_sector_summary=feed.get("today_sector_summary", "AI 요약 없음"),
        weekly_sector_summary=feed.get("weekly_sector_summary", ""),
        built_at=datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"))
    DOCS.mkdir(exist_ok=True)
    (DOCS / "index.html").write_text(html, encoding="utf-8")
    print(f"[OK] HTML 빌드 완료 → {DOCS/'index.html'}")

if __name__ == "__main__":
    main()
