# -*- coding: utf-8 -*-
"""读取并打开「原创声明」开关（用计算样式判断状态）。"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp import Browser  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))

STATE_JS = """(() => {
  const wrap = document.querySelector('.original-wrapper');
  const card = wrap && wrap.querySelector('.custom-switch-card');
  const icon = wrap && wrap.querySelector('.custom-switch-icon');
  const txt  = wrap && wrap.querySelector('.custom-switch-text-content');
  const cs = el => el ? getComputedStyle(el) : null;
  const c = cs(card), i = cs(icon);
  return JSON.stringify({
    card_bg: c ? c.backgroundColor : null,
    card_border: c ? c.borderColor : null,
    icon_bg: i ? i.backgroundColor : null,
    icon_color: i ? i.color : null,
    text: txt ? (txt.innerText || '').trim().slice(0, 30) : null,
    icon_html: icon ? icon.innerHTML.slice(0, 160) : null,
    html_len: wrap ? wrap.innerHTML.length : 0,
  });
})()"""

BOX_JS = """(() => {{
  const el = document.querySelector({sel});
  if (!el) return null;
  el.scrollIntoView({{block: 'center'}});
  const r = el.getBoundingClientRect();
  return JSON.stringify({{x: r.x + r.width / 2, y: r.y + r.height / 2, w: r.width, h: r.height}});
}})()"""

browser = Browser(port=9222)
page = browser.attach("creator.xiaohongshu.com")
page.call("Page.bringToFront")


def state():
    return json.loads(page.js(STATE_JS))


def box(sel):
    raw = page.js(BOX_JS.format(sel=json.dumps(sel)))
    return json.loads(raw) if raw else None


before = state()
print("初始状态:", json.dumps(before, ensure_ascii=False))
print("\n提示：card_bg 从透明变绿/变色，说明开关被打开了\n")

for sel in (".original-wrapper .custom-switch-icon",
            ".original-wrapper .custom-switch-card",
            ".original-wrapper"):
    b = box(sel)
    if not b:
        print(f"跳过（找不到）: {sel}")
        continue
    page.click_xy(b["x"], b["y"])
    time.sleep(1.5)
    now = state()
    changed = (now["card_bg"] != before["card_bg"] or now["icon_bg"] != before["icon_bg"]
               or now["icon_html"] != before["icon_html"] or now["html_len"] != before["html_len"])
    print(f"点击 {sel}")
    print(f"   变化: {changed}")
    print(f"   card_bg={now['card_bg']} icon_bg={now['icon_bg']} html_len={now['html_len']}")
    if changed:
        print("   ✅ 开关状态已改变")
        break

page.screenshot(os.path.join(HERE, "logs", "original-switch.png"))
print("\n截图: logs/original-switch.png")
