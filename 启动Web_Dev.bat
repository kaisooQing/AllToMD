@echo off
chcp 65001 >nul
title AllToMD Web UI Dev

echo ==========================================
echo   AllToMD Web UI - Dev Mode
echo   开发模式：前后端分离启动
echo ==========================================
echo.

REM 检查端口 7860 是否被占用
netstat -ano | findstr ":7860 " | findstr "LISTENING" >nul 2>&1
if %errorlevel% equ 0 (
    echo [警告] 端口 7860 已被占用，后端可能已在运行。
    echo 请先关闭旧进程，或直接访问 http://127.0.0.1:7860
    echo.
    pause
    exit /b 1
)

REM 设置环境变量
set MODELSCOPE_CACHE=%~dp0model_cache
set MINERU_MODEL_SOURCE=modelscope
set MINERU_WEB_UI_DIR=%~dp0frontend\dist

echo [配置] 模型缓存目录: %MODELSCOPE_CACHE%
echo [配置] 后端服务端口: 7860
echo [配置] 前端开发端口: 5173
echo.
echo [启动] 后端服务启动中...
echo [启动] 前端开发服务器将在 3 秒后启动...
echo [提示] 前端访问地址: http://localhost:5173
echo [提示] 按 Ctrl+C 可停止服务
echo.

start "AllToMD Backend" cmd /k "cd /d %~dp0 && set MODELSCOPE_CACHE=%~dp0model_cache && set MINERU_MODEL_SOURCE=modelscope && set MINERU_WEB_UI_DIR=%~dp0frontend\dist && %~dp0.env\python.exe -m mineru.cli.fast_api --port 7860"

timeout /t 3 >nul

start "AllToMD Frontend" cmd /k "cd /d %~dp0\frontend && npm run dev"
