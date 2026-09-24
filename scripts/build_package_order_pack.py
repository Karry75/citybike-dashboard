# -*- coding: utf-8 -*-
"""
把 data/package_order_full.jsonl（全量套餐购买订单，JSONL，约 223 万行）打包成
列式 + 字符串字典编码 + gzip 的「1 份字典 + K 段行体」结构：
  citybike_minimal/package_order.dict.json.gz    <- 列名 + 全局字典 + 段行数清单
  citybike_minimal/package_order.0.json.gz       <- 纯行体
  citybike_minimal/package_order.1.json.gz
  ...
  citybike_minimal/package_order.{K-1}.json.gz

为什么要分段：CloudStudio 静态托管对单文件大小有上限（约 50MB），而整包 74MB 超限
导致部署被拒（400）。拆成 K 段后每段 ~15MB 即可正常部署；前端 GEngine 用 opt.parts
拉取全部段并在本地合并（各段共用同一份全局字典，合并时只需拼接 r，无需重映射下标）。

为什么字典要外置（v2，2026-08-10）：CloudStudio 除单文件上限外还有「部署目录总量」
上限（实测约 95,000,000 字节）。v1 把同一份全局字典（明文 11.19MB / gz 2.40MB）
在每段里各存一遍，K=4 就白白多占 3 份 ≈ 5.57MB，直接把目录顶到 93.84MB 被拒。
抽成独立文件后 4 段合计 59.89MB → 54.31MB，目录回落到 88.26MB。

包格式（解压后 JSON）：
  dict 包 {"v":2,"ts":"...","n":总行数,"parts":K,"counts":[每段行数],
           "c":[列名...], "e":{"order_type":[...], ...}}
  行体段 {"v":2,"part":i,"n":段行数,"r":[[v0,v1,...], ...]}   # 编码列值为全局字典下标
前端 GEngine（key=PKG）并发拉 dict + K 段，decode 后本地分页 / 筛选 / 导出。

为控制内存，直接流式两遍：
  Pass1：逐行读 JSONL，仅对「白名单内的低基数字符串列」统计唯一值（构建全局字典）
  Pass2：逐行读 JSONL，按段编码并流式写各段 gz（不把全量行载入内存）
"""
import os, sys, json, gzip, time, datetime, hashlib, math

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "data", "package_order_full.jsonl")
COLS_FILE = os.path.join(ROOT, "data", "package_order_cols.json")
MINIMAL = os.path.join(ROOT, "citybike_minimal")
META = os.path.join(ROOT, "data", "package_order_pack_meta.json")

# 包格式版本：2 = 字典外置（dict 包 + 纯行体段）
PACK_VERSION = 2

# 字典编码策略：默认「除黑名单外全部编码」。
# 黑名单 = 全量基数过高、字典本身会比原数据还大的列（2026-08-10 全量实测 2,225,590 行）：
#   purchase_order_id  每行唯一          → 字典无意义
#   create_time        >40 万唯一（秒级） → 字典 + 下标反而更大
#   pay_time           >40 万唯一        → 同上
# 其余 29 列实测基数：is_replenish_rent/replenish_amount/refund_operator/refund_trade_no=1、
#   order_type/is_paid=2、order_status=4、sign_agency_name=10、pay_method=18、battery_product=31、
#   sign_agency_id=46、coupon_amount=53、refund_reason=129、coupon_center_id=162、coupon_name=185、
#   order_total_amount=237、order_payable_amount/order_actual_paid=266、remark=354、
#   brand_discount_amount=360、refund_amount=1145、sign_site_name=2639、sign_site_id=2641、
#   coupon_id=26778、exchange_agreement_id=88712、user_id=106613、user_phone=108992、
#   refund_time=112862、pay_trade_no=262478  —— 全部远小于行数，编码收益显著。
NO_ENCODE = {"purchase_order_id", "create_time", "pay_time"}
DICT_MAX_UNIQ = 300000

