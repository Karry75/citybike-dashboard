# -*- coding: utf-8 -*-
"""
全量抽取「换电柜明细」(58 列) 与「设备基础表」(39 列)，直接连生产 ADB (sharing-citybike-pro)。

数据源：
  t_exchange             换电柜主表 (id/device_id/device_sn/online_status/scheme_version/site_id/...)
  t_exchange_model       型号 (show_name/store_num) 经 device_type_id 关联
  t_site                 网点 (名称/状态/开业时间/省市区街/地址/业务员/联系人/电话/channel_mark/merchant_id)
  t_merchant             商户 (lp_phone = 收益人/法人手机) 经 merchant_id 关联
  t_exchange_last_upload 柜机实时 (主控/检测板 软硬版本、电压/电流/电表/备电/烟感/水浸/灭火器/后仓门/温度)
  t_exchange_store       仓位级 (number/status/door/soft_lock/battery_sn/sensor/error/data)，按 device_sn 聚合
  t_exchange_last_store  仓位实时 (soc/slot_temp) —— 优先用 store.data JSON 的 soc/temp
  t_exchange_order       换电订单 (按 take_exchange_id 聚合 7/30/90 天次数&用户数、近1月失败数)
  t_exchange_store_lock_log 锁仓流水 (按 exchange_id+store_number 取最新一条)

输出：
  data/cabinet_full.json   换电柜明细 (柜级，约 8608 行 × 58 列)
  data/devicebase_full.json 设备基础表 (仓位级，约 4 万行 × 39 列)

两表均不采样、不截断，全量落盘，供 build_agreement_pack.py <cabinet|devicebase> 打包。
"""
import json, pymysql, sys, datetime, os, time

ROOT = r"D:/workboddy file/dudu分析/citybike_backup"
DB = json.load(open(os.path.join(ROOT, "config/backup_config.json"), encoding="utf-8"))
DB.pop("workers", None)
OUT_CAB = os.path.join(ROOT, "data", "cabinet_full.json")
OUT_DEV = os.path.join(ROOT, "data", "devicebase_full.json")

# ── 中文映射 ──
ONLINE_CN = {"online": "在线", "offline": "离线", "": "—", None: "—"}
SITE_STATUS_CN = {"have_opened": "已开业", "closed": "已关闭", "not_cooperation": "未合作",
                  "wait_delivery": "待送货", "wait_install": "待安装", "wait_audit": "待审批",
                  "wait_open": "待开业", "wait_acceptance": "待验收", "": "—", None: "—"}
DOOR_CN = {"unopen": "未开", "open": "已开", "": "—", None: "—"}
TOUCH_CN = {"touch": "到位", "untouch": "未到位", "": "—", None: "—"}
ANTI_CN = {"touch": "触发", "untouch": "正常", "": "—", None: "—"}
LOCK_CN = {"on": "锁仓", "off": "未锁", "": "—", None: "—"}
SIMPLE_CN = {"normal": "正常", "abnormal": "异常", "on": "开", "off": "关",
             "open": "开", "close": "关", "": "—", None: "—"}


