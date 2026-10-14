# -*- coding: utf-8 -*-
"""在创作服务平台里找官方推的方向：笔记灵感、活动中心、创作学院。"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp import Browser  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))

LINKS_JS = """(() => {
  const out = [];
  document.querySelectorAll('a[href]').forEach(a => {
    const href = a.getAttribute('href') || '';
    if (href.indexOf('creator.xiaohongshu.com') < 0) return;
    const t = (a.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 16);
    if (t) out.push(t + '  ->  ' + href);
  });
  return [...new Set(out)].join('\\n');
})()"""

TEXT_JS = """(() => {
  const main = document.querySelector('main') || document.body;
  const t = (main.innerText || '').replace(/\\n{2,}/g, '\\n');
  return t.slice(0, 1200);
})()"""

browser = Browser(port=9222)
page = browser.attach("creator.xiaohongshu.com") or browser.new_page()
page.call("Page.bringToFront")
page.navigate("https://creator.xiaohongshu.com/publish/publish?source=official", wait=6)

print("=== 侧边栏链接 ===")
print(page.js(LINKS_JS))

for name, url in (("笔记灵感", "https://creator.xiaohongshu.com/inspiration"),
                  ("活动中心", "https://creator.xiaohongshu.com/activity"),
                  ("创作学院", "https://creator.xiaohongshu.com/creator/school")):
    print(f"\n=== {name}：{url} ===")
    page.navigate(url, wait=6)
    time.sleep(2)
    print("页面标题:", page.js("document.title"))
    print(page.js(TEXT_JS))
