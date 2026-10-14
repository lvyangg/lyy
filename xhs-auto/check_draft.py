# -*- coding: utf-8 -*-
"""检查当前草稿状态：上传了几张图、标题正文填了什么。"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp import Browser  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
browser = Browser(port=9222)
page = browser.attach("creator.xiaohongshu.com")
if not page:
    raise SystemExit("没找到小红书创作服务平台标签页")
page.call("Page.bringToFront")


def js(expr):
    return page.js(expr)


print("标题:", js('(document.querySelector(\'input[placeholder*="标题"]\')||{}).value'))
print("正文长度:", js('(document.querySelector(\'div[contenteditable="true"]\')||{innerText:""}).innerText.length'))
print("正文开头:", (js('(document.querySelector(\'div[contenteditable="true"]\')||{innerText:""}).innerText') or "")[:40].replace("\n", " "))
print("blob 图片数:", js('[...document.querySelectorAll("img")].filter(i=>i.src.startsWith("blob:")).length'))
print("xhscdn 图片数:", js('[...document.querySelectorAll("img")].filter(i=>i.src.includes("xhscdn")).length'))
print("带删除按钮的图片:", js('document.querySelectorAll("[class*=delete], [class*=del-]").length'))
print("页面是否还有「上传中」:", js('document.body.innerText.includes("上传中")'))
shot = page.screenshot(os.path.join(HERE, "logs", "draft.png"))
print("截图:", shot)
