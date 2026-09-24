#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fix_warnings.py — 一键补齐所有 ⚠️ 数据（用户KPI / 销售business / 设备仓库 / 网点状态）
数据源：已有 dashboard_data.json（含 CSV 补列后的丰富字段）
输出：直接改写 dashboard_data.json，注入新计算的 KPI / 聚合维度
"""
import json, os, time, sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(ROOT, '..', 'data', 'dashboard_data.json')

def load():
    with open(DATA_PATH, encoding='utf-8') as f:
        return json.load(f)

def save(D):
    with open(DATA_PATH, 'w', encoding='utf-8') as f:
        json.dump(D, f, ensure_ascii=False, separators=(',', ':'))

def parse_date(s):
    """Parse various date formats to datetime or None."""
    if not s or s in ('-', '', 'null', None): return None
    s = str(s).strip()
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M:%S.%f',
                '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d', '%Y/%m/%d'):
        try: return datetime.strptime(s[:19], fmt)
        except: pass
    return None

def parse_num(s):
    """Parse number string like '45.00元' or '1次' -> float."""
    if not s or s in ('-', '', 'null', None): return 0.0
    s = str(s).strip().replace('元', '').replace('次', '').replace('辆', '').replace('天', '').replace(',', '').strip()
    try: return float(s)
    except: return 0.0

def fmt_int(n):
    return int(n) if n is not None else 0

# ============================================================
# PART 1: 用户看板 KPI（补齐 drawUserKpi 所有 ⚠️ 字段）
# ============================================================
def compute_user_kpis(D):
    print("=" * 60)
    print("PART 1: 用户看板 KPI 计算")
    t0 = time.time()

    U = D.get('user', {})
    ud = U.get('detail', [])
    today = datetime.now().strftime('%Y-%m-%d')
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    today_dt = datetime.now()

    # --- 基础计数 ---
    total = len(ud)
    status_cnt = Counter(str(r.get('status', '') or '') for r in ud)
    working = status_cnt.get('working', 0)
    cancelled = status_cnt.get('cancelled', 0)
    stop = status_cnt.get('stop', 0)
    unsubscribing = status_cnt.get('unsubscribing', 0)
    owe_rent = status_cnt.get('owe_rent', 0)

    # --- 当日新增注册（按 activate_time / create 字段）---
    new_today = 0
    new_yesterday = 0
    reg_field = None
    for k in ['activate_time', 'activate', 'create', 'activate_date']:
        if any(r.get(k) for r in ud[:100]):
            reg_field = k
            break
    if reg_field:
        for r in ud:
            d = parse_date(r.get(reg_field))
            if d:
                ds = d.strftime('%Y-%m-%d')
                if ds == today: new_today += 1
                elif ds == yesterday: new_yesterday += 1
        print(f"  注册字段: {reg_field}, 今日新增: {new_today}, 昨日: {new_yesterday}")
    else:
        print("  ⚠ 未找到注册时间字段")

    # --- 押金快到期(≤3天 / ≤7天 / ≤30天) ---
    deposit_3d = 0
    deposit_7d = 0
    deposit_30d = 0
    expire_soon_users = []
    for r in ud:
        exp = parse_date(r.get('expire') or r.get('expire_time') or r.get('current_package_expire'))
        if exp and exp >= today_dt:
            days_left = (exp - today_dt).days
            if days_left <= 3:
                deposit_3d += 1
                expire_soon_users.append(r.get('phone', ''))
            if days_left <= 7: deposit_7d += 1
            if days_left <= 30: deposit_30d += 1
    print(f"  押金快到期: ≤3天={deposit_3d}, ≤7天={deposit_7d}, ≤30天={deposit_30d}")

    # --- 已过期用户（协议已过期但状态可能未更新）---
    expired = 0
    for r in ud:
        exp = parse_date(r.get('expire') or r.get('expire_time'))
        if exp and exp < today_dt and r.get('status') == 'working':
            expired += 1
    print(f"  已过期仍显示生效: {expired}")

    # --- 换电频次（从 exchange orders 按 user_id 聚合）---
    EX = D.get('site', {}).get('exchange', [])
    uid_swaps = Counter()
    uid_amount = defaultdict(float)
    for r in EX:
        uid = r.get('take_user_id')
        if uid:
            uid_swaps[uid] += 1
            amt = parse_num(r.get('amount', 0))
            uid_amount[uid] += amt

    # 映射到 user.detail 的 phone/user_id
    phone_uid_map = {}
    for r in ud:
        uid = r.get('user_id')
        ph = str(r.get('phone', '')).strip()
        if uid: phone_uid_map[str(uid)] = r
        if ph: phone_uid_map[f'ph:{ph}'] = r

    # 高频用户：exchange 中 swap≥6 的用户（或样本中 top 阈值）
    high_freq_uids = {uid for uid, cnt in uid_swaps.items() if cnt >= 6}
    mid_freq_uids = {uid for uid, cnt in uid_swaps.items() if 2 <= cnt <= 5}
    low_freq_uids = {uid for uid, cnt in uid_swaps.items() if cnt == 1}

    # 也用 renewal_count 作为补充指标（来自协议 CSV）
    renewal_vals = []
    for r in ud:
        rc = parse_num(r.get('renewal_count', 0))
        renewal_vals.append(rc)

    # 高/低价值用户：按 total_paid_amount 排序分位
    paid_amounts = []
    for r in ud:
        amt = parse_num(r.get('total_paid_amount', 0))
        paid_amounts.append((r.get('phone', ''), amt))
    paid_amounts.sort(key=lambda x: x[1], reverse=True)
    n = len(paid_amounts)
    top_10_pct = int(n * 0.1) if n > 10 else max(1, n // 10)
    bot_10_pct = int(n * 0.1) if n > 10 else max(1, n // 10)

    high_value_phones = set(p[0] for p in paid_amounts[:top_10_pct] if p[1] > 0)
    low_value_phones = set(p[0] for p in paid_amounts[-bot_10_pct:] if p[1] == 0)

    total_consumption = sum(p[1] for p in paid_amounts)

    # 租期用户（is_contract=1 或 contract_type 非 day）
    contract_users = sum(1 for r in ud
                        if r.get('is_contract') == 1 or str(r.get('contract_type', '') or '') in ('month', 'quarter', 'year', 'season'))

    # 离职用户定义：status=cancelled 且有 violation 或 long-expired
    resigned = sum(1 for r in ud if r.get('status') in ('cancelled', 'stop') and
                   parse_num(r.get('violation_count', 0)) > 0)
    # 更宽泛的离职：已退订/终止超过30天的
    long_gone = 0
    for r in ud:
        if r.get('status') in ('cancelled', 'stop'):
            term = parse_date(r.get('terminate_time'))
            if term and (today_dt - term).days > 30:
                long_gone += 1

    # 企业用户 vs 个人用户
    enterprise_users = sum(1 for r in ud if r.get('enterprise_name') and r.get('enterprise_name') not in ('-', '', 'null'))
    personal_users = total - enterprise_users

    # 构造 KPI 对象
    kpi = {
        'total': total,
        'working': working,
        'owe_rent': owe_rent,
        'unsub': cancelled + stop + unsubscribing,
        'cancelled': cancelled,
        'stop': stop,
        'deposit_soon_3d': deposit_3d,
        'deposit_soon_7d': deposit_7d,
        'deposit_soon_30d': deposit_30d,
        'new_today': new_today,
        'new_yesterday': new_yesterday,
        'reg_field': reg_field or '',
        'high_freq': len(high_freq_uids),
        'mid_freq': len(mid_freq_uids),
        'low_freq_sample': len(low_freq_uids),  # 仅 exchange 样本内
        'high_value': len(high_value_phones),
        'low_value': len(low_value_phones),
        'total_consumption': round(total_consumption, 2),
        'contract_users': contract_users,
        'enterprise_users': enterprise_users,
        'personal_users': personal_users,
        'resigned_violation': resigned,
        'long_gone': long_gone,
        'expired_still_working': expired,
        'exchange_sample_users': len(uid_swaps),  # exchange 样本中出现的独立用户数
        'avg_renewal': round(sum(renewal_vals) / max(len(renewal_vals), 1), 2) if renewal_vals else 0,
    }

    # 写入 DATA.user.kpi
    if 'user' not in D: D['user'] = {}
    D['user']['kpi'] = kpi

    # 同时为每个 user 注入 swap_count（从 exchange 聚合）
    uid_swap_dict = dict(uid_swaps)
    uid_amt_dict = dict(uid_amount)
    injected_swap = 0
    for r in ud:
        uid = str(r.get('user_id', '')) if r.get('user_id') else ''
        if uid and uid in uid_swap_dict:
            r['_swap_count'] = uid_swap_dict[uid]
            r['_swap_amount'] = round(uid_amt_dict.get(uid, 0), 2)
            injected_swap += 1
    print(f"  注入换电次数到 user.detail: {injected_swap}/{total}")

    print(f"  KPI 汇总:")
    for k, v in sorted(kpi.items()):
        print(f"    {k}: {v}")
    print(f"  耗时: {time.time()-t0:.1f}s")
    return kpi


# ============================================================
# PART 2: 销售 business 维度（补齐 s-biz-* 四图）
# ============================================================
def compute_sales_business(D):
    print("\n" + "=" * 60)
    print("PART 2: 销售 business 维度计算")
    t0 = time.time()

    S = D.get('sales', {})
    sd = S.get('detail', [])

    if not sd:
        print("  ⚠ sales.detail 为空，跳过")
        return

    # 从 user.detail（就是销售明细）聚合
    U = D.get('user', {})
    ud = U.get('detail', [])

    # 2a. 销量排前10门店（按 site_name 分组计数）
    site_sales = Counter()
    site_revenue = defaultdict(float)
    for r in ud:
        sn = r.get('site_name') or r.get('site') or ''
        if sn:
            site_sales[sn] += 1
            site_revenue[sn] += parse_num(r.get('last_package_price', 0))

    top_sites = site_sales.most_common(15)
    biz_topstore = [{'site': s, 'count': c, 'revenue': round(site_revenue[s], 2)} for s, c in top_sites]

    # 2b. 不同套餐销售数量
    pkg_sales = Counter()
    pkg_revenue = defaultdict(float)
    for r in ud:
        pn = r.get('package') or r.get('current_package_name') or r.get('last_package_name') or ''
        if pn:
            pkg_sales[pn] += 1
            pkg_revenue[pn] += parse_num(r.get('last_package_price', 0))

    biz_pkg = [{'package': p, 'count': c, 'revenue': round(pkg_revenue[p], 2)} for p, c in pkg_sales.most_common(20)]

    # 2c. 各协议状态用户（已有 U.by_status，这里增强）
    biz_status = []
    status_detail = Counter(r.get('status', '') for r in ud)
    CN_MAP = {'working': '生效中', 'cancelled': '已退订', 'stop': '已终止',
              'paused': '暂停', 'owe_rent': '欠租', 'wait_activate': '待激活',
              'unsubscribing': '退订中'}
    for st, cnt in status_detail.most_common():
        biz_status.append({'status': st, 'name': CN_MAP.get(st, st), 'count': cnt})

    # 2d. 销售趋势（按 create 月份分组）
    monthly = Counter()
    for r in ud:
        d = parse_date(r.get('create') or r.get('activate_time'))
        if d:
            monthly[d.strftime('%Y-%m')] += 1
    biz_trend = [{'month': m, 'count': c} for m, c in sorted(monthly.items())]

    # 2e. 各城市销售排行
    city_sales = Counter()
    for r in ud:
        c = r.get('city') or ''
        if c: city_sales[c] += 1
    biz_city = [{'city': c, 'count': ct} for c, ct in city_sales.most_common(20)]

    # 2f. 业务员销售排行
    sm_sales = Counter()
    for r in ud:
        sm = r.get('current_salesman_name') or r.get('site_salesman_name') or ''
        if sm: sm_sales[sm] += 1
    biz_salesman = [{'salesman': s, 'count': c} for s, c in sm_sales.most_common(20)]

    # 2g. 代理商销售排行
    ag_sales = Counter()
    for r in ud:
        ag = r.get('agency') or ''
        if ag: ag_sales[ag] += 1
    biz_agency = [{'agency': a, 'count': c} for a, c in ag_sales.most_common(20)]

    business = {
        'topstore': biz_topstore,
        'package': biz_pkg,
        'status': biz_status,
        'trend': biz_trend,
        'city': biz_city,
        'salesman': biz_salesman,
        'agency': biz_agency,
        '_generated_at': datetime.now().isoformat(),
    }
    if 'sales' not in D: D['sales'] = {}
    D['sales']['business'] = business

    print(f"  门店TOP: {len(biz_topstore)}")
    print(f"  套餐种类: {len(biz_pkg)}")
    print(f"  状态种类: {len(biz_status)}")
    print(f"  趋势月数: {len(biz_trend)}")
    print(f"  城市数: {len(biz_city)}")
    print(f"  业务员数: {len(biz_salesman)}")
    print(f"  代理商数: {len(biz_agency)}")
    print(f"  耗时: {time.time()-t0:.1f}s")


# ============================================================
# PART 3: 设备仓库电池分类（补齐设备看板 ⚠️）
# ============================================================
def compute_device_warehouse(D):
    print("\n" + "=" * 60)
    print("PART 3: 设备仓库电池分类")
    t0 = time.time()

    BAT = D.get('device', {}).get('battery_detail', [])
    CAB = D.get('device', {}).get('cabinet_detail', [])

    if not BAT:
        print("  ⚠ battery_detail 为空，跳过")
        return

    # 3a. 按 slot_type（仓位类型）分类 → 仓库分布
    slot_dist = Counter()
    slot_online = Counter()   # 各仓库类型在线数
    slot_offline = Counter()  # 各仓库类型离线数
    slot_high_temp = Counter()  # bms_max_temp > 45°C
    slot_high_cycle = Counter()  # cycle_count > 300
    slot_soc = defaultdict(list)  # 各仓库 SOC 列表

    for b in BAT:
        st = b.get('slot_type') or b.get('slot_name') or '未知'
        # 归类到标准仓库
        std_slot = classify_slot(st)
        slot_dist[std_slot] += 1

        on = str(b.get('online', '') or '')
        if '在线' in on: slot_online[std_slot] += 1
        else: slot_offline[std_slot] += 1

        try:
            if float(b.get('bms_max_temp', 0) or 0) > 45: slot_high_temp[std_slot] += 1
        except: pass
        try:
            if int(b.get('cycle_count', 0) or 0) > 300: slot_high_cycle[std_slot] += 1
        except: pass
        try:
            soc = int(b.get('soc', 0) or 0)
            slot_soc[std_slot].append(soc)
        except: pass

    # SOC 统计
    soc_stats = {}
    for st, socs in slot_soc.items():
        if socs:
            soc_stats[st] = {
                'avg': round(sum(socs) / len(socs), 1),
                'min': min(socs),
                'max': max(socs),
                'count': len(socs),
            }

    warehouse = {
        'by_slot': [{ 'slot': s, 'count': c, 'online': slot_online.get(s, 0),
                     'offline': slot_offline.get(s, 0),
                     'high_temp': slot_high_temp.get(s, 0),
                     'high_cycle': slot_high_cycle.get(s, 0),
                   } for s, c in slot_dist.most_common()],
        'soc_stats': soc_stats,
        'total': len(BAT),
        'online_total': sum(slot_online.values()),
        'offline_total': sum(slot_offline.values()),
        'high_temp_total': sum(slot_high_temp.values()),
        'high_cycle_total': sum(slot_high_cycle.values()),
    }

    # 3b. 换电柜统计
    cab_stats = {
        'total': len(CAB),
        'fault': sum(1 for c in CAB if int(c.get('error', 0) or 0) > 0),
        'online': sum(1 for c in CAB if str(c.get('is_online', '') or '') in ('1', '在线', True)),
        'by_city': Counter(c.get('city', '') or '' for c in CAB if c.get('city')),
        'by_type': Counter(c.get('cabinet_type', '') or '' for c in CAB if c.get('cabinet_type')),
    }

    # 3c. 故障电池明细（可展示列表）
    fault_bats = []
    for b in BAT:
        reasons = []
        try:
            if float(b.get('bms_max_temp', 0) or 0) > 50: reasons.append('高温')
        except: pass
        try:
            if int(b.get('cycle_count', 0) or 0) > 500: reasons.append('高循环')
        except: pass
        if reasons:
            fault_bats.append({
                'sn': b.get('sn'), 'site_name': b.get('site_name'),
                'slot_type': b.get('slot_type'), 'soc': b.get('soc'),
                'temp': b.get('bms_max_temp'), 'cycle': b.get('cycle_count'),
                'reasons': ','.join(reasons), 'online': b.get('online'),
            })

    dev_stats = {
        'warehouse': warehouse,
        'cabinet': cab_stats,
        'fault_batteries': fault_bats[:200],  # 前200条故障
        'fault_battery_count': len(fault_bats),
    }
    if 'device' not in D: D['device'] = {}
    D['device']['stats'] = dev_stats

    print(f"  电池总数: {len(BAT)}")
    print(f"  仓库类型分布:")
    for wh in warehouse['by_slot'][:10]:
        print(f"    {wh['slot']}: {wh['count']} (在线{wh['online']} 离线{wh['offline']} 高温{wh['high_temp']})")
    print(f"  换电柜: {cab_stats['total']} 台, 故障 {cab_stats['fault']}")
    print(f"  故障电池: {len(fault_bats)}")
    print(f"  耗时: {time.time()-t0:.1f}s")


def classify_slot(raw_slot):
    """将原始仓位名归入标准仓库类别."""
    raw = str(raw_slot).lower()
    if any(k in raw for k in ['车辆', 'car', 'vehicle']): return '车辆仓库'
    if any(k in raw for k in ['网点', 'site', '门店', 'store']): return '网点仓库'
    if any(k in raw for k in ['运营平台', '平台', 'platform', 'operation']): return '运营平台仓库'
    if any(k in raw for k in ['代理', 'agent', '收货仓']): return '代理商仓库'
    if any(k in raw for k in ['换电柜', 'cabinet', '柜']): return '换电柜仓库'
    if any(k in raw for k in ['故障', 'fault', '损坏', ' scrap']): return '故障/报废'
    if any(k in raw for k in ['在途', 'transit', '运输']): return '在途'
    return '其他/未识别'


# ============================================================
# PART 4: 网点中间状态 + 单网点详情补全
# ============================================================
def compute_site_enrich(D):
    print("\n" + "=" * 60)
    print("PART 4: 网点中间状态补全")
    t0 = time.time()

    sites = D.get('site', {}).get('detail', [])
    if not sites:
        print("  ⚠ site.detail 为空，跳过")
        return

    # 网点状态分布
    status_dist = Counter(s.get('status', '') for s in sites)
    type_dist = Counter(s.get('type', '') for s in sites)
    city_dist = Counter(s.get('city', '') for s in sites if s.get('city'))

    # 有换电数据的网点（从 exchange_rank_30d 或 exchange_count）
    ex_rank = D.get('site', {}).get('exchange_rank_30d', [])
    ex_count = D.get('site', {}).get('exchange_count', {})

    # 网点业务员信息（从 site_info_pro CSV 已补的字段）
    has_business = sum(1 for s in sites if s.get('business') or s.get('current_salesman_name'))
    has_contact = sum(1 for s in sites if s.get('contact_person_name') or s.get('contact_person_tel'))
    has_address = sum(1 for s in sites if s.get('address'))

    site_stats = {
        'status_breakdown': dict(status_dist.most_common()),
        'type_breakdown': dict(type_dist.most_common()),
        'city_count': len(city_dist),
        'has_business_info': has_business,
        'has_contact': has_contact,
        'has_address': has_address,
        'sites_with_exchange_data': len(ex_count),
        'exchange_rank_size': len(ex_rank),
    }

    # 为每个网点注入更多计算字段
    for s in sites:
        sid = str(s.get('id', '') or s.get('name', ''))
        # 如果有 exchange_count 数据，注入
        if sid in ex_count:
            s['_exchange_count'] = ex_count[sid]

    if 'site' not in D: D['site'] = {}
    D['site']['stats'] = site_stats

    print(f"  网点总数: {len(sites)}")
    print(f"  状态分布: {dict(status_dist.most_common(10))}")
    print(f"  类型分布: {dict(type_dist.most_common(10))}")
    print(f"  有业务员: {has_business}, 有联系人: {has_contact}, 有地址: {has_address}")
    print(f"  有换电数据: {len(ex_count)} 个网点")
    print(f"  耗时: {time.time()-t0:.1f}s")


# ============================================================
# PART 5: 运维告警占位（用现有数据模拟）
# ============================================================
def compute_ops_placeholder(D):
    print("\n" + "=" * 60)
    print("PART 5: 运维告警占位数据")
    t0 = time.time()

    BAT = D.get('device', {}).get('battery_detail', [])
    CAB = D.get('device', {}).get('cabinet_detail', [])

    # 从电池数据生成模拟告警
    warnings = []
    warn_id = 1

    # 高温告警
    for b in BAT:
        try:
            temp = float(b.get('bms_max_temp', 0) or 0)
            if temp > 50:
                warnings.append({
                    'id': warn_id, 'type': '高温预警', 'level': '紧急' if temp > 55 else '一般',
                    'device_type': '电池', 'device_sn': b.get('sn'),
                    'site_name': b.get('site_name'), 'value': f'{temp}°C',
                    'time': b.get('last_report', ''), 'status': '未解决',
                })
                warn_id += 1
        except: pass

    # 离线告警（长时间离线的电池）
    for b in BAT[:500]:
        try:
            off = b.get('last_offline', '')
            on = b.get('last_online', '')
            if on and off:
                last_on = parse_date(on)
                last_off = parse_date(off)
                if last_on and last_off and (last_off - last_on).days > 30:
                    warnings.append({
                        'id': warn_id, 'type': '长期离线', 'level': '一般',
                        'device_type': '电池', 'device_sn': b.get('sn'),
                        'site_name': b.get('site_name'), 'value': f'离线{(last_off-last_on).days}天',
                        'time': off, 'status': '未解决',
                    })
                    warn_id += 1
        except: pass

    # 换电柜故障告警
    for c in CAB:
        try:
            err = int(c.get('error', 0) or 0)
            if err > 0:
                warnings.append({
                    'id': warn_id, 'type': '设备故障', 'level': '紧急' if err > 3 else '一般',
                    'device_type': '换电柜', 'device_sn': c.get('sn'),
                    'site_name': c.get('site_name'), 'value': f'{err}个故障仓',
                    'time': c.get('last_upload', ''), 'status': '未解决',
                })
                warn_id += 1
        except: pass

    ops_data = {
        'warnings': warnings[:300],
        'warning_total': len(warnings),
        'urgent': sum(1 for w in warnings if w.get('level') == '紧急'),
        'normal': sum(1 for w in warnings if w.get('level') == '一般'),
        'resolved': 0,
        'by_type': Counter(w['type'] for w in warnings),
        'generated_from': 'battery bms_max_temp>50 + cabinet error>0 + offline>30d',
    }
    if 'ops' not in D: D['ops'] = {}
    D['ops']['warn_data'] = ops_data

    urg = ops_data["urgent"]
    nrm = ops_data["normal"]
    print(f"  告警总数: {len(warnings)} (紧急{urg} 一般{nrm})")
    print(f"  耗时: {time.time()-t0:.1f}s")


# ============================================================
# MAIN
# ============================================================
if __name__ == '__main__':
    print(f"加载 {DATA_PATH} ...")
    t_start = time.time()
    D = load()
    size_before = os.path.getsize(DATA_PATH) // 1024 // 1024
    print(f"JSON 大小: {size_before}MB")

    compute_user_kpis(D)
    compute_sales_business(D)
    compute_device_warehouse(D)
    compute_site_enrich(D)
    compute_ops_placeholder(D)

    save(D)
    size_after = os.path.getsize(DATA_PATH) // 1024 // 1024
    print(f"\n✅ 完成! JSON: {size_before}MB → {size_after}MB (+{size_after-size_before}MB)")
    print(f"   总耗时: {time.time()-t_start:.1f}s")
