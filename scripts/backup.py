#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
citybike_pro 数据库备份管道
- 全量快照(full): 导出业务核心表 -> data/full_snapshot/<date>/<table>.csv.gz
- 增量(incremental): 导出所有表"最新一天"数据 -> data/incremental/<date>/<table>.csv.gz
- 保留策略: 仅保留最新一份全量快照 + 仅保留最新一天的增量
时间戳为 13 位毫秒(ms)。
"""
import pymysql, os, gzip, csv, json, argparse, datetime, sys, shutil, threading
from concurrent.futures import ThreadPoolExecutor, as_completed

def _load_db():
    cfg_path = os.path.join(BASE, "config", "backup_config.json")
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path, encoding="utf-8") as f:
                c = json.load(f)
            return {
                "host": c["host"], "port": c.get("port", 3306),
                "user": c["user"], "password": c["password"],
                "database": c["database"], "connect_timeout": c.get("connect_timeout", 15),
                "read_timeout": c.get("read_timeout", 600), "charset": "utf8mb4",
            }
        except Exception:
            pass
    return {
        "host": "db.example.com",
        "port": 3306, "user": "citybike_pro", "password":"***",
        "database": "sharing-citybike-pro", "connect_timeout": 15, "read_timeout": 600,
        "charset": "utf8mb4",
    }

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = _load_db()
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")
SCHEMA = os.path.join(DATA, "schema_report.json")
FULL_DIR = os.path.join(DATA, "full_snapshot")
INC_DIR = os.path.join(DATA, "incremental")
CHUNK = 20000

# 巨型遥测/日志表(全量快照排除，但增量仍按天抓取)
GIANT_EXCLUDE = {
    "t_device_online_log", "t_queue_message", "t_bike_ride_log",
    "t_battery_circulate_log", "t_exchange_order_operation_log",
    "t_low_power_message_send_log", "t_banner_pv_log", "t_scan_log",
    "t_exchange_order_check_log", "t_exchange_order_success_message_send_log",
    "t_exchange_order_back_log", "t_user_exchange_package_use_log",
    "t_exchange_package_use_log", "t_user_score_earning_log",
    "t_exchange_standby_duration_statistics", "t_expense_bill",
    "t_monitor_ex_event_source",
}
SUFFIX_EXCLUDE = ("_statistics", "_message", "_pv", "_upload")
ROW_EXCLUDE_GE = 5_000_000  # 单行数 >= 500 万 也排除出全量


def log(msg):
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def load_tables(scope):
    with open(SCHEMA, encoding="utf-8") as f:
        rep = json.load(f)
    out = []
    for t, v in rep.items():
        if scope == "core":
            if t in GIANT_EXCLUDE:
                continue
            if t.lower().startswith("tmp_"):
                continue
            if any(t.lower().endswith(s) for s in SUFFIX_EXCLUDE):
                continue
            if v.get("rows", 0) >= ROW_EXCLUDE_GE:
                continue
        out.append((t, v.get("rows", 0), v.get("inc_col")))
    return out


def day_bounds(day_str):
    y, m, d = map(int, day_str.split("-"))
    a = datetime.datetime(y, m, d)
    b = a + datetime.timedelta(days=1)
    s_ms = int(a.timestamp() * 1000)
    e_ms = int(b.timestamp() * 1000)
    return s_ms, e_ms


def export_table_full(t, path):
    conn = pymysql.connect(**DB)
    try:
        cur = conn.cursor(pymysql.cursors.SSCursor)
        cur.execute(f"SELECT * FROM `{t}`")
        desc = cur.description
        cols = [c[0] for c in desc]
        n = 0
        with gzip.open(path, "wt", newline="", encoding="utf-8") as gz:
            w = csv.writer(gz)
            w.writerow(cols)
            while True:
                rows = cur.fetchmany(CHUNK)
                if not rows:
                    break
                w.writerows(rows)
                n += len(rows)
        return n
    finally:
        conn.close()


def export_table_inc(t, inc_col, s_ms, e_ms, path):
    if not inc_col:
        return None
    conn = pymysql.connect(**DB)
    try:
        cur = conn.cursor(pymysql.cursors.SSCursor)
        q = f"SELECT * FROM `{t}` WHERE `{inc_col}` >= %s AND `{inc_col}` < %s"
        cur.execute(q, (s_ms, e_ms))
        desc = cur.description
        cols = [c[0] for c in desc]
        n = 0
        with gzip.open(path, "wt", newline="", encoding="utf-8") as gz:
            w = csv.writer(gz)
            w.writerow(cols)
            while True:
                rows = cur.fetchmany(CHUNK)
                if not rows:
                    break
                w.writerows(rows)
                n += len(rows)
        return n
    finally:
        conn.close()


def run_full(scope, workers):
    tables = load_tables(scope)
    date = datetime.date.today().isoformat()
    out_dir = os.path.join(FULL_DIR, date)
    os.makedirs(out_dir, exist_ok=True)
    log(f"FULL scope={scope} tables={len(tables)} -> {out_dir}")
    mani = {"mode": "full", "scope": scope, "date": date,
            "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "tables": []}
    total = 0
    lock = threading.Lock()
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        fut = {ex.submit(export_table_full, t, os.path.join(out_dir, f"{t}.csv.gz")): t for t, _, _ in tables}
        for fu in as_completed(fut):
            t = fut[fu]
            done += 1
            try:
                n = fu.result()
                size = os.path.getsize(os.path.join(out_dir, f"{t}.csv.gz"))
                with lock:
                    mani["tables"].append({"table": t, "rows": n, "bytes": size,
                                           "file": f"{t}.csv.gz"})
                    total += n
                log(f"  [{done}/{len(tables)}] {t}: {n} rows")
            except Exception as e:
                log(f"  [{done}/{len(tables)}] {t}: ERROR {e}")
    mani["total_rows"] = total
    mani["table_count"] = len(mani["tables"])
    with open(os.path.join(out_dir, "MANIFEST.json"), "w", encoding="utf-8") as f:
        json.dump(mani, f, ensure_ascii=False, indent=2)
    log(f"FULL done: {total} rows, {len(mani['tables'])} tables. manifest saved.")
    return out_dir, mani


def run_incremental(day_str, scope, workers):
    if day_str == "auto":
        day = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    else:
        day = day_str
    s_ms, e_ms = day_bounds(day)
    tables = load_tables("all")  # 增量覆盖全部表
    out_dir = os.path.join(INC_DIR, day)
    os.makedirs(out_dir, exist_ok=True)
    log(f"INCREMENTAL day={day} tables={len(tables)} -> {out_dir}")
    mani = {"mode": "incremental", "day": day, "range_ms": [s_ms, e_ms],
            "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "tables": []}
    total = 0
    lock = threading.Lock()
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        fut = {}
        for t, _, inc in tables:
            p = os.path.join(out_dir, f"{t}.csv.gz")
            fut[ex.submit(export_table_inc, t, inc, s_ms, e_ms, p)] = (t, p)
        for fu in as_completed(fut):
            t, p = fut[fu]
            done += 1
            try:
                n = fu.result()
                if n is None:
                    continue
                if n == 0:
                    if os.path.exists(p):
                        os.remove(p)
                    continue
                size = os.path.getsize(p)
                with lock:
                    mani["tables"].append({"table": t, "rows": n, "bytes": size, "file": f"{t}.csv.gz"})
                    total += n
                log(f"  [{done}/{len(tables)}] {t}: {n} rows")
            except Exception as e:
                log(f"  [{done}/{len(tables)}] {t}: ERROR {e}")
    mani["total_rows"] = total
    mani["table_count"] = len(mani["tables"])
    with open(os.path.join(out_dir, "MANIFEST.json"), "w", encoding="utf-8") as f:
        json.dump(mani, f, ensure_ascii=False, indent=2)
    log(f"INCREMENTAL done: {total} rows, {len(mani['tables'])} tables with data.")
    return out_dir, mani


def prune(dir_root, keep):
    if not os.path.isdir(dir_root):
        return
    subs = sorted([d for d in os.listdir(dir_root) if os.path.isdir(os.path.join(dir_root, d))],
                 reverse=True)
    for old in subs[keep:]:
        p = os.path.join(dir_root, old)
        shutil.rmtree(p)
        log(f"PRUNE removed {p}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["full", "incremental"], required=True)
    ap.add_argument("--scope", choices=["core", "all"], default="core")
    ap.add_argument("--day", default="auto", help="incremental day YYYY-MM-DD or auto(=昨天)")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--keep-full", type=int, default=1, help="保留最新几份全量快照")
    ap.add_argument("--keep-inc", type=int, default=1, help="保留最新几天增量")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    if a.dry_run:
        tables = load_tables(a.scope if a.mode == "full" else "all")
        log(f"[DRY-RUN] mode={a.mode} tables={len(tables)}")
        for t, r, inc in tables[:20]:
            log(f"  {t} rows={r} inc={inc}")
        if len(tables) > 20:
            log(f"  ... +{len(tables)-20} more")
        return

    if a.mode == "full":
        run_full(a.scope, a.workers)
        prune(FULL_DIR, a.keep_full)
    else:
        run_incremental(a.day, a.scope, a.workers)
        prune(INC_DIR, a.keep_inc)
    log("ALL DONE")


if __name__ == "__main__":
    main()
