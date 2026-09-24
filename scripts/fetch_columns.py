import json, pymysql
DB = json.load(open(r"D:/workboddy file/dudu分析/citybike_backup/config/backup_config.json", encoding="utf-8"))
conn = pymysql.connect(host=DB["host"], port=DB["port"], user=DB["user"], password=DB["password"],
                       database=DB["database"], connect_timeout=15, read_timeout=600, charset="utf8mb4")
cur = conn.cursor()

# Extra table search
extra_kw = ["cabinet", "agent", "agency", "salesman", "employee", "distributor", "guide", "sales", "warehouse", "settlement", "cabinet"]
cur.execute("SELECT TABLE_NAME FROM information_schema.tables WHERE table_schema=%s", (DB["database"],))
allt = [r[0] for r in cur.fetchall()]
print("=== EXTRA TABLE SEARCH ===")
for kw in ["cabinet","agent","agency","salesman","employee","distributor","guide","sales","warehouse","settlement"]:
    m = [t for t in allt if kw in t]
    print(f"[{kw}] {m}")

core = ["t_user","t_battery","t_site","t_exchange_package","t_exchange_rent_package",
        "t_exchange_agreement","t_exchange_order","t_user_exchange_package_order","t_coupon",
        "t_user_coupon","t_promoter","t_work_order","t_expense_bill","t_feedback",
        "t_reception_log","t_monitor_ex_event","t_bike","t_device_type","t_exchange_store",
        "t_exchange_service_order","t_user_exchange_rent","t_user_exchange_deposit"]
print("\n=== CORE TABLE COLUMNS ===")
for t in core:
    cur.execute("""SELECT COLUMN_NAME, DATA_TYPE, COLUMN_COMMENT FROM information_schema.columns
                   WHERE table_schema=%s AND TABLE_NAME=%s ORDER BY ORDINAL_POSITION""",
                (DB["database"], t))
    cols = cur.fetchall()
    print(f"\n## {t} ({len(cols)} cols)")
    for c in cols:
        print(f"   {c[0]}  {c[1]}  {c[2]}")
conn.close()
