import pymysql, json
CONFIG = {
    "host": "db.example.com",
    "port": 3306, "user": "citybike_pro", "password":"***",
    "database": "sharing-citybike-pro", "connect_timeout": 12, "read_timeout": 30, "charset": "utf8mb4",
}
conn = pymysql.connect(**CONFIG); cur = conn.cursor()
for t in ["t_exchange_order", "t_bike_battery_bind_log", "t_device_online_log"]:
    cur.execute(f"SELECT MIN(create_time), MAX(create_time), MIN(update_time), MAX(update_time) FROM `{t}`")
    mn_c, mx_c, mn_u, mx_u = cur.fetchone()
    print(t, "create_min", mn_c, "create_max", mx_c, "update_max", mx_u)
    # heuristic unit
    for v in (mx_c, mx_u):
        if v:
            print("   -> digits", len(str(v)), "unit", "ms" if v > 1e12 else ("s" if v > 1e9 else "unknown"))
conn.close()
