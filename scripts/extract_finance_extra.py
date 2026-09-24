# -*- coding: utf-8 -*-
"""补抽财务三大维度「全量真值」（live 生产库，数据截至 2026-07）：
  1) 提现逐笔   : t_expense_bill WHERE expense_type='withdraw'  → 全量 26,340 笔
  2) 网点分成全量 : t_expense_bill WHERE expense_name LIKE '%分成%' → 聚合 by 收款方/付款方/费用名 + 1.5万明细样本
  3) 电费全量     : t_exchange_electric_settlement              → 按网点聚合 + 1.5万明细样本
  4) 收支对账单   : t_expense_bill 全表                       → 全量聚合 by in_unit/out_unit + 1.5万明细样本
  并刷新 finance.detail 为 2026 live 样本（让财务总览同步最新）。
单位：元（库内 fee/settle_amount 为分，已 ÷100）。
全程可追溯：来源表名 + 抽取时间写入 JSON 的 _meta。
"""
import json, pymysql, datetime, time

BASE = r"D:/workboddy file/dudu分析/citybike_backup"
DB = json.load(open(BASE + r"/config/backup_config.json", encoding="utf-8"))
DB.pop("workers", None)
OUT = BASE + r"/data/dashboard_data.json"
CAP = 15000  # 明细样本上限（库内全量过大，仅存聚合+样本，前端标注）

conn = pymysql.connect(host=DB["host"], port=DB["port"], user=DB["user"], password=DB["password"],
                       database=DB["database"], connect_timeout=15, read_timeout=600, charset="utf8mb4")
cur = conn.cursor()

def q(sql, many=True):
    cur.execute(sql)
    return cur.fetchall() if many else (cur.fetchone()[0] if cur.rowcount else None)

def ts(ms):
    if not ms: return ""
    try: return datetime.datetime.fromtimestamp(ms / 1000).strftime("%Y-%m-%d %H:%M:%S")
    except Exception: return str(ms)

def f2(x):
    try: return round(float(x), 2)
    except Exception: return 0.0

