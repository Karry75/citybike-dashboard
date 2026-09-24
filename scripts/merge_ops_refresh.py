# -*- coding: utf-8 -*-
"""把 data/ops_refresh.json 合并进 dashboard_data.json / dashboard_data_lite.json。

只覆盖运营总览依赖的**聚合键**，不动 detail 明细数组（避免破坏网点/设备/用户等其他模块）。

用法：
    python merge_ops_refresh.py lite      # 只合并 lite（6MB，秒级）
    python merge_ops_refresh.py full      # 只合并全量（752MB，约 3-6 分钟）
    python merge_ops_refresh.py both      # 两个都合（默认）
"""
import json, os, sys, time

ROOT = r"D:/workboddy file/dudu分析/citybike_backup"
SRC = ROOT + "/data/ops_refresh.json"
TARGETS = {
    "lite": ROOT + "/data/dashboard_data_lite.json",
    "full": ROOT + "/data/dashboard_data.json",
}

# 覆盖白名单：("顶层键", "子键" 或 None)。子键为 None 表示整段 dict 逐键覆盖。
OVERRIDE = [
    ("overview", None),          # KPI 总数 + 在线数
    ("device", None),            # 柜/电池 在线离线
    ("user", ["city_rank"]),     # 城市换电排行（全量口径）
    ("analytics", ["daily"]),    # 按天趋势（2021-09 ~ 至今）
    ("dashboard", ["ops"]),      # 全量预聚合：网点类型/状态、电池状态、仓位状态、城市聚合
]

mode = (sys.argv[1] if len(sys.argv) > 1 else "both").lower()
R = json.load(open(SRC, encoding="utf-8"))
print("[src] ops_refresh.json  refreshed_at=%s  daily=%d 天" % (
    R["meta"]["refreshed_at"], len(R.get("analytics", {}).get("daily", []))))


def merge_into(path, tag):
    if not os.path.exists(path):
        print("[%s] SKIP (不存在): %s" % (tag, path))
        return
    t0 = time.time()
    size_mb = os.path.getsize(path) / 1048576.0
    print("\n[%s] 读取 %.1f MB ..." % (tag, size_mb), flush=True)
    D = json.load(open(path, encoding="utf-8"))
    print("[%s] 读取完成 %.1fs" % (tag, time.time() - t0), flush=True)

    changed = []
    for top, subs in OVERRIDE:
        if top not in R:
            continue
        tgt = D.setdefault(top, {})
        if not isinstance(tgt, dict):
            continue
        if subs is None:
            for k, v in R[top].items():
                old = tgt.get(k)
                tgt[k] = v
                if old != v:
                    changed.append("%s.%s" % (top, k))
        else:
            for k in subs:
                if k in R[top]:
                    oldn = len(tgt.get(k) or []) if isinstance(tgt.get(k), list) else "-"
                    tgt[k] = R[top][k]
                    newn = len(R[top][k]) if isinstance(R[top][k], list) else "-"
                    changed.append("%s.%s (%s→%s)" % (top, k, oldn, newn))

    D.setdefault("meta", {})["ops_refreshed_at"] = R["meta"]["refreshed_at"]
    D["meta"]["ops_caliber"] = R["meta"]["caliber"]

    t1 = time.time()
    tmp = path + ".tmp"
    # lite 必须紧凑写回：与 build_lite_data.py 保持一致。
    # 用 indent=1 会让 96.5MB 膨胀到 126.7MB（多出的全是缩进空格），
    # 直接拖慢手机端 gz 解压后的 JSON.parse。full 保留缩进便于人工排查。
    _ind = None if tag == "lite" else 1
    _sep = (",", ":") if tag == "lite" else None
    json.dump(D, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=_ind, separators=_sep)
    os.replace(tmp, path)
    print("[%s] 写回完成 %.1fs  新体积 %.1f MB" % (tag, time.time() - t1, os.path.getsize(path) / 1048576.0))
    print("[%s] 覆盖键 (%d):" % (tag, len(changed)))
    for c in changed:
        print("     -", c)


if mode in ("lite", "both"):
    merge_into(TARGETS["lite"], "lite")
if mode in ("full", "both"):
    merge_into(TARGETS["full"], "full")

print("\nMERGE DONE")
