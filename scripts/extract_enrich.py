# -*- coding: utf-8 -*-
"""列补全：把偏薄的 detail 表补充与 DB 对齐的列（用户要求的 『ID / 订单编号 / 地址 等』）。
策略：
  · site / user / sales 三个 detail 用主键回挂新增列（保留现有派生字段 distributor_name/type_name/promoter 等，安全）。
  · finance.detail 原表无 id 字段无法回挂 → 整体按 t_expense_bill 重抽（含 账单ID / 订单编号(business_id) / 订单类型 / 支出方 / 税后 / 结算时间 / 备注）。
列名尽量与 t_site / t_exchange_agreement / t_expense_bill 真实列对齐（见 full_schema.json）。
时间(ms)统一转 'YYYY-MM-DD HH:MM:SS'；金额(分)→元。
"""
import json, pymysql, time, sys, datetime, os
from decimal import Decimal

def _jdefault(o):
    if isinstance(o, Decimal):
        return float(o)
    raise TypeError("Object of type %s is not JSON serializable" % type(o).__name__)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DB = json.load(open(os.path.join(ROOT, "config", "backup_config.json"), encoding="utf-8"))
DB.pop("workers", None)
OUT = os.path.join(ROOT, "data", "dashboard_data.json")
DETAIL_CAP = 5000

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

D = json.load(open(OUT, encoding="utf-8"))

# ---------- 1) site.detail ：主键 id 回挂 t_site 新列 ----------
smap = {}
for r in q("SELECT id, address, longitude, latitude, contact_person_name, contact_person_tel, "
          "business_id, channel_mark, community, alone_meter_number, remark "
          "FROM t_site WHERE is_del=0", "en_site", many=True) or []:
    smap[r[0]] = {
        "address": r[1], "longitude": r[2], "latitude": r[3],
        "contact_person_name": r[4], "contact_person_tel": r[5],
        "business_id": r[6], "channel_mark": r[7], "community": r[8],
        "alone_meter_number": r[9], "remark": r[10]}
det = D["site"]["detail"]
hit = 0
for r in det:
    m = smap.get(r.get("id"))
    if m:
        r.update(m); hit += 1
D["site"]["detail"] = det
print("site.detail 回挂新列行数:", hit, "/", len(det))

# ---------- 2) user.detail ：agreement_id 回挂 t_exchange_agreement 新列 ----------
amap = {}
for r in q("SELECT id, user_id, battery_product_id, rent_package_id, is_contract, "
          "contract_period, contract_type, create_time, remark, site_id "
          "FROM t_exchange_agreement WHERE is_del=0", "en_agr", many=True) or []:
    amap[r[0]] = {
        "user_id": r[1], "battery_product_id": r[2], "rent_package_id": r[3],
        "is_contract": r[4], "contract_period": r[5], "contract_type": r[6],
        "create": ms2str(r[7]), "remark": r[8], "site_id": r[9]}
ud = D["user"]["detail"]
hit = 0
for r in ud:
    m = amap.get(r.get("agreement_id"))
    if m:
        r.update(m); hit += 1
D["user"]["detail"] = ud
print("user.detail 回挂新列行数:", hit, "/", len(ud))

# ---------- 3) sales.detail ：agreement_id 回挂 t_exchange_agreement 新列 ----------
# ⚠️ t_exchange_agreement 仅有 agency_id（无 agency_name 列），代理商名需另 JOIN t_agency，此处只挂 ID。
smap2 = {}
for r in q("SELECT id, user_id, user_name, user_phone, agency_id, "
          "create_time, is_contract FROM t_exchange_agreement WHERE is_del=0", "en_agr2", many=True) or []:
    smap2[r[0]] = {
        "user_id": r[1], "user_name": r[2], "user_phone": r[3],
        "agency_id": r[4],
        "create": ms2str(r[5]), "is_contract": r[6]}
sd = D["sales"]["detail"]
hit = 0
for r in sd:
    m = smap2.get(r.get("agreement_id"))
    if m:
        r.update(m); hit += 1
D["sales"]["detail"] = sd
print("sales.detail 回挂新列行数:", hit, "/", len(sd))

# ---------- 4) finance.detail ：整体重抽（原表无 id 无法回挂）----------
rows = q(
    "SELECT id, business_id, business_type, expense_name, expense_type, in_unit, out_unit_name, "
    "fee, after_taxes_fee, bill_status, is_refund, create_time, settle_time, remark "
    "FROM t_expense_bill WHERE is_del=0 ORDER BY create_time DESC LIMIT %d" % DETAIL_CAP,
    "en_fin", many=True) or []
F = D.setdefault("finance", {})
F["detail"] = [{
    "id": r[0], "business_id": r[1], "business_type": r[2],
    "name": r[3], "expense_type": r[4], "in_unit": r[5], "out_unit_name": r[6],
    "fee": float(r[7] or 0) / 100.0, "after_taxes_fee": float(r[8] or 0) / 100.0,
    "status": r[9], "is_refund": r[10], "create": ms2str(r[11]),
    "settle": ms2str(r[12]), "remark": r[13]} for r in rows]
D["finance"] = F
print("finance.detail 重抽行数:", len(rows), "(含 账单ID/订单编号/订单类型/支出方/税后/结算时间/备注)")

json.dump(D, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=_jdefault)
conn.close()
print("ERRORS:", len(ERR))
for e in ERR:
    print("  -", e)
print("DONE extract_enrich")
