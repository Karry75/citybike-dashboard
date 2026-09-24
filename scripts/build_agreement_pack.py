# -*- coding: utf-8 -*-
"""
把 data/agreement_full.json（全量协议明细，~182MB）打包成
citybike_minimal/agreement.json.gz（列式 + 字符串字典编码 + gzip，~7.5MB）

包格式（解压后的 JSON）：
{
  "v": 1,                       # 格式版本
  "ts": "2026-08-08 11:44:00",  # 抽取时间
  "n": 121806,                  # 行数
  "c": ["agreement_id", ...],   # 列名（顺序即 r 里每行的顺序）
  "e": {"city":["浙江省杭州市",...], ...},  # 被字典编码的列 -> 字典数组
  "r": [[v0,v1,...], ...]       # 行数据；若列在 e 中，值为字典下标(int)
}

前端解码保持列式（不还原成 12 万个对象），只在渲染当前页 / 导出分批时按需构造行对象。
"""
import os
import sys
import json
import gzip
import time
import hashlib
import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "citybike_minimal")

# 可复用：python build_agreement_pack.py <name>
#   <name>=agreement(默认) -> data/agreement_full.json -> citybike_minimal/agreement.json.gz
#   <name>=deposit         -> data/deposit_full.json   -> citybike_minimal/deposit.json.gz
NAME = sys.argv[1] if len(sys.argv) > 1 else "agreement"
SRC = os.path.join(ROOT, "data", "%s_full.json" % NAME)
OUT = os.path.join(OUT_DIR, "%s.json.gz" % NAME)
META = os.path.join(ROOT, "data", "%s_pack_meta.json" % NAME)

# 字典编码阈值：字符串列，且唯一值数 < 行数*RATIO 且 < MAX_UNIQ
DICT_RATIO = 0.5
DICT_MAX_UNIQ = 60000


def human(b):
    for u in ("B", "KB", "MB", "GB"):
        if b < 1024:
            return "%.2f %s" % (b, u)
        b /= 1024.0
    return "%.2f TB" % b


def main():
    t0 = time.time()
    if not os.path.exists(SRC):
        print("[ERR] 源文件不存在: %s" % SRC)
        return 1

    raw_size = os.path.getsize(SRC)
    print("[1/6] 读取 %s (%s) ..." % (os.path.basename(SRC), human(raw_size)))
    with open(SRC, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        # 容错：可能被包了一层 {"rows":[...]}
        for k in ("rows", "data", "list", "agreement_detail", "deposit_detail"):
            if k in data and isinstance(data[k], list):
                data = data[k]
                break
    n = len(data)
    print("      行数 = %d，耗时 %.1fs" % (n, time.time() - t0))
    if n == 0:
        print("[ERR] 无数据")
        return 1

    # ---- 2. 汇总列名（以出现顺序为准，扫全量以防字段缺失） ----
    print("[2/6] 汇总列名 ...")
    cols = []
    seen = set()
    for r in data:
        for k in r:
            if k not in seen:
                seen.add(k)
                cols.append(k)
    print("      列数 = %d" % len(cols))

    # ---- 3. 逐列判定是否字典编码 ----
    print("[3/6] 统计各列基数 ...")
    dict_cols = []
    col_uniq = {}
    for k in cols:
        vals = set()
        is_str = False
        over = False
        for r in data:
            v = r.get(k)
            if isinstance(v, str):
                is_str = True
            vals.add(v if not isinstance(v, (list, dict)) else json.dumps(v, ensure_ascii=False))
            if len(vals) > DICT_MAX_UNIQ:
                over = True
                break
        col_uniq[k] = ("%d+" % DICT_MAX_UNIQ) if over else len(vals)
        if is_str and (not over) and len(vals) < n * DICT_RATIO:
            dict_cols.append(k)
    print("      字典编码列 = %d / %d" % (len(dict_cols), len(cols)))
    print("      " + ", ".join(dict_cols))

    # ---- 4. 构建字典 ----
    print("[4/6] 构建字典 + 编码 ...")
    dicts = {}
    idxmap = {}
    for k in dict_cols:
        arr = []
        m = {}
        for r in data:
            v = r.get(k)
            if v is None:
                v = ""
            if not isinstance(v, str):
                v = str(v)
            if v not in m:
                m[v] = len(arr)
                arr.append(v)
        dicts[k] = arr
        idxmap[k] = m

    rows = []
    for r in data:
        out = []
        for k in cols:
            if k in idxmap:
                v = r.get(k)
                if v is None:
                    v = ""
                if not isinstance(v, str):
                    v = str(v)
                out.append(idxmap[k][v])
            else:
                out.append(r.get(k))
        rows.append(out)

    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    pack = {"v": 1, "ts": ts, "n": n, "c": cols, "e": dicts, "r": rows}

    # ---- 5. 序列化 + gzip ----
    print("[5/6] 序列化 + gzip(level=9) ...")
    payload = json.dumps(pack, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    print("      列式 JSON = %s" % human(len(payload)))
    os.makedirs(OUT_DIR, exist_ok=True)
    with gzip.GzipFile(OUT, "wb", compresslevel=9, mtime=0) as gf:
        gf.write(payload)
    gz_size = os.path.getsize(OUT)
    md5 = hashlib.md5(open(OUT, "rb").read()).hexdigest()

    # ---- 6. 校验 + meta ----
    print("[6/6] 回读校验 ...")
    with gzip.open(OUT, "rb") as gf:
        back = json.loads(gf.read().decode("utf-8"))
    assert back["n"] == n, "行数不一致"
    assert len(back["r"]) == n, "行数组长度不一致"
    assert back["c"] == cols, "列名不一致"
    # 抽样比对 3 行
    import random
    random.seed(42)
    for i in random.sample(range(n), min(3, n)):
        src = data[i]
        got = {}
        for j, k in enumerate(cols):
            v = back["r"][i][j]
            if k in back["e"]:
                v = back["e"][k][v]
            got[k] = v
        for k in cols:
            a = src.get(k)
            b = got.get(k)
            if k in dicts:
                a = "" if a is None else (a if isinstance(a, str) else str(a))
            if a != b:
                raise AssertionError("行%d 列%s 不一致: %r != %r" % (i, k, a, b))
    print("      抽样校验 OK")

    meta = {
        "generated_at": ts,
        "rows": n,
        "cols": len(cols),
        "dict_cols": dict_cols,
        "col_unique": col_uniq,
        "raw_json_bytes": raw_size,
        "columnar_json_bytes": len(payload),
        "gzip_bytes": gz_size,
        "gzip_md5": md5,
        "out": OUT,
    }
    with open(META, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print("")
    print("=" * 60)
    print(" 原始 JSON     : %s" % human(raw_size))
    print(" 列式 JSON     : %s  (%.1f%%)" % (human(len(payload)), 100.0 * len(payload) / raw_size))
    print(" gzip 产物     : %s  (%.1f%%, 压缩比 %.1fx)" % (human(gz_size), 100.0 * gz_size / raw_size, raw_size / float(gz_size)))
    print(" 行 / 列       : %d / %d" % (n, len(cols)))
    print(" 字典编码列    : %d" % len(dict_cols))
    print(" MD5           : %s" % md5)
    print(" 输出          : %s" % OUT)
    print(" 元信息        : %s" % META)
    print(" 总耗时        : %.1fs" % (time.time() - t0))
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
