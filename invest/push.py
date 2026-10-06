# -*- coding: utf-8 -*-
"""推送报告摘要到微信 / 钉钉 / 邮件。所有渠道留空则自动跳过。"""
import base64
import hashlib
import hmac
import os
import smtplib
import time
import urllib.parse
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests


def _send_wechat_sct(sendkey, title, text):
    r = requests.post(f"https://sctapi.ftqq.com/{sendkey}.send",
                      data={"title": title, "desp": text}, timeout=20)
    r.raise_for_status()
    return r.json().get("code") == 0


def _send_pushplus(token, title, html_content):
    r = requests.post("https://www.pushplus.plus/send",
                      json={"token": token, "title": title,
                            "content": html_content, "template": "html"}, timeout=20)
    r.raise_for_status()
    return r.json().get("code") == 200


def _send_dingtalk(webhook, secret, title, text):
    url = webhook
    if secret:
        ts = str(round(time.time() * 1000))
        string_to_sign = f"{ts}\n{secret}"
        sign_code = hmac.new(secret.encode(), string_to_sign.encode(),
                             digestmod=hashlib.sha256).digest()
        url = f"{webhook}&timestamp={ts}&sign={urllib.parse.quote_plus(base64.b64encode(sign_code))}"
    r = requests.post(url, json={"msgtype": "markdown",
                                 "markdown": {"title": title, "text": text}}, timeout=20)
    r.raise_for_status()
    return r.json().get("errcode") == 0


def _send_email(cfg, title, text, html_path=None):
    msg = MIMEMultipart()
    msg["Subject"] = title
    msg["From"] = cfg["username"]
    msg["To"] = cfg["to"]
    msg.attach(MIMEText(text, "plain", "utf-8"))
    if html_path:
        with open(html_path, "rb") as f:
            part = MIMEApplication(f.read(), _subtype="html")
        part.add_header("Content-Disposition", "attachment",
                        filename=("utf-8", "", os.path.basename(html_path)))
        msg.attach(part)
    with smtplib.SMTP_SSL(cfg["smtp_host"], int(cfg["smtp_port"])) as server:
        server.login(cfg["username"], cfg["password"])
        server.sendmail(cfg["username"], cfg["to"].split(","), msg.as_string())
    return True


def push_all(config, title, text_md, text_html, html_path=None):
    """依次尝试各推送渠道，返回 [(渠道名, 是否成功)]。"""
    p = config.get("push") or {}
    results = []
    if p.get("wechat_sendkey"):
        try:
            results.append(("微信·Server酱", _send_wechat_sct(p["wechat_sendkey"], title, text_md)))
        except Exception as e:  # noqa: BLE001
            results.append((f"微信·Server酱（失败：{e}）", False))
    if p.get("pushplus_token"):
        try:
            results.append(("微信·PushPlus", _send_pushplus(p["pushplus_token"], title, text_html)))
        except Exception as e:  # noqa: BLE001
            results.append((f"微信·PushPlus（失败：{e}）", False))
    if p.get("dingtalk_webhook"):
        try:
            results.append(("钉钉", _send_dingtalk(p["dingtalk_webhook"],
                                                   p.get("dingtalk_secret"), title, text_md)))
        except Exception as e:  # noqa: BLE001
            results.append((f"钉钉（失败：{e}）", False))
    em = p.get("email") or {}
    if em.get("enabled") and em.get("username") and em.get("to"):
        try:
            results.append(("邮件", _send_email(em, title, text_md, html_path)))
        except Exception as e:  # noqa: BLE001
            results.append((f"邮件（失败：{e}）", False))
    return results
