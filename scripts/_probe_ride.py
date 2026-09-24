# -*- coding: utf-8 -*-
"""探测 t_bike_ride_log：体量 / 时间范围 / ride_data 是否为 GPS 轨迹点。"""
import json, pymysql, time
BASE = r"D:/workboddy file/dudu分析/citybike_backup"
DB = json.load(open(BASE + r"/config/backup_config.json", encoding="utf-8"))
conn = pymysql.connect(host=DB["host"], port=DB["port"], user=DB["user"],
                       password=DB["password"], database=DB["database"],
                       connect_timeout=20, read_timeout=300, charset="utf8mb4")
cur = conn.cursor(pymysql.cursors.DictCursor)

print("=== COUNT(总骑行记录) ===")
t0 = time.time()
try:
    cur.execute("SELECT COUNT(*) c FROM t_bike_ride_log WHERE is_del=0")
    print("  total:", cur.fetchone()["c"], " (%.1fs)" % (time.time() - t0))
except Exception as e:
    print("  COUNT failed:", e)

print("=== 时间范围 (begin_time) ===")
try:
    cur.execute("SELECT MIN(begin_time) mn, MAX(begin_time) mx FROM t_bike_ride_log WHERE is_del=0")
    r = cur.fetchone()
    print("  min:", r["mn"], "max:", r["mx"])
except Exception as e:
    print("  range failed:", e)

print("=== 近 50 条样本（看字段形态）===")
cur.execute("""SELECT id, user_id, bike_id, device_sn, begin_time, end_time,
                      distance, use_time, use_power, ride_speed,
                      trace_id, trace_create_time, partition_date,
                      CHAR_LENGTH(ride_data) rd_len, LEFT(ride_data, 240) rd_head
               FROM t_bike_ride_log WHERE is_del=0
               ORDER BY id DESC LIMIT 50""")
for r in cur.fetchall():
    print(f"  id={r['id']} uid={r['user_id']} bike={r['bike_id']} sn={r['device_sn']} "
          f"beg={r['begin_time']} end={r['end_time']} dist={r['distance']} "
          f"usetime={r['use_time']} speed={r['ride_speed']} trace={r['trace_id']} "
          f"pdate={r['partition_date']} rd_len={r['rd_len']}")
    print("      rd_head:", r["rd_head"])
conn.close()
print("PROBE-DONE")
