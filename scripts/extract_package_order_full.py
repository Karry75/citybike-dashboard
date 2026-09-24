# -*- coding: utf-8 -*-
"""
全量抽取「套餐购买订单明细」：
  t_user_exchange_package_order   (电量卡 / 电量包, is_del=0, 约 177 万)
  t_user_exchange_rent_package_order (租期卡, is_del=0, 约 46 万)
合并为统一的 32 列表格，写入 data/package_order_full.jsonl（每行一个 JSON）。
再由 build_package_order_pack.py 转成列式 gz 包。

统一列（与用户提供的 CSV 对齐，32 列）：
  purchase_order_id, order_type, user_id, user_phone, exchange_agreement_id,
  battery_product, sign_site_id, sign_site_name, sign_agency_id, sign_agency_name,
  order_status, order_total_amount, brand_discount_amount, coupon_id, coupon_center_id,
  coupon_name, coupon_amount, order_payable_amount, order_actual_paid, is_replenish_rent,
  replenish_amount, create_time, remark, is_paid, pay_time, pay_method, pay_trade_no,
  refund_amount, refund_time, refund_reason, refund_operator, refund_trade_no

说明（库内无对应字段，按诚实原则填空）：
  - 是否补缴租金 / 补缴金额：库内无该字段，统一填 '否' / 0
  - 退款操作人：库内无该字段，填 '—'
  - 退款流水号：库内无该字段，填 '—'
  - 支付流水号：两订单表均无 trade_no，取 pay_way_table_id（银联支付记录 id）作为代理
  - 签约代理商名称：唯一来源是 t_site_update_agency_log（t_agency 表不存在），尽力解析，缺失填 '—'
"""
import json, pymysql, sys, os, time, datetime

ROOT = r"D:/workboddy file/dudu分析/citybike_backup"
DB = json.load(open(os.path.join(ROOT, "config", "backup_config.json"), encoding="utf-8"))
DB.pop("workers", None)
OUT_JSONL = os.path.join(ROOT, "data", "package_order_full.jsonl")
COLS_FILE = os.path.join(ROOT, "data", "package_order_cols.json")

# 统一列顺序（extract / pack / 前端 三处必须一致）
COLS = ["purchase_order_id","order_type","user_id","user_phone","exchange_agreement_id",
        "battery_product","sign_site_id","sign_site_name","sign_agency_id","sign_agency_name",
        "order_status","order_total_amount","brand_discount_amount","coupon_id","coupon_center_id",
        "coupon_name","coupon_amount","order_payable_amount","order_actual_paid","is_replenish_rent",
        "replenish_amount","create_time","remark","is_paid","pay_time","pay_method","pay_trade_no",
        "refund_amount","refund_time","refund_reason","refund_operator","refund_trade_no"]

LIMIT = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 0  # 0 = 全量

