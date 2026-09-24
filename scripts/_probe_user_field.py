# -*- coding: utf-8 -*-
"""2023-08 后订单的用户标识字段与金额字段口径确认。"""
import json, pymysql

DB = json.load(open(r"D:/workboddy file/dudu分析/citybike_backup/config/backup_config.json", encoding="utf-8"))
DB.pop("workers", None)
conn = pymysql.connect(**DB)
cur = conn.cursor()

W = "exchange_order_status='success' AND create_time >= UNIX_TIMESTAMP('2025-08-01')*1000"


def show(title, sql):
    print("\n===== %s =====" % title)
    try:
        cur.execute(sql)
        for r in cur.fetchall():
            print("   ", " | ".join("" if v is None else str(v) for v in r))
    except Exception as e:
        print("    ERR:", str(e)[:250])


show("用户标识字段非零计数(近1年 success)",
     "SELECT COUNT(*) total, COUNT(DISTINCT take_user_id) d_take, COUNT(DISTINCT bike_user_id) d_bike, "
     "COUNT(DISTINCT back_user_id) d_back, COUNT(DISTINCT exchange_agreement_id) d_agr, "
     "SUM(CASE WHEN take_user_id>0 THEN 1 ELSE 0 END) nz_take, "
     "SUM(CASE WHEN bike_user_id>0 THEN 1 ELSE 0 END) nz_bike "
     "FROM t_exchange_order WHERE " + W)
show("金额字段量级(近1年 success)",
     "SELECT SUM(real_pay_price)/100 real_pay_yuan, SUM(pay_price)/100 pay_yuan, "
     "SUM(profit_fee)/100 profit_yuan, SUM(use_power_fee) power_fee, "
     "SUM(is_refund) refund_cnt, SUM(is_first_take) first_take "
     "FROM t_exchange_order WHERE " + W)
show("按天聚合样例(近6天, 新口径)",
     "SELECT DATE(FROM_UNIXTIME(create_time/1000)) d, COUNT(*) orders, "
     "COUNT(DISTINCT take_user_id) users, COUNT(DISTINCT site_id) sites, "
     "COUNT(DISTINCT take_exchange_sn) cabs, SUM(real_pay_price)/100 fee, SUM(is_first_take) ft "
     "FROM t_exchange_order WHERE exchange_order_status='success' "
     "AND create_time > (UNIX_TIMESTAMP()-6*86400)*1000 GROUP BY d ORDER BY d DESC")
show("城市排行 Top10(近1年 success)",
     "SELECT COALESCE(NULLIF(sys_city_name,''),'未知') city, COUNT(*) c "
     "FROM t_exchange_order WHERE " + W + " GROUP BY city ORDER BY c DESC LIMIT 10")

conn.close()
print("\nPROBE DONE")
