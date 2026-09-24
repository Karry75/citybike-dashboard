# -*- coding: utf-8 -*-
"""
全量押金套餐订单明细抽取（t_user_exchange_deposit_package_order, is_del=0, ~17.5万条）
输出：data/deposit_full.json

背景：
  用户口径中的「押金明细表 173,207 条」= 本表约 2026-07-15 的历史快照
  （2026-07-15 累计 173,178 / 07-16 累计 173,259，今日已增长到 175,000）。
  它与协议表 t_exchange_agreement（121,819 条）不是同一张表，故独立抽取、独立打包。

维度补齐策略（可追溯，绝不编造）：
  1) 主路径：o.exchange_agreement_id -> t_exchange_agreement 取 城市/网点/代理商/协议状态
     -> t_site 取 区域/街道/社区/商户/分销商         ... dim_source = '协议直连'
  2) 回退：exchange_agreement_id = 0（下单时未挂协议，约 2.8 万条）时，
     用 user_id 在协议表中找同一电池产品的协议；找不到则取该用户最早一条协议
                                                    ... dim_source = '按用户推断'
  3) 都找不到 -> 全部维度留 '—'                       ... dim_source = '无关联'
  前端可用 dim_source 列区分口径，避免把推断值当直连值用。
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
DB['connect_timeout'] = 20
conn = pymysql.connect(**DB)
cur = conn.cursor()

def q(sql):
    cur.execute(sql)
    return cur.fetchall()

def ms2str(ms):
    if not ms:
        return ''
    try:
        return (datetime.datetime.utcfromtimestamp(int(ms) / 1000) +
                datetime.timedelta(hours=8)).strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return ''

def yuan(v):
    return round((v or 0) / 100.0, 2)

DASH = '—'
YN = {1: '是', 0: '否'}

PAY_WAY_CN = {
    'alipay_free':         '支付宝免押(预授权冻结)',
    'alipay_free_app':     '支付宝免押(App)',
    'imprest':             '备用金抵扣',
    'unionpay_wechatmini': '银联(微信小程序)',
    'wechat':              '微信小程序支付',
    'wechat_app':          '微信App支付',
    'sys_free':            '系统免押',
    'offline':             '线下支付',
}
ORDER_STATUS_CN = {
    'created': '已创建', 'success': '成功', 'fail': '失败', 'refund': '已退款',
}
AGR_STATUS_CN = {
    'normal': '正常', 'owe_rent': '欠租', 'stop': '已停用', 'expire': '已过期',
    'unactivated': '未激活', 'refund': '已退订', 'cancel': '已取消',
}

# ---------------- 辅助映射 ----------------
log('构建辅助映射…')

# 网点 -> (name, area, street, community, merchant_id, distributor_id)
site_map = {}
for r in q("SELECT id,name,area,street,community,merchant_id,distributor_id "
           "FROM t_site WHERE is_del=0"):
    site_map[r[0]] = (r[1] or '', r[2] or '', r[3] or '', r[4] or '', r[5] or 0, r[6] or 0)
log('  网点 %d' % len(site_map))

merchant_map = {}
for r in q("SELECT id,name FROM t_merchant WHERE is_del=0"):
    merchant_map[r[0]] = r[1] or ''
log('  商户 %d' % len(merchant_map))

distributor_map = {}
try:
    for r in q("SELECT id,name FROM t_distributor WHERE is_del=0"):
        distributor_map[r[0]] = r[1] or ''
except Exception as e:
    log('  t_distributor 跳过: %s' % str(e)[:80])
log('  分销商 %d' % len(distributor_map))

# 代理商名称（库中无 t_agency，取订单表 DISTINCT 兜底，与协议抽取脚本口径一致）
agency_map = {}
for r in q("SELECT DISTINCT agency_id,agency_name FROM t_exchange_order "
           "WHERE agency_name IS NOT NULL AND agency_name<>''"):
    if r[0] and r[0] not in agency_map:
        agency_map[r[0]] = r[1]
log('  代理商 %d' % len(agency_map))

bp_map = {}
for r in q("SELECT id,name FROM t_battery_product"):
    bp_map[r[0]] = r[1] or ''
log('  电池产品 %d' % len(bp_map))

# 协议维度：id -> (city, site_id, agency_id, status, user_id, battery_product_id, create_time)
log('加载协议维度表…')
agr_map = {}
user_agr = {}          # user_id -> [协议id, ...]（按 create_time 升序）
for r in q("SELECT id,sys_city_name,site_id,agency_id,status,user_id,battery_product_id,create_time "
           "FROM t_exchange_agreement WHERE is_del=0 ORDER BY create_time ASC"):
    agr_map[r[0]] = (r[1] or '', r[2] or 0, r[3] or 0, r[4] or '', r[5] or 0, r[6] or 0, r[7] or 0)
    user_agr.setdefault(r[5] or 0, []).append(r[0])
log('  协议 %d，覆盖用户 %d' % (len(agr_map), len(user_agr)))

# ---------------- 主查询 ----------------
log('主查询 t_user_exchange_deposit_package_order…')
SQL = """
SELECT id, oem_id, exchange_agreement_id, battery_product_id, package_id, bike_id,
       user_id, user_name, user_phone,
       fee, real_fee, deposit_fee, other_fee, package_name,
       pay_way_table_name, pay_way, is_discounts, order_status, is_present,
       is_pay, pay_time, is_withdraw, withdraw_time,
       is_deposit_refund, deposit_refund_time, is_other_refund,
       refund_fee, refund_deposit_fee, refund_other_fee, trade_no,
       create_time, update_time
