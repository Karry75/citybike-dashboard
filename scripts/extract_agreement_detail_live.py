# -*- coding: utf-8 -*-
"""协议明细 live 版（2026 统一口径）。

原 extract_agreement_detail.py 读 2023-08 的 exchange_agreement_pro_*.csv（85,694 行）。
本脚本改连 live t_exchange_agreement（121,265 行，2026-07-27 全量），输出 2026 统一口径。

做法（合并式，不动基底）：
  读旧 dashboard_data.json（保留 agreement_bikes/battery 子表不动，仅刷新主表明细）
  → 主表 35 列从 live t_exchange_agreement 直取 + 4 个小映射表补名称
  → 写回 user.agreement_detail / user.agreement_total

说明：车辆/电池 per 协议 live 源不明确，保留原 CSV 派生子表（标注 2023），主表明细统一到 2026。
"""
import json, pymysql, time, datetime, os

BASE = r"D:/workboddy file/dudu分析/citybike_backup"
DB = json.load(open(os.path.join(BASE, "config/backup_config.json"), encoding="utf-8"))
DB.pop("workers", None)
conn = pymysql.connect(host=DB["host"], port=DB["port"], user=DB["user"], password=DB["password"],
                       database=DB["database"], connect_timeout=15, read_timeout=600, charset="utf8mb4")
cur = conn.cursor()

NOW = int(time.time() * 1000)
TODAY = datetime.date.today()

def ms2str(v):
    if not v:
        return ""
    try:
        return (datetime.datetime.utcfromtimestamp(int(v) / 1000) + datetime.timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(v)

def q(sql, label):
    cur.execute(sql)
    return cur.fetchall()

# ── 名称映射表（小表，避免 JOIN 字段名不确定）──
print("加载名称映射表 ...")
bp_map = {r[0]: (r[1] or "—") for r in q("SELECT id, name FROM t_battery_product", "bp")}
pkg_map = {r[0]: (r[1] or "—") for r in q("SELECT id, name FROM t_exchange_rent_package", "pkg")}
site_map = {r[0]: (r[1] or "—") for r in q("SELECT id, name FROM t_site WHERE is_del=0", "site")}
emp_map = {r[0]: (r[1] or "—") for r in q("SELECT id, name FROM t_site_store_employee WHERE is_del=0", "emp")}
promo_map = {}
try:
    promo_map = {r[0]: (r[1] or "—") for r in q("SELECT id, name FROM t_promoter WHERE is_del=0", "promo")}
except Exception as e:
    print("  (t_promoter 不可用，推广员名置 —):", str(e)[:120])

# ── 1. 读旧 JSON（保留 bikes/battery 子表）──
data = json.load(open(os.path.join(BASE, "data/dashboard_data.json"), encoding="utf-8"))
uid_name = {}
for r in data.get("user", {}).get("detail", []):
    uid_name[str(r.get("user_id"))] = r.get("name") or "—"
print("user.detail 昵称索引:", len(uid_name))

# ── 2. 主协议表（live，全量）──
print("查询 live t_exchange_agreement（全量）...")
cur.execute("""
SELECT id, type, site_sale_scenario_name, user_id, user_name, user_phone,
       battery_product_id, bike_count, rent_package_id, sys_city_name,
       site_id, deposit_status, deposit_payway, deposit_fee,
       agency_id, distributor_id, sign_site_store_employee_id,
       promoter_id, create_time, activation_time, stop_time, rent_expire_time,
       status, is_contract, first_rent_package_name
FROM t_exchange_agreement WHERE is_del=0
""")
rows_raw = cur.fetchall()
conn.close()
print("协议总行数:", len(rows_raw))

# 首次签约：同 user_id 最早激活时间
first_sign_by_user = {}
for r in rows_raw:
    uid = r[3]
    act = r[19]
    if uid:
        if uid not in first_sign_by_user or (act and act < first_sign_by_user[uid]):
            first_sign_by_user[uid] = act

def remaining_days(expire_ms):
    if not expire_ms:
        return "—"
    d = (expire_ms - NOW) / 86400000.0
    return max(0, round(d)) if d > 0 else 0

def overdue_days(expire_ms):
    if not expire_ms or expire_ms >= NOW:
        return "—"
    try:
        dt = (datetime.datetime.utcfromtimestamp(int(expire_ms) / 1000) + datetime.timedelta(hours=8)).date()
        return (TODAY - dt).days
    except Exception:
        return "—"

out = []
for r in rows_raw:
    aid = r[0]; typ = r[1]; scene = r[2]; uid = r[3]; uname = r[4]; phone = r[5]
    bpid = r[6]; bike_cnt = r[7]; pkgid = r[8]; city = r[9]
    siteid = r[10]; dstatus = r[11]; dpay = r[12]; dfee = r[13]
    agy = r[14]; dist = r[15]; emp = r[16]; promo = r[17]
    ctime = r[18]; act = r[19]; stop = r[20]; expire = r[21]
    status = r[22]; is_contract = r[23]; fpkg = r[24]
    out.append({
        "agreement_id": aid,
        "type": typ or "—",
        "sales_scene": scene or "—",
        "user_id": uid,
        "user_name": uid_name.get(str(uid), uname) if uid else (uname or "—"),
        "phone": phone or "—",
        "battery_product": bp_map.get(bpid, "—"),
        "vehicle_count": bike_cnt if bike_cnt is not None else "—",
        "battery_count": data.get("user", {}).get("agreement_bat_cnt", {}).get(str(aid), "—"),
        "remaining": remaining_days(expire),
        "package_price": "—",  # live 无"当前套餐实付"单列，不编造
        "rent_package": pkg_map.get(pkgid, fpkg) if pkgid else (fpkg or "—"),
        "city": city or "—",
        "area": "—",
        "street": "—",
        "site_name": site_map.get(siteid, "—"),
        "deposit_status": dstatus or "—",
        "deposit_method": dpay or "—",
        "deposit_fee": (dfee / 100.0) if dfee else 0,
        "deposit_deduct": "—",
        "agency_id": agy if agy is not None else "—",
        "channel_id": dist if dist is not None else "—",
        "guide_id": emp if emp is not None else "—",
        "guide_name": emp_map.get(emp, "—"),
        "promoter_id": promo if promo is not None else "—",
        "promoter_name": promo_map.get(promo, "—"),
        "create": ms2str(ctime),
        "activate": ms2str(act),
        "terminate": ms2str(stop),
        "expire": ms2str(expire),
        "status": status or "—",
        "is_contract": ("是" if is_contract == 1 else ("否" if is_contract == 0 else (is_contract or "—"))),
        "auto_renew": "—",
        "is_exchange": "—",
        "is_long_term": "—",
        "battery_lease_org": "—",
        "first_sign": "是" if (uid and first_sign_by_user.get(uid) == act) else "否",
        "overdue_days": overdue_days(expire),
    })

# 保留原 bikes/battery 子表（2023 CSV 派生，标注）
data.setdefault("user", {})["agreement_detail"] = out
data["user"]["agreement_total"] = len(out)

json.dump(data, open(os.path.join(BASE, "data/dashboard_data.json"), "w", encoding="utf-8"),
            ensure_ascii=False, separators=(",", ":"))
print("WROTE agreement_detail =", len(out), "（live 2026 全量；bikes/battery 子表保留 2023 CSV 派生）")
