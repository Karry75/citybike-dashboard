# -*- coding: utf-8 -*-
"""
网点看板扩展抽取 · 中间状态(9类) + 各角色手机号
================================================
前置条件：ADB 实例需把沙箱公网 IP 120.229.33.42 加入白名单
          （否则 pymysql 连库超时 2003，这是已知前置，非脚本问题）。
运行：     python scripts/extract_site_ext.py
产物：     合并进 data/dashboard_data.json
           1) D["site"]["status_9"]      —— 9 类网点状态真值（有序 [{label,count}]）
           2) D["site"]["detail"][i]     —— 追加 merchant_phone / distributor_phone /
                                            agency_phone / business_phone 四个字段
           3) D["site_ext"]              —— schema 探测报告 + 抽取状态（供核对/排错）

设计原则（诚实标注）：
  · 不臆测字段名。先 information_schema 探测「手机号列」「状态类列」「候选表是否存在」，
    再按真实列名抽取；任何拿不准的映射都落进 site_ext._discovery，绝不硬编码猜列。
  · 单查询失败不影响其余（统一走 q()，自动记入 ERR）。
  · 中间态枚举（待安装/待送货/待验收/待开业/待审批/未合作）需据探测到的真实取值回填
    INTERMEDIATE_MAP 后重跑，否则记 0 并在 status_9_note 说明。

------------------------------------------------------------
【折叠进 extract_dashboard.py 的正式 SQL 骨架（上线用，本脚本仅为扩展/快速探测）】
下列 JOIN 应并进 extract_dashboard.py 的「网点明细」查询（当前 line 228-237），
避免主抽取覆盖本脚本写入的 phone 字段：

  -- 1) w_detail SELECT 末尾追加（需先确认探测到的真实 phone 列名）：
  , m.phone   AS merchant_phone
  , d.phone   AS distributor_phone
  , a.phone   AS agency_phone
  , p.phone   AS business_phone
  -- 2) FROM/JOIN 追加（以 t_merchant / t_distributor / t_agency / t_promoter 真实存在为前提）：
  LEFT JOIN t_merchant    m ON s.merchant_id   = m.id
  LEFT JOIN t_distributor d ON s.distributor_id = d.id
  LEFT JOIN t_agency      a ON s.agency_id      = a.id
  LEFT JOIN t_promoter    p ON s.business_name  = p.name   -- 业务员按姓名关联（主表未抽 business_id）
  -- 3) 9 态计数（替代原仅 on/off 的 w_status）：
  --    先 SELECT DISTINCT <状态列> FROM t_site 探明中间态藏在哪列、哪些取值，再：
  SELECT
    SUM(CASE WHEN site_status='on'  THEN 1 ELSE 0 END) AS 已开业,
    SUM(CASE WHEN site_status='off' THEN 1 ELSE 0 END) AS 已关闭,
    SUM(CASE WHEN <中间态列>='<待安装枚举>'   THEN 1 ELSE 0 END) AS 待安装,
    ... （其余 5 态同理，枚举据探测结果填）
  FROM t_site WHERE is_del=0
------------------------------------------------------------
"""
import json, pymysql, sys, datetime, os, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DB = json.load(open(os.path.join(ROOT, "config", "backup_config.json"), encoding="utf-8"))
DB.pop("workers", None)
OUT = os.path.join(ROOT, "data", "dashboard_data.json")
ERR = []

