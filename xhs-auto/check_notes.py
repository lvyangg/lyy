# -*- coding: utf-8 -*-
"""打开笔记管理页，确认最近发布的笔记状态。"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp import Browser  # noqa: E402

browser = Browser(port=9222)
page = browser.attach("creator.xiaohongshu.com") or browser.new_page()
page.call("Page.bringToFront")
page.navigate("https://creator.xiaohongshu.com/new/note-manager", wait=6)
time.sleep(2)
print("页面标题:", page.js("document.title"))
text = page.js("""(() => {
    const t = document.body.innerText || '';
    return t.replace(/\\n{2,}/g, '\\n').slice(0, 900);
})()""")
print(text)
