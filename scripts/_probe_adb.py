# -*- coding: utf-8 -*-
"""探针：连 ADB，确认核心表是否有 2023-08-09 之后的新鲜数据。"""
import json, pymysql, datetime, sys

CFG = r"D:/workboddy file/dudu分析/citybike_backup/config/backup_config.json"
DB = json.load(open(CFG, encoding="utf-8"))
DB.pop("workers", None)

def bj(ms):
    if not ms:
        return "—"
    return (datetime.datetime.utcfromtimestamp(int(ms) / 1000) + datetime.timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")

try:
    conn = pymysql.connect(**DB)
except Exception as e:
    print("❌ 连接失败:", repr(e)[:300])
    sys.exit(2)

cur = conn.cursor()
def q(sql):
    cur.execute(sql)
    return cur.fetchall()

print("=== ADB 连接成功 ===")
print("当前北京时间:", (datetime.datetime.utcnow() + datetime.timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S"))
print("")

# 1) 每日统计表（运营总览趋势的直接来源）
r = q("SELECT MAX(statistics_date), COUNT(*) FROM t_statistics_daily_exchange_order WHERE is_del=0")
print("[趋势来源] t_statistics_daily_exchange_order")
print("  MAX(statistics_date) =", r[0][0], "| 总行数 =", r[0][1])
r2 = q("SELECT COUNT(*) FROM t_statistics_daily_exchange_order WHERE is_del=0 AND statistics_date > '2023-08-09'")
print("  其中 statistics_date > 2023-08-09 的行数 =", r2[0][0])
print("")

# 2) 换电订单（城市排行/留存/明细来源）
r = q("SELECT MAX(take_battery_time) FROM t_exchange_order")
print("[订单来源] t_exchange_order")
print("  MAX(take_battery_time) =", bj(r[0][0]))
c = q("SELECT COUNT(*) FROM t_exchange_order WHERE take_battery_time > 1691510400000")  # 2023-08-09 00:00 +08:00
print("  take_battery_time > 2023-08-09 00:00 的行数 =", c[0][0])
c2 = q("SELECT COUNT(*) FROM t_exchange_order")
print("  总行数 =", c2[0][0])
print("")

# 3) 用户（用户增长/新增）
r = q("SELECT MAX(create_time) FROM t_user WHERE is_del=0")
print("[用户来源] t_user  MAX(create_time) =", bj(r[0][0]))
c = q("SELECT COUNT(*) FROM t_user WHERE is_del=0 AND create_time > 1691510400000")
print("  create_time > 2023-08-09 的新增用户 =", c[0][0])
print("")

# 4) 网点（运营总览网点数）
r = q("SELECT MAX(create_time) FROM t_site WHERE is_del=0")
print("[网点来源] t_site  MAX(create_time) =", bj(r[0][0]))
c = q("SELECT COUNT(*) FROM t_site WHERE is_del=0 AND create_time > 1691510400000")
print("  create_time > 2023-08-09 的新增网点 =", c[0][0])
print("")

conn.close()
print("=== 探针完成 ===")
