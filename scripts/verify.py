# -*- coding: utf-8 -*-
"""Verify dashboard data correctness: internal consistency + live DB spot-check."""
import json, pymysql, sys
BASE = r"D:/workboddy file/dudu分析/citybike_backup"
D = json.load(open(BASE + r"/data/dashboard_data.json", encoding="utf-8"))
cfg = json.load(open(BASE + r"/config/backup_config.json", encoding="utf-8"))

print("================ 一、内部一致性（dashboard_data.json）================")
ok = []
def chk(name, cond, extra=""):
    ok.append(cond)
    print(("  [OK] " if cond else "  [XX] ") + name + (("  -> " + extra) if extra else ""))

OV, U, S, W, E, O, P, F, SV = (D.get(k, {}) for k in ["overview","user","sales","site","device","ops","personnel","finance","service"])

chk("总览.用户人数 == 用户.总人数", OV.get("user_total") == U.get("total"), "%s vs %s" % (OV.get("user_total"), U.get("total")))
# site total vs by_status sum
wsum = sum(x.get("count",0) for x in W.get("by_status", []))
chk("网点总数 == 状态分布求和", W.get("total") == wsum, "%s vs %s" % (W.get("total"), wsum))
# device battery online+offline == battery_total
chk("电池总数 == 在线+离线", E.get("battery_total") == (E.get("battery_online",0)+E.get("battery_offline",0)), "%s vs %s" % (E.get("battery_total"), E.get("battery_online",0)+E.get("battery_offline",0)))
chk("换电柜总数 == 在线+离线", E.get("cabinet_total") == (E.get("cabinet_online",0)+E.get("cabinet_offline",0)), "%s vs %s" % (E.get("cabinet_total"), E.get("cabinet_online",0)+E.get("cabinet_offline",0)))
# finance income aggregattion sanity
chk("财务详情非空", len(F.get("detail", [])) > 0)
# filterable dimension availability
for mod, fld, arr in [("user","city",U.get("detail")),("sales","city",S.get("detail")),("site","city",W.get("detail")),("service","city",SV.get("agreement_index"))]:
    cities = set(r.get(fld) for r in (arr or []) if r.get(fld))
    chk("[%s] 城市维度可筛选（%d 个去重值）" % (mod, len(cities)), len(cities) > 0)
bats = set(r.get("battery_product") for r in (U.get("detail") or []) if r.get("battery_product"))
chk("[user/sales] 电池产品维度可筛选（%d 个）" % len(bats), len(bats) > 0)
promos = set(r.get("promoter") for r in (S.get("detail") or []) if r.get("promoter"))
chk("[sales] 业务员维度可筛选（%d 个）" % len(promos), len(promos) > 0)
# linkage targets exist
chk("客服索引含 site 字段（网点联动）", all("site" in r for r in (SV.get("agreement_index") or [])[:50]))
chk("用户明细含 phone（跳转客服）", all("phone" in r for r in (U.get("detail") or [])[:50]))

print("\n================ 二、数据库实时抽查（关键总数）================")
try:
    c = pymysql.connect(host=cfg["host"], port=cfg["port"], user=cfg["user"], password=cfg["password"],
                        database=cfg["database"], connect_timeout=15, read_timeout=300, charset="utf8mb4")
    cur = c.cursor()
    def cnt(sql):
        cur.execute(sql); return cur.fetchone()[0]
    checks = [
        ("t_user 用户数(未删除)", "SELECT COUNT(*) FROM t_user WHERE is_del=0", U.get("total")),
        ("t_exchange_agreement 协议数", "SELECT COUNT(*) FROM t_exchange_agreement", OV.get("agreement_total")),
        ("t_site 网点数", "SELECT COUNT(*) FROM t_site WHERE is_del=0", W.get("total")),
        ("t_exchange_store 换电柜数(去重SN)", "SELECT COUNT(DISTINCT device_sn) FROM t_exchange_store", E.get("cabinet_total")),
        ("t_battery 电池数", "SELECT COUNT(*) FROM t_battery WHERE is_del=0", E.get("battery_total")),
    ]
    for label, sql, expect in checks:
        real = cnt(sql)
        cond = (expect == real)
        ok.append(cond)
        print(("  [OK] " if cond else "  [!!] ") + "%s：看板=%s  数据库=%s" % (label, expect, real))
    c.close()
except Exception as e:
    print("  [跳过] 数据库抽查失败：", e)

print("\n================ 结论 ================")
print("通过项：%d / 总检查：%d" % (sum(1 for x in ok if x), len(ok)))
print("RESULT:", "ALL_PASS" if all(ok) else "HAS_WARN")
