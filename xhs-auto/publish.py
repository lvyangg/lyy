# -*- coding: utf-8 -*-
"""把 pages/ 里的图片上传到小红书创作服务平台，并填写标题与正文。

用法：
    python publish.py            # 只上传并填写，最后一个「发布」按钮留给你点
    python publish.py --publish  # 上传、填写、并自动点发布

前提：先双击 start_edge.bat（用独立配置启动 Edge），首次需要你扫码登录一次；
之后这个配置目录里会记住登录状态，不用每次扫码。
"""
import argparse
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp import Browser, CDPError  # noqa: E402
import edge_path  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
PROFILE = os.path.join(HERE, "edge-profile")
LOGS = os.path.join(HERE, "logs")
PORT = 9222
EDGE = edge_path.edge_exe()
PUBLISH_URL = "https://creator.xiaohongshu.com/publish/publish?source=official"

TITLE_SELECTORS = ['input[placeholder*="标题"]', 'input[placeholder*="填写标题"]', "#post-title"]
BODY_SELECTORS = ['div[contenteditable="true"]', ".ql-editor", "#post-textarea", "textarea"]


def log(*a):
    print(*a, flush=True)


def ensure_edge():
    """确保以调试端口启动了一个 Edge（独立配置目录，不影响你平时的 Edge）。"""
    try:
        Browser(port=PORT, timeout=10)
        log("[1/7] Edge 调试端口已就绪")
        return
    except CDPError:
        pass
    os.makedirs(PROFILE, exist_ok=True)
    log("[1/7] 启动 Edge（自动化配置目录）…")
    subprocess.Popen([
        EDGE, f"--remote-debugging-port={PORT}", f"--user-data-dir={PROFILE}",
        "--no-first-run", "--no-default-browser-check", "--start-maximized",
        "about:blank",
    ])
    for _ in range(30):
        time.sleep(1)
        try:
            Browser(port=PORT, timeout=5)
            log("[1/7] Edge 已启动")
            return
        except CDPError:
            continue
    raise SystemExit("Edge 调试端口没有起来，请手动双击 start_edge.bat 看一眼")


def pick(page, selectors, label, timeout=30):
    """在候选选择器里找到第一个存在的元素，返回它的选择器和下标。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        for sel in selectors:
            n = page.js(f"document.querySelectorAll({json.dumps(sel)}).length")
            if n:
                log(f"    · {label} 命中 {sel}（{n} 个）")
                return sel, 0
        time.sleep(1.5)
    return None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--publish", action="store_true", help="填完之后自动点发布")
    args = ap.parse_args()

    os.makedirs(LOGS, exist_ok=True)
    pages = sorted(p for p in os.listdir(os.path.join(HERE, "pages")) if p.endswith(".png"))
    images = [os.path.join(HERE, "pages", p) for p in pages]
    if len(images) < 2:
        raise SystemExit("pages/ 里的图片不足，请先运行 python render_pages.py")
    meta = json.load(open(os.path.join(HERE, "content.json"), encoding="utf-8"))["note"]
    log(f"[0/7] 准备上传 {len(images)} 张图，标题：{meta['title']}")

    ensure_edge()
    browser = Browser(port=PORT)
    page = browser.attach("creator.xiaohongshu.com")
    if page:
        log("[2/7] 复用已打开的创作服务平台标签页")
        page.call("Page.bringToFront")
    else:
        page = browser.new_page(PUBLISH_URL)
        log("[2/7] 已打开创作服务平台发布页")
    time.sleep(3)

    url = page.js("location.href")
    body = page.js("document.body.innerText.slice(0, 400)") or ""
    if "login" in url or "扫码" in body or "登录" in body and "发布" not in body:
        page.screenshot(os.path.join(LOGS, "need-login.png"))
        log("=" * 60)
        log("需要先登录：请在刚打开的 Edge 窗口里扫码登录小红书。")
        log("登录完成后，重新运行：python publish.py")
        log("=" * 60)
        raise SystemExit(2)
    log("[3/7] 登录状态正常")

    if page.js("document.body.innerText.includes('上传图文')"):
        page.click_text("上传图文")
        time.sleep(2.5)
        log("[4/7] 已切换到「上传图文」")
    else:
        log("[4/7] 当前已在图文上传页")

    page.set_files("input[type=file]", images)
    log(f"[5/7] 已投递 {len(images)} 张图片，等待上传完成…")
    deadline = time.time() + 240
    while time.time() < deadline:
        uploading = page.js("document.body.innerText.includes('上传中') || document.body.innerText.includes('处理中')")
        n_img = page.js("document.querySelectorAll('img').length")
        if not uploading and n_img >= len(images):
            log(f"    上传完成（页面图片数 {n_img}）")
            break
        time.sleep(3)
    else:
        log("    ⚠️ 等待上传超时，仍继续尝试填写文字")

    tsel, tidx = pick(page, TITLE_SELECTORS, "标题输入框")
    if not tsel:
        page.screenshot(os.path.join(LOGS, "no-title-input.png"))
        raise SystemExit("找不到标题输入框，已截图 logs/no-title-input.png")
    page.insert_text(tsel, meta["title"][:20], index=tidx)

    bsel, bidx = pick(page, BODY_SELECTORS, "正文编辑器")
    if not bsel:
        page.screenshot(os.path.join(LOGS, "no-body-input.png"))
        raise SystemExit("找不到正文输入框，已截图 logs/no-body-input.png")
    page.insert_text(bsel, meta["body"], index=bidx)
    time.sleep(1.5)

    filled_title = page.js(f"document.querySelector({json.dumps(tsel)}).value || ''")
    filled_body = page.js(f"document.querySelector({json.dumps(bsel)}).innerText || ''")
    log(f"[6/7] 已填写：标题 {len(filled_title)} 字 / 正文 {len(filled_body)} 字")
    page.screenshot(os.path.join(LOGS, "filled.png"))

    if args.publish:
        ok = page.click_text("发布")
        log(f"[7/7] 点击发布：{'成功' if ok else '没找到发布按钮'}")
    else:
        log("[7/7] 已停在第 7 步：请在弹出的 Edge 窗口里检查内容，然后自己点「发布」")
        log("      想让它自动点发布，下次加参数：python publish.py --publish")


if __name__ == "__main__":
    main()
