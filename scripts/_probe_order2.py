import json, pymysql, os, time
HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.dirname(HERE)
DB=json.load(open(os.path.join(ROOT,"config","backup_config.json"),encoding="utf-8")); DB.pop("workers",None)
NOW=int(time.time()*1000); D30=NOW-30*86400000
conn=pymysql.connect(host=DB["host"],port=DB["port"],user=DB["user"],password=DB["password"],database=DB["database"],connect_timeout=15,read_timeout=600,charset="utf8mb4")
c=conn.cursor()
def q(s):
    c.execute(s); return c.fetchall()
print("全量状态分布(any time):")
for r in q("SELECT order_status,COUNT(*) c FROM t_exchange_order WHERE is_del=0 GROUP BY order_status ORDER BY c DESC"): print("  ",r)
print("create_time 最新:", q("SELECT MAX(create_time),MIN(create_time) FROM t_exchange_order WHERE is_del=0"))
print("近30天(NOW-30d) 任意状态 订单数:", q("SELECT COUNT(*) FROM t_exchange_order WHERE is_del=0 AND create_time>=%d"%D30))
print("近30天 success 订单数:", q("SELECT COUNT(*) FROM t_exchange_order WHERE is_del=0 AND order_status='success' AND create_time>=%d"%D30))
print("2026年(create>=2026-01-01) 各状态:", [(r[0],r[1]) for r in q("SELECT order_status,COUNT(*) FROM t_exchange_order WHERE is_del=0 AND create_time>=1767225600000 GROUP BY order_status")])
print("全量 success 按网点 top5:", q("SELECT site_name,COUNT(*) c FROM t_exchange_order WHERE is_del=0 AND order_status='success' GROUP BY site_id ORDER BY c DESC LIMIT 5"))
print("全量 任意状态 按网点 top5:", q("SELECT site_name,COUNT(*) c FROM t_exchange_order WHERE is_del=0 GROUP BY site_id ORDER BY c DESC LIMIT 5"))
conn.close()
