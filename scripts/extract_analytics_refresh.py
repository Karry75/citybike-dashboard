# -*- coding: utf-8 -*-
"""深度分析模块（analytics A1-A10）增量刷新抽取。

只重算 analytics 段的聚合值，不动其他 14 个模块、不动 detail 明细。
输出 data/analytics_refresh.json，再由 merge_analytics_refresh.py 合并进 dashboard_data(.lite).json。

=== 口径说明（2026-08-05 实测校准，务必保留）===
1. 换电成功订单：2023-08-11 切换状态机
     旧 order_status='success'          → 1,307,910 条
     新 exchange_order_status='success' → 9,566,323 条
   必须 OR 合并才是全程真实换电量（约 1087 万）。原 extract_dashboard.py 只用旧口径，
   导致 analytics 模块系统性少算 ~950 万单 → 本轮全部修正。
2. 用户标识：2023-08 之后 consume_user_id 恒为 0，改用
   UID = CASE WHEN take_user_id>0 THEN take_user_id ELSE consume_user_id END
   作为"有效用户"，用于留存/复购/城市 ARPU/代理商 的去重与分组。
3. 金额：real_pay_price / pay_price 在新数据中恒为 0（换电走套餐制），
   实际分成收入在 profit_fee（分）。故 城市 ARPU / 代理商收入 改用
   SUM(profit_fee)/100（分成收入，单位元），与运营总览月度趋势口径一致。
   ⚠️ 原 A7/A9/A10 用 real_pay_price → 新数据全 0，已在 generated_note 标注。
4. A1 daily 已在 ops_refresh 正确刷过（1768 天）；本轮重算以保证自洽（A5 产能依赖它）。
"""
import json, pymysql, time, datetime, os

ROOT = r"D:/workboddy file/dudu分析/citybike_backup"
DB = json.load(open(ROOT + "/config/backup_config.json", encoding="utf-8"))
DB.pop("workers", None)
OUT = ROOT + "/data/analytics_refresh.json"
NOW = int(time.time() * 1000)

# 成功换电订单口径（新旧状态机合并）
SUCCESS_W = "(order_status='success' OR exchange_order_status='success')"
# 有效用户表达式
UID = "CASE WHEN take_user_id>0 THEN take_user_id ELSE consume_user_id END"

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
A = R["analytics"] = {}
R["meta"] = {
    "refreshed_at": ms2str(NOW),
    "caliber": "success=order_status OR exchange_order_status；用户=有效UID(take_user_id优先)；金额=profit_fee/100(分成收入)",
    "source": "extract_analytics_refresh.py",
}

# 读取现有 finance 字典（供 A9 套餐结构健康度复用收入字段，保持与财务模块展示一致）
FIN = {}
try:
    lite = json.load(open(ROOT + "/data/dashboard_data_lite.json", encoding="utf-8"))
    FIN = lite.get("finance", {}) or {}
    print("[finance] 复用自 lite：income_rent=%s income_power=%s" % (FIN.get("income_rent"), FIN.get("income_power")), flush=True)
except Exception as e:
    ERR.append("read_finance: %s" % str(e)[:160])
    print("[finance] 读取失败，A9 收入字段将为 None：%s" % str(e)[:120], flush=True)


# ---------- A1 趋势（按天聚合，全程） ----------
print("[A1] analytics.daily 全程按天聚合", flush=True)
rows = q(
    "SELECT DATE(FROM_UNIXTIME(create_time/1000)) d, COUNT(*) orders, "
    "COUNT(DISTINCT %s) users, COUNT(DISTINCT site_id) sites, COUNT(DISTINCT take_exchange_sn) cabinets, "
    "SUM(profit_fee) profit_fen, SUM(is_first_take) first_take, SUM(is_refund) refund_cnt "
    "FROM t_exchange_order WHERE %s GROUP BY d ORDER BY d" % (UID, SUCCESS_W), "an_daily", many=True) or []
A["daily"] = [{
    "date": str(r[0]), "orders": r[1] or 0, "users": r[2] or 0,
    "sites": r[3] or 0, "cabinets": r[4] or 0,
    "fee": round((r[5] or 0) / 100.0, 2), "first_take": r[6] or 0,
    "refund": r[7] or 0,
} for r in rows]
DAYS = max(len(A["daily"]), 1)
print("      daily rows = %d (%s ~ %s)" % (len(A["daily"]),
      A["daily"][0]["date"] if A["daily"] else "-", A["daily"][-1]["date"] if A["daily"] else "-"), flush=True)


