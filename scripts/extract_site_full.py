# -*- coding: utf-8 -*-
"""全量抽取网点列表（t_site is_del=0，约 11091 条）并写入 data/dashboard_data_lite.json 的 site.detail。

相比 extract_dashboard.py 的网点明细，本脚本额外补充：
  - street / community（街道 / 社区）→ 支撑「城市-区域-街道-社区」四级级联筛选
  - battery_product_id（电池产品ID，用于精确筛选）
  - site_status_cn（t_site.site_status 的 on/off → 启用/停用），与 audit_progress 八态并存
  - 代理商名称多源补全（t_exchange_order + t_site_update_agency_log）
不做任何采样/截断，全量落盘。原文件会先备份为 .bak_siteful。
"""
import json, pymysql, sys, datetime, os, shutil, time

ROOT = r"D:/workboddy file/dudu分析/citybike_backup"
DB = json.load(open(os.path.join(ROOT, "config/backup_config.json"), encoding="utf-8"))
DB.pop("workers", None)
LITE = os.path.join(ROOT, "data/dashboard_data_lite.json")

# ---------- 中文映射（与 extract_dashboard.py 保持一致） ----------
SITE_STATUS_CN = {"have_opened": "已开业", "closed": "已关闭", "not_cooperation": "未合作",
                  "wait_delivery": "待送货", "wait_install": "待安装", "wait_audit": "待审批",
                  "wait_open": "待开业", "wait_acceptance": "待验收", "": "—", None: "—"}
SITE_ONOFF_CN = {"on": "启用", "off": "停用", "": "—", None: "—"}
SITE_TYPE_CN = {1: "换电", 2: "车吧", 4: "售车", 5: "租车", 7: "其他(脏数据)"}
BOOL_CN = {1: "是", 0: "否", "1": "是", "0": "否", True: "是", False: "否", "": "—", None: "—"}
ALONE_METER_CN = {"not_install": "不安装", "only_install": "仅安装", "install_and_use": "安装并用于电费结算",
                  "gdj_install": "供电局安装", "": "—", None: "—"}
ELECTRIC_WAY_CN = {"online": "线上", "offline": "线下", "gdj_deduct": "供电局扣减",
                   "not_settle": "不结算", "": "—", None: "—"}
LOCATE_CN = {"indoor": "室内", "outdoor": "室外", "": "—", None: "—"}


