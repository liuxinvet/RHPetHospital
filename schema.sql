-- ============================================================
-- 仁合宠物医院管理系统 数据库结构
-- SQLite 本地数据库
-- ============================================================

-- 用户表（登录账号）
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT UNIQUE NOT NULL,
  password TEXT NOT NULL,              -- sha256 哈希
  real_name TEXT DEFAULT '',
  role TEXT DEFAULT 'admin',           -- admin 管理员 / doctor 医生 / frontdesk 前台
  status INTEGER DEFAULT 1,            -- 1 启用 0 停用
  created_at TEXT DEFAULT (datetime('now','localtime'))
);

-- 系统设置
CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT DEFAULT ''
);

-- 宠物主（客户）
CREATE TABLE IF NOT EXISTS owners (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  phone TEXT DEFAULT '',
  wechat TEXT DEFAULT '',
  address TEXT DEFAULT '',
  remark TEXT DEFAULT '',
  created_at TEXT DEFAULT (datetime('now','localtime'))
);

-- 宠物档案
CREATE TABLE IF NOT EXISTS pets (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  owner_id INTEGER NOT NULL REFERENCES owners(id),
  name TEXT NOT NULL,
  species TEXT DEFAULT '狗',           -- 狗/猫/其他
  breed TEXT DEFAULT '',
  gender TEXT DEFAULT '公',            -- 公/母
  birthday TEXT DEFAULT '',
  weight REAL DEFAULT 0,
  color TEXT DEFAULT '',
  sterilized INTEGER DEFAULT 0,        -- 1 已绝育
  allergy TEXT DEFAULT '',             -- 过敏史
  chip_no TEXT DEFAULT '',             -- 芯片号
  remark TEXT DEFAULT '',
  created_at TEXT DEFAULT (datetime('now','localtime'))
);

-- 医生
CREATE TABLE IF NOT EXISTS doctors (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  title TEXT DEFAULT '',               -- 职称
  specialty TEXT DEFAULT '',           -- 专长
  phone TEXT DEFAULT '',
  status INTEGER DEFAULT 1,            -- 1 在职 0 离职
  created_at TEXT DEFAULT (datetime('now','localtime'))
);

-- 医生排班
CREATE TABLE IF NOT EXISTS schedules (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  doctor_id INTEGER NOT NULL REFERENCES doctors(id),
  work_date TEXT NOT NULL,             -- YYYY-MM-DD
  shift TEXT DEFAULT '白班',           -- 白班/夜班/休息
  UNIQUE(doctor_id, work_date, shift)
);

-- 挂号/预约
CREATE TABLE IF NOT EXISTS appointments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  pet_id INTEGER NOT NULL REFERENCES pets(id),
  owner_id INTEGER NOT NULL REFERENCES owners(id),
  doctor_id INTEGER REFERENCES doctors(id),
  appt_date TEXT NOT NULL,             -- 就诊日期 YYYY-MM-DD
  appt_time TEXT DEFAULT '',           -- 时段
  type TEXT DEFAULT '门诊',            -- 门诊/急诊/复诊/疫苗/美容/寄养
  status TEXT DEFAULT '待诊',          -- 待诊/就诊中/已完成/已取消/爽约
  symptom TEXT DEFAULT '',             -- 主诉
  fee REAL DEFAULT 0,                  -- 挂号费
  created_at TEXT DEFAULT (datetime('now','localtime'))
);

-- 病历（电子病历）
CREATE TABLE IF NOT EXISTS medical_records (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  pet_id INTEGER NOT NULL REFERENCES pets(id),
  appointment_id INTEGER REFERENCES appointments(id),
  doctor_id INTEGER REFERENCES doctors(id),
  record_date TEXT DEFAULT (date('now','localtime')),
  chief_complaint TEXT DEFAULT '',     -- 主诉
  examination TEXT DEFAULT '',         -- 检查所见
  diagnosis TEXT DEFAULT '',           -- 诊断
  treatment TEXT DEFAULT '',           -- 治疗方案/医嘱
  follow_up TEXT DEFAULT '',           -- 复诊建议
  created_at TEXT DEFAULT (datetime('now','localtime'))
);

-- 药品分类
CREATE TABLE IF NOT EXISTS medicine_categories (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT UNIQUE NOT NULL
);

-- 药品库存
CREATE TABLE IF NOT EXISTS medicines (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  category_id INTEGER REFERENCES medicine_categories(id),
  spec TEXT DEFAULT '',                -- 规格
  unit TEXT DEFAULT '盒',              -- 单位
  manufacturer TEXT DEFAULT '',        -- 厂商
  purchase_price REAL DEFAULT 0,       -- 进价
  sale_price REAL DEFAULT 0,           -- 售价
  stock INTEGER DEFAULT 0,             -- 当前库存
  low_stock INTEGER DEFAULT 10,        -- 库存预警线
  expiry_date TEXT DEFAULT '',         -- 有效期
  status INTEGER DEFAULT 1,            -- 1 在售 0 停用
  created_at TEXT DEFAULT (datetime('now','localtime'))
);

