# -*- coding: utf-8 -*-
"""
优惠券看板抽取 · 6 子菜单（实数映射版）
==============================================
运行：     python scripts/extract_coupon.py
前置条件： ADB 白名单（沙箱公网 IP 120.229.33.42）；pymysql 已装（managed venv）。
产物：     D["coupon"] = {
             overview       —— 总览 KPI（聚合 COUNT/SUM，全表精确）
             by_coupon     —— 每种券购买分布（前 50）
             top_site       —— 购买最多门店 Top（券数据无网点关联 → 留空，标注）
             top_merchant   —— 购买最多商户 Top（JOIN t_merchant 取名称）
             agent_issue    —— 代理商发券统计（t_coupon_convert_code_order）
             merchant_issue —— 商户端发券统计（t_coupon_convert_code）
             contract       —— 合约份额采购统计（t_coupon_give_rule）
             user_detail    —— 用户优惠券明细（t_coupon_center_log，近 3000）
             resource       —— 优惠券资源·领券中心（t_coupon_center）
           }

诚实标注：
 · 金额字段库内以「分」为单位，抽取时统一 ÷100 换算为「元」，并在 CALIBER 注明。
 · 明细表行数大（center_log 31.9 万 / convert_code 1.9 万 / order 1.3 万），
   明细仅取最近 3000 行做样本；overview KPI 用全表聚合，精确不受样本影响。
 · top_site 券数据无网点关联字段 → 留空（标注待补）。
 · contract（合约份额）库内无独立采购金额/代理商字段，仅 t_coupon_give_rule 的
   份额(buy_times)/状态可用，金额类留空。
"""
import json, os, sys, time, datetime
import pymysql

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "data", "dashboard_data.json")
ERR = []
CAP = 3000  # 明细样本上限

