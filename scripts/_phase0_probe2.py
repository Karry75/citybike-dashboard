import json, time
t0=time.time()
D=json.load(open("data/dashboard_data.json", encoding="utf-8"))

print("=== workorder (safety) shape ===")
wo=D.get("workorder",{}).get("detail")
print("  workorder.detail count:", len(wo) if isinstance(wo,list) else type(wo))
if isinstance(wo,list) and wo:
    s=wo[0]
    print("  keys:", list(s.keys())[:30])
    print("  sample status/type/priority:", s.get("status"), s.get("type"), s.get("priority"), "| create_time:", s.get("create_time"), "| finish_time:", s.get("finish_time"))
ops_wo=D.get("ops",{}).get("work_order")
print("  ops.work_order type:", type(ops_wo).__name__, "len:", len(ops_wo) if hasattr(ops_wo,'__len__') else "n/a")
print("  ops.warn_by_level:", D.get("ops",{}).get("warn_by_level"))
print("  ops.warn_recent count:", len(D.get('ops',{}).get('warn_recent',[])) if isinstance(D.get('ops',{}).get('warn_recent'),list) else "n/a")

print("\n=== battery cell_info parseable? ===")
bd=D["device"]["battery_detail"]
sample_with_cell=[b for b in bd if b.get("cell_info")][:3]
for b in sample_with_cell[:2]:
    print("  sn=%s cell_info=%r" % (b.get("sn") or b.get("battery_sn"), str(b.get("cell_info"))[:120]))

print("\n=== exchange time field check ===")
ex=D["site"]["exchange"]
if isinstance(ex,list) and ex:
    s=ex[0]
    print("  keys:", list(s.keys()))
    print("  back_time sample:", s.get("back_time"), "| mileage:", s.get("mileage"), "| status:", s.get("status"))

print("\n=== pre-existing risk object (P0-5) ===")
rk=D.get("risk",{})
print("  risk keys:", list(rk.keys()))
for k,v in rk.items():
    if isinstance(v,dict):
        print("   risk.%s: dict{%d} keys=%s"%(k,len(v),list(v.keys())[:12]))
    elif isinstance(v,list):
        print("   risk.%s: list[%d]"%(k,len(v)))
    else:
        print("   risk.%s: %s"%(k,type(v).__name__))

print("\n=== analytics.daily trend ===")
ad=D.get("analytics",{}).get("daily")
print("  type:", type(ad).__name__, "len:", len(ad) if hasattr(ad,'__len__') else "n/a")
if isinstance(ad,list) and ad:
    print("  first:", ad[0])
    print("  last:", ad[-1])
elif isinstance(ad,dict):
    print("  sample keys:", list(ad.keys())[:5])

print("\nDONE %.1fs"%(time.time()-t0))
