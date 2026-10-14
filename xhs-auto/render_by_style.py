# -*- coding: utf-8 -*-
"""按 content.json 里的 style 字段选择渲染器（hand=手账风，poster=深色海报风）。"""
import json
import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
meta = json.load(open(os.path.join(HERE, "content.json"), encoding="utf-8"))
style = meta.get("style", "poster")
script = "render_hand.py" if style == "hand" else "render_pages.py"
print(f"[renderer] style={style} -> {script}")
sys.argv = [os.path.join(HERE, script)]
runpy.run_path(os.path.join(HERE, script), run_name="__main__")
