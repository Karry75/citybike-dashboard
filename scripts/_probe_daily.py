# -*- coding: utf-8 -*-
"""确认订单按天聚合口径：字段名、时间范围、success 口径下的日均量级。"""
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


show("t_exchange_order 字段清单", "SHOW COLUMNS FROM t_exchange_order")
show("success 订单时间范围",
     "SELECT MIN(DATE(FROM_UNIXTIME(create_time/1000))), MAX(DATE(FROM_UNIXTIME(create_time/1000))), COUNT(*) "
     "FROM t_exchange_order WHERE order_status='success'")
show("success 按天(最近8天)",
     "SELECT DATE(FROM_UNIXTIME(create_time/1000)) d, COUNT(*) orders, "
     "COUNT(DISTINCT consume_user_id) users, COUNT(DISTINCT site_id) sites, COUNT(DISTINCT device_sn) cabs "
     "FROM t_exchange_order WHERE order_status='success' "
     "AND create_time > (UNIX_TIMESTAMP()-8*86400)*1000 GROUP BY d ORDER BY d DESC")
show("success 按月(最近14月)",
     "SELECT DATE_FORMAT(FROM_UNIXTIME(create_time/1000),'%Y-%m') m, COUNT(*) orders, "
     "COUNT(DISTINCT consume_user_id) users "
     "FROM t_exchange_order WHERE order_status='success' "
     "AND create_time > (UNIX_TIMESTAMP()-430*86400)*1000 GROUP BY m ORDER BY m DESC")
show("t_site 字段清单(找类型/行业相关)", "SHOW COLUMNS FROM t_site")

conn.close()
print("\nPROBE DONE")
