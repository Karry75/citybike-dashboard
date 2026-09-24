# -*- coding: utf-8 -*-
"""
根据 exo_monthly2 / exo_near2 实际落盘的包，重新生成 data/exo_manifest.json（或 EXO_MANIFEST 指定路径）。

抽取脚本 extract_exo_package.py 在末尾一次性写 manifest。若当时因权限/并发失败（PermissionError），
本脚本可安全重算——只读各包 dict 的 n/parts 与文件体积，不触网、不重写包本身。

用法：
  EXO_MONTHLY_DIR=.../data/exo_monthly2 EXO_NEAR_DIR=.../data/exo_near2 \
  python scripts/_regen_exo_manifest.py
"""
import os, sys, json, gzip, datetime, glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MONTHLY_DIR = os.environ.get("EXO_MONTHLY_DIR", os.path.join(ROOT, "data", "exo_monthly"))
NEAR_DIR = os.environ.get("EXO_NEAR_DIR", os.path.join(ROOT, "data", "exo_near"))
OUT = os.environ.get("EXO_MANIFEST", os.path.join(ROOT, "data", "exo_manifest2.json"))


def load_dict(d, base):
    p = os.path.join(d, base + ".dict.json.gz")
    if not os.path.exists(p):
        return None
    return json.loads(gzip.GzipFile(p, "rb").read().decode("utf-8"))


def pkg_gz(d, base, parts):
    files = [base + ".dict.json.gz"] + ["%s.%d.json.gz" % (base, i) for i in range(parts)]
    return sum(os.path.getsize(os.path.join(d, f)) for f in files if os.path.exists(os.path.join(d, f)))


def main():
    months = []
    for dp in sorted(glob.glob(os.path.join(MONTHLY_DIR, "exo_*.dict.json.gz"))):
        base = os.path.basename(dp)[:-len(".dict.json.gz")]
        D = load_dict(MONTHLY_DIR, base)
        if D is None:
            print("  [WARN] %s dict 读取失败，跳过" % base)
            continue
        ym = base[len("exo_"):]
        parts = D.get("parts", 1)
        months.append({"ym": ym, "base": base, "rows": D.get("n", 0),
                       "parts": parts, "gz": pkg_gz(MONTHLY_DIR, base, parts)})
    months.sort(key=lambda x: x["ym"])

    near = None
    Dn = load_dict(NEAR_DIR, "exo")
    if Dn is not None:
        parts = Dn.get("parts", 1)
        near = {"base": "exo", "rows": Dn.get("n", 0), "parts": parts,
                "gz": pkg_gz(NEAR_DIR, "exo", parts)}

    total = sum(m["rows"] for m in months) + (near["rows"] if near else 0)
    manifest = {"generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "total_rows": total, "months": months, "near": near}
    json.dump(manifest, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("已写 manifest: %s" % OUT)
    print("  月度包: %d 个（%s ~ %s）" % (len(months), months[0]["ym"] if months else "-", months[-1]["ym"] if months else "-"))
    print("  近90天: %s" % ("%d 行 %d 段" % (near["rows"], near["parts"]) if near else "无"))
    print("  总行数: %s" % format(total, ","))
    return 0


if __name__ == "__main__":
    sys.exit(main())
