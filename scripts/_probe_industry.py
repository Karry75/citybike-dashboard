# -*- coding: utf-8 -*-
"""探查 t_site 的 industry / type 字段分布，为网点类型分布图表排版优化提供依据。"""
import json, pymysql, sys

DB = json.load(open(r"D:/workboddy file/dudu分析/citybike_backup/config/backup_config.json", encoding="utf-8"))
DB.pop("workers", None)
conn = pymysql.connect(**DB)
cur = conn.cursor()


def show(title, sql):
    print("\n===== %s =====" % title)
    try:
        cur.execute(sql)
        rows = cur.fetchall()
        for r in rows:
            print("   ", " | ".join("" if v is None else str(v) for v in r))
        print("    (rows=%d)" % len(rows))
    except Exception as e:
        print("    ERR:", str(e)[:200])


show("t_site.industry 分布 (全部)",
     "SELECT COALESCE(NULLIF(industry,''),'<空>') k, COUNT(*) c FROM t_site WHERE is_del=0 "
     "GROUP BY k ORDER BY c DESC")
show("t_site.type 分布",
     "SELECT COALESCE(type,-1) k, COUNT(*) c FROM t_site WHERE is_del=0 GROUP BY k ORDER BY c DESC")
show("t_site 网点状态 audit_progress 分布",
     "SELECT COALESCE(NULLIF(audit_progress,''),'<空>') k, COUNT(*) c FROM t_site WHERE is_del=0 "
     "GROUP BY k ORDER BY c DESC")
show("t_exchange_order 按天聚合 样例(最近5天)",
     "SELECT DATE(FROM_UNIXTIME(create_time/1000)) d, COUNT(*) c, "
     "COUNT(DISTINCT consume_user_id) u "
     "FROM t_exchange_order WHERE create_time > (UNIX_TIMESTAMP()-5*86400)*1000 "
     "GROUP BY d ORDER BY d DESC")
show("t_exchange_order order_status 枚举",
     "SELECT order_status, COUNT(*) c FROM t_exchange_order GROUP BY order_status ORDER BY c DESC LIMIT 20")

conn.close()
print("\nPROBE DONE")
