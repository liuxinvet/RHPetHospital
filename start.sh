#!/bin/bash
# 仁合宠物医院管理系统 - 一键启动 (Linux / macOS)
cd "$(dirname "$0")"
echo "==> 检查依赖..."
python3 -m pip install -r requirements.txt -q 2>/dev/null
echo "==> 启动系统，浏览器访问 http://127.0.0.1:8080"
python3 app.py
