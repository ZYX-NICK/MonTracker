# -*- coding: utf-8 -*-
"""计算盈亏、仓位、风险指标。"""
import bisect
import html as _html
from datetime import datetime

TRADING_DAYS = 250


def _returns(prices):
    return [prices[i] / prices[i - 1] - 1.0 for i in range(1, len(prices))]


def annualized_vol(prices, window=250):
    """年化波动率。"""
    p = prices[-window - 1:]
    r = _returns(p)
    if len(r) < 2:
        return None
    mean = sum(r) / len(r)
    var = sum((x - mean) ** 2 for x in r) / (len(r) - 1)
    return (var ** 0.5) * (TRADING_DAYS ** 0.5)


def max_drawdown(prices, window=250):
    """最大回撤（负数）。"""
    p = prices[-window - 1:]
    peak = p[0]
    mdd = 0.0
    for x in p:
        peak = max(peak, x)
        mdd = min(mdd, (x - peak) / peak)
    return mdd


def sharpe(prices, window=250, rf=0.0):
    """夏普比率（年化，无风险利率默认 0）。"""
    r = _returns(prices[-window - 1:])
    if len(r) < 2:
        return None
    mean = sum(r) / len(r)
    var = sum((x - mean) ** 2 for x in r) / (len(r) - 1)
    std = var ** 0.5
    if std == 0:
        return None
    return (mean - rf / TRADING_DAYS) / std * (TRADING_DAYS ** 0.5)


def period_return(prices, days=None):
    """近 days 个交易日收益率（%）；days=None 表示全程。"""
    if len(prices) < 2:
        return None
    base = prices[0] if days is None else (prices[-days - 1] if len(prices) > days else prices[0])
    return (prices[-1] / base - 1.0) * 100.0


def _history_returns(history):
    """[(date, price)] -> {date: 当日收益率}。"""
    rets = {}
    for i in range(1, len(history)):
        prev = history[i - 1][1]
        cur = history[i][1]
        if prev:
            rets[history[i][0]] = cur / prev - 1.0
    return rets


def _trade_markers(trades, history):
    """把买卖记录映射到历史净值，返回 [{date, action, amount, nav}, ...]。"""
    if not trades:
        return []
    hm = {d: p for d, p in history}
    dts = sorted(hm)
    markers = []
    for t in trades:
        nav = None
        for dd in dts:
            if dd >= t["date"]:
                nav = hm[dd]
                break
        if nav is None and dts:
            nav = hm[dts[-1]]
        if nav is not None:
            markers.append({"date": t["date"], "action": t.get("action", "buy"),
                            "amount": t.get("amount"), "nav": nav})
    return markers


def _build_trade_log(holdings, positions):
    """汇总所有持仓（含已清仓）的买卖记录，按日期倒序，形成交易日志。"""
    entries = []
    for h in holdings:
        code = str(h["code"])
        name = h.get("name") or code
        data = positions.get(code)
        hist = data.get("history", []) if data else []
        hm = {d: p for d, p in hist}
        dts = sorted(hm)
        for t in h.get("trades", []):
            nav = t.get("nav")
            shares = t.get("shares")
            # 旧格式记录里没有净值/份额时，从历史净值推算
            if (nav is None or shares is None) and hist:
                nav2 = None
                for dd in dts:
                    if dd >= t.get("date", ""):
                        nav2 = hm[dd]
                        break
                if nav2 is None and dts:
                    nav2 = hm[dts[-1]]
                if nav is None:
                    nav = nav2
                if shares is None and nav and t.get("amount"):
                    shares = t.get("amount") / nav
            entries.append({
                "date": t.get("date", ""),
                "action": t.get("action", "buy"),
                "code": code,
                "name": name,
                "amount": t.get("amount"),
                "nav": nav,
                "shares": shares,
            })
    entries.sort(key=lambda e: e["date"], reverse=True)
    return entries


