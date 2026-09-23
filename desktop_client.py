# -*- coding: utf-8 -*-
"""
仁合宠物医院管理系统 - 桌面客户端
架构：本地服务（Flask, 仅本机 127.0.0.1:8080）+ 桌面窗口客户端（pywebview）
双击启动后自动完成：初始化数据库 -> 启动本地服务 -> 打开桌面窗口。
关闭窗口即退出（服务随进程结束），数据保存在 exe 同目录 data\\hospital.db。
"""
import sys
import threading
import time

import app as server_app
import database as db

SERVER_URL = "http://127.0.0.1:8080"


def start_local_server():
    """本地服务线程：初始化数据库并启动 Flask（仅回环地址，外部不可访问）"""
    try:
        db.init_db()
        server_app.app.run(host="127.0.0.1", port=8080, debug=False, use_reloader=False)
    except Exception as e:  # 端口占用等场景给出提示后退出
        print(f"[错误] 本地服务启动失败: {e}")
        if getattr(sys, "frozen", False):
            try:
                import ctypes
                ctypes.windll.user32.MessageBoxW(0, f"本地服务启动失败：{e}", "仁合宠物医院", 0x10)
            except Exception:
                pass
        raise SystemExit(1)


def main():
    # 1. 启动本地服务线程
    threading.Thread(target=start_local_server, daemon=True).start()
    # 等待服务就绪
    import urllib.request
    for _ in range(30):
        try:
            urllib.request.urlopen(SERVER_URL, timeout=1)
            break
        except Exception:
            time.sleep(0.5)

    # 2. 尝试桌面窗口客户端
    try:
        import webview
        webview.create_window(
            "仁合宠物医院管理系统",
            SERVER_URL,
            width=1440,
            height=900,
            min_size=(1024, 700),
        )
        webview.start()
    except Exception:
        # 3. 兜底：无桌面组件时退回系统默认浏览器
        import webbrowser
        webbrowser.open(SERVER_URL)
        print(f"未检测到桌面窗口组件，已用浏览器打开 {SERVER_URL}，关闭本窗口即退出")
        while True:
            time.sleep(3600)


if __name__ == "__main__":
    main()
