# -*- coding: utf-8 -*-
"""手账风格小红书图文（6 页，1080x1440，3:4）。

目的：和之前的"深色科技海报"明显区分开，看起来像真人手作笔记，降低被判定为
「AI 批量模板内容」的概率。视觉母版仍然固定：
  画布 1080x1440 · 安全边距 左右 80 / 上下 96 · 页码固定在右下
  色彩：纸色 #FBF7EE / 墨色 #2B2620 / 砖红 #C8503A / 墨绿 #2F5D50 / 便签 #FFF6D8
  字体：标题楷体（手写感），正文微软雅黑
"""
import json
import math
import os
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1440
MX, MY = 80, 96
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pages")
os.makedirs(OUT, exist_ok=True)

PAPER = (251, 247, 238)
PAPER_D = (243, 236, 222)
INK = (43, 38, 32)
INK_SOFT = (110, 101, 90)
RED = (200, 80, 58)
GREEN = (47, 93, 80)
NOTE = (255, 246, 216)
NOTE_LINE = (232, 214, 168)

KAI = r"C:\Windows\Fonts\simkai.ttf"
HEI = r"C:\Windows\Fonts\msyh.ttc"
HEI_B = r"C:\Windows\Fonts\msyhbd.ttc"
_cache = {}


def font(path, size):
    key = (path, size)
    if key not in _cache:
        _cache[key] = ImageFont.truetype(path, size)
    return _cache[key]


def hand(size):
    return font(KAI, size)


def sans(size, bold=False):
    return font(HEI_B if bold else HEI, size)


def bg():
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    t = np.clip((x / W * 0.35 + y / H * 0.65), 0, 1)[..., None]
    base = (1 - t) * np.array(PAPER, np.float32) + t * np.array(PAPER_D, np.float32)
    base = base + np.random.normal(0, 3.2, (H, W, 1)).astype(np.float32)
    return Image.fromarray(np.clip(base, 0, 255).astype(np.uint8), "RGB").convert("RGBA")


def tw(d, s, f):
    return d.textlength(s, font=f)


def text(d, xy, s, f, fill):
    d.text(xy, s, font=f, fill=fill)
    return xy[0] + tw(d, s, f)


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


def para(d, xy, s, f, fill, max_w, lh=1.6):
    x, y = xy
    for i, line in enumerate(wrap(d, s, f, max_w)):
        text(d, (x, y + i * int(f.size * lh)), line, f, fill)
    return y + len(wrap(d, s, f, max_w)) * int(f.size * lh)


def hand_underline(d, x, y, width, color=RED, width_px=7, seed=7):
    """手绘感下划线：几段略微起伏的短线。"""
    rnd = random.Random(seed)
    seg = 46
    cx = x
    end = x + width
    while cx < end:
        dy = rnd.randint(-4, 4)
        nx = min(cx + seg, end)
        d.line([cx, y + dy, nx, y + rnd.randint(-4, 4)], fill=color, width=width_px)
        if nx >= end:
            break
        cx = nx - 6


def tape(img, xy, w=210, h=58, angle=-18, color=(226, 208, 170), alpha=120):
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rectangle([0, 0, w, h], fill=color + (alpha,))
    layer = layer.rotate(angle, expand=True, resample=Image.BICUBIC)
    img.alpha_composite(layer, (int(xy[0]), int(xy[1])))


def sticky(img, box, color=NOTE, line=NOTE_LINE, radius=10):
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([box[0] + 5, box[1] + 6, box[2] + 5, box[3] + 6], radius=radius,
                        fill=(200, 188, 160, 60))
    d.rounded_rectangle(box, radius=radius, fill=color + (255,), outline=line + (255,), width=2)


def eyebrow(img, xy, s, color=GREEN):
    d = ImageDraw.Draw(img)
    text(d, xy, s, sans(30, True), color)
    d.line([xy[0], xy[1] + 46, xy[0] + 46, xy[1] + 46], fill=color + (200,), width=4)


def page_no(img, idx, total=6):
    d = ImageDraw.Draw(img)
    s = f"{idx} / {total}"
    f = hand(34)
    text(d, (W - MX - tw(d, s, f), H - MY - 30), s, f, INK_SOFT)


def save(img, idx):
    path = os.path.join(OUT, f"page-{idx:02d}.png")
    img.convert("RGB").save(path)
    return path


