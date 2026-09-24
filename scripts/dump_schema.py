# -*- coding: utf-8 -*-
"""Dump full column schema (name/type/comment) for all tables of sharing-citybike-pro."""
import json, pymysql

DB = json.load(open(r"D:/workboddy file/dudu分析/citybike_backup/config/backup_config.json", encoding="utf-8"))
DB.pop("workers", None)

conn = pymysql.connect(
    host=DB["host"], port=DB["port"], user=DB["user"], password=DB["password"],
    database=DB["database"], connect_timeout=15, read_timeout=300, charset="utf8mb4",
)
cur = conn.cursor()

# table comments
cur.execute(
    "SELECT TABLE_NAME, TABLE_COMMENT, TABLE_ROWS FROM information_schema.tables "
    "WHERE table_schema=%s ORDER BY TABLE_NAME", (DB["database"],)
)
tbl_comments = {r[0]: {"comment": r[1], "rows": r[2]} for r in cur.fetchall()}

# columns
cur.execute(
    "SELECT TABLE_NAME, COLUMN_NAME, COLUMN_TYPE, COLUMN_COMMENT, ORDINAL_POSITION "
    "FROM information_schema.columns WHERE table_schema=%s ORDER BY TABLE_NAME, ORDINAL_POSITION",
    (DB["database"],),
)
cols = {}
for t, c, ct, cc, pos in cur.fetchall():
    cols.setdefault(t, []).append({"name": c, "type": ct, "comment": cc, "pos": pos})

out = {"tables": tbl_comments, "columns": cols}
json.dump(out, open(r"D:/workboddy file/dudu分析/citybike_backup/data/full_schema.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
conn.close()
print("TABLES:", len(tbl_comments), "COLUMN_SETS:", len(cols))
print("SAVED data/full_schema.json")
