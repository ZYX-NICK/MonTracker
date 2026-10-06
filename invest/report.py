# -*- coding: utf-8 -*-
"""生成自包含的 HTML 报告（内嵌 ECharts，离线可看）。"""
import html
import json
import os
from datetime import datetime, timedelta, timezone

CN_TZ = timezone(timedelta(hours=8))
UP = "#e0322b"      # 红涨
DOWN = "#0f9d58"    # 绿跌
PALETTE = ["#5b8ff9", "#61c0bf", "#f6bd16", "#7262fd", "#78d3f8",
           "#9661bc", "#f6903d", "#008685", "#f08bb4", "#4aa3df"]

_ECHARTS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             "assets", "echarts.min.js")


def _money(v, sign=False):
    if v is None:
        return "—"
    s = f"{v:,.2f}"
    if sign and v > 0:
        s = "+" + s
    return s


def _pct(v):
    return "—" if v is None else f"{v:+.2f}%"


def _pct_abs(v):
    return "—" if v is None else f"{v:.2f}%"


def _sharpe_str(v):
    return "—" if v is None else f"{v:.2f}"


def _cls(v):
    return "up" if (v or 0) >= 0 else "down"


def _ms(d):
    return int(datetime.strptime(d, "%Y-%m-%d").replace(tzinfo=CN_TZ).timestamp() * 1000)


def _js(obj):
    return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")


def _kpi(s):
    tiles = []
    tiles.append(_tile("总市值", f"¥ {_money(s['total_market_value'])}",
                       f"成本 ¥ {_money(s['total_cost'])}", "neutral"))
    tiles.append(_tile("累计盈亏", f"{_money(s['total_pnl'], sign=True)} 元",
                       f"收益率 {_pct(s['total_pnl_pct'])}", _cls(s['total_pnl'])))
    tiles.append(_tile("今日盈亏", f"{_money(s['daily_pnl'], sign=True)} 元",
                       f"涨跌 {_pct(s['daily_pct'])}", _cls(s['daily_pnl'])))
    tiles.append(_tile("持仓数量", f"{s['n_holdings']} 只",
                       f"数据正常 {s['n_ok']} 只", "neutral"))
    tiles.append(_tile("数据日期", s["date"], "天天基金 / 东方财富", "neutral"))
    return "".join(tiles)


def _tile(label, value, sub, cls):
    return (f'<div class="tile"><div class="t-label">{label}</div>'
            f'<div class="t-value {cls}">{value}</div>'
            f'<div class="t-sub {cls}">{sub}</div></div>')


def _holdings_table(s):
    head = ("<tr><th>名称</th><th>类型</th><th>份额/股数</th><th>成本价</th><th>现价/净值</th>"
            "<th>市值</th><th>累计盈亏</th><th>收益率</th><th>今日涨跌</th><th>仓位</th></tr>")
    rows = []
    for h in s["holdings"]:
        if not h["ok"]:
            rows.append(f'<tr><td>{html.escape(h["name"])}<span class="code">({h["code"]})</span></td>'
                        f'<td colspan="8" class="warn">⚠ 数据获取失败，请检查代码是否正确</td>'
                        f'<td>—</td></tr>')
            continue
        late = "" if h["date"] == s["date"] else f'<span class="late" title="净值日期滞后">({h["date"]})</span>'
        typ = "基金" if h["type"] == "fund" else "股票"
        rows.append(
            f'<tr>'
            f'<td class="name">{html.escape(h["name"])}<span class="code">({h["code"]})</span>{late}</td>'
            f'<td>{typ}</td>'
            f'<td>{h["shares"]:,.0f}</td>'
            f'<td>{h["cost_price"]:,.4f}</td>'
            f'<td>{h["price"]:,.4f}</td>'
            f'<td>{_money(h["market_value"])}</td>'
            f'<td class="{_cls(h["pnl"])}">{_money(h["pnl"], sign=True)}</td>'
            f'<td class="{_cls(h["pnl"])}">{_pct(h["pnl_pct"])}</td>'
            f'<td class="{_cls(h["daily_pct"])}">{_pct(h["daily_pct"])}</td>'
            f'<td>{h["weight"]:.1f}%</td>'
            f'</tr>')
    return head + "".join(rows)


