# -*- coding: utf-8 -*-
"""交互式更新持仓。

用法： python update_holdings.py

支持：
  1. 新增持仓（已知份额 + 成本价）
  2. 按「买入金额 + 日期」自动换算份额（适合场外基金追加/定投）
  3. 修改 / 删除持仓
"""
import os
import sys

import yaml

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

BASE = os.path.dirname(os.path.abspath(__file__))
HP = os.path.join(BASE, "holdings.yaml")
sys.path.insert(0, BASE)
from invest import fetch  # noqa: E402

HEADER = ("# 持仓清单（可用 python update_holdings.py 交互式修改，也可手动编辑）\n"
          "# type: fund=场外基金, stock=股票(沪市sh/深市sz)\n")


def load():
    if os.path.exists(HP):
        with open(HP, encoding="utf-8") as f:
            return (yaml.safe_load(f) or {}).get("holdings", [])
    return []


def save(holdings):
    body = yaml.safe_dump({"holdings": holdings}, allow_unicode=True,
                          sort_keys=False, default_flow_style=False)
    with open(HP, "w", encoding="utf-8") as f:
        f.write(HEADER + body)
    print("✅ 已保存到 holdings.yaml\n")


def ask(prompt, default=None):
    p = prompt + (f"（回车=默认 {default}）" if default not in (None, "") else "") + "："
    v = input(p).strip()
    return v if v != "" else default


def to_float(v):
    try:
        return float(str(v).replace(",", ""))
    except (ValueError, TypeError):
        return None


def show(holdings):
    print("\n========== 当前持仓 ==========")
    if not holdings:
        print("  （空）")
    for i, h in enumerate(holdings, 1):
        typ = "基金" if h["type"] == "fund" else "股票"
        flag = "（已清仓）" if h.get("closed") else ""
        print(f"  {i}. {h['name']}（{h['code']}）{typ}  份额 {h['shares']}  成本 {h['cost_price']}{flag}")
    print("==============================\n")


def add_manual(holdings):
    code = (ask("代码") or "").strip()
    if not code:
        print("⚠ 代码不能为空，已取消。\n")
        return holdings
    typ = (ask("类型 fund=基金 / stock=股票", "fund") or "").strip().lower()
    shares = to_float(ask("份额/股数"))
    cost = to_float(ask("成本净值/成本价"))
    if shares is None or cost is None or shares <= 0 or cost <= 0:
        print("⚠ 份额/成本无效，已取消。\n")
        return holdings
    name = (ask("名称（回车自动获取）", "") or "").strip()
    if not name:
        try:
            name = fetch.fetch_one(code, typ, "").get("name", code)
        except Exception:  # noqa: BLE001
            name = code
        print(f"  已自动获取名称：{name}")
    h = {"code": code, "type": typ, "name": name, "shares": shares, "cost_price": cost}
    if typ == "stock":
        h["market"] = (ask("市场 sh=沪市 / sz=深市", "sh") or "").strip().lower()
    holdings.append(h)
    print(f"  ✓ 已新增：{name}\n")
    return holdings


def add_by_amount(holdings):
    code = (ask("基金代码") or "").strip()
    if not code:
        print("⚠ 代码不能为空，已取消。\n")
        return holdings
    try:
        d = fetch.fetch_fund(code)
    except Exception as e:  # noqa: BLE001
        print(f"⚠ 未取到基金信息：{e}，已取消。\n")
        return holdings
    amt = to_float(ask("买入金额（元）"))
    if amt is None or amt <= 0:
        print("⚠ 金额无效，已取消。\n")
        return holdings
    date = (ask("买入日期（YYYY-MM-DD）", d["date"]) or "").strip()
    nav, used = None, None
    for dd, p in d["history"]:
        if dd >= date:
            nav, used = p, dd
            break
    if nav is None:
        nav, used = d["price"], d["date"]
    shares = amt / nav
    print(f"  → {d['name']}：{amt} 元 ÷ {used} 净值 {nav:.4f} ≈ {shares:,.2f} 份")
    trade = {"date": date, "action": "buy", "amount": amt,
             "shares": round(shares, 2), "nav": round(nav, 4)}
    for h in holdings:
        if h["type"] == "fund" and str(h["code"]) == code:
            old_shares, old_cost = float(h["shares"]), float(h["cost_price"])
            total_amt = old_shares * old_cost + amt
            new_shares = old_shares + shares
            h["shares"] = round(new_shares, 2)
            h["cost_price"] = round(total_amt / new_shares, 4)
            h.setdefault("trades", []).append(trade)
            print(f"  ✓ 已追加到现有持仓，现份额 {h['shares']:,.2f}，成本净值 {h['cost_price']:.4f}（已记录买入点）\n")
            return holdings
    holdings.append({"code": code, "type": "fund", "name": d["name"],
                     "shares": round(shares, 2), "cost_price": round(nav, 4),
                     "trades": [trade]})
    print(f"  ✓ 已新增：{d['name']}（已记录买入点）\n")
    return holdings


