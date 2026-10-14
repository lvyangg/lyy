# -*- coding: utf-8 -*-
"""一键跑完整条流水线：出图 → 上传 → 填写 → 设置声明 → 发布 → 记流水。

用法：
    python auto_post.py                # 完整发布
    python auto_post.py --no-publish   # 只到「填好并设置完」，不点发布
"""
import argparse
import json
import os
import subprocess
import sys
import time

import cv2
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp import Browser, CDPError  # noqa: E402
import edge_path  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
LOGS = os.path.join(HERE, "logs")
PAGES = os.path.join(HERE, "pages")
PROFILE = os.path.join(HERE, "edge-profile")
EDGE = edge_path.edge_exe()
PORT = 9222
PUBLISH_URL = "https://creator.xiaohongshu.com/publish/publish?source=official"
HISTORY = os.path.join(HERE, "history.json")
os.makedirs(LOGS, exist_ok=True)


def log(*a):
    print(*a, flush=True)


def ensure_edge():
    try:
        Browser(port=PORT, timeout=8)
        return
    except CDPError:
        pass
    os.makedirs(PROFILE, exist_ok=True)
    subprocess.Popen([EDGE, f"--remote-debugging-port={PORT}", f"--user-data-dir={PROFILE}",
                      "--no-first-run", "--no-default-browser-check", "--start-maximized", "about:blank"])
    for _ in range(30):
        time.sleep(1)
        try:
            Browser(port=PORT, timeout=5)
            return
        except CDPError:
            continue
    raise SystemExit("Edge 调试端口没起来")


def active_tab(page):
    """当前激活的发布标签（上传视频 / 上传图文 / 写长文 / 发播客）。"""
    return page.js("""(() => {
        const t = [...document.querySelectorAll('.creator-tab')]
          .find(el => (el.className || '').toString().includes('active'));
        return t ? (t.innerText || '').trim() : '';
    })()""") or ""


def switch_to_image_tab(page, tries=3):
    """切到「上传图文」并确认真的切过去了（切错会把图投给视频上传口，图会被丢掉）。"""
    for i in range(tries):
        cur = active_tab(page)
        if "图文" in cur:
            log(f"   标签已确认：{cur}")
            return True
        try:
            page.click_sel_by_text("上传图文")
        except CDPError:
            box = page.js("""(() => {
                const el = [...document.querySelectorAll('.creator-tab')]
                  .find(x => (x.innerText || '').includes('上传图文'));
                if (!el) return null;
                const r = el.getBoundingClientRect();
                return JSON.stringify({x: r.x + r.width / 2, y: r.y + r.height / 2});
            })()""")
            if box:
                c = json.loads(box)
                page.click_xy(c["x"], c["y"])
        time.sleep(3)
        log(f"   第 {i + 1} 次切换后标签：{active_tab(page) or '未知'}")
    return "图文" in active_tab(page)


def count_note_images(page):
    """只数上传区里的图，避免把头像等界面图标算进来。"""
    return page.js("""(() => {
        const area = document.querySelector('.img-upload-area') || document.querySelector('.img-list');
        const root = area || document.body;
        return [...root.querySelectorAll('img')]
          .filter(i => i.src.includes('xhscdn') || i.src.startsWith('blob:')).length;
    })()""") or 0


