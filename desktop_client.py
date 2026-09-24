# -*- coding: utf-8 -*-
"""
仁合宠物医院管理系统 - 桌面客户端
架构：本地服务（Flask, 仅本机 127.0.0.1）+ 桌面窗口客户端（pywebview）
双击启动后自动完成：初始化数据库 -> 启动本地服务 -> 打开桌面窗口。
关闭窗口即退出（服务随进程结束），数据保存在 exe 同目录 data\\hospital.db。
诊断：所有异常写入 exe 同目录 run.log；服务未就绪时弹窗提示。
"""
import os
import socket
import sys
import threading
import time
import traceback

import app as server_app
import database as db


def _exe_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


LOG_PATH = os.path.join(_exe_dir(), "run.log")


def log(msg):
    """写运行日志：优先 exe 同目录，失败则退回系统临时目录"""
    text = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n"
    for path in (LOG_PATH, os.path.join(tempfile_getdir(), "rh_pet_hospital_run.log")):
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(text)
            return
        except Exception:
            continue


def tempfile_getdir():
    import tempfile
    return tempfile.gettempdir()


def msgbox(text):
    """Windows 弹窗提示"""
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, text, "仁合宠物医院", 0x10)
    except Exception:
        pass


def pick_free_port(start=8080):
    """自动挑选空闲端口，避免被系统保留段/其他程序占用"""
    for port in range(start, start + 30):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return start


def start_local_server(port):
    """本地服务线程：初始化数据库并启动 Flask（仅回环地址，外部不可访问）"""
    try:
        log(f"初始化数据库，目录: {db.DATA_DIR}")
        db.init_db()
        log("数据库就绪，启动 Flask 127.0.0.1:" + str(port))
        server_app.app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)
    except Exception as e:
        log("服务启动失败:\n" + traceback.format_exc())
        msgbox(f"本地服务启动失败：{e}\n\n详细原因见 exe 同目录 run.log")
        raise SystemExit(1)


def main():
    port = pick_free_port()
    server_url = f"http://127.0.0.1:{port}"
    log(f"启动桌面客户端，服务地址 {server_url}")

    # 1. 启动本地服务线程
    threading.Thread(target=start_local_server, args=(port,), daemon=True).start()

    # 2. 等待服务就绪（最长 30 秒）
    import urllib.request
    ok = False
    for _ in range(60):
        try:
            urllib.request.urlopen(server_url, timeout=1)
            ok = True
            break
        except Exception:
            time.sleep(0.5)
    if not ok:
        log("30 秒内本地服务未就绪，请检查 run.log")
        msgbox("本地服务未在 30 秒内就绪，请查看 exe 同目录 run.log 后重试")

    # 3. 尝试桌面窗口客户端
    try:
        import webview
        webview.create_window(
            "仁合宠物医院管理系统",
            server_url,
            width=1440,
            height=900,
            min_size=(1024, 700),
        )
        webview.start()
    except Exception:
        # 4. 兜底：无桌面组件时退回系统默认浏览器
        import webbrowser
        webbrowser.open(server_url)
        log("未检测到桌面窗口组件，已用浏览器打开 " + server_url)
        while True:
            time.sleep(3600)


if __name__ == "__main__":
    main()
