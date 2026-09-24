#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_region_pipeline.py — 城市×区下钻 一键数据管线
把「抽数 → 合并 → 构建 → 自包含 → 复制到极简版 → smoke」串成一步。

用法：
  python run_region_pipeline.py                 # 全链（抽数 + 构建 + smoke）
  python run_region_pipeline.py --skip-extract  # 已有 region_monthly.json，跳过抽数
  python run_region_pipeline.py --skip-build    # 只抽数，不构建/不 smoke
  python run_region_pipeline.py --skip-smoke    # 构建但不跑 smoke

依赖：pymysql（运行本脚本的 python 必须已安装）。脚本内所有路径均相对本文件，
      不写死绝对路径，复制到任意位置均可运行。

说明：
  - 抽数前 extract_region_monthly.py 会自检：密码若为占位符 / ADB 白名单未放行，
    会立即退出并给出明确提示，不会误连。
  - 部署（bj8 公网）不在本脚本内：构建 + smoke 通过后，由助手调用部署工具部署
    citybike_minimal/，或你手动部署该目录。
"""
import os
import sys
import time
import shutil
import subprocess
import argparse

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(BASE, "scripts")
SELFCONTAINED = os.path.join(BASE, "citybike_selfcontained", "index.html")
MINIMAL_DIR = os.path.join(BASE, "citybike_minimal")
MINIMAL = os.path.join(MINIMAL_DIR, "index.html")
PY = sys.executable  # 用运行本脚本的 python（须已含 pymysql）


def _step(name, desc, script, *extra):
    print("\n=== [%s] %s ===" % (name, desc), flush=True)
    t = time.time()
    cmd = [PY, os.path.join(SCRIPTS, script)] + list(extra)
    rc = subprocess.call(cmd)
    if rc != 0:
        print("❌ 步骤 [%s] 失败（退出码 %d），管线中止。" % (name, rc), flush=True)
        sys.exit(rc)
    print("✅ [%s] 完成，耗时 %.1fs" % (name, time.time() - t), flush=True)


def _copy_minimal():
    print("\n=== [copy_minimal] selfcontained → citybike_minimal ===", flush=True)
    if not os.path.exists(SELFCONTAINED):
        print("❌ 找不到 %s，请先跑 build_selfcontained.py" % SELFCONTAINED, flush=True)
        sys.exit(1)
    os.makedirs(MINIMAL_DIR, exist_ok=True)
    shutil.copyfile(SELFCONTAINED, MINIMAL)
    print("✅ 复制到 %s (%d bytes)" % (MINIMAL, os.path.getsize(MINIMAL)), flush=True)


def _smoke():
    print("\n=== [smoke_minimal] 零运行时错误回归 ===", flush=True)
    t = time.time()
    rc = subprocess.call([PY, os.path.join(SCRIPTS, "smoke_minimal.py")])
    if rc != 0:
        print("❌ smoke 失败（退出码 %d），请查看上方输出定位问题。" % rc, flush=True)
        sys.exit(rc)
    print("✅ smoke 通过，耗时 %.1fs" % (time.time() - t), flush=True)


def main():
    ap = argparse.ArgumentParser(description="城市×区下钻 一键数据管线")
    ap.add_argument("--skip-extract", action="store_true", help="跳过抽数（用已有 region_monthly.json）")
    ap.add_argument("--skip-build", action="store_true", help="跳过构建与 smoke（只抽数）")
    ap.add_argument("--skip-smoke", action="store_true", help="构建但不跑 smoke")
    args = ap.parse_args()

    if args.skip_extract:
        print("⏭️  跳过 extract（使用已有 region_monthly.json）", flush=True)
    else:
        _step("extract_region_monthly", "抽取 城市×区×月 序列", "extract_region_monthly.py")

    if args.skip_build:
        print("⏭️  跳过构建（--skip-build）", flush=True)
    else:
        _step("build_lite_data", "合并 region_monthly 进 lite", "build_lite_data.py")
        _step("build_static_from_template", "模板 → citybike_static", "build_static_from_template.py")
        _step("build_selfcontained", "内联 gzip+base64 → selfcontained", "build_selfcontained.py")
        _copy_minimal()
        if args.skip_smoke:
            print("⏭️  跳过 smoke（--skip-smoke）", flush=True)
        else:
            _smoke()

    print("\n🎉 管线完成。", flush=True)
    if not args.skip_build:
        print("   本地产物：%s" % MINIMAL, flush=True)
        print("   下一步：部署 citybike_minimal/ 到 bj8（由助手调用部署工具，或手动部署）。", flush=True)


if __name__ == "__main__":
    main()
