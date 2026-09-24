import pymysql, json

CONFIG = {
    "host": "db.example.com",
    "port": 3306,
    "user": "citybike_pro",
    "password":"***",
    "database": "sharing-citybike-pro",
    "connect_timeout": 12,
    "read_timeout": 30,
    "charset": "utf8mb4",
}

conn = pymysql.connect(**CONFIG)
cur = conn.cursor()
cur.execute("SHOW TABLES")
tables = [r[0] for r in cur.fetchall()]

report = {}
for t in tables:
    cur.execute(f"SELECT COUNT(*) FROM `{t}`")
    cnt = cur.fetchone()[0]
    cur.execute(f"SHOW FULL COLUMNS FROM `{t}`")
    cols = []
    date_cols = []
    ts_cols = []
    for c in cur.fetchall():
        name, ctype = c[0], c[1]
        cols.append(f"{name}:{ctype}")
        tl = ctype.lower()
        if any(k in tl for k in ("date", "datetime", "timestamp")):
            date_cols.append(name)
        if "bigint" in tl and ("time" in name.lower() or name.lower() in ("create_time","update_time")):
            ts_cols.append(name)
    # candidate incremental column: prefer update_time, else create_time, else any *_time bigint
    inc = None
    for pref in ("update_time", "create_time"):
        if pref in ts_cols:
            inc = pref
            break
    if inc is None and ts_cols:
        inc = ts_cols[0]
    report[t] = {"rows": cnt, "date_cols": date_cols, "ts_cols": ts_cols, "inc_col": inc}

with open("D:/workboddy file/dudu分析/citybike_backup/data/schema_report.json", "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

total = sum(v["rows"] for v in report.values())
big = {k: v["rows"] for k, v in report.items() if v["rows"] >= 1_000_000}
print("TABLES", len(report))
print("TOTAL_ROWS", total)
print("BIG_TABLES(>=1M):", json.dumps(big, ensure_ascii=False))
print("SAVED schema_report.json")
conn.close()
