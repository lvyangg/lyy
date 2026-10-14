# -*- coding: utf-8 -*-
"""定位 Edge 可执行文件。

顺序：环境变量 EDGE_PATH → 常见安装位置 → PATH 里的 msedge。
找不到会直接退出并提示，避免后面报一堆看不懂的错。
"""
import os
import shutil

CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]


def edge_exe():
    env = os.environ.get("EDGE_PATH")
    if env:
        if os.path.exists(env):
            return env
        raise SystemExit(f"环境变量 EDGE_PATH 指向的文件不存在：{env}")
    for p in CANDIDATES:
        if os.path.exists(p):
            return p
    found = shutil.which("msedge") or shutil.which("msedge.exe")
    if found:
        return found
    raise SystemExit(
        "找不到 Microsoft Edge。\n"
        "请装 Edge，或设置环境变量 EDGE_PATH 指向 msedge.exe，例如：\n"
        r'  set EDGE_PATH=D:\Program Files\Microsoft\Edge\Application\msedge.exe'
    )


if __name__ == "__main__":
    print(edge_exe())
