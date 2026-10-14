# -*- coding: utf-8 -*-
"""确保自动化 Edge 在运行（带调试端口），并打开指定页面。

用法：
    python open_edge.py                        # 打开笔记管理
    python open_edge.py --url https://creator.xiaohongshu.com/publish/publish?source=official
"""
import argparse
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp import Browser, CDPError  # noqa: E402
import edge_path  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
PROFILE = os.path.join(HERE, "edge-profile")
EDGE = edge_path.edge_exe()
PORT = 9222


def ensure_edge():
    try:
        Browser(port=PORT, timeout=8)
        print("Edge 调试端口已就绪")
        return True
    except CDPError:
        pass
    print("启动 Edge（自动化配置目录）…")
    subprocess.Popen([EDGE, f"--remote-debugging-port={PORT}", f"--user-data-dir={PROFILE}",
                      "--no-first-run", "--no-default-browser-check", "--start-maximized", "about:blank"])
    for _ in range(30):
        time.sleep(1)
        try:
            Browser(port=PORT, timeout=5)
            print("Edge 已启动")
            return True
        except CDPError:
            continue
    return False


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="https://creator.xiaohongshu.com/new/note-manager")
    args = ap.parse_args()
    if not ensure_edge():
        raise SystemExit("Edge 启动失败")
    browser = Browser(port=PORT)
    page = browser.attach("creator.xiaohongshu.com") or browser.new_page(args.url)
    page.call("Page.bringToFront")
    page.navigate(args.url, wait=6)
    print("已打开:", page.js("location.href"))
