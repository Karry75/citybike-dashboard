# -*- coding: utf-8 -*-
import json, os, pymysql
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
cfg=json.load(open(os.path.join(ROOT,"config","backup_config.json"),encoding="utf-8")); cfg.pop("workers",None)
conn=pymysql.connect(host=cfg["host"],port=cfg["port"],user=cfg["user"],password=cfg["password"],database=cfg["database"],connect_timeout=15,read_timeout=600,charset="utf8mb4")
cur=conn.cursor(pymysql.cursors.DictCursor)
pats=["%coupon%","%券%","%redeem%","%convert%","%give%","%procure%","%purchase%","%agency%"]
seen=set()
for p in pats:
    rows=cur.execute("SELECT TABLE_NAME,COLUMN_NAME,COLUMN_TYPE FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME LIKE %s",(p,)) or []
    for r in cur.fetchall():
        t=r["TABLE_NAME"]
        if t not in seen:
            seen.add(t)
print("=== COUPON-RELATED TABLES ===")
for t in sorted(seen):
    print("TABLE:",t)
    cols=cur.execute("SELECT COLUMN_NAME,COLUMN_TYPE FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s ORDER BY ORDINAL_POSITION",(t,)) or []
    cl=cur.fetchall()
    print("   cols:", ", ".join("%s:%s"%(c["COLUMN_NAME"],c["COLUMN_TYPE"]) for c in cl))
    try:
        n=cur.execute("SELECT COUNT(*) c FROM `%s`"%t)
        print("   rows:", cur.fetchone()["c"])
    except Exception as e:
        print("   rows: ERR", str(e)[:80])
conn.close()
