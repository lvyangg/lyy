# -*- coding: utf-8 -*-
"""发布前的三项设置：原创声明、加入合集、内容类型声明（笔记含 AI 生成内容）。

用法：python prepare_options.py            # 设置并校验，不发布
     python prepare_options.py --dry      # 只看当前状态
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp import Browser  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


def show(page, label, js, *args):
    print(f"   {label}: {page.js(js)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    browser = Browser(port=9222)
    page = browser.attach("creator.xiaohongshu.com")
    if not page:
        raise SystemExit("没找到小红书发布页")
    page.call("Page.bringToFront")

    state = lambda: json.dumps(page.js("""(() => {
        const orig = document.querySelector('.original-wrapper');
        const coll = document.querySelector('.collection-plugin-choose');
        const decl = document.querySelector('.d-select-wrapper');
        const card = orig && orig.querySelector('.custom-switch-card');
        return {
          orig_html: orig ? orig.outerHTML.slice(0, 200) : null,
          orig_card_cls: card ? (card.className || '').toString() : null,
          coll: coll ? (coll.innerText || '').trim() : null,
          decl: decl ? (decl.innerText || '').trim().slice(0, 30) : null,
        };
    })()"""), ensure_ascii=False)
    print("初始状态:", state())
    if args.dry:
        return

    # ---- 1. 原创声明 ----
    print("\n[1] 原创声明")
    before = page.js("document.querySelector('.original-wrapper').outerHTML")
    box = page.click_sel(".original-wrapper .custom-switch-wrapper")
    print(f"   已真实点击开关（位置 {box['w']:.0f}x{box['h']:.0f}）")
    time.sleep(1.5)
    after = page.js("document.querySelector('.original-wrapper').outerHTML")
    print(f"   DOM 是否变化: {before != after}")
    print("   该行文字:", page.js("document.querySelector('.original-wrapper').innerText.replace(/\\n/g,' | ')"))
    print("   气泡/提示:", page.js("""(() => {
        const tips = [...document.querySelectorAll('.d-popover, [class*=tooltip], [class*=tip]')]
          .filter(el => el.offsetParent !== null && (el.innerText||'').trim());
        return tips.map(el => (el.innerText||'').trim().slice(0,40)).slice(0,3).join(' / ');
    })()"""))

    # ---- 2. 加入合集 ----
    print("\n[2] 加入合集（期望：工具推荐）")
    coll = page.js("(document.querySelector('.collection-plugin-choose')||{}).innerText")
    print(f"   当前合集: {coll!r}")
    if coll and "工具推荐" not in coll:
        print("   需要改合集：点开选择器")
        page.js("""(() => {
            const el = document.querySelector('.collection-plugin-wrapper');
            el.scrollIntoView({block: 'center'}); el.click(); return true;
        })()""")
        time.sleep(2)
        print("   弹层里的候选:", page.js("""(() => {
            return [...document.querySelectorAll('.d-popover, .d-modal, .collection-plugin-wrapper *')]
              .filter(el => el.offsetParent !== null && /工具推荐/.test(el.innerText || ''))
              .map(el => el.tagName + '.' + (el.className||'').toString().slice(0,40)).slice(0,6).join(' | ');
        })()"""))

    # ---- 3. 内容类型声明 ----
    print("\n[3] 内容类型声明（期望：笔记含 AI 生成内容）")
    print(f"   当前: {page.js('(document.querySelector(\".d-select-wrapper\")||{}).innerText')!r}")
    page.click_sel(".d-select-wrapper")
    time.sleep(1.8)
    options = page.js("""(() => {
        return [...document.querySelectorAll('*')]
          .filter(el => el.offsetParent !== null && el.children.length <= 2 && (el.innerText||'').trim())
          .map(el => (el.innerText||'').trim())
          .filter(t => t.length <= 20 && /声明|AI|虚构|演绎|取材|原创|观点|转载|个人/.test(t))
          .filter((v, i, a) => a.indexOf(v) === i).slice(0, 25);
    })()""")
    print("   下拉候选:", options)
    picked = False
    for label in (options or []):
        if "AI" in label.upper():
            n = page.js(f"""(() => {{
                const nodes = [...document.querySelectorAll('*')].filter(el =>
                    el.offsetParent !== null && el.children.length <= 2 &&
                    (el.innerText||'').trim() === {json.dumps(label)});
                if (!nodes.length) return 0;
                const el = nodes[nodes.length - 1];
                el.scrollIntoView({{block: 'center'}});
                return el.getBoundingClientRect().x + el.getBoundingClientRect().width / 2;
            }})()""")
            y = page.js(f"""(() => {{
                const nodes = [...document.querySelectorAll('*')].filter(el =>
                    el.offsetParent !== null && el.children.length <= 2 &&
                    (el.innerText||'').trim() === {json.dumps(label)});
                const el = nodes[nodes.length - 1];
                return el.getBoundingClientRect().y + el.getBoundingClientRect().height / 2;
            }})()""")
            if n:
                page.click_xy(n, y)
                picked = True
                print(f"   已点击选项: {label}")
                break
    time.sleep(1.2)
    print(f"   是否完成选择: {picked}")

    print("\n设置后状态:", state())
    page.screenshot(os.path.join(HERE, "logs", "options-set.png"))
    print("截图: logs/options-set.png")


if __name__ == "__main__":
    main()
