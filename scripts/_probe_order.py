import json, pymysql, os
HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.dirname(HERE)
DB=json.load(open(os.path.join(ROOT,"config","backup_config.json"),encoding="utf-8")); DB.pop("workers",None)
NOW=int(__import__("time").time()*1000); D30=NOW-30*86400000
conn=pymysql.connect(host=DB["host"],port=DB["port"],user=DB["user"],password=DB["password"],database=DB["database"],connect_timeout=15,read_timeout=600,charset="utf8mb4")
c=conn.cursor()
def q(s):
    c.execute(s); return c.fetchall()
print("order_status enum (success count by status):")
for r in q("SELECT order_status, COUNT(*) c FROM t_exchange_order WHERE is_del=0 GROUP BY order_status ORDER BY c DESC"):
    print("  ", r)
print("take_battery_time stats (success):")
for r in q("SELECT MIN(take_battery_time),MAX(take_battery_time),SUM(take_battery_time=0),SUM(take_battery_time IS NULL),COUNT(*) FROM t_exchange_order WHERE order_status='success' AND is_del=0"):
    print("  min/max/zero/null/total =", r)
print("create_time stats (success):")
for r in q("SELECT MIN(create_time),MAX(create_time),SUM(create_time=0) FROM t_exchange_order WHERE order_status='success' AND is_del=0"):
    print("  min/max/zero =", r)
print("30d by create_time (success):", q("SELECT COUNT(*) FROM t_exchange_order WHERE order_status='success' AND is_del=0 AND create_time>=%d"%D30))
print("30d by take_battery_time (success):", q("SELECT COUNT(*) FROM t_exchange_order WHERE order_status='success' AND is_del=0 AND take_battery_time>=%d"%D30))
print("sample take_battery_time values:", [r[0] for r in q("SELECT take_battery_time FROM t_exchange_order WHERE order_status='success' AND is_del=0 LIMIT 5")])
conn.close()
