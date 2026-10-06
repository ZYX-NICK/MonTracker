# -*- coding: utf-8 -*-
"""一键设置 / 卸载 Windows 每日定时任务。

用法（在本目录下运行）：
    python setup_task.py               # 每天 20:00 自动运行
    python setup_task.py --time 08:30  # 自定义运行时间（HH:MM）
    python setup_task.py --remove      # 删除定时任务
"""
import argparse
import os
import subprocess
import sys

TASK_NAME = "每日持仓分析"
BASE = os.path.dirname(os.path.abspath(__file__))


def _write_runner():
    """生成 run_daily.bat（用绝对 Python 路径，避免定时任务找不到 python）。"""
    bat_path = os.path.join(BASE, "run_daily.bat")
    lines = [
        "@echo off",
        f'cd /d "{BASE}"',
        "if not exist logs mkdir logs",
        f'"{sys.executable}" main.py >> logs\\daily.log 2>&1',
    ]
    with open(bat_path, "w", encoding="gbk") as f:
        f.write("\r\n".join(lines) + "\r\n")
    return bat_path


def install(hhmm):
    bat_path = _write_runner()
    rc = subprocess.call(["schtasks", "/Create", "/F", "/TN", TASK_NAME,
                          "/TR", bat_path, "/SC", "DAILY", "/ST", hhmm])
    if rc == 0:
        print(f"✅ 已创建定时任务「{TASK_NAME}」，每天 {hhmm} 自动运行。")
        print("   可到「任务计划程序」中查看或调整。")
    else:
        print("❌ 创建失败。请尝试：右键「以管理员身份运行」命令提示符后重试；")
        print(f'   或手动执行：schtasks /Create /F /TN "{TASK_NAME}" '
              f'/TR "{bat_path}" /SC DAILY /ST {hhmm}')


def remove():
    rc = subprocess.call(["schtasks", "/Delete", "/F", "/TN", TASK_NAME])
    print("✅ 已删除定时任务。" if rc == 0 else "ℹ  未找到该定时任务（可能本就不存在）。")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--time", default="20:00", help="运行时间 HH:MM，默认 20:00")
    p.add_argument("--remove", action="store_true", help="删除定时任务")
    args = p.parse_args()
    if args.remove:
        remove()
    else:
        install(args.time)


if __name__ == "__main__":
    main()