def analyze(positions, holdings, news=None):
    """positions: {code: 抓取结果}，holdings: 配置文件里的持仓清单。"""
    active = [h for h in holdings if not h.get("closed")
              and float(h.get("shares", 0) or 0) > 0]
    rows = []
    for h in active:
        data = positions.get(h["code"])
        shares = float(h["shares"])
        cost_price = float(h["cost_price"])
        row = {
            "code": h["code"],
            "type": h["type"],
            "market": h.get("market", ""),
            "name": (h.get("name") or "").strip() or (data["name"] if data else h["code"]),
            "shares": shares,
            "cost_price": cost_price,
            "ok": data is not None,
        }
        if data:
            price = data["price"]
            mv = shares * price
            cost = shares * cost_price
            pnl = mv - cost
            row.update({
                "price": price,
                "date": data["date"],
                "daily_pct": data["daily_pct"],
                "market_value": mv,
                "cost_value": cost,
                "pnl": pnl,
                "pnl_pct": (pnl / cost * 100.0) if cost else 0.0,
                "daily_pnl": (mv - mv / (1 + data["daily_pct"] / 100.0))
                             if data["daily_pct"] else 0.0,
            })
            prices = [p for _, p in data["history"]]
            row.update({
                "vol": annualized_vol(prices),
                "mdd": max_drawdown(prices),
                "sharpe": sharpe(prices),
                "ret_1y": period_return(prices, 250),
                "ret_6m": period_return(prices, 125),
                "ret_1m": period_return(prices, 22),
                "ret_1w": period_return(prices, 5),
                "top_stocks": data.get("top_stocks", []),
                "trade_markers": _trade_markers(h.get("trades"), data["history"]),
                "history": data["history"],
            })
        else:
            row.update({
                "price": None, "date": None, "daily_pct": None,
                "market_value": None, "cost_value": cost,
                "pnl": None, "pnl_pct": None, "daily_pnl": None,
                "vol": None, "mdd": None, "sharpe": None,
                "ret_1y": None, "ret_6m": None, "ret_1m": None, "ret_1w": None,
                "top_stocks": [], "trade_markers": [], "history": [],
            })
        rows.append(row)

    total_mv = sum(r["market_value"] or 0.0 for r in rows)
    total_cost = sum(r["cost_value"] or 0.0 for r in rows)
    total_pnl = sum(r["pnl"] or 0.0 for r in rows)
    total_daily_pnl = sum(r["daily_pnl"] or 0.0 for r in rows)
    for r in rows:
        r["weight"] = ((r["market_value"] or 0.0) / total_mv * 100.0) if total_mv else 0.0

    dates = [r["date"] for r in rows if r.get("date")]
    report_date = max(dates) if dates else datetime.now().strftime("%Y-%m-%d")

    # 资产类型分布
    alloc = {}
    for r in rows:
        if r["market_value"]:
            alloc.setdefault(r["type"], 0.0)
            alloc[r["type"]] += r["market_value"]
    alloc_weight = {k: (v / total_mv * 100.0 if total_mv else 0.0) for k, v in alloc.items()}

    return {
        "date": report_date,
        "total_market_value": total_mv,
        "total_cost": total_cost,
        "total_pnl": total_pnl,
        "total_pnl_pct": (total_pnl / total_cost * 100.0) if total_cost else 0.0,
        "daily_pnl": total_daily_pnl,
        "daily_pct": (sum(r["weight"] * (r["daily_pct"] or 0.0) for r in rows) / 100.0)
                     if total_mv else 0.0,
        "holdings": rows,
        "allocation": alloc_weight,          # {fund: %, stock: %}
        "portfolio_risk": _portfolio_risk(rows),
        "value_series": _portfolio_value_series(rows),
        "news": news or [],
        "trade_log": _build_trade_log(holdings, positions),
        "n_holdings": len(rows),
        "n_ok": sum(1 for r in rows if r["ok"]),
    }


def _portfolio_risk(rows):
    """用当前市值权重合成组合历史日收益（近似固定权重），计算组合风险指标。"""
    valid = [r for r in rows if r["ok"] and len(r.get("history", [])) >= 60]
    total_w = sum(r["weight"] for r in valid)
    if total_w <= 0:
        return {}
    acc = {}
    for r in valid:
        w = r["weight"] / total_w
        for d, ret in _history_returns(r["history"]).items():
            acc.setdefault(d, [0.0, 0.0])
            acc[d][0] += w * ret
            acc[d][1] += w
    rets = [acc[d][0] for d in sorted(acc) if acc[d][1] > 0.5]
    if len(rets) < 2:
        return {}
    nav = [1.0]
    for ret in rets:
        nav.append(nav[-1] * (1 + ret))
    return {
        "vol": annualized_vol(nav),
        "mdd": max_drawdown(nav),
        "sharpe": sharpe(nav),
        "n_days": len(rets),
    }


