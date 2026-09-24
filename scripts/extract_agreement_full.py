# -*- coding: utf-8 -*-
"""
全量用户协议明细抽取（t_exchange_agreement, is_del=0, ~12.18万条）
输出：data/agreement_full.json （独立文件，供体积方案评估与 lite 注入）

相较原 extract_dashboard.py 的 agreement_detail，本脚本补齐：
  - site_id            签约网点ID
  - business_id        签约业务员ID (sign_site_business_id)
  - merchant_id/name/phone   商户（经 t_site.merchant_id -> t_merchant, 手机取 lp_phone 法人手机）
  - guide_id/name/phone      导购 (sign_site_store_employee_id -> t_site_store_employee)
并移除大体积低价值字段 battery_sns（前端未展示，占 23MB）。
"""
import io, json, os, sys, time, datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(BASE)
sys.stdout.reconfigure(encoding='utf-8')

import pymysql

T0 = time.time()
def log(m):
    print('[%6.1fs] %s' % (time.time() - T0, m), flush=True)

DB = json.load(io.open('config/backup_config.json', encoding='utf-8'))
DB.pop('workers', None)
conn = pymysql.connect(**DB)
cur = conn.cursor()

def q(sql, many=True):
    cur.execute(sql)
    return cur.fetchall() if many else cur.fetchone()

def ms2str(ms):
    if not ms:
        return ''
    try:
        return (datetime.datetime.utcfromtimestamp(int(ms) / 1000) +
                datetime.timedelta(hours=8)).strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return ''

NOW_MS = int(time.time() * 1000)

def remain_days(expire_ms):
    if not expire_ms:
        return '—'
    d = (int(expire_ms) - NOW_MS) / 86400000.0
    if d < 0:
        return '已过期'
    return '%d天' % int(d + 0.999)

def overdue_days(expire_ms):
    if not expire_ms:
        return 0
    d = (NOW_MS - int(expire_ms)) / 86400000.0
    return int(d) if d > 0 else 0

def deposit_deduct(status, bind, unbind):
    if unbind:
        return '已划扣/已解绑'
    if bind:
        return '正常(已绑定)'
    return '未缴纳' if (status or '') != 'on' else '—'

# ---------- 辅助映射 ----------
log('构建辅助映射…')
guide_map = {}
for r in q("SELECT id,name,phone FROM t_site_store_employee WHERE is_del=0"):
    guide_map[r[0]] = (r[1] or '', r[2] or '')
log('  导购 %d' % len(guide_map))

promoter_map = {}
try:
    for r in q("SELECT id,name,phone FROM t_promoter WHERE is_del=0"):
        promoter_map[r[0]] = (r[1] or '', r[2] or '')
except Exception as e:
    log('  t_promoter 跳过: %s' % str(e)[:80])
log('  推广员 %d' % len(promoter_map))

# 网点 -> (merchant_id, area, street, community)
site_map = {}
for r in q("SELECT id,merchant_id,area,street,community FROM t_site WHERE is_del=0"):
    site_map[r[0]] = (r[1] or 0, r[2] or '', r[3] or '', r[4] or '')
log('  网点 %d' % len(site_map))

merchant_map = {}
for r in q("SELECT id,name,lp_phone FROM t_merchant WHERE is_del=0"):
    merchant_map[r[0]] = (r[1] or '', r[2] or '')
log('  商户 %d' % len(merchant_map))

# 代理商名称（库中无 t_agency，取订单表 DISTINCT 兜底）
agency_map = {}
for r in q("SELECT DISTINCT agency_id,agency_name FROM t_exchange_order "
           "WHERE agency_name IS NOT NULL AND agency_name<>''"):
    if r[0] and r[0] not in agency_map:
        agency_map[r[0]] = r[1]
log('  代理商 %d' % len(agency_map))

# 消费者名下在绑电池数（只留数量，不留 SN 串）
bat_cnt = {}
try:
    for r in q("SELECT user_id,COUNT(DISTINCT battery_sn) FROM t_bike_battery_bind_log "
               "WHERE is_del=0 AND bind_status='bind' GROUP BY user_id"):
        bat_cnt[r[0]] = r[1] or 0
except Exception as e:
    log('  电池绑定跳过: %s' % str(e)[:80])
log('  电池绑定用户 %d' % len(bat_cnt))

# ---------- 主查询 ----------
log('主查询 t_exchange_agreement…')
SQL = """
SELECT a.id, a.type, a.service_platform, a.user_id, u.phone, u.username,
       bp.name, a.bike_count, bk.device_sn, bs.name,
       a.battery_standard_rent, a.exchange_scheme_fee, a.rent_package_id, rp.name, rp.fee,
       a.sys_city_name, a.site_id, s.name, a.agency_id,
       s.distributor_id, d.name, a.sign_site_business_id, a.sign_site_business_name,
       a.company_name, a.activation_time, a.rent_expire_time, a.is_rent_permanent_valid,
       a.deposit_fee, a.deposit_bind_time, a.deposit_unbind_time, a.status, a.create_time,
       a.is_first, a.promoter_id, a.site_sale_scenario_name, a.contract_type,
       a.contract_period, a.contract_expire_time, a.deposit_status, a.deposit_payway,
       a.stop_time, a.is_contract, a.battery_product_id, a.battery_series_id,
       a.battery_lessor, a.battery_take_status, a.is_auto_pay, a.is_replacement,
       a.is_bike_share, a.remark, a.sign_site_store_employee_id
FROM t_exchange_agreement a
LEFT JOIN t_user u ON a.user_id=u.id
LEFT JOIN t_battery_product bp ON a.battery_product_id=bp.id
LEFT JOIN t_bike bk ON a.id=bk.exchange_agreement_id AND bk.is_binding=1
LEFT JOIN t_battery_brand bs ON a.battery_series_id=bs.id
LEFT JOIN t_exchange_rent_package rp ON a.rent_package_id=rp.id
LEFT JOIN t_site s ON a.site_id=s.id
LEFT JOIN t_distributor d ON s.distributor_id=d.id
WHERE a.is_del=0
ORDER BY a.create_time DESC
"""
rows = q(SQL)
log('  返回 %d 行' % len(rows))
conn.close()

