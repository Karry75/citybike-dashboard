# -*- coding: utf-8 -*-
"""批量校验 exo 全量包。

核对项：
  1) 每包 dict.n == sum(counts) == 实际解码行数
  2) 每段 v==2，段文件齐全
  3) **列顺序（c）跨包完全一致**
  4) **编码列集合（e 的 key）跨包完全一致 == EXPECTED_ENC**
     —— 这是前端 loadMore 做"次包解码→主包重编码"的硬前提，
        任何一个月度包多编/少编一列都会导致列错位。
  5) 抽样解码首行，人工可读性检查
"""
import os, json, gzip, sys, glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

# 与抽取脚本一致：支持 EXO_MONTHLY_DIR / EXO_NEAR_DIR 指向独立目录（如 exo_monthly2/exo_near2）
MONTHLY_DIR = os.environ.get("EXO_MONTHLY_DIR", os.path.join(ROOT, "data", "exo_monthly"))
NEAR_DIR = os.environ.get("EXO_NEAR_DIR", os.path.join(ROOT, "data", "exo_near"))

# 从抽取脚本导入权威口径，避免两处硬编码漂移
try:
    from extract_exo_package import OUT_COLS, EXPECTED_ENC
except Exception as ex:  # 兜底
    print("!! 无法从 extract_exo_package 导入口径: %s" % ex)
    OUT_COLS, EXPECTED_ENC = None, None


def load_dict(d, base):
    p = os.path.join(d, base + ".dict.json.gz")
    if not os.path.exists(p):
        return None
    return json.loads(gzip.open(p, "rb").read().decode("utf-8"))


