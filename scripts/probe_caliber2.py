import pymysql, json
cfg = json.load(open('config/backup_config.json'))
c = pymysql.connect(host=cfg['host'], port=cfg['port'], user=cfg['user'],
                    password=cfg['password'], database=cfg['database'],
                    connect_timeout=cfg.get('connect_timeout', 15),
                    read_timeout=cfg.get('read_timeout', 600), charset='utf8mb4')
cur = c.cursor()
DB = cfg['database']
out = {}
def q(sql, args=None):
    cur.execute(sql, args)
    return cur.fetchall()

key_tables = ['t_user_exchange_rent_package_order', 't_user_exchange_package_order',
              't_user_exchange_deposit_package_order', 't_user_exchange_deposit',
              'zc_rental_pay_order', 't_user_exchange_rent',
              't_user_exchange_rent_package_order_present_package',
              't_user_exchange_deposit_package_order_present_package']
out['key_tables'] = {}
for t in key_tables:
    try:
        rows = q("SELECT column_name,column_comment,data_type FROM information_schema.columns "
                 "WHERE table_schema=%s AND table_name=%s", (DB, t))
        cols = [{'col': r[0], 'comment': r[1] or '', 'type': r[2]} for r in rows]
        amt = [x for x in cols if any(w in (x['col'] + x['comment']).lower()
              for w in ['amount', 'money', 'fee', 'price', 'paid', 'pay', 'sum', '金额',
                        '实付', '费用', 'total', 'charge', 'cost', '余额', 'deposit', '押金', 'price'])]
        out['key_tables'][t] = {'cols': cols, 'amt_cols': amt}
    except Exception as e:
        out['key_tables'][t] = 'ERR:' + repr(e)

out['pay_way_enums2'] = {}
for t in key_tables:
    try:
        rows = q("SELECT pay_way,COUNT(*) n FROM `%s` GROUP BY pay_way ORDER BY n DESC LIMIT 30" % t)
        out['pay_way_enums2'][t] = [list(r) for r in rows]
    except Exception as e:
        out['pay_way_enums2'][t] = 'ERR:' + repr(e)

d = json.load(open('data/probe_caliber.json'))
out['gift_full'] = d.get('gift_candidates', [])

try:
    rows = q("SELECT column_name,column_comment,data_type FROM information_schema.columns "
             "WHERE table_schema=%s AND table_name='t_distributor'", (DB,))
    out['distributor_cols'] = [{'col': r[0], 'comment': r[1] or '', 'type': r[2]} for r in rows]
    rows = q("SELECT COUNT(*) FROM t_distributor")
    out['distributor_count'] = rows[0][0]
except Exception as e:
    out['distributor_err'] = repr(e)

out['dev'] = {}
for t in ['t_exchange_store', 't_battery']:
    rows = q("SELECT column_name,column_comment,data_type FROM information_schema.columns "
             "WHERE table_schema=%s AND table_name=%s", (DB, t))
    out['dev'][t] = [{'col': r[0], 'comment': r[1] or '', 'type': r[2]} for r in rows]

rows = q("SELECT table_name FROM information_schema.tables WHERE table_schema=%s AND "
         "(table_name LIKE '%%dict%%' OR table_name LIKE '%%config%%' OR table_name LIKE '%%param%%' "
         "OR table_name LIKE '%%enum%%' OR table_name LIKE '%%type%%')", (DB,))
out['dict_tables'] = sorted(r[0] for r in rows)

json.dump(out, open('data/probe_caliber2.json', 'w'), ensure_ascii=False, indent=2)

for t, v in out['key_tables'].items():
    if isinstance(v, dict):
        print(t, '| AMT:', [(a['col'], a['comment']) for a in v['amt_cols']])
        print('   PAY_WAY:', out['pay_way_enums2'].get(t))
print('DISTRIBUTOR count', out.get('distributor_count'))
print('  cols:', [x['col'] for x in out.get('distributor_cols', [])])
print('DEV t_exchange_store (name/type/site/city/cabinet/model/brand/status):')
for x in out['dev']['t_exchange_store']:
    if any(w in x['col'].lower() for w in ['name', 'type', 'site', 'city', 'cabinet', 'model', 'brand', 'status', 'store']):
        print('   ', x['col'], '|', x['comment'])
print('DEV t_battery (name/type/site/city/model/brand/status):')
for x in out['dev']['t_battery']:
    if any(w in x['col'].lower() for w in ['name', 'type', 'site', 'city', 'model', 'brand', 'status', 'cabinet']):
        print('   ', x['col'], '|', x['comment'])
print('DICT tables:', out['dict_tables'])
print('GIFT full count:', len(out['gift_full']))
c.close()
