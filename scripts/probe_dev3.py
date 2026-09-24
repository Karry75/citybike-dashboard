# -*- coding: utf-8 -*-
import json, pymysql
P=r'D:/workboddy file/dudu分析/citybike_backup/config/backup_config.json'
DB=json.load(open(P,encoding='utf-8'))
conn=pymysql.connect(host=DB['host'],port=DB['port'],user=DB['user'],password=DB['password'],
                     database=DB['database'],connect_timeout=15,read_timeout=600,charset='utf8mb4')
cur=conn.cursor(pymysql.cursors.DictCursor)
def cols(t):
    cur.execute("SELECT COLUMN_NAME,COLUMN_COMMENT FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name=%s ORDER BY ORDINAL_POSITION",(t,))
    return [(r['COLUMN_NAME'],r['COLUMN_COMMENT']) for r in cur.fetchall()]
def cnt(t):
    try: cur.execute(f"SELECT COUNT(*) c FROM {t} WHERE is_del=0"); return cur.fetchone()['c']
    except Exception as e: return f'ERR({e})'
def sample(t):
    try:
        cur.execute(f"SELECT * FROM {t} WHERE is_del=0 LIMIT 1")
        r=cur.fetchone(); return {k:(str(v)[:34]) for k,v in r.items()} if r else None
    except Exception as e: return f'ERR({e})'
print('===== t_battery (rows=%s) =====' % cnt('t_battery'))
print(' COLS:', [c[0] for c in cols('t_battery')])
print(' SAMPLE:', sample('t_battery'))
print('\n===== t_battery_belong_relation (rows=%s) =====' % cnt('t_battery_belong_relation'))
print(' COLS:', [c[0] for c in cols('t_battery_belong_relation')])
cur.execute("SELECT belong_type,COUNT(*) c FROM t_battery_belong_relation WHERE is_del=0 GROUP BY belong_type")
print(' belong_type 分布:', cur.fetchall())
print(' SAMPLE:', sample('t_battery_belong_relation'))
print('\n===== t_battery_status (rows=%s) =====' % cnt('t_battery_status'))
print(' COLS:', [c[0] for c in cols('t_battery_status')])
cur.execute("SELECT COLUMN_NAME FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='t_battery_status' AND (COLUMN_NAME LIKE '%status%' OR COLUMN_NAME LIKE '%state%')")
print(' status类列:', [r['COLUMN_NAME'] for r in cur.fetchall()])
print('\n===== t_battery_not_in (rows=%s) =====' % cnt('t_battery_not_in'))
print(' COLS:', [c[0] for c in cols('t_battery_not_in')])
print('\n===== t_exchange_order (rows=%s) =====' % cnt('t_exchange_order'))
print(' COLS:', [c[0] for c in cols('t_exchange_order')])
print(' SAMPLE:', sample('t_exchange_order'))
conn.close(); print('\nDONE-DEV3')
