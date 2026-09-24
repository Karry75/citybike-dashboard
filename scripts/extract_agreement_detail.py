# -*- coding: utf-8 -*-
"""重抽用户协议明细表（35列精确口径）+ 详情抽屉数据（车辆列表/电池数）。
数据源：
  - exchange_agreement_pro_*.csv  (主协议，56列)
  - agreement_bike_data_pro_*.csv (车辆列表，按 换电服务协议ID)
  - agreement_battery_data_pro_*.csv (电池列表，按 换电服务协议 id)
输出：dashboard_data.json 新增
  user.agreement_detail  : 35列协议明细数组
  user.agreement_bikes   : {agreement_id: [车辆行]}
  user.agreement_battery : {agreement_id: [电池行]}
  user.agreement_bat_cnt : {agreement_id: 电池数}
"""
import json, csv, os, glob
from datetime import datetime, date

BASE = r"D:/workboddy file/dudu分析/citybike_backup"
DL = r"C:/Users/Karry/Downloads"

def latest(pat):
    fs = glob.glob(os.path.join(DL, pat))
    if not fs: return None
    # 选最大的（避免选到 12KB 的小采样版）
    return max(fs, key=os.path.getsize)

AGREE = latest("exchange_agreement_pro_*.csv")
BIKE  = latest("agreement_bike_data_pro_*.csv")
BAT   = latest("agreement_battery_data_pro_*.csv")
print("AGREE:", os.path.basename(AGREE) if AGREE else None)
print("BIKE :", os.path.basename(BIKE) if BIKE else None)
print("BAT  :", os.path.basename(BAT) if BAT else None)

def s(v):
    return (v or "").replace("\t","").replace("\r","").replace("\n","").strip()

# ── 1. 加载现有 user.detail 用于 昵称 关联 ──
data = json.load(open(os.path.join(BASE,"data/dashboard_data.json"), encoding="utf-8"))
uid_name = {}
for r in data.get("user",{}).get("detail",[]):
    uid_name[str(r.get("user_id"))] = r.get("name") or "—"
print("user.detail 昵称索引:", len(uid_name))

# ── 2. 车辆 / 电池列表（按协议ID）──
agr_bikes = {}
agr_bat   = {}
agr_bat_cnt = {}
if BIKE:
    with open(BIKE, encoding="utf-8-sig", errors="replace") as f:
        for r in csv.DictReader(f):
            aid = s(r.get("换电服务协议ID"))
            if not aid: continue
            agr_bikes.setdefault(aid, []).append({
                "vehicle_id": s(r.get("车辆ID")), "vehicle_name": s(r.get("车辆名称")),
                "battery_sn": s(r.get("电池SN")), "soc": s(r.get("当前电量")),
                "online": s(r.get("电池在线状态")), "loc_addr": s(r.get("最后一次有效定位地址")),
                "loc_time": s(r.get("最后一次有效定位时间")), "exchange_order_id": s(r.get("换电订单ID")),
                "borrow_type": s(r.get("借出方式")), "borrow_cab": s(r.get("借出换电柜SN")),
                "borrow_site": s(r.get("借出网点名称")), "borrow_time": s(r.get("借出时间")),
                "exchange_cnt": s(r.get("累计换电数")), "fail_cnt": s(r.get("失败记录订单次数"))
            })
if BAT:
    with open(BAT, encoding="utf-8-sig", errors="replace") as f:
        for r in csv.DictReader(f):
            aid = s(r.get("换电服务协议 id"))
            if not aid: continue
            agr_bat.setdefault(aid, []).append({
                "battery_id": s(r.get("电池ID")), "sn": s(r.get("电池设备SN")),
                "product": s(r.get("电池产品名称")), "soc": s(r.get("电池电量")),
                "online": s(r.get("在线状态")), "last_flow": s(r.get("最后流通时间")),
                "loc_addr": s(r.get("最后一次有效定位地址")), "loc_time": s(r.get("最后一次有效定位时间"))
            })
            agr_bat_cnt[aid] = agr_bat_cnt.get(aid,0)+1
print("车辆列表协议数:", len(agr_bikes), " | 电池列表协议数:", len(agr_bat))

