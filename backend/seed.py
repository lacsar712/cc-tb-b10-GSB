import os
import time

import psycopg2

from rules import weigh


def connect():
    last = None
    for _ in range(30):
        try:
            return psycopg2.connect(os.environ["DATABASE_URL"])
        except psycopg2.OperationalError as exc:
            last = exc
            time.sleep(1)
    raise last


def main():
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """CREATE TABLE IF NOT EXISTS cuppings (
            id serial PRIMARY KEY,
            lot text NOT NULL,
            mark text NOT NULL DEFAULT '',
            aroma double precision NOT NULL,
            taste double precision NOT NULL,
            liquor double precision NOT NULL,
            score double precision NOT NULL,
            verdict text NOT NULL,
            note text NOT NULL,
            created_by text NOT NULL
        )"""
    )
    # 兼容旧数据卷：补齐唛头列
    cur.execute("ALTER TABLE cuppings ADD COLUMN IF NOT EXISTS mark text NOT NULL DEFAULT ''")
    # 唛头样式：单行表，审评员可改前缀，只约束之后的提交
    cur.execute(
        """CREATE TABLE IF NOT EXISTS mark_style (
            id integer PRIMARY KEY DEFAULT 1,
            prefix text NOT NULL,
            updated_by text NOT NULL,
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT mark_style_singleton CHECK (id = 1)
        )"""
    )
    # 唛头流水：只追加，事后改样式不改写早先记录
    cur.execute(
        """CREATE TABLE IF NOT EXISTS mark_log (
            id serial PRIMARY KEY,
            mark text NOT NULL,
            prefix text NOT NULL,
            cupping_id integer REFERENCES cuppings(id),
            created_by text NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now()
        )"""
    )
    cur.execute("SELECT COUNT(*) FROM mark_style")
    if cur.fetchone()[0] == 0:
        cur.execute(
            "INSERT INTO mark_style (id, prefix, updated_by) VALUES (1, %s, 'taster')",
            ("茶",),
        )
    cur.execute("SELECT COUNT(*) FROM cuppings")
    if cur.fetchone()[0] == 0:
        for lot, aroma, taste, liquor in (("春茶-A", 8, 8, 7), ("夏茶-C", 5, 4, 6)):
            verdict, note, score = weigh(aroma, taste, liquor)
            cur.execute(
                """INSERT INTO cuppings (lot, mark, aroma, taste, liquor, score, verdict, note, created_by)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (lot, "", aroma, taste, liquor, score, verdict, note, "taster"),
            )
    conn.commit()
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