# ---------- A2 留存 / 复购 ----------
print("[A2] 留存/复购", flush=True)
try:
    total_u = q("SELECT COUNT(DISTINCT %s) FROM t_exchange_order WHERE %s" % (UID, SUCCESS_W), "an_tu", default=0)
    rep = q("SELECT COUNT(*) FROM (SELECT %s uid FROM t_exchange_order WHERE %s GROUP BY %s HAVING COUNT(*)>=2) t"
            % (UID, SUCCESS_W, UID), "an_rep", default=0)
    freq = q(
        "SELECT b, COUNT(*) FROM ("
        "  SELECT CASE WHEN c<2 THEN '1次' WHEN c<=5 THEN '2-5次' WHEN c<=20 THEN '6-20次' ELSE '20+次' END b "
        "  FROM (SELECT %s uid, COUNT(*) c FROM t_exchange_order WHERE %s GROUP BY %s) t"
        ") t2 GROUP BY b" % (UID, SUCCESS_W, UID), "an_freq", many=True) or []
    A["retention"] = {"total_users": total_u, "repurchase_users": rep,
                      "repurchase_rate": round(rep / total_u, 4) if total_u else 0,
                      "freq_dist": [{"bucket": r[0], "users": r[1]} for r in freq]}
except Exception as e:
    ERR.append("an_retention: %s" % str(e)[:200])
    A["retention"] = {"total_users": None, "repurchase_users": None, "repurchase_rate": None, "freq_dist": []}


# ---------- A3 欠租(R)率与金额 ----------
print("[A3] 欠租/违约金", flush=True)
try:
    owe_agr = q("SELECT COUNT(*) FROM t_exchange_agreement WHERE status='owe_rent'", "an_owe", default=0)
    agr_total = q("SELECT COUNT(*) FROM t_exchange_agreement", "an_agrt", default=0) or 1
    pen = q("SELECT COALESCE(SUM(pay_fee),0), COUNT(*) FROM t_user_exchange_rent_violated_log WHERE is_pay=1",
            "an_pen", many=True) or [(0, 0)]
    pen_amount = (pen[0][0] or 0) / 100.0
    pen_count = pen[0][1] or 0
    owe_city = q("SELECT sys_city_name, COUNT(*) FROM t_exchange_agreement WHERE status='owe_rent' "
                 "GROUP BY sys_city_name ORDER BY COUNT(*) DESC LIMIT 15", "an_owecity", many=True) or []
    A["owe"] = {"owe_agreements": owe_agr, "owe_rate": round(owe_agr / agr_total, 4) if agr_total else 0,
                "penalty_amount": pen_amount, "penalty_count": pen_count,
                "by_city": [{"city": (r[0] or "未知"), "count": r[1]} for r in owe_city]}
except Exception as e:
    ERR.append("an_owe: %s" % str(e)[:200])
    A["owe"] = {"owe_agreements": None, "owe_rate": None, "penalty_amount": None, "penalty_count": None, "by_city": []}


# ---------- A4 电池健康与周转 ----------
print("[A4] 电池周转", flush=True)
try:
    turn = q("SELECT COUNT(*), COUNT(DISTINCT battery_device_id) FROM t_battery_circulate_log WHERE is_del=0",
             "an_turn", many=True) or [(0, 0)]
    turn_total, turn_bat = turn[0][0] or 0, turn[0][1] or 0
    top_turn = q("SELECT battery_device_id, COUNT(*) FROM t_battery_circulate_log WHERE is_del=0 "
                  "GROUP BY battery_device_id ORDER BY COUNT(*) DESC LIMIT 12", "an_turntop", many=True) or []
    offline = q("SELECT COUNT(*) FROM t_monitor_ex_event_battery WHERE online_status='offline' AND is_del=0", "an_off", default=0)
    recycled = q("SELECT COUNT(*) FROM t_recover_battery WHERE is_del=0", "an_rec", default=0)
    A["battery"] = {"circulate_logs": turn_total, "distinct_batteries": turn_bat,
                    "avg_turnover": round(turn_total / turn_bat, 1) if turn_bat else 0,
                    "top_turnover": [{"battery": r[0], "times": r[1]} for r in top_turn],
                    "offline": offline, "recycled": recycled}
except Exception as e:
    ERR.append("an_battery: %s" % str(e)[:200])
    A["battery"] = {"circulate_logs": None, "distinct_batteries": None, "avg_turnover": None, "top_turnover": [], "offline": None, "recycled": None}


# ---------- A5 网点产能 ----------
print("[A5] 网点产能", flush=True)
try:
    total_orders = sum(d["orders"] for d in A["daily"]) or 1
    avg_cab = (sum(d["cabinets"] for d in A["daily"]) / DAYS) if A["daily"] else 0
    top_sites = q("SELECT site_name, COUNT(*) FROM t_exchange_order WHERE %s "
                  "GROUP BY site_name ORDER BY COUNT(*) DESC LIMIT 15" % SUCCESS_W, "an_sites", many=True) or []
    A["capacity"] = {"avg_orders_per_cabinet_day": round(total_orders / (DAYS * avg_cab), 2) if avg_cab else 0,
                     "top_sites": [{"site": (r[0] or "未知网点"), "orders": r[1]} for r in top_sites]}
