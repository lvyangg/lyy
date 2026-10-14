@echo off
chcp 65001 >nul
set "EDGE=%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"
if not exist "%EDGE%" set "EDGE=%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"
if not exist "%EDGE%" set "EDGE=msedge.exe"
echo 正在用「自动化配置」启动 Edge（不影响你平时用的 Edge）...
echo 首次使用需要在这个窗口里扫码登录一次小红书，之后会自动记住。
start "" "%EDGE%" ^
 --remote-debugging-port=9222 ^
 --user-data-dir="%~dp0edge-profile" ^
 --no-first-run --no-default-browser-check --start-maximized ^
 "https://creator.xiaohongshu.com/publish/publish?source=official"
echo.
echo 如果页面提示登录，请扫码；登录后回到命令行运行：
echo     python publish.py
timeout /t 6 >nul
