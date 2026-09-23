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


def next_bill_no(prefix="RH", table="bills", date_col="bill_date"):
    """生成单号：RH+YYYYMMDD+3位流水"""
    conn = db.get_conn()
    try:
        d = date.today().strftime("%Y%m%d")
        row = conn.execute(
            f"SELECT COUNT(*) c FROM {table} WHERE {date_col}=?", (today_str(),)
        ).fetchone()
        return f"{prefix}{d}{row['c'] + 1:03d}"
    finally:
        conn.close()


def next_hos_no():
    return next_bill_no(prefix="ZY", table="hospitalizations", date_col="in_date")


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
               type,status,symptom,fee) VALUES(?,?,?,?,?,?,?,?,?)""",
            (
                int(pet_id), pet["owner_id"], doctor_id,
                request.form.get("appt_date", today_str()),
                request.form.get("appt_time", "").strip(),
                request.form.get("type", "门诊"),
                request.form.get("status", "待诊"),
                request.form.get("symptom", "").strip(),
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
            conn.execute(
                """INSERT INTO medical_records(pet_id,appointment_id,doctor_id,record_date,
                   chief_complaint,examination,diagnosis,treatment,follow_up)
                   VALUES(?,?,?,?,?,?,?,?,?)""",
                (
                    int(request.form.get("pet_id", 0)),
                    request.form.get("appointment_id") or None,
                    request.form.get("doctor_id") or None,
                    request.form.get("record_date", today_str()),
                    request.form.get("chief_complaint", "").strip(),
                    request.form.get("examination", "").strip(),
                    request.form.get("diagnosis", "").strip(),
                    request.form.get("treatment", "").strip(),
                    request.form.get("follow_up", "").strip(),
                ),
            )
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
            conn.execute(
                """UPDATE medical_records SET record_date=?,chief_complaint=?,examination=?,
                   diagnosis=?,treatment=?,follow_up=? WHERE id=?""",
                (
                    request.form.get("record_date", today_str()),
                    request.form.get("chief_complaint", "").strip(),
                    request.form.get("examination", "").strip(),
                    request.form.get("diagnosis", "").strip(),
                    request.form.get("treatment", "").strip(),
                    request.form.get("follow_up", "").strip(),
                    rid,
                ),
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
        "record_edit.html", record=record, title="编辑病历",
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
            names = request.form.getlist("item_name[]")
            types = request.form.getlist("item_type[]")
            qtys = request.form.getlist("qty[]")
            prices = request.form.getlist("price[]")
            if not any(n for n in names if n.strip()):
                flash("请至少添加一项收费明细", "warning")
                return redirect(url_for("billing_new"))
            bill_no = next_bill_no()
            cur = conn.execute(
                """INSERT INTO bills(bill_no,owner_id,pet_id,bill_date,method,status,remark)
                   VALUES(?,?,?,?,?,?,?)""",
                (bill_no, owner_id, pet_id, today_str(), method, "未结清", remark),
            )
            bill_id = cur.lastrowid
            total = 0
            for i, n in enumerate(names):
                if not n.strip():
                    continue
                qty = int(qtys[i] or 1)
                price = float(prices[i] or 0)
                sub = round(price * qty, 2)
                total += sub
                conn.execute(
                    """INSERT INTO bill_items(bill_id,item_type,name,qty,price,subtotal)
                       VALUES(?,?,?,?,?,?)""",
                    (bill_id, types[i] if i < len(types) else "其他", n.strip(), qty, price, sub),
                )
            conn.execute("UPDATE bills SET total=? WHERE id=?", (round(total, 2), bill_id))
            conn.commit()
            flash(f"收费单 {bill_no} 已创建", "success")
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
    finally:
        conn.close()
    return render_template("billing_form.html", pets=pets_rows, pres=pres_rows)


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
            "INSERT INTO doctors(name,title,specialty,phone) VALUES(?,?,?,?)",
            (
                request.form.get("name", "").strip(),
                request.form.get("title", "").strip(),
                request.form.get("specialty", "").strip(),
                request.form.get("phone", "").strip(),
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
            "UPDATE doctors SET name=?,title=?,specialty=?,phone=?,status=? WHERE id=?",
            (
                request.form.get("name", "").strip(),
                request.form.get("title", "").strip(),
                request.form.get("specialty", "").strip(),
                request.form.get("phone", "").strip(),
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


# ======================= 启动 =======================

if __name__ == "__main__":
    db.init_db()
    print("=" * 50)
    print("  仁合宠物医院管理系统")
    print("  浏览器访问: http://127.0.0.1:8080")
    print("  默认账号: admin / 123456")
    print("=" * 50)
    app.run(host="127.0.0.1", port=8080, debug=False)
