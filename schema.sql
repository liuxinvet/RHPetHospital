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
  appt_time TEXT DEFAULT '',           -- 具体时间 HH:MM
  time_type TEXT DEFAULT '上午',       -- 时间段 上午/下午/晚上
  type TEXT DEFAULT '门诊',            -- 门诊/急诊/复诊/疫苗/美容/寄养/手术/体检
  status TEXT DEFAULT '待诊',          -- 待诊/就诊中/已完成/已取消/爽约
  symptom TEXT DEFAULT '',             -- 主诉
  remark TEXT DEFAULT '',              -- 备注
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
  -- 生命体征
  temperature REAL DEFAULT 0,          -- 体温 ℃
  weight REAL DEFAULT 0,               -- 体重 kg
  breathe INTEGER DEFAULT 0,           -- 呼吸 次/分
  heartrate INTEGER DEFAULT 0,         -- 心率 次/分
  tongkong TEXT DEFAULT '',            -- 瞳孔
  blood_pressure TEXT DEFAULT '',      -- 血压
  -- 病案分区记录
  chiefnote TEXT DEFAULT '',           -- 主诉记录
  checknote TEXT DEFAULT '',           -- 检查所见
  carenote TEXT DEFAULT '',            -- 护理记录
  processnote TEXT DEFAULT '',         -- 病程记录
  physicalorder TEXT DEFAULT '',       -- 医嘱
  conditionnote TEXT DEFAULT '',       -- 病情记录
  visitrecord TEXT DEFAULT '',         -- 复诊记录
  surgical_record TEXT DEFAULT '',     -- 手术记录
  hospitalnode TEXT DEFAULT '',        -- 住院记录
  -- 问诊信息
  feeding_method TEXT DEFAULT '',      -- 喂养方式
  feeding_frequency TEXT DEFAULT '',   -- 喂食频率
  food_changes TEXT DEFAULT '',        -- 换粮史
  is_vaccine TEXT DEFAULT '',          -- 免疫状态 未免疫/已免疫/免疫不全
  is_deworming TEXT DEFAULT '',        -- 驱虫状态 未驱虫/已驱虫
  previous_medical TEXT DEFAULT '',    -- 既往病史
  -- 精神状态与评分
  mentality TEXT DEFAULT '',           -- 精神 正常/机警/沉郁/嗜睡/昏迷/兴奋
  physical_condition_score INTEGER DEFAULT 0,  -- 体况评分 1-9
  muscle_score INTEGER DEFAULT 0,      -- 肌肉评分 0-3
  periodontal_score INTEGER DEFAULT 0, -- 牙周评分 0-4
  -- 系统检查
  eyes TEXT DEFAULT '', nose TEXT DEFAULT '', ears TEXT DEFAULT '',
  oral_cavity TEXT DEFAULT '', muscle TEXT DEFAULT '', skins TEXT DEFAULT '',
  nerve TEXT DEFAULT '', urology TEXT DEFAULT '',
  heart_lung TEXT DEFAULT '', abdomen TEXT DEFAULT '', lymph_gland TEXT DEFAULT '',
  -- 脱水评估
  skin_elasticity TEXT DEFAULT '',     -- 皮肤弹性
  eye_condition TEXT DEFAULT '',       -- 眼球凹陷
  oral_mucosa TEXT DEFAULT '',         -- 口腔黏膜
  crt TEXT DEFAULT '',                 -- 毛细血管再充盈
  -- 诊断与复诊
  suspected_illness TEXT DEFAULT '',   -- 疑似疾病
  again_visit_num INTEGER DEFAULT 0,   -- 复诊次数
  open_appointment INTEGER DEFAULT 0,  -- 是否预约复诊 1是
  appointment_time TEXT DEFAULT '',    -- 预约复诊时间
  created_at TEXT DEFAULT (datetime('now','localtime'))
);

-- 寄养记录
CREATE TABLE IF NOT EXISTS foster_records (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  foster_no TEXT UNIQUE NOT NULL,      -- 寄养单号 F+日期+序号
  pet_id INTEGER NOT NULL REFERENCES pets(id),
  owner_id INTEGER NOT NULL REFERENCES owners(id),
  in_date TEXT NOT NULL,               -- 入住日期
  out_date TEXT DEFAULT '',            -- 离店日期
  daily_fee REAL DEFAULT 0,            -- 每日费用
  deposit REAL DEFAULT 0,              -- 预交押金
  total_fee REAL DEFAULT 0,            -- 累计费用
  reason TEXT DEFAULT '',              -- 寄养原因
  status TEXT DEFAULT '寄养中',        -- 寄养中/已结束
  remark TEXT DEFAULT '',
  created_at TEXT DEFAULT (datetime('now','localtime'))
);