except Exception as e:
    ERR.append("an_capacity: %s" % str(e)[:200])
    A["capacity"] = {"avg_orders_per_cabinet_day": None, "top_sites": []}


# ---------- A6 销售漏斗 ----------
print("[A6] 销售漏斗", flush=True)
try:
    dep_u = q("SELECT COUNT(DISTINCT user_id) FROM t_user_exchange_deposit WHERE is_del=0", "an_dep", default=0)
    agr_u = q("SELECT COUNT(DISTINCT user_id) FROM t_exchange_agreement", "an_agu", default=0)
    rent_c = q("SELECT COUNT(*) FROM t_user_exchange_rent WHERE is_del=0 AND card_status IN ('using','used')", "an_rent", default=0)
    A["funnel"] = {"deposit_users": dep_u, "agreement_users": agr_u, "rent_card_users": rent_c,
                   "conv_deposit_to_agr": round(agr_u / dep_u, 4) if dep_u else 0,
                   "conv_agr_to_rent": round(rent_c / agr_u, 4) if agr_u else 0}
except Exception as e:
    ERR.append("an_funnel: %s" % str(e)[:200])
    A["funnel"] = {"deposit_users": None, "agreement_users": None, "rent_card_users": None, "conv_deposit_to_agr": None, "conv_agr_to_rent": None}


# ---------- A7 城市对标 / ARPU（收入改用 profit_fee 分成收入） ----------
print("[A7] 城市 ARPU", flush=True)
try:
    city_rows = q("SELECT sys_city_name, COUNT(*), COUNT(DISTINCT %s), COALESCE(SUM(profit_fee),0) "
                  "FROM t_exchange_order WHERE %s GROUP BY sys_city_name ORDER BY COUNT(*) DESC LIMIT 15"
                  % (UID, SUCCESS_W), "an_city", many=True) or []
    city_list = []
    for r in city_rows:
        rev = (r[3] or 0) / 100.0
        u = r[2] or 0
        city_list.append({"city": (r[0] or "未知"), "orders": r[1], "users": u, "revenue": rev,
                          "arpu": round(rev / u, 2) if u else 0})
    rev_all = q("SELECT COALESCE(SUM(profit_fee),0), COUNT(DISTINCT %s) FROM t_exchange_order WHERE %s"
                % (UID, SUCCESS_W), "an_arpu_all", many=True) or [(0, 0)]
    rev_all_v = (rev_all[0][0] or 0) / 100.0
    users_all = rev_all[0][1] or 0
    A["city"] = {"list": city_list, "overall_arpu": round(rev_all_v / users_all, 2) if users_all else 0,
                 "overall_revenue": rev_all_v, "overall_users": users_all}
except Exception as e:
    ERR.append("an_city: %s" % str(e)[:200])
    A["city"] = {"list": [], "overall_arpu": None, "overall_revenue": None, "overall_users": None}


# ---------- A8 客服 / 客诉 ----------
print("[A8] 客诉", flush=True)
try:
    cs_total = q("SELECT COUNT(*) FROM t_exchange_order_complaint WHERE is_del=0", "an_cst", default=0)
    cs_type = q("SELECT type, COUNT(*) FROM t_exchange_order_complaint WHERE is_del=0 GROUP BY type", "an_cstype", many=True) or []
    cs_stat = q("SELECT operation_status, COUNT(*) FROM t_exchange_order_complaint WHERE is_del=0 GROUP BY operation_status", "an_csstat", many=True) or []
    order_total = q("SELECT COUNT(*) FROM t_exchange_order WHERE %s" % SUCCESS_W, "an_ot", default=1) or 1
    A["cs"] = {"total": cs_total,
               "by_type": [{"type": (r[0] or "其他"), "count": r[1]} for r in cs_type],
               "by_status": [{"status": (r[0] or "未知"), "count": r[1]} for r in cs_stat],
               "cs_rate": round(cs_total / order_total, 5) if order_total else 0}
except Exception as e:
    ERR.append("an_cs: %s" % str(e)[:200])
    A["cs"] = {"total": None, "by_type": [], "by_status": [], "cs_rate": None}


