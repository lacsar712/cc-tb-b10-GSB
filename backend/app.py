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


def get_style(cur):
    cur.execute("SELECT prefix, updated_by, updated_at FROM mark_style WHERE id = 1")
    return cur.fetchone()


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
        style = get_style(cur)
    return render_template(
        "home.html",
        rows=rows,
        can_write=session.get("role") == "writer",
        style=style,
    )


@app.route("/marks", methods=["GET", "POST"])
@login_required
def marks():
    error = ""
    notice = ""
    if request.method == "POST":
        if session.get("role") != "writer":
            return ("只读账号不可修改唛头样式", 403)
        prefix = request.form.get("prefix", "").strip()
        if not valid_prefix(prefix):
            error = "前缀须为一个或多个汉字"
        else:
            with db() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """UPDATE mark_style SET prefix = %s, updated_by = %s,
                       updated_at = now() WHERE id = 1""",
                    (prefix, session["user"]),
                )
                conn.commit()
            notice = "样式已更新，仅约束此后提交的唛头"
    with db() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        style = get_style(cur)
        cur.execute("SELECT * FROM mark_ledger ORDER BY id DESC")
        ledger = cur.fetchall()
    return render_template(
        "marks.html",
        style=style,
        ledger=ledger,
        can_write=session.get("role") == "writer",
        error=error,
        notice=notice,
    )


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
        style = get_style(cur)
        if not mark or not mark_matches(mark, style["prefix"]):
            return (f"唛头不符合当前样式：{style['prefix']}-四位数字", 400)
        verdict, note, score = weigh(aroma, taste, liquor)
        cur.execute(
            """INSERT INTO cuppings (lot, mark, aroma, taste, liquor, score, verdict, note, created_by)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
            (lot, mark, aroma, taste, liquor, score, verdict, note, session["user"]),
        )
        row = cur.fetchone()
        cur.execute(
            """INSERT INTO mark_ledger (mark, cupping_id, created_by)
               VALUES (%s, %s, %s)""",
            (mark, row["id"], session["user"]),
        )
        conn.commit()
    if request.headers.get("HX-Request"):
        return render_template("_row.html", row=row)
    return redirect(url_for("home"))
