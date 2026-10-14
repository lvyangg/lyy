@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo [1/3] 生成图文图片...
python render_pages.py
if errorlevel 1 (
  echo 生成失败，请检查上面的报错
  pause
  exit /b 1
)
echo.
echo [2/3] 启动 Edge 并上传填写（如果提示需要登录，请先在 Edge 里登录）
python publish.py
echo.
echo [3/3] 完成。若已停在第 7 步，请到 Edge 窗口检查后自己点「发布」。
pause
