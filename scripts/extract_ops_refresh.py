# -*- coding: utf-8 -*-
"""运营总览（中国地图大屏）增量刷新抽取。

只抽运营总览依赖的**聚合值**，不动 detail 明细大表（避免破坏其他模块）。
输出 data/ops_refresh.json，再由 merge_ops_refresh.py 合并进 dashboard_data(.lite).json。

=== 口径说明（2026-08-05 实测校准，务必保留）===
1. 换电成功订单：系统在 2023-08-11 切换过状态机
     旧口径 order_status='success'          → 1,307,910 条，2021-09-07 ~ 2023-08-11
     新口径 exchange_order_status='success' → 9,566,323 条，2023-08-11 ~ 2026-08-05
   两者时间无缝衔接，必须 OR 合并才是全程真实换电量（约 1087 万）。
2. 用户标识：2023-08 之后 consume_user_id 恒为 0（969 万条无一例外），
   改用 take_user_id（非零率 100%，近 1 年 distinct 50,245）。
3. 金额：real_pay_price / pay_price 在新数据中恒为 0（换电走套餐制不单独收费），
   实际分成收入在 profit_fee（分），近 1 年合计 909 万元。
4. t_site 无 industry 字段（前端曾误读，恒 undefined）→ 网点类型用 type(1/5/4/7/2) 中文映射。
"""
import json, pymysql, time, datetime, os

ROOT = r"D:/workboddy file/dudu分析/citybike_backup"
DB = json.load(open(ROOT + "/config/backup_config.json", encoding="utf-8"))
DB.pop("workers", None)
OUT = ROOT + "/data/ops_refresh.json"
NOW = int(time.time() * 1000)

# 成功换电订单口径（新旧状态机合并）
SUCCESS_W = "(order_status='success' OR exchange_order_status='success')"

SITE_TYPE_CN = {1: "换电网点", 2: "车吧", 4: "售车网点", 5: "租车网点", 7: "其他"}
SITE_STATUS_CN = {"have_opened": "已开业", "closed": "已关闭", "not_cooperation": "未合作",
                  "wait_delivery": "待送货", "wait_install": "待安装", "wait_audit": "待审批",
                  "wait_open": "待开业", "wait_acceptance": "待验收"}
STORE_STATUS_CN = {"full": "满电", "charging": "充电中", "none": "空仓", "error": "故障"}
BAT_ONLINE_CN = {"online": "在线", "offline": "离线", "unregister": "未注册"}

conn = pymysql.connect(**DB)
cur = conn.cursor()
ERR = []