def ms2str(v):
    if not v:
        return ""
    try:
        return (datetime.datetime.utcfromtimestamp(int(v) / 1000) + datetime.timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(v)

# ---------- 连接（带白名单前置说明） ----------
try:
    conn = pymysql.connect(host=DB["host"], port=DB["port"], user=DB["user"], password=DB["password"],
                           database=DB["database"], connect_timeout=15, read_timeout=600, charset="utf8mb4")
    cur = conn.cursor()
except Exception as e:
    print("[DB CONNECT FAILED] 请确认沙箱公网 IP 120.229.33.42 已加入 ADB 白名单。", str(e)[:300], file=sys.stderr)
    sys.exit(2)

def q(sql, label, many=False):
    try:
        cur.execute(sql)
        return cur.fetchall() if many else (cur.fetchone()[0] if cur.rowcount else None)
    except Exception as e:
        ERR.append("%s: %s" % (label, str(e)[:200]))
        print("ERR", label, str(e)[:200], file=sys.stderr)
        return [] if many else None

EXT = {}
EXT["_generated_at"] = ms2str(int(time.time() * 1000))
EXT["_note"] = "扩展抽取：9类网点状态 + 各角色(商户/渠道商/代理商/业务员)手机号。字段均为 schema 探测后真实取值，未臆测。"

# ============================================================
# 1. SCHEMA 探测（先摸清字段，避免瞎猜）
# ============================================================
# 1.1 t_site 中所有「状态/state」类列 → 找中间状态藏在哪
status_cols = q(
    "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
    "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='t_site' "
    "AND (COLUMN_NAME LIKE '%%status%%' OR COLUMN_NAME LIKE '%%state%%')", "disc_status", many=True) or []
status_cols = [r[0] for r in status_cols]
EXT["_discovery"] = {"t_site_status_cols": status_cols}

site_status_probe = []
for col in status_cols:
    vals = q("SELECT DISTINCT %s FROM t_site WHERE is_del=0 AND %s IS NOT NULL AND %s<>'' LIMIT 50"
             % (col, col, col), "sp_" + col, many=True)
    if vals is not None:
        site_status_probe.append({"col": col, "vals": [v[0] for v in vals]})
EXT["_discovery"]["site_status_values"] = site_status_probe

# 1.2 手机号列探测（候选表）
CANDIDATE_TABLES = ["t_site", "t_merchant", "t_distributor", "t_promoter", "t_agency", "t_user"]
phone_cols = {}
for t in CANDIDATE_TABLES:
    cols = q(
        "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='%s' "
        "AND (COLUMN_NAME LIKE '%%phone%%' OR COLUMN_NAME LIKE '%%mobile%%' "
        "OR COLUMN_NAME LIKE '%%tel%%' OR COLUMN_NAME LIKE '%%contact%%')" % t, "disc_phone_" + t, many=True)
    if cols:
        phone_cols[t] = [r[0] for r in cols]
EXT["_discovery"]["phone_cols"] = phone_cols

# 1.3 候选表是否真实存在
tables_exist = {}
for t in CANDIDATE_TABLES:
    ok = q("SELECT 1 FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='%s'" % t, "exist_" + t)
    tables_exist[t] = ok is not None
EXT["_discovery"]["tables_exist"] = tables_exist

# ============================================================
# 2. 9 类网点状态计数
# ============================================================
# on=已开业, off=已关闭 已确认；中间态需据 1.1 探测到的「列+真实枚举」回填 INTERMEDIATE_MAP。
# 回填示例（待你/据探测报告确认后取消注释）：
#   INTERMEDIATE_MAP = {
#       "待安装": {"col": "site_status", "val": "wait_install"},
#       "待送货": {"col": "site_status", "val": "wait_deliver"},
#       "待验收": {"col": "site_status", "val": "wait_check"},
#       "待开业": {"col": "site_status", "val": "wait_open"},
#       "待审批": {"col": "site_status", "val": "wait_audit"},
#       "未合作": {"col": "coop_status", "val": "no_coop"},   # 若藏在别的列
#   }
INTERMEDIATE_MAP = {}

counts = {"已开业": 0, "已关闭": 0, "待安装": 0, "待送货": 0,
          "待验收": 0, "待开业": 0, "待审批": 0, "未合作": 0}
ss = q("SELECT site_status, COUNT(*) c FROM t_site WHERE is_del=0 GROUP BY site_status", "w_status2", many=True) or []
onoff = {"on": "已开业", "off": "已关闭"}
for r in ss:
    nm = onoff.get(r[0])
    if nm:
        counts[nm] += r[1]
for label, spec in INTERMEDIATE_MAP.items():
    c = q("SELECT COUNT(*) FROM t_site WHERE is_del=0 AND %s='%s'" % (spec["col"], spec["val"]), "w_" + label)
    if c:
        counts[label] = c

EXT["status_9"] = [{"label": k, "count": v} for k, v in counts.items()]
EXT["status_9_unmapped"] = [k for k, v in counts.items()
                            if v == 0 and k not in ("已开业", "已关闭")]
EXT["status_9_note"] = ("on/off 已确认；中间态若未在 INTERMEDIATE_MAP 配置、或 DB 无对应取值则记 0。"
                        "请据 _discovery.site_status_values 的真实枚举回填 INTERMEDIATE_MAP 后重跑。")

# ============================================================
# 3. 各角色手机号（基于探测到的表/列动态 JOIN）
# ============================================================
def pick(col_list, prefs=("phone", "mobile", "contact_phone", "contact_mobile", "tel")):
    if not col_list:
        return None
    for p in prefs:
        for c in col_list:
            if p in c.lower():
                return c
    return col_list[0]

def build_phone_map(table, key_col, phone_col):
    """返回 {key: phone} 与状态。表/列不存在时返回 ({}, 'missing')，不阻断。"""
    if not tables_exist.get(table):
        return {}, "table_missing"
    if not phone_col:
        return {}, "phone_col_missing"
    rows = q("SELECT %s, %s FROM %s WHERE is_del=0" % (key_col, phone_col, table), "pmap_" + table, many=True) or []
    return {r[0]: r[1] for r in rows}, "ok"

merchant_pc = pick(phone_cols.get("t_merchant", []))
distributor_pc = pick(phone_cols.get("t_distributor", []))
agency_pc = pick(phone_cols.get("t_agency", []))
promoter_pc = pick(phone_cols.get("t_promoter", []))

# 商户/渠道商/代理商按 id 关联；业务员(促销员)按 name 关联（主表未抽 business_id）
merchant_phone_map, mstat = build_phone_map("t_merchant", "id", merchant_pc)
distributor_phone_map, dstat = build_phone_map("t_distributor", "id", distributor_pc)
agency_phone_map, astat = build_phone_map("t_agency", "id", agency_pc)
promoter_phone_map, pstat = build_phone_map("t_promoter", "name", promoter_pc)

EXT["phone_maps_status"] = {"merchant": mstat, "distributor": dstat, "agency": astat, "promoter": pstat}
EXT["phone_cols_used"] = {"merchant": merchant_pc, "distributor": distributor_pc,
                          "agency": agency_pc, "promoter": promoter_pc}
EXT["phone_note"] = ("代理商手机号取 t_agency(agency_id)；运营代理/渠道商口径见名词字典 Q2。"
                     "若 t_agency 不存在则 agency_phone 全空，需据真实表名调整 build_phone_map 调用。")

# ============================================================
# 4. 合并进 dashboard_data.json
# ============================================================
try:
    D = json.load(open(OUT, encoding="utf-8"))
except Exception:
    D = {}
W = D.setdefault("site", {})
detail = W.get("detail", [])
hit = 0
for r in detail:
    mid = r.get("merchant_id")
    did = r.get("distributor_id")
    aid = r.get("agency_id")
    bname = r.get("business")
    mp = merchant_phone_map.get(mid) if mid is not None else None
    dp = distributor_phone_map.get(did) if did is not None else None
    ap = agency_phone_map.get(aid) if aid is not None else None
    bp = promoter_phone_map.get(bname) if bname else None
    r["merchant_phone"] = mp
    r["distributor_phone"] = dp
    r["agency_phone"] = ap
    r["business_phone"] = bp
    if any([mp, dp, ap, bp]):
        hit += 1
W["detail"] = detail
W["status_9"] = EXT["status_9"]          # 供前端 drawSite 替换 6 张 ⚠️ 卡片 + w-status 饼图
D["site_ext"] = EXT

json.dump(D, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
conn.close()

# ---------- 控制台报告 ----------
print("=== DISCOVERY REPORT ===")
print(json.dumps(EXT["_discovery"], ensure_ascii=False, indent=1))
print("\nstatus_9:", EXT["status_9"])
print("status_9_unmapped:", EXT["status_9_unmapped"])
print("phone_maps_status:", EXT["phone_maps_status"])
print("phone_cols_used:", EXT["phone_cols_used"])
print("detail rows augmented:", len(detail), "| rows with >=1 phone:", hit)
print("ERRORS:", len(ERR))
for e in ERR:
    print("  -", e)
print("DONE site_ext  ->", OUT)
