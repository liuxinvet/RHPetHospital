# -*- coding: utf-8 -*-
"""
仁合宠物医院管理系统 - 主程序
功能模块：登录/用户、仪表盘、宠物主、宠物档案、挂号就诊、电子病历、
处方、药品库存、收费、住院护理、疫苗免疫、医生排班、系统设置
本地 SQLite 数据库，单机运行，浏览器访问。
"""
import os
import sys
from datetime import date, datetime, timedelta
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for, session,
    flash, jsonify, g,
)

import database as db

if getattr(sys, "frozen", False):
    # PyInstaller 打包后：静态资源在 _MEIPASS 临时解包目录，数据文件在 exe 同目录
    RESOURCE_DIR = sys._MEIPASS
    BASE_DIR = os.path.dirname(sys.executable)
else:
    RESOURCE_DIR = os.path.dirname(os.path.abspath(__file__))
    BASE_DIR = RESOURCE_DIR

app = Flask(
    __name__,
    template_folder=os.path.join(RESOURCE_DIR, "templates"),
    static_folder=os.path.join(RESOURCE_DIR, "static"),
)
app.secret_key = "rh-pet-hospital-secret-key-2026"


# ======================= 工具函数 =======================

def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def today_str():
    return date.today().strftime("%Y-%m-%d")


def get_setting(key, default=""):
    conn = db.get_conn()
    try:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default
    finally:
        conn.close()


def next_bill_no(prefix="RH", table="bills", date_col="bill_date", no_col="bill_no"):
    """生成单号：前缀+YYYYMMDD+3位流水（取当日最大号+1，删单后不撞号）"""
    conn = db.get_conn()
    try:
        d = date.today().strftime("%Y%m%d")
        row = conn.execute(
            f"SELECT {no_col} FROM {table} WHERE {date_col}=? ORDER BY {no_col} DESC LIMIT 1",
            (today_str(),),
        ).fetchone()
        last = row[0] if row else ""
        seq = int(last[len(prefix) + 8:]) + 1 if last.startswith(prefix + d) else 1
        return f"{prefix}{d}{seq:03d}"
    finally:
        conn.close()


def next_hos_no():
    return next_bill_no(prefix="ZY", table="hospitalizations", date_col="in_date", no_col="hos_no")


def next_foster_no():
    return next_bill_no(prefix="F", table="foster_records", date_col="in_date", no_col="foster_no")


# ======================= 登录与权限 =======================

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


def role_required(*roles):
    """角色控制：admin 全通；未列出的角色仅允许指定角色"""
    def deco(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not session.get("user_id"):
                return redirect(url_for("login"))
            role = session.get("role", "admin")
            if role == "admin" or role in roles:
                return f(*args, **kwargs)
            flash("权限不足，该操作需要管理员或指定角色", "warning")
            return redirect(request.referrer or url_for("dashboard"))
        return wrapper
    return deco


@app.context_processor
def inject_globals():
    return {
        "hospital_name": get_setting("hospital_name", "仁合宠物医院"),
        "current_user": session.get("real_name") or session.get("username", ""),
        "current_role": session.get("role", ""),
        "today": today_str(),
    }


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        conn = db.get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM users WHERE username=? AND status=1", (username,)
            ).fetchone()
        finally:
            conn.close()
        if row and row["password"] == db.hash_pwd(password):
            session["user_id"] = row["id"]
            session["username"] = row["username"]
            session["real_name"] = row["real_name"]
            session["role"] = row["role"]
            flash(f"欢迎回来，{row['real_name'] or row['username']}", "success")
            return redirect(url_for("dashboard"))
        flash("用户名或密码错误", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ======================= 仪表盘 =======================

@app.route("/")
@login_required
def dashboard():
    conn = db.get_conn()
    try:
        today = today_str()
        stats = {
            "appt_today": conn.execute(
                "SELECT COUNT(*) c FROM appointments WHERE appt_date=? AND status NOT IN ('已取消')",
                (today,),
            ).fetchone()["c"],
            "pet_total": conn.execute("SELECT COUNT(*) c FROM pets").fetchone()["c"],
            "owner_total": conn.execute("SELECT COUNT(*) c FROM owners").fetchone()["c"],
            "income_today": conn.execute(
                "SELECT IFNULL(SUM(paid),0) s FROM bills WHERE bill_date=? AND status='已结清'",
                (today,),
            ).fetchone()["s"],
            "hos_active": conn.execute(
                "SELECT COUNT(*) c FROM hospitalizations WHERE status='住院中'"
            ).fetchone()["c"],
            "pending_appt": conn.execute(
                "SELECT COUNT(*) c FROM appointments WHERE appt_date=? AND status='待诊'",
                (today,),
            ).fetchone()["c"],
        }
        stats["foster_active"] = conn.execute(
            "SELECT COUNT(*) c FROM foster_records WHERE status='寄养中'"
        ).fetchone()["c"]
        stats["rv_today"] = conn.execute(
            "SELECT COUNT(*) c FROM return_visits WHERE status='待回访' AND plan_date<=?",
            (today,),
        ).fetchone()["c"]
        stats["pending_money"] = float(conn.execute(
            "SELECT IFNULL(SUM(total-paid),0) s FROM bills WHERE status='未结清' AND method='挂账'"
        ).fetchone()["s"] or 0)
        stats["card_active"] = conn.execute(
            "SELECT COUNT(*) c FROM member_cards WHERE status='正常'"
        ).fetchone()["c"]
        stats["card_balance"] = float(conn.execute(
            "SELECT IFNULL(SUM(balance),0) s FROM member_cards WHERE status='正常'"
        ).fetchone()["s"] or 0)
        stats["stock_cost"] = float(conn.execute(
            "SELECT IFNULL(SUM(stock*purchase_price),0) s FROM medicines WHERE status=1"
        ).fetchone()["s"] or 0)
        today_appts = conn.execute(
            """SELECT a.*, p.name pet_name, p.species, o.name owner_name, o.phone owner_phone,
                      d.name doctor_name
               FROM appointments a
               JOIN pets p ON p.id=a.pet_id
               JOIN owners o ON o.id=a.owner_id
               LEFT JOIN doctors d ON d.id=a.doctor_id
               WHERE a.appt_date=? ORDER BY a.appt_time, a.id""",
            (today,),
        ).fetchall()

        # 寄养在养
        foster_active = conn.execute(
            "SELECT COUNT(*) c FROM foster_records WHERE status='寄养中'"
        ).fetchone()["c"]
        foster_list = conn.execute(
            """SELECT f.*, p.name pet_name, p.species, o.name owner_name, o.phone owner_phone
               FROM foster_records f JOIN pets p ON p.id=f.pet_id
               JOIN owners o ON o.id=f.owner_id
               WHERE f.status='寄养中' ORDER BY f.in_date LIMIT 8"""
        ).fetchall()

        # 回访提醒：今日到期 + 逾期未回访
        rv_today = conn.execute(
            "SELECT COUNT(*) c FROM return_visits WHERE status='待回访' AND plan_date<=?",
            (today,),
        ).fetchone()["c"]
        rv_list = conn.execute(
            """SELECT r.*, p.name pet_name, o.name owner_name, o.phone owner_phone
               FROM return_visits r JOIN pets p ON p.id=r.pet_id
               JOIN owners o ON o.id=r.owner_id
               WHERE r.status='待回访' AND r.plan_date<=?
               ORDER BY r.plan_date LIMIT 8""",
            (today,),
        ).fetchall()

        # 未结清挂账
        pending_money = conn.execute(
            "SELECT IFNULL(SUM(total-paid),0) s FROM bills WHERE status='未结清' AND method='挂账'"
        ).fetchone()["s"]

        low_stocks = conn.execute(
            """SELECT * FROM medicines WHERE status=1 AND stock<=low_stock
               ORDER BY (low_stock-stock) DESC LIMIT 8"""
        ).fetchall()

        # 疫苗 30 天内到期提醒
        soon = (date.today() + timedelta(days=30)).strftime("%Y-%m-%d")
        vaccine_alerts = conn.execute(
            """SELECT v.*, p.name pet_name, p.species, o.name owner_name, o.phone owner_phone
               FROM vaccines v JOIN pets p ON p.id=v.pet_id
               JOIN owners o ON o.id=p.owner_id
               WHERE v.next_date<>'' AND v.next_date<=? AND v.next_date>=?
               ORDER BY v.next_date LIMIT 8""",
            (soon, today),
        ).fetchall()

        # 近7日营收（柱状）
        days = []
        for i in range(6, -1, -1):
            d = (date.today() - timedelta(days=i)).strftime("%Y-%m-%d")
            amt = conn.execute(
                "SELECT IFNULL(SUM(paid),0) s FROM bills WHERE bill_date=? AND status='已结清'",
                (d,),
            ).fetchone()["s"]
            days.append({"date": d[5:], "amount": float(amt)})
        max_amt = max([d["amount"] for d in days] + [1])
        for d in days:
            d["pct"] = int(d["amount"] / max_amt * 100)

        # 今日值班医生
        on_duty = conn.execute(
            """SELECT d.name, d.title, d.specialty FROM schedules s
               JOIN doctors d ON d.id=s.doctor_id
               WHERE s.work_date=? AND s.shift='白班' AND d.status=1""",
            (today,),
        ).fetchall()
    finally:
        conn.close()
    return render_template(
        "dashboard.html", stats=stats, today_appts=today_appts,
        low_stocks=low_stocks, vaccine_alerts=vaccine_alerts,
        chart_days=days, on_duty=on_duty,
        foster_list=foster_list, rv_list=rv_list,
    )


# ======================= 宠物主管理 =======================

@app.route("/owners")
@login_required
def owners():
    kw = request.args.get("kw", "").strip()
    conn = db.get_conn()
    try:
        if kw:
            rows = conn.execute(
                """SELECT o.*, (SELECT COUNT(*) FROM pets p WHERE p.owner_id=o.id) pet_count
                   FROM owners o
                   WHERE o.name LIKE ? OR o.phone LIKE ? OR o.wechat LIKE ?
                   ORDER BY o.id DESC""",
                (f"%{kw}%", f"%{kw}%", f"%{kw}%"),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT o.*, (SELECT COUNT(*) FROM pets p WHERE p.owner_id=o.id) pet_count
                   FROM owners o ORDER BY o.id DESC"""
            ).fetchall()
    finally:
        conn.close()
    return render_template("owners.html", owners=rows, kw=kw)


@app.route("/owners/new", methods=["GET", "POST"])
@login_required
def owner_new():
    if request.method == "POST":
        conn = db.get_conn()
        try:
            conn.execute(
                "INSERT INTO owners(name,phone,wechat,address,remark) VALUES(?,?,?,?,?)",
                (
                    request.form.get("name", "").strip(),
                    request.form.get("phone", "").strip(),
                    request.form.get("wechat", "").strip(),
                    request.form.get("address", "").strip(),
                    request.form.get("remark", "").strip(),
                ),
            )
            conn.commit()
        finally:
            conn.close()
        flash("宠物主已添加", "success")
        return redirect(url_for("owners"))
    return render_template("owner_form.html", owner=None, title="新增宠物主")


@app.route("/owners/<int:oid>/edit", methods=["GET", "POST"])
@login_required
def owner_edit(oid):
    conn = db.get_conn()
    try:
        if request.method == "POST":
            conn.execute(
                "UPDATE owners SET name=?,phone=?,wechat=?,address=?,remark=? WHERE id=?",
                (
                    request.form.get("name", "").strip(),
                    request.form.get("phone", "").strip(),
                    request.form.get("wechat", "").strip(),
                    request.form.get("address", "").strip(),
                    request.form.get("remark", "").strip(),
                    oid,
                ),
            )
            conn.commit()
            flash("宠物主信息已更新", "success")
            return redirect(url_for("owner_detail", oid=oid))
        owner = conn.execute("SELECT * FROM owners WHERE id=?", (oid,)).fetchone()
    finally:
        conn.close()
    if not owner:
        flash("未找到该宠物主", "warning")
        return redirect(url_for("owners"))
    return render_template("owner_form.html", owner=owner, title="编辑宠物主")


@app.route("/owners/<int:oid>")
@login_required
def owner_detail(oid):
    conn = db.get_conn()
    try:
        owner = conn.execute("SELECT * FROM owners WHERE id=?", (oid,)).fetchone()
        if not owner:
            flash("未找到该宠物主", "warning")
            return redirect(url_for("owners"))
        pets = conn.execute(
            "SELECT * FROM pets WHERE owner_id=? ORDER BY id DESC", (oid,)
        ).fetchall()
        bills = conn.execute(
            "SELECT * FROM bills WHERE owner_id=? ORDER BY id DESC LIMIT 20", (oid,)
        ).fetchall()
    finally:
        conn.close()
    return render_template("owner_detail.html", owner=owner, pets=pets, bills=bills)


@app.route("/owners/<int:oid>/delete", methods=["POST"])
@login_required
@role_required("frontdesk")
def owner_delete(oid):
    conn = db.get_conn()
    try:
        # 有宠物或账单时提示先处理
        n_pets = conn.execute("SELECT COUNT(*) c FROM pets WHERE owner_id=?", (oid,)).fetchone()["c"]
        n_bills = conn.execute("SELECT COUNT(*) c FROM bills WHERE owner_id=?", (oid,)).fetchone()["c"]
        if n_pets or n_bills:
            flash(f"该宠物主名下还有 {n_pets} 只宠物、{n_bills} 张账单，无法删除", "danger")
        else:
            conn.execute("DELETE FROM owners WHERE id=?", (oid,))
            conn.commit()
            flash("宠物主已删除", "success")
    finally:
        conn.close()
    return redirect(url_for("owners"))


# ======================= 宠物档案 =======================

@app.route("/pets")
@login_required
def pets():
    kw = request.args.get("kw", "").strip()
    species = request.args.get("species", "")
    conn = db.get_conn()
    try:
        sql = """SELECT p.*, o.name owner_name, o.phone owner_phone
                 FROM pets p JOIN owners o ON o.id=p.owner_id WHERE 1=1"""
        args = []
        if kw:
            sql += " AND (p.name LIKE ? OR p.breed LIKE ? OR o.name LIKE ? OR o.phone LIKE ?)"
            args += [f"%{kw}%"] * 4
        if species:
            sql += " AND p.species=?"
            args.append(species)
        sql += " ORDER BY p.id DESC"
        rows = conn.execute(sql, args).fetchall()
        species_list = conn.execute("SELECT DISTINCT species FROM pets").fetchall()
    finally:
        conn.close()
    return render_template("pets.html", pets=rows, kw=kw, species=species, species_list=species_list)


@app.route("/pets/new", methods=["GET", "POST"])
@login_required
def pet_new():
    conn = db.get_conn()
    try:
        if request.method == "POST":
            conn.execute(
                """INSERT INTO pets(owner_id,name,species,breed,gender,birthday,weight,
                   color,sterilized,allergy,chip_no,remark) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    int(request.form.get("owner_id", 0)),
                    request.form.get("name", "").strip(),
                    request.form.get("species", "狗"),
                    request.form.get("breed", "").strip(),
                    request.form.get("gender", "公"),
                    request.form.get("birthday", "").strip(),
                    float(request.form.get("weight", 0) or 0),
                    request.form.get("color", "").strip(),
                    1 if request.form.get("sterilized") else 0,
                    request.form.get("allergy", "").strip(),
                    request.form.get("chip_no", "").strip(),
                    request.form.get("remark", "").strip(),
                ),
            )
            conn.commit()
            flash("宠物档案已创建", "success")
            return redirect(url_for("pets"))
        owners_rows = conn.execute("SELECT * FROM owners ORDER BY name").fetchall()
    finally:
        conn.close()
    return render_template("pet_form.html", pet=None, owners=owners_rows, title="新增宠物档案")


