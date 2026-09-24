#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""精准补 battery_detail 的 belong_type 真值（5 类仓位），不触碰其他模块 / region_monthly。
同时把当前 lite 里的 region_monthly 落盘为 data/region_monthly.json，避免后续 build_lite_data 丢失区域下钻。"""
import json, os, pymysql, time

BASE = "D:/workboddy file/dudu分析/citybike_backup"
LITE = os.path.join(BASE, "data", "dashboard_data_lite.json")
RM_PATH = os.path.join(BASE, "data", "region_monthly.json")
CFG = json.load(open(os.path.join(BASE, "config", "backup_config.json"), encoding="utf-8"))

BELONG_TYPE_CN = {"operate_platform": "运营平台仓库", "bike": "车辆仓库",
                  "exchange": "换电柜仓库", "agency_employee": "代理商员工仓库",
                  "site": "网点仓库", "": "未识别", None: "未识别"}

t = time.time()
print("loading lite (91MB)...", flush=True)
data = json.load(open(LITE, encoding="utf-8"))
print("  loaded in %.1fs" % (time.time() - t), flush=True)

# 1) 查 ADB 真值
conn = pymysql.connect(host=CFG["host"], port=CFG.get("port", 3306), user=CFG["user"],
                       password=CFG["password"], database=CFG["database"],
                       connect_timeout=15, read_timeout=600, charset="utf8mb4")
cur = conn.cursor()
cur.execute("SELECT b.device_sn, br.belong_type FROM t_battery b "
            "LEFT JOIN t_battery_belong_relation br ON b.id=br.battery_id AND br.is_del=0 "
            "WHERE b.is_del=0")
sn2bt = {}
for sn, bt in cur.fetchall():
    if sn not in sn2bt:
        sn2bt[sn] = (bt or "")
conn.close()
print("  ADB belong_type map: %d 电池" % len(sn2bt), flush=True)

# 2) 补 battery_detail（按 sn 匹配）
bat = data.get("device", {}).get("battery_detail", [])
n_total = len(bat); n_hit = 0; dist = {}
for r in bat:
    sn = r.get("sn")
    bt = sn2bt.get(sn, "") if sn else ""
    r["belong_type"] = bt
    r["slot_warehouse"] = BELONG_TYPE_CN.get(bt, bt or "未识别")
    if bt:
        n_hit += 1
        dist[bt] = dist.get(bt, 0) + 1
print("  battery_detail: %d 条, 命中 belong_type %d 条, 缺失 %d 条" % (n_total, n_hit, n_total - n_hit), flush=True)
print("  分布:", dist, flush=True)

# 3) 落盘 region_monthly（护栏：避免后续 build_lite_data 因文件缺失而清空区域下钻）
rm = data.get("region_monthly")
if rm:
    json.dump(rm, open(RM_PATH, "w", encoding="utf-8"), ensure_ascii=False)
    print("  region_monthly 已落盘 %s (%d 城市)" % (RM_PATH, len(rm)), flush=True)
else:
    print("  ⚠️ lite 内无 region_monthly，跳过落盘", flush=True)

# 4) 写回 lite
t = time.time()
json.dump(data, open(LITE, "w", encoding="utf-8"), ensure_ascii=False)
print("  saved lite in %.1fs | %.1fMB" % (time.time() - t, os.path.getsize(LITE) / 1024 / 1024), flush=True)
print("DONE")
