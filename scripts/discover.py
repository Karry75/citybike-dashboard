import json, pymysql
from collections import defaultdict

DB = json.load(open(r"D:/workboddy file/dudu分析/citybike_backup/config/backup_config.json", encoding="utf-8"))

conn = pymysql.connect(host=DB["host"], port=DB["port"], user=DB["user"], password=DB["password"],
                       database=DB["database"], connect_timeout=15, read_timeout=600, charset="utf8mb4")
cur = conn.cursor()

# All tables with row counts
tables = {}
cur.execute("SELECT TABLE_NAME FROM information_schema.tables WHERE table_schema=%s", (DB["database"],))
allt = [r[0] for r in cur.fetchall()]

# keyword -> concept
groups = {
    "用户": ["user"],
    "换电柜/设备": ["cabinet", "device"],
    "电池": ["battery"],
    "网点/站点/门店": ["site", "station", "shop", "store", "outlet", "dot"],
    "套餐/产品": ["package", "plan", "product"],
    "协议/合同": ["agreement", "contract", "protocol"],
    "订单": ["order"],
    "优惠券": ["coupon"],
    "业务员/销售/代理商": ["salesman", "sales", "agent", "promoter"],
    "仓库": ["warehouse", "depot", "stock"],
    "工单": ["work_order", "ticket", "order_task"],
    "财务/账单/结算": ["bill", "finance", "settle", "account", "fee", "pay"],
    "客服/反馈": ["service", "feedback", "reception", "cs", "consult"],
    "预警/监控": ["warn", "alert", "monitor"],
    "骑行/车辆": ["ride", "bike", "vehicle"],
    "换电": ["exchange", "swap"],
    "导购": ["guide", "shopping"],
}

result = {}
for concept, kws in groups.items():
    matched = [t for t in allt if any(k in t for k in kws)]
    rows = []
    for t in matched:
        cur.execute(f"SELECT TABLE_ROWS FROM information_schema.tables WHERE table_schema=%s AND TABLE_NAME=%s", (DB["database"], t))
        rc = cur.fetchone()
        rows.append((t, rc[0] if rc else None))
    rows.sort(key=lambda x: -(x[1] or 0))
    result[concept] = rows[:25]

out = []
for concept, rows in result.items():
    out.append(f"\n### {concept} ({len(rows)} shown)")
    for t, rc in rows:
        out.append(f"  {t}  rows={rc}")

with open(r"D:/workboddy file/dudu分析/citybike_backup/docs/table_candidates.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out))
conn.close()
print("DONE", len(allt), "tables")
