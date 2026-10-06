# -*- coding: utf-8 -*-
"""数据抓取：基金净值、股票行情与历史数据。

数据源为天天基金 / 东方财富的公开接口，无需登录：
- 基金：https://fund.eastmoney.com/pingzhongdata/{code}.js  一次性拿到名称 + 全历史净值
- 股票：https://push2.eastmoney.com/api/qt/stock/get          实时行情
        https://push2his.eastmoney.com/api/qt/stock/kline/get 前复权历史K线
"""
import json
import re
from datetime import datetime, timedelta, timezone

import requests

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
TIMEOUT = 20
_CN_TZ = timezone(timedelta(hours=8))


def _get(url, params=None, referer=None, timeout=TIMEOUT):
    headers = dict(UA)
    if referer:
        headers["Referer"] = referer
    resp = requests.get(url, params=params, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp


def _ts_to_date(ms):
    return datetime.fromtimestamp(int(ms) / 1000, _CN_TZ).strftime("%Y-%m-%d")


def _div(v, dec):
    return (v / (10 ** dec)) if isinstance(v, (int, float)) else None


def fetch_fund(code):
    """抓取基金：名称 + 最新净值 + 完整历史净值（升序）。"""
    url = f"https://fund.eastmoney.com/pingzhongdata/{code}.js"
    js = _get(url).text.lstrip("﻿")
    m_name = re.search(r'var fS_name = "(.*?)";', js)
    name = m_name.group(1).strip() if m_name else code
    m_nt = re.search(r"var Data_netWorthTrend = (\[.*?\]);", js, re.S)
    if not m_nt:
        raise RuntimeError(f"基金 {code} 未取到净值数据")
    trend = json.loads(m_nt.group(1))
    history = [(_ts_to_date(t["x"]), float(t["y"])) for t in trend]
    last = trend[-1]
    m_sc = re.search(r"var stockCodes=\s*(\[.*?\]);", js)
    stock_codes_raw = json.loads(m_sc.group(1)) if m_sc else []
    return {
        "code": code,
        "name": name,
        "type": "fund",
        "price": float(last["y"]),                                    # 最新单位净值
        "date": _ts_to_date(last["x"]),
        "daily_pct": float(last.get("equityReturn") or 0.0),          # 当日涨跌（%）
        "history": history,                                            # [(date, nav), ...] 升序
        "stock_codes_raw": stock_codes_raw,                            # 重仓股（最新季报），如 ["6005191", ...]
    }


def _sym(code, market):
    return ("sh" if str(market).lower().startswith("sh") else "sz") + str(code)


def fetch_stock(code, market):
    """抓取股票：优先东方财富，失败自动切换腾讯行情。"""
    sym = _sym(code, market)
    try:
        return _em_stock(sym)
    except Exception:
        return _tx_stock(sym)


def _em_stock(sym):
    code = sym[2:]
    secid = f"{'1' if sym.startswith('sh') else '0'}.{code}"
    fields = "f43,f57,f58,f59,f60,f169,f170"
    data = _get("https://push2.eastmoney.com/api/qt/stock/get",
                params={"secid": secid, "fields": fields}).json().get("data")
    if not data:
        raise RuntimeError(f"股票 {code} 未取到行情")
    dec = int(data.get("f59") or 2)
    history = _em_kline(secid)
    return {
        "code": code, "name": data.get("f58") or code, "type": "stock",
        "price": _div(data.get("f43"), dec),
        "prev_close": _div(data.get("f60"), dec),
        "daily_pct": float(data.get("f170") or 0) / 100.0,
        "daily_chg": _div(data.get("f169"), dec),
        "history": history,
        "date": history[-1][0] if history else datetime.now(_CN_TZ).strftime("%Y-%m-%d"),
    }


def _em_kline(secid, lmt=300):
    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    params = {
        "secid": secid, "klt": "101", "fqt": "1", "lmt": str(lmt),
        "end": "20500101",
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56",
    }
    data = _get(url, params=params).json().get("data") or {}
    hist = []
    for k in data.get("klines") or []:
        p = k.split(",")
        if len(p) >= 3:
            hist.append((p[0], float(p[2])))   # date, close（前复权）
    return hist


def _tx_stock(sym):
    code = sym[2:]
    resp = _get(f"https://qt.gtimg.cn/q={sym}")
    resp.encoding = "gbk"
    fields = resp.text.split('"')[1].split("~")
    # 腾讯字段：1名称 2代码 3当前价 4昨收 30时间 31涨跌额 32涨跌幅%
    name = fields[1]
    price = float(fields[3])
    prev = float(fields[4])
    chg = float(fields[31])
    pct = float(fields[32])
    history = _tx_kline(sym)
    return {
        "code": code, "name": name, "type": "stock",
        "price": price, "prev_close": prev,
        "daily_pct": pct, "daily_chg": chg,
        "history": history,
        "date": history[-1][0] if history else _today(),
    }


def _tx_kline(sym, n=320):
    url = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
    data = _get(url, params={"param": f"{sym},day,,,{n},qfq"}).json().get("data", {})
    node = data.get(sym, {})
    klines = node.get("qfqday") or node.get("day") or []
    hist = []
    for k in klines:
        if len(k) >= 5:
            hist.append((k[0], float(k[2])))   # date, close（前复权）
    return hist


def _today():
    return datetime.now(_CN_TZ).strftime("%Y-%m-%d")


def fetch_crypto(code, api_key):
    """抓取加密货币价格与历史（CryptoCompare，国内可达）。

    code 如 'BTC' 或 'BTC-USDT'；价格与历史统一换算成人民币（CNY）。
    返回额外带 fx（CNY/USD 汇率），用于把 USDT 成本换算成 CNY。
    """
    fsym = str(code).split("-")[0].upper()
    if not api_key:
        raise RuntimeError("缺少 CryptoCompare API Key（config.yaml 的 crypto.api_key）")
    p = _get("https://min-api.cryptocompare.com/data/price",
             params={"fsym": fsym, "tsyms": "USD,CNY", "api_key": api_key}).json()
    if "CNY" not in p or "USD" not in p:
        raise RuntimeError(f"CryptoCompare 返回异常：{p}")
    price_cny = float(p["CNY"])
    price_usd = float(p["USD"])
    fx = price_cny / price_usd if price_usd else 7.2
    hist = _get("https://min-api.cryptocompare.com/data/v2/histoday",
                params={"fsym": fsym, "tsym": "CNY", "limit": "250",
                        "api_key": api_key}).json()
    history = []
    for d in ((hist.get("Data") or {}).get("Data") or []):
        ts, close = d.get("time"), d.get("close")
        if ts and close:
            date = datetime.fromtimestamp(int(ts), _CN_TZ).strftime("%Y-%m-%d")
            history.append((date, float(close)))
    daily_pct = 0.0
    if len(history) >= 2 and history[-2][1]:
        daily_pct = (history[-1][1] / history[-2][1] - 1.0) * 100.0
    return {
        "code": code,
        "name": fsym,
        "type": "crypto",
        "price": price_cny,                                        # 现价（人民币）
        "date": history[-1][0] if history else datetime.now(_CN_TZ).strftime("%Y-%m-%d"),
        "daily_pct": daily_pct,                                    # 24 小时涨跌（%）
        "fx": fx,                                                  # CNY/USD 汇率
        "history": history,                                        # [(date, 收盘价CNY), ...] 升序
    }


def fetch_one(code, type_, market="", crypto_api_key=""):
    """按持仓类型分发抓取。"""
    if type_ == "fund":
        return fetch_fund(code)
    if type_ == "crypto":
        return fetch_crypto(code, crypto_api_key)
    return fetch_stock(code, market)


def stock_code_to_symbol(entry):
    """天天基金重仓股条目 "6005191" -> 腾讯行情代码 "sh600519"（末位 1=沪 0=深）。"""
    return ("sh" if str(entry)[-1] == "1" else "sz") + str(entry)[:-1]


def fetch_stock_batch(symbols):
    """批量抓取股票名称与今日涨跌（腾讯行情，一次请求）。symbols: ['sh600519', ...]。"""
    out = {}
    if not symbols:
        return out
    resp = _get("https://qt.gtimg.cn/q=" + ",".join(symbols))
    resp.encoding = "gbk"
    for line in resp.text.strip().split(";"):
        line = line.strip()
        if not line or '="' not in line:
            continue
        sym = line.split("=")[0].split("_")[-1]
        try:
            fields = line.split('"')[1].split("~")
            out[sym] = {
                "name": fields[1],
                "price": float(fields[3]),
                "daily_pct": float(fields[32]),
            }
        except (IndexError, ValueError):
            continue
    return out


def fetch_news(limit=15):
    """抓取东方财富 7x24 快讯（今日要闻）。返回 [{time, title, summary}, ...]。"""
    url = "https://np-weblist.eastmoney.com/comm/web/getFastNewsList"
    params = {"client": "web", "biz": "web_724", "fastColumn": "102",
              "sortEnd": "", "pageSize": str(limit), "req_trace": "1"}
    data = _get(url, params=params).json().get("data") or {}
    items = []
    for it in data.get("fastNewsList", []):
        t = it.get("showTime", "")
        items.append({
            "time": t[11:16] if len(t) >= 16 else t,
            "title": it.get("title", ""),
            "summary": it.get("summary", ""),
        })
    return items
