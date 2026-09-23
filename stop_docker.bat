@echo off
chcp 65001 >nul
title 仁合宠物医院 - 停止服务
cd /d %~dp0
docker compose down
echo 系统已停止，数据已保存（data 文件夹）
pause