def ms2str(v):
    if not v:
        return ""
    try:
        return (datetime.datetime.utcfromtimestamp(int(v) / 1000) + datetime.timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(v)


def q(sql, tag, many=False, default=None):
    t0 = time.time()
    try:
        cur.execute(sql)
        rows = cur.fetchall()
        r = rows if many else (rows[0][0] if rows and rows[0] else default)
        print("  [%s] %.1fs" % (tag, time.time() - t0), flush=True)
        return r
    except Exception as e:
        msg = "%s: %s" % (tag, str(e)[:200])
        ERR.append(msg)
        print("  [%s] FAIL %s" % (tag, str(e)[:160]), flush=True)
        return [] if many else default


R = {}
R["meta"] = {
    "refreshed_at": ms2str(NOW),
    "caliber": "success=order_status OR exchange_order_status；用户=take_user_id；金额=profit_fee/100",
    "source": "extract_ops_refresh.py",
}

# ---------- 1) OVERVIEW KPI ----------
print("[1/6] overview KPI", flush=True)
OV = R["overview"] = {}
OV["user_total"] = q("SELECT COUNT(*) FROM t_user WHERE is_del=0", "ov_user", default=0)
OV["cabinet_total"] = q("SELECT COUNT(DISTINCT device_sn) FROM t_exchange_store", "ov_cab", default=0)
OV["battery_total"] = q("SELECT COUNT(*) FROM t_battery WHERE is_del=0", "ov_bat", default=0)
OV["site_total"] = q("SELECT COUNT(*) FROM t_site WHERE is_del=0", "ov_site", default=0)
OV["agreement_total"] = q("SELECT COUNT(*) FROM t_exchange_agreement", "ov_agr", default=0)
OV["cabinet_online"] = q(
    "SELECT COUNT(DISTINCT device_sn) FROM t_exchange_store "
    "WHERE status IN ('full','charging') OR last_upload_time>=%d" % (NOW - 86400000), "ov_cabon", default=0)
OV["battery_online"] = q(
    "SELECT COUNT(*) FROM t_battery WHERE is_del=0 AND online_status='online'", "ov_baton", default=0)
OV["order_total"] = q("SELECT COUNT(*) FROM t_exchange_order WHERE " + SUCCESS_W, "ov_ord", default=0)

# 设备段同源（前端 E.cabinet_online 优先）
R["device"] = {
    "cabinet_total": OV["cabinet_total"], "cabinet_online": OV["cabinet_online"],
    "cabinet_offline": (OV["cabinet_total"] or 0) - (OV["cabinet_online"] or 0),
    "battery_total": OV["battery_total"], "battery_online": OV["battery_online"],
    "battery_offline": q("SELECT COUNT(*) FROM t_battery WHERE is_del=0 AND online_status='offline'",
                         "e_batoff", default=0),
}

# ---------- 2) 城市换电排行（全量真实，非 5000 样本） ----------
print("[2/6] city_rank", flush=True)
rows = q("SELECT COALESCE(NULLIF(sys_city_name,''),'未知') city, COUNT(*) c "
         "FROM t_exchange_order WHERE " + SUCCESS_W + " GROUP BY city ORDER BY c DESC LIMIT 60",
         "city_rank", many=True) or []
R["user"] = {"city_rank": [{"city": r[0], "count": r[1]} for r in rows]}

# ---------- 3) analytics.daily 全程按天聚合 ----------
print("[3/6] analytics.daily (全程按天，扫 ~1087 万行)", flush=True)
rows = q(
    "SELECT DATE(FROM_UNIXTIME(create_time/1000)) d, COUNT(*) orders, "
    "COUNT(DISTINCT CASE WHEN take_user_id>0 THEN take_user_id ELSE consume_user_id END) users, "
    "COUNT(DISTINCT site_id) sites, COUNT(DISTINCT take_exchange_sn) cabinets, "
    "SUM(profit_fee) profit_fen, SUM(is_first_take) first_take, SUM(is_refund) refund_cnt "
    "FROM t_exchange_order WHERE " + SUCCESS_W + " GROUP BY d ORDER BY d", "an_daily", many=True) or []
R["analytics"] = {"daily": [{
    "date": str(r[0]), "orders": r[1] or 0, "users": r[2] or 0,
    "sites": r[3] or 0, "cabinets": r[4] or 0,
    "fee": round((r[5] or 0) / 100.0, 2), "first_take": r[6] or 0,
    "refund": r[7] or 0,
} for r in rows]}
print("      daily rows = %d" % len(R["analytics"]["daily"]), flush=True)

# ---------- 4) 网点类型 / 状态分布（全量 11084 网点） ----------
print("[4/6] 网点全量分布", flush=True)
DASH = R.setdefault("dashboard", {})
OPS = DASH["ops"] = {}

rows = q("SELECT COALESCE(type,-1) t, COUNT(*) c FROM t_site WHERE is_del=0 GROUP BY t ORDER BY c DESC",
         "site_type", many=True) or []
OPS["site_type"] = [{"name": SITE_TYPE_CN.get(r[0], "类型%s" % r[0]), "value": r[1], "code": r[0]} for r in rows]

rows = q("SELECT COALESCE(NULLIF(audit_progress,''),'unknown') s, COUNT(*) c FROM t_site WHERE is_del=0 "
         "GROUP BY s ORDER BY c DESC", "site_status", many=True) or []
OPS["site_status"] = [{"name": SITE_STATUS_CN.get(r[0], r[0]), "value": r[1]} for r in rows]

# ---------- 5) 电池 / 仓位状态分布（全量） ----------
print("[5/6] 设备全量分布", flush=True)
rows = q("SELECT COALESCE(NULLIF(online_status,''),'unknown') s, COUNT(*) c FROM t_battery WHERE is_del=0 "
         "GROUP BY s ORDER BY c DESC", "bat_status", many=True) or []
OPS["battery_status"] = [{"name": BAT_ONLINE_CN.get(r[0], r[0]), "value": r[1]} for r in rows]

rows = q("SELECT COALESCE(NULLIF(status,''),'unknown') s, COUNT(*) c FROM t_exchange_store WHERE is_del=0 "
         "GROUP BY s ORDER BY c DESC", "store_status", many=True) or []
OPS["store_status"] = [{"name": STORE_STATUS_CN.get(r[0], r[0]), "value": r[1]} for r in rows]

# ---------- 6) 城市聚合：网点 / 换电柜 / 电池 / 换电量（全量，供地图与 Top5 表） ----------
print("[6/6] 城市聚合(网点/柜/电池)", flush=True)
city_agg = {}


def _bump(city, key, val):
    if not city:
        city = "未知"
    d = city_agg.setdefault(city, {"city": city, "sites": 0, "cabs": 0, "bats": 0, "orders": 0})
    d[key] += val or 0


for r in q("SELECT COALESCE(NULLIF(city,''),'未知') c, COUNT(*) n FROM t_site WHERE is_del=0 GROUP BY c",
           "agg_site", many=True) or []:
    _bump(r[0], "sites", r[1])
for r in q("SELECT COALESCE(NULLIF(s.city,''),'未知') c, COUNT(DISTINCT e.device_sn) n "
           "FROM t_exchange e LEFT JOIN t_site s ON e.site_id=s.id WHERE e.is_del=0 GROUP BY c",
           "agg_cab", many=True) or []:
    _bump(r[0], "cabs", r[1])
# 电池无 city 字段：经 last_upload_exchange_sn（最后上报柜 SN）→ t_exchange.site_id → t_site.city 反查。
# ⚠️ 不能用 b.device_sn（那是电池自身 SN，关联不到柜，会导致全部落入“未知”）。
for r in q("SELECT COALESCE(NULLIF(s.city,''),'未知') c, COUNT(*) n "
           "FROM t_battery b JOIN t_exchange e ON b.last_upload_exchange_sn=e.device_sn AND e.is_del=0 "
           "LEFT JOIN t_site s ON e.site_id=s.id WHERE b.is_del=0 AND b.last_upload_exchange_sn<>'' GROUP BY c",
           "agg_bat", many=True) or []:
    _bump(r[0], "bats", r[1])
for r in q("SELECT COALESCE(NULLIF(site_city,''),'未知') c, COUNT(*) n FROM t_exchange_order "
           "WHERE " + SUCCESS_W + " GROUP BY c ORDER BY n DESC LIMIT 200", "agg_ord", many=True) or []:
    _bump(r[0], "orders", r[1])

OPS["city_agg"] = sorted(city_agg.values(), key=lambda d: -(d["orders"] or d["sites"]))
OPS["refreshed_at"] = R["meta"]["refreshed_at"]

R["errors"] = ERR
tmp = OUT + ".tmp"
json.dump(R, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
os.replace(tmp, OUT)
conn.close()

print("\n=== OPS REFRESH DONE ===")
print("overview :", {k: OV[k] for k in ("user_total", "site_total", "cabinet_total", "battery_total", "order_total")})
print("online   : 柜 %s/%s  电池 %s/%s" % (OV["cabinet_online"], OV["cabinet_total"],
                                          OV["battery_online"], OV["battery_total"]))
print("daily    : %d 天，%s ~ %s" % (len(R["analytics"]["daily"]),
                                    R["analytics"]["daily"][0]["date"] if R["analytics"]["daily"] else "-",
                                    R["analytics"]["daily"][-1]["date"] if R["analytics"]["daily"] else "-"))
print("city_rank: %d 城，Top3 = %s" % (len(R["user"]["city_rank"]), R["user"]["city_rank"][:3]))
print("site_type:", OPS["site_type"])
print("city_agg : %d 城" % len(OPS["city_agg"]))
print("ERRORS   : %d" % len(ERR))
for e in ERR:
    print("  -", e)
print("SIZE     :", os.path.getsize(OUT))