def click_red_button(page, label="发布"):
    """按钮在封闭 shadow DOM 里，用截图找红色按钮再点。"""
    dpr = page.js("window.devicePixelRatio") or 1
    shot = page.screenshot(os.path.join(LOGS, "auto-buttons.png"))
    a = np.asarray(Image.open(shot).convert("RGB")).astype(int)
    r, g, b = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    red = ((r > 165) & (r - g > 55) & (r - b > 35)).astype(np.uint8)
    _, _, stats, _ = cv2.connectedComponentsWithStats(red, 8)
    cands = []
    for i in range(1, stats.shape[0]):
        x, y, w, h, area = stats[i]
        cw, ch = w / dpr, h / dpr
        cy = (y + h / 2) / dpr
        if area < 1200 or not (70 <= cw <= 260) or not (24 <= ch <= 70) or cy < 800:
            continue
        cands.append(((x + w / 2) / dpr, cy, cw, ch))
    if not cands:
        raise SystemExit("没找到红色主按钮，已截图 logs/auto-buttons.png")
    x, y, cw, ch = sorted(cands)[-1]
    log(f"   点击{label}按钮（{cw:.0f}x{ch:.0f} @ {x:.0f},{y:.0f}）")
    page.click_xy(x, y)
    time.sleep(9)
    return page.js("location.href"), (page.js("document.body.innerText") or "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-publish", action="store_true")
    args = ap.parse_args()

    meta = json.load(open(os.path.join(HERE, "content.json"), encoding="utf-8"))["note"]
    images = [os.path.join(PAGES, f) for f in sorted(os.listdir(PAGES)) if f.endswith(".png")]
    log(f"[1/8] 生成图片（按 content.json 的 style 选渲染器）")
    subprocess.run([sys.executable, os.path.join(HERE, "render_by_style.py")], check=True)
    images = [os.path.join(PAGES, f) for f in sorted(os.listdir(PAGES)) if f.endswith(".png")]

    ensure_edge()
    browser = Browser(port=PORT)
    page = browser.attach("creator.xiaohongshu.com") or browser.new_page(PUBLISH_URL)
    log("[2/8] 打开发布页")
    page.call("Page.bringToFront")
    page.js("location.href.includes('/publish/publish') || (location.href = %s)" %
            json.dumps(PUBLISH_URL))
    time.sleep(4)

    if page.js("location.href.includes('/login')"):
        raise SystemExit("需要登录：请在自动化 Edge 窗口里登录小红书后重试")

    if not switch_to_image_tab(page):
        page.screenshot(os.path.join(LOGS, "tab-failed.png"))
        raise SystemExit("没能切到「上传图文」标签，已停止（避免把图投给视频上传口）")
    log("[3/8] 已确认在「上传图文」标签")

    uploaded = False
    for attempt in (1, 2):
        page.set_files("input[type=file]", images)
        log(f"[4/8] 第 {attempt} 次投递 {len(images)} 张图，等待上传…")
        deadline = time.time() + 240
        while time.time() < deadline:
            busy = page.js("document.body.innerText.includes('上传中') || document.body.innerText.includes('处理中')")
            n = count_note_images(page)
            if not busy and n >= len(images):
                log(f"   上传完成（识别到 {n} 张）")
                uploaded = True
                break
            time.sleep(3)
        if uploaded:
            break
        log("   这一轮没传上，重新切标签后再试一次")
        switch_to_image_tab(page)
    if not uploaded:
        page.screenshot(os.path.join(LOGS, "upload-failed.png"))
        raise SystemExit("图片上传失败，已停止（截图 logs/upload-failed.png）")

    title_input = page.js("""(() => {
        const el = document.querySelector('input[placeholder*="标题"]');
        if (!el) return null;
        el.scrollIntoView({block:'center'}); const r = el.getBoundingClientRect();
        return JSON.stringify({x: r.x + r.width/2, y: r.y + r.height/2});
    })()""")
    if title_input:
        c = json.loads(title_input)
        page.click_xy(c["x"], c["y"])
        page.call("Input.insertText", {"text": meta["title"][:20]})
        log(f"[5/8] 已填标题：{meta['title'][:20]}")
    else:
        raise SystemExit("找不到标题输入框")

    editor = page.js("""(() => {
        const el = document.querySelector('div[contenteditable="true"]');
        if (!el) return null;
        el.scrollIntoView({block:'center'}); const r = el.getBoundingClientRect();
        return JSON.stringify({x: r.x + r.width/2, y: r.y + r.height/2});
    })()""")
    if editor:
        c = json.loads(editor)
        page.click_xy(c["x"], c["y"])
        page.call("Input.insertText", {"text": meta["body"]})
        log(f"[6/8] 已填正文（{len(meta['body'])} 字）")
    else:
        raise SystemExit("找不到正文编辑器")

    # 原创声明
    sim = page.js("(document.querySelector('.original-wrapper .d-switch-simulator')||{}).className || ''")
    if "unchecked" in (sim or ""):
        page.click_sel(".original-wrapper .d-switch-simulator")
        time.sleep(1.2)
        sim = page.js("(document.querySelector('.original-wrapper .d-switch-simulator')||{}).className || ''")
    log(f"[7/8] 原创声明：{'已开启' if 'unchecked' not in (sim or '') else '未开启 ✗'}")

    # 内容类型声明
    decl = page.js("(document.querySelector('.d-select-wrapper')||{}).innerText || ''")
    if "AI" not in decl.upper():
        page.click_sel(".d-select-wrapper")
        time.sleep(1.6)
        page.click_sel_by_text("笔记含AI合成内容")
        time.sleep(1.2)
    decl = page.js("(document.querySelector('.d-select-wrapper')||{}).innerText || ''")
    coll = page.js("(document.querySelector('.collection-plugin-choose')||{}).innerText || ''")
    log(f"   内容声明：{decl.strip()!r} | 合集：{coll.strip()!r}")

    info = {"title": meta["title"], "body_len": len(meta["body"]),
            "declaration": decl.strip(), "collection": coll.strip(),
            "original": "on" if "unchecked" not in (sim or "") else "off",
            "images": len(images)}
    if args.no_publish:
        log("[8/8] 已按要求停在上一步（--no-publish），没有点发布")
        return

    url, text = click_red_button(page)
    ok = "发布成功" in text or "/publish/success" in url
    log(f"[8/8] 发布结果：{'成功 ✅' if ok else '未确认 ⚠️'}\n   URL: {url}")
    info.update({"published_at": time.strftime("%Y-%m-%d %H:%M:%S"), "url": url, "ok": ok})
    hist = json.load(open(HISTORY, encoding="utf-8")) if os.path.exists(HISTORY) else []
    hist.append(info)
    json.dump(hist, open(HISTORY, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    log(f"   已记入 history.json（共 {len(hist)} 条）")


if __name__ == "__main__":
    main()
