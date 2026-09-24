# -*- coding: utf-8 -*-
"""把 data/analytics_refresh.json 合并进 dashboard_data.json / dashboard_data_lite.json。

只覆盖 analytics 段的聚合键（A1-A10），不动其他 14 个模块、不动 detail 明细数组。

用法：
    python merge_analytics_refresh.py lite      # 只合并 lite（秒级）
    python merge_analytics_refresh.py full      # 只合并全量（约 1-3 分钟）
    python merge_analytics_refresh.py both      # 两个都合（默认）
"""
import json, os, sys, time

ROOT = r"D:/workboddy file/dudu分析/citybike_backup"
SRC = ROOT + "/data/analytics_refresh.json"
TARGETS = {
    "lite": ROOT + "/data/dashboard_data_lite.json",
    "full": ROOT + "/data/dashboard_data.json",
}

# 覆盖白名单：analytics 段整段逐键覆盖（A1-A10 全部由 extract_analytics_refresh 重算）
OVERRIDE = [
    ("analytics", None),
]

mode = (sys.argv[1] if len(sys.argv) > 1 else "both").lower()
R = json.load(open(SRC, encoding="utf-8"))
print("[src] analytics_refresh.json  refreshed_at=%s  analytics_keys=%s" % (
    R["meta"]["refreshed_at"], list(R.get("analytics", {}).keys())))


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
                    tgt[k] = R[top][k]
                    changed.append("%s.%s" % (top, k))

    D.setdefault("meta", {})["analytics_refreshed_at"] = R["meta"]["refreshed_at"]
    D["meta"]["analytics_caliber"] = R["meta"]["caliber"]

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