def edit(holdings):
    show(holdings)
    idx = to_float(ask("要修改第几个（回车取消）", ""))
    if idx is None or idx < 1 or idx > len(holdings) or idx != int(idx):
        print("⚠ 序号无效，已取消。\n")
        return holdings
    h = holdings[int(idx) - 1]
    for key, label in [("shares", "份额/股数"), ("cost_price", "成本净值/成本价")]:
        cur = h.get(key)
        v = to_float(ask(f"{label}（当前 {cur}，回车不改）", ""))
        if v is not None and v > 0:
            h[key] = v
    print("  ✓ 已更新\n")
    return holdings


def delete(holdings):
    show(holdings)
    idx = to_float(ask("要删除第几个（回车取消）", ""))
    if idx is None or idx < 1 or idx > len(holdings) or idx != int(idx):
        print("⚠ 序号无效，已取消。\n")
        return holdings
    h = holdings.pop(int(idx) - 1)
    print(f"  ✓ 已删除：{h['name']}\n")
    return holdings


def sell(holdings):
    """记录一笔卖出：减少份额并标记卖出点；全部卖出则移出持仓。"""
    show(holdings)
    idx = to_float(ask("要记录哪只的卖出（回车取消）", ""))
    if idx is None or idx < 1 or idx > len(holdings) or idx != int(idx):
        print("⚠ 序号无效，已取消。\n")
        return holdings
    h = holdings[int(idx) - 1]
    try:
        d = fetch.fetch_one(str(h["code"]), h["type"], h.get("market", ""))
    except Exception as e:  # noqa: BLE001
        print(f"⚠ 未取到行情：{e}，已取消。\n")
        return holdings
    date = (ask("卖出日期（YYYY-MM-DD）", d["date"]) or "").strip()
    nav, used = None, None
    for dd, p in d["history"]:
        if dd >= date:
            nav, used = p, dd
            break
    if nav is None:
        nav, used = d["price"], d["date"]
    cur_shares = float(h["shares"])
    print(f"  当前持有 {cur_shares:,.2f} 份，{used} 净值/价格 {nav:.4f}")
    mode = (ask("按 金额(1) 还是 份额(2) 卖出", "1") or "1").strip()
    sold_shares, amount = None, None
    if mode == "2":
        sold_shares = to_float(ask("卖出份额"))
        amount = sold_shares * nav if sold_shares else None
    else:
        amount = to_float(ask("卖出金额（元）"))
        sold_shares = amount / nav if amount else None
    if sold_shares is None or sold_shares <= 0:
        print("⚠ 数值无效，已取消。\n")
        return holdings
    if sold_shares > cur_shares + 0.01:
        print(f"⚠ 卖出份额 {sold_shares:,.2f} 超过持有 {cur_shares:,.2f}，已取消。\n")
        return holdings
    sold_shares = min(sold_shares, cur_shares)
    new_shares = cur_shares - sold_shares
    trade = {"date": date, "action": "sell",
             "amount": round(amount if amount else sold_shares * nav, 2),
             "shares": round(sold_shares, 2), "nav": round(nav, 4)}
    h.setdefault("trades", []).append(trade)
    if new_shares < 0.01:
        h["shares"] = 0.0
        h["closed"] = True
        print(f"  ✓ 已记录卖出，「{h['name']}」已全部卖出（标记清仓，交易记录保留）。\n")
    else:
        h["shares"] = round(new_shares, 2)
        print(f"  ✓ 已记录卖出 {sold_shares:,.2f} 份，剩余 {new_shares:,.2f} 份（已标记卖出点）。\n")
    return holdings


def main():
    holdings = load()
    while True:
        show(holdings)
        print("1) 新增持仓（已知份额/成本）   2) 按买入金额新增/追加")
        print("3) 修改持仓   4) 删除持仓   5) 记录卖出   0) 退出")
        c = (ask("请选择") or "").strip()
        if c == "1":
            holdings = add_manual(holdings)
            save(holdings)
        elif c == "2":
            holdings = add_by_amount(holdings)
            save(holdings)
        elif c == "3":
            holdings = edit(holdings)
            save(holdings)
        elif c == "4":
            holdings = delete(holdings)
            save(holdings)
        elif c == "5":
            holdings = sell(holdings)
            save(holdings)
        elif c == "0":
            save(holdings)
            print("👋 已退出。运行 python main.py 生成最新报告。")
            break
        else:
            print("⚠ 无效选项\n")


if __name__ == "__main__":
    main()
