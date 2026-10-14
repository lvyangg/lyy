# 小红书图文自动化流水线

一句话：**把一份 JSON 文案变成 8 张 3:4 的图文卡片，然后自动填进小红书创作服务平台**——你只负责最后检查一下、按一次发布。

整条链路只用 Python 标准库 + Edge 自带的调试协议，**不需要 Playwright / Selenium，也不往任何服务器传你的账号信息**。

---

## 它能做什么

- **代码排版出图**：中文标题不会被 AI 画糊，字号、边距、圆角、页码每次完全一致，一整套看起来就是同一套设计
- **两种视觉风格**：`hand` 手账风、`poster` 深色海报风，按 `content.json` 里的 `style` 字段切换
- **自动填表**：上传图片 → 填标题 → 填正文 → 加标签 → 开原创声明 → 选内容声明
- **保留人工确认**：默认停在第 7 步，你自己按「发布」；加 `--publish` 才全自动
- **发布流水**：每次发布追加一条到 `history.json`，配合选题池可以自动去重

## 它不做什么

- **不替你登录**。首次要你在弹出的 Edge 里扫码，登录态存在**你自己电脑**的 `edge-profile/` 里
- **不带任何现成文案和选题**。`content.json` / `topics.json` 由你自己填（见下面的示例文件）
- **不绕过平台风控**，也不做批量群发。一天 1-2 篇、人工确认后发布，是更稳的用法

---

## 需要什么

| 项目 | 要求 |
| --- | --- |
| 系统 | Windows 10 / 11 |
| 浏览器 | Microsoft Edge（已经在用就行） |
| Python | 3.9 以上 |
| 依赖 | `pip install -r xhs-auto/requirements.txt`（只有图片排版用到的 pillow / numpy / opencv-python） |
| 账号 | 你自己的小红书创作服务平台账号 |

---

## 三步开始

把 `xhs-auto/` 整个目录拷到你电脑上任意位置，然后：

**第 1 步 · 登录一次**
双击 `start_edge.bat`。会弹出一个新的 Edge 窗口——**这是独立配置目录，不影响你平时用的 Edge**。
在里面扫码登录小红书，登录态会被记住，以后不用再登。

**第 2 步 · 准备内容并出图**

```bash
copy content.example.json content.json     # 复制一份改成你自己的
python render_pages.py                    # 出图，落在 pages/page-01.png ...
```

**第 3 步 · 上传填写**

```bash
python publish.py                 # 填好停在发布前，你自己按发布
python auto_post.py               # 全自动：出图 → 上传 → 填写 → 声明 → 发布 → 记流水
python auto_post.py --no-publish  # 全自动但停在发布前
```

## 目录里都是什么

| 文件 | 作用 |
| --- | --- |
| `cdp.py` | 只用标准库实现的 Edge 调试协议客户端（WebSocket 握手 + 帧编解码） |
| `edge_path.py` | 自动定位 Edge（也支持用环境变量 `EDGE_PATH` 指定） |
| `render_pages.py` | 深色海报风渲染器（`cover` / `pain` / `rule` / `tools` / `end`） |
| `render_hand.py` | 手账风渲染器（`cover` / `pain` / `method` / `end`） |
| `render_by_style.py` | 按 `style` 字段自动选上面两个渲染器 |
| `publish.py` | 打开发布页 → 上传 → 填写（默认不点发布） |
| `auto_post.py` | 一键全流程 |
| `prepare_options.py` / `toggle_original.py` | 设置内容声明 / 原创声明 |
| `open_edge.py` / `start_edge.bat` | 用独立配置目录启动带调试端口的 Edge |
| `status.py` / `check_draft.py` / `check_notes.py` | 查看登录状态、草稿、已发布笔记 |
| `research_trending.py` / `research_inspiration.py` | 抓取同行热门笔记的标题、点赞、封面，用来找选题 |
| `content.example.json` | 文案模板：标题、正文、标签 + 每页文字 |
| `topics.example.json` | 选题池模板 |

## 它是怎么工作的

1. **连浏览器**：用 `--remote-debugging-port=9222` 启动独立的 Edge，脚本通过 Chrome DevTools Protocol 跟它对话。
   `cdp.py` 自己实现了 WebSocket 握手和帧的读写，所以一行第三方依赖都不需要。
2. **出图**：Pillow 按固定视觉母版排版（画布 1080×1440，也就是小红书要的 3:4），
   每页的文字来自 `content.json` 的 `pages` 数组。
3. **投文件**：通过 `DOM.setFileInputFiles` 把 `pages/` 里的图片直接塞给页面的文件输入框，
   模拟的是「选择文件」这一步，不依赖坐标点击。
4. **填表**：用 `Runtime.evaluate` 执行 JS 找标题框和正文框并写入，
   同时用可见性判断确认每个动作真的生效了（小红书改版时，改 `publish.py` 顶部的选择器即可）。

## 关于账号和数据

- 仓库里**不含任何账号信息**：登录态只存在于你本机的 `edge-profile/`，已被 `.gitignore` 排除
- 也不含现成文案和选题：`content.json` / `topics.json` / `history.json` 都在忽略列表里，由你自己填
- 脚本只操作你本机的 Edge，不会把数据发往第三方服务器
- 图片里也不要放个人敏感信息（手机号、住址、真实姓名），发出去就收不回来了

## 常见问题

**提示需要登录？** 在弹出的那个 Edge 窗口里扫码登录，然后重新运行脚本。

**找不到 Edge？** 设置环境变量再运行：
`set EDGE_PATH=D:\Program Files\Microsoft\Edge\Application\msedge.exe`

**找不到标题 / 正文输入框？** 小红书前端改版了。出错时截图会存到 `logs/`，
照着重写 `publish.py` 顶部的 `TITLE_SELECTORS` / `BODY_SELECTORS` 即可。

**想换版式或配色？** 改 `render_hand.py` 顶部的颜色令牌和 `card()`、`head()` 这些组件函数。

**能换成 Chrome 吗？** 可以。`edge_path.py` 里加一条 Chrome 的路径，或直接把 `EDGE_PATH` 指过去——
两者都是 Chromium，调试协议一样。

## 免责声明

用自动化操作第三方平台可能违反其用户协议，**账号风险由使用者自己承担**。
建议低频使用（一天 1-2 篇）、发布前人工过一眼、不做批量群发。
本仓库只提供技术实现，不对使用后果负责。

## 许可

MIT，见 `LICENSE`。随便改、随便用，保留版权声明即可。
