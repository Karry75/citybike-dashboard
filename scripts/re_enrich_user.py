#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""re_enrich_user.py — 用大版协议 CSV (85K行) 重新补全 user.detail"""
import csv, json, time, os

DATA_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'dashboard_data.json')
CSV_PATH = os.path.join(os.path.expanduser('~'), 'Downloads', 'exchange_agreement_pro_20260630225550.csv')

AGR_CSV_COLS = {
    '换电服务协议ID':'agreement_id','协议类型':'agreement_type','用户ID':'user_id',
    '用户手机号':'phone','企业ID':'enterprise_id','企业名称':'enterprise_name',
    '企业管理员手机号':'enterprise_admin_phone','电池产品':'battery_product',
    '签约网点ID':'site_id','签约网点名称':'site_name','协议状态':'status',
    '协议激活时间':'activate_time','协议终止时间':'terminate_time',
    '电池系列ID':'battery_series_id','使用时长':'usage_duration',
    '租期剩余时长':'rent_remaining','协议到期时间':'expire_time',
    '签约代理商ID':'agency_id','网点渠道商ID':'channel_id',
    '城市':'city','地区':'area','街道':'street',
    '网点导购ID':'guide_id','网点导购名称':'guide_name','网点导购手机号':'guide_phone',
    '导购是否店长':'guide_is_manager','签约网点业务员ID':'site_salesman_id',
    '签约网点业务员名称':'site_salesman_name','网点当前业务员ID':'current_salesman_id',
    '网点当前业务员名称':'current_salesman_name',
    '首次签约套餐ID':'first_package_id','首次签约套餐名称':'first_package_name',
    '首次签约套餐原价':'first_package_original_price','首次签约套餐实付价格':'first_package_price',
    '最后购买套餐ID':'last_package_id','最后购买套餐名称':'last_package_name',
    '最后购买套餐原价':'last_package_original_price','最后购买套餐实付价格':'last_package_price',
    '车辆数量':'vehicle_count','当前使用套餐ID':'current_package_id',
    '当前使用套餐名称':'current_package_name','当前使用套餐原价':'current_package_original_price',
    '当前使用套餐实付价格':'current_package_price','当前套餐到期时间':'current_package_expire',
    '累计续租次数':'renewal_count','累计续租金额':'renewal_amount',
    '累计服务单支付金额':'total_paid_amount','累计服务单退款金额':'total_refund_amount',
    '累计服务单优惠券支付金额':'coupon_paid_amount',
    '销售场景id':'scene_id','推广员id':'promoter_id','推广员名称':'promoter_name',
    '销售场景名称':'scene_name','是否合约车':'is_contract_vehicle',
    '合约方案ID':'contract_scheme_id','合约方案名称':'contract_scheme_name',
    '押金状态':'deposit_status','押金方式':'deposit_method','押金金额':'deposit_amount',
    '违约次数':'violation_count','违约合计时长':'violation_total_duration','违约支付金额':'violation_amount',
}

NUMERIC = {'agreement_id','user_id','enterprise_id','site_id','agency_id','channel_id',
           'guide_id','site_salesman_id','current_salesman_id',
           'first_package_id','last_package_id','current_package_id',
           'vehicle_count','renewal_count',
           'scene_id','promoter_id','contract_scheme_id','deposit_amount',
           'violation_count','violation_total_duration','violation_amount'}
FLOATS = {'renewal_amount','total_paid_amount','total_refund_amount','coupon_paid_amount',
          'first_package_original_price','first_package_price','last_package_original_price','last_package_price',
          'current_package_original_price','current_package_price','deposit_amount'}

print('Loading large agreement CSV (85K rows) ...')
t0 = time.time()
rows = []
uid_map = {}
with open(CSV_PATH, encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames or []
    col_map = {cn: AGR_CSV_COLS.get(cn, cn.lower().replace(' ', '_').replace('\uff08', '(').replace('\uff09', ')')) for cn in fieldnames}
    for raw in reader:
        row = {}
        for cn, en in col_map.items():
            v = raw.get(cn, '').strip().replace('\n', '').replace('\r', '').replace('\t', '')
            if en in NUMERIC:
                try: row[en] = int(v) if v else 0
                except ValueError:
                    try: row[en] = float(v) if v else 0.0
                    except ValueError: row[en] = v or 0
            elif en in FLOATS:
                try: row[en] = float(v) if v else 0.0
                except ValueError: row[en] = v or 0
            else:
                row[en] = v if v else ''
        uid = str(row.get('user_id', ''))
        if uid and uid not in uid_map:
            uid_map[uid] = len(rows)
            rows.append(row)
        elif uid in uid_map:
            existing = rows[uid_map[uid]]
            for k, val in row.items():
                if val and not existing.get(k):
                    existing[k] = val

print(f'  Loaded {len(rows)} unique users in {time.time()-t0:.1f}s')

# 回挂到 JSON
with open(DATA_PATH, encoding='utf-8') as f:
    D = json.load(f)

existing_ud = D.get('user', {}).get('detail', [])
merged = 0
for eu in existing_ud:
    uid = str(eu.get('user_id', ''))
    if uid in uid_map:
        src = rows[uid_map[uid]]
        for k, v in src.items():
            if v and k not in eu:
                eu[k] = v
        merged += 1
print(f'Merged by user_id: {merged}/{len(existing_ud)}')

# 手机号二次匹配
phone_map = {}
for ar in rows:
    ph = str(ar.get('phone', '')).strip()
    if ph:
        phone_map[ph] = ar
extra = 0
for eu in existing_ud:
    if not eu.get('enterprise_name'):
        ph = str(eu.get('phone', '')).strip()
        if ph in phone_map:
            src = phone_map[ph]
            for k, v in src.items():
                if v and k not in eu:
                    eu[k] = v
            extra += 1
print(f'Merged by phone (extra): {extra}')

# 写回
with open(DATA_PATH, 'w', encoding='utf-8') as f:
    json.dump(D, f, ensure_ascii=False, separators=(',', ':'))

size = os.path.getsize(DATA_PATH) // 1024 // 1024
print(f'Done! JSON={size}MB, user.detail enriched with {len(rows)} agreement records')
