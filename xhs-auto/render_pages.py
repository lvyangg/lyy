# -*- coding: utf-8 -*-
"""生成小红书图文（8 页，1080x1440，3:4）。

视觉母版（每页硬约束）：
  画布 1080x1440 · 安全边距 左右 72 / 上下 80 · 圆角 28 · 页码固定在右下
  色彩令牌：背景 #0E1113→#141A1C，卡片 #171C1F，主文字 #F2F5F4，辅助 #93A09C，
           强调 A 薄荷 #6EE7A8，强调 B 亮橙 #FF8A3D
  字体令牌：思源黑体（Noto Sans SC）可变字重，标题 Black/Bold，正文 Medium/Regular
"""
import json
import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1440
MX, MY = 72, 80
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pages")
os.makedirs(OUT, exist_ok=True)

BG1, BG2 = (14, 17, 19), (20, 26, 28)
CARD = (23, 28, 31)
BORDER = (38, 45, 48)
TEXT = (242, 245, 244)
MUTED = (147, 160, 156)
MINT = (110, 231, 168)
ORANGE = (255, 138, 61)

FONT_PATH = r"C:\Windows\Fonts\NotoSansSC-VF.ttf"
_cache = {}


def font(size, weight="Regular"):
    key = (size, weight)
    if key not in _cache:
        f = ImageFont.truetype(FONT_PATH, size)
        try:
            f.set_variation_by_name(weight)
        except Exception:
            pass
        _cache[key] = f
    return _cache[key]


def tw(d, s, f):
    return d.textlength(s, font=f)


def bg():
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    t = np.clip(y / H, 0, 1)[..., None]
    base = (1 - t) * np.array(BG1, np.float32) + t * np.array(BG2, np.float32)
    # 右上角薄荷辉光（很淡，避免廉价霓虹感）
    d = np.sqrt(((x - W * 0.82) / (W * 0.85)) ** 2 + ((y - H * 0.06) / (H * 0.55)) ** 2)
    base = base + np.clip(1 - d, 0, 1)[..., None] ** 2 * 20 * np.array(MINT, np.float32) / 255 * 2.2
    base = base + np.random.normal(0, 1.8, (H, W, 1)).astype(np.float32)
    return Image.fromarray(np.clip(base, 0, 255).astype(np.uint8), "RGB").convert("RGBA")


def wrap(d, s, f, max_w):
    lines, cur = [], ""
    for ch in s:
        if ch == "\n":
            lines.append(cur)
            cur = ""
            continue
        if tw(d, cur + ch, f) <= max_w:
            cur += ch
        else:
            lines.append(cur)
            cur = ch
    if cur:
        lines.append(cur)
    return lines


def text(d, xy, s, f, fill):
    d.text(xy, s, font=f, fill=fill)
    return xy[0] + tw(d, s, f)


def para(d, xy, s, f, fill, max_w, lh=1.55):
    x, y = xy
    for i, line in enumerate(wrap(d, s, f, max_w)):
        text(d, (x, y + i * int(f.size * lh)), line, f, fill)


