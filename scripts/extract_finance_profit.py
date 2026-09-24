# -*- coding: utf-8 -*-
"""财务「利润模型」抽取：套用「单个门店收入支出明细」的 收入-支出-利润 思路，放大到全量业务。
收入来自消费者实际支付（订单表，净额=收-退）；支出来自 t_expense_bill（已结算），
按 Excel 模型归类为 推广补贴/换电分成电费/其他运营，**剔除提现(withdraw)**（提现是资金流出，单列财务费用）。
营业利润 = 营业收入 - 营业支出。
结果写入 data/dashboard_data.json 的 D['finance']['profit']。
单位：元（库内 fee 为分，已 ÷100）。全程可追溯。
"""
import json, pymysql, time, datetime

BASE = r"D:/workboddy file/dudu分析/citybike_backup"
DB = json.load(open(BASE + r"/config/backup_config.json", encoding="utf-8"))
DB.pop("workers", None)
OUT = BASE + r"/data/dashboard_data.json"

conn = pymysql.connect(host=DB["host"], port=DB["port"], user=DB["user"], password=DB["password"],
                       database=DB["database"], connect_timeout=15, read_timeout=600, charset="utf8mb4")
cur = conn.cursor()

def q(sql, many=False):
    cur.execute(sql)
    return cur.fetchall() if many else (cur.fetchone()[0] if cur.rowcount else None)

# ---------- 营业收入（消费者实付，净额） ----------
# 套餐/电量包订单（电量包是套餐子集，故套餐收入已含电量包，构图时避免重复计）
income_package = (q("SELECT COALESCE(SUM(real_fee),0) FROM t_user_exchange_package_order WHERE order_status='success'") or 0) / 100.0
income_rent   = (q("SELECT COALESCE(SUM(combo_real_fee),0) FROM t_user_exchange_rent_package_order WHERE is_pay=1") or 0) / 100.0
income_deposit= (q("SELECT COALESCE(SUM(real_fee),0) FROM t_user_exchange_deposit_package_order WHERE is_pay=1") or 0) / 100.0
income_refund = (q("SELECT COALESCE(SUM(refund_fee),0) FROM t_user_exchange_package_order WHERE is_refund=1") or 0) / 100.0
income_total = income_rent + income_package + income_deposit - income_refund

income_comp = [
    {"name": "租金收入(租期卡)", "amount": round(income_rent, 2)},
    {"name": "套餐及电量收入", "amount": round(income_package, 2)},
    {"name": "押金收入", "amount": round(income_deposit, 2)},
    {"name": "退款(冲减)", "amount": round(-income_refund, 2)},
]

# ---------- 营业支出（t_expense_bill 已结算，剔除提现） ----------
PROMO_KW = ['补贴', '拉新', '优惠', '赠送', '活动', '套餐', '售车固定', '租车套餐', '骑手套餐', '69.9', '换电补贴']
SWAP_KW  = ['换电分成', '场地', '机柜', '电费', '渠道分成', '用户拓展', '用户换电', '落柜', '柜机']

def cat_of(name, etype):
    if etype == 'withdraw':
        return '提现(资金类)'
    if any(k in (name or '') for k in PROMO_KW):
        return '推广补贴'
    if any(k in (name or '') for k in SWAP_KW):
        return '换电分成电费'
    return '其他运营'

rows = q(
    "SELECT expense_name, expense_type, COALESCE(SUM(fee),0)/100.0 amt, COUNT(*) c "
    "FROM t_expense_bill WHERE bill_status='settle' AND is_del=0 "
    "GROUP BY expense_name, expense_type ORDER BY amt DESC", many=True) or []
by_cat = {}
by_name = []
withdraw_total = 0.0
for r in rows:
    name, etype, amt, c = r[0] or "其他", r[1], float(r[2]), r[3]
    cat = cat_of(name, etype)
    by_cat[cat] = by_cat.get(cat, 0.0) + amt
    if cat == '提现(资金类)':
        withdraw_total += amt
    by_name.append({"name": name, "type": etype or "—", "amount": round(amt, 2), "count": c, "cat": cat})
by_name.sort(key=lambda x: x["amount"], reverse=True)
by_name = by_name[:20]

