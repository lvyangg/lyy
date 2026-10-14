# -*- coding: utf-8 -*-
"""抓取创作服务平台「笔记灵感」里某个分类的话题和示例笔记（标题 + 点赞）。"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp import Browser  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))

EXTRACT_JS = """(() => {
  const clean = s => (s || '').replace(/\\s+/g, ' ').trim();
  const text = clean(document.body.innerText);
  // 话题块：……万人参与 · ……亿次浏览
  const blocks = [];
  const nodes = [...document.querySelectorAll('div, section, li')];
  nodes.forEach(n => {
    const t = clean(n.innerText);
    const m = t.match(/^(.*?)\\n?([\\d.]+万?人参与 · [\\d.]+亿?万?次浏览)/);
    if (m && t.length < 600 && n.children.length < 12) {
      blocks.push(t);
    }
  });
  const uniq = [...new Set(blocks)];
  return JSON.stringify({raw: text.slice(0, 3000), blocks: uniq.slice(0, 12)});
})()"""

ap = argparse.ArgumentParser()
ap.add_argument("--tab", default="知识")
args = ap.parse_args()

browser = Browser(port=9222)
page = browser.attach("creator.xiaohongshu.com") or browser.new_page()
page.call("Page.bringToFront")
page.navigate("https://creator.xiaohongshu.com/new/inspiration?source=official", wait=7)

print(f"点开分类：{args.tab}")
try:
    page.click_sel_by_text(args.tab)
except Exception as exc:
    print("点击失败:", exc)
time.sleep(6)

data = json.loads(page.js(EXTRACT_JS) or "{}")
out = os.path.join(HERE, "research")
os.makedirs(out, exist_ok=True)
path = os.path.join(out, f"inspiration-{args.tab}.json")
json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

print("\n=== 话题块 ===")
for b in data.get("blocks", []):
    print("—", b.replace("\n", " / ")[:300])
print(f"\n（原始文本已存 {path}）")
