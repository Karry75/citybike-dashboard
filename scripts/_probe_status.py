# -*- coding: utf-8 -*-
"""确认 2023-08 之后的订单完成态口径：exchange_order_status vs order_status。"""
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


show("exchange_order_status 枚举 + 时间范围",
     "SELECT COALESCE(NULLIF(exchange_order_status,''),'<空>') k, COUNT(*) c, "
     "MIN(DATE(FROM_UNIXTIME(create_time/1000))) mn, MAX(DATE(FROM_UNIXTIME(create_time/1000))) mx "
     "FROM t_exchange_order GROUP BY k ORDER BY c DESC")
show("order_status x exchange_order_status 交叉",
     "SELECT order_status, COALESCE(NULLIF(exchange_order_status,''),'<空>') eos, COUNT(*) c "
     "FROM t_exchange_order GROUP BY order_status, eos ORDER BY c DESC LIMIT 20")
show("2023-08 之后 order_status 分布",
     "SELECT order_status, COUNT(*) c, MAX(DATE(FROM_UNIXTIME(create_time/1000))) mx "
     "FROM t_exchange_order WHERE create_time >= UNIX_TIMESTAMP('2023-08-12')*1000 "
     "GROUP BY order_status ORDER BY c DESC")
show("exchange_status / take_status 枚举(2023-08后)",
     "SELECT exchange_status, take_status, COUNT(*) c FROM t_exchange_order "
     "WHERE create_time >= UNIX_TIMESTAMP('2023-08-12')*1000 "
     "GROUP BY exchange_status, take_status ORDER BY c DESC LIMIT 15")
show("按月聚合(exchange_order_status=success, 近14月)",
     "SELECT DATE_FORMAT(FROM_UNIXTIME(create_time/1000),'%Y-%m') m, COUNT(*) orders, "
     "COUNT(DISTINCT consume_user_id) users, COUNT(DISTINCT site_id) sites "
     "FROM t_exchange_order WHERE exchange_order_status='success' "
     "AND create_time > (UNIX_TIMESTAMP()-430*86400)*1000 GROUP BY m ORDER BY m DESC")
show("consume_user_id=0 占比(2023-08后)",
     "SELECT CASE WHEN consume_user_id=0 THEN 'zero' ELSE 'real' END k, COUNT(*) c "
     "FROM t_exchange_order WHERE create_time >= UNIX_TIMESTAMP('2023-08-12')*1000 GROUP BY k")

conn.close()
print("\nPROBE DONE")
