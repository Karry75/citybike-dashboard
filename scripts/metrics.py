import json, pymysql, time, traceback
DB = json.load(open(r"D:/workboddy file/dudu分析/citybike_backup/config/backup_config.json", encoding="utf-8"))
NOW = int(time.time()*1000)
DAY = 86400000
def ms(n): return NOW - n*DAY

conn = pymysql.connect(host=DB["host"], port=DB["port"], user=DB["user"], password=DB["password"],
                       database=DB["database"], connect_timeout=15, read_timeout=600, charset="utf8mb4")
cur = conn.cursor()
M = {}
def q(sql, params=()):
    try:
        cur.execute(sql, params)
        return cur.fetchall()
    except Exception as e:
        return {"_error": str(e)[:200]}

# ---------- 数据总览 ----------
M["overview"] = {}
M["overview"]["user_total"] = q("SELECT COUNT(*) FROM t_user WHERE is_del=0")[0][0]
M["overview"]["user_new_30d"] = q("SELECT COUNT(*) FROM t_user WHERE is_del=0 AND create_time>=%s", (ms(30),))[0][0]
M["overview"]["battery_total"] = q("SELECT COUNT(*) FROM t_battery WHERE is_del=0")[0][0]
M["overview"]["cabinet_total_proxy"] = q("SELECT COUNT(DISTINCT device_sn) FROM t_battery WHERE device_sn IS NOT NULL AND device_sn<>''")[0][0]
M["overview"]["site_total"] = q("SELECT COUNT(*) FROM t_site WHERE is_del=0")[0][0]
M["overview"]["agreement_total"] = q("SELECT COUNT(*) FROM t_exchange_agreement WHERE is_del=0")[0][0]

# 网点套餐销量排行榜 (TOP15): package orders -> agreement -> site
r = q("""SELECT s.name, COUNT(*) cnt, SUM(o.real_fee) amt
         FROM t_user_exchange_package_order o
         JOIN t_exchange_agreement a ON o.exchange_agreement_id=a.id
         JOIN t_site s ON a.site_id=s.id
         WHERE o.order_status='success'
         GROUP BY s.id, s.name ORDER BY cnt DESC LIMIT 15""")
M["overview"]["site_package_sales_top15"] = [list(x) for x in r] if isinstance(r, list) else r

# 区域业务员销冠排行榜 (TOP15 by city)
r = q("""SELECT sys_city_name, sign_site_business_name, COUNT(*) cnt
         FROM t_exchange_agreement WHERE is_del=0 AND sign_site_business_name IS NOT NULL AND sign_site_business_name<>''
         GROUP BY sys_city_name, sign_site_business_name ORDER BY cnt DESC LIMIT 15""")
M["overview"]["salesman_top15"] = [list(x) for x in r] if isinstance(r, list) else r

# ---------- 用户看板 ----------
M["user"] = {}
M["user"]["total"] = M["overview"]["user_total"]
M["user"]["new_30d"] = M["overview"]["user_new_30d"]
M["user"]["agreement_status"] = [list(x) for x in q("SELECT status, COUNT(*) FROM t_exchange_agreement WHERE is_del=0 GROUP BY status")]
# active 7d (risky big scan)
r = q("SELECT COUNT(DISTINCT take_user_id) FROM t_exchange_order WHERE create_time>=%s", (ms(7),))
M["user"]["active_7d"] = r[0][0] if isinstance(r, (list, tuple)) else r
# top50 user value
r = q("""SELECT user_id, user_phone, SUM(real_fee) amt, COUNT(*) cnt
         FROM t_user_exchange_package_order WHERE order_status='success'
         GROUP BY user_id, user_phone ORDER BY amt DESC LIMIT 50""")
M["user"]["top50_value"] = [list(x) for x in r] if isinstance(r, list) else r
# city user ranking top30
r = q("""SELECT COALESCE(city,'未知') city, COUNT(*) cnt FROM t_user WHERE is_del=0 GROUP BY city ORDER BY cnt DESC LIMIT 30""")
M["user"]["city_top30"] = [list(x) for x in r] if isinstance(r, list) else r

# ---------- 销售看板 ----------
M["sales"] = {}
r = q("SELECT COUNT(*), SUM(real_fee), SUM(refund_fee) FROM t_user_exchange_package_order WHERE order_status='success'")
M["sales"]["package_order"] = [list(r[0])] if isinstance(r, list) else r
r = q("""SELECT package_name, COUNT(*) cnt, SUM(real_fee) amt FROM t_user_exchange_package_order
         WHERE order_status='success' GROUP BY package_name ORDER BY cnt DESC LIMIT 15""")
M["sales"]["package_by_name_top15"] = [list(x) for x in r] if isinstance(r, list) else r
# site sales last 30d
r = q("""SELECT s.name, COUNT(*) cnt, SUM(o.real_fee) amt FROM t_user_exchange_package_order o
         JOIN t_exchange_agreement a ON o.exchange_agreement_id=a.id JOIN t_site s ON a.site_id=s.id
         WHERE o.order_status='success' AND o.pay_time>=%s GROUP BY s.id,s.name ORDER BY cnt DESC LIMIT 10""", (ms(30),))
M["sales"]["site_sales_30d_top10"] = [list(x) for x in r] if isinstance(r, list) else r
# salesman sign top10
r = q("""SELECT sign_site_business_name, COUNT(*) cnt FROM t_exchange_agreement WHERE is_del=0
         AND sign_site_business_name IS NOT NULL AND sign_site_business_name<>'' GROUP BY sign_site_business_name ORDER BY cnt DESC LIMIT 10""")