@app.route("/pets/<int:pid>/edit", methods=["GET", "POST"])
@login_required
def pet_edit(pid):
    conn = db.get_conn()
    try:
        if request.method == "POST":
            conn.execute(
                """UPDATE pets SET owner_id=?,name=?,species=?,breed=?,gender=?,birthday=?,
                   weight=?,color=?,sterilized=?,allergy=?,chip_no=?,remark=? WHERE id=?""",
                (
                    int(request.form.get("owner_id", 0)),
                    request.form.get("name", "").strip(),
                    request.form.get("species", "狗"),
                    request.form.get("breed", "").strip(),
                    request.form.get("gender", "公"),
                    request.form.get("birthday", "").strip(),
                    float(request.form.get("weight", 0) or 0),
                    request.form.get("color", "").strip(),
                    1 if request.form.get("sterilized") else 0,
                    request.form.get("allergy", "").strip(),
                    request.form.get("chip_no", "").strip(),
                    request.form.get("remark", "").strip(),
                    pid,
                ),
            )
            conn.commit()
            flash("宠物档案已更新", "success")
            return redirect(url_for("pet_detail", pid=pid))
        pet = conn.execute("SELECT * FROM pets WHERE id=?", (pid,)).fetchone()
        owners_rows = conn.execute("SELECT * FROM owners ORDER BY name").fetchall()
    finally:
        conn.close()
    if not pet:
        flash("未找到该宠物", "warning")
        return redirect(url_for("pets"))
    return render_template("pet_form.html", pet=pet, owners=owners_rows, title="编辑宠物档案")


@app.route("/pets/<int:pid>")
@login_required
def pet_detail(pid):
    conn = db.get_conn()
    try:
        pet = conn.execute(
            """SELECT p.*, o.name owner_name, o.phone owner_phone
               FROM pets p JOIN owners o ON o.id=p.owner_id WHERE p.id=?""",
            (pid,),
        ).fetchone()
        if not pet:
            flash("未找到该宠物", "warning")
            return redirect(url_for("pets"))
        records = conn.execute(
            """SELECT r.*, d.name doctor_name FROM medical_records r
               LEFT JOIN doctors d ON d.id=r.doctor_id
               WHERE r.pet_id=? ORDER BY r.record_date DESC, r.id DESC""",
            (pid,),
        ).fetchall()
        prescriptions = conn.execute(
            """SELECT p.*, d.name doctor_name FROM prescriptions p
               LEFT JOIN doctors d ON d.id=p.doctor_id
               WHERE p.pet_id=? ORDER BY p.pres_date DESC, p.id DESC""",
            (pid,),
        ).fetchall()
        vaccines = conn.execute(
            """SELECT v.*, d.name doctor_name FROM vaccines v
               LEFT JOIN doctors d ON d.id=v.doctor_id
               WHERE v.pet_id=? ORDER BY v.vaccine_date DESC, v.id DESC""",
            (pid,),
        ).fetchall()
        hos = conn.execute(
            "SELECT * FROM hospitalizations WHERE pet_id=? ORDER BY id DESC", (pid,)
        ).fetchall()
        appts = conn.execute(
            """SELECT a.*, d.name doctor_name FROM appointments a
               LEFT JOIN doctors d ON d.id=a.doctor_id
               WHERE a.pet_id=? ORDER BY a.appt_date DESC, a.id DESC LIMIT 20""",
            (pid,),
        ).fetchall()
        doctors_rows = conn.execute("SELECT * FROM doctors WHERE status=1 ORDER BY name").fetchall()
        medicines_rows = conn.execute(
            "SELECT * FROM medicines WHERE status=1 ORDER BY name"
        ).fetchall()
    finally:
        conn.close()
    return render_template(
        "pet_detail.html", pet=pet, records=records, prescriptions=prescriptions,
        vaccines=vaccines, hos=hos, appts=appts,
        doctors=doctors_rows, medicines=medicines_rows,
    )


@app.route("/pets/<int:pid>/delete", methods=["POST"])
@login_required
@role_required("frontdesk")
def pet_delete(pid):
    conn = db.get_conn()
    try:
        conn.execute("DELETE FROM pets WHERE id=?", (pid,))
        conn.commit()
        flash("宠物档案已删除", "success")
    finally:
        conn.close()
    return redirect(url_for("pets"))


# ======================= 挂号就诊 =======================

@app.route("/appointments")
@login_required
def appointments():
    d = request.args.get("d", today_str())
    status = request.args.get("status", "")
    conn = db.get_conn()
    try:
        sql = """SELECT a.*, p.name pet_name, p.species, o.name owner_name, o.phone owner_phone,
                        d.name doctor_name
                 FROM appointments a
                 JOIN pets p ON p.id=a.pet_id
                 JOIN owners o ON o.id=a.owner_id
                 LEFT JOIN doctors d ON d.id=a.doctor_id
                 WHERE a.appt_date=? """
        args = [d]
        if status:
            sql += " AND a.status=?"
            args.append(status)
        sql += " ORDER BY a.appt_time, a.id"
        rows = conn.execute(sql, args).fetchall()
        doctors_rows = conn.execute("SELECT * FROM doctors WHERE status=1 ORDER BY name").fetchall()
    finally:
        conn.close()
    return render_template(
        "appointments.html", appts=rows, d=d, status=status,
        doctors=doctors_rows, reg_fee=get_setting("reg_fee", "20"),
    )


