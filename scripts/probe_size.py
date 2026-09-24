import pymysql, time, shutil, os, json

CONFIG = {
    "host": "db.example.com",
    "port": 3306,
    "user": "citybike_pro",
    "password":"***",
    "database": "sharing-citybike-pro",
    "connect_timeout": 12,
    "read_timeout": 60,
    "charset": "utf8mb4",
}

# Disk headroom on D:
d = shutil.disk_usage("D:/")
info = {
    "disk_total_gb": round(d.total/1e9, 1),
    "disk_free_gb": round(d.free/1e9, 1),
    "disk_used_gb": round(d.used/1e9, 1),
}

conn = pymysql.connect(**CONFIG)
cur = conn.cursor()

# Throughput test on a wide big table
SAMPLE = 200000
t0 = time.time()
cur.execute(f"SELECT * FROM `t_exchange_order` LIMIT {SAMPLE}")
n = 0
for _ in cur.fetchall():
    n += 1
t1 = time.time()
elapsed = t1 - t0
rate = n / elapsed if elapsed else 0
info["sample_rows"] = n
info["sample_seconds"] = round(elapsed, 2)
info["rows_per_sec"] = round(rate, 1)
# estimate full table (11M) time at this rate
est_total = 10_986_536
info["est_full_exchange_order_min"] = round(est_total / rate / 60, 1) if rate else None

# total row estimate across tables from saved schema report
try:
    with open("D:/workboddy file/dudu分析/citybike_backup/data/schema_report.json", encoding="utf-8") as f:
        rep = json.load(f)
    total_rows = sum(v.get("rows", 0) for v in rep.values())
    info["total_tables"] = len(rep)
    info["total_rows_all_tables"] = total_rows
    info["est_full_export_hours_at_sample_rate"] = round(total_rows / rate / 3600, 1) if rate else None
except Exception as e:
    info["schema_read_err"] = str(e)

print(json.dumps(info, ensure_ascii=False, indent=2))
conn.close()
