#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 dashboard_data_lite.json 压成手机极速版 dashboard_data_mobile.json。
原则：结构/字段名 100% 不变，仅截断过长的明细数组与字典、浮点保留2位、超长文本裁剪。
这样前端 bootApp() 渲染逻辑完全不用改，只是表格行数变少、图表聚合值不变。
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LITE = os.path.join(ROOT, "data", "dashboard_data_lite.json")
MOBILE = os.path.join(ROOT, "data", "dashboard_data_mobile.json")

LIMIT_LIST = 80      # 列表超过此长度只保留前 N 条
LIMIT_DICT = 80      # 字典超过此键数只保留前 N 个键
STR_MAX = 200        # 字符串超过此长度裁剪

def shrink(o, depth=0):
    if isinstance(o, dict):
        # 截断过多键
        items = list(o.items())
        if len(items) > LIMIT_DICT:
            items = items[:LIMIT_DICT]
        return {k: shrink(v, depth + 1) for k, v in items}
    if isinstance(o, list):
        if len(o) > LIMIT_LIST:
            o = o[:LIMIT_LIST]
        return [shrink(x, depth + 1) for x in o]
    if isinstance(o, float):
        # 保留整数形态；浮点保留 2 位
        r = round(o, 2)
        return int(r) if r == int(r) else r
    if isinstance(o, str):
        if len(o) > STR_MAX:
            return o[:STR_MAX] + "…"
        return o
    return o

def main():
    print("读取 lite 数据…")
    d = json.load(open(LITE, encoding="utf-8"))
    mb = shrink(d)
    raw = json.dumps(mb, ensure_ascii=False).encode("utf-8")
    import gzip
    gz = gzip.compress(raw, 9)
    json.dump(mb, open(MOBILE, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"解压体积: {len(raw)/1024/1024:.2f} MB  | gzip: {len(gz)/1024/1024:.2f} MB")
    print(f"写入: {MOBILE}")

if __name__ == "__main__":
    main()
