# -*- coding: utf-8 -*-
"""抽取地图与筛选级联所需地理维度：
  geo.site_coords  : t_site 真实经纬度 + 城市/区域/街道/社区/状态/类型（换电真实气泡）
  geo.user_city_area : t_user GROUP BY city,area（用户分布钻取 城市->区域）
  geo.exch_city_area_street : t_exchange_order 近60天 GROUP BY 市/区/街（换电钻取 城市->区域->街道）
  geo.user_areas / site_areas / site_streets / site_communities : 级联下拉去重维度
金额单位：库内"分"，本脚本不涉及金额。
"""
import json, time, pymysql
BASE = r"D:/workboddy file/dudu分析/citybike_backup"
cfg = json.load(open(BASE + r"/config/backup_config.json", encoding="utf-8"))
conn = pymysql.connect(host=cfg["host"], port=cfg["port"], user=cfg["user"],
                     password=cfg["password"], database=cfg["database"],
                     connect_timeout=30, charset="utf8mb4")
cur = conn.cursor()
D60 = int(time.time() * 1000) - 60 * 86400 * 1000

G = {}
# 1) 网点真实经纬度（换电气泡）
print("[1/6] t_site 经纬度 ...")
cur.execute("""SELECT id, name, city, area, street, community, longitude, latitude
               FROM t_site WHERE is_del=0 AND longitude IS NOT NULL AND latitude IS NOT NULL""")
site_coords = []
for r in cur.fetchall():
    try:
        lng, lat = float(r[6]), float(r[7])
    except Exception:
        continue
    site_coords.append({"id": r[0], "name": r[1], "city": r[2] or "", "area": r[3] or "",
                       "street": r[4] or "", "community": r[5] or "",
                       "lng": lng, "lat": lat})
G["site_coords"] = site_coords
print("   站点数(含坐标):", len(site_coords))

# 2) 用户 城市->区域 聚合
print("[2/6] t_user GROUP BY city,area ...")
cur.execute("""SELECT city, area, COUNT(*) c FROM t_user
               WHERE is_del=0 AND city IS NOT NULL AND city<>'' GROUP BY city, area""")
ua = {}
for city, area, c in cur.fetchall():
    ua.setdefault(city, []).append({"area": area or "未知区域", "count": c})
G["user_city_area"] = [{"city": k, "areas": v} for k, v in ua.items()]
print("   覆盖城市:", len(ua))

# 3) 换电 城市->区域->街道 聚合（近60天抽样，标注非全量）
print("[3/6] t_exchange_order 近60天 GROUP BY 市/区/街 ...")
cur.execute("""SELECT site_city, site_area, site_street, COUNT(*) c
               FROM t_exchange_order WHERE is_del=0 AND create_time>%s
               AND site_city IS NOT NULL AND site_city<>''
               GROUP BY site_city, site_area, site_street LIMIT 200000""", (D60,))
ec = {}
for city, area, street, c in cur.fetchall():
    ec.setdefault(city, {}).setdefault(area or "未知区域", []).append({"street": street or "未知街道", "count": c})
G["exch_city_area_street"] = [{"city": k, "areas": [{"area": a, "streets": s} for a, s in v.items()]} for k, v in ec.items()]
print("   覆盖城市:", len(ec))

# 4) 级联下拉去重维度
print("[4/6] 级联维度去重 ...")
cur.execute("SELECT DISTINCT area FROM t_user WHERE is_del=0 AND area IS NOT NULL AND area<>''")
G["user_areas"] = sorted({r[0] for r in cur.fetchall()})
cur.execute("SELECT DISTINCT area FROM t_site WHERE is_del=0 AND area IS NOT NULL AND area<>''")
G["site_areas"] = sorted({r[0] for r in cur.fetchall()})
cur.execute("SELECT DISTINCT street FROM t_site WHERE is_del=0 AND street IS NOT NULL AND street<>''")
G["site_streets"] = sorted({r[0] for r in cur.fetchall()})
cur.execute("SELECT DISTINCT community FROM t_site WHERE is_del=0 AND community IS NOT NULL AND community<>''")
G["site_communities"] = sorted({r[0] for r in cur.fetchall()})
print("   user_areas:", len(G["user_areas"]), "| site_areas:", len(G["site_areas"]),
      "| site_streets:", len(G["site_streets"]), "| site_communities:", len(G["site_communities"]))

conn.close()

# 合并写入 dashboard_data.json（不破坏现有键）
import os
dp = os.path.join(BASE, "data/dashboard_data.json")
data = json.load(open(dp, encoding="utf-8"))
data["geo"] = G
json.dump(data, open(dp, "w", encoding="utf-8"), ensure_ascii=False)
print("WROTE geo dims ->", dp, "| total bytes:", os.path.getsize(dp))
