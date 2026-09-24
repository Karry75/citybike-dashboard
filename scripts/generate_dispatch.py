# -*- coding: utf-8 -*-
"""
generate_dispatch.py —— 区域电池调度分析数据灌库
从《租车套餐明细20260526.xlsx》的 Sheet5（网点明细，290行）抽取网点级真值：
  - 柜内电池数量
  - 近3天 / 近7天 / 近1个月 / 近3个月 换电次数
  - 换电柜状态（判断柜内电池是否可能虚高）
灌入 data/dashboard_data.json 的 dispatch.site 段，供前端 drawDevDispatch 使用。
不依赖数据库连接（数据来自用户已导出的 WPS 明细），可直接执行。
"""
import openpyxl, json, os, shutil

SRC = r'C:/Users/Karry/Desktop/租车套餐明细20260526.xlsx'
DATA = 'data/dashboard_data.json'

def load_sheet(name):
    wb = openpyxl.load_workbook(SRC, read_only=True, data_only=True)
    ws = wb[name]
    rows = list(ws.iter_rows(values_only=True))
    hdr = rows[0]
    idx = {str(c).strip(): j for j, c in enumerate(hdr) if c}
    out = []
    for r in rows[1:]:
        if not any(c is not None and str(c).strip() for c in r):
            continue
        out.append({k: (r[j] if j < len(r) else None) for k, j in idx.items()})
    return out

def num(v):
    if v is None:
        return 0
    s = str(v).strip().replace(',', '')
    try:
        return float(s)
    except Exception:
        return 0

sheet = load_sheet('Sheet5')
sites = []
for r in sheet:
    sid = r.get('网点id')
    name = r.get('网点名称')
    if not name:
        continue
    sites.append({
        'sid': int(sid) if str(sid).strip().isdigit() else str(sid),
        'name': str(name).strip(),
        'city': (r.get('城市') or '').strip(),
        'area': (r.get('区域') or '').strip(),
        'cab_status': (r.get('换电柜状态') or '').strip(),
        'cab_cnt': int(num(r.get('换电柜数量'))),
        'bat_cnt': int(num(r.get('柜内电池数量'))),
        'swap3': int(num(r.get('近3天换电次数'))),
        'swap7': int(num(r.get('近7天换电次数'))),
        'swap30': int(num(r.get('近1个月换电次数'))),   # 近1个月 ≈ 30天近似
        'swap90': int(num(r.get('近3个月换电次数'))),
    })

# 备份原 json（防误覆盖）
if os.path.exists(DATA):
    shutil.copy(DATA, DATA + '.bak')

dd = json.load(open(DATA, encoding='utf-8'))
dd['dispatch'] = {
    'generated': '2026-07-26',
    'source': '租车套餐明细20260526.xlsx!Sheet5',
    'note': '柜内电池数量/换电次数均为业务系统真值；近30天用近1个月近似（数据源无精确30天列）',
    'site_count': len(sites),
    'site': sites,
}
json.dump(dd, open(DATA, 'w', encoding='utf-8'), ensure_ascii=False)

print('OK dispatch sites =', len(sites))
# 速览（1:3，近7天）
bat_total = sum(s['bat_cnt'] for s in sites)
swap7_total = sum(s['swap7'] for s in sites)
need7_3 = sum(s['swap7'] / 7 / 3 for s in sites)
net = sum(s['bat_cnt'] - s['swap7'] / 7 / 3 for s in sites)
lack = sum(1 for s in sites if s['bat_cnt'] - s['swap7'] / 7 / 3 < 0)
off = sum(1 for s in sites if s['cab_status'] and s['cab_status'] != '正常')
print('柜内电池总量 =', bat_total)
print('近7天总换电 =', swap7_total)
print('1:3 所需电池(7天) ≈', round(need7_3, 1))
print('净可取(柜内-所需) ≈', round(net, 1))
print('需补网点数(净<0) ≈', lack)
print('换电柜状态≠正常网点数 =', off)
