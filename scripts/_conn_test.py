#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""一次性连通性测试：用 backup.py 里的兜底密码试连，判断该密码是否仍有效。"""
import pymysql, json, os
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
cfg = json.load(open(os.path.join(BASE, "config", "backup_config.json"), encoding="utf-8"))
# 用 backup.py 的兜底密码
PW = "<DB_PASSWORD_FROM_CONFIG>"
print("host:", cfg["host"], "user:", cfg["user"])
print("config password is placeholder:", cfg.get("password") == "YOUR_DB_PASSWORD_HERE")
try:
    conn = pymysql.connect(
        host=cfg["host"], port=cfg.get("port", 3306), user=cfg["user"],
        password=PW, database=cfg["database"],
        connect_timeout=15, read_timeout=60, charset="utf8mb4")
    cur = conn.cursor()
    cur.execute("SELECT 1")
    print("RESULT: CONNECTED with backup.py fallback password")
    cur.execute("SELECT COUNT(*) FROM t_battery_belong_relation WHERE is_del=0")
    print("t_battery_belong_relation rows:", cur.fetchone()[0])
    cur.execute("SELECT belong_type, COUNT(*) c FROM t_battery_belong_relation WHERE is_del=0 GROUP BY belong_type ORDER BY c DESC")
    print("belong_type distribution:")
    for row in cur.fetchall():
        print("  ", row[0], row[1])
    conn.close()
except Exception as e:
    print("RESULT: FAILED ->", type(e).__name__, str(e)[:300])
