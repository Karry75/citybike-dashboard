# -*- coding: utf-8 -*-
"""
优惠券看板·增量刷新抽取（全量，无样本上限）
====================================================
运行：     python scripts/extract_coupon_refresh.py
前置条件： ADB 白名单（沙箱公网 IP）；pymysql 已装（managed venv）。
产物：     data/coupon_refresh.json  —— 仅 coupon 段，供 merge_coupon_refresh.py 注入 lite。

数据诚实声明：
 · 金额字段库内以「分」为单位，抽取时统一 ÷100 换算为「元」。
 · agent_issue = t_coupon_center_log(platform='agency') JOIN t_coupon_convert_code（约 7,620 行，无上限）
   merchant_issue = t_coupon_convert_code JOIN 订单/协议/服务单（19,181 行，53 列对齐 CSV，全量）
   contract = t_contract_scheme_order（合约销售单，全量，23 列对齐 CSV）
 · 代理商发券 32 列对齐用户 CSV：发放记录来自 center_log；协议/网点/电池/套餐/品牌经 t_user_coupon->t_exchange_agreement 关联；
   发放人手机号受限于库内无直接映射，优先按 giver_employee_id 关联 t_site_store_employee，其次按姓名兜底，覆盖率有限。
 · t_agency 表不存在 → 代理商仅能提供 agency_id（原始 ID），无名称；商户名称经 LEFT JOIN t_merchant 补全。
 · coupon_center_id 经 LEFT JOIN t_coupon_center 补全优惠券名称（merchant_issue）。
 · user_detail / resource 保留原映射（resource 全量 327；user_detail 取近 5000 样本，避免 319159 行撑爆 lite）。
"""
import json, os, sys, time, datetime
import pymysql

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "data", "coupon_refresh.json")
ERR = []
USER_DETAIL_CAP = 5000  # 仅 user_detail 取样本（319159 行全量会撑爆 lite；用户未要求 C5 全量）

def ms2str(v):
    if v is None or v == 0 or v == "0":
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

def b(v):
    """把 '0'/'1'/0/1 转成 JSON 布尔（供前端 tag 渲染）"""
    return str(v) == "1" or v == 1 or v is True

def connect_db():
    try:
        cfg = json.load(open(os.path.join(ROOT, "config", "backup_config.json"), encoding="utf-8"))
        cfg.pop("workers", None)
        return pymysql.connect(host=cfg["host"], port=cfg["port"], user=cfg["user"], password=cfg["password"],
                               database=cfg["database"], connect_timeout=15, read_timeout=600, charset="utf8mb4")
    except Exception as e:
        print("[DB CONNECT FAILED]", str(e)[:300], file=sys.stderr)
        return None

def q(cur, sql, label, many=False, args=()):
    try:
        cur.execute(sql, args)
        if many:
            return cur.fetchall()
        row = cur.fetchone()
        return list(row.values())[0] if row else None
    except Exception as e:
        ERR.append("%s: %s" % (label, str(e)[:200]))
        print("ERR", label, str(e)[:200], file=sys.stderr)
        return [] if many else None

