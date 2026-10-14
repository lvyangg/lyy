# -*- coding: utf-8 -*-
"""查看自动化 Edge 的当前状态：登录了吗、发布页有没有就绪。

用法：
    python status.py            # 查看状态
    python status.py --clean    # 顺手关掉同步提示、空白等无关标签页
"""
import argparse
import json
import os
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp import Browser  # noqa: E402


def list_pages():
    return [t for t in json.load(urllib.request.urlopen("http://127.0.0.1:9222/json/list", timeout=5))
            if t.get("type") == "page"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clean", action="store_true")
    args = ap.parse_args()
    browser = Browser(port=9222)
    pages = list_pages()
    print("标签页:")
    for t in pages:
        print("  ", t.get("title"), "|", t.get("url")[:70])

    if args.clean:
        for _ in range(2):
            for t in list_pages():
                if "sync-confirmation" in t.get("url", "") or t.get("url", "") == "about:blank":
                    browser.call("Target.closeTarget", {"targetId": t["id"]})
            time.sleep(1)
        pages = list_pages()
        print("清理后剩余:", [t.get("title") for t in pages])

    target = next((t for t in pages if "xiaohongshu" in t.get("url", "")), None)
    if not target:
        print("没有小红书页面；先运行 start_edge.bat 或 python publish.py")
        return
    sid = browser.call("Target.attachToTarget", {"targetId": target["id"], "flatten": True})["sessionId"]
    browser.call("Page.bringToFront", session=sid)

    def js(expr):
        r = browser.call("Runtime.evaluate", {"expression": expr, "returnByValue": True}, session=sid)
        return r.get("result", {}).get("value")

    title = js("document.title")
    text = js("document.body.innerText") or ""
    print()
    print("页面标题:", title)
    print("URL:", js("location.href")[:90])
    print("出现「扫码」:", "扫码" in text, "| canvas 数量:", js('document.querySelectorAll("canvas").length'))
    print("出现「标题」输入框:", [s for s in ['input[placeholder*="标题"]', 'div[contenteditable="true"]']
                                  if js(f'document.querySelectorAll({json.dumps(s)}).length')])
    print("页面文字片段:", text[:150].replace("\n", " / "))


if __name__ == "__main__":
    main()