print("== 开始补抽（live 生产库）==", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

# ---------- 1) 提现逐笔（全量） ----------
t0 = time.time()
wd = q("SELECT id, out_unit_name, in_unit_name, fee/100.0, bill_status, create_time, settle_time "
        "FROM t_expense_bill WHERE is_del=0 AND expense_type='withdraw' ORDER BY create_time DESC")
wd_rows = [{"id": r[0], "out": r[1] or "", "in": r[2] or "", "fee": f2(r[3]),
            "status": r[4] or "", "create": ts(r[5]), "settle": ts(r[6])} for r in wd]
wd_by_month = q("SELECT DATE_FORMAT(FROM_UNIXTIME(create_time/1000),'%Y-%m') m, "
                 "COALESCE(SUM(fee),0)/100.0, COUNT(*) FROM t_expense_bill "
                 "WHERE is_del=0 AND expense_type='withdraw' GROUP BY m ORDER BY m")
wd_month = [{"month": r[0], "amount": f2(r[1]), "count": r[2]} for r in wd_by_month if r[0]]
wd_by_out = q("SELECT out_unit_name, COALESCE(SUM(fee),0)/100.0, COUNT(*) FROM t_expense_bill "
               "WHERE is_del=0 AND expense_type='withdraw' GROUP BY out_unit_name ORDER BY 2 DESC")
wd_out = [{"name": (r[0] or "未知"), "amount": f2(r[1]), "count": r[2]} for r in wd_by_out]
wd_total = sum(r["fee"] for r in wd_rows)
print("  提现: 全量 %d 笔, 总额 %.2f 元, 按月 %d 段, 按对象 %d 类  (%.1fs)" % (
    len(wd_rows), wd_total, len(wd_month), len(wd_out), time.time() - t0))

# ---------- 2) 网点分成全量 ----------
t0 = time.time()
SPLIT_WHERE = "is_del=0 AND expense_name LIKE '%分成%'"
sp_tot = q("SELECT COUNT(*), COALESCE(SUM(fee),0)/100.0 FROM t_expense_bill WHERE " + SPLIT_WHERE)[0]
sp_by_in = q("SELECT in_unit_name, COALESCE(SUM(fee),0)/100.0, COUNT(*) FROM t_expense_bill "
              "WHERE %s GROUP BY in_unit_name ORDER BY 2 DESC" % SPLIT_WHERE)
sp_by_out = q("SELECT out_unit_name, COALESCE(SUM(fee),0)/100.0, COUNT(*) FROM t_expense_bill "
               "WHERE %s GROUP BY out_unit_name ORDER BY 2 DESC" % SPLIT_WHERE)
sp_by_name = q("SELECT expense_name, COALESCE(SUM(fee),0)/100.0, COUNT(*) FROM t_expense_bill "
                "WHERE %s GROUP BY expense_name ORDER BY 2 DESC" % SPLIT_WHERE)
sp_detail = q("SELECT id, expense_name, out_unit_name, in_unit_name, fee/100.0, after_taxes_fee/100.0, "
               "bill_status, create_time, settle_time FROM t_expense_bill "
               "WHERE %s ORDER BY id DESC LIMIT %d" % (SPLIT_WHERE, CAP))
sp_rows = [{"id": r[0], "name": r[1] or "", "out": r[2] or "", "in": r[3] or "", "fee": f2(r[4]),
            "after": f2(r[5]), "status": r[6] or "", "create": ts(r[7]), "settle": ts(r[8])} for r in sp_detail]
split_block = {
    "total": f2(sp_tot[1]), "count": sp_tot[0],
    "by_in": [{"name": (r[0] or "未知"), "amount": f2(r[1]), "count": r[2]} for r in sp_by_in],
    "by_out": [{"name": (r[0] or "未知"), "amount": f2(r[1]), "count": r[2]} for r in sp_by_out],
    "by_name": [{"name": (r[0] or "未知"), "amount": f2(r[1]), "count": r[2]} for r in sp_by_name],
    "detail_sample": sp_rows,
}
print("  分成: 全量 %d 笔, 总额 %.2f 元, 收款方 %d / 付款方 %d / 费用名 %d 类, 明细样本 %d  (%.1fs)" % (
    sp_tot[0], split_block["total"], len(split_block["by_in"]), len(split_block["by_out"]),
    len(split_block["by_name"]), len(sp_rows), time.time() - t0))

# ---------- 3) 电费全量（按网点结算表） ----------
t0 = time.time()
el_tot = q("SELECT COUNT(*), COALESCE(SUM(settle_amount),0)/100.0, COALESCE(SUM(total_electric_usage),0) "
            "FROM t_exchange_electric_settlement WHERE is_del=0")[0]
el_by_site = q("SELECT site_id, MAX(site_name), MAX(agency_id), MAX(distributor_name), "
                "COALESCE(SUM(total_electric_usage),0), COALESCE(SUM(settle_amount),0)/100.0, COUNT(*), MAX(settle_status) "
                "FROM t_exchange_electric_settlement WHERE is_del=0 GROUP BY site_id")
el_by_dist = q("SELECT distributor_name, COALESCE(SUM(settle_amount),0)/100.0, "
                "COALESCE(SUM(total_electric_usage),0), COUNT(*) FROM t_exchange_electric_settlement "
                "WHERE is_del=0 GROUP BY distributor_name ORDER BY 2 DESC")
el_detail = q("SELECT site_id, site_name, agency_id, distributor_name, total_electric_usage, "
               "settle_amount/100.0, settle_status, settle_time FROM t_exchange_electric_settlement "
               "WHERE is_del=0 ORDER BY settle_time DESC LIMIT %d" % CAP)
el_rows = [{"site_id": r[0], "site_name": r[1] or "", "agency_id": r[2], "distributor": r[3] or "",
            "usage": f2(r[4]), "amount": f2(r[5]), "status": r[6] or "", "settle": ts(r[7])} for r in el_detail]
electric_block = {
    "total_amount": f2(el_tot[1]), "total_usage": f2(el_tot[2]), "count": el_tot[0],
    "by_site": [{"site_id": r[0], "site_name": r[1] or "", "agency_id": r[2], "distributor": r[3] or "",
                 "usage": f2(r[4]), "amount": f2(r[5]), "count": r[6], "status": r[7] or ""} for r in el_by_site],
    "by_distributor": [{"name": (r[0] or "未知"), "amount": f2(r[1]), "usage": f2(r[2]), "count": r[3]} for r in el_by_dist],
    "detail_sample": el_rows,
}
print("  电费: 全量 %d 条, 总额 %.2f 元, 总电量 %.0f 度, 按网点 %d 个, 明细样本 %d  (%.1fs)" % (
    el_tot[0], electric_block["total_amount"], electric_block["total_usage"],
    len(electric_block["by_site"]), len(el_rows), time.time() - t0))

# ---------- 4) 收支对账单（全量聚合 + 样本） ----------
t0 = time.time()
rc_by_in = q("SELECT in_unit, COALESCE(SUM(fee),0)/100.0, COUNT(*) FROM t_expense_bill "
              "WHERE is_del=0 GROUP BY in_unit ORDER BY 2 DESC")
rc_by_out = q("SELECT out_unit_name, COALESCE(SUM(fee),0)/100.0, COUNT(*) FROM t_expense_bill "
               "WHERE is_del=0 GROUP BY out_unit_name ORDER BY 2 DESC")
rc_detail = q("SELECT id, business_id, business_type, expense_name, expense_type, in_unit, out_unit_name, "
               "fee/100.0, after_taxes_fee/100.0, bill_status, is_refund, create_time, settle_time, remark "
               "FROM t_expense_bill WHERE is_del=0 ORDER BY id DESC LIMIT %d" % CAP)
rc_rows = [{"id": r[0], "business_id": r[1] or "", "business_type": r[2] or "", "name": r[3] or "",
            "expense_type": r[4] or "", "in_unit": r[5] or "", "out_unit_name": r[6] or "", "fee": f2(r[7]),
            "after": f2(r[8]), "status": r[9] or "", "is_refund": r[10], "create": ts(r[11]),
            "settle": ts(r[12]), "remark": r[13] or ""} for r in rc_detail]
recon_block = {
    "by_in": [{"unit": (r[0] or "未知"), "amount": f2(r[1]), "count": r[2]} for r in rc_by_in],
    "by_out": [{"unit": (r[0] or "未知"), "amount": f2(r[1]), "count": r[2]} for r in rc_by_out],
    "detail_sample": rc_rows,
}
print("  收支: 收款方 %d / 付款方 %d 类, 明细样本 %d  (%.1fs)" % (
    len(recon_block["by_in"]), len(recon_block["by_out"]), len(rc_rows), time.time() - t0))

# ---------- 刷新 finance.detail 为 2026 live 样本（与全量聚合同源） ----------
t0 = time.time()
det = q("SELECT id, business_id, business_type, expense_name, expense_type, in_unit, out_unit_name, "
          "fee/100.0, after_taxes_fee/100.0, bill_status, is_refund, create_time, settle_time, remark "
          "FROM t_expense_bill WHERE is_del=0 ORDER BY id DESC LIMIT 5000")
det_rows = [{"id": r[0], "business_id": r[1] or "", "business_type": r[2] or "", "name": r[3] or "",
             "expense_type": r[4] or "", "in_unit": r[5] or "", "out_unit_name": r[6] or "", "fee": f2(r[7]),
             "after_taxes_fee": f2(r[8]), "status": r[9] or "", "is_refund": r[10], "create": ts(r[11]),
             "settle": ts(r[12]), "remark": r[13] or ""} for r in det]
print("  finance.detail 刷新为 live 样本 %d 行  (%.1fs)" % (len(det_rows), time.time() - t0))
conn.close()

# ---------- 写入 dashboard_data.json ----------
print("== 写入 JSON ==")
t0 = time.time()
data = json.load(open(OUT, encoding="utf-8"))
data.setdefault("finance", {})
data["finance"]["withdraw"] = {"total": f2(wd_total), "count": len(wd_rows),
                                "by_month": wd_month, "by_out": wd_out, "detail": wd_rows}
data["finance"]["split"] = split_block
data["finance"]["recon"] = recon_block
data["finance"]["detail"] = det_rows   # 刷新为 live 样本
data["site"] = data.get("site", {})
data["site"]["electric"] = electric_block
now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
data["finance"]["_meta"] = {
    "extracted_at": now,
    "source": "live t_expense_bill + t_exchange_electric_settlement (生产库)",
    "note": "提现/分成/电费/收支均为 2026 实时数据；金额单位=元(÷100)。分成明细与电费/收支明细为样本(上限%d)，聚合为全量。" % CAP,
}
json.dump(data, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
print("  OK 写入完成 (%.1fs)" % (time.time() - t0))
print("== 完成 ==", now)
