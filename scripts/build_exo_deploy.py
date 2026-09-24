# -*- coding: utf-8 -*-
"""
构建「换电订单明细」独立部署目录 citybike_exo/：
  1) 由 html/template.html 生成城市看板壳（含 EXO 引擎）-> citybike_static/index.html
  2) 组装 citybike_exo/：
       index.html + dashboard_data_lite.json.gz（仅 gz，不放 136MB 明文兜底）
       + 近 90 天包 exo.{dict,0,1}.json.gz（来自 data/exo_near/）
       + 尽可能多复制「近 90 天之前」的月度包（来自 data/exo_monthly/），受 CloudStudio 目录总量上限约束
       + exo_manifest.json（供面板「加载更早月份」下拉）
  3) 输出目录总字节数，供部署前预算核对。

注意：CloudStudio 部署目录总量硬上限约 95.4MB（98.4MB 会被拒）。本脚本设安全预算 94MB，
近 90 天包(~60MB)+壳(~13MB)后仅余 ~20MB，通常只能再塞 1 个更早月份（如 2026-04）。
更早月份全量保留在本地 data/exo_monthly/，可由本地全量版/服务端按需加载。

用法：python scripts/build_exo_deploy.py
"""
import os, sys, json, gzip, shutil, subprocess, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TPL = os.path.join(ROOT, "html", "template.html")
STATIC = os.path.join(ROOT, "citybike_static")
EXO_DIR = os.path.join(ROOT, "citybike_exo")
NEAR = os.environ.get("EXO_NEAR_DIR", os.path.join(ROOT, "data", "exo_near"))
MONTHLY = os.environ.get("EXO_MONTHLY_DIR", os.path.join(ROOT, "data", "exo_monthly"))
LITE = os.path.join(ROOT, "data", "dashboard_data_lite.json")

BUDGET = int(os.environ.get("EXO_DEPLOY_BUDGET", "94_000_000"))  # 字节，CloudStudio 安全预算（可被 env 覆盖以适配上传网关上限）

# 近 90 天窗口起始月（2026-05 起算；2026-04 及更早算「更早月份」）
NEAR_FROM_YM = "2026-05"


def pkg_files(dirpath, base):
    """读 {base}.dict.json.gz 的真实 parts，返回该包应有的全部文件名列表。
    不硬编码分段数——near 包 parts 由行数决定（>40万=2 段），月度包一般 1 段但历史包可能不同。
    返回 (files, parts)；包缺失或损坏返回 ([], 0)。"""
    dp = os.path.join(dirpath, base + ".dict.json.gz")
    if not os.path.exists(dp):
        return [], 0
    try:
        with gzip.GzipFile(dp, "rb") as g:
            d = json.loads(g.read().decode("utf-8"))
        k = int(d.get("parts", 1))
    except Exception as e:
        print("     [WARN] %s 的 dict 包读取失败：%s" % (base, e))
        return [], 0
    files = [base + ".dict.json.gz"] + ["%s.%d.json.gz" % (base, i) for i in range(k)]
    missing = [f for f in files if not os.path.exists(os.path.join(dirpath, f))]
    if missing:
        print("     [WARN] %s 缺分段：%s" % (base, ", ".join(missing)))
        return [], 0
    return files, k


def run_build_static():
    print("[1] 由 template.html 生成城市看板壳（含 EXO 引擎）…", flush=True)
    subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "build_static_from_template.py")],
                  check=True, cwd=ROOT)
    assert os.path.exists(os.path.join(STATIC, "index.html")), "citybike_static/index.html 未生成"
    print("      citybike_static/index.html 就绪")


