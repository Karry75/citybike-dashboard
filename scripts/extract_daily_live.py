# -*- coding: utf-8 -*-
"""合并式：用原始 t_exchange_order 重算 analytics.daily 到 2026。

背景：原 extract_dashboard.py 的 A1 段读 t_statistics_daily_exchange_order（预聚合日统计表），
该表在 live 库里仅到 2023-08-09（之后未维护）→ 趋势图卡在 2023-08。
而原始 t_exchange_order 有 2026 全量（1101 万行，take_battery_time 到 2026-07-27），
可直接按日 GROUP BY 重算日级序列，替代废弃统计表。

做法：读旧 dashboard_data.json → 重写 D['analytics']['daily'] → 写回。
不动基底、不重跑其它 enrich（其余模块本就是 2026 live）。
"""
import json, pymysql, datetime, os

BASE = r"D:/workboddy file/dudu分析/citybike_backup"
DB = json.load(open(os.path.join(BASE, "config/backup_config.json"), encoding="utf-8"))
DB.pop("workers", None)
conn = pymysql.connect(host=DB["host"], port=DB["port"], user=DB["user"], password=DB["password"],
                       database=DB["database"], connect_timeout=15, read_timeout=600, charset="utf8mb4")
cur = conn.cursor()

print("查询 t_exchange_order 日聚合（1101 万行，可能需数十秒）...")
cur.execute("""
SELECT DATE(FROM_UNIXTIME(take_battery_time/1000)) d,
       COUNT(*) orders,
       SUM(CASE WHEN is_first_take=1 THEN 1 ELSE 0 END) first_take,
       COUNT(DISTINCT take_user_id) dau,
       COUNT(DISTINCT site_id) sites,
       COUNT(DISTINCT take_exchange_store_id) cabins,
       COALESCE(SUM(real_pay_price),0)/100.0 fee
FROM t_exchange_order
WHERE order_status='success' AND take_battery_time>0
GROUP BY d ORDER BY d
""")
rows = cur.fetchall()
conn.close()

# users = 累计首充用户（近似累计换电用户基数）
cum = 0
daily = []
for r in rows:
    d = str(r[0]); orders = r[1]; ft = int(r[2] or 0); dau = int(r[3] or 0)
    sites = int(r[4] or 0); cabins = int(r[5] or 0); fee = round(float(r[6] or 0), 2)
    cum += ft
    daily.append({"date": d, "orders": orders, "first_take": ft, "users": cum,
                   "sites": sites, "cabinets": cabins, "fee": fee, "refund": 0})

D = json.load(open(os.path.join(BASE, "data/dashboard_data.json"), encoding="utf-8"))
A = D.setdefault("analytics", {})
A["daily"] = daily
A["generated_note"] = (
    "analytics.daily 于 %s 由原始 t_exchange_order（成功订单，take_battery_time 日聚合，1101 万行）重算，"
    "替代已废弃的 t_statistics_daily_exchange_order（该预聚合表仅到 2023-08-09）。"
    "字段：orders=成功订单数；first_take=当日首充(is_first_take=1)；users=累计首充用户(近似累计换电用户基数)；"
    "sites=当日活跃网点数；cabinets=当日活跃换电柜数(供产能均值)；fee=当日实付总额(元)。"
    "refund 趋势因原始订单表无逐单退款金额列暂置 0；退款总额仍可经 finance/U.purchase.refund_total 查证。"
) % datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

json.dump(D, open(os.path.join(BASE, "data/dashboard_data.json"), "w", encoding="utf-8"),
            ensure_ascii=False, separators=(",", ":"))
print("WROTE daily: %d 天, %s ~ %s" % (len(daily), daily[0]["date"], daily[-1]["date"]))
print("refund 趋势已置 0（详见 generated_note）")
