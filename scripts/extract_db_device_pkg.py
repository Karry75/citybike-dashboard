# -*- coding: utf-8 -*-
"""
DB 驱动补全 · 出入库 / 调拨 / 流通 / 套餐购买订单
=================================================
连接 ADB，抽取下列模块真实数据并写回 dashboard_data.json：

1. device.inventory  (出入库明细)
   - 来源：t_battery_transfer_log（电池出入库流转，含 inflow/outflow）
   - list 列：record_id, device_type, device_id, op_type, operator,
              op_time, from_obj, to_obj, result
   - kpis：pending_in / today_in / today_out / total

2. device.transfer  (设备调拨)
   - 来源：t_battery_transfer_batch（电池调拨批次）+ bike/site 调拨日志
   - 列：record_id, operator_id, operator_name, op_time, device_type,
         device_id, op_type, result, from_obj, to_obj

3. DATA.circulation  (电池流通记录)
   - 来源：t_battery_circulate_log（22.5M，采样近 5000）
   - 列：id, bat_sn, bat_model, bat_level, from_obj, from_type,
         to_obj, to_type, method, created_at

4. DATA.agreement_service_orders  (协议→套餐购买订单，抽屉用)
   - 来源：t_exchange_service_order（套餐购买订单，采样 4万分组）
   - 映射 AGR_PKG_COLS

金额单位：库内"分"，本脚本涉及费用的除以 100 转"元"。
"""
import json, os, time, pymysql
BASE = r"D:/workboddy file/dudu分析/citybike_backup"
cfg = json.load(open(BASE + r"/config/backup_config.json", encoding="utf-8"))
cfg.pop("workers", None)
conn = pymysql.connect(host=cfg["host"], port=cfg["port"], user=cfg["user"],
                       password=cfg["password"], database=cfg["database"],
                       connect_timeout=30, read_timeout=600, charset="utf8mb4")
cur = conn.cursor()

DEV_WH_TYPES = ("platform", "warehouse", "agency", "site", "oem", "operate")

# ── 1. 出入库明细 ───────────────────────────────────────────────
print("[1/4] 出入库明细 t_battery_transfer_log ...")
cur.execute("""
    SELECT id, battery_device_sn, transfer_type, transfer_status,
           outflow_name, inflow_name, create_time
    FROM t_battery_transfer_log
    WHERE is_del=0
    ORDER BY create_time DESC LIMIT 5000
""")
inv_list = []
for (rid, sn, ttype, tstatus, outflow, inflow, ctime) in cur.fetchall():
    inv_list.append({
        "record_id": rid,
        "device_type": "电池",
        "device_id": sn or "",
        "op_type": ttype or "",
        "operator": "",
        "op_time": str(ctime or ""),
        "from_obj": outflow or "",
        "to_obj": inflow or "",
        "result": tstatus or "",
    })
# KPI 聚合
cur.execute("""SELECT COUNT(*) FROM t_battery_transfer_log
               WHERE is_del=0 AND transfer_status NOT IN ('success','completed','done')""")
pending_in = cur.fetchone()[0]
cur.execute("""SELECT COUNT(*) FROM t_battery_transfer_log
               WHERE is_del=0 AND DATE(create_time)=CURDATE()
                 AND inflow_type IN (%s)""", (",".join(DEV_WH_TYPES),))
today_in = cur.fetchone()[0]
cur.execute("""SELECT COUNT(*) FROM t_battery_transfer_log
               WHERE is_del=0 AND DATE(create_time)=CURDATE()
                 AND outflow_type IN (%s)""", (",".join(DEV_WH_TYPES),))
today_out = cur.fetchone()[0]
# total 取 battery_total（已存在于 device 段）
battery_total = 0
print(f"  出入库样本: {len(inv_list)} 条 | 待入库:{pending_in} 今日入:{today_in} 今日出:{today_out}")

# ── 2. 设备调拨 ─────────────────────────────────────────────────
print("[2/4] 设备调拨 t_battery_transfer_batch + bike/site ...")
cur.execute("""
    SELECT id, transfer_type, transfer_count, transfer_status,
           inflow_operate_employee_id, inflow_operate_employee_name,
           outflow_name, inflow_name, create_time
    FROM t_battery_transfer_batch
    WHERE is_del=0
    ORDER BY create_time DESC LIMIT 5000
""")
tf_list = []
for (rid, ttype, cnt, tstatus, oeid, oename, outflow, inflow, ctime) in cur.fetchall():
    tf_list.append({
        "record_id": rid,
        "operator_id": oeid or "",
        "operator_name": oename or "",
        "op_time": str(ctime or ""),
        "device_type": "电池",
        "device_id": (str(cnt) + " 节") if cnt else "",
        "op_type": ttype or "",
        "result": tstatus or "",
        "from_obj": outflow or "",
        "to_obj": inflow or "",
    })
# 补充 车辆调拨
cur.execute("""SELECT id, bike_sn, old_user_name, new_user_name, status, transfer_time, create_time
               FROM t_bike_transfer_log WHERE is_del=0 ORDER BY create_time DESC LIMIT 800""")
for (rid, sn, ou, nu, st, tt, ctime) in cur.fetchall():
    tf_list.append({
        "record_id": rid, "operator_id": "", "operator_name": "",
        "op_time": str(ctime or ""), "device_type": "车辆",
        "device_id": sn or "", "op_type": "过户", "result": st or "",
        "from_obj": ou or "", "to_obj": nu or "",
    })