@app.route("/appointments/new", methods=["POST"])
@login_required
def appointment_new():
    pet_id = request.form.get("pet_id", "")
    if not pet_id:
        flash("请选择宠物", "warning")
        return redirect(url_for("appointments"))
    conn = db.get_conn()
    try:
        pet = conn.execute("SELECT * FROM pets WHERE id=?", (pet_id,)).fetchone()
        if not pet:
            flash("未找到该宠物", "danger")
            return redirect(url_for("appointments"))
        doctor_id = request.form.get("doctor_id") or None
        fee = float(request.form.get("fee", 0) or get_setting("reg_fee", "20") or 0)
        conn.execute(
            """INSERT INTO appointments(pet_id,owner_id,doctor_id,appt_date,appt_time,
               time_type,type,status,symptom,remark,fee) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (
                int(pet_id), pet["owner_id"], doctor_id,
                request.form.get("appt_date", today_str()),
                request.form.get("appt_time", "").strip(),
                request.form.get("time_type", "上午"),
                request.form.get("type", "门诊"),
                request.form.get("status", "待诊"),
                request.form.get("symptom", "").strip(),
                request.form.get("remark", "").strip(),
                fee,
            ),
        )
        conn.commit()
        flash("挂号成功", "success")
    finally:
        conn.close()
    return redirect(url_for("appointments", d=request.form.get("appt_date", today_str())))


@app.route("/appointments/<int:aid>/status", methods=["POST"])
@login_required
def appointment_status(aid):
    status = request.form.get("status", "")
    conn = db.get_conn()
    try:
        conn.execute("UPDATE appointments SET status=? WHERE id=?", (status, aid))
        conn.commit()
        flash(f"挂号状态已更新为「{status}」", "success")
    finally:
        conn.close()
    return redirect(request.referrer or url_for("appointments"))


@app.route("/appointments/<int:aid>/delete", methods=["POST"])
@login_required
@role_required("frontdesk")
def appointment_delete(aid):
    conn = db.get_conn()
    try:
        conn.execute("DELETE FROM appointments WHERE id=?", (aid,))
        conn.commit()
        flash("挂号记录已删除", "success")
    finally:
        conn.close()
    return redirect(request.referrer or url_for("appointments"))


# ======================= 电子病历 =======================

_RECORD_COLS = [
    "chief_complaint", "examination", "diagnosis", "treatment", "follow_up",
    "temperature", "weight", "breathe", "heartrate", "tongkong", "blood_pressure",
    "chiefnote", "checknote", "carenote", "processnote", "physicalorder",
    "conditionnote", "visitrecord", "surgical_record", "hospitalnode",
    "feeding_method", "feeding_frequency", "food_changes",
    "is_vaccine", "is_deworming", "previous_medical",
    "mentality", "physical_condition_score", "muscle_score", "periodontal_score",
    "eyes", "nose", "ears", "oral_cavity", "muscle", "skins", "nerve", "urology",
    "heart_lung", "abdomen", "lymph_gland",
    "skin_elasticity", "eye_condition", "oral_mucosa", "crt",
    "suspected_illness", "again_visit_num", "open_appointment", "appointment_time",
]


def _record_form_values():
    """从表单提取病历全部字段"""
    vals = {}
    for col in _RECORD_COLS:
        vals[col] = request.form.get(col, "").strip()
    return vals


@app.route("/records")
@login_required
def records():
    kw = request.args.get("kw", "").strip()
    conn = db.get_conn()
    try:
        sql = """SELECT r.*, p.name pet_name, p.species, o.name owner_name,
                        d.name doctor_name
                 FROM medical_records r
                 JOIN pets p ON p.id=r.pet_id
                 JOIN owners o ON o.id=p.owner_id
                 LEFT JOIN doctors d ON d.id=r.doctor_id WHERE 1=1"""
        args = []
        if kw:
            sql += " AND (p.name LIKE ? OR o.name LIKE ? OR r.diagnosis LIKE ?)"
            args += [f"%{kw}%"] * 3
        sql += " ORDER BY r.record_date DESC, r.id DESC LIMIT 200"
        rows = conn.execute(sql, args).fetchall()
    finally:
        conn.close()
    return render_template("records.html", records=rows, kw=kw)


@app.route("/records/new", methods=["GET", "POST"])
@login_required
@role_required("doctor")
def record_new():
    conn = db.get_conn()
    try:
        if request.method == "POST":
            vals = _record_form_values()
            conn.execute(
                """INSERT INTO medical_records(pet_id,appointment_id,doctor_id,record_date,
                   chief_complaint,examination,diagnosis,treatment,follow_up,
                   temperature,weight,breathe,heartrate,tongkong,blood_pressure,
                   chiefnote,checknote,carenote,processnote,physicalorder,
                   conditionnote,visitrecord,surgical_record,hospitalnode,
                   feeding_method,feeding_frequency,food_changes,
                   is_vaccine,is_deworming,previous_medical,
                   mentality,physical_condition_score,muscle_score,periodontal_score,
                   eyes,nose,ears,oral_cavity,muscle,skins,nerve,urology,
                   heart_lung,abdomen,lymph_gland,
                   skin_elasticity,eye_condition,oral_mucosa,crt,
                   suspected_illness,again_visit_num,open_appointment,appointment_time)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    int(request.form.get("pet_id", 0)),
                    request.form.get("appointment_id") or None,
                    request.form.get("doctor_id") or None,
                    request.form.get("record_date", today_str()),
                    *[vals[c] for c in _RECORD_COLS],
                ),
            )
            # 若从预约就诊进入：预约状态置为已完成
            aid = request.form.get("appointment_id")
            if aid:
                conn.execute("UPDATE appointments SET status='已完成' WHERE id=?", (int(aid),))
            conn.commit()
            flash("病历已保存", "success")
            return redirect(url_for("records"))
        pets_rows = conn.execute(
            """SELECT p.id, p.name, p.species, o.name owner_name FROM pets p
               JOIN owners o ON o.id=p.owner_id ORDER BY p.id DESC"""
        ).fetchall()
        doctors_rows = conn.execute("SELECT * FROM doctors WHERE status=1 ORDER BY name").fetchall()
        pid = request.args.get("pid", "")
        aid = request.args.get("aid", "")
    finally:
        conn.close()
    return render_template(
        "record_form.html", pets=pets_rows, doctors=doctors_rows,
        pid=pid, aid=aid, record=None, title="新建病历",
    )


@app.route("/records/<int:rid>/edit", methods=["GET", "POST"])
@login_required
@role_required("doctor")
def record_edit(rid):
    conn = db.get_conn()
    try:
        record = conn.execute("SELECT * FROM medical_records WHERE id=?", (rid,)).fetchone()
        if request.method == "POST":
            vals = _record_form_values()
            set_clause = ", ".join([f"{c}=?" for c in ["record_date"] + _RECORD_COLS])
            conn.execute(
                f"UPDATE medical_records SET {set_clause} WHERE id=?",
                ([request.form.get("record_date", today_str())] + [vals[c] for c in _RECORD_COLS] + [rid]),
            )
            conn.commit()
            flash("病历已更新", "success")
            return redirect(url_for("records"))
    finally:
        conn.close()
    if not record:
        flash("未找到该病历", "warning")
        return redirect(url_for("records"))
    return render_template(
        "record_form.html", record=record, title="编辑病历",
    )


@app.route("/records/<int:rid>/delete", methods=["POST"])
@login_required
@role_required("doctor")
def record_delete(rid):
    conn = db.get_conn()
    try:
        conn.execute("DELETE FROM medical_records WHERE id=?", (rid,))
        conn.commit()
        flash("病历已删除", "success")
    finally:
        conn.close()
    return redirect(request.referrer or url_for("records"))


# ======================= 处方管理 =======================

@app.route("/prescriptions")
@login_required
def prescriptions():
    kw = request.args.get("kw", "").strip()
    conn = db.get_conn()
    try:
        sql = """SELECT pr.*, p.name pet_name, p.species, o.name owner_name,
                        d.name doctor_name
                 FROM prescriptions pr
                 JOIN pets p ON p.id=pr.pet_id
                 JOIN owners o ON o.id=p.owner_id
                 LEFT JOIN doctors d ON d.id=pr.doctor_id WHERE 1=1"""
        args = []
        if kw:
            sql += " AND (p.name LIKE ? OR o.name LIKE ?)"
            args += [f"%{kw}%"] * 2
        sql += " ORDER BY pr.pres_date DESC, pr.id DESC LIMIT 200"
        rows = conn.execute(sql, args).fetchall()
    finally:
        conn.close()
    return render_template("prescriptions.html", prescriptions=rows, kw=kw)


@app.route("/prescriptions/new", methods=["GET", "POST"])
@login_required
@role_required("doctor")
def prescription_new():
    conn = db.get_conn()
    try:
        medicines_rows = conn.execute(
            "SELECT * FROM medicines WHERE status=1 ORDER BY name"
        ).fetchall()
        if request.method == "POST":
            pet_id = int(request.form.get("pet_id", 0))
            doctor_id = request.form.get("doctor_id") or None
            record_id = request.form.get("record_id") or None
            remark = request.form.get("remark", "").strip()
            med_ids = request.form.getlist("med_id[]")
            qtys = request.form.getlist("qty[]")
            dosages = request.form.getlist("dosage[]")
            if not med_ids or not any(m for m in med_ids if m):
                flash("请至少添加一种药品", "warning")
                return redirect(url_for("prescription_new", pid=pet_id))
            cur = conn.execute(
                """INSERT INTO prescriptions(record_id,pet_id,doctor_id,pres_date,remark)
                   VALUES(?,?,?,?,?)""",
                (record_id, pet_id, doctor_id, today_str(), remark),
            )
            pres_id = cur.lastrowid
            total = 0
            for i, mid in enumerate(med_ids):
                if not mid:
                    continue
                med = conn.execute("SELECT * FROM medicines WHERE id=?", (mid,)).fetchone()
                qty = int(qtys[i] or 1)
                price = float(med["sale_price"])
                sub = round(price * qty, 2)
                total += sub
                conn.execute(
                    """INSERT INTO prescription_items(prescription_id,medicine_id,qty,price,dosage,subtotal)
                       VALUES(?,?,?,?,?,?)""",
                    (pres_id, int(mid), qty, price, dosages[i].strip(), sub),
                )
                # 扣减库存
                conn.execute("UPDATE medicines SET stock=stock-? WHERE id=?", (qty, int(mid)))
            conn.execute("UPDATE prescriptions SET total=? WHERE id=?", (round(total, 2), pres_id))
            conn.commit()
            flash("处方已保存并扣减库存", "success")
            return redirect(url_for("prescription_detail", pid=pres_id))
        pets_rows = conn.execute(
            """SELECT p.id, p.name, p.species, o.name owner_name FROM pets p
               JOIN owners o ON o.id=p.owner_id ORDER BY p.id DESC"""
        ).fetchall()
        doctors_rows = conn.execute("SELECT * FROM doctors WHERE status=1 ORDER BY name").fetchall()
        pid = request.args.get("pid", "")
    finally:
        conn.close()
    return render_template(
        "prescription_form.html", pets=pets_rows, doctors=doctors_rows,
        medicines=medicines_rows, pid=pid,
    )


@app.route("/prescriptions/<int:pid>")
@login_required
def prescription_detail(pid):
    conn = db.get_conn()
    try:
        pres = conn.execute(
            """SELECT pr.*, p.name pet_name, p.species, o.name owner_name, o.phone owner_phone,
                      d.name doctor_name
               FROM prescriptions pr
               JOIN pets p ON p.id=pr.pet_id
               JOIN owners o ON o.id=p.owner_id
               LEFT JOIN doctors d ON d.id=pr.doctor_id
               WHERE pr.id=?""",
            (pid,),
        ).fetchone()
        if not pres:
            flash("未找到该处方", "warning")
            return redirect(url_for("prescriptions"))
        items = conn.execute(
            """SELECT i.*, m.name med_name, m.spec, m.unit
               FROM prescription_items i JOIN medicines m ON m.id=i.medicine_id
               WHERE i.prescription_id=?""",
            (pid,),
        ).fetchall()
    finally:
        conn.close()
    return render_template("prescription_detail.html", pres=pres, items=items)


@app.route("/prescriptions/<int:pid>/delete", methods=["POST"])
@login_required
@role_required("doctor")
def prescription_delete(pid):
    conn = db.get_conn()
    try:
        # 回补库存
        for it in conn.execute(
            "SELECT * FROM prescription_items WHERE prescription_id=?", (pid,)
        ).fetchall():
            conn.execute(
                "UPDATE medicines SET stock=stock+? WHERE id=?",
                (it["qty"], it["medicine_id"]),
            )
        conn.execute("DELETE FROM prescription_items WHERE prescription_id=?", (pid,))
        conn.execute("DELETE FROM prescriptions WHERE id=?", (pid,))
        conn.commit()
        flash("处方已删除，库存已回补", "success")
    finally:
        conn.close()
    return redirect(request.referrer or url_for("prescriptions"))


# ======================= 药品库存 =======================

