# -*- coding: utf-8 -*-
"""抓取小红书搜索结果里的高赞笔记（标题 + 点赞 + 封面图），用于分析爆款特征。

用法：
    python research_trending.py "AI工具"
    python research_trending.py "AI写作" --scroll 4
"""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp import Browser, CDPError  # noqa: E402
import edge_path  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
COVERS = os.path.join(HERE, "research", "covers")
os.makedirs(COVERS, exist_ok=True)

# 抓取：标题、点赞、封面图、笔记链接
EXTRACT_JS = """(() => {
  const clean = s => (s || '').replace(/\\s+/g, ' ').trim();
  const cards = [...document.querySelectorAll('section.note-item, div.note-item')];
  const rows = cards.map(c => {
    const titleEl = c.querySelector('a.title span, .footer .title span, a.title');
    const likeEl = c.querySelector('.like-wrapper .count, .count');
    const img = c.querySelector('img');
    const link = c.querySelector('a.cover, a[href*="/explore/"]');
    return {
      title: clean(titleEl && titleEl.innerText),
      like: clean(likeEl && likeEl.innerText),
      cover: img ? img.src : null,
      url: link ? link.getAttribute('href') : null,
    };
  }).filter(r => r.title);
  return JSON.stringify(rows);
})()"""


def ensure_edge():
    try:
        Browser(port=9222, timeout=8)
        return
    except CDPError:
        pass
    subprocess.Popen([edge_path.edge_exe(),
                      "--remote-debugging-port=9222",
                      f"--user-data-dir={os.path.join(HERE, 'edge-profile')}",
                      "--no-first-run", "--no-default-browser-check", "--start-maximized", "about:blank"])
    for _ in range(30):
        time.sleep(1)
        try:
            Browser(port=9222, timeout=5)
            return
        except CDPError:
            continue
    raise SystemExit("Edge 起不来")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("keyword")
    ap.add_argument("--scroll", type=int, default=3)
    args = ap.parse_args()

    ensure_edge()
    browser = Browser(port=9222)
    page = browser.attach("xiaohongshu.com") or browser.new_page()
    url = f"https://www.xiaohongshu.com/search_result?keyword={urllib.parse.quote(args.keyword)}&source=web_explore_feed"
    page.call("Page.bringToFront")
    page.navigate(url, wait=6)
    for _ in range(args.scroll):
        page.js("window.scrollBy(0, 1400)")
        time.sleep(2.5)

    raw = page.js(EXTRACT_JS) or "[]"
    rows = json.loads(raw)
    print(f"关键词「{args.keyword}」抓到 {len(rows)} 条")
    if not rows:
        print("页面标题:", page.js("document.title"))
        print("文字片段:", (page.js("document.body.innerText") or "")[:200].replace("\n", " / "))
        return

    def like_num(s):
        s = (s or "").strip().replace("+", "")
        try:
            return float(s)
        except Exception:
            if s.endswith("万"):
                try:
                    return float(s[:-1]) * 10000
                except Exception:
                    return 0
            return 0

    rows.sort(key=lambda r: like_num(r["like"]), reverse=True)
    out = os.path.join(HERE, "research")
    os.makedirs(out, exist_ok=True)
    safe = "".join(ch for ch in args.keyword if ch.isalnum() or ch in "AIai")
    path = os.path.join(out, f"notes-{safe}.json")
    json.dump(rows, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    for i, r in enumerate(rows[:15], 1):
        print(f"  {i:2d}. 赞 {r['like']:>6s}  {r['title'][:42]}")
    print("已保存:", path)

    # 下载前 6 张封面，便于分析
    for i, r in enumerate(rows[:6], 1):
        if not r["cover"]:
            continue
        try:
            req = urllib.request.Request(r["cover"], headers={"User-Agent": "Mozilla/5.0"})
            data = urllib.request.urlopen(req, timeout=15).read()
            p = os.path.join(COVERS, f"{safe}-{i:02d}.jpg")
            open(p, "wb").write(data)
            print("  封面已存:", os.path.basename(p), f"{len(data)/1024:.0f}KB")
        except Exception as exc:
            print("  封面下载失败:", exc)


if __name__ == "__main__":
    main()