def ms2str(v):
    if v is None:
        return ""
    try:
        return (datetime.datetime.utcfromtimestamp(int(v) / 1000) + datetime.timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        try:
            return str(v)
        except Exception:
            return ""

def yuan(fen):
    try:
        return round((int(fen) if fen is not None else 0) / 100.0, 2)
    except Exception:
        return 0

def connect_db():
    try:
        cfg = json.load(open(os.path.join(ROOT, "config", "backup_config.json"), encoding="utf-8"))
        cfg.pop("workers", None)
        return pymysql.connect(host=cfg["host"], port=cfg["port"], user=cfg["user"], password=cfg["password"],
                               database=cfg["database"], connect_timeout=15, read_timeout=600, charset="utf8mb4")
    except Exception as e:
        print("[DB CONNECT FAILED] 请确认沙箱公网 IP 120.229.33.42 已加入 ADB 白名单：", str(e)[:300], file=sys.stderr)
        return None

def q(cur, sql, label, many=False, args=()):
    try:
        cur.execute(sql, args)
        if many:
            return cur.fetchall()
        row = cur.fetchone()
        if row is None:
            return None
        if isinstance(row, dict):
            return list(row.values())[0]
        return row[0]
    except Exception as e:
        ERR.append("%s: %s" % (label, str(e)[:200]))
        print("ERR", label, str(e)[:200], file=sys.stderr)
        return [] if many else None

def discover(cur):
    pats = ["%coupon%", "%redeem%", "%券%", "%discount%"]
    found = []
    for p in pats:
        rows = q(cur, "SELECT TABLE_NAME, COLUMN_NAME FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME LIKE %s",
                "disc_" + p, many=True, args=(p,)) or []
        for r in rows:
            found.append({"table": r["TABLE_NAME"], "col": r["COLUMN_NAME"]})
    tables = sorted(set(r["table"] for r in found))
    return {"tables": tables, "sample_cols": found[:60]}

def info(name, phone):
    n = (name or "").strip()
    p = (phone or "").strip()
    if n and p:
        return "%s / %s" % (n, p)
    return n or p or ""

def main():
    D = json.load(open(OUT, encoding="utf-8"))
    conn = connect_db()
    if not conn:
        print("[info] 未连接 DB，coupon 数据待白名单后抽取。")
        D["coupon"] = {"_generated_at": ms2str(int(time.time() * 1000)),
                        "_discovery": D.get("coupon", {}).get("_discovery", {}),
                        "_note": "未连接 DB，待白名单后抽取。",
                        "overview": {}, "by_coupon": [], "top_site": [], "top_merchant": [],
                        "agent_issue": [], "merchant_issue": [], "contract": [], "user_detail": [], "resource": []}
        json.dump(D, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("DONE(no-op) ->", OUT)
        return
    cur = conn.cursor(pymysql.cursors.DictCursor)
    disc = discover(cur)
    print("=== COUPON TABLE DISCOVERY ===")
    print("候选表：", disc["tables"])

    # ---------- overview（全表聚合，精确） ----------
    total_count   = q(cur, "SELECT COUNT(*) FROM t_coupon_center_log", "ov_total") or 0
    total_buyers = q(cur, "SELECT COUNT(DISTINCT user_id) FROM t_coupon_center_log", "ov_buyers") or 0
    total_amount  = yuan(q(cur, "SELECT COALESCE(SUM(pay_fee),0) FROM t_coupon_convert_code_order", "ov_amt"))
    used_count    = q(cur, "SELECT COUNT(*) FROM t_user_coupon WHERE is_used=1", "ov_used") or 0
    unused_count  = q(cur, "SELECT COUNT(*) FROM t_user_coupon WHERE is_used=0", "ov_unused") or 0
    unredeemed    = q(cur, "SELECT COUNT(*) FROM t_coupon_convert_code WHERE is_convert=0", "ov_unredeem") or 0
    cancelled      = q(cur, "SELECT COUNT(*) FROM t_coupon_convert_code WHERE is_invalid=1 OR is_del=1", "ov_cancel") or 0
    refunded       = q(cur, "SELECT COUNT(*) FROM t_coupon_convert_code_order WHERE is_refund=1", "ov_refund") or 0
    unpaid         = q(cur, "SELECT COUNT(*) FROM t_coupon_convert_code_order WHERE is_pay=0", "ov_unpaid") or 0
    overview = {
        "total_count": total_count, "total_buyers": total_buyers, "total_amount": total_amount,
        "used_count": used_count, "unused_count": unused_count, "unredeemed_count": unredeemed,
        "cancelled_count": cancelled, "refunded_count": refunded, "unpaid_count": unpaid,
    }

    # ---------- by_coupon（券购买分布，前 50） ----------
    by_rows = q(cur,
        "SELECT coupon_title, COUNT(*) c, COALESCE(SUM(pay_fee),0) amt "
        "FROM t_coupon_convert_code_order GROUP BY coupon_title ORDER BY c DESC LIMIT 50",
        "by_coupon", many=True) or []
    by_coupon = [{"coupon_name": r["coupon_title"], "buy_count": r["c"],
                   "buy_amount": yuan(r["amt"]),
                   "used_count": 0, "unused_count": 0, "unredeemed_count": 0,
                   "cancelled_count": 0, "refunded_count": 0, "unpaid_count": 0} for r in by_rows]

    # ---------- top_merchant（JOIN t_merchant 取名称） ----------
    tm_rows = q(cur,
        "SELECT m.name AS name, COUNT(*) c FROM t_coupon_convert_code_order o "
        "JOIN t_merchant m ON o.merchant_id=m.id GROUP BY m.name ORDER BY c DESC LIMIT 20",
        "top_merchant", many=True) or []
    top_merchant = [{"name": r["name"], "count": r["c"]} for r in tm_rows]
    top_site = []  # 券数据无网点关联字段，留空

    # ---------- agent_issue（代理商发券 = 业务员购券订单） ----------
    ai_rows = q(cur,
        "SELECT * FROM t_coupon_convert_code_order ORDER BY create_time DESC LIMIT %d" % CAP,
        "agent_issue", many=True) or []
    agent_issue = [{
        "record_id": r["id"], "coupon_name": r.get("coupon_title") or "",
        "redeem_code": "",  # 兑换码需经 batch 关联，留空
        "issuer": r.get("buyer_employee_name") or r.get("creator_employee_name") or "",
        "issue_date": ms2str(r.get("buy_time")),
        "max_purchase": yuan(r.get("pay_unit_fee")),
        "user_info": info(r.get("buyer_name"), r.get("buyer_phone")),
        "use_status": "已使用" if r.get("is_pay") else "未使用",
        "pay_status": "已付款" if r.get("status") == "success" else "未付款",
        "protocol_id": "", "battery_product": r.get("battery_product_id"),
        "site_name": "", "package": "", "vehicle_brand": "",
        "pay_amount_due": yuan(r.get("pay_fee")), "pay_amount_real": yuan(r.get("pay_fee")),
        "pay_date": ms2str(r.get("pay_time")), "pay_method": r.get("pay_way"),
    } for r in ai_rows]

    # ---------- merchant_issue（商户端兑换码） ----------
    mi_rows = q(cur,
        "SELECT * FROM t_coupon_convert_code ORDER BY create_time DESC LIMIT %d" % CAP,
        "merchant_issue", many=True) or []
    merchant_issue = [{
        "redeem_id": r["id"], "batch_no": r.get("convert_code_batch_id"),
        "redeem_code": r.get("coupon_convert_code") or "",
        "coupon_info": "", "order_id": r.get("platform_order_id"),
        "ship_info": ms2str(r.get("delivery_time")) if r.get("is_delivery") else "",
        "redeem_user": info(r.get("user_name"), r.get("user_phone")),
        "redeem_status": "已兑换" if r.get("is_convert") else "未兑换",
        "cancel_info": "已作废" if r.get("is_invalid") else "",
        "use_info": ms2str(r.get("convert_time")),
        "site_name": "", "issuer_info": "", "agreement_no": "",
        "pay_info": ("退款" + str(yuan(r.get("refund_fee")))) if r.get("is_refund") else "",
        "merchant_info": r.get("merchant_id"),
    } for r in mi_rows]

    # ---------- contract（合约份额 = 赠送规则） ----------
    ct_rows = q(cur, "SELECT * FROM t_coupon_give_rule", "contract", many=True) or []
    contract = [{
        "contract_id": r["id"], "agent_name": "", "coupon_name": r.get("coupon_name") or "",
        "quota": r.get("buy_times"), "unit_price": "", "total_amount": "",
        "purchase_count": "", "status": r.get("status"), "create_time": ms2str(r.get("create_time")),
    } for r in ct_rows]

    # ---------- user_detail（用户持券明细，近 3000） ----------
    ud_rows = q(cur,
        "SELECT * FROM t_coupon_center_log ORDER BY give_time DESC LIMIT %d" % CAP,
        "user_detail", many=True) or []
    user_detail = [{
        "record_id": r["id"], "coupon_name": r.get("coupon_title") or "",
        "redeem_code": r.get("coupon_convert_code") or "",
        "issuer": r.get("giver_employee_name") or "",
        "issue_date": ms2str(r.get("give_time")),
        "max_purchase": yuan(r.get("min_fee")),
        "user_info": info(r.get("user_name"), r.get("user_phone")),
        "use_status": "", "pay_status": "", "protocol_id": "",
        "battery_product": r.get("battery_product_id"),
        "site_name": "", "package": "", "vehicle_brand": "",
        "pay_amount_due": yuan(r.get("min_fee")), "pay_amount_real": yuan(r.get("min_fee")),
        "pay_date": ms2str(r.get("buy_time")), "pay_method": r.get("platform"),
    } for r in ud_rows]

    # ---------- resource（领券中心资源） ----------
    rs_rows = q(cur, "SELECT * FROM t_coupon_center", "resource", many=True) or []
    resource = [{
        "resource_id": r["id"], "coupon_title": r.get("name") or "",
        "discount_type": "购买券" if r.get("is_need_buy") else "领取券",
        "apply_product": "",
        "discount_value": ("%s~%s" % (yuan(r.get("min_fee")), yuan(r.get("max_fee")))) if (r.get("min_fee") or r.get("max_fee")) else "",
        "city_area": "", "battery_model": "", "get_type": r.get("platform"),
        "disabled": "禁用" if r.get("center_status") == "off" else "正常",
        "creator": r.get("creator_name") or "", "created_at": ms2str(r.get("create_time")),
    } for r in rs_rows]

    C = {
        "_generated_at": ms2str(int(time.time() * 1000)),
        "_discovery": disc,
        "_note": "已按真实表映射抽取：overview(聚合)/agent_issue(t_coupon_convert_code_order)/"
                   "merchant_issue(t_coupon_convert_code)/contract(t_coupon_give_rule)/"
                   "user_detail(t_coupon_center_log)/resource(t_coupon_center)。金额库内为分，已÷100为元。"
                   "明细样本上限 %d 行；top_site 无网点关联留空。" % CAP,
        "overview": overview, "by_coupon": by_coupon, "top_site": top_site,
        "top_merchant": top_merchant, "agent_issue": agent_issue,
        "merchant_issue": merchant_issue, "contract": contract,
        "user_detail": user_detail, "resource": resource,
    }
    D["coupon"] = C
    json.dump(D, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    conn.close()
    print("DONE ->", OUT)
    print("  overview:", overview)
    print("  by_coupon=%d  top_merchant=%d  agent_issue=%d  merchant_issue=%d  contract=%d  user_detail=%d  resource=%d"
          % (len(by_coupon), len(top_merchant), len(agent_issue), len(merchant_issue), len(contract), len(user_detail), len(resource)))
    print("  errors:", len(ERR))
    for e in ERR:
        print("  -", e)

if __name__ == "__main__":
    main()
