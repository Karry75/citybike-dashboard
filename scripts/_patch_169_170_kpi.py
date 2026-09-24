"""#169+#170: DB查询补齐用户KPI缺口 + 设备仓库电池真实数据（修正版）"""
import json, os, sys, time
sys.path.insert(0, r"C:\Users\Karry\.workbuddy\binaries\python\envs\default\lib\python3.13\site-packages")
import pymysql

cfg = json.load(open("config/backup_config.json", encoding="utf-8"))
cfg.pop("workers", None)
conn = pymysql.connect(host=cfg["host"], port=cfg["port"], user=cfg["user"],
                       password=cfg["password"], database=cfg["database"],
                       connect_timeout=30, read_timeout=600, charset="utf8mb4")
cur = conn.cursor()

NOW_MS = int(time.time() * 1000)
DAY_MS = 86400000
results = {}

# ── #169: 退款笔数(已确认) ──
cur.execute("""
    SELECT COUNT(*), COALESCE(SUM(refund_fee), 0)/100
    FROM t_user_exchange_package_order
    WHERE is_refund = 1 AND is_del = 0
""")
row = cur.fetchone()
results['refund'] = {'count': row[0], 'amount': float(row[1] or 0)}
print(f"1.退款笔数: {results['refund']['count']} | 金额: {results['refund']['amount']:.2f} 元")

# ── #169: 活跃用户(近7天有换电成功记录) ──
cur.execute(f"""
    SELECT COUNT(DISTINCT take_user_id)
    FROM t_exchange_order
    WHERE order_status = 'success'
      AND take_battery_time >= {NOW_MS - 7*DAY_MS}
      AND is_del = 0
""")
results['active7d'] = cur.fetchone()[0]
print(f"2.活跃7天换电用户: {results['active7d']}")

# ── #169: 近30天新增注册 ──
cur.execute(f"""
    SELECT COUNT(*)
    FROM t_user
    WHERE create_time >= {NOW_MS - 30*DAY_MS}
    AND is_del = 0
""")
results['new_reg_30d'] = cur.fetchone()[0]
print(f"3.近30天新增注册: {results['new_reg_30d']}")

# ── #169: 换电订单总数 / 消费金额(real_pay_price 单位分) ──
cur.execute("""
    SELECT COUNT(*),
           COALESCE(SUM(real_pay_price), 0)/100,
           COALESCE(SUM(pay_price), 0)/100
    FROM t_exchange_order
    WHERE is_del = 0 AND order_status = 'success'
""")
row = cur.fetchone()
results['orders'] = {
    'count': row[0],
    'amount_real': float(row[1] or 0),
    'amount_gross': float(row[2] or 0)
}
print(f"4.换电订单: {results['orders']['count']} 笔 | 实付: {results['orders']['amount_real']:.2f} 元 | 标价: {results['orders']['amount_gross']:.2f} 元")

# ── #169: 有消费记录的用户总数(替代'访客量→成交率') ──
cur.execute("""
    SELECT COUNT(DISTINCT take_user_id)
    FROM t_exchange_order
    WHERE order_status = 'success' AND is_del = 0
""")
results['paying_users'] = cur.fetchone()[0]
print(f"5.有换电记录用户: {results['paying_users']}")

# ── #169: 总用户数 ──
cur.execute("SELECT COUNT(*) FROM t_user WHERE is_del = 0")
results['total_users'] = cur.fetchone()[0]
print(f"6.总用户数: {results['total_users']}")

# ── #169: 协议总数 ──
cur.execute("SELECT COUNT(*) FROM t_exchange_agreement WHERE is_del = 0")
results['total_agreements'] = cur.fetchone()[0]
print(f"7.协议总数: {results['total_agreements']}")

conn.close()

# ── Patch dashboard_data.json ──
dp = "data/dashboard_data.json"
D = json.load(open(dp, encoding="utf-8"))

U = D.setdefault("user", {})
U_kpi = U.setdefault("kpi", {})
U_kpi["refund_count"] = results['refund']['count']
U_kpi["active_7d"] = results['active7d']
U_kpi["new_reg_30d_db"] = results['new_reg_30d']
U_kpi["order_count_total"] = results['orders']['count']
U_kpi["order_amount_total"] = results['orders']['amount_real']
U_kpi["paying_users"] = results['paying_users']
U_kpi["total_users_db"] = results['total_users']

F = D.setdefault("finance", {})
F["income_refund"] = results['refund']['amount']
F["order_amount_total"] = results['orders']['amount_real']

OV = D.setdefault("overview", {})
OV["user_total"] = results['total_users']
OV["agreement_total"] = results['total_agreements']

json.dump(D, open(dp, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
sz = os.path.getsize(dp)
print(f"\n✅ Patched JSON -> {sz/1024/1024:.1f}MB")