# 分段数（可通过环境变量覆盖）。每段约 74MB/K；K=4 → 每段 ~18MB，远低于单文件上限。
PARTS = int(os.environ.get("PKG_PARTS", "4"))


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
    cols = json.load(open(COLS_FILE, encoding="utf-8")) if os.path.exists(COLS_FILE) else None
    if cols is None:
        with open(SRC, "r", encoding="utf-8") as _f:
            for _l in _f:
                _l = _l.strip()
                if _l:
                    cols = list(json.loads(_l).keys())
                    break
    ENCODE_COLS = [c for c in cols if c not in NO_ENCODE]

    # ---- Pass 1：统计全局字典 ----
    print("[1/4] Pass1 统计字典编码（流式读 %s，候选 %d 列）..." % (
        os.path.basename(SRC), len(ENCODE_COLS)), flush=True)
    dicts = {c: {} for c in ENCODE_COLS}
    dict_arr = {c: [] for c in ENCODE_COLS}
    n = 0
    with open(SRC, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            n += 1
            if n % 500000 == 0:
                print("      已扫描 %d 行…" % n, flush=True)
            # 注意：JSONL 每行都是数据，不存在表头行。早期版本这里有 `if n <= 1: continue`
            # （CSV 表头逻辑残留），会导致第 1 行的值不进字典 —— 低基数列碰巧无害，但对
            # user_id / user_phone / exchange_agreement_id 这类高基数列，若首行的值全表仅
            # 出现一次，编码时 dicts.get(v, 0) 会静默落到下标 0，把第 1 行改成别人的数据。
            try:
                r = json.loads(line)
            except Exception:
                continue
            for c in ENCODE_COLS:
                if c not in dicts:
                    continue
                v = r.get(c)
                if v is None:
                    v = ""
                if not isinstance(v, str):
                    v = str(v)
                if v not in dicts[c]:
                    if len(dict_arr[c]) >= DICT_MAX_UNIQ:
                        dicts[c] = None
                        dict_arr[c] = None
                        continue
                    dicts[c][v] = len(dict_arr[c])
                    dict_arr[c].append(v)
    if cols is None:
        print("[ERR] 无法解析列名")
        return 1
    for c in ENCODE_COLS:
        if dicts.get(c) is None:
            dict_arr[c] = None
    enc_cols = [c for c in ENCODE_COLS if dict_arr.get(c)]
    e_global = {c: dict_arr[c] for c in enc_cols}
    print("      总行数 = %d，字典编码列 = %d / %d" % (n, len(enc_cols), len(cols)), flush=True)
    for c in enc_cols:
        print("        - %s : %d 唯一值" % (c, len(dict_arr[c])))

    # ---- Pass 2：编码并分段流式写 gz ----
    print("[2/4] Pass2 编码 + 分段流式写 gz（%d 段）..." % PARTS, flush=True)
    if n < PARTS:
        k = 1
    else:
        k = PARTS
    rows_per_part = int(math.ceil(n / float(k)))
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    enc_set = set(enc_cols)

    def enc_row(line):
        r = json.loads(line)
        out = []
        for c in cols:
            v = r.get(c)
            if c in enc_set:
                if v is None:
                    v = ""
                if not isinstance(v, str):
                    v = str(v)
                ix = dicts[c].get(v)
                if ix is None:
                    # 绝不静默落 0：那会把这一行的该列改成字典第 0 个值（张冠李戴且无报错）
                    raise AssertionError("字典缺失: 列 %s 值 %r 未在 Pass1 收录" % (c, v))
                out.append(ix)
            else:
                out.append(v)
        return out

    os.makedirs(MINIMAL, exist_ok=True)
    # 每个段一个 gzip 句柄
    out_paths = [os.path.join(MINIMAL, "package_order.%d.json.gz" % i) for i in range(k)]
    dict_path = os.path.join(MINIMAL, "package_order.dict.json.gz")
    gfs = [gzip.GzipFile(p, "wb", compresslevel=9, mtime=0) for p in out_paths]
    # 各段头部：行数在 Pass1 后已完全确定（pid = cnt // rows_per_part，最后一段收尾），
    # 直接写真实 n，省掉过去 _rewrite_n 对每段 ~200MB 明文的二次 gzip。
    expect_counts = [max(0, min(rows_per_part, n - pid * rows_per_part)) for pid in range(k)]
    for pid, gi in enumerate(gfs):
        # v2：段内不再重复 c / e（见文件头说明），只留 part / n / r
        gi.write(('{"v":%d,"part":%d,"n":%d,"r":[' % (
            PACK_VERSION, pid, expect_counts[pid])).encode("utf-8"))
    part_counts = [0] * k
    first_in_part = [True] * k
    cnt = 0
    with open(SRC, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            pid = min(cnt // rows_per_part, k - 1) if n > 1 else 0
            row = enc_row(line)
            buf = ("" if first_in_part[pid] else ",") + json.dumps(row, ensure_ascii=False, separators=(",", ":"))
            gfs[pid].write(buf.encode("utf-8"))
            first_in_part[pid] = False
            part_counts[pid] += 1
            cnt += 1
            if cnt % 500000 == 0:
                print("      已写入 %d / %d 行…" % (cnt, n), flush=True)
    for gi in gfs:
        gi.write(b"]}")
        gi.close()
    if part_counts != expect_counts:
        raise AssertionError("段行数与预估不符: 实际 %s != 预估 %s" % (part_counts, expect_counts))
    gz_sizes = [os.path.getsize(p) for p in out_paths]
    print("      段大小: " + ", ".join(human(s) for s in gz_sizes), flush=True)

    # ---- 写外置字典包（全部段共用这一份）----
    dict_obj = {
        "v": PACK_VERSION, "ts": ts, "n": n, "parts": k,
        "counts": part_counts, "c": cols, "e": e_global,
    }
    with gzip.GzipFile(dict_path, "wb", compresslevel=9, mtime=0) as gd:
        gd.write(json.dumps(dict_obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    dict_size = os.path.getsize(dict_path)
    print("      字典包: %s（外置，省下 %d 段重复存储）" % (human(dict_size), k - 1), flush=True)

    # ---- 校验：回读每段抽样 ----
    print("[3/4] 回读校验 ...", flush=True)
    # 先校验外置字典包本身（前端所有段都依赖它，读错一处全表错位）
    back_dict = json.loads(gzip.open(dict_path, "rb").read().decode("utf-8"))
    if back_dict["c"] != cols:
        raise AssertionError("字典包列名与源不一致")
    if back_dict["n"] != n or back_dict["parts"] != k or back_dict["counts"] != part_counts:
        raise AssertionError("字典包 n/parts/counts 与实际不一致: %r" % (
            (back_dict["n"], back_dict["parts"], back_dict["counts"]),))
    if sum(back_dict["counts"]) != n:
        raise AssertionError("字典包 counts 求和 %d != 总行数 %d" % (sum(back_dict["counts"]), n))
    if sorted(back_dict["e"].keys()) != sorted(enc_cols):
        raise AssertionError("字典包编码列集合与实际不一致")
    e_back = back_dict["e"]
    print("      字典包 OK（%d 行 / %d 段 / %d 编码列）" % (
        back_dict["n"], back_dict["parts"], len(e_back)), flush=True)

    import random
    random.seed(7)
    # 强制覆盖首行/末行/各段首行（历史 bug 正是只在第 1 行发作，随机抽样打不中）
    sample_idx = set(random.sample(range(n), min(10, n)))
    sample_idx.add(0)
    sample_idx.add(n - 1)
    for _p in range(k):
        sample_idx.add(min(_p * rows_per_part, n - 1))
    by_i = {}
    with open(SRC, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            if i in sample_idx:
                by_i[i] = json.loads(line)
    # 建立全局行号 -> (段, 段内偏移)：用前缀和，避免逐行建 220 万条映射
    starts = []
    _acc = 0
    for pid in range(k):
        starts.append(_acc)
        _acc += part_counts[pid]

    def _seg_of(gi):
        for pid in range(k - 1, -1, -1):
            if gi >= starts[pid]:
                return pid, gi - starts[pid]
        return 0, gi

    _cache = {}

    def _part(pid):
        # 每段只解压一次（一段解开约 200MB JSON，逐样本重解会慢到不可用）
        if pid not in _cache:
            _cache.clear()
            _cache[pid] = json.loads(gzip.open(out_paths[pid], "rb").read().decode("utf-8"))
        return _cache[pid]

    for i in sorted(sample_idx):
        pid, j = _seg_of(i)
        back = _part(pid)
        if back.get("part") != pid or back.get("n") != part_counts[pid]:
            raise AssertionError("段%d 头部 part/n 不符: %r" % (pid, (back.get("part"), back.get("n"))))
        if len(back["r"]) != part_counts[pid]:
            raise AssertionError("段%d 行数 %d != 声明 %d" % (pid, len(back["r"]), part_counts[pid]))
        got = back["r"][j]
        src = by_i[i]
        for ci, c in enumerate(cols):
            v = got[ci]
            a = src.get(c)
            if a is None:
                a = ""
            # v2：字典来自外置 dict 包（段内已不含 e），用回读的 e_back 解码，
            # 这样这条断言同时覆盖了「dict 包与行体段是否配套」
            if c in e_back:
                # 字典列一律以 str() 形态入库（Pass1/Pass2 都这么做），
                # 所以源侧的 int/float 要同样规范化后再比，否则 2505239335 != '2505239335' 误报
                v = e_back[c][v]
                if not isinstance(a, str):
                    a = str(a)
            if a != v:
                raise AssertionError("行%d 列%s 不一致: %r != %r" % (i, c, a, v))
    print("      抽样校验 OK（覆盖 %d 个样本，跨 %d 段，字典走外置包）" % (len(sample_idx), k), flush=True)

    total_gz = sum(gz_sizes) + dict_size
    meta = {
        "pack_version": PACK_VERSION,
        "generated_at": ts, "rows": n, "cols": len(cols), "parts": k,
        "rows_per_part": rows_per_part, "counts": part_counts, "dict_cols": enc_cols,
        "dict_file": dict_path, "dict_bytes": dict_size,
        "gzip_bytes_per_part": gz_sizes,
        "gzip_bytes_total": total_gz,
        "gzip_md5": [hashlib.md5(open(p, "rb").read()).hexdigest() for p in [dict_path] + out_paths],
        "out": out_paths,
    }
    json.dump(meta, open(META, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print("")
    print("=" * 60)
    print(" 包格式版本      : v%d（字典外置）" % PACK_VERSION)
    print(" 行 / 列        : %d / %d" % (n, len(cols)))
    print(" 字典编码列      : %d" % len(enc_cols))
    print(" 分段数 K        : %d（每段 %d 行）" % (k, rows_per_part))
    print(" gzip 字典包     : %s" % human(dict_size))
    print(" gzip 每段       : %s" % ", ".join(human(s) for s in gz_sizes))
    print(" gzip 合计       : %s" % human(total_gz))
    print(" 输出           : %s" % ", ".join([dict_path] + out_paths))
    print(" 总耗时         : %.1fs" % (time.time() - t0))
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
