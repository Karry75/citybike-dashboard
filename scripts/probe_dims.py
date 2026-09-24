# -*- coding: utf-8 -*-
import pymysql, json, sys
cfg = json.load(open('config/backup_config.json', encoding='utf-8'))
DB = cfg['database']
def con():
    return pymysql.connect(host=cfg['host'], port=cfg['port'], user=cfg['user'],
        password=cfg['password'], database=DB, connect_timeout=15,
        read_timeout=600, charset='utf8mb4')
c = con(); cur = c.cursor()

def cols(t):
    cur.execute("SELECT column_name, column_comment, data_type FROM information_schema.columns "
                "WHERE table_schema=%s AND table_name=%s ORDER BY ordinal_position", (DB, t))
    return [{'col': r[0], 'comment': r[1] or '', 'type': r[2]} for r in cur.fetchall()]

def cnt(t):
    try:
        cur.execute("SELECT COUNT(*) FROM `%s`" % t); return cur.fetchone()[0]
    except Exception as e:
        return 'ERR:' + str(e)[:60]

def tables_like(pattern):
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema=%s AND table_name LIKE %s", (DB, pattern))
    return [r[0] for r in cur.fetchall()]

def cols_like_col(pattern):
    cur.execute("SELECT table_name, column_name, column_comment, data_type FROM information_schema.columns "
                "WHERE table_schema=%s AND column_name LIKE %s", (DB, pattern))
    return [{'table': r[0], 'col': r[1], 'comment': r[2], 'type': r[3]} for r in cur.fetchall()]

def cols_like_comment(pattern):
    cur.execute("SELECT table_name, column_name, column_comment, data_type FROM information_schema.columns "
                "WHERE table_schema=%s AND column_comment LIKE %s", (DB, pattern))
    return [{'table': r[0], 'col': r[1], 'comment': r[2], 'type': r[3]} for r in cur.fetchall()]

out = {}

# 1) 换电订单表
eo = set(['t_exchange_order', 't_order'])
eo |= set(tables_like('%exchange%order%'))
out['exchange_orders'] = {}
for t in eo:
    try:
        out['exchange_orders'][t] = {'rows': cnt(t), 'cols': cols(t)}
    except Exception as e:
        out['exchange_orders'][t] = 'ERR:' + str(e)[:60]

# 2) 欠租金额字段
out['owe_fields'] = cols_like_col('%owe%') + cols_like_comment('%欠租%') + cols_like_comment('%欠款%') + cols_like_comment('%欠费%')

# 3) 电池流转表
bf = set(tables_like('%battery%flow%')) | set(tables_like('%battery%log%')) | set(tables_like('%battery%record%')) | set(tables_like('%flow%'))
out['battery_flow_tables'] = list(bf)
out['battery_flow_detail'] = {t: {'rows': cnt(t), 'cols': cols(t)} for t in list(bf)[:6]}

# 4) 注册/激活链路
rg = set(tables_like('%register%')) | set(tables_like('%regist%')) | set(tables_like('%signup%')) | set(tables_like('%invite%')) | set(tables_like('%user%log%'))
out['register_tables'] = list(rg)
out['register_detail'] = {t: {'rows': cnt(t), 'cols': cols(t)} for t in list(rg)[:6]}

# 5) 预警/告警/维修（MTTR）
wn = set(tables_like('%warn%')) | set(tables_like('%alert%')) | set(tables_like('%fault%')) | set(tables_like('%repair%')) | set(tables_like('%alarm%')) | set(tables_like('%mainten%'))
out['warn_tables'] = list(wn)
out['warn_detail'] = {t: {'rows': cnt(t), 'cols': cols(t)} for t in list(wn)[:8]}

# 6) 客诉/工单
cs = set(tables_like('%complaint%')) | set(tables_like('%work%order%')) | set(tables_like('%ticket%')) | set(tables_like('%cs%')) | set(tables_like('%service%'))
out['cs_tables'] = list(cs)
out['cs_detail'] = {t: {'rows': cnt(t), 'cols': cols(t)} for t in list(cs)[:8]}

# 7) 协议表 owe 字段确认
try:
    out['agreement_cols'] = cols('t_user_exchange_agreement')
except Exception as e:
    out['agreement_cols'] = 'ERR:' + str(e)

json.dump(out, open('data/probe_dims.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('PROBE_DONE')
c.close()
