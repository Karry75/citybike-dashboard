#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_lite_data.py — 生成手机极速版数据
把超大明细表(list/dict)裁剪到 CAP 行，KPI/汇总类小字段原样保留。
输出 data/dashboard_data_lite.json，供移动端 /api/data?lite=1 或移动 UA 自动使用。
"""
import json, os, time

SRC = "D:/workboddy file/dudu分析/citybike_backup/data/dashboard_data.json"
DST = "D:/workboddy file/dudu分析/citybike_backup/data/dashboard_data_lite.json"
CAP = 500  # 明细表最大保留行数（手机足够；桌面端仍用全量）

def cap(v, depth=0):
    """递归裁剪：list 超 CAP 取前 CAP；dict 超 CAP 取前 CAP 个 key。其余原样。"""
    if isinstance(v, list):
        if len(v) > CAP:
            v = v[:CAP]
        return [cap(x, depth+1) for x in v]
    if isinstance(v, dict):
        if len(v) > CAP:
            # 保持插入顺序，取前 CAP 个 key（多为按数值/时间排序的明细）
            items = list(v.items())[:CAP]
            v = dict(items)
        return {k: cap(val, depth+1) for k, val in v.items()}
    return v

def size_mb(obj):
    return len(json.dumps(obj, ensure_ascii=False).encode('utf-8')) / 1024 / 1024

t = time.time()
print("loading full data (409MB)...", flush=True)
with open(SRC, encoding='utf-8') as f:
    data = json.load(f)
print(f"  loaded in {time.time()-t:.1f}s | {len(data)} modules | {size_mb(data):.1f}MB", flush=True)

t = time.time()
lite = cap(data)
print(f"capped in {time.time()-t:.1f}s -> {size_mb(lite):.1f}MB", flush=True)

# 5 张核心明细表中，3 张维持 500 行控体积；cabinet_detail / battery_detail 放开到全量
# （前端分页每页 20 条，不影响渲染性能）
_DETAIL_CAP = {
    ("user", "agreement_detail"): 500,
    ("user", "deposit_detail"): 500,
    ("site", "detail"): 500,
}
for (mod, key), n in _DETAIL_CAP.items():
    if mod in data and isinstance(data[mod], dict) and key in data[mod] and isinstance(data[mod][key], list):
        lite.setdefault(mod, {})[key] = data[mod][key][:n]
        print(f"  明细截{n}: {mod}.{key} = {len(lite[mod][key])} 行", flush=True)
# 换电柜/电池明细不截断：保留全部（分页展示）
for _key in ("cabinet_detail", "battery_detail"):
    if "device" in data and isinstance(data.get("device"), dict) and _key in data["device"] and isinstance(data["device"][_key], list):
        _n = len(data["device"][_key])
        lite.setdefault("device", {})[_key] = data["device"][_key]
        print(f"  明细全量: device.{_key} = {_n} 行", flush=True)

# 临时方案：电池明细补 battery_product（经用户协议 battery_sns 反查）
# 注：待 ADB 重抽 t_battery 补 model 字段后，可由 model 直接替换（覆盖 100%）；
#     此处用 SN→用户协议 反查，覆盖约 63%，其余诚实留空不编造。
_agr = data.get("user", {}).get("agreement_detail") if isinstance(data.get("user"), dict) else None
_bat = lite.get("device", {}).get("battery_detail") if isinstance(lite.get("device"), dict) else None
if isinstance(_agr, list) and isinstance(_bat, list):
    _sn2prod = {}
    for _r in _agr:
        _sns = _r.get("battery_sns")
        _bp = _r.get("battery_product")
        if not _sns or not _bp:
            continue
        for _s in str(_sns).split(","):
            _s = _s.strip()
            if _s and _s != "—" and _s not in _sn2prod:
                _sn2prod[_s] = _bp
    _hit = 0
    for _b in _bat:
        _sn = _b.get("sn")
        if _sn and _sn in _sn2prod:
            _b["battery_product"] = _sn2prod[_sn]
            _hit += 1
    print(f"  电池产品补值: {_hit}/{len(_bat)} 命中（经用户协议反查，覆盖约 {_hit*100//len(_bat)}%）", flush=True)

# 合并区域月度序列（城市×区×月），来自 extract_region_monthly.py；不存在则留空壳
_rm = os.path.join(os.path.dirname(DST), "region_monthly.json")
if os.path.exists(_rm):
    try:
        _rm_data = json.load(open(_rm, encoding="utf-8"))
        lite["region_monthly"] = _rm_data
        print(f"  合并 region_monthly: {len(_rm_data)} 个城市（区域月度下钻已启用）", flush=True)
    except Exception as e:
        print(f"  ⚠️ region_monthly 合并失败: {e}", flush=True)
else:
    lite.setdefault("region_monthly", {})
    print("  region_monthly 缺失（extract_region_monthly.py 未跑）→ 留空壳（看板显示待接入）", flush=True)

t = time.time()
with open(DST, 'w', encoding='utf-8') as f:
    json.dump(lite, f, ensure_ascii=False)
print(f"written {DST} in {time.time()-t:.1f}s | {os.path.getsize(DST)/1024/1024:.1f}MB", flush=True)
print("DONE")
