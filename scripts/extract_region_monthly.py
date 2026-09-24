#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extract_region_monthly.py — 抽取「城市 × 区 × 月」三指标序列，供看板月度趋势下钻使用。

产出 data/region_monthly.json：
{
  "深圳市": {
    "months": ["2024-09", ..., "2026-08"],
    "areas": { "宝安区": {"swap":[...], "users":[...], "revenue":[...]}, ... },
    "total": {"swap":[...], "users":[...], "revenue":[...]}
  },
  ...
}

口径：
  - 换电量(swap)     = t_exchange_order 成功单(order_status='success') COUNT(*)
  - 活跃用户(users)  = 同组内 COUNT(DISTINCT take_user_id)
  - 分成收入(revenue)= SUM(profit_fee)/100（profit_fee 单位为分）
  - 月份            = DATE_FORMAT(create_time,'%Y-%m')
  - 城市键名        = 去省前缀后的短名（"广东省深圳市"→"深圳市"），与前端选择器一致

依赖：pymysql + config/backup_config.json（库密码必须已填入，且阿里云 ADB 白名单已放行本机出口 IP）。
前置：ADB 当前(2026-08)从本环境连不通，需先：
  ① 阿里云 ADB 白名单加 120.229.33.0/24
  ② 把真实 DB 密码填入 config/backup_config.json（勿进聊天）
然后：python extract_region_monthly.py  →  python build_lite_data.py  →  构建看板。
"""
import json, os, re, sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = os.path.join(BASE, "config", "backup_config.json")
OUT = os.path.join(BASE, "data", "region_monthly.json")
PLACE = "YOUR_DB_PASSWORD_HERE"

def short_city(c):
    if not c:
        return c
    return re.sub(r"^(.+省|北京市|天津市|上海市|重庆市)", "", str(c)).strip()

def main():
    assert os.path.exists(CFG), "缺少 config/backup_config.json"
    cfg = json.load(open(CFG, encoding="utf-8"))
    pw = cfg.get("password", "")
    if not pw or pw == PLACE:
        sys.exit("⛔ 库密码未配置：请先把真实密码填入 %s 的 password 字段（当前为占位符）" % CFG)
    try:
        import pymysql
    except ImportError:
        sys.exit("⛔ 缺少 pymysql：先 pip install pymysql")

    conn = pymysql.connect(
        host=cfg["host"], port=int(cfg.get("port", 3306)),
        user=cfg["user"], password=pw, database=cfg.get("database", ""),
        charset=cfg.get("charset", "utf8mb4"),
        connect_timeout=int(cfg.get("connect_timeout", 15)),
        read_timeout=int(cfg.get("read_timeout", 120)),
        cursorclass=pymysql.cursors.Cursor,
    )
    print("[ok] 已连接 ADB:", cfg["host"])

    cur = conn.cursor()
    # 防御：先探一列，确认 order_status / take_user_id / profit_fee 存在
    cur.execute("SHOW COLUMNS FROM t_exchange_order")
    cols = {r[0] for r in cur.fetchall()}
    need = {"site_city", "site_area", "create_time", "order_status", "take_user_id", "profit_fee"}
    miss = need - cols
    if miss:
        sys.exit("⛔ t_exchange_order 缺列: %s（实际列：%s）" % (miss, sorted(cols)))

    MONTHS_BACK = 24
    SQL = (
        "SELECT site_city, site_area, DATE_FORMAT(create_time,'%%Y-%%m') ym, "
        "       COUNT(*) swap, "
        "       COUNT(DISTINCT take_user_id) au, "
        "       COALESCE(SUM(profit_fee),0)/100.0 revenue "
        "FROM t_exchange_order "
        "WHERE order_status='success' AND site_city IS NOT NULL AND site_city<>'' "
        "GROUP BY site_city, site_area, ym"
    )
    print("[run] 抽取城市×区×月 ...")
    cur.execute(SQL)
    rows = cur.fetchall()
    conn.close()
    print("  原始分组行数:", len(rows))

    # 聚合：city -> area -> month -> metrics
    city_area = {}
    all_months = set()
    for city, area, ym, swap, au, revenue in rows:
        sc = short_city(city)
        a = area or "未知区域"
        all_months.add(ym)
        city_area.setdefault(sc, {}).setdefault(a, {})
        city_area[sc][a][ym] = {
            "swap": int(swap or 0),
            "users": int(au or 0),
            "revenue": round(float(revenue or 0), 2),
        }

    # 取全局最近 MONTHS_BACK 个月
    months = sorted(all_months)[-MONTHS_BACK:]
    mset = set(months)

    out = {}
    for sc, areas in city_area.items():
        out[sc] = {"months": months, "areas": {}, "total": {}}
        for m in months:
            out[sc]["total"].setdefault("swap", []).append(0)
            out[sc]["total"].setdefault("users", []).append(0)
            out[sc]["total"].setdefault("revenue", []).append(0)
        for a, mm in areas.items():
            out[sc]["areas"][a] = {"swap": [], "users": [], "revenue": []}
            for i, m in enumerate(months):
                rec = mm.get(m)
                if rec:
                    out[sc]["areas"][a]["swap"].append(rec["swap"])
                    out[sc]["areas"][a]["users"].append(rec["users"])
                    out[sc]["areas"][a]["revenue"].append(rec["revenue"])
                    out[sc]["total"]["swap"][i] += rec["swap"]
                    out[sc]["total"]["users"][i] += rec["users"]
                    out[sc]["total"]["revenue"][i] += rec["revenue"]
                else:
                    out[sc]["areas"][a]["swap"].append(0)
                    out[sc]["areas"][a]["users"].append(0)
                    out[sc]["areas"][a]["revenue"].append(0)

    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    print("✔ 写出 %s" % OUT)
    print("  覆盖城市数:", len(out))
    for sc in list(out.keys())[:8]:
        print("   - %s: %d 个区, %d 个月" % (sc, len(out[sc]["areas"]), len(out[sc]["months"])))

if __name__ == "__main__":
    main()
