# -*- coding: utf-8 -*-
import json, pymysql, time
DB = json.load(open(r"D:/workboddy file/dudu分析/citybike_backup/config/backup_config.json", encoding="utf-8"))
DB.pop("workers", None)
t0 = time.time()
conn = pymysql.connect(host=DB["host"], port=int(DB.get("port", 3306)),
                       user=DB["user"], password=DB["password"], database=DB["database"],
                       charset="utf8mb4", connect_timeout=30)
cur = conn.cursor()
tables = {
    "协议(t_exchange_agreement)": "SELECT COUNT(*) FROM t_exchange_agreement WHERE is_del=0",
    "押金(t_user_exchange_deposit)": "SELECT COUNT(*) FROM t_user_exchange_deposit WHERE is_del=0",
    "网点(t_site)": "SELECT COUNT(*) FROM t_site WHERE is_del=0",
    "换电柜(t_exchange)": "SELECT COUNT(*) FROM t_exchange WHERE is_del=0",
    "电池(t_battery)": "SELECT COUNT(*) FROM t_battery WHERE is_del=0",
}
for name, sql in tables.items():
    cur.execute(sql)
    n = cur.fetchone()[0]
    print("%-32s : %d 行" % (name, n))
conn.close()
print("elapsed=%.2fs" % (time.time() - t0))
