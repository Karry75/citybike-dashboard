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

# 1) 表名匹配：租期/卡/套餐/代理/经销
kw = ['rent', 'term', 'card', 'package', 'agent', 'agency', 'proxy', 'dealer', 'distribut', 'lease']
sql = ("SELECT table_name FROM information_schema.tables WHERE table_schema=%s AND ("
       + " OR ".join(["table_name LIKE %s"] * len(kw)) + ")")
rows = q(sql, [DB] + ["%" + k + "%" * 0 + "%" for k in kw])
out['tables_like'] = sorted(r[0] for r in rows)

# 2) 列名匹配：赠送/gift/租期/卡/代理/押金/券/套餐/租
ckw = ['gift', 'donate', 'present', 'rent', 'term', 'card', 'agent', 'deposit',
       'coupon', 'package', '租', '赠', '押', '套餐', '期限']
sql = ("SELECT table_name, column_name, column_comment, data_type FROM information_schema.columns "
       "WHERE table_schema=%s AND (" + " OR ".join(["column_name LIKE %s OR column_comment LIKE %s"] * len(ckw)) + ")")
args = []
for k in ckw:
    args.append("%" + k + "%")
    args.append("%" + k + "%")
rows = q(sql, [DB] + args)
out['cols_like'] = [{'table': r[0], 'col': r[1], 'comment': r[2], 'type': r[3]} for r in rows]

# 3) t_site 列 + type 枚举
try:
    rows = q("SELECT column_name, column_comment, data_type FROM information_schema.columns "
             "WHERE table_schema=%s AND table_name='t_site'", (DB,))
    out['t_site_cols'] = [{'col': r[0], 'comment': r[1], 'type': r[2]} for r in rows]
    rows = q("SELECT type, COUNT(*) AS n FROM t_site GROUP BY type ORDER BY n DESC LIMIT 50")
    out['t_site_type_vals'] = [list(r) for r in rows]
except Exception as e:
    out['t_site_err'] = repr(e)

# 4) 含 pay_way 的表
rows = q("SELECT table_name FROM information_schema.columns WHERE table_schema=%s AND column_name='pay_way'", (DB,))
out['pay_way_tables'] = sorted(r[0] for r in rows)
out['pay_way_enums'] = {}
for t in out['pay_way_tables'][:12]:
    try:
        rows = q("SELECT pay_way, COUNT(*) AS n FROM `%s` GROUP BY pay_way ORDER BY n DESC LIMIT 30" % t)
        out['pay_way_enums'][t] = [list(r) for r in rows]
    except Exception as e:
        out['pay_way_enums'][t] = 'ERR:' + repr(e)

# 5) 设备相关表列
dev_tables = ['t_exchange_store', 't_battery', 't_device', 't_cabinet', 't_exchange_cabinet', 't_battery_model']
out['dev_cols'] = {}
for t in dev_tables:
    try:
        rows = q("SELECT column_name, column_comment, data_type FROM information_schema.columns "
                 "WHERE table_schema=%s AND table_name=%s", (DB, t))
        out['dev_cols'][t] = [{'col': r[0], 'comment': r[1], 'type': r[2]} for r in rows]
    except Exception as e:
        out['dev_cols'][t] = 'ERR:' + repr(e)

# 6) t_user_exchange_package_order 完整列 + 套餐类型枚举
try:
    rows = q("SELECT column_name, column_comment, data_type FROM information_schema.columns "
             "WHERE table_schema=%s AND table_name='t_user_exchange_package_order'", (DB,))
    out['pkg_order_cols'] = [{'col': r[0], 'comment': r[1], 'type': r[2]} for r in rows]
    rows = q("SELECT DISTINCT package_type FROM t_user_exchange_package_order LIMIT 60")
    out['pkg_order_types'] = [r[0] for r in rows]
except Exception as e:
    out['pkg_order_err'] = repr(e)

# 7) 赠送/赠金类金额：搜 gift/donate/赠送 列并抽样取值
gift_cols = [x for x in out['cols_like'] if any(w in ((x['col'] or '') + (x['comment'] or '')) for w in ['gift', 'donate', '赠', 'present'])]
out['gift_candidates'] = gift_cols[:80]

json.dump(out, open('data/probe_caliber.json', 'w'), ensure_ascii=False, indent=2)
# 打印精简摘要
summary = {
    'tables_like': out['tables_like'],
    'pay_way_tables': out['pay_way_tables'],
    't_site_type_vals': out.get('t_site_type_vals'),
    'pkg_order_types': out.get('pkg_order_types'),
    't_site_err': out.get('t_site_err'),
    'pkg_order_err': out.get('pkg_order_err'),
}
print(json.dumps(summary, ensure_ascii=False, indent=2))
print('\n--- cols_like count:', len(out['cols_like']))
print('--- gift_candidates count:', len(out.get('gift_candidates', [])))
c.close()
