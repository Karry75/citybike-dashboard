# -*- coding: utf-8 -*-
"""仅抽取工单维度(t_work_order)并合并进现有 data/dashboard_data.json。
避免重跑整条抽取流水线；金额/时间为分/毫秒转标准单位，全程可追溯。"""
import json, pymysql, time, datetime

BASE = r"D:/workboddy file/dudu分析/citybike_backup"
DB = json.load(open(BASE + r"/config/backup_config.json", encoding="utf-8"))
DB.pop("workers", None)
OUT = BASE + r"/data/dashboard_data.json"
DETAIL_CAP = 5000
NOW = int(time.time() * 1000)

def ms2str(v):
    if not v:
        return ""
    try:
        return (datetime.datetime.utcfromtimestamp(int(v) / 1000) + datetime.timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(v)

conn = pymysql.connect(host=DB["host"], port=DB["port"], user=DB["user"], password=DB["password"],
                       database=DB["database"], connect_timeout=15, read_timeout=600, charset="utf8mb4")
cur = conn.cursor()
CUT30 = NOW - 30 * 86400000

def q(sql, many=False):
    cur.execute(sql)
    return cur.fetchall() if many else (cur.fetchone()[0] if cur.rowcount else None)

wo = {}
wo["total"] = q("SELECT COUNT(*) FROM t_work_order WHERE is_del=0")
wo["by_status"] = [{"status": r[0], "count": r[1]} for r in q(
    "SELECT status, COUNT(*) c FROM t_work_order WHERE is_del=0 GROUP BY status ORDER BY c DESC", many=True) or []]
# 优先级归一：源数据 normal 与中文'一般'并存（数据质量问题），统一为'一般'；urgent→紧急、notUrgent→不紧急
PRI_MAP = {'normal': '一般', '一般': '一般', 'urgent': '紧急', 'notUrgent': '不紧急'}
wo["by_priority"] = [{"priority": PRI_MAP.get(r[0], r[0] or "未知"), "count": r[1]} for r in q(
    "SELECT CASE WHEN priority IN ('normal','一般') THEN '一般' WHEN priority='urgent' THEN '紧急' "
    "WHEN priority='notUrgent' THEN '不紧急' ELSE priority END pr, COUNT(*) c "
    "FROM t_work_order WHERE is_del=0 GROUP BY pr ORDER BY c DESC", many=True) or []]
wo["overdue"] = q("SELECT COUNT(*) FROM t_work_order WHERE is_del=0 AND is_overdue=1")
wo["by_city"] = [{"city": r[0], "count": r[1], "overdue": r[2]} for r in q(
    "SELECT city, COUNT(*) c, SUM(is_overdue) od FROM t_work_order WHERE is_del=0 AND city IS NOT NULL AND city<>'' "
    "GROUP BY city ORDER BY c DESC LIMIT 20", many=True) or []]
wo["by_event"] = [{"event_type": r[0], "event_name": r[1], "count": r[2]} for r in q(
    "SELECT event_type, event_name, COUNT(*) c FROM t_work_order WHERE is_del=0 "
    "GROUP BY event_type, event_name ORDER BY c DESC LIMIT 20", many=True) or []]
wo["trend_created"] = [{"date": r[0], "count": r[1]} for r in q(
    "SELECT FROM_UNIXTIME(create_time/1000,'%%Y-%%m-%%d') d, COUNT(*) c FROM t_work_order "
    "WHERE is_del=0 AND create_time>=%d GROUP BY d ORDER BY d" % CUT30, many=True) or []]
wo["trend_completed"] = [{"date": r[0], "count": r[1]} for r in q(
    "SELECT FROM_UNIXTIME(handle_stop_time/1000,'%%Y-%%m-%%d') d, COUNT(*) c FROM t_work_order "
    "WHERE is_del=0 AND handle_stop_time>=%d AND status='completed' GROUP BY d ORDER BY d" % CUT30, many=True) or []]
rows = q(
    "SELECT id, event_name, priority, status, is_overdue, city, agency_name, handler_name, create_time "
    "FROM t_work_order WHERE is_del=0 ORDER BY create_time DESC LIMIT %d" % DETAIL_CAP, many=True) or []
wo["list"] = [{"id": r[0], "event_name": r[1], "priority": PRI_MAP.get(r[2], r[2] or "未知"), "status": r[3],
    "is_overdue": r[4], "city": r[5], "agency": r[6], "handler": r[7], "create": ms2str(r[8])} for r in rows]

data = json.load(open(OUT, encoding="utf-8"))
if "ops" not in data:
    data["ops"] = {}
data["ops"]["work_order"] = wo
data["ops"]["work_order_total"] = wo["total"]
json.dump(data, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
print("OK total=%s status=%d city=%d event=%d list=%d trend_c=%d trend_cp=%d overdue=%s" % (
    wo["total"], len(wo["by_status"]), len(wo["by_city"]), len(wo["by_event"]), len(wo["list"]),
    len(wo["trend_created"]), len(wo["trend_completed"]), wo["overdue"]))
print("by_status:", wo["by_status"])
print("by_priority:", wo["by_priority"])