-- 处方
CREATE TABLE IF NOT EXISTS prescriptions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  record_id INTEGER REFERENCES medical_records(id),
  pet_id INTEGER NOT NULL REFERENCES pets(id),
  doctor_id INTEGER REFERENCES doctors(id),
  pres_date TEXT DEFAULT (date('now','localtime')),
  total REAL DEFAULT 0,
  remark TEXT DEFAULT '',
  created_at TEXT DEFAULT (datetime('now','localtime'))
);

-- 处方明细
CREATE TABLE IF NOT EXISTS prescription_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  prescription_id INTEGER NOT NULL REFERENCES prescriptions(id),
  medicine_id INTEGER NOT NULL REFERENCES medicines(id),
  qty INTEGER DEFAULT 1,
  price REAL DEFAULT 0,                -- 单价快照
  dosage TEXT DEFAULT '',              -- 用法用量
  subtotal REAL DEFAULT 0
);

-- 收费单
CREATE TABLE IF NOT EXISTS bills (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  bill_no TEXT UNIQUE NOT NULL,        -- 单号 RH+日期+序号
  owner_id INTEGER REFERENCES owners(id),
  pet_id INTEGER REFERENCES pets(id),
  appointment_id INTEGER REFERENCES appointments(id),
  bill_date TEXT DEFAULT (date('now','localtime')),
  total REAL DEFAULT 0,
  paid REAL DEFAULT 0,
  method TEXT DEFAULT '现金',          -- 现金/微信/支付宝/刷卡/挂账
  status TEXT DEFAULT '未结清',        -- 已结清/未结清/已退款
  remark TEXT DEFAULT '',
  created_at TEXT DEFAULT (datetime('now','localtime'))
);

-- 收费明细
CREATE TABLE IF NOT EXISTS bill_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  bill_id INTEGER NOT NULL REFERENCES bills(id),
  item_type TEXT DEFAULT '诊疗费',     -- 挂号费/诊疗费/药品费/检查费/住院费/美容费/其他
  name TEXT DEFAULT '',
  qty INTEGER DEFAULT 1,
  price REAL DEFAULT 0,
  subtotal REAL DEFAULT 0
);

-- 住院
CREATE TABLE IF NOT EXISTS hospitalizations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  hos_no TEXT UNIQUE NOT NULL,         -- 住院号
  pet_id INTEGER NOT NULL REFERENCES pets(id),
  room TEXT DEFAULT '',                -- 房间/笼位
  in_date TEXT DEFAULT (date('now','localtime')),
  out_date TEXT DEFAULT '',
  daily_fee REAL DEFAULT 0,            -- 每日费用
  reason TEXT DEFAULT '',              -- 住院原因
  status TEXT DEFAULT '住院中',        -- 住院中/已出院
  remark TEXT DEFAULT '',
  created_at TEXT DEFAULT (datetime('now','localtime'))
);

-- 护理记录
CREATE TABLE IF NOT EXISTS nursing_records (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  hospitalization_id INTEGER NOT NULL REFERENCES hospitalizations(id),
  nurse_time TEXT DEFAULT (datetime('now','localtime')),
  content TEXT DEFAULT '',             -- 护理内容
  temperature REAL DEFAULT 0,          -- 体温
  appetite TEXT DEFAULT '',            -- 食欲
  staff TEXT DEFAULT ''                -- 护理人员
);

-- 疫苗/免疫记录
CREATE TABLE IF NOT EXISTS vaccines (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  pet_id INTEGER NOT NULL REFERENCES pets(id),
  vaccine_name TEXT NOT NULL,          -- 犬四联/犬八联/狂犬/猫三联/妙三多等
  dose INTEGER DEFAULT 1,              -- 第几针
  vaccine_date TEXT DEFAULT (date('now','localtime')),
  next_date TEXT DEFAULT '',           -- 下次接种日期
  doctor_id INTEGER REFERENCES doctors(id),
  remark TEXT DEFAULT '',
  created_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_pets_owner ON pets(owner_id);
CREATE INDEX IF NOT EXISTS idx_appointments_date ON appointments(appt_date);
CREATE INDEX IF NOT EXISTS idx_appointments_status ON appointments(status);
CREATE INDEX IF NOT EXISTS idx_records_pet ON medical_records(pet_id);
CREATE INDEX IF NOT EXISTS idx_medicines_cat ON medicines(category_id);
CREATE INDEX IF NOT EXISTS idx_pres_items_pres ON prescription_items(prescription_id);
CREATE INDEX IF NOT EXISTS idx_bill_items_bill ON bill_items(bill_id);
CREATE INDEX IF NOT EXISTS idx_vaccines_pet ON vaccines(pet_id);
CREATE INDEX IF NOT EXISTS idx_hos_pet ON hospitalizations(pet_id);
