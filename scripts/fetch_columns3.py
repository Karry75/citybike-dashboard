import json, pymysql
DB = json.load(open(r"D:/workboddy file/dudu分析/citybike_backup/config/backup_config.json", encoding="utf-8"))
conn = pymysql.connect(host=DB["host"], port=DB["port"], user=DB["user"], password=DB["password"],
                       database=DB["database"], connect_timeout=15, read_timeout=600, charset="utf8mb4")
cur = conn.cursor()
need = ["t_user_exchange_package_order","t_exchange_order","t_monitor_ex_event","t_bike_sale_relation",
        "t_distributor","t_site_store_employee","t_user_exchange_rent","t_exchange_store","t_battery_product"]
for t in need:
    cur.execute("""SELECT COLUMN_NAME, DATA_TYPE, COLUMN_COMMENT FROM information_schema.columns
                   WHERE table_schema=%s AND TABLE_NAME=%s ORDER BY ORDINAL_POSITION""", (DB["database"], t))
    cols = cur.fetchall()
    print(f"\n## {t} ({len(cols)} cols)")
    for c in cols[:50]:
        print(f"   {c[0]}  {c[1]}  {c[2]}")
conn.close()
