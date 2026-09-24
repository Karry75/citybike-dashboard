import json, pymysql
DB = json.load(open(r"D:/workboddy file/dudu分析/citybike_backup/config/backup_config.json", encoding="utf-8"))
conn = pymysql.connect(host=DB["host"], port=DB["port"], user=DB["user"], password=DB["password"],
                       database=DB["database"], connect_timeout=15, read_timeout=600, charset="utf8mb4")
cur = conn.cursor()
cur.execute("SELECT TABLE_NAME FROM information_schema.tables WHERE table_schema=%s", (DB["database"],))
allt = [r[0] for r in cur.fetchall()]
print("=== SEARCH cabinet/device master ===")
for kw in ["machine","box","_cab","exchange_device","device_master","cabinet","kiosk","exchange_machine"]:
    print(f"[{kw}]", [t for t in allt if kw in t][:10])

need = ["t_exchange_agreement","t_promoter","t_work_order","t_expense_bill","t_feedback",
        "t_reception_log","t_monitor_ex_event","t_bike","t_exchange_order","t_user_exchange_package_order",
        "t_user_exchange_rent","t_exchange_service_order","t_distributor","t_promoter_relation"]
for t in need:
    cur.execute("""SELECT COLUMN_NAME, DATA_TYPE, COLUMN_COMMENT FROM information_schema.columns
                   WHERE table_schema=%s AND TABLE_NAME=%s ORDER BY ORDINAL_POSITION""", (DB["database"], t))
    cols = cur.fetchall()
    print(f"\n## {t} ({len(cols)} cols)")
    for c in cols:
        print(f"   {c[0]}  {c[1]}  {c[2]}")
conn.close()
