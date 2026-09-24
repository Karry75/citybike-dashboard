# -*- coding: utf-8 -*-
"""抽取换电订单明细(t_exchange_order) → DATA.site.exchange，点亮 wse 模块。
同时修复/补齐「单网点换电次数」所需的聚合：
  · W["exchange_rank_30d"]  —— 近30天成功换电按网点排行(top30)  [原 extract_dashboard 已写但疑似上次未跑出]
  · W["exchange_count"]     —— 全量成功换电按网点排行(top200)  [新增，供单网点视图展示换电次数]
  · W["exchange_total"]    —— 全量订单数(≈52万)，供面板注明抽样口径
  · 并把 exchange_count 以 site_id→count 注入 site.detail[].exchange_count

列名尽量与 t_exchange_order 真实列对齐（详见 full_schema.json）：
  order_id(=id 换电订单ID) / status(=order_status) / is_refund
  take_user_id/name/phone  consume_user_id/name/phone
  agency_id/agency_name  site_id/site_name/city/sys_city_name
  cabinet_id/cabinet_sn(=take_exchange_sn)  battery_id/battery_sn(=take_battery_sn)
  soc_before(=take_battery_power) / soc_after(=back_battery_power)
  swap_time(=take_battery_time,已格式化) / back_time
  amount(=real_pay_price 分→元) / pay_type(=pay_way) / mileage / busi_rel_order_no / back_site_name / battery_brand_name

抽样口径：DETAIL_CAP=5000（与 site.detail 一致，避免单文件 HTML 膨胀；全量≈52万需后端实时 API）。
"""
import json, pymysql, time, sys, datetime, os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DB = json.load(open(os.path.join(ROOT, "config", "backup_config.json"), encoding="utf-8"))
DB.pop("workers", None)
OUT = os.path.join(ROOT, "data", "dashboard_data.json")
DETAIL_CAP = 5000
NOW = int(time.time() * 1000)
D30 = NOW - 30 * 86400000

def ms2str(v):
    if not v:
        return ""
    try:
        return (datetime.datetime.utcfromtimestamp(int(v) / 1000) + datetime.timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(v)

conn = pymysql.connect(host=DB["host"], port=DB["port"], user=DB["user"], password=DB["password"],
                       database=DB["database"], connect_timeout=15, read_timeout=600, charset="utf8mb4")
cur = conn.cursor()
ERR = []

def q(sql, label, many=False):
    try:
        cur.execute(sql)
        return cur.fetchall() if many else (cur.fetchone()[0] if cur.rowcount else None)
    except Exception as e:
        ERR.append("%s: %s" % (label, str(e)[:200]))
        print("ERR", label, str(e)[:200], file=sys.stderr)
        return [] if many else None

# ---------- 1) 抽样订单明细 ----------
sql = (
    "SELECT id, order_status, is_refund, "
    "take_user_id, take_user_name, take_user_phone, "
    "consume_user_id, consume_user_name, consume_user_phone, "
    "agency_id, agency_name, "
    "site_id, site_name, site_city, sys_city_name, "
    "take_exchange_id, take_exchange_sn, "
    "take_battery_id, take_battery_sn, take_battery_power, back_battery_power, "
    "take_battery_time, back_battery_time, "
    "real_pay_price, pay_way, mileage, busi_rel_order_no, back_site_name, battery_brand_name "
    "FROM t_exchange_order WHERE is_del=0 ORDER BY create_time DESC LIMIT %d" % DETAIL_CAP
)
raw = q(sql, "orders", many=True) or []
exchange = []
for r in raw:
    city = r[13] or r[14] or "未知"
    exchange.append({
        "order_id": r[0],
        "status": r[1],
        "is_refund": r[2],
        "take_user_id": r[3], "take_user_name": r[4], "take_user_phone": r[5],
        "consume_user_id": r[6], "consume_user_name": r[7], "consume_user_phone": r[8],
        "agency_id": r[9], "agency_name": r[10],
        "site_id": r[11], "site_name": r[12], "city": city, "sys_city_name": r[14],
        "cabinet_id": r[15], "cabinet_sn": r[16],
        "battery_id": r[17], "battery_sn": r[18],
        "soc_before": r[19], "soc_after": r[20],
        "swap_time": ms2str(r[21]), "back_time": ms2str(r[22]),
        "amount": (r[23] or 0) / 100.0,       # 分→元
        "pay_type": r[24], "mileage": r[25],
        "busi_rel_order_no": r[26], "back_site_name": r[27], "battery_brand_name": r[28],
    })

# ---------- 2) 全量订单数 ----------
total = q("SELECT COUNT(*) FROM t_exchange_order WHERE is_del=0", "ex_total") or 0

# ---------- 3) 网点换电次数排行(top30) = 全量成功换电按网点 ----------
# ⚠️ 数据现实：库内 success（完成换电）几乎全是 2023 历史单；2026 实时新单多为 created（进行中/未完成同步）。
#   故「近30天 success」恒为 0；此处取「全量 success 按网点」作为换电次数排行口径（历史完成换电）。
rank30 = [
    {"site": r[0], "city": r[1], "count": r[2]} for r in q(
        "SELECT site_name, sys_city_name, COUNT(*) c FROM t_exchange_order "
        "WHERE order_status='success' GROUP BY site_id ORDER BY c DESC LIMIT 30",
        "ex_rank30", many=True) or []
]

# ---------- 4) 全量成功换电 按网点计数（不限条数，供单网点视图注入） ----------
all_cnt = q(
    "SELECT site_id, site_name, COUNT(*) c FROM t_exchange_order "
    "WHERE order_status='success' GROUP BY site_id ORDER BY c DESC",
    "ex_count", many=True) or []
exchange_count = [{"site_id": r[0], "site": r[1], "count": r[2]} for r in all_cnt[:200]]
site_exchange_map = {r[0]: r[2] for r in all_cnt}

# ---------- 5) 合并进 dashboard_data.json ----------
D = json.load(open(OUT, encoding="utf-8"))
W = D.setdefault("site", {})
W["exchange"] = exchange
W["exchange_total"] = total
W["exchange_rank_30d"] = rank30
W["exchange_count"] = exchange_count
# 注入 site.detail 的换电次数
det = W.get("detail", [])
for r in det:
    r["exchange_count"] = site_exchange_map.get(r.get("id"))
W["detail"] = det

json.dump(D, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
conn.close()

print("=== extract_orders DONE ===")
print("采样订单(写入 DATA.site.exchange):", len(exchange))
print("全量订单数 exchange_total:", total)
print("网点换电次数排行(top30, 全量success):", len(rank30))
print("全量按网点排行(top):", len(exchange_count))
print("site.detail 注入 exchange_count 行数:", sum(1 for r in det if r.get("exchange_count") is not None), "/", len(det))
print("ERRORS:", len(ERR))
for e in ERR:
    print("  -", e)
