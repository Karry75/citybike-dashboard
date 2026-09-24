# -*- coding: utf-8 -*-
import json, os, pymysql
cfg = json.load(open("config/backup_config.json", encoding="utf-8")); cfg.pop("workers", None)
conn = pymysql.connect(host=cfg["host"], port=cfg["port"], user=cfg["user"],
                       password=cfg["password"], database=cfg["database"],
                       connect_timeout=30, read_timeout=600, charset="utf8mb4")
cur = conn.cursor()
WH = "('operate_platform','agency_employee','site','distributor_maker')"
cur.execute("SELECT COUNT(*) FROM t_battery_transfer_log WHERE is_del=0 AND transfer_status IN ('wait_confirm','cancelled')")
pending_in = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM t_battery_transfer_log WHERE is_del=0 AND DATE(FROM_UNIXTIME(create_time/1000))=CURDATE() AND inflow_type IN " + WH)
today_in = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM t_battery_transfer_log WHERE is_del=0 AND DATE(FROM_UNIXTIME(create_time/1000))=CURDATE() AND outflow_type IN " + WH)
today_out = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM t_battery_transfer_log WHERE is_del=0 AND transfer_status='finished'")
finished = cur.fetchone()[0]
conn.close()
print("pending_in:", pending_in, "today_in:", today_in, "today_out:", today_out, "finished:", finished)
dp = "data/dashboard_data.json"
D = json.load(open(dp, encoding="utf-8"))
DEV = D.setdefault("device", {})
DEV["inventory"]["kpis"] = {"pending_in": pending_in, "today_in": today_in,
                            "today_out": today_out, "total": DEV.get("battery_total", 0)}
DEV["inventory"]["_note"] = "出入库明细来自 t_battery_transfer_log（电池流转 in/out）；待入=wait_confirm/cancelled，今日=毫秒时间戳换算；全量25.78万条"
json.dump(D, open(dp, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print("patched kpis -> bytes", os.path.getsize(dp))
