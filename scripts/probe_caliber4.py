import pymysql, json
cfg = json.load(open('config/backup_config.json'))
c = pymysql.connect(host=cfg['host'], port=cfg['port'], user=cfg['user'],
                    password=cfg['password'], database=cfg['database'],
                    connect_timeout=cfg.get('connect_timeout', 15),
                    read_timeout=cfg.get('read_timeout', 600), charset='utf8mb4')
cur = c.cursor()
DB = cfg['database']
def q(sql, args=None):
    cur.execute(sql, args); return cur.fetchall()
out = {}

# 搜设备/柜主表
rows = q("SELECT table_name FROM information_schema.tables WHERE table_schema=%s AND "
         "(table_name LIKE '%%device%%' OR table_name LIKE '%%cabinet%%' OR table_name LIKE '%%exchange%%')", (DB,))
cands = sorted(r[0] for r in rows)
out['candidates'] = cands

# 重点探查疑似柜/设备主表
focus = ['t_device', 't_cabinet', 't_exchange_cabinet', 't_exchange', 't_exchange_device']
out['focus'] = {}
for t in focus:
    if t in cands:
        try:
            rows = q("SELECT column_name,column_comment,data_type FROM information_schema.columns "
                     "WHERE table_schema=%s AND table_name=%s", (DB, t))
            cols = [{'col': r[0], 'comment': r[1] or '', 'type': r[2]} for r in rows]
            n = q("SELECT COUNT(*) FROM `%s`" % t)[0][0]
            # 找 name/site/city/type 列
            rel = [x for x in cols if any(w in x['col'].lower()
                  for w in ['name', 'site', 'city', 'type', 'sn', 'code', 'addr', 'lng', 'lat', 'store'])]
            out['focus'][t] = {'count': n, 'rel': rel, 'all': cols}
        except Exception as e:
            out['focus'][t] = 'ERR:' + repr(e)

json.dump(out, open('data/probe_caliber4.json', 'w'), ensure_ascii=False, indent=2)
print('candidates:', cands)
for t, v in out['focus'].items():
    if isinstance(v, dict):
        print('==', t, 'count=', v['count'])
        for x in v['rel']:
            print('   ', x['col'], '|', x['comment'])
    else:
        print('==', t, v)
c.close()