M["sales"]["salesman_sign_top10"] = [list(x) for x in r] if isinstance(r, list) else r

# ---------- 网点看板 ----------
M["site"] = {}
M["site"]["total"] = M["overview"]["site_total"]
M["site"]["status"] = [list(x) for x in q("SELECT COALESCE(site_status,'未知'), COUNT(*) FROM t_site WHERE is_del=0 GROUP BY site_status")]
r = q("""SELECT site_name, COUNT(*) cnt FROM t_exchange_order WHERE create_time>=%s
         AND site_name IS NOT NULL AND site_name<>'' GROUP BY site_id, site_name ORDER BY cnt DESC LIMIT 30""", (ms(30),))
M["site"]["exchange_30d_top30"] = [list(x) for x in r] if isinstance(r, list) else r
r = q("""SELECT sale_site_name, COUNT(*) cnt, SUM(exchange_order_amount) amt FROM t_bike_sale_relation
         WHERE is_del=0 GROUP BY sale_site_id, sale_site_name ORDER BY cnt DESC LIMIT 15""")
M["site"]["sale_top15"] = [list(x) for x in r] if isinstance(r, list) else r

# ---------- 设备资产看板 ----------
M["device"] = {}
M["device"]["battery_total"] = M["overview"]["battery_total"]
M["device"]["battery_status"] = [list(x) for x in q("SELECT COALESCE(battery_status,'未知'), COUNT(*) FROM t_battery WHERE is_del=0 GROUP BY battery_status")]
M["device"]["battery_online"] = [list(x) for x in q("SELECT COALESCE(online_status,'未知'), COUNT(*) FROM t_battery WHERE is_del=0 GROUP BY online_status")]
r = q("SELECT device_type_id, COUNT(DISTINCT device_sn) cnt FROM t_battery WHERE device_sn<>'' GROUP BY device_type_id ORDER BY cnt DESC LIMIT 10")
M["device"]["cabinet_by_type_top10"] = [list(x) for x in r] if isinstance(r, list) else r

# ---------- 运维看板 ----------
M["ops"] = {}
M["ops"]["monitor_level"] = [list(x) for x in q("SELECT COALESCE(level,'未知'), COUNT(*) FROM t_monitor_ex_event WHERE is_del=0 GROUP BY level")]
M["ops"]["monitor_status"] = [list(x) for x in q("SELECT COALESCE(status,'未知'), COUNT(*) FROM t_monitor_ex_event WHERE is_del=0 GROUP BY status")]
M["ops"]["battery_alert"] = q("SELECT COUNT(*) FROM t_monitor_ex_event_battery")[0][0]
M["ops"]["work_order_status"] = [list(x) for x in q("SELECT COALESCE(status,'未知'), COUNT(*) FROM t_work_order WHERE is_del=0 GROUP BY status")]
M["ops"]["work_order_overdue"] = q("SELECT COUNT(*) FROM t_work_order WHERE is_del=0 AND is_overdue=1")[0][0]
r = q("SELECT COALESCE(event_name,'未知'), COUNT(*) cnt FROM t_work_order WHERE is_del=0 GROUP BY event_name ORDER BY cnt DESC LIMIT 10")
M["ops"]["work_order_event_top10"] = [list(x) for x in r] if isinstance(r, list) else r

# ---------- 人员看板 ----------
M["personnel"] = {}
M["personnel"]["promoter"] = q("SELECT COUNT(*) FROM t_promoter WHERE is_del=0")[0][0]
M["personnel"]["store_employee_on"] = q("SELECT COUNT(*) FROM t_site_store_employee WHERE is_del=0 AND status='on'")[0][0]
M["personnel"]["distributor_on"] = q("SELECT COUNT(*) FROM t_distributor WHERE is_del=0 AND status='on'")[0][0]
M["personnel"]["agency_employee"] = q("SELECT COUNT(*) FROM t_warehouse_agency_employee")[0][0]

# ---------- 财务看板 ----------
M["finance"] = {}
r = q("SELECT SUM(real_fee), SUM(refund_fee) FROM t_user_exchange_package_order WHERE order_status='success' AND is_pay=1")
M["finance"]["package_income_refund"] = [list(r[0])] if isinstance(r, list) else r
r = q("""SELECT COALESCE(expense_type,'未知'), COUNT(*), SUM(fee) FROM t_expense_bill
         WHERE is_del=0 GROUP BY expense_type ORDER BY SUM(fee) DESC LIMIT 12""")
M["finance"]["expense_by_type_top12"] = [list(x) for x in r] if isinstance(r, list) else r
M["finance"]["expense_settled"] = q("SELECT SUM(fee) FROM t_expense_bill WHERE is_del=0 AND bill_status='settle'")[0][0]

# ---------- 客服服务台 ----------
M["service"] = {}
M["service"]["feedback_count"] = q("SELECT COUNT(*) FROM t_feedback WHERE is_del=0")[0][0]
r = q("SELECT COALESCE(scene,'未知'), COUNT(*), ROUND(AVG(score),2) FROM t_feedback WHERE is_del=0 GROUP BY scene")
M["service"]["feedback_by_scene"] = [list(x) for x in r] if isinstance(r, list) else r
M["service"]["reception_count"] = q("SELECT COUNT(*) FROM t_reception_log")[0][0]

json.dump(M, open(r"D:/workboddy file/dudu分析/citybike_backup/data/metrics.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
conn.close()
print("METRICS_DONE")
for k, v in M.items():
    print("##", k)
    for kk, vv in v.items():
        if isinstance(vv, (list, dict)):
            print("  ", kk, "= (list/dict)")
        else:
            print("  ", kk, "=", vv)