# ---------------- 页面 ----------------
def page_cover(p):
    img = bg()
    d = ImageDraw.Draw(img)
    tape(img, (MX - 20, MY - 40), 230, 60, -16)
    text(d, (MX, MY + 30), p["eyebrow"], sans(32, True), GREEN)
    y = 300
    for key, size in (("title1", 132), ("title2", 132)):
        text(d, (MX, y), p[key], hand(size), INK)
        y += 168
    text(d, (MX, y), p["title3"], hand(132), INK)
    hand_underline(d, MX, y + 158, int(tw(d, p["title3"], hand(132))), RED, 8, seed=3)
    para(d, (MX, y + 214), p["sub"], sans(40), INK_SOFT, W - MX * 2)
    sticky(img, [MX, 1120, W - MX, 1290])
    d = ImageDraw.Draw(img)
    text(d, (MX + 44, 1168), p["footer"], sans(38, True), INK)
    text(d, (MX + 44, 1224), "滑到最后有一句我常说的话术", sans(30), INK_SOFT)
    print("   cover: title3-right", MX + tw(d, p["title3"], hand(132)))
    return img


def page_pain(p):
    img = bg()
    eyebrow(img, (MX, MY), p["eyebrow"])
    d = ImageDraw.Draw(img)
    y = MY + 110
    text(d, (MX, y), p["title"], hand(92), INK)
    text(d, (MX, y + 118), p["title2"], hand(92), INK)
    hand_underline(d, MX, y + 118 + 112, int(tw(d, p["title2"], hand(92))), RED, 7, seed=11)
    y += 300
    for i, (t, b) in enumerate(p["items"], 1):
        raw = [MX, y, W - MX, y + 210]
        sticky(img, raw)
        d = ImageDraw.Draw(img)
        d.ellipse([MX + 34, y + 40, MX + 106, y + 112], outline=RED + (255,), width=5)
        text(d, (MX + 52, y + 56), str(i), hand(48), RED)
        text(d, (MX + 140, y + 44), t, hand(56), INK)
        para(d, (MX + 140, y + 122), b, sans(34), INK_SOFT, W - MX * 2 - 190)
        y += 240
    print("   pain bottom:", y)
    return img


def page_method(p):
    img = bg()
    eyebrow(img, (MX, MY), p["eyebrow"])
    d = ImageDraw.Draw(img)
    num = p["num"]
    d.ellipse([MX, MY + 100, MX + 150, MY + 250], outline=GREEN + (255,), width=6)
    text(d, (MX + 44, MY + 132), num, hand(90), GREEN)
    text(d, (MX + 200, MY + 118), p["title"], hand(104), INK)
    hand_underline(d, MX + 200, MY + 244, int(tw(d, p["title"], hand(104))), RED, 7, seed=5)
    y = MY + 340
    y = para(d, (MX, y), p["body"], sans(40), INK, W - MX * 2, lh=1.65)
    d = ImageDraw.Draw(img)
    box = [MX, y + 70, W - MX, y + 70 + 250]
    d.rounded_rectangle(box, radius=14, fill=(255, 255, 255, 210), outline=NOTE_LINE + (255,), width=2)
    d.rectangle([box[0], box[1], box[0] + 12, box[3]], fill=GREEN + (255,))
    text(d, (box[0] + 46, box[1] + 34), "我常说的话", sans(30, True), GREEN)
    para(d, (box[0] + 46, box[1] + 90), p["quote"], hand(44), INK, W - MX * 2 - 100, lh=1.5)
    print(f"   method{num} bottom:", box[3])
    return img


def page_end(p):
    img = bg()
    eyebrow(img, (MX, MY), p["eyebrow"])
    d = ImageDraw.Draw(img)
    y = MY + 110
    text(d, (MX, y), p["title"], hand(96), INK)
    text(d, (MX, y + 124), p["title2"], hand(96), INK)
    hand_underline(d, MX, y + 124 + 116, int(tw(d, p["title2"], hand(96))), RED, 7, seed=9)
    y += 330
    for t, b in p["steps"]:
        d.rounded_rectangle([MX, y, W - MX, y + 170], radius=14, fill=(255, 255, 255, 220),
                            outline=NOTE_LINE + (255,), width=2)
        d.line([MX + 40, y + 60, MX + 40, y + 112], fill=RED + (255,), width=6)
        text(d, (MX + 74, y + 40), t, hand(54), INK)
        para(d, (MX + 74, y + 104), b, sans(32), INK_SOFT, W - MX * 2 - 120)
        y += 200
    d = ImageDraw.Draw(img)
    text(d, (MX, y + 24), p["ask"], hand(52), GREEN)
    print("   end bottom:", y + 24 + 60)
    return img


BUILDERS = {"cover": page_cover, "pain": page_pain, "method": page_method, "end": page_end}


def main():
    data = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "content.json"),
                          encoding="utf-8"))
    pages = data["pages"]
    for old in os.listdir(OUT):                      # 清掉上一版的图，避免页数不一致
        if old.endswith(".png"):
            os.remove(os.path.join(OUT, old))
    for i, page in enumerate(pages, 1):
        img = BUILDERS[page["kind"]](page)
        page_no(img, i, len(pages))
        print("saved", os.path.basename(save(img, i)))
    print(f"\n共 {len(pages)} 张（手账风），目录：{OUT}")


if __name__ == "__main__":
    main()