def ms2str(v):
    if not v:
        return ""
    try:
        return (datetime.datetime.utcfromtimestamp(int(v) / 1000)
                + datetime.timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(v)


def cv(v):
    return v if v not in (None, "") else "—"


t0 = time.time()
conn = pymysql.connect(**DB)
cur = conn.cursor()
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
    print("[%6.1fs] %s" % (time.time() - t0, msg), flush=True)


# 时间窗口（毫秒）
NOW = int(time.time() * 1000)
C7, C30, C90 = NOW - 7 * 86400000, NOW - 30 * 86400000, NOW - 90 * 86400000

# ── 1. 维度映射 ──
log("加载维度映射…")
site_map = {}
for r in q("SELECT id,name,site_status,audit_progress,start_open_time,city,area,street,community,address,"
           "business_name,contact_person_name,contact_person_tel,channel_mark,merchant_id,province "
           "FROM t_site WHERE is_del=0", "m_site"):
    site_map[r[0]] = r
merch_lp = {r[0]: (r[1] or "") for r in q("SELECT id, lp_phone FROM t_merchant WHERE is_del=0", "m_merch")}
model_map = {r[0]: (r[1] or "", r[2] or 0) for r in q(
    "SELECT id, show_name, store_num FROM t_exchange_model WHERE is_del=0", "m_model")}
up_map = {}
for r in q("SELECT device_sn, main_soft_ver, main_hard_ver, acq_soft_ver, acq_hard_ver, "
           "e_meter_v, e_meter_a, e_meter_w, e_meter_wh, smoke, flooded, fire, backup_power, "
           "backup_volt, back_door, temp FROM t_exchange_last_upload WHERE is_del=0", "m_up"):
    up_map[r[0]] = r

# ── 2. 仓位聚合（按 device_sn）──
log("聚合仓位 (t_exchange_store)…")
stores = q("SELECT device_sn, number, status, door_status, touch_status, soft_lock_status, "
            "battery_sn, sensor, error, last_upload_time, data "
            "FROM t_exchange_store WHERE is_del=0", "stores")
store_by_sn = {}
for r in stores:
    store_by_sn.setdefault(r[0], []).append(r)
log("仓位 %d 条 / %d 个设备SN" % (len(stores), len(store_by_sn)))


def parse_data(j):
    if not j:
        return {}
    try:
        return json.loads(j)
    except Exception:
        return {}


def build_store_agg(sn):
    rows = store_by_sn.get(sn, [])
    total = len(rows)
    have_bat = avail = ret = empty = locked = charge_err = fault = 0
    bat_list, temp_list, door_list, touch_list, anti_list, lock_list, fault_slots = [], [], [], [], [], [], []
    for r in rows:
        num, status, door, touch, soft, bsn, sensor, error, data = r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8], r[10]
        dj = parse_data(data)
        soc = dj.get("soc", "")
        tempv = dj.get("temp", "")
        # 数字
        if bsn:
            have_bat += 1
        if status == "full":
            avail += 1
        if status == "none":
            empty += 1
            if soft != "on":
                ret += 1
        if soft == "on":
            locked += 1
        err_arr = (error or "[]")
        has_err = err_arr not in ("[]", "", "null", None)
        if status == "error" or has_err:
            fault += 1
            fault_slots.append(str(num))
        if status == "charging" and has_err:
            charge_err += 1
        # 文本聚合
        if bsn:
            bat_list.append("%s:%s(%s%%)" % (num, bsn, soc if soc != "" else "—"))
        if tempv:
            try:
                tarr = json.loads(tempv) if isinstance(tempv, str) and tempv.startswith("[") else [float(tempv)]
                tv = "%.1f" % (sum(tarr) / len(tarr))
            except Exception:
                tv = str(tempv)
            temp_list.append("%s:%s" % (num, tv))
        door_list.append("%s:%s" % (num, DOOR_CN.get(door, door or "—")))
        touch_list.append("%s:%s" % (num, TOUCH_CN.get(touch, touch or "—")))
        # 防盗 = sensor "unopen|unlock|touch" 第三部分
        anti = "—"
        if sensor and "|" in sensor:
            parts = sensor.split("|")
            if len(parts) >= 3:
                anti = ANTI_CN.get(parts[2], parts[2])
        anti_list.append("%s:%s" % (num, anti))
        lock_list.append("%s:%s" % (num, LOCK_CN.get(soft, soft or "—")))
    return dict(total=total, have_bat=have_bat, avail=avail, ret=ret, empty=empty, locked=locked,
                charge_err=charge_err, fault=fault, fault_slots=" / ".join(fault_slots),
                bat_list=" / ".join(bat_list), temp_list=" / ".join(temp_list),
                door_list=" / ".join(door_list), touch_list=" / ".join(touch_list),
                anti_list=" / ".join(anti_list), lock_list=" / ".join(lock_list))


# ── 3. 换电订单聚合（按 take_exchange_id）──
log("聚合换电订单 (t_exchange_order)…")
order_agg = {}
for r in q("SELECT take_exchange_id,"
           " SUM(CASE WHEN exchange_order_status='success' AND create_time>=%d THEN 1 ELSE 0 END)," % C7 +
           " COUNT(DISTINCT CASE WHEN exchange_order_status='success' AND create_time>=%d THEN consume_user_id END)," % C7 +
           " SUM(CASE WHEN exchange_order_status='success' AND create_time>=%d THEN 1 ELSE 0 END)," % C30 +
           " COUNT(DISTINCT CASE WHEN exchange_order_status='success' AND create_time>=%d THEN consume_user_id END)," % C30 +
           " SUM(CASE WHEN exchange_order_status='success' AND create_time>=%d THEN 1 ELSE 0 END)," % C90 +
           " COUNT(DISTINCT CASE WHEN exchange_order_status='success' AND create_time>=%d THEN consume_user_id END)," % C90 +
           " SUM(CASE WHEN exchange_order_status<>'success' AND create_time>=%d THEN 1 ELSE 0 END)" % C30 +
           " FROM t_exchange_order WHERE take_exchange_id>0 AND is_del=0 GROUP BY take_exchange_id", "ord_agg"):
    order_agg[r[0]] = r[1:]
log("订单聚合 %d 个柜" % len(order_agg))

