# -*- coding: utf-8 -*-
"""AI 研判：优先调用大模型，无 Key 时退化为内置规则研判。"""
import requests


def _pct(v):
    return "—" if v is None else f"{v:.2f}%"


def _build_prompt(s):
    lines = [
        f"今天是 {s['date']}，以下是用户投资组合的【每日】概况（人民币，中国大陆）：",
        f"总市值 {s['total_market_value']:,.2f} 元，今日盈亏 {s['daily_pnl']:+,.2f} 元"
        f"（{s['daily_pct']:+.2f}%），累计盈亏 {s['total_pnl_pct']:+.2f}%。",
        "",
        "各持仓近期表现：",
    ]
    for h in s["holdings"]:
        if h["ok"]:
            lines.append(
                f"- {h['name']}（{h['code']}）：今日 {h['daily_pct']:+.2f}%，"
                f"近1周 {_pct(h.get('ret_1w'))}，近1月 {_pct(h.get('ret_1m'))}。"
            )
    for h in s["holdings"]:
        if h.get("top_stocks"):
            stocks = "、".join(f"{st['name']}({st['daily_pct']:+.1f}%)" for st in h["top_stocks"])
            lines.append(f"「{h['name']}」重仓股今日涨跌：{stocks}。")
    if s.get("news"):
        lines.append("")
        lines.append("今日要闻：")
        for n in s["news"][:12]:
            lines.append(f"- {n['title']}")
    lines.append("")
    lines.append(
        "请做【每日】视角的简洁研判，直接输出要点："
        "1) 今日要闻/行业动态对持仓的影响；2) 重仓股异动如何解释基金今日涨跌；"
        "3) 近期需要关注的短期风险点。控制在 200 字内，只谈当下，不要给长期持有或再平衡建议。"
    )
    return "\n".join(lines)


def _llm(s, ai):
    url = ai["base_url"].rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {ai['api_key']}",
               "Content-Type": "application/json"}
    body = {
        "model": ai["model"],
        "messages": [{"role": "user", "content": _build_prompt(s)}],
        "temperature": 0.4,
        "max_tokens": 1200,
    }
    resp = requests.post(url, headers=headers, json=body, timeout=60)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def _rule_based(s):
    pts = []
    top = max((h for h in s["holdings"] if h["ok"]), key=lambda h: h["weight"], default=None)
    if top and top["weight"] > 40:
        pts.append(f"仓位高度集中于「{top['name']}」（{top['weight']:.0f}%），建议适度分散。")
    max_vol = max((h["vol"] for h in s["holdings"]
                   if h["ok"] and h.get("vol") is not None), default=0.0)
    if max_vol > 0.35:
        pts.append("部分持仓年化波动率超过 35%，风险偏高。")
    worst_mdd = min((h["mdd"] for h in s["holdings"]
                     if h["ok"] and h.get("mdd") is not None), default=0.0)
    if worst_mdd < -0.25:
        pts.append("部分持仓历史最大回撤超过 25%，需警惕。")
    stock_pct = s["allocation"].get("stock", 0.0)
    if stock_pct > 60:
        pts.append(f"股票类资产占比 {stock_pct:.0f}%，权益仓位较高，注意波动。")
    if s["daily_pct"] < -2:
        pts.append("今日组合回撤明显，关注是否有事件驱动。")
    if not pts:
        pts.append("组合整体较为均衡，暂无显著风险信号。")
    pts.append("（以上为基于规则的自动研判，不构成投资建议。）")
    return "\n".join("• " + p for p in pts)


def generate_analysis(summary, config):
    ai = config.get("ai") or {}
    if ai.get("api_key") and str(ai.get("provider", "")).lower() != "none":
        try:
            return _llm(summary, ai)
        except Exception as e:  # noqa: BLE001
            return _rule_based(summary) + f"\n\n（大模型调用失败，已退回规则研判：{e}）"
    return _rule_based(summary)
