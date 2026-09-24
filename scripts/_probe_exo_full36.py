# -*- coding: utf-8 -*-
"""实测 t_exchange_order 全 36 列（含 JOIN 派生）真实 gz 字节/行。
只抽 10 万样本，外推全量(11,131,625)与最近90天(≈786,000)的包体。
JOIN:
  协议类型      <- t_exchange_agreement.type   (exchange_agreement_id)
  车辆名称      <- t_bike.name                 (bike_id)
  借出网点/代理商 <- t_exchange.site_id->t_site.name/agency_id (take_exchange_id)
  归还代理商     <- t_exchange.site_id->t_site.agency_id       (back_exchange_id)
  电量卡*       : busi_rel_order_no 指向招小充外部单, ADB内无对应表 -> 用占位(实付金额=use_power_fee 同量级, 套餐id='')
"""
import pymysql, json, gzip, io, time, sys

import json as _json
_cfg = _json.load(open("config/backup_config.json", encoding="utf-8"))
CFG = dict(host=_cfg["host"], port=_cfg["port"], user=_cfg["user"], password=_cfg["password"],
           database=_cfg["database"], charset="utf8mb4",
           cursorclass=pymysql.cursors.Cursor, connect_timeout=20, read_timeout=600)

def con():
    return pymysql.connect(**CFG)

def q(cur, sql, args=None):
    cur.execute(sql, args); return cur.fetchall()

t0 = time.time()
cn = con(); cur = cn.cursor()

# 1) 抽 10 万样本（最近 + 全量混合，按 create_time 倒序取最近的，更贴近"近90天"字节分布）
print("采样 100000 行...", flush=True)
SAMPLE_SQL = """
SELECT id, exchange_agreement_id, order_status, battery_product_name, site_name, agency_name,
       take_battery_sn, take_battery_way, take_exchange_sn, take_user_id, take_user_phone,
       take_battery_power, take_battery_time, back_battery_sn, back_battery_way, back_exchange_sn,
       back_site_name, back_user_id, back_user_phone, back_battery_power, back_battery_time,
       use_power, mileage, real_pay_price, use_power_fee, busi_rel_order_no,
       bike_user_id, bike_user_phone, take_exchange_id, back_exchange_id, bike_id, create_time
FROM t_exchange_order WHERE is_del=0 ORDER BY create_time DESC LIMIT 100000
"""
cur.execute(SAMPLE_SQL)
rows = cur.fetchall()
cols = [d[0] for d in cur.description]
print("采样耗时 %.1fs, 行=%d" % (time.time()-t0, len(rows)), flush=True)

# 2) 收集 distinct 外键
def collect(idx):
    s = set()
    for r in rows:
        v = r[idx]
        if v is not None:
            s.add(v)
    return s

ci = {c: i for i, c in enumerate(cols)}
aids = collect(ci['exchange_agreement_id'])
bids = collect(ci['bike_id'])
tex = collect(ci['take_exchange_id'])
bex = collect(ci['back_exchange_id'])

print("distinct: agreement=%d bike=%d take_ex=%d back_ex=%d" % (len(aids), len(bids), len(tex), len(bex)), flush=True)

# 3) 加载 lookup（ADB IN 上限 4000，分批）
def batch_in(sql_prefix, ids, getter):
    out = {}
    items = list(ids)
    for i in range(0, len(items), 4000):
        chunk = items[i:i+4000]
        cur.execute(sql_prefix % ",".join(["%s"]*len(chunk)), chunk)
        for row in cur.fetchall():
            getter(out, row)
    return out

agr = batch_in("SELECT id, type FROM t_exchange_agreement WHERE id IN (%s)",
               aids, lambda o, r: o.__setitem__(r[0], r[1] or ""))
bike = batch_in("SELECT id, name FROM t_bike WHERE id IN (%s)",
                bids, lambda o, r: o.__setitem__(r[0], r[1] or ""))
ex2site = {}
if tex or bex:
    allids = (tex | bex)
    ex2site = batch_in("SELECT id, site_id FROM t_exchange WHERE id IN (%s)",
                       allids, lambda o, r: o.__setitem__(r[0], r[1]))
site_info = {}
if ex2site:
    sids = set(ex2site.values())
    site_info = batch_in("SELECT id, name, agency_id FROM t_site WHERE id IN (%s)",
                         sids, lambda o, r: o.__setitem__(r[0], (r[1] or "", r[2] if r[2] is not None else "")))
print("lookup 加载完成, site_info=%d" % len(site_info), flush=True)

def site_of(exid):
    if exid is None: return ("", "")
    sid = ex2site.get(exid)
    if sid is None: return ("", "")
    return site_info.get(sid, ("", ""))

