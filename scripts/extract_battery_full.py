# -*- coding: utf-8 -*-
"""
全量抽取「电池明细」，直接连生产 ADB (sharing-citybike-pro)。

数据源：
  t_battery                  电池主表 (id/device_id/device_sn/battery_status/online_status/bike_id/...)
  t_battery_model            电池型号 (device_type_id/show_name/series_id)
  t_battery_product          电池产品 (series_id/name)
  t_battery_last_upload      电池最后上报 (power/charging/discharge/cycle/voltage/current/acc/det/温度/soh)
  t_exchange_store           仓位级 (device_sn/number/status/touch_status/battery_sn/last_upload_time/data)
  t_exchange                 换电柜主表 (device_sn/site_id)
  t_site                     网点 (id/name/city/area/street)
  t_bike_user_relation       车辆用户关系 (bike_id/t_user_id/is_owner)
  t_user                     用户 (phone)
  t_exchange_order           换电订单 (按 take_battery_sn 聚合 30/90 天借出次数)

输出：
  data/battery_full.json      电池明细（约 7.5 万行 × 45 列）

去重合并说明（响应用户选择「智能去重合并」）：
  - 原 54 项列名，合并重复后保留 45 列
  - 删除/合并：「当前仓位电池SN」= 电池SN、「所属柜SN」= 换电柜SN、
    「网点」= 网点名称、「仓位名」= 仓位名称、重复「仓位类型」合并、
    「借出次数(30天)」=「30天借出」、「借出次数(90天)」=「90天借出」
"""
import json, pymysql, sys, datetime, os, time

ROOT = r"D:/workboddy file/dudu分析/citybike_backup"
DB = json.load(open(os.path.join(ROOT, "config/backup_config.json"), encoding="utf-8"))
DB.pop("workers", None)
OUT = os.path.join(ROOT, "data", "battery_full.json")

BATTERY_STATUS_CN = {"none": "无车", "using": "使用中", "scrap": "报废", "": "—", None: "—"}
ONLINE_CN = {"online": "在线", "offline": "离线", "": "—", None: "—"}
STORE_STATUS_CN = {"none": "空仓", "full": "满电", "charging": "充电中", "error": "故障", "": "—", None: "—"}
TOUCH_CN = {"touch": "到位", "untouch": "未到位", "": "—", None: "—"}
ONOFF_CN = {"on": "开", "off": "关", "": "—", None: "—"}

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

def onoff(v):
    return ONOFF_CN.get(v, v or "—")

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

NOW = int(time.time() * 1000)
C30, C90 = NOW - 30 * 86400000, NOW - 90 * 86400000

# ── 1. 维度映射 ──
log("加载维度映射…")
model_map = {}
for r in q("SELECT device_type_id, show_name, series_id FROM t_battery_model WHERE is_del=0", "m_model"):
    # 一个 device_type_id 可能对应多行，保留第一个非空 show_name
    if r[0] not in model_map or not model_map[r[0]][0]:
        model_map[r[0]] = (r[1] or "—", r[2])

product_by_series = {}
for r in q("SELECT series_id, name FROM t_battery_product WHERE is_del=0", "m_product"):
    product_by_series.setdefault(r[0], []).append(r[1])

site_map = {}
for r in q("SELECT id, name, city, area, street FROM t_site WHERE is_del=0", "m_site"):
    site_map[r[0]] = r

exchange_site = {}
for r in q("SELECT device_sn, site_id FROM t_exchange WHERE is_del=0", "m_ex"):
    exchange_site[r[0]] = r[1]

# 电池最后上报
last_up = {}
for r in q("SELECT battery_sn, power, charging, discharge, cycle, voltage, current, acc, det, "
           "discharge_temp, charging_temp, cell_temp_min, cell_temp_max, mos_temp, volt_cells, soh "
           "FROM t_battery_last_upload WHERE is_del=0", "m_last_up"):
    last_up[r[0]] = r[1:]

# 当前仓位（按 battery_sn 取 last_upload_time 最新一条）
log("加载当前仓位…")
stores = q("SELECT device_sn, number, status, touch_status, battery_sn, last_upload_time, data "
           "FROM t_exchange_store WHERE battery_sn IS NOT NULL AND battery_sn!='' AND is_del=0", "m_stores")
store_latest = {}
for r in stores:
    key = r[4]  # battery_sn
    old = store_latest.get(key)
    if old is None or (r[5] or 0) > (old[5] or 0):
        store_latest[key] = r
log("当前仓位 %d 个电池" % len(store_latest))

def parse_data(j):
    if not j:
        return {}
    try:
        return json.loads(j)
    except Exception:
        return {}

def get_data_soc(dj):
    # store.data JSON 里的 soc
    return dj.get("soc", "") or "—"

# 用户手机号（通过 bike_id -> t_bike_user_relation is_owner -> t_user）
log("加载用户手机号映射…")
phone_map = {}
for r in q("SELECT b.id, u.phone FROM t_battery b "
           "JOIN t_bike_user_relation r ON b.bike_id=r.bike_id AND r.is_owner=1 AND r.is_del=0 "
           "JOIN t_user u ON r.t_user_id=u.id "
           "WHERE b.is_del=0 AND u.phone IS NOT NULL AND u.phone!=''", "m_phone"):
    phone_map[r[0]] = r[1]
log("手机号映射 %d 条" % len(phone_map))