def ms2str(v):
    if not v:
        return ""
    try:
        return (datetime.datetime.utcfromtimestamp(int(v) / 1000)
                + datetime.timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(v)


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


# ---------- 1. 维度映射 ----------
log("构建维度映射…")
industry_map = {r[0]: (r[1] or "行业#%s" % r[0]) for r in q(
    "SELECT id, name FROM t_site_industry WHERE is_del=0", "m_ind")}
distributor_map = {r[0]: (r[1] or "渠道商#%s" % r[0]) for r in q(
    "SELECT id, name FROM t_distributor WHERE is_del=0", "m_dis")}
merchant_map = {r[0]: (r[1] or "商户#%s" % r[0]) for r in q(
    "SELECT id, name FROM t_merchant WHERE is_del=0", "m_mer")}
battery_product_map = {r[0]: (r[1] or "电池产品#%s" % r[0]) for r in q(
    "SELECT id, name FROM t_battery_product WHERE is_del=0", "m_bp")}

# 代理商名称：多源补全（换电订单 + 网点归属变更日志）
agency_name_map = {}
for r in q("SELECT DISTINCT agency_id, agency_name FROM t_exchange_order "
           "WHERE agency_name IS NOT NULL AND agency_name<>''", "m_ag_order"):
    if r[0]:
        agency_name_map[r[0]] = r[1]
for r in q("SELECT before_agency_id, before_agency_name FROM t_site_update_agency_log "
           "WHERE before_agency_name IS NOT NULL AND before_agency_name<>'' GROUP BY 1,2", "m_ag_lb"):
    if r[0] and r[0] not in agency_name_map:
        agency_name_map[r[0]] = r[1]
for r in q("SELECT after_agency_id, after_agency_name FROM t_site_update_agency_log "
           "WHERE after_agency_name IS NOT NULL AND after_agency_name<>'' GROUP BY 1,2", "m_ag_la"):
    if r[0] and r[0] not in agency_name_map:
        agency_name_map[r[0]] = r[1]
log("代理商名称映射 %d 个" % len(agency_name_map))

# 网点监控
site_monitor_map = {r[0]: True for r in q(
    "SELECT DISTINCT site_id FROM t_monitor_install_log WHERE status='install' AND is_del=0", "m_mon")}

# 换电柜数量 / 在线离线
site_cab_cnt, site_cab_onoff = {}, {}
for r in q("SELECT site_id, COUNT(*) FROM t_exchange WHERE is_del=0 GROUP BY site_id", "m_cc"):
    site_cab_cnt[r[0]] = r[1]
for r in q("SELECT site_id, online_status, COUNT(*) FROM t_exchange WHERE is_del=0 "
           "GROUP BY site_id, online_status", "m_co"):
    d = site_cab_onoff.setdefault(r[0], {"online": 0, "offline": 0})
    d["online" if r[1] == "online" else "offline"] += r[2]

# 网点仓位电池状态聚合
site_store_map = {}
for r in q("SELECT e.site_id, es.status, COUNT(*) FROM t_exchange_store es "
           "JOIN t_exchange e ON es.device_sn=e.device_sn "
           "WHERE es.is_del=0 AND e.is_del=0 GROUP BY e.site_id, es.status", "m_st"):
    d = site_store_map.setdefault(r[0], {"full": 0, "error": 0, "charging": 0, "none": 0})
    if r[1] in d:
        d[r[1]] += r[2]
log("柜机映射 %d / 仓位映射 %d / 监控 %d" % (len(site_cab_cnt), len(site_store_map), len(site_monitor_map)))


def _battery(sid):
    d = site_store_map.get(sid)
    if not d:
        return "0/0"
    return "%d/%d" % (d["full"] + d["error"] + d["charging"], d["full"] + d["charging"])


def _cab_status(sid):
    d = site_cab_onoff.get(sid)
    if not d:
        return "无柜机"
    return "在线%d/离线%d" % (d["online"], d["offline"])


def _pair(name, _id, fallback):
    """输出 名称#ID；ID 为空返回 —"""
    if not _id:
        return "—"
    return "%s#%s" % (name or fallback, _id)


# ---------- 2. 全量网点 ----------
log("抽取 t_site 全量…")
rows = q(
    "SELECT id, name, images, industry_id, type, audit_progress, locating_place, alone_meter_status, "
    "electric_settle_way, address, create_time, start_open_time, close_time, is_show, is_promoter, "
    "merchant_id, business_id, business_name, business_type, agency_id, distributor_id, battery_product_id, "
    "site_status, remark, province, city, area, street, community "
    "FROM t_site WHERE is_del=0 ORDER BY create_time DESC", "site_full")
log("t_site 返回 %d 行" % len(rows))
if not rows:
    print("!! 未取到网点数据，终止", file=sys.stderr)
    sys.exit(1)

detail = [{
    "id": r[0], "name": r[1] or "—", "images": r[2] or "",
    "industry": industry_map.get(r[3], "行业#%s" % r[3] if r[3] else "—"),
    "type": r[4], "type_name": SITE_TYPE_CN.get(r[4], "未知(%s)" % r[4]),
    "cabinet_count": site_cab_cnt.get(r[0], 0),
    "cabinet_status": _cab_status(r[0]),
    "battery_count": _battery(r[0]),
    "agency": _pair(agency_name_map.get(r[19]), r[19], "未知代理商"),
    "agency_id": r[19],
    "distributor": _pair(distributor_map.get(r[20]), r[20], "未知渠道商"),
    "distributor_id": r[20],
    "merchant": _pair(merchant_map.get(r[15]), r[15], "未知商家"),
    "merchant_id": r[15],
    "business": _pair(r[17], r[16], "未知业务员"),
    "business_id": r[16],
    "battery_product": battery_product_map.get(r[21], "电池产品#%s" % r[21] if r[21] else "—"),
    "battery_product_id": r[21],
    "status": SITE_STATUS_CN.get(r[5], r[5] or "—"),
    "site_status": SITE_ONOFF_CN.get(r[22], r[22] or "—"),
    "locating": LOCATE_CN.get(r[6], r[6] or "—"),
    "monitor": ("有监控" if r[0] in site_monitor_map else "无监控"),
    "is_promoter": BOOL_CN.get(r[14], "—"),
    "sale_qrcode": "未接入",  # t_site 无该字段，诚实标注
    "meter": ALONE_METER_CN.get(r[7], r[7] or "—"),
    "settle_way": ELECTRIC_WAY_CN.get(r[8], r[8] or "—"),
    "address": r[9] or "—",
    "create": ms2str(r[10]), "open": ms2str(r[11]), "close": ms2str(r[12]),
    "is_show": BOOL_CN.get(r[13], "—"),
    "remark": r[23] or "—",
    "province": r[24] or "—", "city": r[25] or "—", "area": r[26] or "—",
    "street": r[27] or "—", "community": r[28] or "—",
} for r in rows]

conn.close()

# ---------- 3. 质量快检 ----------
log("数据质量快检…")


def _fill(k):
    n = sum(1 for d in detail if d.get(k) not in ("", "—", None, 0))
    return "%s: %d/%d (%.1f%%)" % (k, n, len(detail), n * 100.0 / len(detail))


for k in ("name", "city", "area", "street", "community", "agency", "merchant",
          "business", "battery_product", "open", "create"):
    log("  " + _fill(k))
log("  未知代理商: %d" % sum(1 for d in detail if "未知代理商" in str(d["agency"])))

# ---------- 4. 写回 lite JSON ----------
log("读取 lite JSON…")
data = json.load(open(LITE, encoding="utf-8"))
old = len(data.get("site", {}).get("detail", []))
bak = LITE + ".bak_siteful"
if not os.path.exists(bak):
    log("备份原文件 → %s" % os.path.basename(bak))
    shutil.copy2(LITE, bak)
data.setdefault("site", {})["detail"] = detail
data["site"]["detail_total"] = len(detail)
data["site"]["detail_synced_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
log("写回 lite JSON（site.detail %d → %d）…" % (old, len(detail)))
json.dump(data, open(LITE, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
log("完成，文件 %.2f MB" % (os.path.getsize(LITE) / 1048576.0))
if ERR:
    print("\n有 %d 处查询异常:" % len(ERR))
    for e in ERR:
        print("  -", e)