def validate_pkg(d, base):
    D = load_dict(d, base)
    if D is None:
        return (False, "缺失 dict", None)
    parts = D.get("parts", 1)
    counts = D.get("counts", [])
    c = D["c"]
    e = D.get("e", {})

    # 逐段处理，段间释放内存（不把整包行堆在内存里）
    got = 0
    probes = []      # 采样若干行做越界/解码检查
    for i in range(parts):
        sp = os.path.join(d, base + ".%d.json.gz" % i)
        if not os.path.exists(sp):
            return (False, "缺失段 %d" % i, None)
        P = json.loads(gzip.open(sp, "rb").read().decode("utf-8"))
        if P.get("v") != 2:
            return (False, "段 %d 版本非2" % i, None)
        pr = P.get("r", [])
        if i < len(counts) and len(pr) != counts[i]:
            return (False, "段 %d 行数与 counts 不符 %d != %d" % (i, len(pr), counts[i]), None)
        if pr:
            if len(pr[0]) != len(c):
                return (False, "段 %d 行宽不符 cols=%d rowlen=%d" % (i, len(c), len(pr[0])), None)
            for ri in (0, len(pr) // 2, len(pr) - 1):
                probes.append((i, ri, pr[ri]))
        got += len(pr)
        del P, pr
    if not (sum(counts) == got == D["n"]):
        return (False, "行数不符 n=%s counts=%s got=%s" % (D["n"], sum(counts), got), None)

    # 编码下标越界检查
    for pi, ri, row in probes:
        for ci, col in enumerate(c):
            if col in e:
                v = row[ci]
                if not isinstance(v, int) or v < 0 or v >= len(e[col]):
                    return (False, "编码越界 段%d 行%d 列%s 值=%r 字典长=%d" % (pi, ri, col, v, len(e[col])), None)

    samp = []
    if probes:
        row = probes[0][2]
        samp.append({col: (e[col][row[ci]] if col in e else row[ci]) for ci, col in enumerate(c)})

    meta = {"cols": c, "enc": sorted(e.keys()), "n": D["n"], "parts": parts, "samp": samp}
    return (True, samp, meta)


def main():
    bad = []
    good = 0
    metas = []  # (name, meta)

    targets = []
    for dp in sorted(glob.glob(os.path.join(MONTHLY_DIR, "*.dict.json.gz"))):
        base = os.path.basename(dp)[: -len(".dict.json.gz")]
        targets.append(("monthly/" + base, MONTHLY_DIR, base))
    if os.path.exists(os.path.join(NEAR_DIR, "exo.dict.json.gz")):
        targets.append(("near/exo", NEAR_DIR, "exo"))
    if not targets:
        print("!! 未找到任何包（MONTHLY_DIR=%s, NEAR_DIR=%s）" % (MONTHLY_DIR, NEAR_DIR))
        sys.exit(2)

    for name, d, base in targets:
        try:
            ok, info, meta = validate_pkg(d, base)
        except Exception as ex:
            ok, info, meta = False, "读取异常 %s: %s" % (type(ex).__name__, ex), None
        if ok:
            good += 1
            metas.append((name, meta))
        else:
            bad.append((name, info))

    print("=" * 68)
    print(" 扫描包数 : %d   有效 : %d   坏包 : %d" % (len(targets), good, len(bad)))

    # ---- 跨包一致性：列顺序 ----
    col_sigs = {}
    enc_sigs = {}
    for name, m in metas:
        col_sigs.setdefault(tuple(m["cols"]), []).append(name)
        enc_sigs.setdefault(tuple(m["enc"]), []).append(name)

    print("-" * 68)
    if len(col_sigs) <= 1:
        print(" [OK] 列顺序跨包一致（%d 列）" % (len(metas[0][1]["cols"]) if metas else 0))
    else:
        print(" [坏] 列顺序存在 %d 种不同签名：" % len(col_sigs))
        for sig, names in col_sigs.items():
            print("      %d 列 -> %d 个包，如 %s" % (len(sig), len(names), names[:3]))
        bad.append(("列顺序", "跨包不一致"))

    if len(enc_sigs) <= 1:
        enc = list(enc_sigs.keys())[0] if enc_sigs else ()
        print(" [OK] 编码列集合跨包一致（%d 列）" % len(enc))
        if EXPECTED_ENC is not None:
            if set(enc) == set(EXPECTED_ENC):
                print(" [OK] 编码列集合 == EXPECTED_ENC")
            else:
                print(" [坏] 编码列集合 != EXPECTED_ENC")
                print("      仅包内有: %s" % sorted(set(enc) - set(EXPECTED_ENC)))
                print("      仅期望有: %s" % sorted(set(EXPECTED_ENC) - set(enc)))
                bad.append(("编码列", "!= EXPECTED_ENC"))
        print("      编码列: %s" % "、".join(enc))
    else:
        print(" [坏] 编码列集合存在 %d 种不同签名（loadMore 会错位！）：" % len(enc_sigs))
        for sig, names in enc_sigs.items():
            print("      %d 列 -> %d 个包，如 %s" % (len(sig), len(names), names[:3]))
        bad.append(("编码列", "跨包不一致"))

    # ---- 汇总行数 ----
    total_monthly = sum(m["n"] for name, m in metas if name.startswith("monthly/"))
    near_n = next((m["n"] for name, m in metas if name == "near/exo"), 0)
    print("-" * 68)
    print(" 月度包合计行数 : %s（%d 个月）" % (format(total_monthly, ","), sum(1 for n, _ in metas if n.startswith("monthly/"))))
    print(" 近90天包行数   : %s" % format(near_n, ","))

    if metas:
        nm, m0 = metas[-1]
        if m0["samp"]:
            print("-" * 68)
            print(" 样本（%s 首行）:" % nm)
            for k, v in list(m0["samp"][0].items()):
                print("   %-22s %s" % (k, v))

    print("=" * 68)
    if bad:
        for b in bad:
            print("   [坏] %s : %s" % b)
        sys.exit(1)
    else:
        print(" 全量校验通过 ✅")
        sys.exit(0)


if __name__ == "__main__":
    main()