# ── 3. 主协议 → 35列 ──
TODAY = date.today()
rows = []
first_sign_by_user = {}  # user_id -> 最早激活时间
with open(AGREE, encoding="utf-8-sig", errors="replace") as f:
    for r in csv.DictReader(f):
        aid = s(r.get("换电服务协议ID"))
        if not aid: continue
        uid = s(r.get("用户ID"))
        activate = s(r.get("协议激活时间"))
        # 首次签约：同一 user_id 中激活时间最早者
        if uid:
            if uid not in first_sign_by_user or (activate and activate < first_sign_by_user[uid]):
                first_sign_by_user[uid] = activate
        rows.append({
            "agreement_id": aid,
            "type": s(r.get("协议类型")),
            "sales_scene": s(r.get("销售场景名称")),
            "user_id": uid,
            "user_name": uid_name.get(uid, "—"),
            "phone": s(r.get("用户手机号")),
            "battery_product": s(r.get("电池产品")),
            "vehicle_count": s(r.get("车辆数量")),
            "battery_count": agr_bat_cnt.get(aid, "—"),
            "remaining": s(r.get("租期剩余时长")),
            "package_price": s(r.get("当前使用套餐实付价格")),
            "rent_package": s(r.get("当前使用套餐名称")),
            "city": s(r.get("城市")), "area": s(r.get("地区")), "street": s(r.get("街道")),
            "site_name": s(r.get("签约网点名称")),
            "deposit_status": s(r.get("押金状态")),
            "deposit_method": s(r.get("押金方式")),
            "deposit_fee": s(r.get("押金金额")),
            "deposit_deduct": "—",  # CSV 无此字段
            "agency_id": s(r.get("签约代理商ID")),
            "channel_id": s(r.get("网点渠道商ID")),
            "guide_id": s(r.get("网点导购ID")),
            "guide_name": s(r.get("网点导购名称")),
            "promoter_id": s(r.get("推广员id")),
            "promoter_name": s(r.get("推广员名称")),
            "create": "—",  # 协议CSV无创建时间
            "activate": activate,
            "terminate": s(r.get("协议终止时间")),
            "expire": s(r.get("协议到期时间")),
            "status": s(r.get("协议状态")),
            "is_contract": s(r.get("是否合约车")),
            "auto_renew": "—",  # CSV 无
            "is_exchange": "—",  # CSV 无
            "is_long_term": "—",  # CSV 无
            "battery_lease_org": "—",  # CSV 无
            # 派生
            "_pkg_expire": s(r.get("当前套餐到期时间"))
        })

# 计算 欠租天数 + 是否首次签约
for rr in rows:
    # 首次签约
    rr["first_sign"] = "是" if (rr["user_id"] and first_sign_by_user.get(rr["user_id"])==rr["activate"]) else "否"
    # 欠租天数 = today - 当前套餐到期时间（仅当已过期）
    pe = rr.pop("_pkg_expire","")
    rr["overdue_days"] = "—"
    if pe:
        try:
            d = datetime.strptime(pe[:19], "%Y-%m-%d %H:%M:%S").date()
            if d < TODAY:
                rr["overdue_days"] = (TODAY - d).days
        except Exception:
            try:
                d = datetime.strptime(pe[:10], "%Y-%m-%d").date()
                if d < TODAY: rr["overdue_days"] = (TODAY - d).days
            except Exception:
                pass

print("协议明细行数:", len(rows))

# ── 4. 写回 JSON ──
data.setdefault("user", {})["agreement_detail"] = rows
data["user"]["agreement_bikes"] = agr_bikes
data["user"]["agreement_battery"] = agr_bat
data["user"]["agreement_bat_cnt"] = agr_bat_cnt
# 概览口径
data["user"]["agreement_total"] = len(rows)

json.dump(data, open(os.path.join(BASE,"data/dashboard_data.json"),"w",encoding="utf-8"),
          ensure_ascii=False, separators=(",",":"))
print("WROTE dashboard_data.json  agreement_detail=", len(rows),
      " bikes=", len(agr_bikes), " battery=", len(agr_bat))
