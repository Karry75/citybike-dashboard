# -*- coding: utf-8 -*-
"""校验 v2 列式包：读取 dict + 段，解码并打印样本行 + 行数核对。用法：python _validate_exo.py <dir> <base> [part]"""
import sys, os, json, gzip
d = sys.argv[1]
base = sys.argv[2]
parts = int(sys.argv[3]) if len(sys.argv) > 3 else 1
dict_path = os.path.join(d, base + ".dict.json.gz")
segs = [os.path.join(d, base + ".%d.json.gz" % i) for i in range(parts)]
D = json.loads(gzip.open(dict_path, "rb").read().decode("utf-8"))
print("dict v=%s n=%s parts=%s counts=%s enc_cols=%d" % (D["v"], D["n"], D["parts"], D["counts"], len(D["e"])))
print("cols =", D["c"])
rows = []
for s in segs:
    P = json.loads(gzip.open(s, "rb").read().decode("utf-8"))
    assert P["v"] == 2
    rows.extend(P["r"])
print("decoded rows =", len(rows))
assert sum(D["counts"]) == len(rows) == D["n"], "行数不符"
# 解码前 3 行
for i in range(min(3, len(rows))):
    o = {}
    for ci, col in enumerate(D["c"]):
        v = rows[i][ci]
        o[col] = D["e"][col][v] if col in D["e"] else v
    print("row%d:" % i, json.dumps(o, ensure_ascii=False)[:300])
print("OK: 包格式有效，行数一致")