# ── 4. 锁仓流水（按 exchange_id + store_number 取最新一条）──
log("聚合锁仓流水 (t_exchange_store_lock_log)…")
lock_map = {}
for r in q("SELECT l.exchange_id, l.store_number, l.create_time, l.remark, l.operation_user_id, l.operation_user_name "
           "FROM t_exchange_store_lock_log l JOIN ("
           "SELECT exchange_id, store_number, MAX(id) AS mid FROM t_exchange_store_lock_log WHERE is_del=0 "
           "GROUP BY exchange_id, store_number) m ON l.id=m.mid WHERE l.is_del=0", "lock"):
    lock_map[(r[0], r[1])] = r[2:]
log("锁仓流水 %d 个 (柜,仓位) 组合" % len(lock_map))

# ── 5. 换电柜主表 ──
log("抽取 t_exchange 主表…")
exs = q("SELECT id, device_id, device_sn, online_status, scheme_version, site_id, last_online_time, "
         "last_offline_time, last_upload_time, site_bind_time, site_unbind_time, device_type_id "
         "FROM t_exchange WHERE is_del=0 ORDER BY id", "ex")
log("换电柜 %d 台" % len(exs))
if not exs:
    print("!! 未取到换电柜数据，终止", file=sys.stderr)
    sys.exit(1)

conn.close()