def main():
    import time
    t0 = time.time()
    if not os.path.exists(NEAR) or not os.path.exists(os.path.join(NEAR, "exo.dict.json.gz")):
        print("[ERR] 未找到近 90 天包 data/exo_near/exo.* —— 请先运行 extract_exo_package.py", flush=True)
        return 1
    if not os.path.exists(LITE):
        print("[ERR] 缺少 data/dashboard_data_lite.json", flush=True)
        return 1

    run_build_static()

    if os.path.exists(EXO_DIR):
        shutil.rmtree(EXO_DIR)
    os.makedirs(EXO_DIR, exist_ok=True)

    total = 0

    # 先探测近 90 天包的真实分段数，用于校正壳里的 EXO_OPT.parts
    near_files, near_parts = pkg_files(NEAR, "exo")
    if not near_files:
        print("[ERR] 近 90 天包不完整（data/exo_near/exo.*），请重跑 extract_exo_package.py")
        return 1

    # 复制壳（仅 gz 版 lite 数据，不放 136MB 明文兜底）
    with open(os.path.join(STATIC, "index.html"), "r", encoding="utf-8") as f:
        shell = f.read()
    # 模板默认 parts:2；若近 90 天包实际分段数不同，必须同步校正，否则前端会 404 或漏段
    old_sig = "url:'exo', parts:2,"
    new_sig = "url:'exo', parts:%d," % near_parts
    if old_sig not in shell:
        print("[ERR] 壳中未找到 EXO_OPT 特征串 %r，template.html 可能已改动，请同步本脚本" % old_sig)
        return 1
    if near_parts != 2:
        shell = shell.replace(old_sig, new_sig, 1)
        print("      已校正 EXO_OPT.parts: 2 -> %d（依据近 90 天包实际分段）" % near_parts)
    with open(os.path.join(EXO_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(shell)
    total += os.path.getsize(os.path.join(EXO_DIR, "index.html"))
    lite_gz = os.path.join(STATIC, "dashboard_data_lite.json.gz")
    if not os.path.exists(lite_gz):
        # 重新压缩
        with open(LITE, "rb") as fi, open(lite_gz, "wb") as fo:
            fo.write(gzip.compress(fi.read(), 9))
    shutil.copy(lite_gz, os.path.join(EXO_DIR, "dashboard_data_lite.json.gz"))
    total += os.path.getsize(lite_gz)
    print("[2] 壳: index.html + lite.gz = %.2f MB（累计 %.2f MB）" % (
        (os.path.getsize(os.path.join(EXO_DIR, "index.html")) + os.path.getsize(lite_gz)) / 1048576, total / 1048576))

    # 复制近 90 天包（分段数已在上方从 dict 实读）
    near_bytes = 0
    for f in near_files:
        src = os.path.join(NEAR, f)
        shutil.copy(src, os.path.join(EXO_DIR, f))
        near_bytes += os.path.getsize(src)
    total += near_bytes
    print("[3] 近 90 天包: %.2f MB（%d 段，累计 %.2f MB）" % (
        near_bytes / 1048576, near_parts, total / 1048576))

    # 读完整清单（支持 EXO_MANIFEST 指向独立目录的清单，避免被默认 data/exo_manifest.json 覆盖）
    manifest_path = os.environ.get("EXO_MANIFEST", os.path.join(ROOT, "data", "exo_manifest2.json"))
    if not os.path.exists(manifest_path):
        print("[ERR] 未找到清单 %s（请先运行 _regen_exo_manifest.py）" % manifest_path)
        return 1
    full_manifest = json.load(open(manifest_path, encoding="utf-8"))
    near_rows = (full_manifest.get("near") or {}).get("rows", 0)

    # 复制「近 90 天之前」的月度包（新→旧），直到预算用尽
    included = []
    months = sorted([m for m in full_manifest.get("months", []) if m["ym"] < NEAR_FROM_YM],
                    key=lambda x: x["ym"], reverse=True)
    for m in months:
        base = m["base"]
        files, mparts = pkg_files(MONTHLY, base)
        if not files:
            continue
        add = sum(os.path.getsize(os.path.join(MONTHLY, f)) for f in files)
        if total + add > BUDGET:
            print("     [跳过] %s（%+0.2fMB 将超预算 %.2fMB）" % (m["ym"], add / 1048576, BUDGET / 1048576))
            continue
        for f in files:
            shutil.copy(os.path.join(MONTHLY, f), os.path.join(EXO_DIR, f))
        total += add
        m = dict(m)
        m["parts"] = mparts
        m["gz"] = add
        included.append(m)
        print("     [纳入] %s : +%.2fMB（累计 %.2fMB）" % (m["ym"], add / 1048576, total / 1048576))
        if total > BUDGET - 5_000_000:  # 留 5MB 余量
            break

    # 写部署用清单（只列实际放入的包）
    dep_manifest = {
        "generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "near": {"base": "exo", "rows": near_rows, "parts": near_parts},
        "months": [{"ym": m["ym"], "base": m["base"], "rows": m["rows"],
                    "parts": m["parts"], "gz": m["gz"]} for m in included],
    }
    json.dump(dep_manifest, open(os.path.join(EXO_DIR, "exo_manifest.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    print("")
    print("=" * 60)
    print(" 部署目录 : %s" % EXO_DIR)
    print(" 目录总量 : %.2f MB / 预算 %.2f MB" % (total / 1048576, BUDGET / 1048576))
    print(" 近90天    : %d 行（默认加载）" % near_rows)
    print(" 更早月份  : %d 个（%s）" % (len(included), ", ".join(m["ym"] for m in included) or "无（精简版仅含近90天）"))
    print("=" * 60)
    if total > BUDGET:
        print("[WARN] 超出预算，部署可能被 CloudStudio 拒绝！")
        return 2
    print("构建完成：可部署 citybike_exo/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