def _risk_table(s):
    head = ("<tr><th>名称</th><th>年化波动率</th><th>最大回撤</th><th>夏普比率</th>"
            "<th>近6月收益</th><th>近1年收益</th></tr>")
    rows = []
    for h in s["holdings"]:
        if not h["ok"]:
            continue
        rows.append(
            f'<tr><td class="name">{html.escape(h["name"])}</td>'
            f'<td>{_pct_abs(h["vol"])}</td>'
            f'<td class="{_cls(h["mdd"] or 0)}">{_pct_abs(h["mdd"])}</td>'
            f'<td>{_sharpe_str(h["sharpe"])}</td>'
            f'<td class="{_cls(h["ret_6m"] or 0)}">{_pct(h["ret_6m"])}</td>'
            f'<td class="{_cls(h["ret_1y"] or 0)}">{_pct(h["ret_1y"])}</td></tr>')
    pr = s["portfolio_risk"]
    if pr:
        rows.append(
            f'<tr class="portfolio"><td class="name">组合整体</td>'
            f'<td>{_pct_abs(pr.get("vol"))}</td>'
            f'<td class="{_cls(pr.get("mdd") or 0)}">{_pct_abs(pr.get("mdd"))}</td>'
            f'<td>{_sharpe_str(pr.get("sharpe"))}</td>'
            f'<td colspan="2">—</td></tr>')
    return head + "".join(rows)


def _constituents_html(s):
    blocks = []
    for h in s["holdings"]:
        stocks = h.get("top_stocks") or []
        if not stocks:
            continue
        pills = []
        for st in stocks:
            cls = "up" if (st["daily_pct"] or 0) >= 0 else "down"
            pills.append(
                f'<span class="pill"><span class="pn">{html.escape(st["name"])}</span>'
                f'<span class="{cls}">{st["daily_pct"]:+.2f}%</span></span>'
            )
        blocks.append(f'<div class="fund-block"><h3>{html.escape(h["name"])}</h3>'
                      f'<div class="stocks">{"".join(pills)}</div></div>')
    if not blocks:
        return '<p class="warn">当前组合没有股票型/混合型基金的成分股数据。</p>'
    return "".join(blocks)


def _news_html(s):
    items = s.get("news") or []
    if not items:
        return '<p class="warn">未获取到今日要闻。</p>'
    lis = "".join(f'<li><span class="t">{html.escape(n["time"])}</span>{html.escape(n["title"])}</li>'
                  for n in items)
    return f'<ul class="news">{lis}</ul>'


def _pie_data(s):
    data = [{"name": h["name"], "value": round(h["weight"], 2)}
            for h in sorted(s["holdings"], key=lambda x: -x["weight"]) if h["ok"]]
    if len(data) > 8:
        rest = sum(d["value"] for d in data[7:])
        data = data[:7] + [{"name": "其他", "value": round(rest, 2)}]
    return [{"name": d["name"], "value": d["value"],
             "itemStyle": {"color": PALETTE[i % len(PALETTE)]}}
            for i, d in enumerate(data)]


def _bar_data(s):
    items = sorted([h for h in s["holdings"] if h["ok"]], key=lambda x: x["pnl_pct"])
    return {
        "names": [h["name"] for h in items],
        "values": [round(h["pnl_pct"], 2) for h in items],
    }


def _trade_mark(action):
    is_buy = action == "buy"
    return {
        "value": "买" if is_buy else "卖",
        "itemStyle": {"color": UP if is_buy else DOWN},
        "label": {"show": True, "formatter": "买" if is_buy else "卖",
                  "color": "#fff", "fontSize": 10},
    }


