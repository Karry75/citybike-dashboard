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
def cnt(t):
    try:
        cur.execute("SELECT COUNT(*) FROM `%s`" % t); return cur.fetchone()[0]
    except Exception as e:
        return 'ERR:'+str(e)[:50]
def tables_like(p):
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema=%s AND table_name LIKE %s", (DB, p))
    return [r[0] for r in cur.fetchall()]

out={}
# 主订单表候选
cands = ['t_exchange_order','t_exchange_service_order','t_user_exchange_order','t_service_order']
for t in cands:
    try:
        out.setdefault('main_orders',{})[t]={'rows':cnt(t),'cols':cols(t)}
    except Exception as e:
        out.setdefault('main_orders',{})[t]='ERR:'+str(e)[:50]

# 违约金/欠租 完整字段
out['violated'] = cols('t_user_exchange_rent_violated_order')
# 协议表 owe 字段
ag = cols('t_user_exchange_agreement')
out['agreement_owe'] = [x for x in ag if any(w in (x['col']+x['comment']).lower() for w in ['owe','arrear','debt','欠','fee','押金','deposit','status'])]
# 电池流转候选（更广）
bf = set(tables_like('%battery%')) | set(tables_like('%exchange%store%')) | set(tables_like('%store%log%'))
out['battery_all'] = list(bf)
# 注册/激活候选
rg = set(tables_like('%user%')) | set(tables_like('%sms%')) | set(tables_like('%code%'))
out['user_all'] = list(rg)
# 预警/工单候选
wn = set(tables_like('%warning%')) | set(tables_like('%message%')) | set(tables_like('%notice%')) | set(tables_like('%order%warn%'))
out['warn_all'] = list(wn)
# 客诉完整字段
out['complaint'] = cols('t_exchange_order_complaint')
json.dump(out, open('data/probe_dims2.json','w',encoding='utf-8'), ensure_ascii=False, indent=1)
print('DONE2')
c.close()
