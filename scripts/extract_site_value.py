# -*- coding: utf-8 -*-
"""
网点价值评估模型 (Task#267)
对 site.detail(10681) 逐条打分，输出 S/A/B/C 四级 + 建议动作。
评分维度(已批准权重)：
  换电效益 40：swap_30d >=500->40, >=200->28, >=50->16, >=10->8, else 0
  用户粘性 25：net=sign_30d-unsub_30d >=20->25, >=5->18, >=0->12, else 4
  设备健康 20：cabinet_status=='正常' 且 offline_rate==0 ->20, <0.3->14, <0.7->8, else 2
  成长性 15：growth=(swap_30d*3-swap_90d)/swap_90d >0.2->15, >0->10, >-0.2->6, else 2 (无90d数据->0)
淘汰标准(已批准)：C级(<25) + audit_status=='已开业' + swap_30d<10
单点月运维成本 OPEX_PER_SITE_MONTH = 2000 元 (估算假设，依据运维费用制度DD-YW-230208口径，可调)
注入: site.value = {stats, tier_dist, by_city, eliminate_candidates, top_sites, list}
"""
import json, time, os

PATH = "data/dashboard_data.json"
OPEX_PER_SITE_MONTH = 2000  # 估算假设（元/网点/月），可调整
t0 = time.time()
print("LOAD", PATH)
D = json.load(open(PATH, encoding="utf-8"))
sd = D["site"]["detail"]
print("site.detail=", len(sd))

def to_int(x):
    try: return 0 if x is None else int(float(str(x).strip()))
    except: return 0

def score_site(s):
    swap30 = to_int(s.get("swap_30d"))
    swap90 = to_int(s.get("swap_90d"))
    cab = to_int(s.get("cabinet_count"))
    cab_off = to_int(s.get("cabinet_offline_count"))
    cab_status = s.get("cabinet_status") or ""
    sign = to_int(s.get("sign_users_30d"))
    unsub = to_int(s.get("unsub_users_30d"))
    audit = s.get("audit_status") or ""

    # 1 换电效益
    if swap30 >= 500: sw = 40
    elif swap30 >= 200: sw = 28
    elif swap30 >= 50: sw = 16
    elif swap30 >= 10: sw = 8
    else: sw = 0

    # 2 用户粘性
    net = sign - unsub
    if net >= 20: st = 25
    elif net >= 5: st = 18
    elif net >= 0: st = 12
    else: st = 4

    # 3 设备健康
    offline_rate = cab_off / max(cab, 1)
    if cab_status == "正常" and offline_rate == 0: hth = 20
    elif offline_rate < 0.3: hth = 14
    elif offline_rate < 0.7: hth = 8
    else: hth = 2

    # 4 成长性
    if swap90 > 0:
        growth = (swap30 * 3 - swap90) / swap90
        if growth > 0.2: gr = 15
        elif growth > 0: gr = 10
        elif growth > -0.2: gr = 6
        else: gr = 2
    else:
        gr = 0

    total = sw + st + hth + gr
    if total >= 75: tier, action = "S", "保留扩张（明星网点）"
    elif total >= 50: tier, action = "A", "优化提升（潜力网点）"
    elif total >= 25: tier, action = "B", "观察考核（边际网点）"
    else: tier, action = "C", "建议淘汰（低价值网点）"

    cab_eff = round(swap30 / max(cab, 1) / 30.0, 3) if cab > 0 else 0
    eliminate = (tier == "C" and audit == "已开业" and swap30 < 10)
    return total, tier, action, sw, st, hth, gr, cab_eff, eliminate, (swap30, swap90, cab, cab_off, cab_status, net, audit)

lst = []
tier_dist = {"S":0,"A":0,"B":0,"C":0}
by_city = {}
elim = []
for s in sd:
    total, tier, action, sw, st, hth, gr, cab_eff, eliminate, raw = score_site(s)
    city = s.get("city") or "未知"
    rec = {
        "id": s.get("id"), "name": s.get("name"), "city": city, "area": s.get("area"),
        "audit_status": raw[6], "swap_30d": raw[0], "swap_90d": raw[1],
        "cabinet_count": raw[2], "cabinet_offline": raw[3], "cabinet_status": raw[4],
        "net_users_30d": raw[5], "cab_eff": cab_eff,
        "score": total, "tier": tier, "action": action,
        "breakdown": {"swap":sw,"sticky":st,"health":hth,"growth":gr},
        "eliminate": eliminate,
    }
    lst.append(rec)
    tier_dist[tier] += 1
    c = by_city.get(city, {"city":city,"total":0,"S":0,"A":0,"B":0,"C":0,"eliminate":0})
    c["total"]+=1; c[tier]+=1
    if eliminate: c["eliminate"]+=1
    by_city[city]=c
    if eliminate: elim.append(rec)

