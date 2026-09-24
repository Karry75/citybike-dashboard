"""Diagnose column names and date formats"""
import json, sys
sys.path.insert(0, r"C:\Users\Karry\.workbuddy\binaries\python\envs\default\lib\python3.13\site-packages")
import pymysql

cfg = json.load(open("config/backup_config.json", encoding="utf-8"))
cfg.pop("workers", None)
conn = pymysql.connect(host=cfg["host"], port=cfg["port"], user=cfg["user"],
                       password=cfg["password"], database=cfg["database"],
                       connect_timeout=30, read_timeout=600, charset="utf8mb4")
cur = conn.cursor()

# Check t_exchange_order columns
cur.execute("""
    SELECT COLUMN_NAME FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='t_exchange_order'
    ORDER BY ORDINAL_POSITION
""")
cols = [r[0] for r in cur.fetchall()]
print("t_exchange_order cols:", cols)

# Check t_user columns (create_time type)
cur.execute("""
    SELECT COLUMN_NAME, DATA_TYPE FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='t_user'
    AND COLUMN_NAME IN ('create_time','created_at','created')
""")
print("\ncb_user time cols:", cur.fetchall())

# Check create_time sample values from t_user
cur.execute("SELECT create_time FROM t_user ORDER BY create_time DESC LIMIT 5")
print("\ncb_user.create_time samples:", cur.fetchall())

# Check take_battery_time from exchange_order
cur.execute("SELECT take_battery_time, create_time FROM t_exchange_order ORDER BY create_time DESC LIMIT 3")
print("\nexchange_order time samples:", cur.fetchall())

# Check refund count query that worked
cur.execute("""
    SELECT COUNT(*) FROM t_user_exchange_package_order
    WHERE is_refund = 1 AND is_del = 0
""")
print(f"\nrefund count (confirmed): {cur.fetchone()[0]}")

conn.close()
