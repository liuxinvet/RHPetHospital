# -*- coding: utf-8 -*-
"""仁合宠物医院管理系统 - 数据库访问层（SQLite 本地库）"""
import os
import sys
import sqlite3
import hashlib

if getattr(sys, "frozen", False):
    # PyInstaller 打包后：数据库写在 exe 同目录（持久化），schema 从解包资源读
    BASE_DIR = os.path.dirname(sys.executable)
    RESOURCE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    RESOURCE_DIR = BASE_DIR

DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "hospital.db")
SCHEMA_PATH = os.path.join(RESOURCE_DIR, "schema.sql")

SALT = "rh_pet_hospital_2026"


def get_conn():
    """获取数据库连接（每请求/每次调用独立连接）"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def hash_pwd(password):
    """密码哈希"""
    return hashlib.sha256((SALT + password).encode("utf-8")).hexdigest()


def init_db():
    """初始化数据库：建表 + 种子数据"""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema = f.read()
    conn = get_conn()
    try:
        conn.executescript(schema)
        conn.commit()
        _seed(conn)
    finally:
        conn.close()


def _seed(conn):
    """种子数据：仅在对应表为空时插入"""
    # 默认管理员
    if conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"] == 0:
        conn.execute(
            "INSERT INTO users(username,password,real_name,role) VALUES(?,?,?,?)",
            ("admin", hash_pwd("123456"), "系统管理员", "admin"),
        )
        conn.execute(
            "INSERT INTO users(username,password,real_name,role) VALUES(?,?,?,?)",
            ("doctor", hash_pwd("123456"), "张医生", "doctor"),
        )
        conn.execute(
            "INSERT INTO users(username,password,real_name,role) VALUES(?,?,?,?)",
            ("front", hash_pwd("123456"), "前台小李", "frontdesk"),
        )

    # 系统设置
    defaults = {
        "hospital_name": "仁合宠物医院",
        "hospital_phone": "010-88888888",
        "hospital_address": "示例路 88 号",
        "reg_fee": "20",           # 默认挂号费
        "low_stock_default": "10", # 默认库存预警线
        "welcome_msg": "欢迎使用仁合宠物医院管理系统",
    }
    for k, v in defaults.items():
        if conn.execute("SELECT COUNT(*) c FROM settings WHERE key=?", (k,)).fetchone()["c"] == 0:
            conn.execute("INSERT INTO settings(key,value) VALUES(?,?)", (k, v))

    # 示例医生
    if conn.execute("SELECT COUNT(*) c FROM doctors").fetchone()["c"] == 0:
        for name, title, specialty in [
            ("张伟", "主治医师", "犬猫内科、皮肤科"),
            ("李娜", "执业兽医师", "外科手术、骨科"),
            ("王强", "助理兽医师", "影像诊断、化验"),
        ]:
            conn.execute(
                "INSERT INTO doctors(name,title,specialty) VALUES(?,?,?)",
                (name, title, specialty),
            )

    # 药品分类
    if conn.execute("SELECT COUNT(*) c FROM medicine_categories").fetchone()["c"] == 0:
        for cat in ["疫苗", "抗生素", "消炎药", "驱虫药", "皮肤病药", "营养品", "消毒用品", "手术用品"]:
            conn.execute("INSERT INTO medicine_categories(name) VALUES(?)", (cat,))

    # 示例药品
    if conn.execute("SELECT COUNT(*) c FROM medicines").fetchone()["c"] == 0:
        samples = [
            ("犬四联疫苗", "疫苗", "1头份/瓶", "瓶", "国产某厂", 35, 60, 20, 5, ""),
            ("狂犬疫苗", "疫苗", "1头份/瓶", "瓶", "国产某厂", 30, 50, 20, 5, ""),
            ("猫三联疫苗", "疫苗", "1头份/瓶", "瓶", "进口某厂", 80, 120, 15, 5, ""),
            ("阿莫西林克拉维酸钾片", "抗生素", "50mg*12片", "盒", "某药厂", 18, 35, 30, 10, ""),
            ("头孢氨苄片", "抗生素", "125mg*10片", "盒", "某药厂", 22, 40, 25, 10, ""),
            ("恩诺沙星注射液", "抗生素", "10ml", "支", "某药厂", 15, 28, 40, 20, ""),
            ("伊维菌素滴剂", "驱虫药", "0.5ml*3支", "盒", "某药厂", 25, 45, 18, 6, ""),
            ("非泼罗尼滴剂", "驱虫药", "1ml*3支", "盒", "某药厂", 30, 55, 16, 6, ""),
            ("益生菌粉", "营养品", "5g*10袋", "盒", "某药厂", 20, 38, 22, 8, ""),
            ("洗眼液", "消毒用品", "60ml", "瓶", "某药厂", 12, 25, 30, 10, ""),
            ("碘伏消毒液", "消毒用品", "100ml", "瓶", "某药厂", 6, 12, 50, 20, ""),
            ("医用棉签", "手术用品", "50支/包", "包", "某厂", 3, 6, 80, 30, ""),
        ]
        for name, cat, spec, unit, mfr, pp, sp, stock, low, exp in samples:
            cat_id = conn.execute(
                "SELECT id FROM medicine_categories WHERE name=?", (cat,)
            ).fetchone()["id"]
            conn.execute(
                """INSERT INTO medicines(name,category_id,spec,unit,manufacturer,
                   purchase_price,sale_price,stock,low_stock,expiry_date)
                   VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (name, cat_id, spec, unit, mfr, pp, sp, stock, low, exp),
            )

    conn.commit()
