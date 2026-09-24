# -*- coding: utf-8 -*-
"""P0 跨源聚合补丁：注入 device.anomaly_12 (12类异常) 与 risk (风险监控) 两个新对象。
所有数字均来自 dashboard_data.json 已有字段，不编造；未上报类型标 0 并注明。
"""
import json, datetime

SRC = 'data/dashboard_data.json'
print('loading', SRC, '...')
with open(SRC, 'r', encoding='utf-8') as f:
    D = json.load(f)
TODAY = '2026-07-28'
gen = f'数据快照 {TODAY}（源 dashboard_data.json 已落盘字段聚合）'

# ========== 1. device.anomaly_12（12 类设备异常，框架来自知识库《资产管理手册》）==========
fault = D.get('device', {}).get('fault', {})
fault_list = fault.get('list', [])
cab_kpis = D.get('device', {}).get('cabinet_kpis', {})
cab_off = cab_kpis.get('offline', 0)
cab_fault = cab_kpis.get('fault', 0)          # 306
bat_off = D.get('device', {}).get('battery_offline', 0)   # 44496
# 从 fault.list 细分
from collections import Counter
ft = Counter(r.get('fault_type', '?') for r in fault_list)
hi_temp = ft.get('高温', 0)
hi_cycle = ft.get('高循环', 0)
slot_err = sum(v for k, v in ft.items() if k.startswith('仓口错误'))  # 306

anomaly_12 = {
    'generated': gen,
    'source': 'device.fault.list(332) + device.cabinet_kpis + device.battery_offline',
    'note': '12 类框架取自知识库《嘟嘟换电资产管理手册》；实际数据仅覆盖仓口/高温/高循环/离线，其余类型平台暂未上报，标 0。',
    'rows': [
        {'type': '柜机-仓口错误', 'cat': '柜机', 'count': slot_err, 'level': '高',
         'desc': '换电柜仓口通信/机械故障（含(1)(2)(3)级）'},
        {'type': '柜机-离线>12h', 'cat': '柜机', 'count': cab_off, 'level': '中',
         'desc': '柜机失联超过 12 小时，无法提供换电服务'},
        {'type': '柜机-空仓', 'cat': '柜机', 'count': 0, 'level': '中', 'note': '未上报',
         'desc': '柜内无可用电池，用户无法借电'},
        {'type': '柜机-满仓', 'cat': '柜机', 'count': 0, 'level': '低', 'note': '未上报',
         'desc': '柜内满电池无空位，用户无法还电'},
        {'type': '柜机-换电失败≥3次', 'cat': '柜机', 'count': 0, 'level': '高', 'note': '未上报',
         'desc': '同一柜连续换电失败≥3次'},
        {'type': '柜机-门未关', 'cat': '柜机', 'count': 0, 'level': '中', 'note': '未上报',
         'desc': '仓门未正常关闭'},
        {'type': '柜机-烟感告警', 'cat': '柜机', 'count': 0, 'level': '紧急', 'note': '未上报',
         'desc': '烟雾感应告警'},
        {'type': '柜机-水浸告警', 'cat': '柜机', 'count': 0, 'level': '紧急', 'note': '未上报',
         'desc': '水浸感应告警'},
        {'type': '柜机-通讯超时', 'cat': '柜机', 'count': 0, 'level': '中', 'note': '未上报',
         'desc': '与平台通讯超时'},
        {'type': '电池-高温', 'cat': '电池', 'count': hi_temp, 'level': '高',
         'desc': '电池温度超阈值（>50℃），存在热失控风险'},
        {'type': '电池-高循环', 'cat': '电池', 'count': hi_cycle, 'level': '中',
         'desc': '循环次数超阈值，寿命衰减'},
        {'type': '电池-电流越限', 'cat': '电池', 'count': 0, 'level': '高', 'note': '未上报',
         'desc': '充放电电流超阈值'},
    ],
}
total_anom = sum(r['count'] for r in anomaly_12['rows'])
anomaly_12['total'] = total_anom
anomaly_12['reported_types'] = sum(1 for r in anomaly_12['rows'] if r['count'] > 0)
D['device']['anomaly_12'] = anomaly_12
print(f'  device.anomaly_12: {total_anom} 异常 / {anomaly_12["reported_types"]} 类已上报')

# ========== 2. risk（风险监控大屏聚合）==========
U = D.get('user', {}).get('kpi', {})
OV = D.get('overview', {})
FIN = D.get('finance', {})
AOW = D.get('analytics', {}).get('owe', {})
OPS = D.get('ops', {})
SITE = D.get('site', {})

warn_data = OPS.get('warn_data', {})
wo = OPS.get('work_order', {})

risk = {
    'generated': gen,
    'users': {
        'silent_30d': D.get('user', {}).get('low_freq_30d', 0),     # 21754 真实
        'owe': FIN.get('overdue_count', 0) or AOW.get('owe_agreements', 0),  # 1404 真值
        'unsub': U.get('unsub', 0),                                  # 1696 (采样，真值待DB)
        'long_gone': U.get('long_gone', 0),                          # 959 (采样)
        'expired_still_working': U.get('expired_still_working', 0),  # 85 (采样)
        'resigned_violation': U.get('resigned_violation', 0),        # 123 (采样)
    },
    'device': {
        'cab_offline': cab_off,        # 2717
        'bat_offline': bat_off,        # 44496
        'cab_fault': cab_fault,       # 306
        'bat_fault': fault.get('kpis', {}).get('battery', 0),  # 26
    },
    'site': {
        'total': OV.get('site_total', 0),     # 11064
        'open': 0, 'closed': 0, 'pipeline': 0,
    },
    'ops': {
        'warn_total': warn_data.get('warning_total', 0),
        'warn_urgent': warn_data.get('urgent', 0),
        'warn_resolved': warn_data.get('resolved', 0),
        'work_order_overdue': wo.get('overdue', 0),
        'work_order_total': wo.get('total', 0),
    },
    'finance': {
        'overdue_count': FIN.get('overdue_count', 0),
        'penalty_count': AOW.get('penalty_count', 0),
    },
}
# 网点状态映射
for r in SITE.get('status_9', []):
    lbl = r.get('label', '')
    c = r.get('count', 0)
    if lbl == '已开业':
        risk['site']['open'] = c
    elif lbl == '已关闭':
        risk['site']['closed'] = c
    else:
        risk['site']['pipeline'] += c
D['risk'] = risk
print(f'  risk: 沉默{risk["users"]["silent_30d"]} 欠租{risk["users"]["owe"]} 退订{risk["users"]["unsub"]} '
      f'柜离线{risk["device"]["cab_offline"]} 电池离线{risk["device"]["bat_offline"]} '
      f'告警{risk["ops"]["warn_total"]}(紧急{risk["ops"]["warn_urgent"]}) 工单逾期{risk["ops"]["work_order_overdue"]}')

with open(SRC, 'w', encoding='utf-8') as f:
    json.dump(D, f, ensure_ascii=False)
print('OK: wrote', SRC)