def _portfolio_value_series(rows, window=250):
    """按当前份额回测的组合总市值历史（前向填充），返回 [(date, value), ...]。"""
    per = []
    for r in rows:
        if r["ok"] and len(r.get("history", [])) >= 2:
            ds = [d for d, _ in r["history"]]
            ps = [p for _, p in r["history"]]
            per.append((r["shares"], ds, ps))
    if not per:
        return []
    dates = sorted({d for _, ds, _ in per for d in ds})[-window:]
    series = []
    for d in dates:
        val = 0.0
        for shares, ds, ps in per:
            i = bisect.bisect_right(ds, d) - 1
            if i >= 0:
                val += shares * ps[i]
        series.append((d, round(val, 2)))
    return series


def text_summary(s):
    """生成控制台用的文本摘要。"""
    L = [
        f"📊 每日持仓分析 · {s['date']}",
        "",
        f"总市值：{s['total_market_value']:,.2f} 元",
        f"累计盈亏：{s['total_pnl']:+,.2f} 元（{s['total_pnl_pct']:+.2f}%）",
        f"今日盈亏：{s['daily_pnl']:+,.2f} 元（{s['daily_pct']:+.2f}%）",
        "",
        "持仓明细：",
    ]
    for h in s["holdings"]:
        if h["ok"]:
            L.append(f"· {h['name']}（{h['code']}） 仓位 {h['weight']:.1f}% "
                     f"累计 {h['pnl_pct']:+.2f}% 今日 {h['daily_pct']:+.2f}%")
        else:
            L.append(f"· {h['name']}（{h['code']}） ⚠ 数据获取失败")
    return "\n".join(L)


def _short_name(name):
    """去掉基金名称常见后缀，让推送里的表格更紧凑。"""
    for suf in ("股票发起式A", "股票发起式C", "混合C", "混合A", "债券A", "债券C",
                "指数A", "指数C", "联接A", "联接C"):
        if name.endswith(suf):
            return name[:-len(suf)]
    return name


def push_summary(s, ai_text=""):
    """生成微信推送用的 Markdown 摘要（含 AI 研判）。"""
    L = [
        f"**总市值** ¥{s['total_market_value']:,.0f}",
        f"**今日** {s['daily_pct']:+.2f}%（{s['daily_pnl']:+,.0f}元）　"
        f"**累计** {s['total_pnl_pct']:+.2f}%（{s['total_pnl']:+,.0f}元）",
        "",
        "**持仓表现**",
    ]
    for h in s["holdings"]:
        if h["ok"]:
            nm = _short_name(h["name"])
            L.append(f"· {nm}｜今日 {h['daily_pct']:+.2f}%｜累计 {h['pnl_pct']:+.2f}%"
                     f"｜仓位 {h['weight']:.1f}%")
        else:
            L.append(f"· {h['name']}｜⚠ 数据获取失败")
    if ai_text:
        L += ["", "**🤖 AI 研判**", ai_text.strip()]
    L += ["", "📎 完整可视化报告见 output/latest.html"]
    return "\n".join(L)


def _wan(v):
    """金额格式化：大额显示万元，小额显示元。"""
    if v is None:
        return "—"
    if abs(v) >= 10000:
        return f"{v / 10000:.2f}万"
    return f"{v:,.0f}"


