import json, sys, time

t0=time.time()
PATH="data/dashboard_data.json"
print("LOADING", PATH, "...")
with open(PATH, encoding="utf-8") as f:
    D=json.load(f)
print("LOADED in %.1fs, top-level keys: %d" % (time.time()-t0, len(D)))

def info(name, obj):
    if obj is None:
        return "%s: <None>" % name
    if isinstance(obj, list):
        n=len(obj)
        if n:
            keys=list(obj[0].keys()) if isinstance(obj[0], dict) else type(obj[0]).__name__
            return "%s: list[%d] sample_keys=%s" % (name, n, keys)
        return "%s: list[0 EMPTY]" % name
    if isinstance(obj, dict):
        return "%s: dict{%d} keys=%s" % (name, len(obj), list(obj.keys())[:40])
    return "%s: %s" % (name, type(obj).__name__)

# top-level
for k in sorted(D.keys()):
    print(" -", info(k, D[k]))

# drill into the important sub-keys for the 7-dimension models
print("\n=== battery_detail (risk model source) ===")
bd=D.get("device",{}).get("battery_detail") if isinstance(D.get("device"),dict) else D.get("battery_detail")
if bd is None:
    # try other locations
    bd = D.get("battery_detail")
print("  count:", len(bd) if isinstance(bd,list) else "n/a")
if isinstance(bd,list) and bd:
    s=bd[0]
    need=["soc","bms_max_temp","bms_max_min_temp","cycle_count","cell_info","online","is_online","voltage","voltage_cells","status","cabinet_sn","site_id","city","area","temperature","charge_temp","discharge_temp"]
    got={k:(k in s) for k in need}
    print("  field presence:", got)
    print("  sample soc/cycle/bms:", s.get("soc"), s.get("cycle_count"), s.get("bms_max_temp"))

print("\n=== site.detail (value model source) ===")
sd=D.get("site",{}).get("detail") if isinstance(D.get("site"),dict) else None
if sd is None: sd=D.get("site_detail")
if sd is None:
    # search
    for k,v in D.items():
        if isinstance(v,dict) and "detail" in v and isinstance(v["detail"],list) and v["detail"] and "audit_status" in v["detail"][0]:
            sd=v["detail"]; print("  found under key",k); break
print("  count:", len(sd) if isinstance(sd,list) else "n/a")
if isinstance(sd,list) and sd:
    s=sd[0]
    need=["swap_30d","swap_90d","swap_7d","cabinet_count","cabinet_offline_count","cabinet_status","audit_status","sign_users_30d","unsub_users_30d","is_24h","indoor_outdoor","fee_settle_method","meter_status","city","area","user_count","battery_in_cabinet"]
    print("  field presence:", {k:(k in s) for k in need})

print("\n=== exchange (orders, travel dimension) ===")
ex=D.get("site",{}).get("exchange") if isinstance(D.get("site"),dict) else D.get("exchange")
if ex is None: ex=D.get("exchange")
print("  count:", len(ex) if isinstance(ex,list) else "n/a (not a list)")
if isinstance(ex,list) and ex:
    s=ex[0]
    need=["order_time","take_time","back_time","mileage","battery_sn","take_user_phone","consume_user_phone","user_id","city","area","site_name","cabinet_sn","soc_before","soc_after","status","amount","pay_type"]
    print("  field presence:", {k:(k in s) for k in need})

print("\n=== workorder (safety alerts) ===")
wo=D.get("ops",{}).get("work_order") if isinstance(D.get("ops"),dict) else D.get("workorder")
if wo is None:
    for k,v in D.items():
        if isinstance(v,dict) and "detail" in v and isinstance(v["detail"],list) and v["detail"] and ("create_time" in v["detail"][0] or "type" in v["detail"][0]):
            wo=v["detail"]; print("  found under",k); break
print("  count:", len(wo) if isinstance(wo,list) else "n/a")
if isinstance(wo,list) and wo:
    s=wo[0]
    print("  sample keys:", list(s.keys())[:30])

print("\n=== geo (maps) ===")
geo=D.get("geo")
if geo is not None:
    print("  geo keys:", list(geo.keys()) if isinstance(geo,dict) else type(geo))
    for gk,gv in (geo.items() if isinstance(geo,dict) else []):
        print("   geo.%s:"%gk, info(gk,gv))

print("\n=== cabinet_detail (online rate) ===")
cd=D.get("device",{}).get("cabinet_detail") if isinstance(D.get("device"),dict) else D.get("cabinet_detail")
print("  count:", len(cd) if isinstance(cd,list) else "n/a")
if isinstance(cd,list) and cd:
    s=cd[0]
    print("  field presence:", {k:(k in s) for k in ["is_online","online","slots_error","slots_locked","slots_with_battery","site_id","status"]})

print("\n=== user.detail ===")
ud=D.get("user",{}).get("detail") if isinstance(D.get("user"),dict) else D.get("user_detail")
if ud is None:
    for k,v in D.items():
        if isinstance(v,dict) and "detail" in v and isinstance(v["detail"],list) and v["detail"] and ("phone" in v["detail"][0] or "user_id" in v["detail"][0]):
            ud=v["detail"]; print("  found under",k); break
print("  count:", len(ud) if isinstance(ud,list) else "n/a")

print("\nDONE in %.1fs" % (time.time()-t0))