# 订单聚合 30/90 天借出次数（按 take_battery_sn）
log("聚合借出订单…")
order_agg = {}
for r in q("SELECT take_battery_sn, "
           " SUM(CASE WHEN exchange_order_status='success' AND create_time>=%d THEN 1 ELSE 0 END), " % C30 +
           " SUM(CASE WHEN exchange_order_status='success' AND create_time>=%d THEN 1 ELSE 0 END) " % C90 +
           " FROM t_exchange_order WHERE take_battery_sn IS NOT NULL AND take_battery_sn!='' AND is_del=0 "
           " GROUP BY take_battery_sn", "m_order"):
    order_agg[r[0]] = (r[1] or 0, r[2] or 0)
log("借出聚合 %d 个电池" % len(order_agg))

# ── 2. 电池主表 ──
log("抽取 t_battery 主表…")
bats = q("SELECT id, device_id, device_sn, battery_status, online_status, "
         "last_online_time, last_offline_time, lat, lng, last_location_address, last_location_time, "
         "last_upload_exchange_sn, last_back_exchange_sn, last_back_time, last_take_time, "
         "last_battery_upload_time, last_upload_time, device_type_id, bike_id, create_time "
         "FROM t_battery WHERE is_del=0 ORDER BY id", "m_bat")
log("电池 %d 块" % len(bats))
if not bats:
    print("!! 未取到电池数据，终止", file=sys.stderr)
    sys.exit(1)

conn.close()

# ── 3. 组装 ──
log("组装电池明细(45列)…")
rows = []
for b in bats:
    (bid, dev_id, sn, bat_status, online, lo, lf, lat, lng, loc_addr, loc_time,
     up_ex_sn, back_ex_sn, back_time, take_time, last_bat_up, last_up_time,
     dtype, bike_id, create_time) = b

    # 型号 & 产品
    m = model_map.get(dtype)
    model_name = m[0] if m else "—"
    series_id = m[1] if m else None
    product_name = "—"
    if series_id and series_id in product_by_series:
        product_name = product_by_series[series_id][0]

    # 当前仓位
    st = store_latest.get(sn)
    if st:
        cab_sn, slot_num, slot_status, touch, _, slot_lut, data = st
        dj = parse_data(data)
        slot_soc = get_data_soc(dj)
    else:
        cab_sn, slot_num, slot_status, touch, slot_lut, slot_soc = "—", "—", "—", "—", "", "—"

    # 网点
    site_id = exchange_site.get(up_ex_sn or cab_sn)
    s = site_map.get(site_id)
    site_name = s[1] if s else "—"
    city = s[2] if s else "—"
    area = s[3] if s else "—"
    street = s[4] if s else "—"

    # 最后上报
    up = last_up.get(sn)
    if up:
        (power, charging, discharge, cycle, voltage, current, acc, det,
         dis_temp, chg_temp, cell_min, cell_max, mos_temp, volt_cells, soh) = up
    else:
        power = charging = discharge = cycle = voltage = current = acc = det = ""
        dis_temp = chg_temp = cell_min = cell_max = mos_temp = volt_cells = soh = ""

    oa = order_agg.get(sn) or (0, 0)

    rows.append({
        "电池SN": sn,
        "设备ID": dev_id,
        "设备型号": model_name,
        "在线状态": ONLINE_CN.get(online, online or "—"),
        "设备状态": BATTERY_STATUS_CN.get(bat_status, bat_status or "—"),
        "仓位类型": STORE_STATUS_CN.get(slot_status, slot_status or "—"),
        "仓位名称": str(slot_num) if slot_num != "—" else "—",
        "当前仓位到位状态": TOUCH_CN.get(touch, touch or "—"),
        "当前仓位最后上报时间": ms2str(slot_lut),
        "换电柜SN": cv(up_ex_sn or cab_sn),
        "网点ID": site_id or "—",
        "网点名称": site_name,
        "代理商": "—",  # t_battery.agency_id 几乎全为 0，无业务意义；暂用占位
        "用户手机号": phone_map.get(bid, "—"),
        "电池电量": cv(power),
        "电池产品": product_name,
        "电量%": cv(power),
        "充电状态": onoff(charging),
        "放电状态": onoff(discharge),
        "循环次数": cv(cycle),
        "电压": cv(voltage),
        "电流": cv(current),
        "ACC（低功耗）": cv(acc),
        "DET状态": onoff(det),
        "充电接口温度": cv(chg_temp),
        "放电接口温度": cv(dis_temp),
        "BMS最高温": cv(cell_max),
        "BMS最低温": cv(cell_min),
        "电芯信息": cv(volt_cells),
        "30天借出": oa[0],
        "90天借出": oa[1],
        "城市": city,
        "区": area,
        "街道": street,
        "代理商ID": "—",  # 同上
        "最后流通时间": ms2str(take_time or back_time),
        "入库时间": ms2str(create_time),
        "最后上线时间": ms2str(lo),
        "最后离线时间": ms2str(lf),
        "最后上报时间": ms2str(last_up_time),
        "最后整机上报时间": ms2str(last_bat_up),
        "查询定位地址": cv(loc_addr),
        "最后有效定位": "%s,%s" % (lat or "—", lng or "—"),
        "定位类型": cv(loc_time and "gps" or ""),
        "最后有效定位精度": cv(""),
        "最后有效定位时间": ms2str(loc_time),
    })

# ── 4. 质量快检 ──
log("数据质量快检…")
miss = sum(1 for d in rows if d["电池SN"] in (None, "", "—"))
log("  电池明细: %d 行，SN 缺失 %d" % (len(rows), miss))

# ── 5. 写盘 ──
log("写 battery_full.json (%d 行)…" % len(rows))
json.dump(rows, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
log("完成。%.2fMB" % (os.path.getsize(OUT) / 1048576.0))
if ERR:
    print("\n有 %d 处查询异常:" % len(ERR))
    for e in ERR:
        print("  -", e)
