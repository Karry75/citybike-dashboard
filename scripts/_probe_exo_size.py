# -*- coding: utf-8 -*-
"""抽 10 万行样本(28 个主表直取列)实测 gz 字节/行，外推各时间窗口包体。"""
import json, time, os, gzip, io
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DB = json.load(open(os.path.join(ROOT, "config", "backup_config.json"), encoding="utf-8"))
DB.pop("workers", None)
import pymysql
conn = pymysql.connect(host=DB["host"], port=DB["port"], user=DB["user"], password=DB["password"],
                       database=DB["database"], connect_timeout=15, read_timeout=600, charset="utf8mb4")
cur = conn.cursor()

# 28 个主表直取列（不含需 JOIN 的 9 列）
COLS = ["id","exchange_agreement_id","bike_user_id","bike_user_phone","battery_product_name",
        "site_name","agency_name","order_status","take_battery_sn","take_battery_way","take_exchange_sn",
        "take_user_id","take_user_phone","take_battery_power","take_battery_time","back_battery_sn",
        "back_battery_way","back_exchange_sn","back_site_name","back_user_id","back_user_phone",
        "back_battery_power","back_battery_time","mileage","real_pay_price","busi_rel_order_no","use_power"]
sel = ",".join(COLS)
N = 100000
t0 = time.time()
cur.execute("SELECT %s FROM t_exchange_order WHERE is_del=0 ORDER BY create_time DESC LIMIT %s" % (sel, N))
rows = cur.fetchall()
print("sampled rows =", len(rows), "in %.1fs" % (time.time()-t0))

# 转 list-of-lists（与打包格式一致）
data = [list(r) for r in rows]
raw = json.dumps(data, ensure_ascii=False, separators=(',',':')).encode("utf-8")
gz = gzip.compress(raw, 9)
bpr = len(gz) / len(rows)
print("sample raw json = %.2f MB" % (len(raw)/1e6))
print("sample gz      = %.2f MB" % (len(gz)/1e6))
print("gz bytes/row (28 直取列) = %.2f" % bpr)

# 外推（含 +30% 安全余量，覆盖 9 个 JOIN/字符串列）
for label, n in [("最近90天",785680),("最近180天",1574576),("最近365天",3400717),("全量",11131625)]:
    base = bpr * n / 1e6
    with_join = base * 1.3
    print("%-10s %9d 行 -> gz≈%.1f MB (直取) / %.1f MB (+30%%JOIN余量)" % (label, n, base, with_join))
conn.close()
