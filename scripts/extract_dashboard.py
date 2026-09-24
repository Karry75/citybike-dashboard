# -*- coding: utf-8 -*-
"""Extract citybike dashboard data (overview + 8 modules) into data/dashboard_data.json.
All timestamps (bigint ms) are converted to 'YYYY-MM-DD HH:MM:SS' strings.
Detail extracts are capped to keep the HTML self-contained & offline-capable.
"""
import json, pymysql, time, sys, datetime

DB = json.load(open(r"D:/workboddy file/dudu分析/citybike_backup/config/backup_config.json", encoding="utf-8"))
DB.pop("workers", None)
OUT = r"D:/workboddy file/dudu分析/citybike_backup/data/dashboard_data.json"
DETAIL_CAP = 5000
NOW = int(time.time() * 1000)
D7 = NOW - 7 * 86400000
D30 = NOW - 30 * 86400000
D90 = NOW - 90 * 86400000

def ms2str(v):
    if not v:
        return ""
    try:
        return (datetime.datetime.utcfromtimestamp(int(v) / 1000) + datetime.timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(v)

# ---------- 中文映射辅助 ----------
# 网点状态：实际数据来源为 t_site.audit_progress（八态），非 site_status(on/off)
SITE_STATUS_CN = {"have_opened": "已开业", "closed": "已关闭", "not_cooperation": "未合作",
                  "wait_delivery": "待送货", "wait_install": "待安装", "wait_audit": "待审批",
                  "wait_open": "待开业", "wait_acceptance": "待验收", "": "—", None: "—"}
SITE_ONOFF_CN = {"on": "已开业", "off": "已关闭", "": "—", None: "—"}
STATUS_CN = {"working": "生效中", "cancelled": "已取消", "owe_rent": "欠租", "stop": "已终止",
             "paused": "已暂停", "unsubscribing": "退订中", "wait_activate": "待激活", "": "—", None: "—"}
AGREEMENT_TYPE_CN = {"single": "个人", "company": "企业", "": "—", None: "—"}
FIRST_CN = {1: "是", 0: "否", "1": "是", "0": "否", "": "—", None: "—"}
BOOL_CN = {1: "是", 0: "否", "1": "是", "0": "否", True: "是", False: "否", "": "—", None: "—"}
TYPE_CN = {"single": "个人", "company": "企业"}
DEPOSIT_STATUS_CN = {"on": "已缴纳", "off": "未缴纳", "": "—"}
DEPOSIT_PAYWAY_CN = {"money": "现金", "wechat_mini": "微信", "alipay_mini": "支付宝小程序",
                     "system_present": "系统赠送", "wechat_free": "微信免押", "alipay_free": "支付宝免押",
                     "sys_city_id": "城市", "": "—"}
ALONE_METER_CN = {"not_install": "不安装", "only_install": "仅安装", "install_and_use": "安装并用于电费结算",
                  "gdj_install": "供电局安装", "": "—"}
ELECTRIC_WAY_CN = {"online": "线上", "offline": "线下", "gdj_deduct": "供电局扣减", "not_settle": "不结算", "": "—"}  # gdj=供电局(同 ALONE_METER_CN.gdj_install)；gdj_deduct=电费由供电局直扣，not_settle=不参与电费结算
ONLINE_CN = {"online": "在线", "offline": "离线", "unregister": "未注册", "": "—"}
STORE_STATUS_CN = {"full": "满电", "charging": "充电中", "none": "空闲", "error": "故障", "": "—"}
LOCATE_CN = {"indoor": "室内", "outdoor": "室外", "": "—"}
CAB_STATUS_CN = {"on": "已开业", "off": "已关闭", "delivered": "已交付", "await_deliver": "待交付", "": "—"}
# 电池仓位真值（来自 t_battery_belong_relation.belong_type，5 类）
BELONG_TYPE_CN = {"operate_platform": "运营平台仓库", "bike": "车辆仓库",
                  "exchange": "换电柜仓库", "agency_employee": "代理商员工仓库",
                  "site": "网点仓库", "": "未识别", None: "未识别"}

def _cn(d, key, default="—"):
    return d.get(key, default) if key else default

def _bool_cn(v, t="是", f="否"):
    return t if v else f

def _remain_days(expire_ms):
    """剩余租期（天），负数表示已超期"""
    if not expire_ms:
        return "—"
    d = (int(expire_ms) - NOW) / 86400000.0
    if d >= 0:
        return "%.0f天" % d
    return "已超期%.0f天" % (-d)

def _overdue_days(expire_ms):
    """欠租天数：租金已到期且未终止则记超期天数"""
    if not expire_ms:
        return 0
    if int(expire_ms) < NOW:
        return max(0, int((NOW - int(expire_ms)) / 86400000.0))
    return 0

def _deposit_deduct(status, bind_ms, unbind_ms):
    """押金划扣状态推导"""
    if status == "off":
        return "未缴纳"
    if bind_ms and not unbind_ms:
        return "正常(已绑定)"
    if unbind_ms:
        return "已解绑"
    return "已缴纳"

def _promoter_info(pid):
    if not pid:
        return "—"
    name = promoter_map.get(pid, {}).get("name") if pid in promoter_map else None
    phone = promoter_phone_map.get(pid)
    if name:
        return "%s(%s)" % (name, phone) if phone else name
    return "推广员#%s" % pid

conn = pymysql.connect(host=DB["host"], port=DB["port"], user=DB["user"], password=DB["password"],
                       database=DB["database"], connect_timeout=15, read_timeout=600, charset="utf8mb4")
cur = conn.cursor()

D = {}
ERR = []
def q(sql, label, many=False):
    try:
        cur.execute(sql)
        return cur.fetchall() if many else (cur.fetchone()[0] if cur.rowcount else None)
    except Exception as e:
        ERR.append("%s: %s" % (label, str(e)[:200]))
        print("ERR", label, str(e)[:200], file=sys.stderr)
        return [] if many else None

# ---------- 维度映射表（口径补全：代理商 / 柜类型 / 电池品牌 / 网点类型） ----------
def _map(sql, label):
    return q(sql, label, many=True) or []
site_map = {}
for r in _map("SELECT id, name, city, distributor_id FROM t_site WHERE is_del=0", "map_site"):
    site_map[r[0]] = {"name": r[1] or "未知网点", "city": r[2] or "", "distributor_id": r[3]}
distributor_map = {}
for r in _map("SELECT id, name FROM t_distributor WHERE is_del=0", "map_dis"):
    distributor_map[r[0]] = r[1] or ("代理商#%s" % r[0])
device_type_map = {}
for r in _map("SELECT id, device_product_name FROM t_device_type", "map_dt"):
    device_type_map[r[0]] = r[1] or ("类型#%s" % r[0])
BATTERY_BRAND_MAP = {}  # 待用户提供 编码→品牌 对照；命中则展示可读品牌
battery_brand_map = {}
for r in _map("SELECT id, name FROM t_battery_brand", "map_bb"):
    battery_brand_map[r[0]] = BATTERY_BRAND_MAP.get(r[1], r[1] or ("品牌#%s" % r[0]))
SITE_TYPE_CN = {1: "换电", 2: "车吧", 4: "售车", 5: "租车", 7: "其他(脏数据)"}
# 赠送 / 免押 / 兑换码 / 补贴 等渠道枚举（来自 pay_way 实际取值探查）
GIFT_WAYS = ("deposit", "deposit_present", "present_rent", "zero", "sys_free",
             "alipay_free", "wechat_free", "redemption", "subsidy")
GIFT_IN = "','".join(GIFT_WAYS)

# ---------- P0 补全映射（代理商/商户/型号/业务员手机/设备→网点/监控/仓位状态） ----------
merchant_map = {}
for r in _map("SELECT id, name, lp_phone FROM t_merchant WHERE is_del=0", "map_mer"):
    merchant_map[r[0]] = {"name": r[1] or ("商户#%s" % r[0]), "phone": r[2] or ""}
exchange_model_map = {}
for r in _map("SELECT device_type_id, show_name FROM t_exchange_model WHERE is_del=0", "map_em"):
    exchange_model_map[r[0]] = r[1] or ""
promoter_phone_map = {}
for r in _map("SELECT agency_employee_id, phone FROM t_promoter WHERE is_del=0", "map_pp"):
    if r[0] is not None:
        promoter_phone_map[r[0]] = r[1] or ""
promoter_map = {}
for r in _map("SELECT id, name, phone FROM t_promoter WHERE is_del=0", "map_prom"):
    promoter_map[r[0]] = {"name": r[1] or "", "phone": r[2] or ""}
# 门店导购（签约网点导购人员）：t_site_store_employee
guide_map = {}
for r in _map("SELECT id, name, phone FROM t_site_store_employee WHERE is_del=0", "map_guide"):
    if r[0] is not None:
        guide_map[r[0]] = {"name": r[1] or "", "phone": r[2] or ""}
# 电池产品 / 型号映射
battery_product_map = {}
for r in _map("SELECT id, name FROM t_battery_product WHERE is_del=0", "map_bp"):
    battery_product_map[r[0]] = r[1] or ("电池产品#%s" % r[0])
battery_model_map = {}
for r in _map("SELECT id, name FROM t_battery_model WHERE is_del=0", "map_bm"):
    battery_model_map[r[0]] = r[1] or ("型号#%s" % r[0])
# 设备SN → 网点ID（用于电池归属网点反查）
device_site_map = {}
for r in _map("SELECT device_sn, site_id FROM t_exchange WHERE is_del=0", "map_ds"):
    device_site_map[r[0]] = r[1]
# 网点是否有监控（存在活跃安装记录即视为有监控）
site_monitor_map = {}
for r in _map("SELECT DISTINCT site_id FROM t_monitor_install_log WHERE status='install' AND is_del=0", "map_mon"):
    site_monitor_map[r[0]] = True
# 网点换电柜仓位状态聚合（full/error/charging/none/total）
site_cabinet_map = {}
for r in _map(
    "SELECT e.site_id, es.status, COUNT(*) c FROM t_exchange_store es "
    "JOIN t_exchange e ON es.device_sn=e.device_sn WHERE es.is_del=0 AND e.is_del=0 "
    "GROUP BY e.site_id, es.status", "map_cab"):
    sid, st, c = r[0], r[1], r[2]
    d = site_cabinet_map.setdefault(sid, {"full": 0, "error": 0, "charging": 0, "none": 0, "total": 0})
    if st == "full":
        d["full"] += c
    elif st == "error":
        d["error"] += c
    elif st == "charging":
        d["charging"] += c
    elif st == "none":
        d["none"] += c
    d["total"] += c

# ---------- OVERVIEW ----------
D["meta"] = {"generated_at": ms2str(NOW), "db": DB["database"], "detail_cap": DETAIL_CAP}
D["overview"] = {}
D["overview"]["user_total"] = q("SELECT COUNT(*) FROM t_user WHERE is_del=0", "ov_user")
D["overview"]["cabinet_total"] = q("SELECT COUNT(DISTINCT device_sn) FROM t_exchange_store", "ov_cabinet")
D["overview"]["battery_total"] = q("SELECT COUNT(*) FROM t_battery WHERE is_del=0", "ov_battery")
D["overview"]["site_total"] = q("SELECT COUNT(*) FROM t_site WHERE is_del=0", "ov_site")
D["overview"]["agreement_total"] = q("SELECT COUNT(*) FROM t_exchange_agreement", "ov_agt")
# 网点套餐销量排行榜 (by site)
D["overview"]["pkg_sales_by_site"] = [
    {"site": (r[0] or "未知网点"), "count": r[1]} for r in q(
        "SELECT s.name, COUNT(*) c FROM t_exchange_agreement a LEFT JOIN t_site s ON a.site_id=s.id "
        "GROUP BY a.site_id, s.name ORDER BY c DESC LIMIT 15", "pkg_site", many=True) or []
]
# 套餐销量排行 (by package name)
D["overview"]["pkg_sales_by_pkg"] = [
    {"pkg": (r[0] or "未知套餐"), "count": r[1]} for r in q(
        "SELECT p.name, COUNT(*) c FROM t_exchange_agreement a LEFT JOIN t_exchange_rent_package p ON a.rent_package_id=p.id "
        "GROUP BY a.rent_package_id ORDER BY c DESC LIMIT 15", "pkg_pkg", many=True) or []
]
# 区域业务员销冠
D["overview"]["promoter_rank"] = [
    {"city": r[0], "promoter": r[1], "count": r[2]} for r in q(
        "SELECT sys_city_name, sign_site_business_name, COUNT(*) c FROM t_exchange_agreement "
        "WHERE sign_site_business_name IS NOT NULL AND sign_site_business_name<>'' "
        "GROUP BY sys_city_id, sign_site_business_id ORDER BY c DESC LIMIT 20", "promo", many=True) or []
]

# ---------- 用户看板 ----------
U = D["user"] = {}
U["total"] = D["overview"]["user_total"]
U["new_30d"] = q("SELECT COUNT(*) FROM t_user WHERE is_del=0 AND create_time>=%d" % D30, "u_new30")
# 协议状态分布
st = q("SELECT status, COUNT(*) c FROM t_exchange_agreement GROUP BY status ORDER BY c DESC", "u_status", many=True) or []
U["by_status"] = [{"status": r[0], "count": r[1]} for r in st]
# 活跃(近7天换电)
U["active_7d"] = q(
    "SELECT COUNT(DISTINCT take_user_id) FROM t_exchange_order WHERE order_status='success' AND take_battery_time>=%d" % D7, "u_act7")
# 近30天活跃
active_30 = q(
    "SELECT COUNT(DISTINCT take_user_id) FROM t_exchange_order WHERE order_status='success' AND take_battery_time>=%d" % D30, "u_act30") or 0
working_users = q("SELECT COUNT(DISTINCT user_id) FROM t_exchange_agreement WHERE status='working'", "u_working") or 0
U["low_freq_30d"] = max(working_users - active_30, 0)  # 估算口径：在生效协议但未近30天换电
# 用户价值 Top50
U["top50_value"] = [
    {"name": r[0], "phone": r[1], "exchanges": r[2], "amount": (r[3] or 0) / 100.0}
    for r in q(
        "SELECT u.username, u.phone, COUNT(*) cnt, SUM(o.real_pay_price) amt FROM t_exchange_order o "
        "JOIN t_user u ON o.take_user_id=u.id WHERE o.order_status='success' "
        "GROUP BY o.take_user_id ORDER BY amt DESC LIMIT 50", "u_top50", many=True) or []
]
# 城市骑行/换电排行 Top30
U["city_rank"] = [
    {"city": r[0], "count": r[1]} for r in q(
        "SELECT sys_city_name, COUNT(*) c FROM t_exchange_order WHERE order_status='success' "
        "GROUP BY sys_city_id ORDER BY c DESC LIMIT 30", "u_city", many=True) or []
]
# 购买金额（套餐订单）
rent_ids = "(SELECT id FROM t_exchange_rent_package)"
pow_ids = "(SELECT id FROM t_exchange_package)"
U["purchase"] = {}
U["purchase"]["consume_total"] = (q(
    "SELECT COALESCE(SUM(real_fee),0) FROM t_user_exchange_package_order WHERE order_status='success'", "u_cons") or 0) / 100.0
U["purchase"]["refund_total"] = (q(
    "SELECT COALESCE(SUM(refund_fee),0) FROM t_user_exchange_package_order WHERE is_refund=1", "u_refund") or 0) / 100.0
# 租期卡（真正的租期套餐订单 t_user_exchange_rent_package_order，单位分）
U["purchase"]["rent_card_total"] = (q(
    "SELECT COALESCE(SUM(combo_real_fee),0) FROM t_user_exchange_rent_package_order WHERE is_pay=1", "u_rent") or 0) / 100.0
U["purchase"]["power_card_total"] = (q(
    "SELECT COALESCE(SUM(real_fee),0) FROM t_user_exchange_package_order WHERE order_status='success' AND package_id IN %s" % pow_ids, "u_pow") or 0) / 100.0
# 押金套餐订单实付（单位分）
U["purchase"]["deposit_card_total"] = (q(
    "SELECT COALESCE(SUM(real_fee),0) FROM t_user_exchange_deposit_package_order WHERE is_pay=1", "u_dep") or 0) / 100.0
# 赠送（免押 / 押金赠送 / 兑换码 / 补贴等口径，跨三表；gift_amount 取各表套餐价值字段，单位分）
def _gift_cnt(tab):
    return q("SELECT COUNT(*) FROM %s WHERE pay_way IN ('%s')" % (tab, GIFT_IN), "u_gc_" + tab) or 0
def _gift_amt(tab, col):
    return (q("SELECT COALESCE(SUM(%s),0) FROM %s WHERE pay_way IN ('%s')" % (col, tab, GIFT_IN), "u_ga_" + tab) or 0) / 100.0
U["purchase"]["gift_count"] = (_gift_cnt("t_user_exchange_package_order") + _gift_cnt("t_user_exchange_rent_package_order")
                               + _gift_cnt("t_user_exchange_deposit_package_order"))
U["purchase"]["gift_amount"] = (_gift_amt("t_user_exchange_package_order", "will_pay_fee")
                                + _gift_amt("t_user_exchange_rent_package_order", "will_pay_fee")
                                + _gift_amt("t_user_exchange_deposit_package_order", "fee"))
# 用户明细（协议级，最近激活优先，cap）—— 补：代理商、激活日期
rows = q(
    "SELECT a.id, u.phone, u.username, a.sys_city_name, bp.name, ag.name, a.type, a.status, a.activation_time, "
    "a.rent_expire_time, a.deposit_fee, a.user_rent_id, a.agency_id, ao.agency_name, s2.distributor_id "
    "FROM t_exchange_agreement a LEFT JOIN t_user u ON a.user_id=u.id "
    "LEFT JOIN t_battery_product bp ON a.battery_product_id=bp.id "
    "LEFT JOIN t_exchange_rent_package ag ON a.rent_package_id=ag.id "
    "LEFT JOIN (SELECT DISTINCT agency_id, agency_name FROM t_exchange_order WHERE agency_name IS NOT NULL) ao ON a.agency_id=ao.agency_id "
    "LEFT JOIN t_site s2 ON a.site_id=s2.id "
    "ORDER BY a.activation_time DESC LIMIT %d" % DETAIL_CAP, "u_detail", many=True) or []
U["detail"] = [{"agreement_id": r[0], "phone": r[1], "name": r[2], "city": r[3], "battery_product": r[4],
               "package": r[5], "type": r[6], "status": r[7], "activate": ms2str(r[8]),
               "expire": ms2str(r[9]), "deposit_fee": (r[10] or 0) / 100.0, "rent_id": r[11],
               "agency_id": r[12], "agency": (r[13] or ("代理商#"+str(r[12] or "?"))),
               "distributor_name": distributor_map.get(r[14]) or "—",
               "activate_date": ms2str(r[8])[:10]} for r in rows]

# ---------- 销售看板 ----------
S = D["sales"] = {}
# 套餐购买统计
S["pkg_income"] = (q("SELECT COALESCE(SUM(real_fee),0) FROM t_user_exchange_package_order WHERE order_status='success'", "s_inc") or 0) / 100.0
S["pkg_refund"] = (q("SELECT COALESCE(SUM(refund_fee),0) FROM t_user_exchange_package_order WHERE is_refund=1", "s_ref") or 0) / 100.0
S["pkg_rent_total"] = U["purchase"]["rent_card_total"]
S["pkg_power_total"] = U["purchase"]["power_card_total"]
S["pkg_deposit_total"] = U["purchase"]["deposit_card_total"]
S["pkg_gift_count"] = U["purchase"]["gift_count"]
S["pkg_gift_amount"] = U["purchase"]["gift_amount"]
# 网点近一个月销售排行（城市/套餐/电池产品 前10）
S["site_sales_30d"] = [
    {"site": (r[0] or "未知网点"), "city": r[1], "pkg": r[2] or "未知", "battery": r[3] or "未知", "count": r[4]}
    for r in q(
        "SELECT s.name, a.sys_city_name, p.name, bp.name, COUNT(*) c FROM t_exchange_agreement a "
        "LEFT JOIN t_site s ON a.site_id=s.id "
        "LEFT JOIN t_exchange_rent_package p ON a.rent_package_id=p.id "
        "LEFT JOIN t_battery_product bp ON a.battery_product_id=bp.id "
        "WHERE a.create_time>=%d GROUP BY a.site_id, s.name, a.rent_package_id, p.name, bp.name ORDER BY c DESC LIMIT 10" % D30, "s_site30", many=True) or []
]
# 业务员销冠（城市/签约数量 前10）
S["promoter_rank"] = [
    {"city": r[0], "promoter": r[1], "count": r[2]} for r in q(
        "SELECT sys_city_name, sign_site_business_name, COUNT(*) c FROM t_exchange_agreement "
        "WHERE sign_site_business_name IS NOT NULL AND sign_site_business_name<>'' "
        "GROUP BY sys_city_id, sign_site_business_id ORDER BY c DESC LIMIT 10", "s_promo", many=True) or []
]
# 销售明细（签约协议级，支持按 城市/电池产品/套餐/代理商/业务员/商户/渠道商 筛选）
rows = q(
    "SELECT a.id, a.sys_city_name, bp.name, ag.name, a.sign_site_business_name, s.name, a.distributor_id, "
    "a.agency_id, a.sign_site_business_id, s.merchant_id, a.status, a.activation_time "
    "FROM t_exchange_agreement a "
    "LEFT JOIN t_battery_product bp ON a.battery_product_id=bp.id "
    "LEFT JOIN t_exchange_rent_package ag ON a.rent_package_id=ag.id "
    "LEFT JOIN t_site s ON a.site_id=s.id "
    "ORDER BY a.create_time DESC LIMIT %d" % DETAIL_CAP, "s_detail", many=True) or []
S["detail"] = [{"agreement_id": r[0], "city": r[1], "battery_product": r[2], "package": r[3],
               "promoter": (r[4] or "—"), "site": (r[5] or "—"), "distributor_id": r[6],
               "distributor_name": distributor_map.get(r[6]) or "—",
               "agency_id": r[7], "agency": distributor_map.get(r[7]) or "—",
               "business_id": r[8], "business": (r[4] or "—"),
               "business_phone": promoter_phone_map.get(r[8], "—"),
               "merchant_id": r[9], "merchant": merchant_map.get(r[9], {}).get("name", "—"),
               "merchant_phone": merchant_map.get(r[9], {}).get("phone", "—"),
               "status": r[10], "activate": ms2str(r[11])} for r in rows]

# ---------- 维度映射补全（行业 / 换电柜实时 / 电池实时 / 周期计数） ----------
industry_map = {}
for r in _map("SELECT id, name FROM t_site_industry WHERE is_del=0", "map_ind"):
    industry_map[r[0]] = r[1] or ("行业#%s" % r[0])
# 换电柜实时上报（安全/电气/温度）：t_exchange_last_upload，按 device_sn
cabinet_realtime_map = {}
for r in _map(
    "SELECT device_sn, smoke, flooded, fire, e_meter_v, e_meter_a, e_meter_w, e_meter_wh, temp, last_upload_time "
    "FROM t_exchange_last_upload WHERE is_del=0", "map_cab_rt"):
    if r[0]:
        cabinet_realtime_map[r[0]] = {
            "smoke": r[1], "flooded": r[2], "fire": r[3],
            "e_meter_v": r[4], "e_meter_a": r[5], "e_meter_w": r[6], "e_meter_wh": r[7],
            "temp": r[8], "last_upload": r[9]}
# 电池实时遥测：t_battery_last_upload + t_battery_status，按 battery_sn
battery_rt_last = {}
for r in _map(
    "SELECT battery_sn, power, charging, discharge, cycle, voltage, current, cell_temp_min, cell_temp_max, "
    "discharge_temp, charging_temp, main_s, main_h, update_time "
    "FROM t_battery_last_upload WHERE is_del=0", "map_bat_lu"):
    if r[0]:
        battery_rt_last[r[0]] = {
            "power": r[1], "charging": r[2], "discharge": r[3], "cycle": r[4], "voltage": r[5],
            "current": r[6], "cell_temp_min": r[7], "cell_temp_max": r[8], "discharge_temp": r[9],
            "charging_temp": r[10], "main_s": r[11], "main_h": r[12], "last_upload": r[13]}
battery_rt_status = {}
for r in _map(
    "SELECT device_sn, using, charging, discharge, voltage_out, current_out, cycle "
    "FROM t_battery_status WHERE is_del=0", "map_bat_st"):
    if r[0]:
        battery_rt_status[r[0]] = {
            "using": r[1], "charging": r[2], "discharge": r[3], "voltage_out": r[4],
            "current_out": r[5], "cycle": r[6]}
# 换电柜 7/30/90 天换电次数与用户数（best-effort，按柜聚合最近90天订单）
cabinet_daycount_map = {}
try:
    dc_rows = q(
        "SELECT ex_id, "
        "SUM(CASE WHEN ct>=%d THEN 1 ELSE 0 END) c7, COUNT(DISTINCT CASE WHEN ct>=%d THEN uid END) u7, "
        "SUM(CASE WHEN ct>=%d THEN 1 ELSE 0 END) c30, COUNT(DISTINCT CASE WHEN ct>=%d THEN uid END) u30, "
        "COUNT(*) c90, COUNT(DISTINCT uid) u90 "
        "FROM ("
        "  SELECT take_exchange_id ex_id, consume_user_id uid, create_time ct FROM t_exchange_order WHERE create_time>=%d AND take_exchange_id IS NOT NULL "
        "  UNION ALL "
        "  SELECT back_exchange_id ex_id, consume_user_id uid, create_time ct FROM t_exchange_order WHERE create_time>=%d AND back_exchange_id IS NOT NULL "
        ") t GROUP BY ex_id" % (D7, D7, D30, D30, D90, D90),
        "map_cab_dc", many=True) or []
    for r in dc_rows:
        cabinet_daycount_map[r[0]] = {"c7": r[1], "u7": r[2], "c30": r[3], "u30": r[4], "c90": r[5], "u90": r[6]}
except Exception as e:
    ERR.append("map_cab_dc: %s" % str(e)[:200])
# 电池 30/90 天借出次数（best-effort，流通记录 outflow=借出）
battery_circulate_map = {}
try:
    circ_rows = q(
        "SELECT battery_device_sn, "
        "SUM(CASE WHEN create_time>=%d THEN 1 ELSE 0 END) c30, "
        "SUM(CASE WHEN create_time>=%d THEN 1 ELSE 0 END) c90 "
        "FROM t_battery_circulate_log WHERE outflow_id IS NOT NULL AND business_type_first='exchange_order' GROUP BY battery_device_sn"
        % (D30, D90), "map_bat_circ", many=True) or []
    for r in circ_rows:
        battery_circulate_map[r[0]] = {"c30": r[1], "c90": r[2]}
except Exception as e:
    ERR.append("map_bat_circ: %s" % str(e)[:200])

# ---------- 网点看板 ----------
W = D["site"] = {}
W["total"] = D["overview"]["site_total"]
ss = q("SELECT site_status, COUNT(*) c FROM t_site WHERE is_del=0 GROUP BY site_status", "w_status", many=True) or []
W["by_status"] = [{"status": r[0], "count": r[1]} for r in ss]
# 网点类型分布（中文映射：1换电 / 2车吧 / 4售车，5/7 待业务确认）
st = q("SELECT type, COUNT(*) c FROM t_site WHERE is_del=0 GROUP BY type", "w_type", many=True) or []
W["by_type"] = [{"type": r[0], "type_name": SITE_TYPE_CN.get(r[0], "未知(%s)" % r[0]), "count": r[1]} for r in st]
# 近一个月换电次数排行
W["exchange_rank_30d"] = [
    {"site": r[0], "city": r[1], "count": r[2]} for r in q(
        "SELECT site_name, sys_city_name, COUNT(*) c FROM t_exchange_order "
        "WHERE order_status='success' AND take_battery_time>=%d GROUP BY site_id ORDER BY c DESC LIMIT 30" % D30, "w_ex30", many=True) or []
]
# 售车排行（关联售车记录）
W["bike_sale_rank"] = [
    {"site": r[0], "count": r[1]} for r in q(
        "SELECT site_name, COUNT(DISTINCT bike_sale_log_id) c FROM t_exchange_order "
        "WHERE bike_sale_log_id>0 GROUP BY site_id ORDER BY c DESC LIMIT 20", "w_bike", many=True) or []
]
# 电费支出（已结算）
W["electric_fee"] = [
    {"site": r[0], "amount": (r[1] or 0) / 100.0} for r in q(
        "SELECT site_name, COALESCE(SUM(settle_amount),0) FROM t_exchange_electric_settlement "
        "WHERE settle_status='finish_settle' GROUP BY site_id ORDER BY SUM(settle_amount) DESC LIMIT 20", "w_elec", many=True) or []
]
# 网点明细（渲染层 26 列中文规范）
site_cabinet_count_map = {}
for r in _map("SELECT site_id, COUNT(*) c FROM t_exchange WHERE is_del=0 GROUP BY site_id", "map_scc"):
    site_cabinet_count_map[r[0]] = r[1]
site_cabinet_onoff_map = {}
for r in _map("SELECT site_id, online_status, COUNT(*) c FROM t_exchange WHERE is_del=0 GROUP BY site_id, online_status", "map_sco"):
    d = site_cabinet_onoff_map.setdefault(r[0], {"online": 0, "offline": 0})
    if r[1] == "online":
        d["online"] += r[2]
    else:
        d["offline"] += r[2]
agency_name_map = {}
for r in _map("SELECT DISTINCT agency_id, agency_name FROM t_exchange_order WHERE agency_name IS NOT NULL", "map_an"):
    if r[0] is not None:
        agency_name_map[r[0]] = r[1]
rows = q(
    "SELECT id, name, images, industry_id, type, audit_progress, locating_place, alone_meter_status, "
    "electric_settle_way, address, create_time, start_open_time, close_time, is_show, is_promoter, "
    "merchant_id, business_id, business_name, business_type, agency_id, distributor_id, battery_product_id, "
    "site_status, remark, province, city, area "
    "FROM t_site WHERE is_del=0 ORDER BY create_time DESC LIMIT 15000", "w_detail", many=True) or []  # 网点全量(~11075)
# 注：SELECT 顺序 id,name,images,industry_id,type,audit_progress,locating_place,alone_meter_status,
#   electric_settle_way,address,create_time,start_open_time,close_time,is_show,is_promoter,
#   merchant_id,business_id,business_name,business_type,agency_id,distributor_id,battery_product_id,site_status,remark,
#   province,city,area
def _site_battery(sid):
    d = site_cabinet_map.get(sid)
    if not d:
        return "0/0"
    allb = d["full"] + d["error"] + d["charging"]
    avail = d["full"] + d["charging"]
    return "%d/%d" % (allb, avail)
def _site_cabinet_status(sid):
    d = site_cabinet_onoff_map.get(sid)
    if not d:
        return "无柜机"
    return "在线%d/离线%d" % (d["online"], d["offline"])
W["detail"] = [{
    "id": r[0], "name": r[1] or "—", "images": r[2] or "",
    "industry": industry_map.get(r[3], "行业#%s" % r[3] if r[3] else "—"),
    "type": r[4], "type_name": SITE_TYPE_CN.get(r[4], "未知(%s)" % r[4]),
    "cabinet_count": site_cabinet_count_map.get(r[0], 0),
    "cabinet_status": _site_cabinet_status(r[0]),
    "battery_count": _site_battery(r[0]),
    "agency": ("%s#%s" % (agency_name_map.get(r[19], "未知代理商"), r[19]) if r[19] else "—"),
    "agency_id": r[19],
    "distributor": ("%s#%s" % (distributor_map.get(r[20], "未知渠道商"), r[20]) if r[20] else "—"),
    "distributor_id": r[20],
    "merchant": ("%s#%s" % (merchant_map.get(r[15], {}).get("name", "未知商家"), r[15]) if r[15] else "—"),
    "merchant_id": r[15],
    "business": ("%s#%s" % (r[17] or "未知业务员", r[16]) if r[16] else "—"),
    "business_id": r[16],
    "battery_product": battery_product_map.get(r[21], "电池产品#%s" % r[21] if r[21] else "—"),
    "status": SITE_STATUS_CN.get(r[5], r[5] or "—"),
    "locating": LOCATE_CN.get(r[6], r[6] or "—"),
    "monitor": ("有监控" if r[0] in site_monitor_map else "无监控"),
    "is_promoter": BOOL_CN.get(r[14], "—"),
    "sale_qrcode": "未接入",  # t_site 无售车二维码字段，诚实标注"未接入"而非伪造
    "meter": ALONE_METER_CN.get(r[7], r[7] or "—"),
    "settle_way": ELECTRIC_WAY_CN.get(r[8], r[8] or "—"),
    "address": r[9] or "—",
    "create": ms2str(r[10]), "open": ms2str(r[11]), "close": ms2str(r[12]),
    "is_show": BOOL_CN.get(r[13], "—"),
    "remark": r[23] or "—",
    "province": r[24] or "—", "city": r[25] or "—", "area": r[26] or "—"
} for r in rows]

# ---------- 设备资产看板 ----------
E = D["device"] = {}
E["cabinet_total"] = D["overview"]["cabinet_total"]
E["cabinet_online"] = q("SELECT COUNT(DISTINCT device_sn) FROM t_exchange_store WHERE status IN ('full','charging') OR last_upload_time>=%d" % (NOW-86400000), "e_con")
E["cabinet_offline"] = E["cabinet_total"] - E["cabinet_online"]
# 不同仓位数的换电柜数量
E["by_slot"] = [
    {"slots": r[0], "count": r[1]} for r in q(
        "SELECT slot_cnt, COUNT(*) c FROM (SELECT device_sn, COUNT(*) slot_cnt FROM t_exchange_store "
        "GROUP BY device_sn) t GROUP BY slot_cnt ORDER BY slot_cnt LIMIT 20", "e_slot", many=True) or []
]
E["battery_total"] = D["overview"]["battery_total"]
E["battery_online"] = q("SELECT COUNT(*) FROM t_battery WHERE is_del=0 AND online_status='online'", "e_bon")
E["battery_offline"] = q("SELECT COUNT(*) FROM t_battery WHERE is_del=0 AND online_status='offline'", "e_boff")
# 换电柜明细（柜级聚合 + 实时安全/电气 + 周期计数）
def _safe_flag(v):
    if v in ("1", 1, "1.0"):
        return "触发"
    if v in ("0", 0, "0.0", "", None):
        return "正常"
    return str(v)
rows = q(
    "SELECT es.device_sn, COUNT(*) total, "
    "SUM(CASE WHEN es.status IN ('full','charging','error') THEN 1 ELSE 0 END) have_battery, "
    "SUM(CASE WHEN es.status IN ('full','charging') THEN 1 ELSE 0 END) avail, "
    "SUM(CASE WHEN es.status='none' THEN 1 ELSE 0 END) empty, "
    "SUM(CASE WHEN es.status='error' THEN 1 ELSE 0 END) err, "
    "SUM(CASE WHEN es.soft_lock_status='on' THEN 1 ELSE 0 END) locked, "
    "MAX(es.last_upload_time) lu, "
    "e.id, e.device_type_id, e.scheme_version, e.meter_value, e.online_status, "
    "e.last_online_time, e.last_offline_time, e.site_id, e.agency_id, e.supplier_name, e.oem_device_status, "
    "s.city, s.area, s.street, s.address, s.business_name, s.contact_person_name, s.contact_person_tel "
    "FROM t_exchange_store es "
    "LEFT JOIN t_exchange e ON es.device_sn=e.device_sn AND e.is_del=0 "
    "LEFT JOIN t_site s ON e.site_id=s.id "
    "WHERE es.is_del=0 "
    "GROUP BY es.device_sn, e.id, e.device_type_id, e.scheme_version, e.meter_value, e.online_status, "
    "e.last_online_time, e.last_offline_time, e.site_id, e.agency_id, e.supplier_name, e.oem_device_status, "
    "s.city, s.area, s.street, s.address, s.business_name, s.contact_person_name, s.contact_person_tel "
    "ORDER BY total DESC LIMIT 12000", "e_detail", many=True) or []  # 换电柜全量(~8607)
E["cabinet_detail"] = []
for r in rows:
    _rt = cabinet_realtime_map.get(r[0], {}) or {}
    _dc = cabinet_daycount_map.get(r[0], {}) or {}
    E["cabinet_detail"].append({
        "sn": r[0], "total": r[1], "have_battery": r[2], "avail": r[3], "empty": r[4], "err": r[5], "locked": r[6],
        "returnable": ((r[1] or 0) - (r[2] or 0)) if (isinstance(r[1], (int, float)) and isinstance(r[2], (int, float))) else 0,
        "last_upload": ms2str(r[7]), "id": r[8],
        "model": exchange_model_map.get(r[9], "") or device_type_map.get(r[9], "—"),
        "scheme_version": r[10] or "—", "meter_value": r[11], "online": ONLINE_CN.get(r[12], r[12] or "—"),
        "last_online": ms2str(r[13]), "last_offline": ms2str(r[14]), "site_id": r[15],
        "agency_id": r[16], "supplier": r[17] or "—",
        "active": ("已激活" if (r[18] == "delivered") else "未激活"),
        "city": r[19] or "", "area": r[20] or "", "street": r[21] or "", "address": r[22] or "—",
        "business": r[23] or "—", "contact": r[24] or "—", "contact_tel": r[25] or "—",
        "site_name": (site_map.get(r[15]) or {}).get("name", "—"),
        # 展平实时安全/电气（来自 t_exchange_last_upload）
        "cab_voltage": _rt.get("e_meter_v"), "cab_current": _rt.get("e_meter_a"),
        "cab_meter_w": _rt.get("e_meter_w"), "cab_meter_wh": _rt.get("e_meter_wh"),
        "cab_temp": _rt.get("temp"), "cab_smoke": _rt.get("smoke"),
        "cab_flooded": _rt.get("flooded"), "cab_fire": _rt.get("fire"),
        "cab_rt_upload": (ms2str(_rt.get("last_upload")) if _rt.get("last_upload") else "—"),
        # 展平周期计数（7/30/90 天换电次数与用户数）
        "cab_c7": _dc.get("c7", 0), "cab_u7": _dc.get("u7", 0),
        "cab_c30": _dc.get("c30", 0), "cab_u30": _dc.get("u30", 0),
        "cab_c90": _dc.get("c90", 0), "cab_u90": _dc.get("u90", 0),
    })
# 电池明细（实时遥测 + 流通计数）
BATTERY_STATUS_CN = {"none": "空闲", "using": "使用中", "maintain": "维修", "scrap": "报废", "": "—", None: "—"}
FLAG_CN = {"on": "是", "off": "否", "none": "无", "": "—", None: "—"}
rows = q(
    "SELECT b.device_sn, b.device_id, b.device_type_id, b.battery_status, b.online_status, "
    "b.last_take_time, b.last_back_time, b.last_online_time, b.last_offline_time, b.last_battery_upload_time, "
    "b.last_location_address, b.location_type, b.agency_id, b.type, b.bike_sn, b.scheme_version, "
    "b.last_upload_exchange_sn, b.last_back_exchange_sn, br.belong_type "
    "FROM t_battery b LEFT JOIN t_battery_belong_relation br ON b.id=br.battery_id AND br.is_del=0 "
    "WHERE b.is_del=0 ORDER BY b.last_take_time DESC LIMIT 85000", "e_bdetail", many=True) or []  # 电池全量(~74217) + 仓位真值 belong_type
E["battery_detail"] = []
for r in rows:
    _rt = battery_rt_last.get(r[0], {}) or {}
    _rts = battery_rt_status.get(r[0], {}) or {}
    _circ = battery_circulate_map.get(r[0], {}) or {}
    E["battery_detail"].append({
        "sn": r[0], "device_id": r[1], "model": battery_model_map.get(r[2], "—"),
        "status": BATTERY_STATUS_CN.get(r[3], r[3] or "—"), "online": ONLINE_CN.get(r[4], r[4] or ""),
        "last_take": ms2str(r[5]), "last_back": ms2str(r[6]),
        "last_online": ms2str(r[7]), "last_offline": ms2str(r[8]), "last_upload": ms2str(r[9]),
        "last_location": r[10] or "—", "location_type": (_rt.get("location_type") or r[11] or "—"),
        "agency_id": r[12], "agency": distributor_map.get(r[12], "—"),
        "slottype": ("中控电池" if r[13] == "control" else "普通电池" if r[13] == "normal" else (r[13] or "—")),
        "belong_type": (r[18] or ""),
        "slot_warehouse": BELONG_TYPE_CN.get(r[18], r[18] or "未识别"),
        "slotname": "待确认", "sw_version": "待确认", "hw_version": "待确认", "bike_sn": r[14] or "—", "scheme_version": r[15] or "—",
        "cabinet_sn": (r[16] or r[17] or "—"),
        "site_id": device_site_map.get(r[0]),
        "site_name": (site_map.get(device_site_map.get(r[0])) or {}).get("name", "—"),
        "user": "待确认",
        # 展平实时遥测（t_battery_last_upload）
        "bat_power": _rt.get("power"), "bat_charging": _rt.get("charging"),
        "bat_discharge": _rt.get("discharge"), "bat_cycle": _rt.get("cycle"),
        "bat_voltage": _rt.get("voltage"), "bat_current": _rt.get("current"),
        "bat_temp_max": _rt.get("cell_temp_max"), "bat_temp_min": _rt.get("cell_temp_min"),
        "bat_chg_temp": _rt.get("charging_temp"), "bat_dis_temp": _rt.get("discharge_temp"),
        "bat_rt_upload": (ms2str(_rt.get("last_upload")) if _rt.get("last_upload") else "—"),
        # 展平状态表（t_battery_status）
        "bat_using": _rts.get("using"), "bat_rts_charging": _rts.get("charging"),
        "bat_rts_discharge": _rts.get("discharge"), "bat_voltage_out": _rts.get("voltage_out"),
        "bat_current_out": _rts.get("current_out"), "bat_rts_cycle": _rts.get("cycle"),
        # 展平流通计数（30/90 天借出）
        "bat_c30": _circ.get("c30", 0), "bat_c90": _circ.get("c90", 0),
    })

# ---------- 运维看板 ----------
O = D["ops"] = {}
# 预警（未解除，按等级）
warn = q("SELECT level, COUNT(*) c FROM t_monitor_ex_event WHERE status='init' GROUP BY level", "o_warn", many=True) or []
O["warn_by_level"] = [{"level": r[0], "count": r[1]} for r in warn]
O["warn_recent"] = [
    {"id": r[0], "name": r[1], "level": r[2], "agency": r[3], "create": ms2str(r[4])}
    for r in q(
        "SELECT id, name, level, agency_name, create_time FROM t_monitor_ex_event WHERE status='init' "
        "ORDER BY create_time DESC LIMIT 300", "o_warnr", many=True) or []
]

# ---------- 人员看板 ----------
P = D["personnel"] = {}
P["promoter_total"] = q("SELECT COUNT(*) FROM t_promoter WHERE is_del=0", "p_pt")
P["employee_total"] = q("SELECT COUNT(*) FROM t_site_store_employee WHERE is_del=0", "p_et")
P["distributor_total"] = q("SELECT COUNT(*) FROM t_distributor WHERE is_del=0", "p_dt")
# 业务员销售排行（按签约协议数）
P["promoter_sales_rank"] = [
    {"name": r[0], "count": r[1]} for r in q(
        "SELECT sign_site_business_name, COUNT(*) c FROM t_exchange_agreement "
        "WHERE sign_site_business_name IS NOT NULL AND sign_site_business_name<>'' "
        "GROUP BY sign_site_business_id ORDER BY c DESC LIMIT 50", "p_rank", many=True) or []
]
# 店员/导购列表
rows = q(
    "SELECT id, name, phone, serve_site_name, status, is_manager, merchant_id FROM t_site_store_employee "
    "WHERE is_del=0 ORDER BY create_time DESC LIMIT %d" % DETAIL_CAP, "p_emp", many=True) or []
P["employees"] = [{"id": r[0], "name": r[1], "phone": r[2], "site": r[3], "status": r[4],
                  "is_manager": r[5], "merchant_id": r[6]} for r in rows]
# 渠道商/代理商列表
rows = q(
    "SELECT id, name, level, status, agency_id FROM t_distributor WHERE is_del=0 ORDER BY id LIMIT %d" % DETAIL_CAP, "p_dis", many=True) or []
P["distributors"] = [{"id": r[0], "name": r[1], "level": r[2], "status": r[3], "agency_id": r[4]} for r in rows]

# ---------- 财务看板 ----------
F = D["finance"] = {}
# 收入：消费者购买套餐
F["income_package"] = U["purchase"]["consume_total"]
F["income_rent"] = U["purchase"]["rent_card_total"]
F["income_power"] = U["purchase"]["power_card_total"]
F["income_deposit"] = U["purchase"]["deposit_card_total"]
F["income_refund"] = U["purchase"]["refund_total"]
F["gift_count"] = U["purchase"]["gift_count"]
F["gift_amount"] = U["purchase"]["gift_amount"]
# 逾期（协议欠租数量，金额口径待确认）
F["overdue_count"] = q("SELECT COUNT(*) FROM t_exchange_agreement WHERE status='owe_rent'", "f_ov")
# 支出：按费用名聚合（已结算账单）
rows = q(
    "SELECT expense_name, COALESCE(SUM(fee),0) amt, COUNT(*) c FROM t_expense_bill "
    "WHERE bill_status='settle' AND is_del=0 GROUP BY expense_name ORDER BY amt DESC LIMIT 20", "f_exp", many=True) or []
F["expense_by_name"] = [{"name": r[0] or "其他", "amount": r[1] / 100.0, "count": r[2]} for r in rows]
# 导购/商户分成（按收入单位判断近似）
F["guide_split"] = (q(
    "SELECT COALESCE(SUM(fee),0) FROM t_expense_bill WHERE bill_status='settle' AND in_unit LIKE '%%导购%%' AND is_del=0", "f_guide") or 0) / 100.0
F["merchant_split"] = (q(
    "SELECT COALESCE(SUM(fee),0) FROM t_expense_bill WHERE bill_status='settle' AND (in_unit LIKE '%%商户%%' OR in_unit LIKE '%%site%%') AND is_del=0", "f_merch") or 0) / 100.0
F["electric_subsidy"] = (q(
    "SELECT COALESCE(SUM(settle_amount),0) FROM t_exchange_electric_settlement WHERE settle_status='finish_settle'", "f_elec") or 0) / 100.0
# 支出明细（行级，支持筛选）
rows = q(
    "SELECT expense_name, fee, in_unit, bill_status, create_time, settle_time FROM t_expense_bill "
    "WHERE is_del=0 ORDER BY create_time DESC LIMIT %d" % DETAIL_CAP, "f_detail", many=True) or []
F["detail"] = [{"name": (r[0] or "其他"), "fee": (r[1] or 0) / 100.0, "in_unit": (r[2] or "—"),
               "status": r[3], "create": ms2str(r[4]), "settle_date": ms2str(r[5]), "type": "expense"} for r in rows]
# 提现记录并入财务明细（资金类型 ftype=withdraw），列对齐到 name/fee/in_unit/status/create 同构
wrows = q(
    "SELECT user_name, user_phone, user_deposit_fee, withdraw_status, create_time FROM t_user_exchange_deposit_withdraw_log "
    "WHERE is_del=0 ORDER BY create_time DESC LIMIT %d" % DETAIL_CAP, "f_withdraw", many=True) or []
for r in wrows:
    F["detail"].append({"name": ("%s 押金提现" % (r[0] or "用户")), "fee": (r[2] or 0) / 100.0,
                        "in_unit": "用户提现", "status": r[3], "create": ms2str(r[4]),
                        "settle_date": ms2str(r[4]), "type": "withdraw"})

# ---------- 客服服务台（可查询索引，cap） ----------
C = D["service"] = {}
# 用户协议索引（用于查询）
rows = q(
    "SELECT a.id, u.phone, u.username, a.sys_city_name, a.type, a.status, a.activation_time, a.rent_expire_time, "
    "a.user_id, a.agency_id, s.name, ag.name "
    "FROM t_exchange_agreement a LEFT JOIN t_user u ON a.user_id=u.id "
    "LEFT JOIN t_site s ON a.site_id=s.id "
    "LEFT JOIN t_exchange_rent_package ag ON a.rent_package_id=ag.id "
    "ORDER BY a.create_time DESC LIMIT %d" % DETAIL_CAP, "c_idx", many=True) or []
C["agreement_index"] = [{"agreement_id": r[0], "phone": r[1], "name": r[2], "city": r[3], "type": r[4],
                         "status": r[5], "activate": ms2str(r[6]), "expire": ms2str(r[7]), "user_id": r[8],
                         "agency_id": r[9], "site": r[10], "package": r[11]} for r in rows]

# ---------- 深度分析（10 维度：留存/欠租/电池/产能/漏斗/城市/客服/ARPU/套餐/渠道） ----------
A = D["analytics"] = {}
A["generated_note"] = "聚合口径来源于换电订单(11M+)、每日统计(423行)、违约金记录、电池流转、客诉等表；全量明细聚合已容错，单查询失败不影响其余。"

# A1 趋势（每日统计，快）
rows = q("SELECT statistics_date, success_count, total_user_count, first_take_count, site_count, exchange_count, "
         "success_fee, refund_fee FROM t_statistics_daily_exchange_order WHERE is_del=0 ORDER BY statistics_date",
         "an_daily", many=True) or []
A["daily"] = [{"date": r[0], "orders": r[1] or 0, "users": r[2] or 0, "first_take": r[3] or 0,
               "sites": r[4] or 0, "cabinets": r[5] or 0, "fee": (r[6] or 0) / 100.0,
               "refund": (r[7] or 0) / 100.0} for r in rows]

# A2 留存/复购（11M，重，容错）
try:
    total_u = q("SELECT COUNT(DISTINCT consume_user_id) FROM t_exchange_order WHERE order_status='success'", "an_tu") or 0
    rep = q("SELECT COUNT(*) FROM (SELECT consume_user_id FROM t_exchange_order WHERE order_status='success' "
            "GROUP BY consume_user_id HAVING COUNT(*)>=2) t", "an_rep") or 0
    freq = q("SELECT CASE WHEN c<2 THEN '1次' WHEN c<=5 THEN '2-5次' WHEN c<=20 THEN '6-20次' ELSE '20+次' END b, "
             "COUNT(*) FROM (SELECT consume_user_id, COUNT(*) c FROM t_exchange_order WHERE order_status='success' "
             "GROUP BY consume_user_id) t GROUP BY b", "an_freq", many=True) or []
    A["retention"] = {"total_users": total_u, "repurchase_users": rep,
                      "repurchase_rate": round(rep / total_u, 4) if total_u else 0,
                      "freq_dist": [{"bucket": r[0], "users": r[1]} for r in freq]}
except Exception as e:
    ERR.append("an_retention: %s" % str(e)[:200])
    A["retention"] = {"total_users": None, "repurchase_users": None, "repurchase_rate": None, "freq_dist": []}

# A3 欠租(R)率与金额
try:
    owe_agr = q("SELECT COUNT(*) FROM t_exchange_agreement WHERE status='owe_rent'", "an_owe") or 0
    agr_total = D.get("overview", {}).get("agreement_total") or q("SELECT COUNT(*) FROM t_exchange_agreement", "an_agrt") or 1
    pen = q("SELECT COALESCE(SUM(pay_fee),0), COUNT(*) FROM t_user_exchange_rent_violated_log WHERE is_pay=1", "an_pen", many=True) or [(0, 0)]
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

# A4 电池健康与周转
try:
    turn = q("SELECT COUNT(*), COUNT(DISTINCT battery_device_id) FROM t_battery_circulate_log WHERE is_del=0", "an_turn", many=True) or [(0, 0)]
    turn_total, turn_bat = turn[0][0] or 0, turn[0][1] or 0
    top_turn = q("SELECT battery_device_id, COUNT(*) FROM t_battery_circulate_log WHERE is_del=0 "
                  "GROUP BY battery_device_id ORDER BY COUNT(*) DESC LIMIT 12", "an_turntop", many=True) or []
    offline = q("SELECT COUNT(*) FROM t_monitor_ex_event_battery WHERE online_status='offline' AND is_del=0", "an_off") or 0
    recycled = q("SELECT COUNT(*) FROM t_recover_battery WHERE is_del=0", "an_rec") or 0
    A["battery"] = {"circulate_logs": turn_total, "distinct_batteries": turn_bat,
                    "avg_turnover": round(turn_total / turn_bat, 1) if turn_bat else 0,
                    "top_turnover": [{"battery": r[0], "times": r[1]} for r in top_turn],
                    "offline": offline, "recycled": recycled}
except Exception as e:
    ERR.append("an_battery: %s" % str(e)[:200])
    A["battery"] = {"circulate_logs": None, "distinct_batteries": None, "avg_turnover": None, "top_turnover": [], "offline": None, "recycled": None}

# A5 网点产能
try:
    days = max(len(A["daily"]), 1)
    total_orders = sum(d["orders"] for d in A["daily"]) or q("SELECT COUNT(*) FROM t_exchange_order WHERE order_status='success'", "an_to") or 1
    avg_cab = (sum(d["cabinets"] for d in A["daily"]) / days) if A["daily"] else 0
    top_sites = q("SELECT site_name, COUNT(*) FROM t_exchange_order WHERE order_status='success' "
                  "GROUP BY site_name ORDER BY COUNT(*) DESC LIMIT 15", "an_sites", many=True) or []
    A["capacity"] = {"avg_orders_per_cabinet_day": round(total_orders / (days * avg_cab), 2) if avg_cab else 0,
                     "top_sites": [{"site": (r[0] or "未知网点"), "orders": r[1]} for r in top_sites]}
except Exception as e:
    ERR.append("an_capacity: %s" % str(e)[:200])
    A["capacity"] = {"avg_orders_per_cabinet_day": None, "top_sites": []}

# A6 销售漏斗
try:
    dep_u = q("SELECT COUNT(DISTINCT user_id) FROM t_user_exchange_deposit WHERE is_del=0", "an_dep") or 0
    agr_u = q("SELECT COUNT(DISTINCT user_id) FROM t_exchange_agreement", "an_agu") or 0
    rent_c = q("SELECT COUNT(*) FROM t_user_exchange_rent WHERE is_del=0 AND card_status IN ('using','used')", "an_rent") or 0
    A["funnel"] = {"deposit_users": dep_u, "agreement_users": agr_u, "rent_card_users": rent_c,
                   "conv_deposit_to_agr": round(agr_u / dep_u, 4) if dep_u else 0,
                   "conv_agr_to_rent": round(rent_c / agr_u, 4) if agr_u else 0}
except Exception as e:
    ERR.append("an_funnel: %s" % str(e)[:200])
    A["funnel"] = {"deposit_users": None, "agreement_users": None, "rent_card_users": None, "conv_deposit_to_agr": None, "conv_agr_to_rent": None}

# A7 城市对标 / ARPU
try:
    city_rows = q("SELECT sys_city_name, COUNT(*), COUNT(DISTINCT consume_user_id), COALESCE(SUM(real_pay_price),0) "
                  "FROM t_exchange_order WHERE order_status='success' GROUP BY sys_city_name "
                  "ORDER BY COUNT(*) DESC LIMIT 15", "an_city", many=True) or []
    city_list = []
    for r in city_rows:
        rev = (r[3] or 0) / 100.0
        u = r[2] or 0
        city_list.append({"city": (r[0] or "未知"), "orders": r[1], "users": u, "revenue": rev,
                          "arpu": round(rev / u, 2) if u else 0})
    # 总体 ARPU
    rev_all = q("SELECT COALESCE(SUM(real_pay_price),0), COUNT(DISTINCT consume_user_id) FROM t_exchange_order WHERE order_status='success'", "an_arpu_all", many=True) or [(0, 0)]
    rev_all_v = (rev_all[0][0] or 0) / 100.0
    users_all = rev_all[0][1] or 0
    A["city"] = {"list": city_list, "overall_arpu": round(rev_all_v / users_all, 2) if users_all else 0,
                 "overall_revenue": rev_all_v, "overall_users": users_all}
except Exception as e:
    ERR.append("an_city: %s" % str(e)[:200])
    A["city"] = {"list": [], "overall_arpu": None, "overall_revenue": None, "overall_users": None}

# A8 客服 / 客诉
try:
    cs_total = q("SELECT COUNT(*) FROM t_exchange_order_complaint WHERE is_del=0", "an_cst") or 0
    cs_type = q("SELECT type, COUNT(*) FROM t_exchange_order_complaint WHERE is_del=0 GROUP BY type", "an_cstype", many=True) or []
    cs_stat = q("SELECT operation_status, COUNT(*) FROM t_exchange_order_complaint WHERE is_del=0 GROUP BY operation_status", "an_csstat", many=True) or []
    order_total = q("SELECT COUNT(*) FROM t_exchange_order WHERE order_status='success'", "an_ot") or 1
    A["cs"] = {"total": cs_total,
               "by_type": [{"type": (r[0] or "其他"), "count": r[1]} for r in cs_type],
               "by_status": [{"status": (r[0] or "未知"), "count": r[1]} for r in cs_stat],
               "cs_rate": round(cs_total / order_total, 5) if order_total else 0}
except Exception as e:
    ERR.append("an_cs: %s" % str(e)[:200])
    A["cs"] = {"total": None, "by_type": [], "by_status": [], "cs_rate": None}

# A9 套餐结构健康度（复用 F 收入 + 用户分布）
try:
    pkg_users = q("SELECT COUNT(DISTINCT user_id) FROM t_user_exchange_package_order WHERE order_status='success'", "an_pu") or 0
    F = D.get("finance", {})
    A["package"] = {
        "rent_revenue": F.get("income_rent"), "power_revenue": F.get("income_power"),
        "deposit_revenue": F.get("income_deposit"), "package_revenue": F.get("income_package"),
        "rent_users": q("SELECT COUNT(DISTINCT user_id) FROM t_user_exchange_rent_package_order WHERE order_status='success'", "an_ru") or 0,
        "power_users": pkg_users,
        "gift_count": F.get("gift_count"), "gift_amount": F.get("gift_amount")}
except Exception as e:
    ERR.append("an_package: %s" % str(e)[:200])
    A["package"] = {}

# A10 代理商/渠道效能
try:
    agy_rows = q("SELECT agency_name, COUNT(*), COALESCE(SUM(real_pay_price),0) FROM t_exchange_order "
                 "WHERE order_status='success' GROUP BY agency_name ORDER BY COUNT(*) DESC LIMIT 15", "an_agy", many=True) or []
    # 代理商欠租率
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

# ---------- 维度映射补全（行业 / 换电柜实时 / 电池实时 / 周期计数） ----------
industry_map = {}
for r in _map("SELECT id, name FROM t_site_industry WHERE is_del=0", "map_ind"):
    industry_map[r[0]] = r[1] or ("行业#%s" % r[0])
# 换电柜实时上报（安全/电气/温度）：t_exchange_last_upload，按 device_sn
cabinet_realtime_map = {}
for r in _map(
    "SELECT device_sn, smoke, flooded, fire, e_meter_v, e_meter_a, e_meter_w, e_meter_wh, temp, last_upload_time "
    "FROM t_exchange_last_upload WHERE is_del=0", "map_cab_rt"):
    if r[0]:
        cabinet_realtime_map[r[0]] = {
            "smoke": r[1], "flooded": r[2], "fire": r[3],
            "e_meter_v": r[4], "e_meter_a": r[5], "e_meter_w": r[6], "e_meter_wh": r[7],
            "temp": r[8], "last_upload": r[9]}
# 电池实时遥测：t_battery_last_upload + t_battery_status，按 battery_sn
battery_rt_last = {}
for r in _map(
    "SELECT battery_sn, power, charging, discharge, cycle, voltage, current, cell_temp_min, cell_temp_max, "
    "discharge_temp, charging_temp, main_s, main_h, update_time "
    "FROM t_battery_last_upload WHERE is_del=0", "map_bat_lu"):
    if r[0]:
        battery_rt_last[r[0]] = {
            "power": r[1], "charging": r[2], "discharge": r[3], "cycle": r[4], "voltage": r[5],
            "current": r[6], "cell_temp_min": r[7], "cell_temp_max": r[8], "discharge_temp": r[9],
            "charging_temp": r[10], "main_s": r[11], "main_h": r[12], "last_upload": r[13]}
battery_rt_status = {}
for r in _map(
    "SELECT device_sn, using, charging, discharge, voltage_out, current_out, cycle "
    "FROM t_battery_status WHERE is_del=0", "map_bat_st"):
    if r[0]:
        battery_rt_status[r[0]] = {
            "using": r[1], "charging": r[2], "discharge": r[3], "voltage_out": r[4],
            "current_out": r[5], "cycle": r[6]}
# 换电柜 7/30/90 天换电次数与用户数（best-effort，按柜聚合最近90天订单）
cabinet_daycount_map = {}
try:
    dc_rows = q(
        "SELECT ex_id, "
        "SUM(CASE WHEN ct>=%d THEN 1 ELSE 0 END) c7, COUNT(DISTINCT CASE WHEN ct>=%d THEN uid END) u7, "
        "SUM(CASE WHEN ct>=%d THEN 1 ELSE 0 END) c30, COUNT(DISTINCT CASE WHEN ct>=%d THEN uid END) u30, "
        "COUNT(*) c90, COUNT(DISTINCT uid) u90 "
        "FROM ("
        "  SELECT take_exchange_id ex_id, consume_user_id uid, create_time ct FROM t_exchange_order WHERE create_time>=%d AND take_exchange_id IS NOT NULL "
        "  UNION ALL "
        "  SELECT back_exchange_id ex_id, consume_user_id uid, create_time ct FROM t_exchange_order WHERE create_time>=%d AND back_exchange_id IS NOT NULL "
        ") t GROUP BY ex_id" % (D7, D7, D30, D30, D90, D90),
        "map_cab_dc", many=True) or []
    for r in dc_rows:
        cabinet_daycount_map[r[0]] = {"c7": r[1], "u7": r[2], "c30": r[3], "u30": r[4], "c90": r[5], "u90": r[6]}
except Exception as e:
    ERR.append("map_cab_dc: %s" % str(e)[:200])
# 电池 30/90 天借出次数（best-effort，流通记录 outflow=借出）
battery_circulate_map = {}
try:
    circ_rows = q(
        "SELECT battery_device_sn, "
        "SUM(CASE WHEN create_time>=%d THEN 1 ELSE 0 END) c30, "
        "SUM(CASE WHEN create_time>=%d THEN 1 ELSE 0 END) c90 "
        "FROM t_battery_circulate_log WHERE outflow_id IS NOT NULL AND business_type_first='exchange_order' GROUP BY battery_device_sn"
        % (D30, D90), "map_bat_circ", many=True) or []
    for r in circ_rows:
        battery_circulate_map[r[0]] = {"c30": r[1], "c90": r[2]}
except Exception as e:
    ERR.append("map_bat_circ: %s" % str(e)[:200])
# 消费者名下电池（当前在绑）：t_bike_battery_bind_log，按 user_id 聚合去重 battery_sn
battery_bind_map = {}
try:
    cur.execute("SET SESSION group_concat_max_len=1048576")
    bb_rows = q(
        "SELECT user_id, COUNT(DISTINCT battery_sn) AS cnt, "
        "LEFT(GROUP_CONCAT(DISTINCT battery_sn SEPARATOR ','), 1500) AS sns "
        "FROM t_bike_battery_bind_log WHERE is_del=0 AND bind_status='bind' GROUP BY user_id",
        "map_bat_bind", many=True) or []
    for r in bb_rows:
        uid = r[0]; cnt = r[1] or 0; sns = r[2] or ""
        battery_bind_map[uid] = {"count": cnt, "sns": sns}
    cur.execute("SET SESSION group_concat_max_len=1024")
except Exception as e:
    ERR.append("map_bat_bind: %s" % str(e)[:200])

# ---------- P0 扩展：5 张明细表全量补全 + 销售/设备新增数据 ----------

# 1) 用户协议明细表（全量已开通协议，匹配图片1列名）
AGR_CAP = 200000  # 协议全量（当前12万行，留余量）
agr_rows = q(
    "SELECT a.id, a.type, a.service_platform, a.user_id, u.phone, u.username, "
    "bp.name AS battery_product, a.bike_count, bk.device_sn AS bike_sn, bs.name AS battery_standard, "
    "a.battery_standard_rent, a.exchange_scheme_fee, a.rent_package_id, rp.name AS rent_package_name, rp.fee AS package_fee, "
    "a.sys_city_name, s.name AS site_name, a.agency_id, ao.agency_name, "
    "s.distributor_id, d.name AS distributor_name, a.sign_site_business_name, "
    "a.company_name, a.activation_time, a.rent_expire_time, a.is_rent_permanent_valid, "
    "a.deposit_fee, a.deposit_bind_time, a.deposit_unbind_time, a.status, a.create_time, a.is_first, a.promoter_id, "
    "a.site_sale_scenario_name, a.contract_type, a.contract_period, a.contract_expire_time, "
    "a.deposit_status, a.deposit_payway, a.stop_time, a.is_contract, a.battery_product_id, "
    "a.battery_series_id, a.battery_lessor, a.battery_take_status, a.is_auto_pay, "
    "a.is_replacement, a.is_bike_share, a.remark, "
    "s.area, s.street, s.community, a.sign_site_store_employee_id "
    "FROM t_exchange_agreement a "
    "LEFT JOIN t_user u ON a.user_id=u.id "
    "LEFT JOIN t_battery_product bp ON a.battery_product_id=bp.id "
    "LEFT JOIN t_bike bk ON a.id=bk.exchange_agreement_id AND bk.is_binding=1 "
    "LEFT JOIN t_battery_brand bs ON a.battery_series_id=bs.id "
    "LEFT JOIN t_exchange_rent_package rp ON a.rent_package_id=rp.id "
    "LEFT JOIN t_site s ON a.site_id=s.id "
    "LEFT JOIN (SELECT DISTINCT agency_id, agency_name FROM t_exchange_order WHERE agency_name IS NOT NULL) ao ON a.agency_id=ao.agency_id "
    "LEFT JOIN t_distributor d ON s.distributor_id=d.id "
    "WHERE a.is_del=0 ORDER BY a.create_time DESC LIMIT %d" % AGR_CAP,
    "ext_agreement_full", many=True) or []
U["agreement_detail"] = [{
    "agreement_id": r[0], "type": r[1] or "—", "channel": r[2] or "—",
    "user_id": r[3], "phone": r[4] or "—", "user_name": r[5] or "—",
    "battery_product": r[6] or "—", "bike_count": r[7] or 0, "bike_sn": r[8] or "—", "battery_model": r[9] or "—",
    "battery_standard_rent": (r[10] or 0) / 100.0,
    "exchange_scheme_fee": (r[11] or 0) / 100.0,
    "rent_package_id": r[12], "rent_package_name": r[13] or "—", "package_fee": (r[14] or 0) / 100.0,
    "city": r[15] or "—", "site_name": r[16] or "—",
    "agency_id": r[17], "agency_name": r[18] or "—",
    "distributor_id": r[19], "distributor_name": r[20] or "—",
    "business_name": r[21] or "—", "company_name": r[22] or "—",
    "activation_time": ms2str(r[23]), "expire_time": ms2str(r[24]),
    "is_permanent": bool(r[25]),
    "deposit_fee": (r[26] or 0) / 100.0, "deposit_bind_time": r[27], "deposit_unbind_time": r[28],
    "status": r[29] or "—", "create_time": ms2str(r[30]), "is_first": r[31],
    "promoter_id": r[32], "sale_scenario": r[33] or "—",
    "contract_type": r[34] or "—", "contract_period": r[35],
    "contract_expire": ms2str(r[36]),     "deposit_status": r[37] or "—",
    "deposit_payway": r[38] or "—", "stop_time": ms2str(r[39]),
    "is_contract": r[40], "battery_product_id": r[41],
    "battery_series_id": r[42], "battery_lessor": r[43] or "—",
    "battery_take_status": r[44] or "—", "is_auto_pay": r[45],
    "is_replacement": r[46], "is_bike_share": r[47], "remark": r[48] or "—",
    "remain_days": _remain_days(r[24]),
    "overdue_days": (_overdue_days(r[24]) if r[29] == "owe_rent" else 0),
    "deposit_deduct": _deposit_deduct(r[37], r[27], r[28]),
    "promoter_name": ((promoter_map.get(r[32]) or {}).get("name") if r[32] else None) or ("推广员#%s" % r[32] if r[32] else "—"),
    "battery_count": ((battery_bind_map.get(r[3]) or {}).get("count") or 0),
    "battery_sns": ((battery_bind_map.get(r[3]) or {}).get("sns") or "—"),
    "guide": "待确认",
    "area": r[49] or "—", "street": r[50] or "—", "community": r[51] or "—",
    "sign_employee_id": r[52],
    # 中文显示拼装（ID#名称 / ID#名称#手机 / ID/手机）
    "user_disp": ("%s#%s" % ((r[5] or "匿名"), r[3])) if r[3] else (r[5] or "—"),
    "agency_disp": ("%s#%s" % (r[17], r[18])) if (r[17] and r[18]) else (r[18] or r[17] or "—"),
    "distributor_disp": ("%s#%s" % (r[19], r[20])) if (r[19] and r[20]) else (r[20] or r[19] or "—"),
    "promoter_disp": (lambda p: ("%s#%s#%s" % (r[32], p.get("name", ""), p.get("phone", ""))) if p else ("推广员#%s" % r[32] if r[32] else "—"))(promoter_map.get(r[32]) if r[32] else None),
    "guide_disp": (lambda g: ("%s/%s" % (r[52], g.get("phone", ""))) if g else ("导购#%s" % r[52] if r[52] else "—"))(guide_map.get(r[52]) if r[52] else None)
} for r in agr_rows]

# 2) 押金明细表（t_user_exchange_deposit 全量 + 押金套餐订单）
dep_rows = q(
    "SELECT id, deposit_order_id, pay_way, user_id, bike_id, fee, take_battery_status, "
    "is_withdraw, withdraw_time, is_freeze, create_time, update_time "
    "FROM t_user_exchange_deposit WHERE is_del=0 ORDER BY create_time DESC LIMIT 40000",
    "ext_deposit", many=True) or []  # 押金全量(~34340)
U["deposit_detail"] = [{
    "id": r[0], "deposit_order_id": r[1], "pay_way": r[2] or "—",
    "user_id": r[3], "bike_id": r[4], "fee": (r[5] or 0) / 100.0,
    "take_battery_status": r[6] or "—", "is_withdraw": bool(r[7]),
    "withdraw_time": ms2str(r[8]), "is_freeze": bool(r[9]),
    "create_time": ms2str(r[10]), "update_time": ms2str(r[11])
} for r in dep_rows]

# 2b) 押金明细表（用户规范 10 列：协议ID/手机号/姓名/城市/签约网点/套餐/押金(元)/押金状态/缴纳方式/划扣状态）
dep_view_rows = q(
    "SELECT a.id, u.phone, u.username, a.sys_city_name, s.name, rp.name, "
    "a.deposit_fee, a.deposit_status, a.deposit_payway, a.deposit_bind_time, a.deposit_unbind_time "
    "FROM t_exchange_agreement a "
    "LEFT JOIN t_user u ON a.user_id=u.id "
    "LEFT JOIN t_site s ON a.site_id=s.id "
    "LEFT JOIN t_exchange_rent_package rp ON a.rent_package_id=rp.id "
    "WHERE a.is_del=0 ORDER BY a.create_time DESC LIMIT %d" % AGR_CAP,
    "ext_deposit_view", many=True) or []
U["deposit_view"] = [{
    "agreement_id": r[0], "phone": r[1] or "—", "name": r[2] or "—",
    "city": r[3] or "—", "site_name": r[4] or "—", "package": r[5] or "—",
    "deposit_fee": (r[6] or 0) / 100.0, "deposit_status": r[7] or "—",
    "deposit_payway": r[8] or "—",
    "deposit_deduct": _deposit_deduct(r[7], r[9], r[10])
} for r in dep_view_rows]

# 押金套餐订单（套餐购买明细的数据源之一，匹配图片2）
dep_pkg_cap = 20000
dep_pkg_rows = q(
    "SELECT id, exchange_agreement_id, battery_product_id, package_id, bike_id, user_id, "
    "user_name, user_phone, fee, real_fee, deposit_fee, other_fee, package_name, "
    "pay_way_table_id, pay_way_table_name, pay_way, is_discounts, order_status, is_present, "
    "is_pay, pay_time, is_withdraw, withdraw_time, is_deposit_refund, deposit_refund_time, "
    "is_other_refund, refund_fee, refund_deposit_fee, refund_other_fee, trade_no, create_time "
    "FROM t_user_exchange_deposit_package_order WHERE is_del=0 "
    "ORDER BY create_time DESC LIMIT %d" % dep_pkg_cap,
    "ext_dep_pkg", many=True) or []
U["deposit_package_detail"] = [{
    "id": r[0], "agreement_id": r[1], "battery_product_id": r[2],
    "package_id": r[3], "bike_id": r[4], "user_id": r[5],
    "user_name": r[6] or "—", "user_phone": r[7] or "—",
    "fee": (r[8] or 0) / 100.0, "real_fee": (r[9] or 0) / 100.0,
    "deposit_fee": (r[10] or 0) / 100.0, "other_fee": (r[11] or 0) / 100.0,
    "package_name": r[12] or "—", "pay_way_table_id": r[13],
    "pay_way_table_name": r[14] or "—", "pay_way": r[15] or "—",
    "is_discounts": bool(r[16]), "order_status": r[17] or "—",
    "is_present": bool(r[18]), "is_pay": bool(r[19]),
    "pay_time": ms2str(r[20]), "is_withdraw": bool(r[21]),
    "withdraw_time": ms2str(r[22]), "is_deposit_refund": bool(r[23]),
    "deposit_refund_time": ms2str(r[24]), "is_other_refund": bool(r[25]),
    "refund_fee": (r[26] or 0) / 100.0,
    "refund_deposit_fee": (r[27] or 0) / 100.0,
    "refund_other_fee": (r[28] or 0) / 100.0,
    "trade_no": r[29] or "—", "create_time": ms2str(r[30])
} for r in dep_pkg_rows]

# 3) 退订申请明细（停用申请）
cancel_cap = 50000
cancel_rows = q(
    "SELECT id, exchange_agreement_id, status, site_id, site_name, agency_id, agency_name, "
    "battery_product_id, battery_product_name, refund_total_fee, refund_deposit_fee, refund_rent_fee, "
    "applicant_id, applicant_name, applicant_phone, apply_time, stop_reason, stop_remark, "
    "auditor_id, auditor_name, audit_time, audit_remark, finish_time, back_battery_time, "
    "create_time, update_time "
    "FROM t_exchange_agreement_stop_apply WHERE is_del=0 "
    "ORDER BY create_time DESC LIMIT %d" % cancel_cap,
    "ext_cancel", many=True) or []
U["cancel_detail"] = [{
    "id": r[0], "agreement_id": r[1], "status": r[2] or "—",
    "site_id": r[3], "site_name": r[4] or "—",
    "agency_id": r[5], "agency_name": r[6] or "—",
    "battery_product_id": r[7], "battery_product_name": r[8] or "—",
    "refund_total_fee": (r[9] or 0) / 100.0,
    "refund_deposit_fee": (r[10] or 0) / 100.0,
    "refund_rent_fee": (r[11] or 0) / 100.0,
    "applicant_id": r[12], "applicant_name": r[13] or "—",
    "applicant_phone": r[14] or "—", "apply_time": ms2str(r[15]),
    "stop_reason": r[16] or "—", "stop_remark": r[17] or "—",
    "auditor_id": r[18], "auditor_name": r[19] or "—",
    "audit_time": ms2str(r[20]), "audit_remark": r[21] or "—",
    "finish_time": ms2str(r[22]), "back_battery_time": ms2str(r[23]),
    "create_time": ms2str(r[24]), "update_time": ms2str(r[25])
} for r in cancel_rows]

# 4) 换电订单明细（匹配图片2列名，cap 控体积；11M 全量太大）
order_cap = 15000
order_rows = q(
    "SELECT o.id, o.sys_city_name, o.consume_user_name, o.consume_user_phone, "
    "o.battery_product_name, o.bike_id, o.bike_sn, o.pay_price, o.real_pay_price, "
    "o.pre_pay_price, o.pay_way, o.create_time AS pay_time, o.site_name, o.agency_name, "
    "o.order_status, o.exchange_order_status, o.create_time, o.exchange_agreement_id, "
    "o.take_user_id, o.take_user_name, o.take_user_phone, o.mileage, o.use_days, "
    "o.use_power, o.expend_power, o.battery_status, o.is_refund, o.is_first_take "
    "FROM t_exchange_order o WHERE o.is_del=0 "
    "ORDER BY o.create_time DESC LIMIT %d" % order_cap,
    "ext_order", many=True) or []
U["order_detail"] = [{
    "order_id": r[0], "city": r[1] or "—", "user_name": r[2] or "—",
    "user_phone": r[3] or "—", "battery_product": r[4] or "—",
    "bike_id": r[5], "bike_sn": r[6] or "—",
    "order_amount": (r[7] or 0) / 100.0,
    "paid_amount": (r[8] or 0) / 100.0,
    "pre_pay": (r[9] or 0) / 100.0,
    "pay_way": r[10] or "—", "pay_time": ms2str(r[11]),
    "site_name": r[12] or "—", "agency_name": r[13] or "—",
    "order_status": r[14] or "—", "exchange_order_status": r[15] or "—",
    "create_time": ms2str(r[16]), "agreement_id": r[17],
    "take_user_id": r[18], "take_user_name": r[19] or "—",
    "take_user_phone": r[20] or "—", "mileage": r[21] or 0,
    "use_days": r[22] or 0, "use_power": r[23] or 0,
    "expend_power": r[24] or 0, "battery_status": r[25] or "—",
    "is_refund": bool(r[26]), "is_first_take": bool(r[27])
} for r in order_rows]

# 5) 车辆总览明细（t_bike 全量 cap）
bike_cap = 20000
bike_rows = q(
    "SELECT b.id, b.name, b.device_sn, b.vin, b.brand_id, b.device_type_id, "
    "b.site_id, b.agency_id, b.exchange_agreement_id, b.online_status, "
    "b.last_online_time, b.last_offline_time, b.lat, b.lng, b.last_location_address, "
    "b.last_location_time, b.is_binding, b.is_smart_bike, b.images, "
    "b.exchange_count, b.exchange_power, b.usable_charge_count, b.used_charge_count, "
    "b.create_time, b.update_time, b.certificate_code, b.is_del, "
    "bt.name AS brand_name, dt.device_product_name AS device_type_name, "
    "s.name AS site_name, s.city AS site_city, u.phone AS user_phone, u.username AS user_name "
    "FROM t_bike b "
    "LEFT JOIN t_bike_brand bt ON b.brand_id=bt.id "
    "LEFT JOIN t_device_type dt ON b.device_type_id=dt.id "
    "LEFT JOIN t_site s ON b.site_id=s.id "
    "LEFT JOIN t_bike_user_relation bur ON b.id=bur.bike_id AND bur.is_del=0 AND bur.is_owner=1 "
    "LEFT JOIN t_user u ON bur.t_user_id=u.id "
    "WHERE b.is_del=0 ORDER BY b.create_time DESC LIMIT %d" % bike_cap,
    "ext_bike", many=True) or []
# NOTE: bike→user join via agreement is imperfect; for exact mapping need bike_user_relation table
U["vehicle_detail"] = [{
    "bike_id": r[0], "name": r[1] or "—", "device_sn": r[2] or "—",
    "vin": r[3] or "—", "brand_id": r[4], "device_type_id": r[5],
    "site_id": r[6], "agency_id": r[7], "agreement_id": r[8],
    "online_status": r[9] or "—", "last_online": ms2str(r[10]),
    "last_offline": ms2str(r[11]), "lat": r[12] or "—", "lng": r[13] or "—",
    "location": r[14] or "—", "location_time": ms2str(r[15]),
    "is_binding": bool(r[16]), "is_smart_bike": bool(r[17]),
    "images": r[18] or "—", "exchange_count": r[19] or 0,
    "exchange_power": r[20] or 0, "usable_charge": r[21] or 0,
    "used_charge": r[22] or 0, "create_time": ms2str(r[23]),
    "update_time": ms2str(r[24]), "certificate_code": r[25] or "—",
    "brand_name": r[26] or "—", "device_type_name": r[27] or "—",
    "site_name": r[28] or "—", "site_city": r[29] or "—",
    "user_phone": r[30] or "—", "user_name": r[31] or "—"
} for r in bike_rows]

# 6) 销售看板数据源：协议签约汇总（复用 U["agreement_detail"] 聚合）
S["agreement_sign_stats"] = {
    "total_agreements": len(U["agreement_detail"]),
    "by_status": {},
    "by_city": {},
    "by_package": {},
    "by_type": {}
}
for a in U["agreement_detail"]:
    st = a.get("status") or "未知"
    S["agreement_sign_stats"]["by_status"][st] = S["agreement_sign_stats"]["by_status"].get(st, 0) + 1
    ct = a.get("city") or "未知"
    S["agreement_sign_stats"]["by_city"][ct] = S["agreement_sign_stats"]["by_city"].get(ct, 0) + 1
    pkg = a.get("rent_package_name") or "未知"
    S["agreement_sign_stats"]["by_package"][pkg] = S["agreement_sign_stats"]["by_package"].get(pkg, 0) + 1
    tp = a.get("type") or "未知"
    S["agreement_sign_stats"]["by_type"][tp] = S["agreement_sign_stats"]["by_type"].get(tp, 0) + 1

# 7) 销售看板数据源：套餐购买明细汇总（图片2 汇总行）
S["package_purchase_stats"] = {
    "order_count": len(U["deposit_package_detail"]),
    "total_order_amount": sum(d.get("fee", 0) for d in U["deposit_package_detail"]),
    "total_paid_amount": sum(d.get("real_fee", 0) for d in U["deposit_package_detail"]),
    "total_refund_amount": sum(d.get("refund_fee", 0) + d.get("refund_deposit_fee", 0) for d in U["deposit_package_detail"]),
}
# 也加上普通套餐订单(t_user_exchange_package_order)的统计
pkg_ord_rows = q(
    "SELECT COUNT(*) cnt, COALESCE(SUM(fee),0) fee_sum, COALESCE(SUM(real_fee),0) real_sum, "
    "COALESCE(SUM(refund_fee),0) ref_sum "
    "FROM t_user_exchange_package_order WHERE is_del=0",
    "ext_pkg_stats", many=True) or [(0, 0, 0, 0)]
if pkg_ord_rows:
    pr = pkg_ord_rows[0]
    S["package_purchase_stats"]["power_order_count"] = pr[0]
    S["package_purchase_stats"]["power_total_amount"] = (pr[1] or 0) / 100.0
    S["package_purchase_stats"]["power_paid_amount"] = (pr[2] or 0) / 100.0
    S["package_purchase_stats"]["power_refund_amount"] = (pr[3] or 0) / 100.0

# 8) 设备资产：调拨流通记录（t_oem_device_transfer_log）
trans_cap = 10000
trans_rows = q(
    "SELECT tl.id, tl.transfer_id, tl.device_id, tl.device_sn, tl.device_type_id, "
    "tl.product_code, tl.product_name, tl.product_model_code, tl.product_model_name, "
    "tl.create_time, t.transfer_type, t.device_type, t.remark, t.creator_name "
    "FROM t_oem_device_transfer_log tl "
    "LEFT JOIN t_oem_device_transfer t ON tl.transfer_id=t.id "
    "WHERE tl.is_del=0 ORDER BY tl.create_time DESC LIMIT %d" % trans_cap,
    "ext_transfer", many=True) or []
E["transfer_log"] = [{
    "log_id": r[0], "transfer_id": r[1], "device_id": r[2] or "—",
    "device_sn": r[3] or "—", "device_type_id": r[4] or "—",
    "product_code": r[5] or "—", "product_name": r[6] or "—",
    "product_model_code": r[7] or "—", "product_model_name": r[8] or "—",
    "create_time": ms2str(r[9]), "transfer_type": r[10] or "—",
    "device_category": r[11] or "—", "remark": r[12] or "—",
    "creator_name": r[13] or "—"
} for r in trans_rows]

# 设备调拨汇总
E["transfer_summary"] = q(
    "SELECT transfer_type, device_type, SUM(transfer_count) total_cnt, COUNT(*) batch_cnt "
    "FROM t_oem_device_transfer WHERE is_del=0 GROUP BY transfer_type, device_type",
    "ext_trans_summary", many=True) or []

# 9) 电池流通记录（从电池循环日志取）
bat_flow_cap = 10000
bat_flow_rows = q(
    "SELECT id, battery_device_id, battery_device_sn AS battery_sn, inflow_id AS site_id, "
    "inflow_name AS site_name, outflow_id AS user_id, outflow_name AS user_name, "
    "business_type_first AS action_type, create_time, remark "
    "FROM t_battery_circulate_log WHERE is_del=0 "
    "ORDER BY create_time DESC LIMIT %d" % bat_flow_cap,
    "ext_batflow", many=True) or []
E["battery_flow"] = [{
    "id": r[0], "battery_device_id": r[1], "battery_sn": r[2] or "—",
    "site_id": r[3], "site_name": r[4] or "—",
    "user_id": r[5], "user_name": r[6] or "—",
    "action_type": r[7] or "—", "create_time": ms2str(r[8]),
    "remark": r[9] or "—"
} for r in bat_flow_rows]

# 10) 退款明细（t_pay_refund_log）
refund_cap = 10000
refund_rows = q(
    "SELECT id, exchange_agreement_id, pay_way, user_id, user_name, business_id, "
    "business_type, sub_business_type, channel, pay_unit_price, unit_price, "
    "refund_status, goods_info, operator_id, operator_name, remark, create_time "
    "FROM t_pay_refund_log WHERE is_del=0 "
    "ORDER BY create_time DESC LIMIT %d" % refund_cap,
    "ext_refund", many=True) or []
U["refund_detail"] = [{
    "id": r[0], "agreement_id": r[1], "pay_way": r[2] or "—",
    "user_id": r[3], "user_name": r[4] or "—", "business_id": r[5],
    "business_type": r[6] or "—", "sub_business_type": r[7] or "—",
    "channel": r[8] or "—", "unit_price": (r[9] or 0) / 100.0,
    "price": (r[10] or 0) / 100.0, "refund_status": r[11] or "—",
    "goods_info": r[12] or "—", "operator_id": r[13],
    "operator_name": r[14] or "—", "remark": r[15] or "—",
    "create_time": ms2str(r[16])
} for r in refund_rows]

D["errors"] = ERR
import os as _os
_tmp = OUT + ".tmp"
json.dump(D, open(_tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
_os.replace(_tmp, OUT)
conn.close()
print("DONE modules:", [k for k in D if k not in ("errors", "meta")])
print("ERRORS:", len(ERR))
for e in ERR:
    print("  -", e)
import os
print("SIZE:", os.path.getsize(OUT))