# 4) 列式打包（真实部署格式：列名只存一次，同列值高度重复）vs 逐行JSON上限
OUT_COLS = ["订单编号","协议编号","协议类型","车辆名称","车主用户id","车主用户手机号","电池产品","签约网点","签约代理商",
            "订单状态","借出电池SN","借出方式","借出换电柜","借出网点","借出代理商","借出用户id","借出用户手机号",
            "借出电量","借出时间","归还电池SN","归还方式","归还换电柜","归还网点","归还代理商","归还用户id","归还用户手机号",
            "归还电量","归还时间","消耗电量","预计耗电度数(kw/h)","行驶里程（千米）","订单金额","电量卡实付金额","电费",
            "电量卡服务单购买订单id","电量卡套餐id"]

col = {k: [] for k in OUT_COLS}
gn = 0
tot_src_bytes = 0
perrow_gz = 0
for r in rows:
    d = {c: r[ci[c]] for c in cols}
    t_site, t_agency = site_of(d['take_exchange_id'])
    b_site, b_agency = site_of(d['back_exchange_id'])
    rec = {
        "订单编号": d['id'],
        "协议编号": d['exchange_agreement_id'],
        "协议类型": agr.get(d['exchange_agreement_id'], ""),
        "车辆名称": bike.get(d['bike_id'], ""),
        "车主用户id": d['bike_user_id'],
        "车主用户手机号": d['bike_user_phone'],
        "电池产品": d['battery_product_name'],
        "签约网点": d['site_name'],
        "签约代理商": d['agency_name'],
        "订单状态": d['order_status'],
        "借出电池SN": d['take_battery_sn'],
        "借出方式": d['take_battery_way'],
        "借出换电柜": d['take_exchange_sn'],
        "借出网点": t_site,
        "借出代理商": t_agency,
        "借出用户id": d['take_user_id'],
        "借出用户手机号": d['take_user_phone'],
        "借出电量": d['take_battery_power'],
        "借出时间": d['take_battery_time'],
        "归还电池SN": d['back_battery_sn'],
        "归还方式": d['back_battery_way'],
        "归还换电柜": d['back_exchange_sn'],
        "归还网点": d['back_site_name'],
        "归还代理商": b_agency,
        "归还用户id": d['back_user_id'],
        "归还用户手机号": d['back_user_phone'],
        "归还电量": d['back_battery_power'],
        "归还时间": d['back_battery_time'],
        "消耗电量": d['use_power'],
        "预计耗电度数(kw/h)": round((d['use_power'] or 0)/1000.0, 3) if d['use_power'] is not None else None,
        "行驶里程（千米）": round((d['mileage'] or 0)/1000.0, 3) if d['mileage'] is not None else None,
        "订单金额": round((d['real_pay_price'] or 0)/100.0, 2) if d['real_pay_price'] is not None else None,
        "电量卡实付金额": float(d['use_power_fee']) if d['use_power_fee'] is not None else None,
        "电费": float(d['use_power_fee']) if d['use_power_fee'] is not None else None,
        "电量卡服务单购买订单id": d['busi_rel_order_no'],
        "电量卡套餐id": "",
    }
    line = json.dumps(rec, ensure_ascii=False, separators=(",", ":"))
    tot_src_bytes += len(line.encode("utf-8"))
    perrow_gz += len(gzip.compress(line.encode("utf-8"), 9))
    for k, v in rec.items():
        col[k].append(v)
    gn += 1

# 列式整体 gzip
col_gz = len(gzip.compress(json.dumps(col, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), 9))
bpr_col = col_gz / gn
bpr_row = perrow_gz / gn
print("=" * 60)
print("样本行数: %d" % gn)
print("源 JSON: %.1f 字节/行" % (tot_src_bytes/gn))
print("逐行JSON gzip(上限): %d 总字节 => %.2f 字节/行" % (perrow_gz, bpr_row))
print("列式 gzip(真实部署): %d 总字节 => %.2f 字节/行" % (col_gz, bpr_col))
print("外推(列式,真实部署):")
print("  最近90天 (786,000 行): %.1f MB" % (bpr_col*786000/1024/1024))
print("  全量   (11,131,625 行): %.1f MB" % (bpr_col*11131625/1024/1024))
print("  (含 +30%% 字典/余量): %.1f MB" % (bpr_col*11131625*1.3/1024/1024))
print("外推(逐行JSON上限):")
print("  全量   (11,131,625 行): %.1f MB" % (bpr_row*11131625/1024/1024))
print("耗时 %.1fs" % (time.time()-t0))
cn.close()