stats = {
    "total": len(lst),
    "tier_dist": tier_dist,
    "eliminate_candidates": len(elim),
    "est_annual_saving_yuan": len(elim) * OPEX_PER_SITE_MONTH * 12,
    "opex_per_site_month": OPEX_PER_SITE_MONTH,
}
top_sites = sorted(lst, key=lambda x:-x["score"])[:100]
by_city_list = sorted(by_city.values(), key=lambda c:-c.get("eliminate",0))

D["site"]["value"] = {
    "stats": stats,
    "tier_dist": tier_dist,
    "by_city": by_city_list,
    "eliminate_candidates": elim,
    "top_sites": top_sites,
    "list": lst,
    "thresholds": {"swap_tiers":[500,200,50,10],"sticky_tiers":[20,5,0],
        "health_offline_rates":[0,0.3,0.7],"growth_tiers":[0.2,0,-0.2],
        "tier_cut":[75,50,25],"elim_rule":"C级+已开业+swap_30d<10"},
    "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
}

# 安全写回
newp = PATH + ".new"
json.dump(D, open(newp, "w", encoding="utf-8"), ensure_ascii=False)
side = PATH + ".prev2"
if os.path.exists(side): os.rename(side, side + "." + str(int(time.time())))
os.rename(PATH, side)
os.rename(newp, PATH)
print("WROTE", PATH)

rep = []
rep.append("# 网点价值评估模型 · 结果报告\n")
rep.append("> 生成：%s | 源：site.detail(%d条)" % (D["site"]["value"]["generated_at"], len(sd)))
rep.append("")
rep.append("## 一、价值分级分布")
rep.append("")
rep.append("| 等级 | 数量 | 占比 | 含义 |")
rep.append("|------|------|------|------|")
mean={"S":"保留扩张（明星）","A":"优化提升（潜力）","B":"观察考核（边际）","C":"建议淘汰（低价值）"}
for k in ["S","A","B","C"]:
    rep.append("| %s | %d | %.1f%% | %s |" % (k, tier_dist[k], 100.0*tier_dist[k]/len(lst), mean[k]))
rep.append("")
rep.append("## 二、淘汰候选（C级 + 已开业 + 30天换电<10）")
rep.append("")
rep.append("- **候选数量：%d 个网点**" % len(elim))
rep.append("- **预计年节省（按 %d 元/网点/月 估算）：¥%s**（= %d × %d × 12）" % (OPEX_PER_SITE_MONTH, format(stats["est_annual_saving_yuan"],","), len(elim), OPEX_PER_SITE_MONTH))
rep.append("- ⚠️ 单点月运维成本为估算假设，需以《运维费用管理标准制度 DD-YW-230208》实际口径校准。")
rep.append("")
rep.append("## 三、城市淘汰候选排行（Top15）")
rep.append("")
rep.append("| 城市 | 网点总数 | S | A | B | C | 淘汰候选 |")
rep.append("|------|---------|---|---|---|---|---------|")
for c in by_city_list[:15]:
    if c["eliminate"]>0:
        rep.append("| %s | %d | %d | %d | %d | %d | %d |" % (c["city"] or "未知", c["total"], c["S"], c["A"], c["B"], c["C"], c["eliminate"]))
rep.append("")
rep.append("## 四、明星网点 Top15（S级，保留扩张）")
rep.append("")
rep.append("| 网点ID | 名称 | 城市 | 30天换电 | 柜数 | 评分 |")
rep.append("|--------|------|------|---------|------|------|")
for x in top_sites[:15]:
    rep.append("| %s | %s | %s | %d | %d | %d |" % (x["id"], (x["name"] or "")[:20], x["city"], x["swap_30d"], x["cabinet_count"], x["score"]))
rep.append("")
rep.append("## 五、所以呢？（业务建议）")
rep.append("")
rep.append("1. **优先处置 %d 个僵尸网点**：已开业却 30 天换电<10 次，纯消耗运维资源，建议关停回收。")
rep.append("2. **A级 %d 个潜力网点**重点投放资源（补柜/促销），争取升 S。")
rep.append("3. 数据已注入 `site.value`，大屏(网点运营/指挥总览)可直接消费 tier_dist / eliminate_candidates / by_city。")
rep.append("")
open("docs/网点价值评估报告.md", "w", encoding="utf-8").write("\n".join(rep))
print("\n".join(rep[:40]))
print("...\nREPORT -> docs/网点价值评估报告.md | 耗时 %.1fs" % (time.time()-t0))