@app.route("/medicines")
@login_required
def medicines():
    kw = request.args.get("kw", "").strip()
    cat = request.args.get("cat", "")
    low = request.args.get("low", "")
    conn = db.get_conn()
    try:
        sql = """SELECT m.*, c.name cat_name FROM medicines m
                 LEFT JOIN medicine_categories c ON c.id=m.category_id WHERE 1=1"""
        args = []
        if kw:
            sql += " AND (m.name LIKE ? OR m.manufacturer LIKE ?)"
            args += [f"%{kw}%"] * 2
        if cat:
            sql += " AND m.category_id=?"
            args.append(cat)
        if low:
            sql += " AND m.status=1 AND m.stock<=m.low_stock"
        sql += " ORDER BY m.name"
        rows = conn.execute(sql, args).fetchall()
        cats = conn.execute("SELECT * FROM medicine_categories ORDER BY name").fetchall()
    finally:
        conn.close()
    return render_template("medicines.html", medicines=rows, cats=cats, kw=kw, cat=cat, low=low)


@app.route("/medicines/new", methods=["GET", "POST"])
@login_required
def medicine_new():
    conn = db.get_conn()
    try:
        if request.method == "POST":
            conn.execute(
                """INSERT INTO medicines(name,category_id,spec,unit,manufacturer,
                   purchase_price,sale_price,stock,low_stock,expiry_date)
                   VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (
                    request.form.get("name", "").strip(),
                    request.form.get("category_id") or None,
                    request.form.get("spec", "").strip(),
                    request.form.get("unit", "盒"),
                    request.form.get("manufacturer", "").strip(),
                    float(request.form.get("purchase_price", 0) or 0),
                    float(request.form.get("sale_price", 0) or 0),
                    int(request.form.get("stock", 0) or 0),
                    int(request.form.get("low_stock", 0) or int(get_setting("low_stock_default", "10") or 10)),
                    request.form.get("expiry_date", "").strip(),
                ),
            )
            conn.commit()
            flash("药品已添加", "success")
            return redirect(url_for("medicines"))
        cats = conn.execute("SELECT * FROM medicine_categories ORDER BY name").fetchall()
    finally:
        conn.close()
    return render_template("medicine_form.html", med=None, cats=cats, title="新增药品")


@app.route("/medicines/<int:mid>/edit", methods=["GET", "POST"])
@login_required
def medicine_edit(mid):
    conn = db.get_conn()
    try:
        med = conn.execute("SELECT * FROM medicines WHERE id=?", (mid,)).fetchone()
        if request.method == "POST":
            conn.execute(
                """UPDATE medicines SET name=?,category_id=?,spec=?,unit=?,manufacturer=?,
                   purchase_price=?,sale_price=?,low_stock=?,expiry_date=?,status=? WHERE id=?""",
                (
                    request.form.get("name", "").strip(),
                    request.form.get("category_id") or None,
                    request.form.get("spec", "").strip(),
                    request.form.get("unit", "盒"),
                    request.form.get("manufacturer", "").strip(),
                    float(request.form.get("purchase_price", 0) or 0),
                    float(request.form.get("sale_price", 0) or 0),
                    int(request.form.get("low_stock", 0) or 10),
                    request.form.get("expiry_date", "").strip(),
                    1 if request.form.get("status") else 0,
                    mid,
                ),
            )
            conn.commit()
            flash("药品信息已更新", "success")
            return redirect(url_for("medicines"))
        cats = conn.execute("SELECT * FROM medicine_categories ORDER BY name").fetchall()
    finally:
        conn.close()
    if not med:
        flash("未找到该药品", "warning")
        return redirect(url_for("medicines"))
    return render_template("medicine_form.html", med=med, cats=cats, title="编辑药品")


@app.route("/medicines/<int:mid>/stock", methods=["POST"])
@login_required
def medicine_stock(mid):
    delta = int(request.form.get("delta", 0) or 0)
    note = request.form.get("note", "").strip()
    if delta == 0:
        flash("数量不能为 0", "warning")
        return redirect(request.referrer or url_for("medicines"))
    conn = db.get_conn()
    try:
        conn.execute("UPDATE medicines SET stock=stock+? WHERE id=?", (delta, mid))
        conn.commit()
        action = "入库" if delta > 0 else "出库"
        flash(f"{action}成功：{abs(delta)}", "success")
    finally:
        conn.close()
    return redirect(request.referrer or url_for("medicines"))


@app.route("/medicines/<int:mid>/delete", methods=["POST"])
@login_required
def medicine_delete(mid):
    conn = db.get_conn()
    try:
        used = conn.execute(
            "SELECT COUNT(*) c FROM prescription_items WHERE medicine_id=?", (mid,)
        ).fetchone()["c"]
        if used:
            flash(f"该药品已被 {used} 条处方引用，不能删除，可改为停用", "danger")
        else:
            conn.execute("DELETE FROM medicines WHERE id=?", (mid,))
            conn.commit()
            flash("药品已删除", "success")
    finally:
        conn.close()
    return redirect(request.referrer or url_for("medicines"))


# ======================= 收费管理 =======================

@app.route("/billing")
@login_required
def billing():
    d = request.args.get("d", "")
    status = request.args.get("status", "")
    conn = db.get_conn()
    try:
        sql = """SELECT b.*, p.name pet_name, o.name owner_name
                 FROM bills b LEFT JOIN pets p ON p.id=b.pet_id
                 LEFT JOIN owners o ON o.id=b.owner_id WHERE 1=1"""
        args = []
        if d:
            sql += " AND b.bill_date=?"
            args.append(d)
        if status:
            sql += " AND b.status=?"
            args.append(status)
        sql += " ORDER BY b.id DESC LIMIT 200"
        rows = conn.execute(sql, args).fetchall()
    finally:
        conn.close()
    return render_template("billing.html", bills=rows, d=d, status=status)


@app.route("/billing/new", methods=["GET", "POST"])
@login_required
def billing_new():
    conn = db.get_conn()
    try:
        if request.method == "POST":
            pet_id = request.form.get("pet_id", "") or None
            owner_id = request.form.get("owner_id", "") or None
            method = request.form.get("method", "现金")
            remark = request.form.get("remark", "").strip()
            sale_emp_id = request.form.get("sale_employee_id", "") or None
            service_emp_id = request.form.get("service_employee_id", "") or None
            card_id = request.form.get("card_id", "") or None
            names = request.form.getlist("item_name[]")
            types = request.form.getlist("item_type[]")
            qtys = request.form.getlist("qty[]")
            prices = request.form.getlist("price[]")
            member_prices = request.form.getlist("member_price[]")
            member_flags = request.form.getlist("is_member_price[]")
            if not any(n for n in names if n.strip()):
                flash("请至少添加一项收费明细", "warning")
                return redirect(url_for("billing_new"))
            bill_no = next_bill_no()
            sale_emp_name = ""
            service_emp_name = ""
            if sale_emp_id:
                row = conn.execute("SELECT name FROM doctors WHERE id=?", (sale_emp_id,)).fetchone()
                sale_emp_name = row["name"] if row else ""
            if service_emp_id:
                row = conn.execute("SELECT name FROM doctors WHERE id=?", (service_emp_id,)).fetchone()
                service_emp_name = row["name"] if row else ""
            cur = conn.execute(
                """INSERT INTO bills(bill_no,owner_id,pet_id,bill_date,method,status,
                   sale_employee_id,sale_employee_name,service_employee_id,service_employee_name,remark)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (bill_no, owner_id, pet_id, today_str(), method, "未结清",
                 sale_emp_id, sale_emp_name, service_emp_id, service_emp_name, remark),
            )
            bill_id = cur.lastrowid
            total = 0
            for i, n in enumerate(names):
                if not n.strip():
                    continue
                qty = int(qtys[i] or 1)
                price = float(prices[i] or 0)
                mflag = 1 if (i < len(member_flags) and member_flags[i]) else 0
                if mflag and i < len(member_prices) and member_prices[i]:
                    price = float(member_prices[i] or 0)
                sub = round(price * qty, 2)
                total += sub
                conn.execute(
                    """INSERT INTO bill_items(bill_id,item_type,name,qty,price,subtotal,is_member_price)
                       VALUES(?,?,?,?,?,?,?)""",
                    (bill_id, types[i] if i < len(types) else "其他", n.strip(), qty, price, sub, mflag),
                )
            conn.execute("UPDATE bills SET total=? WHERE id=?", (round(total, 2), bill_id))
            # 储值卡支付：扣余额、记积分、写消费流水
            if card_id:
                card = conn.execute(
                    "SELECT * FROM member_cards WHERE id=?", (card_id,)
                ).fetchone()
                if not card or card["status"] != "正常" or card["card_type"] != "储值卡":
                    conn.rollback()
                    flash("会员卡不可用或未开通储值", "danger")
                    return redirect(url_for("billing_new"))
                if float(card["balance"] or 0) < total:
                    conn.rollback()
                    flash(f"会员卡余额不足（余额 {card['balance']:.2f}，需 {total:.2f}）", "danger")
                    return redirect(url_for("billing_new"))
                conn.execute(
                    """UPDATE member_cards SET balance=balance-?, points=points+?,
                       total_consume=total_consume+? WHERE id=?""",
                    (total, int(total), total, card_id),
                )
                conn.execute(
                    """INSERT INTO card_consumes(card_id,bill_id,kind,amount,points,consume_date,remark)
                       VALUES(?,?,?,?,?,?,?)""",
                    (card_id, bill_id, "储值扣款", total, int(total), today_str(), f"收费单 {bill_no}"),
                )
                conn.execute(
                    "UPDATE bills SET method='储值卡', paid=?, status='已结清' WHERE id=?",
                    (round(total, 2), bill_id),
                )
            conn.commit()
            flash(f"收费单 {bill_no} 已创建" + ("，储值卡支付成功" if card_id else ""), "success")
            return redirect(url_for("bill_detail", bid=bill_id))
        pets_rows = conn.execute(
            """SELECT p.id, p.name, p.species, o.id owner_id, o.name owner_name
               FROM pets p JOIN owners o ON o.id=p.owner_id ORDER BY p.id DESC"""
        ).fetchall()
        pres_rows = conn.execute(
            """SELECT pr.id, pr.total, p.name pet_name, o.name owner_name, pr.pres_date
               FROM prescriptions pr JOIN pets p ON p.id=pr.pet_id
               JOIN owners o ON o.id=p.owner_id ORDER BY pr.id DESC LIMIT 20"""
        ).fetchall()
        doctors_rows = conn.execute(
            "SELECT id, name, title FROM doctors WHERE status=1 ORDER BY name"
        ).fetchall()
        cards_rows = conn.execute(
            """SELECT c.id, c.card_no, c.card_name, c.balance, c.points, c.status,
                      o.name owner_name
               FROM member_cards c JOIN owners o ON o.id=c.owner_id
               WHERE c.status='正常' AND c.card_type='储值卡'
               ORDER BY c.id DESC LIMIT 50"""
        ).fetchall()
    finally:
        conn.close()
    return render_template("billing_form.html", pets=pets_rows, pres=pres_rows,
                           doctors=doctors_rows, cards=cards_rows)


@app.route("/billing/<int:bid>")
@login_required
def bill_detail(bid):
    conn = db.get_conn()
    try:
        bill = conn.execute(
            """SELECT b.*, p.name pet_name, p.species, o.name owner_name, o.phone owner_phone
               FROM bills b LEFT JOIN pets p ON p.id=b.pet_id
               LEFT JOIN owners o ON o.id=b.owner_id WHERE b.id=?""",
            (bid,),
        ).fetchone()
        if not bill:
            flash("未找到该收费单", "warning")
            return redirect(url_for("billing"))
        items = conn.execute(
            "SELECT * FROM bill_items WHERE bill_id=? ORDER BY id", (bid,)
        ).fetchall()
    finally:
        conn.close()
    return render_template("bill_detail.html", bill=bill, items=items)


