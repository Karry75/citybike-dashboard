# -*- coding: utf-8 -*-
"""
将 coupon_refresh.json 注入 data/dashboard_data_lite.json 的 D["coupon"] 段。
非破坏式：仅替换 coupon 键，其余部分原样保留；紧凑写回（与 lite 既有格式一致）。
"""
import json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LITE = os.path.join(ROOT, "data", "dashboard_data_lite.json")
SRC  = os.path.join(ROOT, "data", "coupon_refresh.json")
BAK  = os.path.join(ROOT, "data", "dashboard_data_lite.json.bak_coupon_%s" % time.strftime("%Y%m%d_%H%M%S"))

def main():
    if not os.path.exists(LITE):
        print("[FATAL] 找不到 lite 文件:", LITE); sys.exit(1)
    if not os.path.exists(SRC):
        print("[FATAL] 找不到抽取结果:", SRC); sys.exit(1)

    print("读取 lite (%s) ..." % (os.path.getsize(LITE)/1024/1024,))
    D = json.load(open(LITE, encoding="utf-8"))
    C = json.load(open(SRC, encoding="utf-8"))

    # 备份（一次性，便于回滚）
    json.dump(D, open(BAK, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print("已备份到:", BAK)

    old = D.get("coupon", {})
    D["coupon"] = C

    print("写回 lite (compact) ...")
    json.dump(D, open(LITE, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    sz = os.path.getsize(LITE)
    print("写回完成，新大小 = %.1f MB" % (sz/1024/1024))

    # 校验
    cp = D["coupon"]
    checks = {
        "overview": bool(cp.get("overview")),
        "agent_issue": len(cp.get("agent_issue", [])),
        "merchant_issue": len(cp.get("merchant_issue", [])),
        "contract": len(cp.get("contract", [])),
        "by_coupon": len(cp.get("by_coupon", [])),
        "top_merchant": len(cp.get("top_merchant", [])),
        "user_detail": len(cp.get("user_detail", [])),
        "resource": len(cp.get("resource", [])),
    }
    print("校验:", json.dumps(checks, ensure_ascii=False))
    assert checks["agent_issue"] > 0 and checks["merchant_issue"] > 0 and checks["contract"] > 0, "三统计注入失败"
    print("OK: coupon 段已注入 lite（全量，无上限）")

if __name__ == "__main__":
    main()
