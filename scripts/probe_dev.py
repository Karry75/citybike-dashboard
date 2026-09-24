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
        r=cur.fetchone(); return {k:(str(v)[:40]) for k,v in r.items()} if r else None
    except Exception as e: return f'ERR({e})'
for t in ['t_bike','t_bike_status','t_bike_rent','t_battery','t_battery_belong_relation','t_battery_status','t_battery_not_in']:
    print(f'\n===== {t} (rows={cnt(t)}) =====')
    print(' COLS:', [c[0] for c in cols(t)])
    s=sample(t)
    if isinstance(s,dict):
        for k,v in s.items(): print(f'   {k} = {v}')
    else: print('   sample:',s)
# belong_relation 的 belong 类型分布（决定 6 类电池归属）
print('\n===== t_battery_belong_relation · belong_type 分布 =====')
try:
    cur.execute("SELECT belong_type,COUNT(*) c FROM t_battery_belong_relation WHERE is_del=0 GROUP BY belong_type")
    for r in cur.fetchall(): print('  ',r)
except Exception as e: print('  ERR',e)
conn.close(); print('\nDONE-DEV-A')