# ---------- A9 套餐结构健康度（复用 finance 收入 + 正确口径用户数） ----------
print("[A9] 套餐结构", flush=True)
try:
    pkg_users = q("SELECT COUNT(DISTINCT user_id) FROM t_user_exchange_package_order WHERE order_status='success'", "an_pu", default=0)
    rent_users = q("SELECT COUNT(DISTINCT user_id) FROM t_user_exchange_rent_package_order WHERE order_status='success'", "an_ru", default=0)
    A["package"] = {
        "rent_revenue": FIN.get("income_rent"), "power_revenue": FIN.get("income_power"),
        "deposit_revenue": FIN.get("income_deposit"), "package_revenue": FIN.get("income_package"),
        "rent_users": rent_users, "power_users": pkg_users,
        "gift_count": FIN.get("gift_count"), "gift_amount": FIN.get("gift_amount")}
except Exception as e:
    ERR.append("an_package: %s" % str(e)[:200])
    A["package"] = {}


# ---------- A10 代理商 / 渠道效能（收入改用 profit_fee 分成收入） ----------
print("[A10] 代理商", flush=True)
try:
    agy_rows = q("SELECT agency_name, COUNT(*), COALESCE(SUM(profit_fee),0) FROM t_exchange_order "
                 "WHERE %s GROUP BY agency_name ORDER BY COUNT(*) DESC LIMIT 15" % SUCCESS_W, "an_agy", many=True) or []
    agy_owe = q("SELECT a.agency_id, COUNT(*) FROM t_exchange_agreement a WHERE a.status='owe_rent' "
                "GROUP BY a.agency_id ORDER BY COUNT(*) DESC LIMIT 15", "an_agyowe", many=True) or []
    agy_owe_map = {r[0]: r[1] for r in agy_owe}
    agy_list = []
    for r in agy_rows:
        agy_list.append({"agency": (r[0] or "未知代理商"), "orders": r[1], "revenue": (r[2] or 0) / 100.0,
                         "owe_count": agy_owe_map.get(r[0], 0)})
    A["agency"] = {"list": agy_list}
except Exception as e:
    ERR.append("an_agency: %s" % str(e)[:200])
    A["agency"] = {"list": []}

A["generated_note"] = (
    "深度分析模块于 %s 重抽刷新（extract_analytics_refresh.py）。"
    "口径修正：成功订单=order_status OR exchange_order_status（修复原脚本只计旧口径、漏算~950万单）；"
    "用户=有效UID(take_user_id优先，修复 consume_user_id 恒0 塌桶)；"
    "收入=profit_fee/100 分成收入（修复 real_pay_price 恒0）。A1 daily 全程 %d 天。"
) % (R["meta"]["refreshed_at"], len(A["daily"]))

R["errors"] = ERR
tmp = OUT + ".tmp"
json.dump(R, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
os.replace(tmp, OUT)
conn.close()

print("\n=== ANALYTICS REFRESH DONE ===")
print("daily        : %d 天，%s ~ %s" % (len(A["daily"]),
      A["daily"][0]["date"] if A["daily"] else "-", A["daily"][-1]["date"] if A["daily"] else "-"))
print("retention    : total_users=%s  repurchase=%s  rate=%s" % (
    A["retention"].get("total_users"), A["retention"].get("repurchase_users"), A["retention"].get("repurchase_rate")))
print("owe          : %s 欠租（率 %s），违约金 %.0f 元" % (
    A["owe"].get("owe_agreements"), A["owe"].get("owe_rate"), A["owe"].get("penalty_amount") or 0))
print("battery      : 周转日志 %s，离线 %s，回收 %s" % (
    A["battery"].get("circulate_logs"), A["battery"].get("offline"), A["battery"].get("recycled")))
print("capacity     : 单柜日均 %.2f 单，Top1=%s" % (
    A["capacity"].get("avg_orders_per_cabinet_day") or 0,
    (A["capacity"].get("top_sites") or [{}])[0].get("site")))
print("funnel       : 押金 %s → 协议 %s → 租赁卡 %s" % (
    A["funnel"].get("deposit_users"), A["funnel"].get("agreement_users"), A["funnel"].get("rent_card_users")))
print("city ARPU    : overall_arpu=%s 元，overall_revenue=%.0f 元，城市数=%d" % (
    A["city"].get("overall_arpu"), A["city"].get("overall_revenue") or 0, len(A["city"].get("list", []))))
print("cs           : 客诉 %s，客诉率 %s" % (A["cs"].get("total"), A["cs"].get("cs_rate")))
print("package      : 租赁用户 %s，套餐(换电)用户 %s" % (A["package"].get("rent_users"), A["package"].get("power_users")))
print("agency       : %d 家代理商，Top1=%s 订单 %s" % (
    len(A["agency"].get("list", [])),
    (A["agency"].get("list") or [{}])[0].get("agency"),
    (A["agency"].get("list") or [{}])[0].get("orders")))
print("ERRORS       : %d" % len(ERR))
for e in ERR:
    print("  -", e)
print("SIZE         :", os.path.getsize(OUT))