def _line_data(s):
    series = []
    picks = sorted([h for h in s["holdings"] if h["ok"] and len(h["history"]) >= 30],
                   key=lambda x: -x["weight"])[:8]
    for i, h in enumerate(picks):
        hist = h["history"][-250:]
        base = hist[0][1]
        if not base:
            continue
        pts = [[_ms(d), round(p / base * 100, 2)] for d, p in hist]
        marks = []
        for t in h.get("trade_markers", []):
            if t.get("nav"):
                m = _trade_mark(t["action"])
                m["coord"] = [_ms(t["date"]), round(t["nav"] / base * 100, 2)]
                marks.append(m)
        item = {
            "name": h["name"], "type": "line", "showSymbol": False,
            "smooth": True, "data": pts,
            "lineStyle": {"width": 2}, "itemStyle": {"color": PALETTE[i % len(PALETTE)]},
        }
        if marks:
            item["markPoint"] = {"symbol": "pin", "symbolSize": 30, "data": marks}
        series.append(item)
    return series


def _total_data(s):
    series = [[_ms(d), v] for d, v in s.get("value_series", [])]
    vs = {d: v for d, v in s.get("value_series", [])}
    vdates = sorted(vs)
    marks = []
    for h in s["holdings"]:
        for t in h.get("trade_markers", []):
            val = None
            for dd in vdates:
                if dd >= t["date"]:
                    val = vs[dd]
                    break
            if val is None and vdates:
                val = vs[vdates[-1]]
            if val is not None:
                m = _trade_mark(t["action"])
                m["coord"] = [_ms(t["date"]), val]
                marks.append(m)
    return {"series": series, "cost": round(s["total_cost"], 2), "marks": marks}


def render(summary, ai_text):
    echarts_src = ""
    if os.path.exists(_ECHARTS_PATH):
        with open(_ECHARTS_PATH, encoding="utf-8") as f:
            echarts_src = f.read().replace("</script>", "<\\/script>")
    echarts_tag = f"<script>{echarts_src}</script>" if echarts_src else \
        '<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>'

    page = _TEMPLATE
    page = page.replace("__TITLE__", html.escape(summary["date"]))
    page = page.replace("__KPI__", _kpi(summary))
    page = page.replace("__HOLDINGS__", _holdings_table(summary))
    page = page.replace("__CONSTITUENTS__", _constituents_html(summary))
    page = page.replace("__NEWS__", _news_html(summary))
    page = page.replace("__RISK__", _risk_table(summary))
    page = page.replace("__AI__", html.escape(ai_text or "（暂无研判）"))
    page = page.replace("__ECHARTS__", echarts_tag)
    page = page.replace("__PIE__", _js(_pie_data(summary)))
    page = page.replace("__BAR_NAMES__", _js(_bar_data(summary)["names"]))
    page = page.replace("__BAR_VALUES__", _js(_bar_data(summary)["values"]))
    page = page.replace("__LINE__", _js(_line_data(summary)))
    td = _total_data(summary)
    page = page.replace("__TOTAL__", _js(td["series"]))
    page = page.replace("__COST__", _js(td["cost"]))
    page = page.replace("__MARKS__", _js(td["marks"]))
    return page


def save(summary, ai_text, report_dir):
    os.makedirs(report_dir, exist_ok=True)
    content = render(summary, ai_text)
    # 按运行时间命名，每次生成独立文件，方便回溯
    filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    path = os.path.join(report_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    latest = os.path.join(report_dir, "latest.html")
    with open(latest, "w", encoding="utf-8") as f:
        f.write(content)
    return path


_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>每日持仓分析 · __TITLE__</title>
<style>
:root { --up:#e0322b; --down:#0f9d58; --ink:#1f2329; --muted:#86909c;
        --card:#ffffff; --bg:#f4f6f8; --line:#eef0f3; }
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--ink);
       font-family:"PingFang SC","Microsoft YaHei","Segoe UI",sans-serif; }