def push_html(s, ai_text=""):
    """生成 PushPlus HTML 推送：KPI 卡片 + 持仓表 + 重仓股 + 要闻 + AI 研判。"""
    UP = "#e0322b"
    DOWN = "#0f9d58"

    def c(v):
        return UP if (v or 0) >= 0 else DOWN

    def tile(label, main, sub, color):
        return (f'<td style="padding:10px 6px;text-align:center;background:#f6f7f9;">'
                f'<div style="font-size:11px;color:#86909c;">{label}</div>'
                f'<div style="font-size:16px;font-weight:700;color:{color};">{main}</div>'
                f'<div style="font-size:11px;color:{color};">{sub}</div></td>')

    kpi = (
        '<table style="width:100%;border-collapse:separate;border-spacing:4px 0;">'
        '<tr>'
        + tile("总市值", f"¥{_wan(s['total_market_value'])}", f"{s['n_holdings']}只持仓", "#1f2329")
        + tile("今日", f"{s['daily_pct']:+.2f}%", f"{s['daily_pnl']:+,.0f}元", c(s["daily_pnl"]))
        + tile("累计", f"{s['total_pnl_pct']:+.2f}%", f"{s['total_pnl']:+,.0f}元", c(s["total_pnl"]))
        + '</tr></table>'
    )

    rows = []
    for h in s["holdings"]:
        if not h["ok"]:
            rows.append(f'<tr><td colspan="4" style="padding:6px 4px;color:#c08a00;">'
                        f'{_html.escape(h["name"])} ⚠ 数据获取失败</td></tr>')
            continue
        nm = _html.escape(_short_name(h["name"]))
        rows.append(
            f'<tr style="border-bottom:1px solid #f2f3f5;">'
            f'<td style="padding:6px 4px;">{nm}</td>'
            f'<td style="padding:6px 4px;text-align:right;color:{c(h["daily_pct"])};">{h["daily_pct"]:+.2f}%</td>'
            f'<td style="padding:6px 4px;text-align:right;color:{c(h["pnl_pct"])};">{h["pnl_pct"]:+.2f}%</td>'
            f'<td style="padding:6px 4px;text-align:right;color:#86909c;">{h["weight"]:.1f}%</td></tr>'
        )
    table = (
        '<table style="width:100%;border-collapse:collapse;font-size:13px;">'
        '<tr style="color:#86909c;border-bottom:1px solid #e5e6eb;">'
        '<th style="padding:5px 4px;text-align:left;font-weight:500;">持仓</th>'
        '<th style="padding:5px 4px;text-align:right;font-weight:500;">今日</th>'
        '<th style="padding:5px 4px;text-align:right;font-weight:500;">累计</th>'
        '<th style="padding:5px 4px;text-align:right;font-weight:500;">仓位</th></tr>'
        + "".join(rows) + '</table>'
    )

    # 重仓股异动
    const_parts = []
    for h in s["holdings"]:
        stocks = h.get("top_stocks") or []
        if not stocks:
            continue
        top = sorted(stocks, key=lambda x: -abs(x["daily_pct"]))[:5]
        seg = [f'{_html.escape(st["name"])} <span style="color:{c(st["daily_pct"])};">{st["daily_pct"]:+.1f}%</span>'
               for st in top]
        const_parts.append(f'<div style="margin:4px 0;line-height:1.8;">'
                           f'<b style="color:#4b5563;">{_html.escape(_short_name(h["name"]))}</b>　'
                           + "　".join(seg) + '</div>')
    const_html = "".join(const_parts) if const_parts else '<div style="color:#86909c;">（无股票型基金）</div>'

    # 今日要闻
    news = s.get("news") or []
    news_html = "".join(f'<div style="padding:3px 0;">· {_html.escape(n["title"])}</div>' for n in news[:6]) \
        if news else '<div style="color:#86909c;">（无）</div>'

    ai_block = ""
    if ai_text:
        ai_esc = _html.escape(ai_text.strip()).replace("\n", "<br>")
        ai_block = f'<div style="margin-top:4px;color:#3c4043;line-height:1.7;">{ai_esc}</div>'

    def sec(title):
        return f'<div style="font-weight:700;font-size:14px;margin:14px 0 6px;">{title}</div>'

    return (
        '<div style="font-family:-apple-system,\'PingFang SC\',\'Microsoft YaHei\',sans-serif;'
        'font-size:14px;color:#1f2329;line-height:1.6;max-width:560px;">'
        f'<div style="font-size:16px;font-weight:700;padding:2px 0 2px;">📊 每日持仓分析 · {s["date"]}</div>'
        + kpi
        + sec("持仓表现") + table
        + sec("重仓股异动") + const_html
        + sec("今日要闻") + news_html
        + sec("🤖 AI 研判") + ai_block
        + '<div style="margin-top:14px;color:#86909c;font-size:12px;">📎 完整可视化报告见 output/latest.html</div>'
        '</div>'
    )
