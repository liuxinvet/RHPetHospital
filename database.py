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
    """初始化数据库：建表 + 种子数据 + 增量迁移"""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema = f.read()
    conn = get_conn()
    try:
        conn.executescript(schema)
        migrate(conn)
        conn.commit()
        _seed(conn)
    finally:
        conn.close()


# ============ 增量迁移：老库自动补列/建表 ============

_MIGRATIONS = {
    "appointments": [
        ("time_type", "TEXT DEFAULT '上午'"),
        ("remark", "TEXT DEFAULT ''"),
    ],
    "medical_records": [
        ("temperature", "REAL DEFAULT 0"),
        ("weight", "REAL DEFAULT 0"),
        ("breathe", "INTEGER DEFAULT 0"),
        ("heartrate", "INTEGER DEFAULT 0"),
        ("tongkong", "TEXT DEFAULT ''"),
        ("blood_pressure", "TEXT DEFAULT ''"),
        ("chiefnote", "TEXT DEFAULT ''"),
        ("checknote", "TEXT DEFAULT ''"),
        ("carenote", "TEXT DEFAULT ''"),
        ("processnote", "TEXT DEFAULT ''"),
        ("physicalorder", "TEXT DEFAULT ''"),
        ("conditionnote", "TEXT DEFAULT ''"),
        ("visitrecord", "TEXT DEFAULT ''"),
        ("surgical_record", "TEXT DEFAULT ''"),
        ("hospitalnode", "TEXT DEFAULT ''"),
        ("feeding_method", "TEXT DEFAULT ''"),
        ("feeding_frequency", "TEXT DEFAULT ''"),
        ("food_changes", "TEXT DEFAULT ''"),
        ("is_vaccine", "TEXT DEFAULT ''"),
        ("is_deworming", "TEXT DEFAULT ''"),
        ("previous_medical", "TEXT DEFAULT ''"),
        ("mentality", "TEXT DEFAULT ''"),
        ("physical_condition_score", "INTEGER DEFAULT 0"),
        ("muscle_score", "INTEGER DEFAULT 0"),
        ("periodontal_score", "INTEGER DEFAULT 0"),
        ("eyes", "TEXT DEFAULT ''"),
        ("nose", "TEXT DEFAULT ''"),
        ("ears", "TEXT DEFAULT ''"),
        ("oral_cavity", "TEXT DEFAULT ''"),
        ("muscle", "TEXT DEFAULT ''"),
        ("skins", "TEXT DEFAULT ''"),
        ("nerve", "TEXT DEFAULT ''"),
        ("urology", "TEXT DEFAULT ''"),
        ("heart_lung", "TEXT DEFAULT ''"),
        ("abdomen", "TEXT DEFAULT ''"),
        ("lymph_gland", "TEXT DEFAULT ''"),
        ("skin_elasticity", "TEXT DEFAULT ''"),
        ("eye_condition", "TEXT DEFAULT ''"),
        ("oral_mucosa", "TEXT DEFAULT ''"),
        ("crt", "TEXT DEFAULT ''"),
        ("suspected_illness", "TEXT DEFAULT ''"),
        ("again_visit_num", "INTEGER DEFAULT 0"),
        ("open_appointment", "INTEGER DEFAULT 0"),
        ("appointment_time", "TEXT DEFAULT ''"),
    ],
    "bills": [
        ("sale_employee_id", "INTEGER REFERENCES doctors(id)"),
        ("sale_employee_name", "TEXT DEFAULT ''"),
        ("service_employee_id", "INTEGER REFERENCES doctors(id)"),
        ("service_employee_name", "TEXT DEFAULT ''"),
    ],
    "bill_items": [
        ("is_member_price", "INTEGER DEFAULT 0"),
    ],
    "doctors": [
        ("commission_rate", "REAL DEFAULT 0"),
    ],
}

