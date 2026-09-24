# -*- coding: utf-8 -*-
"""确认电池的城市归属字段。"""
import json, pymysql

DB = json.load(open(r"D:/workboddy file/dudu分析/citybike_backup/config/backup_config.json", encoding="utf-8"))
DB.pop("workers", None)
conn = pymysql.connect(**DB)
cur = conn.cursor()


def show(title, sql):
    print("\n===== %s =====" % title)
    try:
        cur.execute(sql)
        for r in cur.fetchall():
            print("   ", " | ".join("" if v is None else str(v) for v in r))
    except Exception as e:
        print("    ERR:", str(e)[:250])


show("t_battery 字段", "SHOW COLUMNS FROM t_battery")
conn.close()
print("\nPROBE DONE")
