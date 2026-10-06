# -*- coding: utf-8 -*-
"""每日持仓分析 · 入口。

流程：读取配置 → 抓取行情/净值 → 计算盈亏与风险 → AI 研判 → 生成 HTML 报告 → 推送。

用法：
    python main.py            # 正常跑（含推送）
    python main.py --no-push  # 只生成报告，不推送
"""
import os
import sys

import yaml

sys.stdout.reconfigure(encoding="utf-8")

from invest import analyze as ana   # noqa: E402
from invest import ai               # noqa: E402
from invest import fetch            # noqa: E402
from invest import push             # noqa: E402
from invest import report           # noqa: E402

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.yaml")
HOLDINGS_PATH = os.path.join(BASE_DIR, "holdings.yaml")


def load_config():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    with open(HOLDINGS_PATH, encoding="utf-8") as f:
        hd = yaml.safe_load(f) or {}
    cfg["holdings"] = hd.get("holdings") or []
    if not cfg["holdings"]:
        raise SystemExit("holdings.yaml 中的持仓为空，请先填写（或运行 python update_holdings.py）。")
    return cfg


def main():
    do_push = "--no-push" not in sys.argv
    cfg = load_config()

    # 1) 抓取
    print("⏳ 正在抓取行情与净值 ...")
    positions = {}
    for h in cfg["holdings"]:
        code = str(h["code"]).strip()
        type_ = h.get("type", "fund").strip().lower()
        market = str(h.get("market", "")).strip()
        try:
            positions[code] = fetch.fetch_one(code, type_, market)
            print(f"  ✓ {positions[code]['name']}（{code}）")
        except Exception as e:  # noqa: BLE001
            positions[code] = None
            print(f"  ✗ {code} 抓取失败：{e}")

    # 1.5) 解析基金重仓股（成分股）今日表现
    for code, pos in positions.items():
        if pos and pos.get("type") == "fund" and pos.get("stock_codes_raw"):
            try:
                symbols = [fetch.stock_code_to_symbol(e) for e in pos["stock_codes_raw"]]
                quotes = fetch.fetch_stock_batch(symbols)
                pos["top_stocks"] = [
                    {"code": e[:-1], "name": quotes[sym]["name"],
                     "daily_pct": quotes[sym]["daily_pct"]}
                    for e, sym in zip(pos["stock_codes_raw"], symbols) if sym in quotes
                ]
            except Exception as e:  # noqa: BLE001
                pos["top_stocks"] = []
                print(f"  ⚠ {code} 重仓股解析失败：{e}")

    # 1.6) 抓取今日要闻
    try:
        news = fetch.fetch_news(15)
    except Exception as e:  # noqa: BLE001
        news = []
        print(f"  ⚠ 新闻抓取失败：{e}")

    # 2) 计算
    summary = ana.analyze(positions, cfg["holdings"], news=news)

    # 3) AI 研判
    print("🤖 生成 AI 研判 ...")
    ai_text = ai.generate_analysis(summary, cfg)

    # 4) 生成报告
    report_dir = os.path.join(BASE_DIR, cfg.get("report_dir", "output"))
    html_path = report.save(summary, ai_text, report_dir)

    # 5) 控制台摘要
    print("\n" + ana.text_summary(summary))
    print(f"\n✅ 报告已生成：{html_path}")

    # 6) 推送
    if do_push:
        title = f"每日持仓分析 {summary['date']}｜今日{summary['daily_pct']:+.2f}%"
        push_md = ana.push_summary(summary, ai_text)
        push_html = ana.push_html(summary, ai_text)
        results = push.push_all(cfg, title, push_md, push_html, html_path)
        if results:
            for name, ok in results:
                print(f"  {'✓' if ok else '✗'} {name}")
        else:
            print("ℹ  未配置任何推送渠道（在 config.yaml 的 push 段填写即可开启）。")
    else:
        print("ℹ  已跳过推送（--no-push）。")


if __name__ == "__main__":
    main()
