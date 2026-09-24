# -*- coding: utf-8 -*-
import pymysql, json
cfg = json.load(open('config/backup_config.json', encoding='utf-8'))
DB = cfg['database']
c = pymysql.connect(host=cfg['host'], port=cfg['port'], user=cfg['user'],
    password=cfg['password'], database=DB, connect_timeout=15, read_timeout=600, charset='utf8mb4')
cur = c.cursor()
def cols(t):
    cur.execute("SELECT column_name, column_comment, data_type FROM information_schema.columns "
                "WHERE table_schema=%s AND table_name=%s ORDER BY ordinal_position", (DB, t))
    return [{'col': r[0], 'comment': r[1] or '', 'type': r[2]} for r in cur.fetchall()]
out={}
for t in ['t_exchange_order','t_user_exchange_rent_violated_log','t_user_exchange_agreement',
          't_battery_circulate_log','t_user_exchange_rent','t_battery_circulation_log']:
    try:
        out[t]=cols(t)
    except Exception as e:
        out[t]='ERR:'+str(e)[:60]
json.dump(out, open('data/probe_dims3.json','w',encoding='utf-8'), ensure_ascii=False, indent=1)
print('DONE3')
c.close()