.wrap { max-width:1080px; margin:0 auto; padding:24px 20px 40px; }
header { display:flex; align-items:baseline; justify-content:space-between;
         padding:6px 2px 18px; }
header h1 { font-size:22px; margin:0; font-weight:700; }
header .sub { color:var(--muted); font-size:13px; }
.kpis { display:grid; grid-template-columns:repeat(5,1fr); gap:12px; margin-bottom:16px; }
.tile { background:var(--card); border:1px solid var(--line); border-radius:12px;
        padding:14px 16px; }
.t-label { font-size:12px; color:var(--muted); margin-bottom:8px; }
.t-value { font-size:20px; font-weight:700; }
.t-sub { font-size:12px; color:var(--muted); margin-top:6px; }
.up { color:var(--up) !important; }
.down { color:var(--down) !important; }
.neutral { color:var(--ink); }
.grid { display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-bottom:16px; }
.card { background:var(--card); border:1px solid var(--line); border-radius:12px;
        padding:18px; margin-bottom:16px; }
.card h2 { font-size:15px; margin:0 0 14px; font-weight:700; }
.chart { width:100%; height:320px; }
table { width:100%; border-collapse:collapse; font-size:13px; }
th,td { padding:9px 8px; text-align:right; white-space:nowrap; }
th { color:var(--muted); font-weight:500; border-bottom:1px solid var(--line); }
td { border-bottom:1px solid var(--line); }
th:first-child,td:first-child { text-align:left; }
td.name { font-weight:600; }
.code { color:var(--muted); font-weight:400; font-size:12px; margin-left:4px; }
.late { color:#c08a00; font-size:11px; margin-left:4px; }
.warn { color:#c08a00; text-align:left; }
tr.portfolio td { font-weight:700; background:#fafbfc; }
.ai-text { white-space:pre-wrap; line-height:1.8; font-size:14px; }
.fund-block { margin-bottom:16px; }
.fund-block h3 { font-size:13px; font-weight:600; margin:0 0 8px; color:#4b5563; }
.stocks { display:flex; flex-wrap:wrap; gap:8px; }
.pill { display:inline-flex; align-items:center; gap:6px; padding:5px 10px;
        border:1px solid var(--line); border-radius:20px; font-size:12px; }
.pill .pn { color:#4b5563; }
.news { list-style:none; margin:0; padding:0; }
.news li { padding:7px 0; border-bottom:1px solid var(--line); font-size:13px; line-height:1.6; }
.news li:last-child { border-bottom:none; }
.news .t { color:var(--muted); margin-right:8px; font-variant-numeric:tabular-nums; }
footer { color:var(--muted); font-size:12px; text-align:center; margin-top:24px; line-height:1.7; }
@media (max-width:760px){
  .kpis { grid-template-columns:repeat(2,1fr); }
  .grid { grid-template-columns:1fr; }
  table { display:block; overflow-x:auto; }
}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>📊 每日持仓分析</h1>
    <span class="sub">数据日期：__TITLE__</span>
  </header>

  <div class="kpis">__KPI__</div>

  <div class="grid">
    <div class="card"><h2>仓位占比</h2><div id="pie" class="chart"></div></div>
    <div class="card"><h2>各持仓累计收益率</h2><div id="bar" class="chart"></div></div>
  </div>

  <div class="card"><h2>组合总市值走势（近一年 · 按当前持仓回测）</h2><div id="total" class="chart"></div></div>

  <div class="card"><h2>近一年净值走势（归一化 = 100）</h2><div id="line" class="chart"></div></div>

  <div class="card"><h2>持仓明细</h2><table>__HOLDINGS__</table></div>

  <div class="card"><h2>重仓股今日表现（最新季报）</h2>__CONSTITUENTS__</div>

  <div class="card"><h2>今日要闻</h2>__NEWS__</div>

  <div class="card"><h2>风险指标（近一年）</h2><table>__RISK__</table></div>

  <div class="card"><h2>🤖 AI 研判</h2><div class="ai-text">__AI__</div></div>

  <footer>
    数据来源：天天基金 / 东方财富公开行情接口。风险指标基于历史数据计算，仅供参考。<br>
    本报告仅供个人使用，不构成任何投资建议。市场有风险，投资需谨慎。
  </footer>
</div>

__ECHARTS__
<script>
var up = '#e0322b', down = '#0f9d58';
function barColor(p){ return p.value >= 0 ? up : down; }

var pie = echarts.init(document.getElementById('pie'));
pie.setOption({
  tooltip:{ trigger:'item', formatter:'{b}<br/>{c}%（{d}%）' },
  legend:{ bottom:0, type:'scroll', icon:'circle' },
  series:[{ type:'pie', radius:['42%','70%'], center:['50%','45%'],
    avoidLabelOverlap:true, itemStyle:{ borderColor:'#fff', borderWidth:2 },
    label:{ formatter:'{b}\\n{d}%', fontSize:11 }, data:__PIE__ }]
});

var bar = echarts.init(document.getElementById('bar'));
bar.setOption({
  grid:{ left:8, right:40, top:8, bottom:8, containLabel:true },
  xAxis:{ type:'value', axisLabel:{ formatter:'{value}%' }, splitLine:{ lineStyle:{ color:'#eef0f3' } } },
  yAxis:{ type:'category', data:__BAR_NAMES__, inverse:true,
          axisTick:{ show:false }, axisLine:{ show:false } },
  series:[{ type:'bar', data:__BAR_VALUES__, barWidth:16,
    label:{ show:true, position:'right', formatter:'{c}%' },
    itemStyle:{ color:barColor, borderRadius:[0,4,4,0] } }]
});

var line = echarts.init(document.getElementById('line'));
line.setOption({
  color:['#5b8ff9','#61c0bf','#f6bd16','#7262fd','#78d3f8','#9661bc','#f6903d','#008685'],
  tooltip:{ trigger:'axis', valueFormatter:function(v){ return v + '%'; } },
  legend:{ top:0, type:'scroll', icon:'roundRect', itemWidth:12, itemHeight:4 },
  grid:{ left:48, right:20, top:40, bottom:28 },
  xAxis:{ type:'time', axisLine:{ lineStyle:{ color:'#eef0f3' } } },
  yAxis:{ type:'value', scale:true, axisLabel:{ formatter:'{value}' },
          splitLine:{ lineStyle:{ color:'#eef0f3' } } },
  series:__LINE__
});

var total = echarts.init(document.getElementById('total'));
total.setOption({
  tooltip:{ trigger:'axis',
    valueFormatter:function(v){ return '¥ ' + v.toLocaleString('zh-CN'); } },
  grid:{ left:70, right:24, top:20, bottom:28 },
  xAxis:{ type:'time', axisLine:{ lineStyle:{ color:'#eef0f3' } } },
  yAxis:{ type:'value', scale:true,
    axisLabel:{ formatter:function(v){ return (v/10000) + '万'; } },
    splitLine:{ lineStyle:{ color:'#eef0f3' } } },
  series:[{ name:'组合总市值', type:'line', showSymbol:false, smooth:true,
    data:__TOTAL__, areaStyle:{ color:'rgba(91,143,249,0.12)' },
    lineStyle:{ width:2, color:'#5b8ff9' },
    markPoint:{ symbol:'pin', symbolSize:30, data:__MARKS__ },
    markLine:{ silent:true, symbol:'none',
      lineStyle:{ type:'dashed', color:'#c08a00' },
      label:{ formatter:'投入本金 ¥{c}', position:'insideEndTop', color:'#c08a00' },
      data:[{ yAxis:__COST__ }] } }]
});

window.addEventListener('resize', function(){ pie.resize(); bar.resize(); line.resize(); total.resize(); });
</script>
</body>
</html>
"""