def main():
    conn = connect_db()
    if not conn:
        print("[info] 未连接 DB，无法抽取。")
        return
    cur = conn.cursor(pymysql.cursors.DictCursor)

    # ---------- overview（全表聚合，精确，无 cap） ----------
    total_count   = q(cur, "SELECT COUNT(*) FROM t_coupon_center_log", "ov_total") or 0
    total_buyers  = q(cur, "SELECT COUNT(DISTINCT user_id) FROM t_coupon_center_log", "ov_buyers") or 0
    total_amount  = yuan(q(cur, "SELECT COALESCE(SUM(pay_fee),0) FROM t_coupon_convert_code_order WHERE is_pay=1", "ov_amt"))
    used_count    = q(cur, "SELECT COUNT(*) FROM t_user_coupon WHERE is_used=1", "ov_used") or 0
    unused_count  = q(cur, "SELECT COUNT(*) FROM t_user_coupon WHERE is_used=0", "ov_unused") or 0
    unredeemed    = q(cur, "SELECT COUNT(*) FROM t_coupon_convert_code WHERE is_convert=0", "ov_unredeem") or 0
    cancelled     = q(cur, "SELECT COUNT(*) FROM t_coupon_convert_code WHERE is_invalid=1 OR is_del=1", "ov_cancel") or 0
    refunded      = q(cur, "SELECT COUNT(*) FROM t_coupon_convert_code_order WHERE is_refund=1", "ov_refund") or 0
    unpaid        = q(cur, "SELECT COUNT(*) FROM t_coupon_convert_code_order WHERE is_pay=0", "ov_unpaid") or 0
    overview = {
        "total_count": total_count, "total_buyers": total_buyers, "total_amount": total_amount,
        "used_count": used_count, "unused_count": unused_count, "unredeemed_count": unredeemed,
        "cancelled_count": cancelled, "refunded_count": refunded, "unpaid_count": unpaid,
    }

    # ---------- by_coupon（券购买分布，TOP100） ----------
    bc_rows = q(cur,
        "SELECT coupon_title, COUNT(*) c, COALESCE(SUM(pay_fee),0) amt "
        "FROM t_coupon_convert_code_order GROUP BY coupon_title ORDER BY c DESC LIMIT 100",
        "by_coupon", many=True) or []
    by_coupon = [{"coupon_name": r["coupon_title"], "buy_count": r["c"],
                  "buy_amount": yuan(r["amt"]),
                  "used_count": 0, "unused_count": 0, "unredeemed_count": 0,
                  "cancelled_count": 0, "refunded_count": 0, "unpaid_count": 0} for r in bc_rows]

    # ---------- top_merchant（购买最多商户 TOP20，JOIN 取名称） ----------
    tm_rows = q(cur,
        "SELECT m.name AS name, COUNT(*) c FROM t_coupon_convert_code_order o "
        "LEFT JOIN t_merchant m ON o.merchant_id=m.id GROUP BY m.name ORDER BY c DESC LIMIT 20",
        "top_merchant", many=True) or []
    top_merchant = [{"name": r["name"] or "（无商户）", "count": r["c"]} for r in tm_rows]
    top_site = []  # 券数据无网点关联字段，留空

    # ---------- C2 代理商发券统计（按 CSV 32 列，platform='agency' 全量） ----------
    # 数据源：t_coupon_center_log(platform='agency') -> t_coupon_convert_code -> t_user_coupon ->
    #        t_exchange_agreement(按 target_ids/最近匹配) -> site/battery_product/rent_package/bike_brand ->
    #        t_coupon_convert_code_order(支付，聚合去重)
    ai_main = q(cur,
        "SELECT "
        "  log.id AS issue_record_id, "
        "  cc.name AS coupon_name, "
        "  c.coupon_convert_code AS coupon_code, "
        "  log.giver_employee_id AS issuer_id, "
        "  log.giver_employee_name AS issuer_name, "
        "  emp.phone AS issuer_phone_emp, "
        "  log.give_time AS issue_time, "
        "  cc.is_need_buy AS is_need_buy, "
        "  c.user_id AS receiver_id, "
        "  c.user_name AS receiver_name, "
        "  c.user_phone AS receiver_phone, "
        "  c.is_convert AS is_convert, "
        "  c.is_invalid AS is_invalid, "
        "  c.is_del AS is_del, "
        "  uc.is_used AS is_used, "
        "  uc.target_ids AS target_ids, "
        "  c.is_refund AS is_refund, "
        "  c.refund_fee AS refund_fee, "
        "  c.refund_time AS refund_time, "
        "  o.pay_fee AS pay_fee, "
        "  o.is_pay AS is_pay, "
        "  o.pay_time AS pay_time, "
        "  o.pay_way AS pay_way, "
        "  o.trade_no AS trade_no, "
        "  o.pay_remark AS pay_remark, "
        "  uc.user_id AS agreement_user_id "
        "FROM t_coupon_center_log log "
        "INNER JOIN t_coupon_convert_code c ON log.coupon_convert_code=c.coupon_convert_code "
        "LEFT JOIN t_user_coupon uc ON c.coupon_convert_code=uc.coupon_convert_code "
        "LEFT JOIN t_coupon_center cc ON c.coupon_center_id=cc.id "
        "LEFT JOIN t_site_store_employee emp ON log.giver_employee_id=emp.id "
        "LEFT JOIN ("
        "  SELECT coupon_center_log_id, "
        "    COALESCE(MAX(CASE WHEN is_pay=1 THEN pay_fee END), MAX(pay_fee)) AS pay_fee, "
        "    MAX(is_pay) AS is_pay, "
        "    COALESCE(MAX(CASE WHEN is_pay=1 THEN pay_time END), MAX(pay_time)) AS pay_time, "
        "    COALESCE(MAX(CASE WHEN is_pay=1 THEN pay_way END), MAX(pay_way)) AS pay_way, "
        "    COALESCE(MAX(CASE WHEN is_pay=1 THEN trade_no END), MAX(trade_no)) AS trade_no, "
        "    COALESCE(MAX(CASE WHEN is_pay=1 THEN pay_remark END), MAX(pay_remark)) AS pay_remark "
        "  FROM t_coupon_convert_code_order GROUP BY coupon_center_log_id"
        ") o ON log.id=o.coupon_center_log_id "
        "WHERE log.platform='agency' "
        "ORDER BY log.give_time DESC",
        "agent_issue_main", many=True) or []

    # 批量拉取涉及用户的全部协议（ADB IN 限制 4000，分块）
    user_ids = list(set(str(r.get("agreement_user_id") or r.get("receiver_id") or "") for r in ai_main) - {""})
    agreements = {}
    BATCH = 3000
    for i in range(0, len(user_ids), BATCH):
        chunk = user_ids[i:i+BATCH]
        uid_sql = ",".join(chunk)
        ag_rows = q(cur,
            "SELECT id, user_id, status, battery_product_id, site_id, rent_package_id, "
            "bike_brand_id, first_rent_package_name, create_time "
            "FROM t_exchange_agreement WHERE user_id IN (%s)" % uid_sql,
            "agent_issue_agreements_%d" % i, many=True) or []
        for ag in ag_rows:
            uid = ag.get("user_id")
            agreements.setdefault(uid, []).append(ag)

    def pick_agreement(r):
        uid = r.get("agreement_user_id") or r.get("receiver_id")
        ags = agreements.get(uid, [])
        if not ags:
            return None
        target_ids = (r.get("target_ids") or "").replace("[", "").replace("]", "").replace("\"", "").split(",")
        target_ids = [x.strip() for x in target_ids if x.strip()]
        # 优先匹配 rent_package_id 在 target_ids 中
        for ag in ags:
            if str(ag.get("rent_package_id") or "") in target_ids:
                return ag
        # 其次匹配 first_rent_package_id（兼容旧协议）
        for ag in ags:
            if str(ag.get("first_rent_package_id") or "") in target_ids:
                return ag
        #  fallback 取最近创建
        return sorted(ags, key=lambda x: x.get("create_time") or 0, reverse=True)[0]

    def ag_status_cn(s):
        return {
            "working": "生效中", "stop": "已终止", "stopped": "已终止",
            "cancelled": "已取消", "paused": "已暂停", "owe_rent": "欠租",
            "unsubscribing": "退约中", "wait_activate": "待激活", "invalid": "已失效"
        }.get(s, s or "")

    agent_issue = []
    for r in ai_main:
        ag = pick_agreement(r)
        issuer_phone = r.get("issuer_phone_emp") or ""
        usage_status = "已作废" if b(r.get("is_invalid")) or b(r.get("is_del")) else \
                       "已使用" if b(r.get("is_used")) else \
                       "已兑换" if b(r.get("is_convert")) else "未使用"
        agent_issue.append({
            "issue_record_id": r.get("issue_record_id") or "",
            "coupon_name": r.get("coupon_name") or "",
            "coupon_code": r.get("coupon_code") or "",
            "issuer_id": r.get("issuer_id") or "",
            "issuer_name": r.get("issuer_name") or "",
            "issuer_phone": issuer_phone,
            "issue_time": ms2str(r.get("issue_time")),
            "need_purchase": "是" if b(r.get("is_need_buy")) else "否",
            "receiver_id": r.get("receiver_id") or "",
            "receiver_name": r.get("receiver_name") or "",
            "receiver_phone": r.get("receiver_phone") or "",
            "usage_status": usage_status,
            "agreement_id": ag.get("id") if ag else "",
            "agreement_status": ag_status_cn(ag.get("status")) if ag else "",
            "battery_product_id": ag.get("battery_product_id") if ag else "",
            "battery_product_name": "",
            "site_id": ag.get("site_id") if ag else "",
            "site_name": "",
            "package_id": ag.get("rent_package_id") if ag else "",
            "package_name": ag.get("first_rent_package_name") if ag else "",
            "brand_id": ag.get("bike_brand_id") if ag else "",
            "brand_name": "",
            "due_amount": yuan(r.get("pay_fee")),
            "pay_status": "已支付" if b(r.get("is_pay")) else "未支付",
            "paid_amount": yuan(r.get("pay_fee")),
            "pay_time": ms2str(r.get("pay_time")),
            "pay_method": r.get("pay_way") or "",
            "pay_no": r.get("trade_no") or "",
            "no_pay_remark": r.get("pay_remark") or "",
            "refund_status": "已退款" if b(r.get("is_refund")) else "未退款",
            "refund_amount": yuan(r.get("refund_fee")),
            "refund_time": ms2str(r.get("refund_time")),
        })

    # 批量补名称：site / battery_product / rent_package / bike_brand
    site_ids = list(set(str(r["site_id"]) for r in agent_issue if r["site_id"]) - {""})
    bp_ids = list(set(str(r["battery_product_id"]) for r in agent_issue if r["battery_product_id"]) - {""})
    pkg_ids = list(set(str(r["package_id"]) for r in agent_issue if r["package_id"]) - {""})
    brand_ids = list(set(str(r["brand_id"]) for r in agent_issue if r["brand_id"]) - {""})
    names = {"site": {}, "bp": {}, "pkg": {}, "brand": {}}
    if site_ids:
        for row in q(cur, "SELECT id, name FROM t_site WHERE id IN (%s)" % ",".join(site_ids), "agent_site_names", many=True) or []:
            names["site"][str(row["id"])] = row.get("name") or ""
    if bp_ids:
        for row in q(cur, "SELECT id, name FROM t_battery_product WHERE id IN (%s)" % ",".join(bp_ids), "agent_bp_names", many=True) or []:
            names["bp"][str(row["id"])] = row.get("name") or ""
    if pkg_ids:
        for row in q(cur, "SELECT id, name FROM t_exchange_rent_package WHERE id IN (%s)" % ",".join(pkg_ids), "agent_pkg_names", many=True) or []:
            names["pkg"][str(row["id"])] = row.get("name") or ""
    if brand_ids:
        for row in q(cur, "SELECT id, name FROM t_bike_brand WHERE id IN (%s)" % ",".join(brand_ids), "agent_brand_names", many=True) or []:
            names["brand"][str(row["id"])] = row.get("name") or ""
    for r in agent_issue:
        r["site_name"] = names["site"].get(str(r["site_id"]), "")
        r["battery_product_name"] = names["bp"].get(str(r["battery_product_id"]), "")
        r["package_name"] = names["pkg"].get(str(r["package_id"]), r["package_name"])
        r["brand_name"] = names["brand"].get(str(r["brand_id"]), "")

    # 发放人手机号兜底：按名字再查一次 t_site_store_employee（ID 无法一一对应时尽量补）
    issuer_names_no_phone = list(set(r["issuer_name"] for r in agent_issue if r["issuer_name"] and not r["issuer_phone"]))
    name_phone = {}
    if issuer_names_no_phone:
        placeholders = ",".join(["%s"] * len(issuer_names_no_phone))
        for row in q(cur, "SELECT name, phone FROM t_site_store_employee WHERE name IN (%s) AND phone IS NOT NULL AND phone!='' GROUP BY name" % placeholders,
                     "agent_issuer_phone_by_name", many=True, args=tuple(issuer_names_no_phone)) or []:
            name_phone[row.get("name") or ""] = row.get("phone") or ""
    for r in agent_issue:
        if not r["issuer_phone"] and r["issuer_name"] in name_phone:
            r["issuer_phone"] = name_phone[r["issuer_name"]]

    # ---------- C3 商户端发券统计（按 CSV 53 列，t_coupon_convert_code 全量） ----------
    mi_rows = q(cur,
        "SELECT "
        "  c.id AS convert_code_id, c.coupon_convert_code, c.convert_code_batch_id, "
        "  c.coupon_center_id, cc.name AS coupon_resource_name, "
        "  c.merchant_id, m.name AS merchant_name, "
        "  c.is_convert, c.convert_time, c.is_invalid, c.invalid_time, c.is_refund, "
        "  c.user_id, c.user_name, c.user_phone, c.create_time AS code_create_time, "
        "  log.id AS center_log_id, log.coupon_center_id AS center_id, "
        "  log.coupon_id, log.coupon_title, "
        "  log.giver_agency_id, log.giver_agency_name, "
        "  log.giver_merchant_id, log.giver_merchant_name, "
        "  log.giver_employee_id, log.giver_employee_name, log.giver_employee_type, log.give_time, "
        "  uc.is_used, uc.use_time, "
        "  o.id AS order_id, o.status AS order_status, o.pay_way, o.trade_no, o.is_pay, o.pay_time, "
        "  o.pay_fee, o.is_pay_now, o.pay_unit_fee, o.buyer_id, o.buyer_name, o.buyer_employee_type, "
        "  o.creator_id, o.creator_name, o.creator_employee_type, "
        "  o.refund_fee, o.refund_time, o.pay_remark, o.agency_id AS order_agency_id, o.battery_product_id "
        "FROM t_coupon_convert_code c "
        "LEFT JOIN t_coupon_center cc ON c.coupon_center_id=cc.id "
        "LEFT JOIN t_merchant m ON c.merchant_id=m.id "
        "LEFT JOIN t_coupon_center_log log ON c.coupon_convert_code=log.coupon_convert_code "
        "LEFT JOIN t_user_coupon uc ON c.coupon_convert_code=uc.coupon_convert_code "
        "LEFT JOIN t_coupon_convert_code_order o ON c.convert_code_batch_id=o.coupon_convert_batch_id "
        "WHERE c.is_del=0 ORDER BY c.create_time DESC",
        "merchant_issue", many=True) or []

    # 批量补协议：按 user_id 取最近创建协议
    user_ids = list(set(str(r.get("user_id") or "") for r in mi_rows) - {"", "0"})
    agreements = {}
    if user_ids:
        BATCH = 3000
        for i in range(0, len(user_ids), BATCH):
            chunk = user_ids[i:i+BATCH]
            for ag in q(cur,
                "SELECT id, user_id, status, site_id, rent_package_id, first_rent_package_name, "
                "  battery_product_id, create_time, activation_time, stop_time "
                "FROM t_exchange_agreement WHERE user_id IN (%s)" % ",".join(chunk),
                "merchant_issue_agreements_%d" % i, many=True) or []:
                uid = str(ag.get("user_id"))
                agreements.setdefault(uid, []).append(ag)

    def pick_agreement_for_merchant(r):
        uid = str(r.get("user_id") or "")
        ags = agreements.get(uid, [])
        if not ags: return None
        use_time = r.get("use_time") or 0
        if use_time:
            # use_time 之前最近创建的协议
            before = [ag for ag in ags if (ag.get("create_time") or 0) <= use_time]
            if before:
                return sorted(before, key=lambda x: x.get("create_time") or 0, reverse=True)[0]
        # fallback 最近创建
        return sorted(ags, key=lambda x: x.get("create_time") or 0, reverse=True)[0]

    # 批量补服务单：按 agreement_id 取最近创建服务单
    agreement_ids = list(set(str(pick_agreement_for_merchant(r).get("id")) for r in mi_rows if pick_agreement_for_merchant(r)) - {"", "0"})
    service_orders = {}
    if agreement_ids:
        BATCH = 3000
        for i in range(0, len(agreement_ids), BATCH):
            chunk = agreement_ids[i:i+BATCH]
            for so in q(cur,
                "SELECT id, exchange_agreement_id, create_time FROM t_exchange_service_order "
                "WHERE exchange_agreement_id IN (%s)" % ",".join(chunk),
                "merchant_issue_service_orders_%d" % i, many=True) or []:
                aid = str(so.get("exchange_agreement_id"))
                service_orders.setdefault(aid, []).append(so)

    # 批量补名称
    site_ids = list(set(str(ag.get("site_id")) for ags in agreements.values() for ag in ags if ag.get("site_id")) - {""})
    bp_ids = list(set(str(ag.get("battery_product_id")) for ags in agreements.values() for ag in ags if ag.get("battery_product_id")) - {""})
    order_bp_ids = list(set(str(r.get("battery_product_id") or "") for r in mi_rows if r.get("battery_product_id")) - {"", "0"})
    bp_ids = list(set(bp_ids + order_bp_ids))
    names = {"site": {}, "bp": {}}
    if site_ids:
        for row in q(cur, "SELECT id, name FROM t_site WHERE id IN (%s)" % ",".join(site_ids), "merchant_site_names", many=True) or []:
            names["site"][str(row["id"])] = row.get("name") or ""
    if bp_ids:
        for row in q(cur, "SELECT id, name FROM t_battery_product WHERE id IN (%s)" % ",".join(bp_ids), "merchant_bp_names", many=True) or []:
            names["bp"][str(row["id"])] = row.get("name") or ""

    def status_cn(s):
        return {"success":"已完成","pending":"待处理","cancel":"已取消","refund":"已退款","failed":"失败","working":"生效中"}.get(s, s or "")
    def yesno(v): return "是" if b(v) else "否"

    # 订单维度统计（按 batch_id）
    batch_stats = {}
    for r in mi_rows:
        bid = str(r.get("convert_code_batch_id") or "")
        if not bid: continue
        if bid not in batch_stats:
            batch_stats[bid] = {"total":0, "valid":0, "sent":0, "used":0}
        batch_stats[bid]["total"] += 1
        if not b(r.get("is_invalid")):
            batch_stats[bid]["valid"] += 1
        if b(r.get("is_convert")):
            batch_stats[bid]["sent"] += 1
        if b(r.get("is_used")):
            batch_stats[bid]["used"] += 1

    merchant_issue = []
    for r in mi_rows:
        ag = pick_agreement_for_merchant(r)
        aid = str(ag.get("id")) if ag else ""
        sos = service_orders.get(aid, [])
        so = None
        if sos:
            use_time = r.get("use_time") or 0
            if use_time:
                so = min(sos, key=lambda x: abs((x.get("create_time") or 0) - use_time))
            else:
                so = sorted(sos, key=lambda x: x.get("create_time") or 0, reverse=True)[0]
        bp_id = r.get("battery_product_id") or (ag.get("battery_product_id") if ag else "")
        bid = str(r.get("convert_code_batch_id") or "")
        stats = batch_stats.get(bid, {"total":0, "valid":0, "sent":0, "used":0})
        creator_name = r.get("creator_name") or r.get("buyer_name") or ""
        merchant_issue.append({
            "convert_code_id": r.get("convert_code_id") or "",
            "order_id": r.get("order_id") or "",
            "agency_id": r.get("giver_agency_id") or r.get("order_agency_id") or "",
            "agency_name": r.get("giver_agency_name") or "",
            "merchant_id": r.get("giver_merchant_id") or r.get("merchant_id") or "",
            "merchant_name": r.get("giver_merchant_name") or r.get("merchant_name") or "",
            "coupon_resource_id": r.get("coupon_id") or r.get("coupon_center_id") or "",
            "coupon_resource_name": r.get("coupon_title") or r.get("coupon_resource_name") or "",
            "convert_code_batch_id": r.get("convert_code_batch_id") or "",
            "is_converted": yesno(r.get("is_convert")),
            "convert_time": ms2str(r.get("convert_time")),
            "issuer_id": r.get("giver_employee_id") or "",
            "issuer_name": r.get("giver_employee_name") or "",
            "issuer_type": r.get("giver_employee_type") or "",
            "receiver_id": r.get("user_id") or "",
            "receiver_name": r.get("user_name") or "",
            "receiver_phone": r.get("user_phone") or "",
            "is_used": yesno(r.get("is_used")),
            "use_time": ms2str(r.get("use_time")),
            "is_invalid": yesno(r.get("is_invalid")),
            "invalid_time": ms2str(r.get("invalid_time")),
            "agreement_id": aid,
            "site_id": ag.get("site_id") if ag else "",
            "site_name": names["site"].get(str(ag.get("site_id"))) if ag and ag.get("site_id") else "",
            "service_order_id": so.get("id") if so else "",
            "is_refund": yesno(r.get("is_refund")),
            "refund_amount": yuan(r.get("refund_fee")),
            "refund_reason": r.get("pay_remark") or "",
            "refund_time": ms2str(r.get("refund_time")),
            "refund_operator_id": "",
            "refund_operator_name": "",
            "order_buy_count": stats["valid"],
            "order_available_count": stats["total"],
            "order_sent_count": stats["sent"],
            "order_used_count": stats["used"],
            "center_id": r.get("center_id") or "",
            "center_log_id": r.get("center_log_id") or "",
            "battery_product_id": bp_id,
            "battery_product_name": names["bp"].get(str(bp_id), "") if bp_id else "",
            "pay_channel": r.get("pay_way") or "",
            "pay_channel_trade_no": r.get("trade_no") or "",
            "pay_no": r.get("trade_no") or "",
            "order_status": status_cn(r.get("order_status")),
            "pay_now": yesno(r.get("is_pay_now")),
            "is_paid": yesno(r.get("is_pay")),
            "pay_time": ms2str(r.get("pay_time")),
            "order_pay_amount": yuan(r.get("pay_fee")),
            "code_unit_price": yuan(r.get("pay_unit_fee")),
            "buyer_id": r.get("buyer_id") or "",
            "buyer_name": r.get("buyer_name") or "",
            "buyer_type": r.get("buyer_employee_type") or "",
            "creator_id": r.get("creator_id") or "",
            "creator_name": creator_name,
            "creator_type": r.get("creator_employee_type") or "",
            "create_time": ms2str(r.get("code_create_time")),
        })

    # ---------- C4 合约份额采购统计（按 CSV 23 列，t_contract_scheme_order 全量） ----------
    ct_rows = q(cur,
        "SELECT o.*, bp.name AS battery_product_name "
        "FROM t_contract_scheme_order o "
        "LEFT JOIN t_battery_product bp ON o.battery_product_id=bp.id "
        "WHERE o.is_del=0 ORDER BY o.create_time DESC",
        "contract", many=True) or []
    contract = [{
        "contract_order_no": str(r.get("id") or ""),
        "battery_product_id": r.get("battery_product_id") or "",
        "battery_product_name": r.get("battery_product_name") or "",
        "contract_scheme_id": r.get("contract_scheme_id") or "",
        "contract_scheme_name": r.get("contract_name") or "",
        "belong_maker_id": r.get("belong_maker_id") or "",
        "belong_maker_name": r.get("belong_maker_name") or "",
        "belong_maker_phone": r.get("belong_maker_phone") or "",
        "contract_period": (str(r.get("contract_period") or "") + {"year":"年","month":"个月","day":"天"}.get(r.get("contract_period_type") or "", "")) if r.get("contract_period_type") else str(r.get("contract_period") or ""),
        "buy_quantity": r.get("buy_quantity") or 0,
        "sales_amount": yuan(r.get("pay_fee")),
        "refund_quantity": r.get("refund_quantity") or 0,
        "refund_amount": yuan(r.get("refund_fee")),
        "used_quantity": r.get("use_quantity") or 0,
        "remaining_quantity": r.get("last_quantity") or 0,
        "buyer_id": r.get("buyer_id") or "",
        "buyer_name": r.get("buyer_name") or "",
        "buyer_phone": r.get("buyer_phone") or "",
        "order_status": r.get("status") or "",
        "pay_method": r.get("pay_way") or "",
        "pay_trade_no": r.get("trade_no") or "",
        "pay_time": ms2str(r.get("pay_time")),
        "refund_trade_no": "",
        "refund_time": ms2str(r.get("refund_time")),
        "create_time": ms2str(r.get("create_time")),
    } for r in ct_rows]

    # ---------- C4-detail 合约销售份额明细（按 CSV 18 列，t_user_contract_code 全量） ----------
    ccd_rows = q(cur,
        "SELECT c.*, o.battery_product_id AS order_battery_product_id, o.contract_scheme_id, "
        "  o.contract_name, o.belong_maker_id, o.belong_maker_name, o.belong_maker_phone, "
        "  o.contract_period, o.contract_period_type "
        "FROM t_user_contract_code c "
        "INNER JOIN t_contract_scheme_order o ON c.contract_scheme_order_id=o.id "
        "WHERE c.is_del=0 AND o.is_del=0 ORDER BY c.create_time DESC",
        "contract_detail", many=True) or []
    # 批量拉协议
    ag_ids = list(set(str(r.get("agreement_id") or "") for r in ccd_rows) - {"", "0"})
    agreements = {}
    if ag_ids:
        BATCH = 3000
        for i in range(0, len(ag_ids), BATCH):
            chunk = ag_ids[i:i+BATCH]
            for ag in q(cur,
                "SELECT id, user_id, user_phone, status, site_id, rent_package_id, first_rent_package_name, "
                "  battery_product_id, create_time, activation_time, stop_time "
                "FROM t_exchange_agreement WHERE id IN (%s)" % ",".join(chunk),
                "contract_detail_agreements_%d" % i, many=True) or []:
                agreements[str(ag.get("id"))] = ag
    # 批量拉名称
    site_ids = list(set(str(ag.get("site_id")) for ag in agreements.values() if ag.get("site_id")) - {""})
    pkg_ids = list(set(str(ag.get("rent_package_id")) for ag in agreements.values() if ag.get("rent_package_id")) - {""})
    bp_ids = list(set(str(ag.get("battery_product_id")) for ag in agreements.values() if ag.get("battery_product_id")) - {""})
    names = {"site": {}, "pkg": {}, "bp": {}}
    if site_ids:
        for row in q(cur, "SELECT id, name FROM t_site WHERE id IN (%s)" % ",".join(site_ids), "cd_site_names", many=True) or []:
            names["site"][str(row["id"])] = row.get("name") or ""
    if pkg_ids:
        for row in q(cur, "SELECT id, name FROM t_exchange_rent_package WHERE id IN (%s)" % ",".join(pkg_ids), "cd_pkg_names", many=True) or []:
            names["pkg"][str(row["id"])] = row.get("name") or ""
    if bp_ids:
        for row in q(cur, "SELECT id, name FROM t_battery_product WHERE id IN (%s)" % ",".join(bp_ids), "cd_bp_names", many=True) or []:
            names["bp"][str(row["id"])] = row.get("name") or ""

    def cn_status(s):
        return {"working":"生效中","stop":"已终止","stopped":"已终止","cancelled":"已取消","paused":"已暂停",
                "owe_rent":"欠租","unsubscribing":"退约中","wait_activate":"待激活","invalid":"已失效"}.get(s, s or "")
    def cn_code_status(s):
        return {"used":"已使用","unused":"未使用","refund":"已退款"}.get(s, s or "")

    contract_detail = []
    for r in ccd_rows:
        ag = agreements.get(str(r.get("agreement_id") or ""))
        bp_id = r.get("order_battery_product_id") or (ag.get("battery_product_id") if ag else "")
        site_id = ag.get("site_id") if ag else ""
        pkg_id = ag.get("rent_package_id") if ag else ""
        contract_detail.append({
            "contract_order_no": str(r.get("contract_scheme_order_id") or ""),
            "battery_product_id": bp_id,
            "battery_product_name": names["bp"].get(str(bp_id), "") if bp_id else "",
            "contract_scheme_id": r.get("contract_scheme_id") or "",
            "contract_scheme_name": r.get("contract_name") or "",
            "belong_maker_id": r.get("belong_maker_id") or "",
            "belong_maker_name": r.get("belong_maker_name") or "",
            "belong_maker_phone": r.get("belong_maker_phone") or "",
            "contract_code_id": str(r.get("id") or ""),
            "contract_code_status": cn_code_status(r.get("status")),
            "agreement_id": r.get("agreement_id") or "",
            "site_name": names["site"].get(str(site_id), "") if site_id else "",
            "user_id": ag.get("user_id") if ag else "",
            "user_phone": ag.get("user_phone") if ag else "",
            "agreement_status": cn_status(ag.get("status")) if ag else "",
            "package_name": ag.get("first_rent_package_name") or names["pkg"].get(str(pkg_id), "") if ag else "",
            "agreement_create_time": ms2str(ag.get("create_time")) if ag else "",
            "agreement_activate_time": ms2str(ag.get("activation_time")) if ag else "",
            "agreement_terminate_time": ms2str(ag.get("stop_time")) if ag else "",
        })

    # ---------- C5 用户优惠券明细（近样本 5000，保留原映射） ----------
    ud_rows = q(cur,
        "SELECT * FROM t_coupon_center_log ORDER BY give_time DESC LIMIT %d" % USER_DETAIL_CAP,
        "user_detail", many=True) or []
    user_detail = [{
        "record_id": r["id"], "coupon_name": r.get("coupon_title") or "",
        "coupon_code": r.get("coupon_convert_code") or "",
        "issuer_name": r.get("giver_employee_name") or "",
        "issue_time": ms2str(r.get("give_time")),
        "receiver_name": r.get("user_name") or "", "receiver_phone": r.get("user_phone") or "",
        "usage_status": "", "pay_status": "", "paid_amount": yuan(r.get("min_fee")),
        "agreement_id": "", "site_name": "", "battery_product_name": "",
        "package_name": "", "pay_method": r.get("platform") or "", "refund_status": "",
    } for r in ud_rows]

    # ---------- C6 优惠券资源（领券中心，全量 327，保留原映射） ----------
    rs_rows = q(cur, "SELECT * FROM t_coupon_center ORDER BY create_time DESC", "resource", many=True) or []
    resource = [{
        "resource_id": r["id"], "coupon_title": r.get("name") or "",
        "discount_type": "购买券" if str(r.get("is_need_buy")) == "1" else "领取券",
        "apply_product": "",
        "discount_value": ("%s~%s" % (yuan(r.get("min_fee")), yuan(r.get("max_fee")))) if (r.get("min_fee") or r.get("max_fee")) else "",
        "city_area": "", "battery_model": "", "get_type": r.get("platform") or "",
        "disabled": "禁用" if r.get("center_status") == "off" else "正常",
        "creator": r.get("creator_name") or "", "created_at": ms2str(r.get("create_time")),
        "ops": "",
    } for r in rs_rows]

    C = {
        "_generated_at": ms2str(int(time.time() * 1000)),
        "_note": "全量刷新（无样本上限）：agent_issue(t_coupon_center_log.platform='agency' %d 行，32 列对齐 CSV)/"
                 "merchant_issue(t_coupon_convert_code %d 行)/contract(t_contract_scheme_order %d 行，23 列对齐 CSV)/contract_detail(t_user_contract_code %d 行，18 列对齐 CSV) 均全量；"
                 "overview 为全表聚合。金额库内为分，已÷100为元。t_agency 不存在→代理商仅 agency_id；"
                 "商户名称经 LEFT JOIN t_merchant 补全。" % (len(agent_issue), len(merchant_issue), len(contract), len(contract_detail)),
        "overview": overview, "by_coupon": by_coupon, "top_site": top_site,
        "top_merchant": top_merchant, "agent_issue": agent_issue,
        "merchant_issue": merchant_issue, "contract": contract,
        "contract_detail": contract_detail,
        "user_detail": user_detail, "resource": resource,
    }
    json.dump(C, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    conn.close()
    print("DONE ->", OUT)
    print("  overview:", overview)
    print("  by_coupon=%d  top_merchant=%d  agent_issue=%d  merchant_issue=%d  contract=%d  contract_detail=%d  user_detail=%d  resource=%d"
          % (len(by_coupon), len(top_merchant), len(agent_issue), len(merchant_issue), len(contract), len(contract_detail), len(user_detail), len(resource)))
    print("  errors:", len(ERR))
    for e in ERR:
        print("  -", e)

if __name__ == "__main__":
    main()
