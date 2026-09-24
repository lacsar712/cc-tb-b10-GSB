import os
from functools import wraps

import psycopg2
from flask import Flask, redirect, render_template, request, session, url_for
from psycopg2.extras import RealDictCursor

from rules import mark_matches, valid_prefix, weigh

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "tea-cupping-dev-secret")

ACCOUNTS = {
    "taster": {"password": "tea123456", "role": "writer"},
    "observer": {"password": "look123456", "role": "reader"},
}


def db():
    return psycopg2.connect(os.environ["DATABASE_URL"])


def login_required(fn):
    @wraps(fn)
    def wrap(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        return fn(*args, **kwargs)

    return wrap


@app.get("/health")
def health():
    return {"status": "ok", "service": "tea-blend-cupping"}


@app.route("/login", methods=["GET", "POST"])
def login():
    error = ""
    if request.method == "POST":
        name = request.form.get("username", "").strip()
        account = ACCOUNTS.get(name)
        if not account or account["password"] != request.form.get("password", ""):
            error = "用户名或密码错误"
        else:
            session["user"] = name
            session["role"] = account["role"]
            return redirect(url_for("home"))
    return render_template("login.html", error=error)


@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.get("/")
@login_required
def home():
    with db() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM cuppings ORDER BY id DESC")
        rows = cur.fetchall()
        cur.execute("SELECT prefix FROM mark_style WHERE id = 1")
        style = cur.fetchone()
    prefix = style["prefix"] if style else "茶"
    return render_template(
        "home.html",
        rows=rows,
        prefix=prefix,
        can_write=session.get("role") == "writer",
    )


@app.get("/mark-gate")
@login_required
def mark_gate():
    with db() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM mark_style WHERE id = 1")
        style = cur.fetchone()
        cur.execute(
            """SELECT * FROM mark_log ORDER BY id DESC"""
        )
        logs = cur.fetchall()
    return render_template(
        "mark_gate.html",
        style=style,
        logs=logs,
        can_write=session.get("role") == "writer",
        error=request.args.get("error", ""),
    )


@app.post("/mark-style")
@login_required
def update_mark_style():
    if session.get("role") != "writer":
        return ("仅审评员可修改唛头样式", 403)
    prefix = request.form.get("prefix", "").strip()
    if not valid_prefix(prefix):
        return redirect(url_for("mark_gate", error="前缀须为非空汉字段"))
    with db() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        # 样式只约束之后提交：覆盖当前样式，不触碰流水里的历史记录
        cur.execute(
            """INSERT INTO mark_style (id, prefix, updated_by, updated_at)
               VALUES (1, %s, %s, now())
               ON CONFLICT (id) DO UPDATE
               SET prefix = EXCLUDED.prefix,
                   updated_by = EXCLUDED.updated_by,
                   updated_at = now()""",
            (prefix, session["user"]),
        )
        conn.commit()
    return redirect(url_for("mark_gate"))


@app.post("/cuppings")
@login_required
def create():
    if session.get("role") != "writer":
        return ("仅审评员可提交拼配审评", 403)
    aroma = float(request.form["aroma"])
    taste = float(request.form["taste"])
    liquor = float(request.form["liquor"])
    lot = request.form["lot"].strip()
    mark = request.form.get("mark", "").strip()
    with db() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT prefix FROM mark_style WHERE id = 1")
        style = cur.fetchone()
        prefix = style["prefix"] if style else ""
        if not mark:
            return ("出口唛头为强制项，不得空缺", 400)
        if not mark_matches(mark, prefix):
            return (f"唛头不符合样式：{prefix}-四位数字（半角中划线）", 400)
        verdict, note, score = weigh(aroma, taste, liquor)
        cur.execute(
            """INSERT INTO cuppings (lot, mark, aroma, taste, liquor, score, verdict, note, created_by)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
            (lot, mark, aroma, taste, liquor, score, verdict, note, session["user"]),
        )
        row = cur.fetchone()
        # 唛头落流水：只追加，样式事后变更不回改此记录
        cur.execute(
            """INSERT INTO mark_log (mark, prefix, cupping_id, created_by)
               VALUES (%s,%s,%s,%s)""",
            (mark, prefix, row["id"], session["user"]),
        )
        conn.commit()
    if request.headers.get("HX-Request"):
        return render_template("_row.html", row=row)
    return redirect(url_for("home"))
