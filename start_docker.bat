@echo off
chcp 65001 >nul
title 仁合宠物医院 - 一键启动
cd /d %~dp0

echo ============================================
echo  仁合宠物医院管理系统 - Docker 版启动
echo ============================================
echo.

where docker >nul 2>nul
if %errorlevel% neq 0 (
    echo [错误] 未检测到 Docker Desktop
    echo 请先安装 Docker Desktop（免费）: https://www.docker.com/products/docker-desktop/
    echo 安装后重新双击本脚本即可。
    pause
    exit /b 1
)

echo [1/2] 构建并启动服务（首次约 1-3 分钟，之后秒开）...
docker compose up -d --build
if %errorlevel% neq 0 (
    echo [错误] 启动失败，请检查 Docker Desktop 是否已打开
    pause
    exit /b 1
)

echo [2/2] 正在打开浏览器...
timeout /t 2 /nobreak >nul
start http://localhost:8080

echo.
echo 系统已启动！浏览器未自动打开时请手动访问: http://localhost:8080
echo 默认账号: admin / 123456
echo 停止系统请双击 stop_docker.bat
pause
