"""
合并式脚本：运营总览数据增强
- dashboard.battery_product_city: 电池产品 x 城市 矩阵（从 agreement_detail 聚合）
- dashboard.city_drill: 城市钻取数据（用户数/网点数/换电柜数/电池数/各区域明细）
- 更新 overview.cabinet_online / overview.battery_online（从 device 明细实时算）

用法：python scripts/enrich_dashboard_ops.py
依赖：读取 data/dashboard_data.json，写回（合并式，不破坏其他 key）
"""

import json
import os
import sys
from collections import defaultdict, Counter

JSON_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'dashboard_data.json')


def main():
    with open(JSON_PATH, 'r', encoding='utf-8') as f:
        D = json.load(f)

    # ── 1. 电池产品 × 城市矩阵 ──
    agr = D.get('user', {}).get('agreement_detail', [])
    city_prod = defaultdict(Counter)
    for r in agr:
        city = r.get('city') or ''
        prod = r.get('battery_product') or '(空)'
        city_prod[city][prod] += 1

    # 输出结构：list of {city, total, products:[{name,count,pct}]}
    bp_city_list = []
    for city, prods in sorted(city_prod.items(), key=lambda x: -sum(x[1].values())):
        total = sum(prods.values())
        prod_list = [{'name': n, 'count': c, 'pct': round(c / total * 100, 1)}
                     for n, c in prods.most_common(10)]
        bp_city_list.append({'city': city, 'total': total, 'products': prod_list})

    D.setdefault('dashboard', {})['battery_product_city'] = bp_city_list
    print(f"[1] battery_product_city: {len(bp_city_list)} cities")

    # ── 2. 城市钻取数据（含用户数 + 区域层级）──
    sites = D.get('site', {}).get('detail', [])
    cab = D.get('device', {}).get('cabinet_detail', [])
    bat = D.get('device', {}).get('battery_detail', [])

    # 用户按城市聚合（去重 phone）
    city_users = defaultdict(set)
    for r in agr:
        city = r.get('city') or ''
        phone = r.get('phone') or ''
        if phone:
            city_users[city].add(phone)

    # 网点/换电柜/电池 按城市
    city_sites = Counter((r.get('city') or '') for r in sites)
    city_cabs = Counter((r.get('city') or '') for r in cab)
    city_bats = Counter()
    for r in bat:
        c = r.get('city') or r.get('location') or ''
        city_bats[c] += 1

    # 在线数
    city_cab_on = Counter()
    for r in cab:
        c = r.get('city') or ''
        if r.get('is_online') == '在线':
            city_cab_on[c] += 1

    city_bat_on = Counter()
    for r in bat:
        c = r.get('city') or r.get('location') or ''
        if r.get('online') == '在线':
            city_bat_on[c] += 1

    # 所有出现过的城市
    all_cities = set(city_users.keys()) | set(city_sites.keys()) | set(city_cabs.keys()) | set(city_bats.keys())

    geo = D.get('geo', {})
    uca_map = {}  # city → [{area, count}]
    if geo.get('user_city_area'):
        for item in geo['user_city_area']:
            uca_map[item['city']] = item.get('areas', [])

    city_drill = []
    for city in sorted(all_cities, key=lambda c: -(len(city_users.get(c, [])) + city_sites.get(c, 0))):
        entry = {
            'city': city,
            'users': len(city_users.get(city, [])),
            'sites': city_sites.get(city, 0),
            'cabs': city_cabs.get(city, 0),
            'bats': city_bats.get(city, 0),
            'cab_on': city_cab_on.get(city, 0),
            'bat_on': city_bat_on.get(city, 0),
            'areas': []
        }
        # 附加区域明细（来自 geo.user_city_area）
        for area_info in uca_map.get(city.replace('省', '').split('市')[0] + '市' if '市' not in city else city, []):
            # 尝试匹配城市名
            pass
        # 直接用城市名匹配
        for ci_key in [city, city.replace('省', ''), city.split('市')[0] + '市']:
            if ci_key in uca_map:
                entry['areas'] = uca_map[ci_key]
                break
        city_drill.append(entry)

    D['dashboard']['city_drill'] = city_drill
    print(f"[2] city_drill: {len(city_drill)} cities with user/site/cab/bat counts")

    # ── 3. 补全 overview.cabinet_online / battery_online ──
    ov = D.setdefault('overview', {})
    cab_total = len(cab)
    bat_total = len(bat)
    ov['cabinet_total'] = cab_total
    ov['battery_total'] = bat_total
    ov['cabinet_online'] = sum(1 for r in cab if r.get('is_online') == '在线')
    ov['battery_online'] = sum(1 for r in bat if r.get('online') == '在线')
    print(f"[3] overview online: cabinet {ov['cabinet_online']}/{cab_total}, battery {ov['battery_online']}/{bat_total}")

    # ── 4. 网点类型分布（尝试从 site.detail 的 industry 或其他字段推断）──
    # 检查是否有可用字段
    if sites:
        sample = sites[0]
        type_candidates = [k for k in sample.keys() if 'type' in k.lower() or 'industry' in k.lower() or 'category' in k.lower()]
        print(f"[4] site type candidate fields: {type_candidates}")
        # 如果有 industry 字段，统计分布
        if 'industry' in sample:
            ind_dist = Counter((r.get('industry') or '(空)') for r in sites)
            D['dashboard']['site_industry_dist'] = dict(ind_dist.most_common(20))
            print(f"    industry distribution: {dict(ind_dist.most_common(10))}")

    # ── 写回 ──
    with open(JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(D, f, ensure_ascii=False, separators=(',', ':'))
    print(f"\nDone! JSON written back ({os.path.getsize(JSON_PATH)/1024/1024:.0f}MB)")


if __name__ == '__main__':
    main()