def card(img, box, radius=28, fill=CARD, border=BORDER, accent=None, accent_w=8):
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(box, radius=radius, fill=fill + (255,), outline=border + (255,), width=2)
    if accent:
        d.rounded_rectangle([box[0] + 24, box[1] + 26, box[0] + 24 + accent_w, box[3] - 26],
                            radius=accent_w // 2, fill=accent + (255,))


def pill(img, xy, label, fg, fill=None, size=32, pad=34):
    d = ImageDraw.Draw(img)
    f = font(size, "Bold")
    w = int(tw(d, label, f)) + pad * 2
    h = size + 34
    x, y = xy
    if fill:
        d.rounded_rectangle([x, y, x + w, y + h], radius=h // 2, fill=fill + (255,))
    else:
        d.rounded_rectangle([x, y, x + w, y + h], radius=h // 2, outline=fg + (200,), width=3)
    text(d, (x + pad, y + 17), label, f, fg)
    return x + w


def page_number(img, idx):
    d = ImageDraw.Draw(img)
    s = f"{idx:02d} / 08"
    f = font(26, "Medium")
    text(d, (W - MX - tw(d, s, f), H - MY - 30), s, f, MUTED)


def head(img, eyebrow, title, title_size=78, y=MY):
    d = ImageDraw.Draw(img)
    text(d, (MX, y), eyebrow, font(30, "Bold"), MINT)
    d.rectangle([MX, y + 58, MX + 64, y + 64], fill=(60, 74, 70))
    yy = y + 106
    for line in wrap(d, title, font(title_size, "Black"), W - MX * 2):
        text(d, (MX, yy), line, font(title_size, "Black"), TEXT)
        yy += int(title_size * 1.22)
    return yy + 26


def save(img, idx):
    path = os.path.join(OUT, f"page-{idx:02d}.png")
    img.convert("RGB").save(path)
    return path


# ---------------- 页面 ----------------
def page_cover(p):
    img = bg()
    d = ImageDraw.Draw(img)
    pill(img, (MX, MY), p["eyebrow"], (16, 22, 20), fill=MINT)
    text(d, (MX, 268), p["title_a"], font(96, "Black"), TEXT)
    text(d, (MX, 398), p["title_b"], font(96, "Black"), TEXT)
    text(d, (MX, 556), p["title_c"], font(136, "Black"), MINT)
    d.rectangle([MX, 728, MX + 220, 736], fill=ORANGE)
    para(d, (MX, 790), p["sub"], font(40, "Medium"), MUTED, W - MX * 2)
    x = MX
    for c in p["chips"]:
        x = pill(img, (x, 900), c, TEXT, size=34) + 18
    card(img, [MX, 1180, W - MX, 1330], accent=MINT)
    text(d, (MX + 62, 1232), p["footer"], font(40, "Bold"), TEXT)
    print("   cover footer-right:", MX + 62 + tw(d, p["footer"], font(40, "Bold")))
    return img


def page_pain(p):
    img = bg()
    y = head(img, p["eyebrow"], p["title"])
    d = ImageDraw.Draw(img)
    text(d, (MX, y - 108 + 96), p["title2"], font(78, "Black"), MINT)
    y += 60
    for i, (t, b) in enumerate(p["items"]):
        box = [MX, y, W - MX, y + 190]
        card(img, box, accent=ORANGE if i == 0 else None)
        d = ImageDraw.Draw(img)
        text(d, (MX + 56, y + 40), t, font(44, "Bold"), TEXT)
        para(d, (MX + 56, y + 112), b, font(32, "Regular"), MUTED, W - MX * 2 - 112)
        y += 218
    text(d, (MX, y + 26), "不是你不够自律，是工具太多了", font(36, "Bold"), MINT)
    print("   pain bottom:", y + 26 + 40)
    return img


def page_rule(p):
    img = bg()
    y = head(img, p["eyebrow"], p["title"])
    d = ImageDraw.Draw(img)
    text(d, (MX, y - 108 + 96), p["title2"], font(78, "Black"), MINT)
    y += 70
    for i, (t, b) in enumerate(p["rules"], 1):
        box = [MX, y, W - MX, y + 200]
        card(img, box)
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([MX + 44, y + 52, MX + 132, y + 140], radius=22, fill=MINT + (255,))
        text(d, (MX + 66, y + 74), f"{i:02d}", font(46, "Black"), (14, 20, 18))
        text(d, (MX + 168, y + 52), t, font(46, "Bold"), TEXT)
        para(d, (MX + 168, y + 118), b, font(32, "Regular"), MUTED, W - MX * 2 - 224)
        y += 232
    print("   rule bottom:", y)
    return img


def page_tools(p):
    img = bg()
    y = head(img, p["eyebrow"], p["title"])
    d = ImageDraw.Draw(img)
    for i, (name, what, when) in enumerate(p["tools"]):
        box = [MX, y, W - MX, y + 212]
        card(img, box, accent=MINT if i == 0 else None)
        d = ImageDraw.Draw(img)
        text(d, (MX + 56, y + 32), name, font(50, "Black"), TEXT)
        para(d, (MX + 56, y + 104), what, font(32, "Regular"), MUTED, W - MX * 2 - 112)
        text(d, (MX + 56, y + 158), f"→ {when}", font(30, "Bold"), MINT)
        y += 240
    print(f"   tools({p['index']}) bottom:", y - 28)
    return img


def page_end(p):
    img = bg()
    y = head(img, p["eyebrow"], p["title"])
    d = ImageDraw.Draw(img)
    for i, (t, b) in enumerate(p["steps"], 1):
        box = [MX, y, W - MX, y + 196]
        card(img, box)
        d = ImageDraw.Draw(img)
        d.ellipse([MX + 44, y + 56, MX + 132, y + 144], outline=MINT + (255,), width=4)
        text(d, (MX + 74, y + 78), str(i), font(44, "Black"), MINT)
        text(d, (MX + 168, y + 50), t, font(46, "Bold"), TEXT)
        para(d, (MX + 168, y + 116), b, font(32, "Regular"), MUTED, W - MX * 2 - 224)
        y += 226
    card(img, [MX, y + 10, W - MX, y + 150], accent=ORANGE)
    d = ImageDraw.Draw(img)
    text(d, (MX + 62, y + 60), p["footer"], font(38, "Bold"), TEXT)
    text(d, (MX, y + 190), p["ask"], font(40, "Bold"), MINT)
    print("   end bottom:", y + 190 + 50)
    return img


BUILDERS = {"cover": page_cover, "pain": page_pain, "rule": page_rule,
            "tools": page_tools, "end": page_end}


def main():
    data = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "content.json"),
                          encoding="utf-8"))
    paths = []
    for i, page in enumerate(data["pages"], 1):
        img = BUILDERS[page["kind"]](page)
        if page["kind"] != "cover":
            page_number(img, i)
        p = save(img, i)
        paths.append(p)
        print("saved", os.path.basename(p))
    print(f"\n共 {len(paths)} 张，输出目录：{OUT}")


if __name__ == "__main__":
    main()