# ---------- 组装 ----------
log('组装记录…')
DASH = '—'
out = []
for r in rows:
    sid = r[16] or 0
    sm = site_map.get(sid, (0, '', '', ''))
    mid = sm[0]
    mrc = merchant_map.get(mid, ('', ''))
    gid = r[50] or 0
    gd = guide_map.get(gid, ('', ''))
    pid = r[33] or 0
    pm = promoter_map.get(pid, ('', ''))
    aid_ag = r[18] or 0
    exp = r[25]

    out.append({
        'agreement_id': r[0],
        'type': r[1] or DASH,
        'channel': r[2] or DASH,
        'user_id': r[3] or 0,
        'phone': r[4] or DASH,
        'user_name': r[5] or DASH,
        'battery_product': r[6] or DASH,
        'bike_count': r[7] or 0,
        'bike_sn': r[8] or DASH,
        'battery_model': r[9] or DASH,
        'battery_standard_rent': (r[10] or 0) / 100.0,
        'exchange_scheme_fee': (r[11] or 0) / 100.0,
        'rent_package_id': r[12] or 0,
        'rent_package_name': r[13] or DASH,
        'package_fee': (r[14] or 0) / 100.0,
        'city': r[15] or DASH,
        'area': sm[1] or DASH,
        'street': sm[2] or DASH,
        'community': sm[3] or DASH,
        'site_id': sid,
        'site_name': r[17] or DASH,
        'agency_id': aid_ag,
        'agency_name': agency_map.get(aid_ag) or DASH,
        'distributor_id': r[19] or 0,
        'distributor_name': r[20] or DASH,
        'business_id': r[21] or 0,
        'business_name': r[22] or DASH,
        'merchant_id': mid,
        'merchant_name': mrc[0] or DASH,
        'merchant_phone': mrc[1] or DASH,
        'guide_id': gid,
        'guide_name': gd[0] or DASH,
        'guide_phone': gd[1] or DASH,
        'promoter_id': pid,
        'promoter_name': pm[0] or DASH,
        'promoter_phone': pm[1] or DASH,
        'company_name': r[23] or DASH,
        'activation_time': ms2str(r[24]),
        'expire_time': ms2str(exp),
        'is_permanent': 1 if r[26] else 0,
        'deposit_fee': (r[27] or 0) / 100.0,
        'deposit_bind_time': r[28] or 0,
        'deposit_unbind_time': r[29] or 0,
        'status': r[30] or DASH,
        'create_time': ms2str(r[31]),
        'is_first': r[32] or 0,
        'sale_scenario': r[34] or DASH,
        'contract_type': r[35] or DASH,
        'contract_period': r[36] or 0,
        'contract_expire': ms2str(r[37]),
        'deposit_status': r[38] or DASH,
        'deposit_payway': r[39] or DASH,
        'stop_time': ms2str(r[40]),
        'is_contract': r[41] or 0,
        'battery_product_id': r[42] or 0,
        'battery_series_id': r[43] or 0,
        'battery_lessor': r[44] or DASH,
        'battery_take_status': r[45] or DASH,
        'is_auto_pay': r[46] or 0,
        'is_replacement': r[47] or 0,
        'is_bike_share': r[48] or 0,
        'remark': r[49] or DASH,
        'remain_days': remain_days(exp),
        'overdue_days': (overdue_days(exp) if (r[30] or '') == 'owe_rent' else 0),
        'deposit_deduct': deposit_deduct(r[38], r[28], r[29]),
        'battery_count': bat_cnt.get(r[3], 0),
    })

log('组装完成 %d 条，字段 %d 个' % (len(out), len(out[0])))

os.makedirs('data', exist_ok=True)
P = 'data/agreement_full.json'
with io.open(P, 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, separators=(',', ':'))
log('已写 %s  %.2f MB' % (P, os.path.getsize(P) / 1024 / 1024))

# ---------- 覆盖率速检 ----------
N = len(out)
print()
print('=== 关键筛选维度覆盖率 ===')
for f in ['city', 'area', 'street', 'battery_product', 'agency_id', 'agency_name',
          'user_id', 'phone', 'site_id', 'site_name', 'business_id', 'business_name',
          'merchant_id', 'merchant_phone', 'guide_id', 'guide_phone']:
    n = sum(1 for r in out if r.get(f) not in (None, '', DASH, 0))
    dv = len({r.get(f) for r in out if r.get(f) not in (None, '', DASH, 0)})
    print('  %-18s %6d/%d (%5.1f%%)  去重 %d' % (f, n, N, n * 100.0 / N, dv))