-- 回访记录
CREATE TABLE IF NOT EXISTS return_visits (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  pet_id INTEGER NOT NULL REFERENCES pets(id),
  owner_id INTEGER NOT NULL REFERENCES owners(id),
  record_id INTEGER REFERENCES medical_records(id),
  plan_date TEXT NOT NULL,             -- 计划回访日期
  actual_date TEXT DEFAULT '',         -- 实际回访日期
  visit_type TEXT DEFAULT '电话',      -- 电话/微信/短信/上门
  visit_result TEXT DEFAULT '',        -- 回访内容/结果
  status TEXT DEFAULT '待回访',        -- 待回访/已回访/无需回访
  main_employee_id INTEGER REFERENCES doctors(id),
  diagnosis TEXT DEFAULT '',           -- 相关诊断
  remark TEXT DEFAULT '',
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
  sale_employee_id INTEGER REFERENCES doctors(id),     -- 销售员工
  sale_employee_name TEXT DEFAULT '',
  service_employee_id INTEGER REFERENCES doctors(id), -- 服务员工（业绩归属）
  service_employee_name TEXT DEFAULT '',
  remark TEXT DEFAULT '',
  created_at TEXT DEFAULT (datetime('now','localtime'))
);

-- 收费明细
CREATE TABLE IF NOT EXISTS bill_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  bill_id INTEGER NOT NULL REFERENCES bills(id),
  item_type TEXT DEFAULT '诊疗费',     -- 挂号费/诊疗费/药品费/检查费/住院费/寄养费/美容费/其他
  name TEXT DEFAULT '',
  qty INTEGER DEFAULT 1,
  price REAL DEFAULT 0,
  subtotal REAL DEFAULT 0,
  is_member_price INTEGER DEFAULT 0    -- 1 按会员价
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
CREATE INDEX IF NOT EXISTS idx_foster_pet ON foster_records(pet_id);
CREATE INDEX IF NOT EXISTS idx_foster_status ON foster_records(status);
CREATE INDEX IF NOT EXISTS idx_rv_plan ON return_visits(plan_date);
CREATE INDEX IF NOT EXISTS idx_rv_status ON return_visits(status);

-- 会员卡
CREATE TABLE IF NOT EXISTS member_cards (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  card_no TEXT UNIQUE NOT NULL,
  owner_id INTEGER NOT NULL REFERENCES owners(id),
  card_type TEXT DEFAULT '储值卡',      -- 储值卡 / 计次卡
  card_name TEXT DEFAULT '',            -- 卡名（如 金卡、洗澡卡10次）
  balance REAL DEFAULT 0,               -- 储值卡余额（元）
  times_left INTEGER DEFAULT 0,         -- 计次卡剩余次数
  discount REAL DEFAULT 1,              -- 折扣（1=无折扣）
  points INTEGER DEFAULT 0,             -- 积分
  total_recharge REAL DEFAULT 0,        -- 累计充值
  total_consume REAL DEFAULT 0,         -- 累计消费
  status TEXT DEFAULT '正常',           -- 正常 / 停用 / 挂失 / 注销
  remark TEXT DEFAULT '',
  created_at TEXT DEFAULT (datetime('now','localtime'))
);

-- 会员卡充值/办卡记录
CREATE TABLE IF NOT EXISTS card_recharges (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  card_id INTEGER NOT NULL REFERENCES member_cards(id),
  amount REAL DEFAULT 0,
  method TEXT DEFAULT '现金',
  operator TEXT DEFAULT '',
  recharge_date TEXT DEFAULT (date('now','localtime')),
  remark TEXT DEFAULT '',
  created_at TEXT DEFAULT (datetime('now','localtime'))
);

-- 会员卡消费记录（储值扣款 / 计次扣次 / 积分变动）
CREATE TABLE IF NOT EXISTS card_consumes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  card_id INTEGER NOT NULL REFERENCES member_cards(id),
  bill_id INTEGER REFERENCES bills(id),
  kind TEXT DEFAULT '储值扣款',          -- 储值扣款 / 计次扣次 / 积分变动
  amount REAL DEFAULT 0,                -- 金额（扣款/充值积分时用）
  times INTEGER DEFAULT 0,              -- 扣次
  points INTEGER DEFAULT 0,             -- 积分变动（正负）
  consume_date TEXT DEFAULT (date('now','localtime')),
  remark TEXT DEFAULT '',
  created_at TEXT DEFAULT (datetime('now','localtime'))
);

-- 库存单据（采购入库/其他入库/报损/盘点调整）
CREATE TABLE IF NOT EXISTS stock_bills (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  bill_no TEXT UNIQUE NOT NULL,
  bill_type TEXT DEFAULT '采购入库',     -- 采购入库 / 其他入库 / 报损 / 盘点调整
  supplier TEXT DEFAULT '',
  total_amount REAL DEFAULT 0,
  bill_date TEXT DEFAULT (date('now','localtime')),
  operator TEXT DEFAULT '',
  remark TEXT DEFAULT '',
  created_at TEXT DEFAULT (datetime('now','localtime'))
);

-- 库存单据明细
CREATE TABLE IF NOT EXISTS stock_bill_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  bill_id INTEGER NOT NULL REFERENCES stock_bills(id),
  medicine_id INTEGER NOT NULL REFERENCES medicines(id),
  qty INTEGER DEFAULT 0,                -- 入库为正，出库/报损为负
  price REAL DEFAULT 0,
  amount REAL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_cards_owner ON member_cards(owner_id);
CREATE INDEX IF NOT EXISTS idx_card_recharge_card ON card_recharges(card_id);
CREATE INDEX IF NOT EXISTS idx_card_consume_card ON card_consumes(card_id);
CREATE INDEX IF NOT EXISTS idx_stock_bill_date ON stock_bills(bill_date);
CREATE INDEX IF NOT EXISTS idx_stock_items_bill ON stock_bill_items(bill_id);
