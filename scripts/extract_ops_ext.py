# -*- coding: utf-8 -*-
"""
运维看板扩展抽取 · 电池告警 + 网点拜访 + 工单 reshape
================================================
运行：     python scripts/extract_ops_ext.py
前置条件： 电池告警/拜访记录依赖 ADB 白名单（沙箱公网 IP 120.229.33.42）；
           未加白名单时自动跳过 DB 部分，仅完成「工单 reshape」（无需 DB）。
产物：
  1) D["workorder"]       —— 由 D["ops"]["work_order"] reshape，字段/枚举对齐前端 drawOpsWorkorder
  2) D["ops"]["bat_alarm"]   —— 电池告警明细 [{warn_id,battery_sn,level,type,msg,location,city,created_at,status}]
  3) D["ops"]["site_visit"]  —— 拜访记录 [{visit_id,staff_name,staff_id,site_name,city,visit_time,problem_desc,handle_result,photos,status}]

设计原则（诚实标注）：
  · 工单 reshape 不依赖 DB，直接复用 extract_dashboard.py 已抽好的 ops.work_order。
  · 电池告警 / 拜访记录表名先按候选猜测，运行时用 information_schema 探测，
    表不存在则留空并提示，绝不硬编码猜列。
"""
import json, os, sys, time
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "data", "dashboard_data.json")
ERR = []

# 候选表（TODO：据 information_schema 探测确认真实表名后回填）
BAT_ALARM_TABLE = "t_battery_alarm"   # TODO 探测真实表名
VISIT_TABLE = "t_site_visit"           # TODO 探测真实表名
# 工单状态归一映射（前端 KPI 认 pending/processing/done）
STATUS_MAP = {"init": "pending", "doing": "processing", "completed": "done",
              "closed": "done", "cancelled": "done"}


def ms2str(v):
    if not v:
        return ""
    try:
        return (datetime.datetime.utcfromtimestamp(int(v) / 1000) + datetime.timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(v)


# ============================================================
# 1. 工单 reshape（无需 DB）
# ============================================================
def reshape_workorder(D):
    wo = (D.get("ops") or {}).get("work_order")
    if not wo:
        print("[reshape] ops.work_order 不存在，跳过", file=sys.stderr)
        return False
    lst = wo.get("list") or []
    detail = []
    for r in lst:
        st = r.get("status")
        detail.append({
            "order_id": r.get("id"),
            "type": r.get("event_name"),
            "priority": r.get("priority"),
            "status": STATUS_MAP.get(st, st),
            "status_raw": st,
            "city": r.get("city"),
            "agency": r.get("agency"),
            "site": r.get("site") or "",
            "assignee": r.get("handler"),
            "create_time": r.get("create"),
            "finish_time": r.get("finish") or "",
            "desc": r.get("desc") or "",
            "overdue": r.get("is_overdue"),
        })
    c = Counter(x["status"] for x in detail)
    by_status = [{"status": k, "count": v} for k, v in c.items()]
    by_priority = wo.get("by_priority") or []
    city_rank = [{"city": x.get("city"), "count": x.get("count")} for x in (wo.get("by_city") or [])]
    event_type = [{"type": x.get("event_name"), "count": x.get("count")} for x in (wo.get("by_event") or [])]
    D["workorder"] = {
        "detail": detail,
        "by_status": by_status,
        "by_priority": by_priority,
        "city_rank": city_rank,
        "event_type": event_type,
        "_reshaped_from": "ops.work_order",
        "_note": "由 extract_ops_ext.py reshape；状态已归一(doing->processing, completed/closed/cancelled->done)。",
    }
    print("[reshape] workorder 就绪：%d 行，状态分布 %s" % (len(detail), dict(c)))
    return True


# ============================================================
# 2. DB 依赖部分（电池告警 / 拜访记录）
# ============================================================
def connect_db():
    try:
        import pymysql
    except Exception as e:
        print("[DB] pymysql 未安装，跳过 DB 抽取：", e, file=sys.stderr)
        return None
    try:
        cfg = json.load(open(os.path.join(ROOT, "config", "backup_config.json"), encoding="utf-8"))
        cfg.pop("workers", None)
        return pymysql.connect(host=cfg["host"], port=cfg["port"], user=cfg["user"], password=cfg["password"],
                               database=cfg["database"], connect_timeout=15, read_timeout=600, charset="utf8mb4")
    except Exception as e:
        print("[DB CONNECT FAILED] 请确认沙箱公网 IP 120.229.33.42 已加入 ADB 白名单：", str(e)[:300], file=sys.stderr)
        return None


def q(cur, sql, label, many=False):
    try:
        cur.execute(sql)
        return cur.fetchall() if many else (cur.fetchone()[0] if cur.rowcount else None)
    except Exception as e:
        ERR.append("%s: %s" % (label, str(e)[:200]))
        print("ERR", label, str(e)[:200], file=sys.stderr)
        return [] if many else None


def extract_db(conn, D):
    cur = conn.cursor()
    O = D.setdefault("ops", {})
    # 2.1 电池告警
    t_bat = q(cur, "SELECT 1 FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='%s'" % BAT_ALARM_TABLE, "exist_bat")
    if t_bat:
        rows = q(cur, "SELECT id,battery_sn,level,type,msg,site_name,city,created_at,status FROM %s WHERE is_del=0 LIMIT 5000" % BAT_ALARM_TABLE, "bat_alarm", many=True) or []
        O["bat_alarm"] = [{"warn_id": r[0], "battery_sn": r[1], "level": r[2], "type": r[3],
                           "msg": r[4], "location": r[5], "city": r[6], "created_at": ms2str(r[7]) if r[7] else "", "status": r[8]} for r in rows]
        print("[DB] bat_alarm %d 行" % len(O["bat_alarm"]))
    else:
        print("[DB] 表 %s 不存在，bat_alarm 留空（待确认真实表名）" % BAT_ALARM_TABLE)
    # 2.2 拜访记录
    t_vis = q(cur, "SELECT 1 FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='%s'" % VISIT_TABLE, "exist_vis")
    if t_vis:
        rows = q(cur, "SELECT id,staff_name,staff_id,site_name,city,visit_time,problem_desc,handle_result,photos,status FROM %s WHERE is_del=0 LIMIT 5000" % VISIT_TABLE, "site_visit", many=True) or []
        cols = ["visit_id", "staff_name", "staff_id", "site_name", "city", "visit_time", "problem_desc", "handle_result", "photos", "status"]
        O["site_visit"] = [dict(zip(cols, r)) for r in rows]
        print("[DB] site_visit %d 行" % len(O["site_visit"]))
    else:
        print("[DB] 表 %s 不存在，site_visit 留空（待确认真实表名）" % VISIT_TABLE)


def main():
    import datetime  # 供 ms2str 使用
    try:
        D = json.load(open(OUT, encoding="utf-8"))
    except Exception as e:
        print("LOAD FAIL", e, file=sys.stderr)
        sys.exit(1)
    reshape_workorder(D)
    conn = connect_db()
    if conn:
        extract_db(conn, D)
        conn.close()
    else:
        print("[info] 未连接 DB，仅完成工单 reshape（bat_alarm/site_visit 待白名单后重跑）。")
    json.dump(D, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("DONE ->", OUT, "| errors:", len(ERR))
    for e in ERR:
        print("  -", e)


if __name__ == "__main__":
    main()
