# -*- coding: utf-8 -*-
"""骑行轨迹抽取：t_bike_ride_log（全量 5182 万行，时间跨度约 2024-05 ~ 2026-07）。
产出 DATA.ride：
  sample    : 最近骑行样本（默认 3000 条，id 倒序≈时间倒序），含轨迹缩略图/起止/里程/时长/均速/SOC
  daily     : 近 120 天每日聚合（次数 + 里程）
  top_bike  : 近 30 天 里程 Top15 车辆
  top_user  : 近 30 天 次数 Top15 用户
  kpi       : 样本汇总指标
  total_all : 全量骑行记录数（COUNT，供 KPI 上下文）
  _note     : 口径说明
单位：distance=米(库内)，use_time=秒(库内)，ride_speed=km/h(库内)；展示端换算 km/min。
"""
import json, time, pymysql
BASE = r"D:/workboddy file/dudu分析/citybike_backup"
cfg = json.load(open(BASE + r"/config/backup_config.json", encoding="utf-8"))
conn = pymysql.connect(host=cfg["host"], port=cfg["port"], user=cfg["user"],
                       password=cfg["password"], database=cfg["database"],
                       connect_timeout=30, read_timeout=600, charset="utf8mb4")
cur = conn.cursor(pymysql.cursors.DictCursor)

NOW_MS = int(time.time() * 1000)
D120 = NOW_MS - 120 * 86400 * 1000
D30  = NOW_MS - 30 * 86400 * 1000
SAMPLE_N = 3000

def fmt_ts(ms):
    try:
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(ms / 1000.0))
    except Exception:
        return str(ms)

print("[1/5] 全量骑行记录数 ...")
cur.execute("SELECT COUNT(*) c FROM t_bike_ride_log WHERE is_del=0")
total_all = cur.fetchone()["c"]
print("    total_all:", total_all)

print("[2/5] 最近骑行样本 %d 条 ..." % SAMPLE_N)
cur.execute("""SELECT id, user_id, bike_id, device_sn, begin_time, end_time,
                    distance, use_time, use_power, ride_speed, trace_id, ride_data
             FROM t_bike_ride_log WHERE is_del=0
             ORDER BY id DESC LIMIT %s""", (SAMPLE_N,))
sample = []
for r in cur.fetchall():
    thumb, soc_b, soc_e, tr_speed = "", None, None, None
    rd = r.get("ride_data")
    if rd:
        try:
            o = json.loads(rd)
            thumb = o.get("traceThumb") or ""
            soc_b = o.get("traceSocBegin")
            soc_e = o.get("traceSocEnd")
            tr_speed = o.get("traceSpeed")
        except Exception:
            pass
    sample.append({
        "id": r["id"],
        "user_id": r["user_id"],
        "bike_id": r["bike_id"],
        "sn": r["device_sn"],
        "bt": fmt_ts(r["begin_time"]),
        "et": fmt_ts(r["end_time"]) if r["end_time"] else "",
        "dist_m": r["distance"] or 0,
        "use_s": r["use_time"] or 0,
        "power": r["use_power"] if r["use_power"] is not None else "",
        "speed": r["ride_speed"] if r["ride_speed"] is not None else "",
        "trace_id": r["trace_id"],
        "thumb": thumb,
        "soc_b": soc_b if soc_b is not None else "",
        "soc_e": soc_e if soc_e is not None else "",
    })
print("    sample rows:", len(sample))

print("[3/5] 近 120 天每日聚合 ...")
cur.execute("""SELECT DATE_FORMAT(FROM_UNIXTIME(begin_time DIV 1000),'%%Y-%%m-%%d') d,
                    COUNT(*) c, SUM(distance) sd, SUM(use_time) su
             FROM t_bike_ride_log WHERE is_del=0 AND begin_time>=%s
             GROUP BY d ORDER BY d""", (D120,))
daily = [{"date": r["d"], "cnt": r["c"], "dist_m": int(r["sd"] or 0), "use_s": int(r["su"] or 0)}
         for r in cur.fetchall()]
print("    daily days:", len(daily))

print("[4/5] 近 30 天 Top 车辆(里程) / Top 用户(次数) ...")
cur.execute("""SELECT bike_id, COUNT(*) rides, SUM(distance) sd
             FROM t_bike_ride_log WHERE is_del=0 AND begin_time>=%s
             GROUP BY bike_id ORDER BY sd DESC LIMIT 15""", (D30,))
top_bike = [{"bike_id": r["bike_id"], "rides": r["rides"], "dist_m": int(r["sd"] or 0)}
            for r in cur.fetchall()]
cur.execute("""SELECT user_id, COUNT(*) rides, SUM(distance) sd
             FROM t_bike_ride_log WHERE is_del=0 AND begin_time>=%s
             GROUP BY user_id ORDER BY rides DESC LIMIT 15""", (D30,))
top_user = [{"user_id": r["user_id"], "rides": r["rides"], "dist_m": int(r["sd"] or 0)}
            for r in cur.fetchall()]
print("    top_bike:", len(top_bike), "| top_user:", len(top_user))

conn.close()

# KPI 汇总（基于样本）
tot_dist = sum(x["dist_m"] for x in sample)
tot_use = sum(x["use_s"] for x in sample)
spds = [x["speed"] for x in sample if isinstance(x["speed"], (int, float))]
kpi = {
    "sample_n": len(sample),
    "total_dist_km": round(tot_dist / 1000.0, 1),
    "total_use_h": round(tot_use / 3600.0, 1),
    "avg_speed": round(sum(spds) / len(spds), 1) if spds else 0,
    "window_daily_days": len(daily),
    "window_top_days": 30,
}

note = ("来源 t_bike_ride_log（全量 %s 行，时间跨度约 2024-05 ~ 2026-07）。" % str(total_all) +
        "sample=最近 id 倒序 %d 条；daily=近 120 天每日聚合；top_bike/top_user=近 30 天排名。" % SAMPLE_N +
        "distance 库内单位米、use_time 秒、ride_speed km/h；展示端换算。轨迹缩略图来自 ride_data.traceThumb（OSS 远程图，需联网加载，离线降级为占位）。" +
        "注：ride_data 仅含轨迹元数据（起止/SOC/缩略图），精细 GPS 点在独立轨迹服务，未直连 ADB，故模块以「骑行记录+缩略图」呈现真实路径形状。")

R = {
    "sample": sample, "daily": daily, "top_bike": top_bike, "top_user": top_user,
    "kpi": kpi, "total_all": total_all, "_note": note,
}

dp = BASE + r"/data/dashboard_data.json"
data = json.load(open(dp, encoding="utf-8"))
data["ride"] = R
json.dump(data, open(dp, "w", encoding="utf-8"), ensure_ascii=False)
import os
print("WROTE DATA.ride ->", dp, "| bytes:", os.path.getsize(dp))
print("RIDE-DONE")
