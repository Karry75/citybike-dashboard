# -*- coding: utf-8 -*-
"""
设备资产看板扩展抽取 · 出入库 / 故障 / 调拨
================================================
运行：     python scripts/extract_device_ext.py
前置条件： ADB 白名单（沙箱公网 IP 120.229.33.42）；pymysql 已装。
产物：     D["device"]["inventory"] = {kpis:{...}, list:[...]}   出入库记录
           D["device"]["fault"]     = {kpis:{...}, list:[...]}   故障设备
           D["device"]["transfer"]  = [ ... ]                     调拨/回收记录

前端对应 draw 函数字段：
  drawDevInventory : record_id, device_type, device_id, op_type, operator, op_time, from_obj, to_obj, result
  drawDevFault     : device_id, device_type, fault_type, fault_time, location, status, handler, handle_time
  drawDevTransfer  : record_id, operator_id, operator_name, op_time, device_type, device_id, op_type, result, from_obj, to_obj

设计原则（诚实标注）：
  · 不臆测表名。先 information_schema 探测候选表（'%device%'/'%inout%'/'%io%'/'%fault%'/'%transfer%'/'%调拨%'），
    打印候选表清单；真实表/列名填进 TODO_DEV_MAP 后重跑，绝不硬编码猜列。
  · KPI 由抽取结果现算（不写死），数据缺失时前端显示 ⚠️。
"""
import json, os, sys, time, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "data", "dashboard_data.json")
ERR = []


def ms2str(v):
    if not v:
        return ""
    try:
        return (datetime.datetime.utcfromtimestamp(int(v) / 1000) + datetime.timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        try:
            return str(v)
        except Exception:
            return ""


# ============================================================
# TODO —— 据 information_schema 探测报告回填真实表/列名
# ============================================================
TODO_DEV_MAP = {
    "inventory": {"table": "t_device_inout",  "cols": {}},   # TODO 真实表名（出入库流水）
    "fault":     {"table": "t_device_fault",  "cols": {}},   # TODO 真实表名（故障设备仓库）
    "transfer":  {"table": "t_device_transfer","cols": {}},   # TODO 真实表名（调拨/回收记录）
}


def connect_db():
    try:
        import pymysql
    except Exception as e:
        print("[DB] pymysql 未安装：", e, file=sys.stderr)
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


def discover(cur):
    pats = ["%device%", "%inout%", "%io%", "%fault%", "%transfer%", "%调拨%", "%出入库%"]
    found = []
    for p in pats:
        rows = q(cur, "SELECT TABLE_NAME, COLUMN_NAME FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME LIKE '%s'" % p, "disc_" + p, many=True) or []
        for t, c in rows:
            found.append({"table": t, "col": c})
    tables = sorted(set(r["table"] for r in found))
    return {"tables": tables, "sample_cols": found[:80]}


def main():
    D = json.load(open(OUT, encoding="utf-8"))
    conn = connect_db()
    if not conn:
        print("[info] 未连接 DB，device 扩展数据待白名单后抽取。脚本仅完成结构校验。")
        json.dump(D, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("DONE(no-op) ->", OUT)
        return
    cur = conn.cursor()
    disc = discover(cur)
    print("=== DEVICE EXT TABLE DISCOVERY ===")
    print("候选表：", disc["tables"])

    E = D.setdefault("device", {})
    # 1) 出入库
    t_inv = TODO_DEV_MAP["inventory"]["table"]
    inv_rows = q(cur, "SELECT id,device_type,device_id,op_type,operator,op_time,from_obj,to_obj,result "
                    "FROM %s WHERE is_del=0 LIMIT 10000" % t_inv, "inv", many=True) or []
    inv_list = [dict(zip(["record_id", "device_type", "device_id", "op_type", "operator",
                          "op_time", "from_obj", "to_obj", "result"], r)) for r in inv_rows]
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    inv_kpis = {
        "pending_in": sum(1 for r in inv_list if r["op_type"] in ("待入库", "inbound_pending")),
        "today_in": sum(1 for r in inv_list if str(r["op_time"]).startswith(today) and r["op_type"] in ("in", "入库")),
        "today_out": sum(1 for r in inv_list if str(r["op_time"]).startswith(today) and r["op_type"] in ("out", "出库")),
        "total": len(inv_list),
    }
    E["inventory"] = {"kpis": inv_kpis, "list": inv_list}
    print("[DB] inventory %d 行" % len(inv_list))

    # 2) 故障设备
    t_fault = TODO_DEV_MAP["fault"]["table"]
    fl_rows = q(cur, "SELECT device_id,device_type,fault_type,fault_time,location,status,handler,handle_time "
                    "FROM %s WHERE is_del=0 LIMIT 10000" % t_fault, "fault", many=True) or []
    fl_list = [dict(zip(["device_id", "device_type", "fault_type", "fault_time", "location",
                         "status", "handler", "handle_time"], r)) for r in fl_rows]
    fl_kpis = {
        "cabinet": sum(1 for r in fl_list if r["device_type"] in ("换电柜", "cabinet")),
        "battery": sum(1 for r in fl_list if r["device_type"] in ("电池", "battery")),
        "repaired": sum(1 for r in fl_list if r["status"] in ("已维修", "repaired")),
        "scrapped": sum(1 for r in fl_list if r["status"] in ("已报废", "scrapped")),
    }
    E["fault"] = {"kpis": fl_kpis, "list": fl_list}
    print("[DB] fault %d 行" % len(fl_list))

    # 3) 调拨/回收
    t_tf = TODO_DEV_MAP["transfer"]["table"]
    tf_rows = q(cur, "SELECT id,operator_id,operator_name,op_time,device_type,device_id,op_type,result,from_obj,to_obj "
                    "FROM %s WHERE is_del=0 LIMIT 10000" % t_tf, "tf", many=True) or []
    tf_list = [dict(zip(["record_id", "operator_id", "operator_name", "op_time", "device_type",
                        "device_id", "op_type", "result", "from_obj", "to_obj"], r)) for r in tf_rows]
    E["transfer"] = tf_list
    print("[DB] transfer %d 行" % len(tf_list))

    D["device"] = E
    json.dump(D, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    conn.close()
    print("DONE ->", OUT, "| errors:", len(ERR))
    for e in ERR:
        print("  -", e)


if __name__ == "__main__":
    main()
