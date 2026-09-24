import json
from collections import Counter
D=json.load(open("data/dashboard_data.json",encoding="utf-8"))
bd=D["device"]["battery_detail"]
print("total batteries:", len(bd))

# online field distribution
oc=Counter(str(b.get("online")) for b in bd)
print("\nonline values:", dict(oc))

# soc distribution
soc_zero=sum(1 for b in bd if b.get("soc") in (0,"0",None,""))
soc_vals=[b.get("soc") for b in bd if isinstance(b.get("soc"),(int,float))]
import statistics
def fnum(x):
    try: return float(x)
    except: return None
socnums=[fnum(b.get("soc")) for b in bd]
socnums=[x for x in socnums if x is not None]
print("\nsoc: zero/null=%d  nonnull=%d" % (soc_zero, len(socnums)))
if socnums:
    print("  soc min/mean/max: %.1f / %.1f / %.1f" % (min(socnums), statistics.mean(socnums), max(socnums)))
    print("  soc==0 count:", sum(1 for x in socnums if x==0))
    print("  soc<10 count:", sum(1 for x in socnums if 0<x<10))
    print("  soc 10-20:", sum(1 for x in socnums if 10<=x<20))

# temp distribution (bms_max_temp)
temps=[fnum(b.get("bms_max_temp")) for b in bd]
temps=[x for x in temps if x is not None]
print("\nbms_max_temp nonnull:", len(temps))
if temps:
    print("  temp min/mean/max: %.1f / %.1f / %.1f" % (min(temps), statistics.mean(temps), max(temps)))
    print("  temp>55:", sum(1 for x in temps if x>55), " >45:", sum(1 for x in temps if x>45))

# cycle distribution
cycles=[fnum(b.get("cycle_count")) for b in bd]
cycles=[x for x in cycles if x is not None]
print("\ncycle nonnull:", len(cycles))
if cycles:
    print("  cycle min/mean/max: %.0f / %.0f / %.0f" % (min(cycles), statistics.mean(cycles), max(cycles)))
    print("  cycle>800:", sum(1 for x in cycles if x>800), " >500:", sum(1 for x in cycles if x>500))

# how many offline AND soc==0 (double default?) 
both=sum(1 for b in bd if str(b.get("online"))!="在线" and b.get("soc") in (0,"0",None))
print("\noffline AND soc zero/null:", both, "(%.1f%%)" % (100.0*both/len(bd)))

# cell_info present & parseable
import json as J
ok=0; bad=0; nonempty=0
for b in bd:
    ci=b.get("cell_info")
    if not ci: continue
    nonempty+=1
    try:
        arr=J.loads(ci) if isinstance(ci,str) else ci
        if isinstance(arr,list) and len([1 for v in arr if fnum(v) is not None])>=2: ok+=1
        else: bad+=1
    except: bad+=1
print("\ncell_info: present=%d  parseable=%d  unparseable=%d" % (nonempty, ok, bad))