expense_op = by_cat.get('推广补贴', 0.0) + by_cat.get('换电分成电费', 0.0) + by_cat.get('其他运营', 0.0)
expense_cats = [{"cat": k, "amount": round(v, 2)} for k, v in sorted(by_cat.items(), key=lambda kv: kv[1], reverse=True) if k != '提现(资金类)']

operating_profit = income_total - expense_op
net_margin = (operating_profit / income_total * 100.0) if income_total else 0.0

# ---------- 月度趋势（收入 / 营业支出 / 营业利润） ----------
def monthly(sql):
    out = {}
    for r in q(sql, many=True) or []:
        m, v = r[0], float(r[1])
        if m:
            out[m] = out.get(m, 0.0) + v
    return out

m_inc_pkg = monthly("SELECT DATE_FORMAT(FROM_UNIXTIME(create_time/1000),'%Y-%m') m, COALESCE(SUM(real_fee),0)/100.0 "
                     "FROM t_user_exchange_package_order WHERE order_status='success' GROUP BY m")
m_inc_rent= monthly("SELECT DATE_FORMAT(FROM_UNIXTIME(create_time/1000),'%Y-%m') m, COALESCE(SUM(combo_real_fee),0)/100.0 "
                     "FROM t_user_exchange_rent_package_order WHERE is_pay=1 GROUP BY m")
m_inc_dep = monthly("SELECT DATE_FORMAT(FROM_UNIXTIME(create_time/1000),'%Y-%m') m, COALESCE(SUM(real_fee),0)/100.0 "
                     "FROM t_user_exchange_deposit_package_order WHERE is_pay=1 GROUP BY m")
m_refund  = monthly("SELECT DATE_FORMAT(FROM_UNIXTIME(create_time/1000),'%Y-%m') m, COALESCE(SUM(refund_fee),0)/100.0 "
                     "FROM t_user_exchange_package_order WHERE is_refund=1 GROUP BY m")
m_exp_op  = monthly("SELECT DATE_FORMAT(FROM_UNIXTIME(create_time/1000),'%Y-%m') m, COALESCE(SUM(fee),0)/100.0 "
                     "FROM t_expense_bill WHERE bill_status='settle' AND is_del=0 AND expense_type<>'withdraw' GROUP BY m")

months = sorted(set(list(m_inc_pkg) + list(m_inc_rent) + list(m_inc_dep) + list(m_refund) + list(m_exp_op)))
trend = []
for m in months:
    inc = m_inc_pkg.get(m, 0) + m_inc_rent.get(m, 0) + m_inc_dep.get(m, 0) - m_refund.get(m, 0)
    exp = m_exp_op.get(m, 0)
    trend.append({"month": m, "income": round(inc, 2), "expense": round(exp, 2), "profit": round(inc - exp, 2)})

P = {
    "income_total": round(income_total, 2),
    "income_rent": round(income_rent, 2),
    "income_package": round(income_package, 2),
    "income_deposit": round(income_deposit, 2),
    "income_refund": round(income_refund, 2),
    "income_comp": income_comp,
    "expense_op": round(expense_op, 2),
    "expense_cats": expense_cats,
    "expense_by_name": by_name,
    "withdraw_total": round(withdraw_total, 2),
    "operating_profit": round(operating_profit, 2),
    "net_margin": round(net_margin, 2),
    "trend": trend,
}

data = json.load(open(OUT, encoding="utf-8"))
if "finance" not in data:
    data["finance"] = {}
data["finance"]["profit"] = P
json.dump(data, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
print("OK finance.profit")
print("  营业收入(净额): %.2f" % income_total)
print("   租金=%.2f 套餐电量=%.2f 押金=%.2f 退款=%.2f" % (income_rent, income_package, income_deposit, income_refund))
print("  营业支出(剔除提现): %.2f  分类:" % expense_op, {k: round(v, 2) for k, v in by_cat.items() if k != '提现(资金类)'})
print("  提现(资金类): %.2f" % withdraw_total)
print("  营业利润: %.2f  净利率: %.2f%%" % (operating_profit, net_margin))
print("  月度趋势条数:", len(trend), "首:", trend[0] if trend else None, "尾:", trend[-1] if trend else None)
