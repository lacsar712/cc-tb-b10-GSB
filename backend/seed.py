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
            mark text,
            aroma double precision NOT NULL,
            taste double precision NOT NULL,
            liquor double precision NOT NULL,
            score double precision NOT NULL,
            verdict text NOT NULL,
            note text NOT NULL,
            created_by text NOT NULL
        )"""
    )
    cur.execute("ALTER TABLE cuppings ADD COLUMN IF NOT EXISTS mark text")
    # 唛头样式：前缀汉字段，出口唛头须形如 前缀-四位数字
    cur.execute(
        """CREATE TABLE IF NOT EXISTS mark_style (
            id integer PRIMARY KEY DEFAULT 1 CHECK (id = 1),
            prefix text NOT NULL,
            updated_by text NOT NULL,
            updated_at timestamptz NOT NULL DEFAULT now()
        )"""
    )
    # 唛头流水：只可追加，触发器拒绝事后改写
    cur.execute(
        """CREATE TABLE IF NOT EXISTS mark_ledger (
            id serial PRIMARY KEY,
            mark text NOT NULL,
            cupping_id integer REFERENCES cuppings(id),
            created_by text NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now()
        )"""
    )
    cur.execute(
        """CREATE OR REPLACE FUNCTION mark_ledger_immutable() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION '唛头流水只可追加，不得改写或删除';
        END;
        $$ LANGUAGE plpgsql"""
    )
    cur.execute("DROP TRIGGER IF EXISTS mark_ledger_no_update ON mark_ledger")
    cur.execute(
        """CREATE TRIGGER mark_ledger_no_update BEFORE UPDATE ON mark_ledger
           FOR EACH ROW EXECUTE FUNCTION mark_ledger_immutable()"""
    )
    cur.execute("DROP TRIGGER IF EXISTS mark_ledger_no_delete ON mark_ledger")
    cur.execute(
        """CREATE TRIGGER mark_ledger_no_delete BEFORE DELETE ON mark_ledger
           FOR EACH ROW EXECUTE FUNCTION mark_ledger_immutable()"""
    )
    cur.execute("SELECT COUNT(*) FROM mark_style")
    if cur.fetchone()[0] == 0:
        cur.execute(
            "INSERT INTO mark_style (id, prefix, updated_by) VALUES (1, %s, 'taster')",
            ("茶",),
        )
    cur.execute("SELECT COUNT(*) FROM cuppings")
    if cur.fetchone()[0] == 0:
        for lot, mark, aroma, taste, liquor in (
            ("春茶-A", "茶-1001", 8, 8, 7),
            ("夏茶-C", "茶-1002", 5, 4, 6),
        ):
            verdict, note, score = weigh(aroma, taste, liquor)
            cur.execute(
                """INSERT INTO cuppings (lot, mark, aroma, taste, liquor, score, verdict, note, created_by)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                (lot, mark, aroma, taste, liquor, score, verdict, note, "taster"),
            )
            cupping_id = cur.fetchone()[0]
            cur.execute(
                """INSERT INTO mark_ledger (mark, cupping_id, created_by)
                   VALUES (%s, %s, 'taster')""",
                (mark, cupping_id),
            )
    conn.commit()
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
