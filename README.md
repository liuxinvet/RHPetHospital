---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: 81e972de7a8c0aa07b4200ca63e9cf5a_983e1e33b6da11f1b0b2525400638852
    ReservedCode1: 683WU4eifn3oyVg85ANFigKj49ajMM6C1DwZgVEpJZ4/42oZXeMN+SEKY493y2tgKuQXyfdkCNXob0bTllLleHYOMHG66fWP/e6PoqC9yqcyIrH+NJcd+bJl7OA9jC4Hkxl1WXfbSGBsiimXreHXmsrCQVdaVm5Tdacbv4mCBb6V5ZwFfrJoMMXBinc=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: 81e972de7a8c0aa07b4200ca63e9cf5a_983e1e33b6da11f1b0b2525400638852
    ReservedCode2: 683WU4eifn3oyVg85ANFigKj49ajMM6C1DwZgVEpJZ4/42oZXeMN+SEKY493y2tgKuQXyfdkCNXob0bTllLleHYOMHG66fWP/e6PoqC9yqcyIrH+NJcd+bJl7OA9jC4Hkxl1WXfbSGBsiimXreHXmsrCQVdaVm5Tdacbv4mCBb6V5ZwFfrJoMMXBinc=
---

# 仁合宠物医院管理系统

面向宠物医院的本地化管理系统，基于 Flask + SQLite，开箱即用、数据全在本地、无需联网。

## 功能总览

| 模块 | 说明 |
|------|------|
| 仪表盘 | 今日挂号、在院宠物、今日营收、近 7 日营收图、库存预警、疫苗到期提醒、今日值班医生 |
| 宠物主管理 | 客户档案（电话/微信/地址/备注）、按姓名/电话检索、客户名下宠物与消费账单 |
| 宠物档案 | 品种/性别/生日/体重/绝育/过敏史/芯片号，宠物详情页集成挂号、病历、处方、疫苗、住院入口 |
| 挂号就诊 | 按日期/状态筛选，待诊/就诊中/已完成/已取消，支持指定医生与挂号费 |
| 电子病历 | 主诉、检查所见、诊断、治疗方案、复诊建议，支持检索与编辑 |
| 处方管理 | 多药品明细、自动计价、自动扣减库存、用法用量记录 |
| 药品库存 | 分类管理、进销价、库存预警线、入库/出库、有效期、药品停用保护 |
| 收费管理 | 自定义收费项目、从处方一键带入、现金/微信/支付宝/刷卡/储值卡、挂账与收款、退款 |
| 会员卡 | 储值卡/计次卡开卡、充值、扣款、扣次、余额不足拦截、消费积分、停用/删除、消费流水 |
| 库存单据 | 采购入库/报损/盘点调整单据，动态明细行，自动增减库存，单据删除自动回滚库存 |
| 库存盘点 | 按药品录入实盘数量，自动生成差异调整单并同步库存 |
| 经营报表 | 日营业报表、月度趋势、宠物消费榜、员工业绩（含提成率）、库存资产报表 |
| 住院管理 | 房间笼位、每日费用、护理记录（体温/食欲）、出院自动计算费用并生成收费单 |
| 疫苗免疫 | 疫苗名称、剂次、下次接种日期，到期自动提醒 |
| 医生排班 | 医生档案、本周排班表（白班/夜班/休息） |
| 系统设置 | 医院信息、默认挂号费、库存预警线、修改密码、用户账户管理（前台/医生/管理员） |

## 技术栈

- Python 3.8+ / Flask
- SQLite 本地数据库（无需安装数据库服务）
- 原生 HTML/CSS/JS（无前端框架，打开即用）

## 快速开始

### Windows
双击 `start.bat`（或命令行执行 `python app.py`），浏览器访问 http://127.0.0.1:8080

### Linux / macOS
```bash
bash start.sh
# 或
python3 app.py
```

### 默认账号（登录后请在「系统设置」中修改密码）

| 账号 | 密码 | 角色 |
|------|------|------|
| admin | 123456 | 管理员 |
| doctor | 123456 | 医生 |
| front | 123456 | 前台 |

## 目录结构

```
rh_pet_hospital/
├── app.py            # 主程序（全部业务路由）
├── database.py       # 数据库连接与种子数据
├── schema.sql        # 表结构（SQLite）
├── requirements.txt  # 依赖
├── start.sh          # Linux/macOS 一键启动
├── start.bat         # Windows 一键启动
├── templates/        # 页面模板
├── static/           # 样式与前端脚本
└── data/             # 运行时自动生成 hospital.db（本地数据库）
```

## 数据备份

系统全部数据保存在 `data/hospital.db` 单个文件中，直接复制该文件即可完成备份；恢复时将文件放回 `data/` 目录即可。
*（内容由AI生成，仅供参考）*
