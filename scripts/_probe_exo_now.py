# -*- coding: utf-8 -*-
"""连 ADB 实时探针：评估 t_exchange_order 换电订单明细的数据量与可行性（逐段打印，容错）。"""
import json, time, os
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DB = json.load(open(os.path.join(ROOT, "config", "backup_config.json"), encoding="utf-8"))
DB.pop("workers", None)
import pymysql
conn = pymysql.connect(host=DB["host"], port=DB["port"], user=DB["user"], password=DB["password"],
                       database=DB["database"], connect_timeout=15, read_timeout=300, charset="utf8mb4")
cur = conn.cursor()

def q1(sql, *a):
    cur.execute(sql, a); r = cur.fetchone(); return r[0] if r else None

def qall(sql, *a):
    cur.execute(sql, a); return cur.fetchall()

# 1) 总量
total0 = q1("SELECT COUNT(*) FROM t_exchange_order WHERE is_del=0")
total_all = q1("SELECT COUNT(*) FROM t_exchange_order")
print("total_is_del0 =", total0)
print("total_all     =", total_all)

# 2) 单位
s = q1("SELECT create_time FROM t_exchange_order WHERE is_del=0 LIMIT 1")
print("sample_create_time =", s)
if s and s > 1e12:
    div, unit = 1000, "ms"
elif s and s > 1e9:
    div, unit = 1, "s"
else:
    div, unit = 1, "unknown"
print("create_time_unit =", unit, "(div=%d)" % div)

# 3) 状态分布
sts = qall("SELECT order_status, COUNT(*) c FROM t_exchange_order WHERE is_del=0 GROUP BY order_status ORDER BY c DESC")
print("status_dist =", [[a, int(b)] for a, b in sts])

# 4) 按月分布（最近 30 个月）—— 用 replace 注入 div，%% 防 pymysql 误解析
sql_month = "SELECT DATE_FORMAT(FROM_UNIXTIME(create_time/%s),'%%Y-%%m') ym, COUNT(*) c FROM t_exchange_order WHERE is_del=0 GROUP BY ym ORDER BY ym DESC LIMIT 30"
sql_month = sql_month.replace("%s", str(div))
td = qall(sql_month)
print("month_dist =", [[a, int(b)] for a, b in td])

# 5) 最近 N 天
now_ms = int(time.time() * 1000)
def since(days):
    return q1("SELECT COUNT(*) FROM t_exchange_order WHERE is_del=0 AND create_time >= %s", now_ms - days * 86400000)
print("recent_90d  =", since(90))
print("recent_180d =", since(180))
print("recent_365d =", since(365))

# 6) 列数
cur.execute("SELECT * FROM t_exchange_order WHERE is_del=0 LIMIT 1")
print("ncols =", len(cur.description))

conn.close()
print("DONE")
