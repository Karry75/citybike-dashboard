# -*- coding: utf-8 -*-
"""看 ride_data 完整内容 + 搜 trace/gps/point 表。"""
import json, pymysql
BASE = r"D:/workboddy file/dudu分析/citybike_backup"
DB = json.load(open(BASE + r"/config/backup_config.json", encoding="utf-8"))
conn = pymysql.connect(host=DB["host"], port=DB["port"], user=DB["user"],
                       password=DB["password"], database=DB["database"],
                       connect_timeout=20, read_timeout=300, charset="utf8mb4")
cur = conn.cursor(pymysql.cursors.DictCursor)

print("=== 1 行完整 ride_data ===")
cur.execute("""SELECT ride_data FROM t_bike_ride_log
               WHERE is_del=0 AND CHAR_LENGTH(ride_data)>400
               ORDER BY id DESC LIMIT 1""")
row = cur.fetchone()
print(json.dumps(json.loads(row["ride_data"]), ensure_ascii=False, indent=1)[:1600])

print("\n=== 搜 trace/gps/point 相关表 ===")
cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema=%s", (DB["database"],))
tabs = [r[0] for r in cur.fetchall()]
hits = [t for t in tabs if any(k in t.lower() for k in ("trace","gps","point","track","locus","route","path"))]
for t in hits:
    print("  TABLE:", t)
    try:
        cur.execute(f"SELECT COUNT(*) c FROM `{t}`")
        print("     rows:", cur.fetchone()["c"])
    except Exception as e:
        print("     count err:", e)
conn.close()
print("PROBE2-DONE")
