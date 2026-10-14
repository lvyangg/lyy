# -*- coding: utf-8 -*-
"""极简 Chrome DevTools Protocol 客户端（只用标准库）。

用途：连接 Edge/Chrome 的调试端口，创建标签页、执行 JS、点击元素、上传文件。
"""
import base64
import json
import os
import socket
import struct
import time
import urllib.request


class CDPError(RuntimeError):
    pass


class _WS:
    """最小可用的 WebSocket 客户端（客户端帧带掩码，服务端帧不带）。"""

    def __init__(self, url, timeout=30):
        assert url.startswith("ws://"), url
        rest = url[5:]
        hostport, _, path = rest.partition("/")
        host, _, port = hostport.partition(":")
        self.sock = socket.create_connection((host, int(port or 80)), timeout=timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        req = (
            f"GET /{path} HTTP/1.1\r\nHost: {hostport}\r\nUpgrade: websocket\r\n"
            f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        self.sock.sendall(req.encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise CDPError("WebSocket 握手失败：连接被关闭")
            buf += chunk
        head, self.buf = buf.split(b"\r\n\r\n", 1)
        if b"101" not in head.split(b"\r\n")[0]:
            raise CDPError("WebSocket 握手失败: " + head.decode("latin1", "replace")[:200])

    def send(self, obj):
        payload = json.dumps(obj).encode()
        header = bytearray([0x81])
        mask = os.urandom(4)
        n = len(payload)
        if n < 126:
            header.append(0x80 | n)
        elif n < 65536:
            header.append(0x80 | 126)
            header += struct.pack(">H", n)
        else:
            header.append(0x80 | 127)
            header += struct.pack(">Q", n)
        header += mask
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        self.sock.sendall(bytes(header) + masked)

    def _frame(self):
        while True:
            if len(self.buf) >= 2:
                b0, b1 = self.buf[0], self.buf[1]
                length, offset = b1 & 0x7F, 2
                if length == 126 and len(self.buf) >= 4:
                    length, offset = struct.unpack(">H", self.buf[2:4])[0], 4
                elif length == 127 and len(self.buf) >= 10:
                    length, offset = struct.unpack(">Q", self.buf[2:10])[0], 10
                need = offset + (length if length >= 0 else 0)
                if len(self.buf) >= need and length < 2 ** 40:
                    payload, self.buf = self.buf[offset:need], self.buf[need:]
                    return b0 & 0x0F, payload
            chunk = self.sock.recv(262144)
            if not chunk:
                raise CDPError("连接已关闭")
            self.buf += chunk

    def recv(self):
        while True:
            opcode, payload = self._frame()
            if opcode == 9:
                continue
            if opcode == 8:
                raise CDPError("服务端关闭连接")
            if opcode == 1:
                return json.loads(payload.decode())


class Browser:
    def __init__(self, port=9222, timeout=60):
        self.port = port
        try:
            info = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=5))
        except Exception as exc:
            raise CDPError(
                f"连不上 Edge 调试端口 {port}：{exc}\n"
                f"请先双击 start_edge.bat（用自动化配置启动 Edge）"
            )
        self.version = info
        self.ws = _WS(info["webSocketDebuggerUrl"], timeout=timeout)
        self._id = 0
        self._sessions = {}

    def call(self, method, params=None, session=None, timeout=60):
        self._id += 1
        msg = {"id": self._id, "method": method, "params": params or {}}
        if session:
            msg["sessionId"] = session
        self.ws.send(msg)
        deadline = time.time() + timeout
        pending = []
        while time.time() < deadline:
            reply = self.ws.recv()
            if reply.get("id") == self._id:
                if "error" in reply:
                    raise CDPError(f"{method} 失败: {reply['error']}")
                for ev in pending:
                    self._dispatch(ev)
                return reply.get("result", {})
            if "method" in reply:
                pending.append(reply)
        raise CDPError(f"{method} 超时")

    def _dispatch(self, event):
        if event.get("method") == "Target.attachedToTarget":
            sid = event["params"]["sessionId"]
            self._sessions[event["params"]["targetInfo"]["targetId"]] = sid

    def new_page(self, url="about:blank"):
        target = self.call("Target.createTarget", {"url": url})
        attached = self.call("Target.attachToTarget", {"targetId": target["targetId"], "flatten": True})
        return Page(self, attached["sessionId"], target["targetId"])

    def attach(self, url_part):
        """复用已经打开的标签页（按 URL 片段匹配），没有就返回 None。"""
        try:
            pages = json.load(urllib.request.urlopen(
                f"http://127.0.0.1:{self.port}/json/list", timeout=5))
        except Exception:
            return None
        target = next((t for t in pages
                       if t.get("type") == "page" and url_part in t.get("url", "")), None)
        if not target:
            return None
        sid = self.call("Target.attachToTarget", {"targetId": target["id"], "flatten": True})["sessionId"]
        return Page(self, sid, target["id"])


class Page:
    def __init__(self, browser, session, target_id):
        self.b = browser
        self.session = session
        self.target_id = target_id
        self.call("Page.enable")
        self.call("Runtime.enable")

    def call(self, method, params=None, timeout=60):
        return self.b.call(method, params, session=self.session, timeout=timeout)

    def navigate(self, url, wait=3.0):
        self.call("Page.navigate", {"url": url})
        time.sleep(wait)

    def js(self, expression, await_promise=False, timeout=60):
        r = self.call("Runtime.evaluate", {
            "expression": expression, "returnByValue": True,
            "awaitPromise": await_promise, "userGesture": True,
        }, timeout=timeout)
        if r.get("exceptionDetails"):
            raise CDPError(json.dumps(r["exceptionDetails"], ensure_ascii=False)[:400])
        return r.get("result", {}).get("value")

    def wait_text(self, text, timeout=30, interval=1.0):
        """等页面上出现某段文字。"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.js(f"document.body && document.body.innerText.includes({json.dumps(text)})"):
                return True
            time.sleep(interval)
        return False

    def wait_js(self, expression, timeout=30, interval=1.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.js(expression):
                return True
            time.sleep(interval)
        return False

    def set_files(self, selector, files):
        doc = self.call("DOM.getDocument", {"depth": -1})
        node = self.call("DOM.querySelector", {"nodeId": doc["root"]["nodeId"], "selector": selector})
        if not node.get("nodeId"):
            raise CDPError(f"找不到文件输入框: {selector}")
        self.call("DOM.setFileInputFiles", {"files": files, "nodeId": node["nodeId"]})

    def insert_text(self, selector, text, index=0):
        """聚焦元素并模拟真人输入（能触发 React 的 onChange）。"""
        ok = self.js(f"""(() => {{
            const els = document.querySelectorAll({json.dumps(selector)});
            const el = els[{index}];
            if (!el) return false;
            el.scrollIntoView({{block: 'center'}});
            el.focus();
            if (el.isContentEditable && el.innerText.trim() === '') {{
                // 清空占位提示
                el.innerHTML = '';
            }}
            return true;
        }})()""")
        if not ok:
            raise CDPError(f"找不到输入框: {selector}[{index}]")
        time.sleep(0.4)
        self.call("Input.insertText", {"text": text})
        time.sleep(0.4)

    def click_text(self, text, tag="*"):
        """点击页面上包含指定文字的元素（取最内层可点击的）。"""
        return self.js(f"""(() => {{
            const target = {json.dumps(text)};
            const nodes = [...document.querySelectorAll({json.dumps(tag)})];
            const hit = nodes.reverse().find(n => (n.innerText || '').trim().includes(target)
                && n.offsetParent !== null && n.getBoundingClientRect().width > 0);
            if (!hit) return false;
            const clickable = hit.closest('button, a, [role=button], [class*=btn], [class*=tab]') || hit;
            clickable.scrollIntoView({{block: 'center'}});
            clickable.click();
            return true;
        }})()""")

    def screenshot(self, path):
        data = self.call("Page.captureScreenshot", {"format": "png"})["data"]
        with open(path, "wb") as f:
            f.write(base64.b64decode(data))
        return path

    def click_xy(self, x, y):
        """在页面坐标处派发真实鼠标事件（对付不响应 JS click 的自定义组件）。"""
        for kind, extra in (("mouseMoved", {}),
                            ("mousePressed", {"button": "left", "clickCount": 1}),
                            ("mouseReleased", {"button": "left", "clickCount": 1})):
            self.call("Input.dispatchMouseEvent", dict(
                {"type": kind, "x": float(x), "y": float(y), "buttons": 1 if kind != "mouseMoved" else 0}, **extra))
            time.sleep(0.08)

    def click_sel(self, selector, index=0):
        """把元素滚到中间，取它的中心坐标，然后真实鼠标点击。"""
        box = self.js(f"""(() => {{
            const el = document.querySelectorAll({json.dumps(selector)})[{index}];
            if (!el) return null;
            el.scrollIntoView({{block: 'center'}});
            const r = el.getBoundingClientRect();
            return {{x: r.x + r.width / 2, y: r.y + r.height / 2, w: r.width, h: r.height}};
        }})()""")
        if not box:
            raise CDPError(f"找不到元素: {selector}[{index}]")
        time.sleep(0.4)
        self.click_xy(box["x"], box["y"])
        return box

    def click_sel_by_text(self, text, exact=True):
        """按可见文字找到元素（取最内层匹配的），再真实鼠标点击。"""
        box = self.js(f"""(() => {{
            const want = {json.dumps(text)};
            const exact = {json.dumps(exact)};
            const nodes = [...document.querySelectorAll('*')].filter(el => {{
                const t = (el.innerText || '').trim();
                if (el.offsetParent === null || el.children.length > 2) return false;
                return exact ? t === want : t.includes(want);
            }});
            if (!nodes.length) return null;
            const el = nodes[nodes.length - 1];
            el.scrollIntoView({{block: 'center'}});
            const r = el.getBoundingClientRect();
            return {{x: r.x + r.width / 2, y: r.y + r.height / 2, w: r.width, h: r.height}};
        }})()""")
        if not box:
            raise CDPError(f"找不到文字为「{text}」的元素")
        time.sleep(0.4)
        self.click_xy(box["x"], box["y"])
        return box