@app.route("/billing/<int:bid>/pay", methods=["POST"])
@login_required
def bill_pay(bid):
    conn = db.get_conn()
    try:
        bill = conn.execute("SELECT * FROM bills WHERE id=?", (bid,)).fetchone()
        if not bill:
            flash("未找到该收费单", "danger")
            return redirect(url_for("billing"))
        paid = float(request.form.get("paid", bill["total"]) or bill["total"])
        method = request.form.get("method", bill["method"] or "现金")
        status = "已结清" if paid >= bill["total"] else "未结清"
        conn.execute(
            "UPDATE bills SET paid=?, method=?, status=? WHERE id=?",
            (paid, method, status, bid),
        )
        conn.commit()
        flash("收款成功", "success")
    finally:
        conn.close()
    return redirect(url_for("bill_detail", bid=bid))


@app.route("/billing/<int:bid>/refund", methods=["POST"])
@login_required
@role_required("frontdesk")
def bill_refund(bid):
    conn = db.get_conn()
    try:
        conn.execute("UPDATE bills SET status='已退款', paid=0 WHERE id=?", (bid,))
        conn.commit()
        flash("已退款", "success")
    finally:
        conn.close()
    return redirect(url_for("bill_detail", bid=bid))


@app.route("/billing/<int:bid>/delete", methods=["POST"])
@login_required
@role_required("frontdesk")
def bill_delete(bid):
    conn = db.get_conn()
    try:
        conn.execute("DELETE FROM bill_items WHERE bill_id=?", (bid,))
        conn.execute("DELETE FROM bills WHERE id=?", (bid,))
        conn.commit()
        flash("收费单已删除", "success")
    finally:
        conn.close()
    return redirect(url_for("billing"))


@app.route("/api/prescription/<int:pid>")
@login_required
def api_prescription(pid):
    """处方转收费：返回处方明细供收费单带入"""
    conn = db.get_conn()
    try:
        pres = conn.execute(
            """SELECT pr.*, p.id pet_id, p.name pet_name, p.owner_id owner_id,
                      o.name owner_name
               FROM prescriptions pr JOIN pets p ON p.id=pr.pet_id
               JOIN owners o ON o.id=p.owner_id WHERE pr.id=?""",
            (pid,),
        ).fetchone()
        if not pres:
            return jsonify({"ok": False, "msg": "处方不存在"})
        items = [
            {
                "item_type": "药品费",
                "name": f"{it['med_name']}",
                "qty": it["qty"],
                "price": it["price"],
                "subtotal": it["subtotal"],
            }
            for it in conn.execute(
                """SELECT i.*, m.name med_name FROM prescription_items i
                   JOIN medicines m ON m.id=i.medicine_id WHERE i.prescription_id=?""",
                (pid,),
            ).fetchall()
        ]
        return jsonify({
            "ok": True,
            "pet_id": pres["pet_id"], "pet_name": pres["pet_name"],
            "owner_id": pres["owner_id"], "owner_name": pres["owner_name"],
            "items": items, "total": pres["total"],
        })
    finally:
        conn.close()


# ======================= 住院管理 =======================

@app.route("/hospitalizations")
@login_required
def hospitalizations():
    status = request.args.get("status", "")
    conn = db.get_conn()
    try:
        sql = """SELECT h.*, p.name pet_name, p.species, o.name owner_name, o.phone owner_phone
                 FROM hospitalizations h JOIN pets p ON p.id=h.pet_id
                 JOIN owners o ON o.id=p.owner_id WHERE 1=1"""
        args = []
        if status:
            sql += " AND h.status=?"
            args.append(status)
        sql += " ORDER BY h.id DESC"
        rows = conn.execute(sql, args).fetchall()
    finally:
        conn.close()
    return render_template("hospitalizations.html", hos=rows, status=status)


@app.route("/hospitalizations/new", methods=["GET", "POST"])
@login_required
def hospitalization_new():
    conn = db.get_conn()
    try:
        if request.method == "POST":
            pet_id = int(request.form.get("pet_id", 0))
            conn.execute(
                """INSERT INTO hospitalizations(hos_no,pet_id,room,in_date,daily_fee,reason,remark)
                   VALUES(?,?,?,?,?,?,?)""",
                (
                    next_hos_no(),
                    pet_id,
                    request.form.get("room", "").strip(),
                    request.form.get("in_date", today_str()),
                    float(request.form.get("daily_fee", 0) or 0),
                    request.form.get("reason", "").strip(),
                    request.form.get("remark", "").strip(),
                ),
            )
            conn.commit()
            flash("已办理住院", "success")
            return redirect(url_for("hospitalizations"))
        pets_rows = conn.execute(
            """SELECT p.id, p.name, p.species, o.name owner_name FROM pets p
               JOIN owners o ON o.id=p.owner_id ORDER BY p.id DESC"""
        ).fetchall()
    finally:
        conn.close()
    return render_template("hospitalization_form.html", pets=pets_rows)


@app.route("/hospitalizations/<int:hid>")
@login_required
def hospitalization_detail(hid):
    conn = db.get_conn()
    try:
        h = conn.execute(
            """SELECT h.*, p.name pet_name, p.species, o.name owner_name, o.phone owner_phone
               FROM hospitalizations h JOIN pets p ON p.id=h.pet_id
               JOIN owners o ON o.id=p.owner_id WHERE h.id=?""",
            (hid,),
        ).fetchone()
        if not h:
            flash("未找到该住院记录", "warning")
            return redirect(url_for("hospitalizations"))
        nursings = conn.execute(
            "SELECT * FROM nursing_records WHERE hospitalization_id=? ORDER BY id DESC",
            (hid,),
        ).fetchall()
    finally:
        conn.close()
    return render_template("hospitalization_detail.html", h=h, nursings=nursings)


@app.route("/hospitalizations/<int:hid>/nursing", methods=["POST"])
@login_required
def nursing_add(hid):
    conn = db.get_conn()
    try:
        conn.execute(
            """INSERT INTO nursing_records(hospitalization_id,content,temperature,appetite,staff)
               VALUES(?,?,?,?,?)""",
            (
                hid,
                request.form.get("content", "").strip(),
                float(request.form.get("temperature", 0) or 0),
                request.form.get("appetite", "").strip(),
                request.form.get("staff", "").strip(),
            ),
        )
        conn.commit()
        flash("护理记录已添加", "success")
    finally:
        conn.close()
    return redirect(url_for("hospitalization_detail", hid=hid))


@app.route("/hospitalizations/<int:hid>/discharge", methods=["POST"])
@login_required
def hospitalization_discharge(hid):
    conn = db.get_conn()
    try:
        h = conn.execute(
            """SELECT h.*, p.owner_id owner_id FROM hospitalizations h
               JOIN pets p ON p.id=h.pet_id WHERE h.id=?""",
            (hid,),
        ).fetchone()
        if not h:
            flash("未找到该住院记录", "danger")
            return redirect(url_for("hospitalizations"))
        out_date = request.form.get("out_date", today_str())
        # 计算住院天数与费用
        days = max(1, (datetime.strptime(out_date, "%Y-%m-%d") -
                       datetime.strptime(h["in_date"], "%Y-%m-%d")).days + 1)
        fee_total = round(days * float(h["daily_fee"]), 2)
        conn.execute(
            "UPDATE hospitalizations SET status='已出院', out_date=? WHERE id=?",
            (out_date, hid),
        )
        # 自动生成收费单
        bill_no = next_bill_no()
        cur = conn.execute(
            """INSERT INTO bills(bill_no,owner_id,pet_id,bill_date,method,status,remark,total)
               VALUES(?,?,?,?,?,?,?,?)""",
            (
                bill_no, h["owner_id"], h["pet_id"], today_str(), "现金", "未结清",
                f"住院费（{h['in_date']} 至 {out_date}，共 {days} 天）", fee_total,
            ),
        )
        bid = cur.lastrowid
        conn.execute(
            """INSERT INTO bill_items(bill_id,item_type,name,qty,price,subtotal)
               VALUES(?,?,?,?,?,?)""",
            (bid, "住院费", f"住院护理费（{days}天）", days, float(h["daily_fee"]), fee_total),
        )
        conn.commit()
        flash(f"已出院，共 {days} 天，住院费 {fee_total} 元，已生成收费单 {bill_no}", "success")
        return redirect(url_for("bill_detail", bid=bid))
    finally:
        conn.close()


@app.route("/hospitalizations/<int:hid>/delete", methods=["POST"])
@login_required
def hospitalization_delete(hid):
    conn = db.get_conn()
    try:
        conn.execute("DELETE FROM nursing_records WHERE hospitalization_id=?", (hid,))
        conn.execute("DELETE FROM hospitalizations WHERE id=?", (hid,))
        conn.commit()
        flash("住院记录已删除", "success")
    finally:
        conn.close()
    return redirect(url_for("hospitalizations"))


# ======================= 疫苗免疫 =======================

@app.route("/vaccines/new", methods=["POST"])
@login_required
def vaccine_new():
    pet_id = request.form.get("pet_id", "")
    if not pet_id:
        flash("请选择宠物", "warning")
        return redirect(request.referrer or url_for("pets"))
    conn = db.get_conn()
    try:
        conn.execute(
            """INSERT INTO vaccines(pet_id,vaccine_name,dose,vaccine_date,next_date,doctor_id,remark)
               VALUES(?,?,?,?,?,?,?)""",
            (
                int(pet_id),
                request.form.get("vaccine_name", "").strip(),
                int(request.form.get("dose", 1) or 1),
                request.form.get("vaccine_date", today_str()),
                request.form.get("next_date", "").strip(),
                request.form.get("doctor_id") or None,
                request.form.get("remark", "").strip(),
            ),
        )
        conn.commit()
        flash("疫苗记录已保存", "success")
    finally:
        conn.close()
    return redirect(url_for("pet_detail", pid=pet_id))


# ======================= 医生与排班 =======================