def ms2str(v):
    if not v:
        return ""
    try:
        return (datetime.datetime.fromtimestamp(int(v) / 1000, tz=datetime.timezone.utc)
                + datetime.timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(v)

def yuan(v):
    if v is None or v == "":
        return 0
    try:
        return round(float(v) / 100.0, 2)
    except Exception:
        return 0

PAY_WAY_CN = {
    "unionpay_wechatmini": "微信小程序(银联)",
    "unionpay_alipaymini": "支付宝小程序(银联)",
    "unionpay_app": "APP(银联)",
    "wechat": "微信支付",
    "alipay": "支付宝",
    "balance": "余额支付",
}
def pay_way_cn(v):
    return PAY_WAY_CN.get(v, v or "—")

def parse_deduct_money(rule):
    if not rule:
        return 0
    try:
        d = json.loads(rule)
        return yuan(d.get("money"))
    except Exception:
        return 0

t0 = time.time()
conn = pymysql.connect(host=DB["host"], port=DB["port"], user=DB["user"], password=DB["password"],
                       database=DB["database"], connect_timeout=60, read_timeout=1800, charset="utf8mb4",
                       cursorclass=pymysql.cursors.SSCursor)
cur = conn.cursor(pymysql.cursors.DictCursor)
ERR = []

def q(sql, label):
    try:
        cur.execute(sql)
        return cur.fetchall()
    except Exception as e:
        ERR.append("%s: %s" % (label, str(e)[:200]))
        print("ERR", label, str(e)[:200], file=sys.stderr)
        return []

def log(msg):
    print("[%7.1fs] %s" % (time.time() - t0, msg), flush=True)

# ── 维度映射 ──
log("加载维度映射…")
bp = {}
for r in q("SELECT id, name FROM t_battery_product WHERE is_del=0", "m_bp"):
    bp[r["id"]] = r["name"] or "—"

site_map = {}
for r in q("SELECT id, name, agency_id FROM t_site WHERE is_del=0", "m_site"):
    site_map[r["id"]] = (r["name"] or "—", r["agency_id"] or 0)

agr_map = {}
for r in q("SELECT id, site_id, agency_id FROM t_exchange_agreement WHERE is_del=0", "m_agr"):
    agr_map[r["id"]] = (r["site_id"] or 0, r["agency_id"] or 0)

# 代理商名称：唯一来源 t_site_update_agency_log
#   该表列为 before_agency_id/before_agency_name/after_agency_id/after_agency_name
#   按 create_time DESC 扫描，对每个出现的 agency_id 取首次（即最新）出现的名称
agency_name = {}
try:
    cnt = list(q("SELECT COUNT(*) AS c FROM t_site_update_agency_log WHERE is_del=0", "m_agrlog_cnt"))
    n = cnt[0]["c"] if cnt else 0
    if n and n <= 2000000:
        for r in q("SELECT before_agency_id, before_agency_name, after_agency_id, after_agency_name "
                   "FROM t_site_update_agency_log WHERE is_del=0 ORDER BY create_time DESC", "m_agrlog"):
            for aid, aname in ((r.get("before_agency_id"), r.get("before_agency_name")),
                               (r.get("after_agency_id"), r.get("after_agency_name"))):
                if aid and aid not in agency_name and aname:
                    agency_name[aid] = aname
        log("代理商名称日志 %d 条，解析到 %d 个代理商名" % (n, len(agency_name)))
    else:
        log("代理商日志 %s 条，跳过名称解析（仅保留代理商ID）" % n)
except Exception as e:
    log("代理商名称解析失败: %s" % e)

# 用户优惠券（券名称 / 抵扣金额 / 领券中心日志id）
uc_map = {}
for r in q("SELECT id, coupon_title, coupon_center_log_id, deduct_rule FROM t_user_coupon WHERE is_del=0", "m_uc"):
    uc_map[r["id"]] = (r["coupon_title"] or "—", r["coupon_center_log_id"] or 0, parse_deduct_money(r["deduct_rule"]))

# 领券中心日志 → 领券中心ID
ccl_map = {}
for r in q("SELECT id, coupon_center_id FROM t_coupon_center_log WHERE is_del=0", "m_ccl"):
    ccl_map[r["id"]] = r["coupon_center_id"] or 0

def resolve_site(agreement_id):
    """返回 (site_id, site_name, agency_id)"""
    a = agr_map.get(agreement_id)
    if not a:
        return (0, "—", 0)
    site_id = a[0]
    agency_id = a[1]
    site = site_map.get(site_id)
    site_name = site[0] if site else "—"
    if not agency_id and site:
        agency_id = site[1]
    return (site_id, site_name, agency_id)

def resolve_agency_name(agency_id):
    if not agency_id:
        return "—"
    return agency_name.get(agency_id, "—")

def coupon_fields(user_coupon_id):
    if not user_coupon_id:
        return (0, 0, "—", 0)
    uc = uc_map.get(user_coupon_id)
    if not uc:
        return (user_coupon_id, 0, "—", 0)
    title, ccl_id, money = uc
    center_id = ccl_map.get(ccl_id, 0)
    return (user_coupon_id, center_id, title, money)

# ── 主抽取 ──
log("抽取电量卡订单…")
def build_common(row, order_type, total, brand_disc, fee, real_fee, remark):
    agreement_id = row.get("exchange_agreement_id") or 0
    site_id, site_name, agency_id = resolve_site(agreement_id)
    cid, center_id, coupon_name, coupon_money = coupon_fields(row.get("user_coupon_id") or 0)
    is_pay = row.get("is_pay")
    total_y = yuan(total); brand_y = yuan(brand_disc); coupon_y = coupon_money
    payable = round(max(total_y - brand_y - coupon_y, 0.0), 2)
    return {
        "purchase_order_id": row.get("id"),
        "order_type": order_type,
        "user_id": row.get("user_id"),
        "user_phone": row.get("user_phone") or "—",
        "exchange_agreement_id": agreement_id,
        "battery_product": bp.get(row.get("battery_product_id"), "—"),
        "sign_site_id": site_id,
        "sign_site_name": site_name,
        "sign_agency_id": agency_id,
        "sign_agency_name": resolve_agency_name(agency_id),
        "order_status": row.get("order_status") or "—",
        "order_total_amount": total_y,
        "brand_discount_amount": brand_y,
        "coupon_id": cid,
        "coupon_center_id": center_id,
        "coupon_name": coupon_name,
        "coupon_amount": coupon_y,
        "order_payable_amount": payable,
        "order_actual_paid": yuan(real_fee),
        "is_replenish_rent": "否",
        "replenish_amount": 0,
        "create_time": ms2str(row.get("create_time")),
        "remark": remark or "—",
        "is_paid": "是" if is_pay else "否",
        "pay_time": ms2str(row.get("pay_time")),
        "pay_method": pay_way_cn(row.get("pay_way")),
        "pay_trade_no": row.get("pay_way_table_id") or "—",
        "refund_amount": yuan(row.get("refund_fee")),
        "refund_time": ms2str(row.get("refund_time")),
        "refund_reason": row.get("modify_refund_fee_reason") or "—",
        "refund_operator": "—",
        "refund_trade_no": "—",
    }

count = 0
with open(OUT_JSONL, "w", encoding="utf-8") as f:
    sql_pkg = ("SELECT id, exchange_agreement_id, battery_product_id, user_id, user_phone, "
               "package_name, total_fee, brand_discount_fee, fee, real_fee, is_pay, pay_way, "
               "pay_time, pay_way_table_id, user_coupon_id, order_status, refund_fee, "
               "modify_refund_fee_reason, refund_time, create_time "
               "FROM t_user_exchange_package_order WHERE is_del=0 ORDER BY create_time DESC")
    if LIMIT:
        sql_pkg += " LIMIT %d" % LIMIT
    for r in q(sql_pkg, "pkg"):
        d = build_common(r, "电量卡", r.get("total_fee"), r.get("brand_discount_fee"),
                         r.get("fee"), r.get("real_fee"), None)
        f.write(json.dumps(d, ensure_ascii=False, separators=(",", ":")) + "\n")
        count += 1
    log("电量卡 %d 行" % count)

    sql_rent = ("SELECT id, exchange_agreement_id, battery_product_id, user_id, user_phone, "
                "package_name, package_total_fee, package_brand_discount_fee, package_fee, package_real_fee, "
                "is_pay, pay_way, pay_time, pay_way_table_id, user_coupon_id, order_status, refund_fee, "
                "modify_refund_fee_reason, refund_time, create_time, package_remark "
                "FROM t_user_exchange_rent_package_order WHERE is_del=0 ORDER BY create_time DESC")
    if LIMIT:
        sql_rent += " LIMIT %d" % LIMIT
    n0 = count
    for r in q(sql_rent, "rent"):
        d = build_common(r, "租期卡", r.get("package_total_fee"), r.get("package_brand_discount_fee"),
                         r.get("package_fee"), r.get("package_real_fee"), r.get("package_remark"))
        f.write(json.dumps(d, ensure_ascii=False, separators=(",", ":")) + "\n")
        count += 1
    log("租期卡 +%d 行" % (count - n0))

cur.close(); conn.close()

with open(COLS_FILE, "w", encoding="utf-8") as f:
    json.dump(COLS, f, ensure_ascii=False, indent=2)

log("完成：共 %d 行 → %s" % (count, OUT_JSONL))
if ERR:
    log("⚠️ 有 %d 个维度查询警告（已降级为 '—'）：%s" % (len(ERR), ERR[:3]))
print("DONE rows=%d" % count)