# ── 6. 组装两表 ──
log("组装换电柜明细(58列) + 设备基础表(39列)…")
cabinet_rows, dev_rows = [], []
ex_id_to_sn = {}
for ex in exs:
    ex_id, dev_id, sn, online, scheme, site_id, lo, lf, lu, bind, unbind, dtype = ex
    ex_id_to_sn[ex_id] = sn
    s = site_map.get(site_id)
    sname = s[1] if s else "—"
    sstatus = SITE_STATUS_CN.get(s[3], s[3] or "—") if s else "—"
    sopen = ms2str(s[4]) if s else ""
    city = s[5] if s else "—"; area = s[6] if s else "—"; street = s[7] if s else "—"
    community = s[8] if s else "—"; addr = s[9] if s else "—"
    business = s[10] if s else "—"; contact = s[11] if s else "—"; ctel = s[12] if s else "—"
    channel = s[13] if s else "—"; merch_id = s[14] if s else None
    benphone = merch_lp.get(merch_id, "") if merch_id else "—"
    benphone = benphone or "—"
    m = model_map.get(dtype)
    model_name = m[0] if m else "—"; mstore = m[1] if m else 0
    up = up_map.get(sn)
    up_d = dict(zip(["main_soft_ver", "main_hard_ver", "acq_soft_ver", "acq_hard_ver",
                     "e_meter_v", "e_meter_a", "e_meter_w", "e_meter_wh", "smoke", "flooded",
                     "fire", "backup_power", "backup_volt", "back_door", "temp"],
                    up[1:16])) if up else {}
    sa = build_store_agg(sn)
    oa = order_agg.get(ex_id) or (0, 0, 0, 0, 0, 0, 0)

    def U(k):
        v = up_d.get(k, "")
        return SIMPLE_CN.get(v, v) if k in ("smoke", "flooded", "fire", "backup_power", "back_door") else (v or "—")

    cabinet_rows.append({
        "设备ID": dev_id, "换电柜ID": ex_id, "换电柜SN": sn,
        "在线状态": ONLINE_CN.get(online, online or "—"), "换电柜型号": model_name,
        "协议版本": scheme or "—", "网点ID": site_id or "—", "网点名称": sname,
        "网点状态": sstatus, "网点开业时间": sopen, "城市": city, "区": area, "街道": street,
        "社区": community, "地址": addr, "业务员": business, "网点联系人": contact,
        "联系人电话": ctel, "网点收益人手机号": benphone, "标签": channel or "—",
        "主控软件版本": cv(up_d.get("main_soft_ver")), "主控硬件版本": cv(up_d.get("main_hard_ver")),
        "检测板软件版本": cv(up_d.get("acq_soft_ver")), "检测板硬件版本": cv(up_d.get("acq_hard_ver")),
        "总仓位数": sa["total"] or (mstore or 0), "有电池仓位数": sa["have_bat"],
        "可换仓位数": sa["avail"], "可还仓位数": sa["ret"], "空仓仓位数": sa["empty"],
        "锁仓仓位数": sa["locked"], "充电异常仓位数": sa["charge_err"], "故障仓": sa["fault"],
        "实时电压": cv(up_d.get("e_meter_v")), "实时电流": cv(up_d.get("e_meter_a")),
        "电表度数": cv(up_d.get("e_meter_wh")), "备电状态": U("backup_power"),
        "备电电压": cv(up_d.get("backup_volt")), "后仓门状态": U("back_door"),
        "烟感检测": U("smoke"), "水浸检测": U("flooded"), "灭火器": U("fire"),
        "7天换电次数": oa[0] or 0, "7天换电用户数": oa[1] or 0,
        "30天换电次数": oa[2] or 0, "30天换电用户": oa[3] or 0,
        "90天换电次数": oa[4] or 0, "90天换电用户": oa[5] or 0,
        "近1个月换电失败订单数": oa[6] or 0,
        "最后上线时间": ms2str(lo), "最后离线时间": ms2str(lf), "最后上报时间": ms2str(lu),
        "所有电池SN": sa["bat_list"] or "—", "换电柜故障仓位编号": sa["fault_slots"] or "—",
        "换电柜仓位温度": sa["temp_list"] or "—", "仓门状态": sa["door_list"] or "—",
        "到位状态": sa["touch_list"] or "—", "防盗状态": sa["anti_list"] or "—",
        "锁仓状态": sa["lock_list"] or "—",
    })

    # 设备基础表（仓位级）：每台柜的每个仓位一行
    slist = store_by_sn.get(sn, [])
    oa_dev = oa
    for r in slist:
        num, status, door, touch, soft, bsn, sensor, error, sut, data = r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8], r[9], r[10]
        dj = parse_data(data)
        soc = dj.get("soc", "") or "—"
        tempv = dj.get("temp", "")
        if tempv:
            try:
                tarr = json.loads(tempv) if isinstance(tempv, str) and tempv.startswith("[") else [float(tempv)]
                tv = "%.1f" % (sum(tarr) / len(tarr))
            except Exception:
                tv = str(tempv)
        else:
            tv = "—"
        anti = "—"
        if sensor and "|" in sensor:
            parts = sensor.split("|")
            if len(parts) >= 3:
                anti = ANTI_CN.get(parts[2], parts[2])
        lk = lock_map.get((ex_id, num))
        if lk:
            lk_time, lk_remark, lk_uid, lk_uname = lk
        else:
            lk_time, lk_remark, lk_uid, lk_uname = "", "", "", ""
        dev_rows.append({
            "换电柜ID": ex_id, "设备ID": dev_id, "设备SN": sn,
            "在线状态": ONLINE_CN.get(online, online or "—"), "设备型号": model_name,
            "协议版本": scheme or "—", "网点ID": site_id or "—", "网点名称": sname,
            "网点联系人": contact, "联系人电话": ctel, "业务员名称": business,
            "省": cv(s[15] if s else None) if s else "—", "市": city, "区": area,
            "街道": street, "详细地址": addr, "网点状态": sstatus,
            "网点首次绑定时间": ms2str(bind), "网点最新绑定时间": ms2str(unbind),
            "最后上线时间": ms2str(lo), "最后离线时间": ms2str(lf), "最后上报时间": ms2str(lu),
            "总仓位数": len(slist) or (mstore or 0), "仓位编号": num,
            "电池SN": bsn or "—", "电池电电量": soc, "仓位温度": tv,
            "仓门状态": DOOR_CN.get(door, door or "—"), "到位状态": TOUCH_CN.get(touch, touch or "—"),
            "防盗状态": anti, "锁仓状态": LOCK_CN.get(soft, soft or "—"),
            "最后一次锁仓时间": ms2str(lk_time), "最后一次锁仓备注": lk_remark or "—",
            "最后一次锁仓操作人id": lk_uid or "—", "最后一次锁仓操作人名称": lk_uname or "—",
            "近1个月换电次数": oa_dev[2] or 0, "近1个月换电用户数": oa_dev[3] or 0,
            "近3个月换电次数": oa_dev[4] or 0, "近3个月换电用户数": oa_dev[5] or 0,
        })

# 设备基础表「网点最新绑定时间」：库内无独立"最新绑定"字段，统一以 site_unbind_time
# （最近一次绑定/解绑时间）近似标注；如需严格"最新绑定"应接入 t_exchange_site_bind_log。

# ── 7. 质量快检 ──
log("数据质量快检…")
for nm, rows, pk in (("换电柜明细", cabinet_rows, "换电柜SN"), ("设备基础表", dev_rows, "设备SN")):
    miss = sum(1 for d in rows if d.get(pk) in (None, "", "—"))
    log("  %s: %d 行，SN 缺失 %d" % (nm, len(rows), miss))

# ── 8. 写盘 ──
log("写 cabinet_full.json (%d 行)…" % len(cabinet_rows))
json.dump(cabinet_rows, open(OUT_CAB, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
log("写 devicebase_full.json (%d 行)…" % len(dev_rows))
json.dump(dev_rows, open(OUT_DEV, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
log("完成。cabinet=%.2fMB, devicebase=%.2fMB" % (
    os.path.getsize(OUT_CAB) / 1048576.0, os.path.getsize(OUT_DEV) / 1048576.0))
if ERR:
    print("\n有 %d 处查询异常:" % len(ERR))
    for e in ERR:
        print("  -", e)
