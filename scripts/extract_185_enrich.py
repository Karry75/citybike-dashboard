# -*- coding: utf-8 -*-
"""
#185 补全：车辆总览 / 套餐情况表 / 业务员业绩
==============================================
1. DATA.user.vehicle ← user.agreement_bikes(dict) + rental.rows(array) 合并
2. 套餐情况表数据 ← sales.business.package(已有20条) + sales.detail 聚合
3. 业务员业绩 ← sales.promoter_rank(10条) + sales.business.salesman(20条) 验证

产物：data/dashboard_data.json 的 user.vehicle 新增
"""
import json, os
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "data", "dashboard_data.json")


def main():
    print("载入 dashboard_data.json ...")
    D = json.load(open(OUT, encoding='utf-8'))

    # ── 1. 车辆总览（user.vehicle）───────────────────────────────
    print("\n[1/3] 车辆总览 user.vehicle ...")
    U = D.setdefault('user', {})

    # 1a) 从 agreement_bikes 派生（dict key=agreement_id）
    bikes_dict = U.get('agreement_bikes', {})
    vehicles = []
    for agr_id, bdata in bikes_dict.items():
        if isinstance(bdata, dict):
            vehicles.append({
                'vid': bdata.get('vehicle_id') or bdata.get('id', ''),
                'sn': bdata.get('sn') or bdata.get('device_sn', '') or bdata.get('plate', ''),
                'img': bdata.get('img', ''),
                'frame': bdata.get('frame', '') or bdata.get('idcard', ''),
                'addr': bdata.get('site', '') or bdata.get('area', ''),
                'agreement': agr_id,
                'bat_cnt': len(bdata.get('batteries', [])) if isinstance(bdata.get('batteries'), list) else (bdata.get('bat_cnt') or 0),
                'bat_sn': '',
                'flow': '',
                'loc': bdata.get('city', '') or '',
                '_source': 'agreement_bikes',
            })

    # 1b) 从 rental.rows 补充（WPS 导入的 134 条）
    rental = D.get('rental', {}).get('rows', [])
    seen_agr = {v['agreement'] for v in vehicles if v.get('agreement')}
    for r in rental:
        agr = r.get('agreement', '')
        if not agr or agr in seen_agr:
            if agr and agr in seen_agr:
                # 补充已有记录的字段
                for v in vehicles:
                    if v['agreement'] == agr:
                        if not v.get('sn') and r.get('plate'): v['sn'] = r['plate']
                        if not v.get('img') and r.get('img'): v['img'] = r['img']
                        break
            continue
        vehicles.append({
            'vid': r.get('uid', ''),
            'sn': r.get('plate', ''),
            'img': r.get('img', ''),
            'frame': r.get('idcard', ''),
            'addr': r.get('site', ''),
            'agreement': agr,
            'bat_cnt': 0,
            'bat_sn': '',
            'flow': '',
            'loc': r.get('area', ''),
            '_source': 'rental',
        })
        seen_agr.add(agr)

    U['vehicle'] = vehicles
    print(f"  user.vehicle: {len(vehicles)} 辆 (agreement_bikes + rental)")

    # ── 2. 套餐情况表验证 ─────────────────────────────────────
    print("\n[2/3] 套餐情况表验证 ...")
    S = D.setdefault('sales', {})
    biz = S.get('business', {})

    # 确保 package 数据存在且有内容
    pkg_list = biz.get('package', [])
    detail_rows = S.get('detail', [])
    if not pkg_list and detail_rows:
        # 从 sales.detail 聚合套餐
        pkg_agg = Counter()
        for r in detail_rows:
            p = (r.get('package') or '') or '未知'
            pkg_agg[p] += 1
        pkg_list = [{'name': k, 'count': v, 'type': '电量卡(推测)' if '电量' in k or '换电' in k else '租期卡(推测)'}
                    for k, v in pkg_agg.most_common(30)]
        biz['package'] = pkg_list
        print(f"  business.package: 从 detail 聚合 {len(pkg_list)} 条")
    else:
        print(f"  business.package: 已有 {len(pkg_list)} 条")

    # ── 3. 业务员业绩验证 ───────────────────────────────────────
    print("\n[3/3] 业务员业绩验证 ...")
    promoter = S.get('promoter_rank', [])
    salesman = biz.get('salesman', [])
    print(f"  promoter_rank: {len(promoter)} 条")
    print(f"  business.salesman: {len(salesman)} 条")

    # 如果 salesman 为空，从 detail 聚合
    if not salesman and detail_rows:
        sm_agg = Counter()
        for r in detail_rows:
            s = (r.get('promoter') or '') or '未知导购'
            sm_agg[s] += 1
        salesman = [{'name': k, 'count': v} for k, v in sm_agg.most_common(30)]
        biz['salesman'] = salesman
        print(f"  business.salesman: 从 detail 聚合 {len(salesman)} 条")

    # ── 写回 ────────────────────────────────────────────────────
    json.dump(D, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print(f"\nDONE -> {OUT}")
    print(f"  user.vehicle: {len(vehicles)} 辆")
    print(f"  sales.business.package: {len(biz.get('package',[]))} 套餐")
    print(f"  sales.promoter_rank: {len(S.get('promoter_rank',[]))} 导购")
    print(f"  sales.business.salesman: {len(biz.get('salesman',[]))} 业务员")


if __name__ == '__main__':
    main()