_NEW_TABLES = {
    "foster_records": """
        CREATE TABLE IF NOT EXISTS foster_records (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          foster_no TEXT UNIQUE NOT NULL,
          pet_id INTEGER NOT NULL REFERENCES pets(id),
          owner_id INTEGER NOT NULL REFERENCES owners(id),
          in_date TEXT NOT NULL,
          out_date TEXT DEFAULT '',
          daily_fee REAL DEFAULT 0,
          deposit REAL DEFAULT 0,
          total_fee REAL DEFAULT 0,
          reason TEXT DEFAULT '',
          status TEXT DEFAULT '寄养中',
          remark TEXT DEFAULT '',
          created_at TEXT DEFAULT (datetime('now','localtime'))
        )""",
    "return_visits": """
        CREATE TABLE IF NOT EXISTS return_visits (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          pet_id INTEGER NOT NULL REFERENCES pets(id),
          owner_id INTEGER NOT NULL REFERENCES owners(id),
          record_id INTEGER REFERENCES medical_records(id),
          plan_date TEXT NOT NULL,
          actual_date TEXT DEFAULT '',
          visit_type TEXT DEFAULT '电话',
          visit_result TEXT DEFAULT '',
          status TEXT DEFAULT '待回访',
          main_employee_id INTEGER REFERENCES doctors(id),
          diagnosis TEXT DEFAULT '',
          remark TEXT DEFAULT '',
          created_at TEXT DEFAULT (datetime('now','localtime'))
        )""",
    "member_cards": """
        CREATE TABLE IF NOT EXISTS member_cards (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          card_no TEXT UNIQUE NOT NULL,
          owner_id INTEGER NOT NULL REFERENCES owners(id),
          card_type TEXT DEFAULT '储值卡',
          card_name TEXT DEFAULT '',
          balance REAL DEFAULT 0,
          times_left INTEGER DEFAULT 0,
          discount REAL DEFAULT 1,
          points INTEGER DEFAULT 0,
          total_recharge REAL DEFAULT 0,
          total_consume REAL DEFAULT 0,
          status TEXT DEFAULT '正常',
          remark TEXT DEFAULT '',
          created_at TEXT DEFAULT (datetime('now','localtime'))
        )""",
    "card_recharges": """
        CREATE TABLE IF NOT EXISTS card_recharges (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          card_id INTEGER NOT NULL REFERENCES member_cards(id),
          amount REAL DEFAULT 0,
          method TEXT DEFAULT '现金',
          operator TEXT DEFAULT '',
          recharge_date TEXT DEFAULT (date('now','localtime')),
          remark TEXT DEFAULT '',
          created_at TEXT DEFAULT (datetime('now','localtime'))
        )""",
    "card_consumes": """
        CREATE TABLE IF NOT EXISTS card_consumes (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          card_id INTEGER NOT NULL REFERENCES member_cards(id),
          bill_id INTEGER REFERENCES bills(id),
          kind TEXT DEFAULT '储值扣款',
          amount REAL DEFAULT 0,
          times INTEGER DEFAULT 0,
          points INTEGER DEFAULT 0,
          consume_date TEXT DEFAULT (date('now','localtime')),
          remark TEXT DEFAULT '',
          created_at TEXT DEFAULT (datetime('now','localtime'))
        )""",
    "stock_bills": """
        CREATE TABLE IF NOT EXISTS stock_bills (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          bill_no TEXT UNIQUE NOT NULL,
          bill_type TEXT DEFAULT '采购入库',
          supplier TEXT DEFAULT '',
          total_amount REAL DEFAULT 0,
          bill_date TEXT DEFAULT (date('now','localtime')),
          operator TEXT DEFAULT '',
          remark TEXT DEFAULT '',
          created_at TEXT DEFAULT (datetime('now','localtime'))
        )""",
    "stock_bill_items": """
        CREATE TABLE IF NOT EXISTS stock_bill_items (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          bill_id INTEGER NOT NULL REFERENCES stock_bills(id),
          medicine_id INTEGER NOT NULL REFERENCES medicines(id),
          qty INTEGER DEFAULT 0,
          price REAL DEFAULT 0,
          amount REAL DEFAULT 0
        )""",
}


def migrate(conn):
    """对已存在的旧库执行增量迁移：补列 + 建新表，全程幂等"""
    # 1) 补列
    for table, cols in _MIGRATIONS.items():
        existing = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        for col, decl in cols:
            if col not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")
    # 2) 建新表
    for name, ddl in _NEW_TABLES.items():
        conn.execute(ddl)
    # 3) 补索引
    for idx, ddl in {
        "idx_foster_pet": "CREATE INDEX IF NOT EXISTS idx_foster_pet ON foster_records(pet_id)",
        "idx_foster_status": "CREATE INDEX IF NOT EXISTS idx_foster_status ON foster_records(status)",
        "idx_rv_plan": "CREATE INDEX IF NOT EXISTS idx_rv_plan ON return_visits(plan_date)",
        "idx_rv_status": "CREATE INDEX IF NOT EXISTS idx_rv_status ON return_visits(status)",
        "idx_cards_owner": "CREATE INDEX IF NOT EXISTS idx_cards_owner ON member_cards(owner_id)",
        "idx_card_recharge_card": "CREATE INDEX IF NOT EXISTS idx_card_recharge_card ON card_recharges(card_id)",
        "idx_card_consume_card": "CREATE INDEX IF NOT EXISTS idx_card_consume_card ON card_consumes(card_id)",
        "idx_stock_bill_date": "CREATE INDEX IF NOT EXISTS idx_stock_bill_date ON stock_bills(bill_date)",
        "idx_stock_items_bill": "CREATE INDEX IF NOT EXISTS idx_stock_bill_items ON stock_bill_items(bill_id)",
    }.items():
        conn.execute(ddl)


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