FROM t_user_exchange_deposit_package_order
WHERE is_del=0
ORDER BY create_time DESC
"""
rows = q(SQL)
log('  返回 %d 行' % len(rows))
conn.close()

# ---------------- 组装 ----------------
log('组装记录…')
out = []
stat_src = {'协议直连': 0, '按用户推断': 0, '无关联': 0}

for r in rows:
    (oid, oem_id, agr_id, bp_id, pkg_id, bike_id,
     user_id, user_name, user_phone,
     fee, real_fee, dep_fee, other_fee, pkg_name,
     pw_table, pay_way, is_disc, ostatus, is_present,
     is_pay, pay_time, is_wd, wd_time,
     is_dep_rf, dep_rf_time, is_oth_rf,
     rf_fee, rf_dep_fee, rf_oth_fee, trade_no,
     ctime, utime) = r

    bp_id = bp_id or 0
    user_id = user_id or 0

    # --- 维度归属 ---
    dim = agr_map.get(agr_id or 0)
    if dim:
        dim_src = '协议直连'
        eff_agr = agr_id
    else:
        eff_agr = 0
        cands = user_agr.get(user_id) or []
        pick = None
        for cid in cands:
            if agr_map[cid][5] == bp_id and bp_id:
                pick = cid
                break
        if pick is None and cands:
            pick = cands[0]
        if pick is not None:
            dim = agr_map[pick]
            eff_agr = pick
            dim_src = '按用户推断'
        else:
            dim_src = '无关联'
    stat_src[dim_src] += 1

    if dim:
        city, sid, ag_id, agr_status = dim[0], dim[1], dim[2], dim[3]
    else:
        city, sid, ag_id, agr_status = '', 0, 0, ''

    sm = site_map.get(sid, ('', '', '', '', 0, 0))
    mid, did = sm[4], sm[5]

    out.append({
        'order_id': oid,
        'agreement_id': (agr_id or 0),
        'ref_agreement_id': eff_agr,          # 实际用于取维度的协议ID
        'dim_source': dim_src,
        'user_id': user_id,
        'user_name': user_name or DASH,
        'user_phone': user_phone or DASH,
        'battery_product_id': bp_id,
        'battery_product': bp_map.get(bp_id) or DASH,
        'city': city or DASH,
        'area': sm[1] or DASH,
        'street': sm[2] or DASH,
        'community': sm[3] or DASH,
        'site_id': sid,
        'site_name': sm[0] or DASH,
        'agency_id': ag_id,
        'agency_name': agency_map.get(ag_id) or DASH,
        'merchant_id': mid,
        'merchant_name': merchant_map.get(mid) or DASH,
        'distributor_id': did,
        'distributor_name': distributor_map.get(did) or DASH,
        'agreement_status': AGR_STATUS_CN.get(agr_status, agr_status or DASH),
        'package_id': pkg_id or 0,
        'package_name': pkg_name or DASH,
        'fee': yuan(fee),
        'real_fee': yuan(real_fee),
        'deposit_fee': yuan(dep_fee),
        'other_fee': yuan(other_fee),
        'pay_way': PAY_WAY_CN.get(pay_way, pay_way or DASH),
        'pay_way_raw': pay_way or DASH,
        'pay_way_table': pw_table or DASH,
        'order_status': ORDER_STATUS_CN.get(ostatus, ostatus or DASH),
        'order_status_raw': ostatus or DASH,
        'is_discounts': YN.get(is_disc, DASH),
        'is_present': YN.get(is_present, DASH),
        'is_pay': YN.get(is_pay, DASH),
        'pay_time': ms2str(pay_time),
        'is_withdraw': YN.get(is_wd, DASH),
        'withdraw_time': ms2str(wd_time),
        'is_deposit_refund': YN.get(is_dep_rf, DASH),
        'deposit_refund_time': ms2str(dep_rf_time),
        'is_other_refund': YN.get(is_oth_rf, DASH),
        'refund_fee': yuan(rf_fee),
        'refund_deposit_fee': yuan(rf_dep_fee),
        'refund_other_fee': yuan(rf_oth_fee),
        'trade_no': trade_no or DASH,
        'bike_id': bike_id or 0,
        'oem_id': oem_id or 0,
        'create_time': ms2str(ctime),
        'update_time': ms2str(utime),
    })

log('组装完成 %d 条，字段 %d 个' % (len(out), len(out[0])))

os.makedirs('data', exist_ok=True)
P = 'data/deposit_full.json'
with io.open(P, 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, separators=(',', ':'))
log('已写 %s  %.2f MB' % (P, os.path.getsize(P) / 1024 / 1024))

# ---------------- 覆盖率速检 ----------------
N = len(out)
print()
print('=== 维度归属来源 ===')
for k, v in stat_src.items():
    print('  %-10s %6d  (%5.1f%%)' % (k, v, v * 100.0 / N))

print()
print('=== 关键筛选维度覆盖率 ===')
for f in ['city', 'area', 'street', 'battery_product', 'agreement_id',
          'agency_id', 'agency_name', 'user_id', 'user_phone',
          'site_id', 'site_name', 'package_name', 'order_status', 'pay_way']:
    n = sum(1 for r in out if r.get(f) not in (None, '', DASH, 0))
    dv = len({r.get(f) for r in out if r.get(f) not in (None, '', DASH, 0)})
    print('  %-20s %6d/%d (%5.1f%%)  去重 %d' % (f, n, N, n * 100.0 / N, dv))

print()
print('=== 金额合计（元） ===')
for f in ['fee', 'real_fee', 'deposit_fee', 'refund_fee', 'refund_deposit_fee']:
    print('  %-20s %,.2f'.replace(',', '') % (f, sum(r[f] for r in out)))
