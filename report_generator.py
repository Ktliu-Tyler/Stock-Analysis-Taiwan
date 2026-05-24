# report_generator.py — HTML 報告產生器

import os
import json
import logging
from datetime import datetime
from jinja2 import Template

import sys
sys.path.insert(0, os.path.dirname(__file__))
from config import REPORT_OUTPUT_DIR, WEIGHTS, MIN_SCORE_THRESHOLD

logger = logging.getLogger(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>台股選股報告 — {{ date }}</title>
<style>
  :root {
    --bg: #0f1117; --surface: #1a1d27; --card: #21253a;
    --accent: #4f8ef7; --green: #00c853; --red: #ff3d57;
    --yellow: #ffc107; --text: #e8eaf6; --muted: #8892b0;
    --border: #2d3254;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--text); font-family: 'Segoe UI', -apple-system, sans-serif; }

  /* ─ Header ─ */
  .header { background: linear-gradient(135deg, #1a1d27 0%, #21253a 100%);
    border-bottom: 1px solid var(--border); padding: 24px 32px; }
  .header h1 { font-size: 1.8rem; font-weight: 700; }
  .header h1 span { color: var(--accent); }
  .meta { color: var(--muted); margin-top: 6px; font-size: .9rem; }
  .market-badge { display: inline-block; padding: 4px 12px; border-radius: 20px;
    font-size: .8rem; font-weight: 600; margin-left: 12px; }
  .bullish { background: rgba(0,200,83,.15); color: var(--green); border: 1px solid var(--green); }
  .bearish { background: rgba(255,61,87,.15); color: var(--red);   border: 1px solid var(--red); }
  .neutral { background: rgba(255,193,7,.15); color: var(--yellow); border: 1px solid var(--yellow); }

  /* ─ Stats Bar ─ */
  .stats-bar { display: flex; gap: 20px; padding: 20px 32px; border-bottom: 1px solid var(--border);
    background: var(--surface); flex-wrap: wrap; }
  .stat { text-align: center; }
  .stat-val { font-size: 1.6rem; font-weight: 700; color: var(--accent); }
  .stat-label { font-size: .75rem; color: var(--muted); margin-top: 2px; }

  /* ─ Container ─ */
  .container { max-width: 1400px; margin: 0 auto; padding: 24px 32px; }
  .section-title { font-size: 1.1rem; font-weight: 600; color: var(--muted);
    text-transform: uppercase; letter-spacing: .1em; margin-bottom: 16px; margin-top: 32px; }

  /* ─ Stock Card ─ */
  .stock-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(580px, 1fr)); gap: 20px; }
  .stock-card { background: var(--card); border: 1px solid var(--border); border-radius: 12px;
    overflow: hidden; transition: transform .2s; }
  .stock-card:hover { transform: translateY(-2px); }
  .card-header { display: flex; justify-content: space-between; align-items: center;
    padding: 16px 20px; border-bottom: 1px solid var(--border); }
  .stock-id { font-size: .8rem; color: var(--muted); }
  .stock-name { font-size: 1.2rem; font-weight: 700; margin-top: 2px; }
  .stock-price { font-size: 1.4rem; font-weight: 700; color: var(--green); }
  .score-badge { display: flex; flex-direction: column; align-items: center; }
  .total-score { font-size: 2.2rem; font-weight: 800; line-height: 1; }
  .grade-label { font-size: .7rem; font-weight: 600; margin-top: 4px; white-space: nowrap; }

  /* ─ Dimension Bars ─ */
  .dimensions { padding: 16px 20px; display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
  .dim { }
  .dim-header { display: flex; justify-content: space-between; margin-bottom: 5px; font-size: .82rem; }
  .dim-name { color: var(--muted); }
  .dim-score { font-weight: 700; }
  .progress { height: 6px; background: rgba(255,255,255,.08); border-radius: 3px; overflow: hidden; }
  .progress-fill { height: 100%; border-radius: 3px; transition: width .6s; }

  /* ─ Signals ─ */
  .signals { padding: 0 20px 16px; }
  .signal-item { font-size: .82rem; color: var(--muted); margin-bottom: 4px; padding: 4px 0;
    border-bottom: 1px solid rgba(255,255,255,.04); }
  .signal-item:last-child { border-bottom: none; }

  /* ─ Footer ─ */
  .footer { text-align: center; padding: 32px; color: var(--muted); font-size: .8rem; border-top: 1px solid var(--border); margin-top: 40px; }
  .disclaimer { background: rgba(255,193,7,.08); border: 1px solid var(--yellow); border-radius: 8px;
    padding: 12px 16px; margin-top: 32px; font-size: .82rem; color: var(--yellow); }

  /* ─ Score Color Helper ─ */
  .s-high { color: #00c853; }
  .s-mid  { color: #ffc107; }
  .s-low  { color: #ff3d57; }
</style>
</head>
<body>

<div class="header">
  <h1>🔍 <span>台股智慧選股</span> 報告</h1>
  <div class="meta">
    產生時間：{{ date }} {{ time }}
    <span class="market-badge {{ market.sentiment }}">
      {{ market.description }}
    </span>
  </div>
</div>

<div class="stats-bar">
  <div class="stat"><div class="stat-val">{{ scanned_count }}</div><div class="stat-label">掃描股票數</div></div>
  <div class="stat"><div class="stat-val" style="color:var(--green)">{{ result_count }}</div><div class="stat-label">推薦標的數</div></div>
  <div class="stat"><div class="stat-val">{{ threshold }}</div><div class="stat-label">篩選門檻分數</div></div>
  <div class="stat"><div class="stat-val">{{ "%.0f"|format(weights.technical*100) }}%</div><div class="stat-label">技術面權重</div></div>
  <div class="stat"><div class="stat-val">{{ "%.0f"|format(weights.chips*100) }}%</div><div class="stat-label">籌碼面權重</div></div>
  <div class="stat"><div class="stat-val">{{ "%.0f"|format(weights.fundamental*100) }}%</div><div class="stat-label">基本面權重</div></div>
  <div class="stat"><div class="stat-val">{{ "%.0f"|format(weights.sentiment*100) }}%</div><div class="stat-label">情緒面權重</div></div>
</div>

<div class="container">
  <div class="section-title">📈 推薦買入標的（依總分排序）</div>
  <div class="stock-grid">
  {% for s in stocks %}
  <div class="stock-card">
    <div class="card-header">
      <div>
        <div class="stock-id">{{ s.stock_id }}</div>
        <div class="stock-name">{{ s.name }}</div>
        {% if s.price %}<div class="stock-price">NT$ {{ "%.2f"|format(s.price) }}</div>{% endif %}
      </div>
      <div class="score-badge">
        <div class="total-score" style="color:{{ s.grade.color }}">{{ s.total_score }}</div>
        <div class="grade-label" style="color:{{ s.grade.color }}">{{ s.grade.emoji }} {{ s.grade.label }}</div>
      </div>
    </div>

    <div class="dimensions">
      {% set dims = [
        ('技術面', s.dimension_scores.technical,   '#4f8ef7'),
        ('籌碼面', s.dimension_scores.chips,        '#00c853'),
        ('基本面', s.dimension_scores.fundamental,  '#ffc107'),
        ('情緒面', s.dimension_scores.sentiment,    '#ab47bc'),
      ] %}
      {% for name, score, color in dims %}
      <div class="dim">
        <div class="dim-header">
          <span class="dim-name">{{ name }}</span>
          <span class="dim-score {% if score >= 70 %}s-high{% elif score >= 50 %}s-mid{% else %}s-low{% endif %}">
            {{ "%.0f"|format(score) }}
          </span>
        </div>
        <div class="progress">
          <div class="progress-fill" style="width:{{ score }}%; background:{{ color }};"></div>
        </div>
      </div>
      {% endfor %}
    </div>

    <div class="signals">
      {% for key, text in s.all_signals.items() %}
      <div class="signal-item">{{ text }}</div>
      {% endfor %}
    </div>
  </div>
  {% endfor %}
  </div>

  <div class="disclaimer">
    ⚠️ <strong>免責聲明：</strong>本報告為系統自動分析，僅供參考，不構成任何投資建議。
    股市存在風險，投資請依個人風險承受能力審慎判斷。過去績效不代表未來結果。
  </div>
</div>

<div class="footer">
  台股智慧選股系統 · 資料來源：台灣證券交易所（TWSE）· {{ date }}
</div>
</body>
</html>
"""


def generate(
    results:        list,
    scanned_count:  int,
    market_info:    dict,
) -> str:
    """
    產生 HTML 報告並儲存
    回傳：報告路徑
    """
    os.makedirs(REPORT_OUTPUT_DIR, exist_ok=True)

    now       = datetime.now()
    date_str  = now.strftime('%Y-%m-%d')
    time_str  = now.strftime('%H:%M')
    filename  = f"report_{now.strftime('%Y%m%d_%H%M')}.html"
    filepath  = os.path.join(REPORT_OUTPUT_DIR, filename)

    # 整合所有 signals
    for s in results:
        all_signals = {}
        for module in ['tech_signals', 'chips_signals', 'fund_signals', 'sent_signals']:
            all_signals.update(s.get(module, {}))
        s['all_signals'] = all_signals

    template = Template(HTML_TEMPLATE)
    html     = template.render(
        date           = date_str,
        time           = time_str,
        stocks         = results,
        scanned_count  = scanned_count,
        result_count   = len(results),
        threshold      = MIN_SCORE_THRESHOLD,
        weights        = WEIGHTS,
        market         = market_info,
    )

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html)

    logger.info(f"報告已產生：{filepath}")
    return filepath
