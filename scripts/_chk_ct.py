# -*- coding: utf-8 -*-
import json, time, os
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DB = json.load(open(os.path.join(ROOT, "config", "backup_config.json"), encoding="utf-8"))
DB.pop("workers", None)
import pymysql
conn = pymysql.connect(host=DB["host"], port=DB["port"], user=DB["user"], password=DB["password"],
                       database=DB["database"], connect_timeout=15, read_timeout=300, charset="utf8mb4")
cur = conn.cursor()

def q1(s, *a):
    cur.execute(s, a); r = cur.fetchone(); return r[0] if r else None

def qall(s, *a):
    cur.execute(s, a); return cur.fetchall()

s = q1("SELECT create_time FROM t_exchange_order WHERE is_del=0 LIMIT 1")
print("sample_create_time =", s, type(s))
if isinstance(s, (int, float)):
    if s > 1e12: div, unit = 1000, "ms"
    elif s > 1e9: div, unit = 1, "s"
    else: div, unit = 1, "unknown"
    print("unit =", unit, "div=", div)
    td = qall("SELECT DATE_FORMAT(FROM_UNIXTIME(create_time/" + str(div) + "), %s) ym, COUNT(*) c FROM t_exchange_order WHERE is_del=0 GROUP BY ym ORDER BY ym DESC", '%Y-%m')
    print("month_dist =", [[a, int(b)] for a, b in td])
    now = int(time.time())
    for d in (90, 180, 365):
        print("recent_%dd =" % d, q1("SELECT COUNT(*) FROM t_exchange_order WHERE is_del=0 AND create_time>=%s" % (now - d * 86400)))
else:
    print("create_time is datetime type:", s)
conn.close()
