# -*- coding: utf-8 -*-
"""
设备模块全量补全 · #183
======================
从现有 JSON 数据派生/重组以下空缺模块：

1. device.fault.list ← device.stats.fault_batteries(26条真数据) + 柜故障派生
2. device.fault.kpis ← 从 list 聚合
3. DATA.warehouse ← device.stats.warehouse.by_slot 派生列表格式
4. device.inventory ← 标注"无来源CSV，需DB抽取"
5. device.transfer ← 标注"无来源CSV，需DB抽取"

产物：data/dashboard_data.json 的 device 段 + 新增 warehouse 顶层键
"""
import json, os, sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "data", "dashboard_data.json")


def main():
    print("载入 dashboard_data.json ...")
    D = json.load(open(OUT, encoding='utf-8'))
    DEV = D.setdefault('device', {})

    # ── 1. 故障设备（fault）───────────────────────────────────────
    print("\n[1/4] 故障设备 ...")
    STATS = DEV.get('stats', {})
    fault_bats = STATS.get('fault_batteries', [])       # 26 条真数据
    cab_detail = DEV.get('cabinet_detail', [])           # 6260 条
    bat_detail = DEV.get('battery_detail', [])           # 49683 条

    fault_list = []
    # 1a) 已有故障电池（来自 stats 派生）
    seen_sn = set()
    for fb in fault_bats:
        rec = {
            'device_id': fb.get('sn', ''),
            'device_type': '电池',
            'fault_type': fb.get('reasons', ''),
            'fault_time': '',                          # 原数据无时间字段
            'location': fb.get('site_name', '') or fb.get('slot_type', ''),
            'status': '处理中' if fb.get('online') == '离线' else '监控中',
            'handler': '',
            'handle_time': '',
            '_source': 'stats.fault_batteries',
            'soc': fb.get('soc'),
            'temp': str(fb.get('temp', '')),
            'cycle': fb.get('cycle', 0),
        }
        fault_list.append(rec)
        seen_sn.add(rec['device_id'])

    # 1b) 从 cabinet_detail 派生故障柜（slots_error > 0 或 离线超7天）
    import datetime
    now_ts = datetime.datetime(2026, 7, 28)  # 快照日期
    fault_cab_count = 0
    for cab in cab_detail:
        err = int(cab.get('slots_error', 0) or 0)
        is_ol = str(cab.get('is_online', ''))
        # 故障定义：仓口错误 > 0 或 状态异常
        if err > 0 or '故障' in str(cab.get('backup_status', '')):
            fault_list.append({
                'device_id': cab.get('sn', cab.get('device_sn', '')),
                'device_type': '换电柜',
                'fault_type': f'仓口错误({err})' if err > 0 else str(cab.get('backup_status', '')),
                'fault_time': cab.get('last_online', ''),
                'location': cab.get('site_name', ''),
                'status': '离线' if is_ol == '离线' else '异常',
                'handler': '',
                'handle_time': '',
                '_source': 'cabinet_detail.derived',
                'city': cab.get('city', ''),
            })
            fault_cab_count += 1

    # 1c) 从 battery_detail 派生高温/高循环电池（补充 stats 未覆盖的）
    hi_temp_cnt = 0
    hi_cycle_cnt = 0
    for bat in bat_detail:
        sn = bat.get('device_sn', '') or bat.get('sn', '')
        if sn in seen_sn:
            continue
        try:
            temp = float(bat.get('temperature', 0) or 0)
            cycle = int(bat.get('cycle_count', 0) or 0)
        except (ValueError, TypeError):
            continue
        reasons = []
        if temp >= 50:
            reasons.append(f'高温({temp}°C)')
            hi_temp_cnt += 1
        if cycle >= 500:
            reasons.append(f'高循环({cycle})')
            hi_cycle_cnt += 1
        if reasons:
            fault_list.append({
                'device_id': sn,
                'device_type': '电池',
                'fault_type': '+'.join(reasons),
                'fault_time': bat.get('last_online', ''),
                'location': bat.get('site_name', '') or bat.get('slot_type', ''),
                'status': '在线' if str(bat.get('online', '')) == '在线' else '离线',
                'handler': '',
                'handle_time': '',
                '_source': 'battery_detail.derived',
                'soc': bat.get('soc'),
                'temp': str(temp),
                'cycle': cycle,
            })
            seen_sn.add(sn)

    # KPIs
    bat_faults = [f for f in fault_list if f['device_type'] == '电池']
    cab_faults = [f for f in fault_list if f['device_type'] == '换电柜']
    fault_kpis = {
        'cabinet': len(cab_faults),
        'battery': len(bat_faults),
        'repaired': 0,     # 无维修记录来源
        'scrapped': 0,      # 无报废记录来源
    }
    DEV['fault'] = {'kpis': fault_kpis, 'list': fault_list}
    print(f"  fault: {len(fault_list)} 条 (柜{fault_cab_count} / 电池{len(bat_faults)})")

    # ── 2. 仓库（warehouse）───────────────────────────────────────
    print("\n[2/4] 仓库 ...")
    wh_stats = STATS.get('warehouse', {})
    by_slot = wh_stats.get('by_slot', [])

    # 构造平台仓库列表和代理商仓库列表
    platform_wh = []
    agent_wh = []
    for ws in by_slot:
        slot_name = ws.get('slot', '')
        rec = {
            'id': slot_name,
            'name': slot_name,
            'type': slot_name,
            'count': ws.get('count', 0),
            'online': ws.get('online', 0),
            'offline': ws.get('offline', 0),
            'high_temp': ws.get('high_temp', 0),
            'high_cycle': ws.get('high_cycle', 0),
        }
        if '平台' in slot_name or '运营' in slot_name:
            platform_wh.append(rec)
        elif '代理' in slot_name:
            agent_wh.append(rec)
        else:
            # 其他归入平台侧
            platform_wh.append(rec)

    # 尝试从 DB 抽取的旧数据恢复（如果存在）
    old_wh = D.get('warehouse')
    if isinstance(old_wh, dict) and (old_wh.get('platform') or old_wh.get('agent')):
        platform_wh = old_wh.get('platform', platform_wh)
        agent_wh = old_wh.get('agent', agent_wh)

    D['warehouse'] = {
        'platform': platform_wh,
        'agent': agent_wh,
        'total_warehouses': len(by_slot),
        'total_batteries': wh_stats.get('total', 0),
        'online_total': wh_stats.get('online_total', 0),
        'offline_total': wh_stats.get('offline_total', 0),
        'high_temp_total': wh_stats.get('high_temp_total', 0),
        'high_cycle_total': wh_stats.get('high_cycle_total', 0),
        'soc_stats': wh_stats.get('soc_stats', {}),
        '_note': '仓库列表由 device.stats.warehouse.by_slot 派生；详细仓库清单需连 DB 抽取 t_warehouse_* 表',
    }
    print(f"  warehouse: 平台{len(platform_wh)}类 / 代理{len(agent_wh)}类")

    # ── 3. 出入库（inventory）────────────────────────────────────
    print("\n[3/4] 出入库 ...")
    DEV.setdefault('inventory', {
        'kpis': {
            'pending_in': 0,
            'today_in': 0,
            'today_out': 0,
            'total': DEV.get('battery_total', 0),   # 用电池总量近似
        },
        'list': [],
        '_note': '出入库明细需连 DB 抽取 t_warehouse_operate_log 等表；本地无 CSV 来源',
    })
    print("  inventory: 标注待抽（无本地 CSV）")

    # ── 4. 调拨（transfer）────────────────────────────────────────
    print("\n[4/4] 调拨 ...")
    if not DEV.get('transfer'):
        DEV['transfer'] = []
    DEV['_transfer_note'] = '调拨记录需连 DB 抽取；本地无 CSV；当前为空'
    print("  transfer: 标注待抽（无本地 CSV）")

    # ── 写回 ────────────────────────────────────────────────────
    json.dump(D, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print(f"\nDONE -> {OUT}")
    print(f"  总故障记录: {len(fault_list)}")
    print(f"    - 换电柜故障: {fault_kpis['cabinet']}")
    print(f"    - 电池故障: {fault_kpis['battery']}")


if __name__ == '__main__':
    main()