@app.route("/doctors")
@login_required
def doctors():
    conn = db.get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM doctors ORDER BY status DESC, id"
        ).fetchall()
        # 本周排班
        week_start = date.today() - timedelta(days=date.today().weekday())
        week_dates = [(week_start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
        weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        week = list(zip(week_dates, weekdays))
        sched_rows = conn.execute(
            """SELECT s.*, d.name doctor_name FROM schedules s
               JOIN doctors d ON d.id=s.doctor_id
               WHERE s.work_date BETWEEN ? AND ? ORDER BY s.work_date, s.doctor_id""",
            (week_dates[0], week_dates[6]),
        ).fetchall()
    finally:
        conn.close()
    return render_template("doctors.html", doctors=rows, week=week, sched=sched_rows)


@app.route("/doctors/new", methods=["POST"])
@login_required
def doctor_new():
    conn = db.get_conn()
    try:
        conn.execute(
            "INSERT INTO doctors(name,title,specialty,phone,commission_rate) VALUES(?,?,?,?,?)",
            (
                request.form.get("name", "").strip(),
                request.form.get("title", "").strip(),
                request.form.get("specialty", "").strip(),
                request.form.get("phone", "").strip(),
                float(request.form.get("commission_rate", 0) or 0),
            ),
        )
        conn.commit()
        flash("医生已添加", "success")
    finally:
        conn.close()
    return redirect(url_for("doctors"))


@app.route("/doctors/<int:did>/edit", methods=["POST"])
@login_required
def doctor_edit(did):
    conn = db.get_conn()
    try:
        conn.execute(
            "UPDATE doctors SET name=?,title=?,specialty=?,phone=?,commission_rate=?,status=? WHERE id=?",
            (
                request.form.get("name", "").strip(),
                request.form.get("title", "").strip(),
                request.form.get("specialty", "").strip(),
                request.form.get("phone", "").strip(),
                float(request.form.get("commission_rate", 0) or 0),
                1 if request.form.get("status") else 0,
                did,
            ),
        )
        conn.commit()
        flash("医生信息已更新", "success")
    finally:
        conn.close()
    return redirect(url_for("doctors"))


@app.route("/schedules/new", methods=["POST"])
@login_required
def schedule_new():
    doctor_id = request.form.get("doctor_id", "")
    work_date = request.form.get("work_date", "")
    shift = request.form.get("shift", "白班")
    if not doctor_id or not work_date:
        flash("请选择医生和日期", "warning")
        return redirect(url_for("doctors"))
    conn = db.get_conn()
    try:
        exists = conn.execute(
            "SELECT COUNT(*) c FROM schedules WHERE doctor_id=? AND work_date=? AND shift=?",
            (doctor_id, work_date, shift),
        ).fetchone()["c"]
        if exists:
            flash("该排班已存在", "warning")
        else:
            conn.execute(
                "INSERT INTO schedules(doctor_id,work_date,shift) VALUES(?,?,?)",
                (doctor_id, work_date, shift),
            )
            conn.commit()
            flash("排班已添加", "success")
    finally:
        conn.close()
    return redirect(url_for("doctors"))


@app.route("/schedules/<int:sid>/delete", methods=["POST"])
@login_required
def schedule_delete(sid):
    conn = db.get_conn()
    try:
        conn.execute("DELETE FROM schedules WHERE id=?", (sid,))
        conn.commit()
        flash("排班已删除", "success")
    finally:
        conn.close()
    return redirect(url_for("doctors"))


# ======================= 系统设置 =======================

@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if request.method == "POST":
        form = {
            "hospital_name": request.form.get("hospital_name", "").strip(),
            "hospital_phone": request.form.get("hospital_phone", "").strip(),
            "hospital_address": request.form.get("hospital_address", "").strip(),
            "reg_fee": request.form.get("reg_fee", "20").strip(),
            "low_stock_default": request.form.get("low_stock_default", "10").strip(),
            "welcome_msg": request.form.get("welcome_msg", "").strip(),
        }
        conn = db.get_conn()
        try:
            for k, v in form.items():
                conn.execute(
                    "INSERT INTO settings(key,value) VALUES(?,?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (k, v),
                )
            # 修改密码
            old_pwd = request.form.get("old_pwd", "")
            new_pwd = request.form.get("new_pwd", "")
            if old_pwd and new_pwd:
                uid = session.get("user_id")
                user = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
                if user and user["password"] == db.hash_pwd(old_pwd):
                    conn.execute(
                        "UPDATE users SET password=? WHERE id=?",
                        (db.hash_pwd(new_pwd), uid),
                    )
                    flash("密码已修改", "success")
                else:
                    flash("原密码错误，密码未修改", "danger")
            conn.commit()
        finally:
            conn.close()
        flash("设置已保存", "success")
        return redirect(url_for("settings"))
    conn = db.get_conn()
    try:
        rows = conn.execute("SELECT * FROM settings").fetchall()
        settings_map = {r["key"]: r["value"] for r in rows}
        users = conn.execute("SELECT id,username,real_name,role,status,created_at FROM users").fetchall()
    finally:
        conn.close()
    return render_template("settings.html", s=settings_map, users=users)


@app.route("/settings/users/new", methods=["POST"])
@login_required
def user_new():
    username = request.form.get("username", "").strip()
    if not username:
        flash("请输入用户名", "warning")
        return redirect(url_for("settings"))
    conn = db.get_conn()
    try:
        exists = conn.execute("SELECT COUNT(*) c FROM users WHERE username=?", (username,)).fetchone()["c"]
        if exists:
            flash("用户名已存在", "danger")
        else:
            conn.execute(
                "INSERT INTO users(username,password,real_name,role) VALUES(?,?,?,?)",
                (username, db.hash_pwd(request.form.get("password", "123456")),
                 request.form.get("real_name", "").strip(),
                 request.form.get("role", "frontdesk")),
            )
            conn.commit()
            flash("用户已创建", "success")
    finally:
        conn.close()
    return redirect(url_for("settings"))


@app.route("/settings/users/<int:uid>/toggle", methods=["POST"])
@login_required
def user_toggle(uid):
    if uid == session.get("user_id"):
        flash("不能停用自己", "warning")
        return redirect(url_for("settings"))
    conn = db.get_conn()
    try:
        conn.execute("UPDATE users SET status=1-status WHERE id=?", (uid,))
        conn.commit()
        flash("用户状态已切换", "success")
    finally:
        conn.close()
    return redirect(url_for("settings"))


# ======================= 寄养管理 =======================

@app.route("/fosters")
@login_required
def fosters():
    status = request.args.get("status", "")
    conn = db.get_conn()
    try:
        sql = """SELECT f.*, p.name pet_name, p.species, p.gender, o.name owner_name, o.phone owner_phone,
                        (julianday(date('now','localtime')) - julianday(f.in_date)) + 1 AS stay_days
                 FROM foster_records f JOIN pets p ON p.id=f.pet_id
                 JOIN owners o ON o.id=f.owner_id WHERE 1=1"""
        args = []
        if status:
            sql += " AND f.status=?"
            args.append(status)
        sql += " ORDER BY f.status='寄养中' DESC, f.in_date DESC LIMIT 200"
        rows = conn.execute(sql, args).fetchall()
        doctors_rows = conn.execute("SELECT * FROM doctors WHERE status=1 ORDER BY name").fetchall()
        pets_rows = conn.execute(
            """SELECT p.id, p.name, p.species, o.id owner_id, o.name owner_name
               FROM pets p JOIN owners o ON o.id=p.owner_id
               WHERE p.id NOT IN (SELECT pet_id FROM foster_records WHERE status='寄养中')
               ORDER BY p.id DESC"""
        ).fetchall()
    finally:
        conn.close()
    return render_template("fosters.html", fosters=rows, status=status,
                           doctors=doctors_rows, pets=pets_rows,
                           today=today_str())


@app.route("/fosters/new", methods=["POST"])
@login_required
def foster_new():
    pet_id = request.form.get("pet_id", "")
    if not pet_id:
        flash("请选择宠物", "warning")
        return redirect(url_for("fosters"))
    conn = db.get_conn()
    try:
        pet = conn.execute("SELECT * FROM pets WHERE id=?", (pet_id,)).fetchone()
        if not pet:
            flash("未找到该宠物", "danger")
            return redirect(url_for("fosters"))
        daily = float(request.form.get("daily_fee", 0) or 0)
        deposit = float(request.form.get("deposit", 0) or 0)
        conn.execute(
            """INSERT INTO foster_records(foster_no,pet_id,owner_id,in_date,daily_fee,deposit,reason,status,remark)
               VALUES(?,?,?,?,?,?,?,?,?)""",
            (next_foster_no(), int(pet_id), pet["owner_id"],
             request.form.get("in_date", today_str()), daily, deposit,
             request.form.get("reason", "").strip(), "寄养中",
             request.form.get("remark", "").strip()),
        )
        conn.commit()
        flash("寄养登记成功", "success")
    finally:
        conn.close()
    return redirect(url_for("fosters"))


@app.route("/fosters/<int:fid>/finish", methods=["POST"])
@login_required
def foster_finish(fid):
    """结束寄养：按在养天数结算费用，并可一键生成收费单"""
    conn = db.get_conn()
    try:
        foster = conn.execute("SELECT * FROM foster_records WHERE id=?", (fid,)).fetchone()
        if not foster:
            flash("未找到寄养记录", "danger")
            return redirect(url_for("fosters"))
        if foster["status"] != "寄养中":
            flash("该记录已结束", "warning")
            return redirect(url_for("fosters"))
        out_date = request.form.get("out_date", today_str())
        days = int((date.fromisoformat(out_date) - date.fromisoformat(foster["in_date"])).days) + 1
        if days < 1:
            days = 1
        total = round(days * foster["daily_fee"], 2)
        to_bill = request.form.get("to_bill", "1") == "1"
        conn.execute(
            "UPDATE foster_records SET out_date=?, total_fee=?, status='已结束' WHERE id=?",
            (out_date, total, fid),
        )
        if to_bill and total > 0:
            bill_no = next_bill_no()
            cur = conn.execute(
                """INSERT INTO bills(bill_no,owner_id,pet_id,bill_date,method,status,remark)
                   VALUES(?,?,?,?,?,?,?)""",
                (bill_no, foster["owner_id"], foster["pet_id"], today_str(), "现金", "未结清",
                 f"寄养结算 {foster['foster_no']} {days}天"),
            )
            bill_id = cur.lastrowid
            conn.execute(
                """INSERT INTO bill_items(bill_id,item_type,name,qty,price,subtotal)
                   VALUES(?,?,?,?,?,?)""",
                (bill_id, "寄养费", f"寄养 {days} 天", 1, total, total),
            )
            conn.execute("UPDATE bills SET total=? WHERE id=?", (total, bill_id))
            conn.commit()
            flash(f"寄养已结束，结算 {total} 元，收费单已生成", "success")
            return redirect(url_for("bill_detail", bid=bill_id))
        conn.commit()
        flash(f"寄养已结束，结算 {total} 元", "success")
    finally:
        conn.close()
    return redirect(url_for("fosters"))


@app.route("/fosters/<int:fid>/delete", methods=["POST"])
@login_required
@role_required("frontdesk")
def foster_delete(fid):
    conn = db.get_conn()
    try:
        conn.execute("DELETE FROM foster_records WHERE id=?", (fid,))
        conn.commit()
        flash("寄养记录已删除", "success")
    finally:
        conn.close()
    return redirect(request.referrer or url_for("fosters"))


# ======================= 回访管理 =======================

@app.route("/return_visits")
@login_required
def return_visits():
    status = request.args.get("status", "")
    conn = db.get_conn()
    try:
        sql = """SELECT r.*, p.name pet_name, p.species, o.name owner_name, o.phone owner_phone,
                        d.name doctor_name
                 FROM return_visits r JOIN pets p ON p.id=r.pet_id
                 JOIN owners o ON o.id=r.owner_id
                 LEFT JOIN doctors d ON d.id=r.main_employee_id WHERE 1=1"""
        args = []
        if status:
            sql += " AND r.status=?"
            args.append(status)
        sql += " ORDER BY r.status='待回访' DESC, r.plan_date LIMIT 300"
        rows = conn.execute(sql, args).fetchall()
        pets_rows = conn.execute(
            """SELECT p.id, p.name, p.species, o.id owner_id, o.name owner_name, o.phone
               FROM pets p JOIN owners o ON o.id=p.owner_id ORDER BY p.id DESC LIMIT 100"""
        ).fetchall()
        doctors_rows = conn.execute("SELECT * FROM doctors WHERE status=1 ORDER BY name").fetchall()
    finally:
        conn.close()
    return render_template("return_visits.html", visits=rows, status=status,
                           pets=pets_rows, doctors=doctors_rows,
                           today=today_str())


@app.route("/return_visits/new", methods=["POST"])
@login_required
def return_visit_new():
    pet_id = request.form.get("pet_id", "")
    if not pet_id:
        flash("请选择宠物", "warning")
        return redirect(url_for("return_visits"))
    conn = db.get_conn()
    try:
        pet = conn.execute("SELECT * FROM pets WHERE id=?", (pet_id,)).fetchone()
        if not pet:
            flash("未找到该宠物", "danger")
            return redirect(url_for("return_visits"))
        conn.execute(
            """INSERT INTO return_visits(pet_id,owner_id,record_id,plan_date,visit_type,
               status,main_employee_id,diagnosis,remark)
               VALUES(?,?,?,?,?,?,?,?,?)""",
            (int(pet_id), pet["owner_id"],
             request.form.get("record_id") or None,
             request.form.get("plan_date", today_str()),
             request.form.get("visit_type", "电话"),
             request.form.get("status", "待回访"),
             request.form.get("main_employee_id") or None,
             request.form.get("diagnosis", "").strip(),
             request.form.get("remark", "").strip()),
        )
        conn.commit()
        flash("回访计划已登记", "success")
    finally:
        conn.close()
    return redirect(url_for("return_visits"))


@app.route("/return_visits/<int:vid>/done", methods=["POST"])
@login_required
def return_visit_done(vid):
    conn = db.get_conn()
    try:
        conn.execute(
            """UPDATE return_visits SET status='已回访', actual_date=?, visit_result=?
               WHERE id=?""",
            (request.form.get("actual_date", today_str()),
             request.form.get("visit_result", "").strip(), vid),
        )
        conn.commit()
        flash("回访已完成", "success")
    finally:
        conn.close()
    return redirect(url_for("return_visits"))


@app.route("/return_visits/<int:vid>/skip", methods=["POST"])
@login_required
def return_visit_skip(vid):
    conn = db.get_conn()
    try:
        conn.execute("UPDATE return_visits SET status='无需回访' WHERE id=?", (vid,))
        conn.commit()
        flash("已标记无需回访", "success")
    finally:
        conn.close()
    return redirect(url_for("return_visits"))


@app.route("/return_visits/<int:vid>/delete", methods=["POST"])
@login_required
@role_required("frontdesk")
def return_visit_delete(vid):
    conn = db.get_conn()
    try:
        conn.execute("DELETE FROM return_visits WHERE id=?", (vid,))
        conn.commit()
        flash("回访记录已删除", "success")
    finally:
        conn.close()
    return redirect(request.referrer or url_for("return_visits"))


# ======================= 会员卡 =======================

def next_card_no():
    prefix = "MC" + date.today().strftime("%Y%m%d")
    conn = db.get_conn()
    try:
        row = conn.execute(
            "SELECT card_no FROM member_cards WHERE card_no LIKE ? ORDER BY card_no DESC LIMIT 1",
            (prefix + "%",),
        ).fetchone()
        last = row["card_no"] if row else ""
        seq = int(last[len(prefix):]) + 1 if last.startswith(prefix) else 1
        return f"{prefix}{seq:04d}"
    finally:
        conn.close()


@app.route("/cards")
@login_required
def cards():
    kw = request.args.get("kw", "").strip()
    status = request.args.get("status", "")
    conn = db.get_conn()
    try:
        sql = """SELECT c.*, o.name owner_name, o.phone owner_phone
                 FROM member_cards c JOIN owners o ON o.id=c.owner_id WHERE 1=1"""
        args = []
        if kw:
            sql += " AND (c.card_no LIKE ? OR c.card_name LIKE ? OR o.name LIKE ? OR o.phone LIKE ?)"
            args += [f"%{kw}%"] * 4
        if status:
            sql += " AND c.status=?"
            args.append(status)
        sql += " ORDER BY c.id DESC LIMIT 200"
        rows = conn.execute(sql, args).fetchall()
        active = conn.execute(
            "SELECT COUNT(*) c FROM member_cards WHERE status='正常'"
        ).fetchone()["c"]
        total_balance = conn.execute(
            "SELECT IFNULL(SUM(balance),0) s FROM member_cards WHERE status='正常'"
        ).fetchone()["s"]
        month_recharge = conn.execute(
            """SELECT IFNULL(SUM(amount),0) s FROM card_recharges
               WHERE strftime('%Y-%m', recharge_date)=strftime('%Y-%m','now','localtime')"""
        ).fetchone()["s"]
    finally:
        conn.close()
    return render_template("cards.html", cards=rows, kw=kw, status=status,
                           active=active, total_balance=total_balance,
                           month_recharge=month_recharge)


@app.route("/cards/new", methods=["GET", "POST"])
@login_required
@role_required("frontdesk")
def card_new():
    conn = db.get_conn()
    try:
        if request.method == "POST":
            owner_id = request.form.get("owner_id", "")
            card_type = request.form.get("card_type", "储值卡")
            card_name = request.form.get("card_name", "").strip()
            discount = float(request.form.get("discount", 1) or 1)
            remark = request.form.get("remark", "").strip()
            if not owner_id:
                flash("请选择宠物主", "warning")
                return redirect(url_for("card_new"))
            card_no = next_card_no()
            cur = conn.execute(
                """INSERT INTO member_cards(card_no,owner_id,card_type,card_name,discount,remark)
                   VALUES(?,?,?,?,?,?)""",
                (card_no, owner_id, card_type, card_name, discount, remark),
            )
            cid = cur.lastrowid
            if card_type == "储值卡":
                amount = float(request.form.get("amount", 0) or 0)
                if amount > 0:
                    conn.execute(
                        """UPDATE member_cards SET balance=balance+?, points=points+?,
                           total_recharge=total_recharge+? WHERE id=?""",
                        (amount, int(amount), amount, cid),
                    )
                    conn.execute(
                        """INSERT INTO card_recharges(card_id,amount,method,operator,remark)
                           VALUES(?,?,?,?,?)""",
                        (cid, amount, "现金", session.get("real_name", ""), "开卡充值"),
                    )
            else:
                times = int(request.form.get("times", 0) or 0)
                if times > 0:
                    conn.execute(
                        "UPDATE member_cards SET times_left=times_left+? WHERE id=?",
                        (times, cid),
                    )
            conn.commit()
            flash(f"会员卡 {card_no} 开卡成功", "success")
            return redirect(url_for("card_detail", cid=cid))
        owners_rows = conn.execute(
            "SELECT id, name, phone FROM owners ORDER BY name"
        ).fetchall()
    finally:
        conn.close()
    return render_template("card_form.html", owners=owners_rows)


@app.route("/cards/<int:cid>")
@login_required
def card_detail(cid):
    conn = db.get_conn()
    try:
        card = conn.execute(
            """SELECT c.*, o.name owner_name, o.phone owner_phone
               FROM member_cards c JOIN owners o ON o.id=c.owner_id WHERE c.id=?""",
            (cid,),
        ).fetchone()
        if not card:
            flash("未找到该会员卡", "warning")
            return redirect(url_for("cards"))
        recharges = conn.execute(
            "SELECT * FROM card_recharges WHERE card_id=? ORDER BY id DESC LIMIT 100",
            (cid,),
        ).fetchall()
        consumes = conn.execute(
            "SELECT * FROM card_consumes WHERE card_id=? ORDER BY id DESC LIMIT 100",
            (cid,),
        ).fetchall()
    finally:
        conn.close()
    return render_template("card_detail.html", card=card, recharges=recharges,
                           consumes=consumes)


@app.route("/cards/<int:cid>/recharge", methods=["POST"])
@login_required
@role_required("frontdesk")
def card_recharge(cid):
    conn = db.get_conn()
    try:
        card = conn.execute("SELECT * FROM member_cards WHERE id=?", (cid,)).fetchone()
        if not card:
            flash("未找到该会员卡", "danger")
            return redirect(url_for("cards"))
        amount = float(request.form.get("amount", 0) or 0)
        method = request.form.get("method", "现金")
        if amount <= 0:
            flash("充值金额需大于 0", "warning")
            return redirect(url_for("card_detail", cid=cid))
        conn.execute(
            """UPDATE member_cards SET balance=balance+?, points=points+?,
               total_recharge=total_recharge+? WHERE id=?""",
            (amount, int(amount), amount, cid),
        )
        conn.execute(
            """INSERT INTO card_recharges(card_id,amount,method,operator,remark)
               VALUES(?,?,?,?,?)""",
            (cid, amount, method, session.get("real_name", ""),
             request.form.get("remark", "").strip()),
        )
        conn.commit()
        flash(f"充值 {amount:.2f} 元成功", "success")
    finally:
        conn.close()
    return redirect(url_for("card_detail", cid=cid))


@app.route("/cards/<int:cid>/consume", methods=["POST"])
@login_required
@role_required("frontdesk")
def card_consume(cid):
    conn = db.get_conn()
    try:
        card = conn.execute("SELECT * FROM member_cards WHERE id=?", (cid,)).fetchone()
        if not card:
            flash("未找到该会员卡", "danger")
            return redirect(url_for("cards"))
        kind = request.form.get("kind", "")
        if kind == "扣次":
            times = int(request.form.get("times", 0) or 0)
            if times <= 0:
                flash("扣除次数需大于 0", "warning")
                return redirect(url_for("card_detail", cid=cid))
            if times > card["times_left"]:
                flash("卡内剩余次数不足", "danger")
                return redirect(url_for("card_detail", cid=cid))
            conn.execute(
                "UPDATE member_cards SET times_left=times_left-? WHERE id=?",
                (times, cid),
            )
            conn.execute(
                """INSERT INTO card_consumes(card_id,kind,times,consume_date,remark)
                   VALUES(?,?,?,?,?)""",
                (cid, kind, times, today_str(), request.form.get("remark", "").strip()),
            )
        else:
            amount = float(request.form.get("amount", 0) or 0)
            if amount <= 0:
                flash("扣款金额需大于 0", "warning")
                return redirect(url_for("card_detail", cid=cid))
            if amount > card["balance"]:
                flash("卡内余额不足", "danger")
                return redirect(url_for("card_detail", cid=cid))
            conn.execute(
                """UPDATE member_cards SET balance=balance-?, total_consume=total_consume+?
                   WHERE id=?""",
                (amount, amount, cid),
            )
            conn.execute(
                """INSERT INTO card_consumes(card_id,kind,amount,consume_date,remark)
                   VALUES(?,?,?,?,?)""",
                (cid, kind, amount, today_str(), request.form.get("remark", "").strip()),
            )
        conn.commit()
        flash("操作成功", "success")
    finally:
        conn.close()
    return redirect(url_for("card_detail", cid=cid))


@app.route("/cards/<int:cid>/toggle", methods=["POST"])
@login_required
@role_required("frontdesk")
def card_toggle(cid):
    conn = db.get_conn()
    try:
        card = conn.execute("SELECT * FROM member_cards WHERE id=?", (cid,)).fetchone()
        if not card:
            flash("未找到该会员卡", "danger")
            return redirect(url_for("cards"))
        new_status = "停用" if card["status"] == "正常" else "正常"
        conn.execute("UPDATE member_cards SET status=? WHERE id=?", (new_status, cid))
        conn.commit()
        flash(f"会员卡已{new_status}", "success")
    finally:
        conn.close()
    return redirect(url_for("card_detail", cid=cid))


@app.route("/cards/<int:cid>/delete", methods=["POST"])
@login_required
@role_required("frontdesk")
def card_delete(cid):
    conn = db.get_conn()
    try:
        conn.execute("DELETE FROM card_consumes WHERE card_id=?", (cid,))
        conn.execute("DELETE FROM card_recharges WHERE card_id=?", (cid,))
        conn.execute("DELETE FROM member_cards WHERE id=?", (cid,))
        conn.commit()
        flash("会员卡已删除", "success")
    finally:
        conn.close()
    return redirect(url_for("cards"))


# ======================= 库存单据（采购入库/出库/报损） =======================

def next_stock_no():
    prefix = "ST" + date.today().strftime("%Y%m%d")
    conn = db.get_conn()
    try:
        row = conn.execute(
            "SELECT bill_no FROM stock_bills WHERE bill_no LIKE ? ORDER BY bill_no DESC LIMIT 1",
            (prefix + "%",),
        ).fetchone()
        last = row["bill_no"] if row else ""
        seq = int(last[len(prefix):]) + 1 if last.startswith(prefix) else 1
        return f"{prefix}{seq:04d}"
    finally:
        conn.close()


@app.route("/stock_bills")
@login_required
def stock_bills():
    btype = request.args.get("type", "")
    conn = db.get_conn()
    try:
        sql = "SELECT * FROM stock_bills WHERE 1=1"
        args = []
        if btype:
            sql += " AND bill_type=?"
            args.append(btype)
        sql += " ORDER BY id DESC LIMIT 200"
        rows = conn.execute(sql, args).fetchall()
    finally:
        conn.close()
    return render_template("stock_bills.html", bills=rows, btype=btype)


@app.route("/stock_bills/new", methods=["GET", "POST"])
@login_required
@role_required("frontdesk")
def stock_bill_new():
    conn = db.get_conn()
    try:
        if request.method == "POST":
            bill_type = request.form.get("bill_type", "采购入库")
            supplier = request.form.get("supplier", "").strip()
            bill_date = request.form.get("bill_date", today_str())
            remark = request.form.get("remark", "").strip()
            mids = request.form.getlist("medicine_id[]")
            qtys = request.form.getlist("qty[]")
            prices = request.form.getlist("price[]")
            items = []
            for i, mid in enumerate(mids):
                if not mid:
                    continue
                qty = int(qtys[i] or 0)
                if qty == 0:
                    continue
                if bill_type in ("采购入库", "其他入库"):
                    eff = qty
                else:
                    eff = -abs(qty)
                price = float(prices[i] or 0)
                items.append((int(mid), eff, price, round(price * abs(qty), 2)))
            if not items:
                flash("请至少添加一条药品明细", "warning")
                return redirect(url_for("stock_bill_new"))
            bill_no = next_stock_no()
            total = sum(it[3] for it in items)
            cur = conn.execute(
                """INSERT INTO stock_bills(bill_no,bill_type,supplier,total_amount,bill_date,operator,remark)
                   VALUES(?,?,?,?,?,?,?)""",
                (bill_no, bill_type, supplier, total, bill_date,
                 session.get("real_name", ""), remark),
            )
            bid = cur.lastrowid
            for mid, eff, price, amount in items:
                conn.execute(
                    """INSERT INTO stock_bill_items(bill_id,medicine_id,qty,price,amount)
                       VALUES(?,?,?,?,?)""",
                    (bid, mid, eff, price, amount),
                )
                conn.execute(
                    "UPDATE medicines SET stock=MAX(0, stock+?) WHERE id=?", (eff, mid)
                )
            conn.commit()
            flash(f"库存单据 {bill_no} 已保存，库存已更新", "success")
            return redirect(url_for("stock_bill_detail", bid=bid))
        meds = conn.execute(
            "SELECT id, name, spec, unit, sale_price, stock FROM medicines WHERE status=1 ORDER BY name"
        ).fetchall()
        cats = conn.execute("SELECT id, name FROM medicine_categories ORDER BY name").fetchall()
    finally:
        conn.close()
    return render_template("stock_bill_form.html", meds=meds, cats=cats, today=today_str())


@app.route("/stock_bills/<int:bid>")
@login_required
def stock_bill_detail(bid):
    conn = db.get_conn()
    try:
        bill = conn.execute("SELECT * FROM stock_bills WHERE id=?", (bid,)).fetchone()
        if not bill:
            flash("未找到该单据", "warning")
            return redirect(url_for("stock_bills"))
        items = conn.execute(
            """SELECT s.*, m.name med_name, m.spec, m.unit FROM stock_bill_items s
               JOIN medicines m ON m.id=s.medicine_id WHERE s.bill_id=? ORDER BY s.id""",
            (bid,),
        ).fetchall()
    finally:
        conn.close()
    return render_template("stock_bill_detail.html", bill=bill, items=items)


@app.route("/stock_bills/<int:bid>/delete", methods=["POST"])
@login_required
@role_required("frontdesk")
def stock_bill_delete(bid):
    conn = db.get_conn()
    try:
        bill = conn.execute("SELECT * FROM stock_bills WHERE id=?", (bid,)).fetchone()
        if not bill:
            flash("未找到该单据", "danger")
            return redirect(url_for("stock_bills"))
        items = conn.execute(
            "SELECT * FROM stock_bill_items WHERE bill_id=?", (bid,)
        ).fetchall()
        for it in items:
            # 回滚库存：入库单回滚为减，出库/报损单回滚为加
            conn.execute(
                "UPDATE medicines SET stock=MAX(0, stock-?) WHERE id=?", (it["qty"], it["medicine_id"])
            )
        conn.execute("DELETE FROM stock_bill_items WHERE bill_id=?", (bid,))
        conn.execute("DELETE FROM stock_bills WHERE id=?", (bid,))
        conn.commit()
        flash(f"单据 {bill['bill_no']} 已删除，库存已回滚", "success")
    finally:
        conn.close()
    return redirect(url_for("stock_bills"))


# ======================= 库存盘点 =======================

@app.route("/stock_check", methods=["GET", "POST"])
@login_required
@role_required("frontdesk")
def stock_check():
    conn = db.get_conn()
    try:
        if request.method == "POST":
            mids = request.form.getlist("mid[]")
            actuals = request.form.getlist("actual[]")
            diffs = []
            for i, mid in enumerate(mids):
                if not mid:
                    continue
                med = conn.execute("SELECT * FROM medicines WHERE id=?", (mid,)).fetchone()
                if not med:
                    continue
                try:
                    actual = int(actuals[i] or 0)
                except ValueError:
                    actual = 0
                diff = actual - med["stock"]
                if diff != 0:
                    diffs.append((int(mid), diff, med["purchase_price"]))
            if not diffs:
                flash("盘点结果与账面一致，无需调整", "success")
                return redirect(url_for("stock_check"))
            bill_no = next_stock_no()
            total = sum(abs(d[1]) * d[2] for d in diffs)
            cur = conn.execute(
                """INSERT INTO stock_bills(bill_no,bill_type,supplier,total_amount,bill_date,operator,remark)
                   VALUES(?,?,?,?,?,?,?)""",
                (bill_no, "盘点调整", "盘点", round(total, 2), today_str(),
                 session.get("real_name", ""), "库存盘点自动调整"),
            )
            bid = cur.lastrowid
            for mid, diff, price in diffs:
                conn.execute(
                    """INSERT INTO stock_bill_items(bill_id,medicine_id,qty,price,amount)
                       VALUES(?,?,?,?,?)""",
                    (bid, mid, diff, price, round(abs(diff) * price, 2)),
                )
                conn.execute(
                    "UPDATE medicines SET stock=MAX(0, stock+?) WHERE id=?", (diff, mid)
                )
            conn.commit()
            flash(f"盘点完成，差异 {len(diffs)} 项已生成调整单 {bill_no}", "success")
            return redirect(url_for("stock_bill_detail", bid=bid))
        meds = conn.execute(
            """SELECT m.*, c.name cat_name FROM medicines m
               LEFT JOIN medicine_categories c ON c.id=m.category_id
               WHERE m.status=1 ORDER BY m.name"""
        ).fetchall()
        cats = conn.execute("SELECT id, name FROM medicine_categories ORDER BY name").fetchall()
    finally:
        conn.close()
    return render_template("stock_check.html", meds=meds, cats=cats, today=today_str())


# ======================= 经营报表 =======================

@app.route("/reports")
@login_required
def reports():
    view = request.args.get("view", "daily")
    conn = db.get_conn()
    try:
        data = None
        if view == "daily":
            d1 = request.args.get("d1", today_str())
            d2 = request.args.get("d2", today_str())
            rows = conn.execute(
                """SELECT bill_date, method, COUNT(*) cnt, IFNULL(SUM(total),0) total,
                          IFNULL(SUM(paid),0) paid
                   FROM bills WHERE bill_date BETWEEN ? AND ? AND status!='已退款'
                   GROUP BY bill_date, method ORDER BY bill_date, method""",
                (d1, d2),
            ).fetchall()
            summary = {
                "orders": sum(r["cnt"] for r in rows),
                "total": float(sum(r["total"] for r in rows)),
                "paid": float(sum(r["paid"] for r in rows)),
            }
            recharge = conn.execute(
                """SELECT IFNULL(SUM(amount),0) s FROM card_recharges
                   WHERE recharge_date BETWEEN ? AND ?""",
                (d1, d2),
            ).fetchone()["s"]
            data = {"rows": rows, "d1": d1, "d2": d2, "summary": summary,
                    "recharge": float(recharge or 0)}
        elif view == "monthly":
            rows = conn.execute(
                """SELECT strftime('%Y-%m', bill_date) ym, COUNT(*) cnt,
                          IFNULL(SUM(total),0) total, IFNULL(SUM(paid),0) paid
                   FROM bills WHERE status!='已退款'
                   GROUP BY ym ORDER BY ym DESC LIMIT 12"""
            ).fetchall()
            data = {"rows": rows}
        elif view == "pets":
            rows = conn.execute(
                """SELECT p.name pet_name, p.species, o.name owner_name,
                          COUNT(b.id) cnt, IFNULL(SUM(b.total),0) total
                   FROM bills b JOIN pets p ON p.id=b.pet_id
                   JOIN owners o ON o.id=b.owner_id
                   WHERE b.status!='已退款'
                   GROUP BY p.id ORDER BY total DESC LIMIT 30"""
            ).fetchall()
            data = {"rows": rows}
        elif view == "employees":
            rows = conn.execute(
                """SELECT COALESCE(NULLIF(b.sale_employee_name,''), b.service_employee_name) emp,
                          COUNT(*) cnt, IFNULL(SUM(b.total),0) total,
                          IFNULL(SUM(b.total * IFNULL(d.commission_rate,0) / 100.0),0) commission
                   FROM bills b
                   LEFT JOIN doctors d ON d.id=COALESCE(b.sale_employee_id, b.service_employee_id)
                   WHERE b.status!='已退款'
                   GROUP BY emp ORDER BY total DESC LIMIT 30"""
            ).fetchall()
            data = {"rows": rows}
        elif view == "stock":
            rows = conn.execute(
                """SELECT c.name cat_name, COUNT(m.id) cnt,
                          IFNULL(SUM(m.stock),0) stock,
                          IFNULL(SUM(m.stock*m.purchase_price),0) cost_value,
                          SUM(CASE WHEN m.stock<=m.low_stock AND m.status=1 THEN 1 ELSE 0 END) low_cnt
                   FROM medicines m LEFT JOIN medicine_categories c ON c.id=m.category_id
                   GROUP BY c.id ORDER BY cost_value DESC"""
            ).fetchall()
            data = {"rows": rows}
    finally:
        conn.close()
    return render_template("reports.html", view=view, data=data)


# ======================= 启动 =======================

if __name__ == "__main__":
    db.init_db()
    print("=" * 50)
    print("  仁合宠物医院管理系统")
    print("  浏览器访问: http://127.0.0.1:8080")
    print("  默认账号: admin / 123456")
    print("=" * 50)
    app.run(host="127.0.0.1", port=8080, debug=False)