# 补充 网点调拨
cur.execute("""SELECT id, site_name, old_business_name, new_business_name, operator_name, create_time
               FROM t_site_transfer_log WHERE is_del=0 ORDER BY create_time DESC LIMIT 4000""")
for (rid, sname, ob, nb, oname, ctime) in cur.fetchall():
    tf_list.append({
        "record_id": rid, "operator_id": "", "operator_name": oname or "",
        "op_time": str(ctime or ""), "device_type": "网点",
        "device_id": sname or "", "op_type": "业务变更", "result": "",
        "from_obj": ob or "", "to_obj": nb or "",
    })
cur.execute("SELECT COUNT(*) FROM t_battery_transfer_batch WHERE is_del=0")
tf_total = cur.fetchone()[0]
print(f"  调拨记录: {len(tf_list)} 条（电池批次全量 {tf_total}）")

# ── 3. 电池流通记录 ─────────────────────────────────────────────
print("[3/4] 电池流通 t_battery_circulate_log ...")
cur.execute("""
    SELECT id, battery_device_sn, battery_device_type_id, battery_power,
           outflow_name, outflow_type, inflow_name, inflow_type,
           business_type_first, business_type_second, create_time
    FROM t_battery_circulate_log
    WHERE is_del=0
    ORDER BY create_time DESC LIMIT 5000
""")
circ_list = []
for (rid, sn, mdl, pwr, ofn, oft, ifn, ift, bt1, bt2, ctime) in cur.fetchall():
    circ_list.append({
        "id": rid,
        "bat_sn": sn or "",
        "bat_model": mdl or "",
        "bat_level": pwr if pwr is not None else "",
        "from_obj": ofn or "",
        "from_type": oft or "",
        "to_obj": ifn or "",
        "to_type": ift or "",
        "method": "/".join([x for x in (bt1, bt2) if x]),
        "created_at": str(ctime or ""),
    })
print(f"  流通样本: {len(circ_list)} 条")

# ── 4. 协议→套餐购买订单 ────────────────────────────────────────
print("[4/4] 套餐购买订单 t_exchange_service_order ...")
cur.execute("""
    SELECT id, goods_quantity, goods_type, order_status, pay_way,
           exchange_agreement_id, buyer_user_name, buyer_user_phone,
           pay_fee, will_pay_fee, battery_product_id,
           sys_city_name, sign_site_name, sign_agency_name, create_time
    FROM t_exchange_service_order
    WHERE is_del=0 AND exchange_agreement_id IS NOT NULL AND exchange_agreement_id<>''
    ORDER BY create_time DESC LIMIT 40000
""")
svc = {}
for (oid, qty, gtype, status, payway, aid, bname, bphone,
     payfee, willfee, bprod, city, site, agency, ctime) in cur.fetchall():
    aid = str(aid)
    pf = (payfee or 0) / 100.0
    wf = (willfee or 0) / 100.0
    svc.setdefault(aid, []).append({
        "order_id": oid,
        "qty": qty if qty is not None else "",
        "type": gtype or "",
        "status": status or "",
        "pay_time": "",
        "pay_method": payway or "",
        "desc": gtype or "",
        "agreement_id": aid,
        "buyer": bname or "",
        "buyer_phone": bphone or "",
        "payable_paid": round(pf, 2),
        "effect_time": "",
        "expire_time": "",
        "residual": "",
        "use_status": status or "",
        "use_quota": qty if qty is not None else "",
        "remain_quota": "",
        "battery_product": bprod or "",
        "order_amount": round(wf, 2),
        "discount": "",
        "city_area": city or "",
        "site": site or "",
        "agency": agency or "",
        "create": str(ctime or ""),
    })
conn.close()
print(f"  套餐订单样本: {sum(len(v) for v in svc.values())} 条，覆盖协议 {len(svc)} 个")

# ── 写回 JSON ────────────────────────────────────────────────────
dp = os.path.join(BASE, "data/dashboard_data.json")
print("\n载入 dashboard_data.json ...")
D = json.load(open(dp, encoding="utf-8"))
DEV = D.setdefault("device", {})

DEV["inventory"] = {
    "kpis": {
        "pending_in": pending_in,
        "today_in": today_in,
        "today_out": today_out,
        "total": DEV.get("battery_total", 0),
    },
    "list": inv_list,
    "_note": "出入库明细来自 t_battery_transfer_log（电池流转 in/out），全量 %.0f 万+" % (pending_in/10000.0 + today_in + today_out),
}
DEV["transfer"] = tf_list
DEV["_transfer_note"] = "调拨记录来自 t_battery_transfer_batch + t_bike_transfer_log + t_site_transfer_log；电池批次全量 %d" % tf_total
D["circulation"] = circ_list
D["_circulation_note"] = "电池流通采样自 t_battery_circulate_log（近5000条，非全量22.5M）"
D["agreement_service_orders"] = svc
D["_agreement_service_orders_note"] = "套餐购买订单采样自 t_exchange_service_order 近4万单，按 exchange_agreement_id 分组；覆盖 %d 个协议" % len(svc)

json.dump(D, open(dp, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print("\nWROTE ->", dp, "| bytes:", os.path.getsize(dp))
