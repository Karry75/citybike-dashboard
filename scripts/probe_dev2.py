# -*- coding: utf-8 -*-
import json, pymysql
P=r'D:/workboddy file/dudu分析/citybike_backup/config/backup_config.json'
DB=json.load(open(P,encoding='utf-8'))
conn=pymysql.connect(host=DB['host'],port=DB['port'],user=DB['user'],password=DB['password'],
                     database=DB['database'],connect_timeout=15,read_timeout=600,charset='utf8mb4')
cur=conn.cursor(pymysql.cursors.DictCursor)
def cols(t):
    cur.execute("SELECT COLUMN_NAME,COLUMN_COMMENT FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name=%s ORDER BY ORDINAL_POSITION",(t,))
    return [r['COLUMN_NAME'] for r in cur.fetchall()]
def cnt(t):
    try: cur.execute(f"SELECT COUNT(*) c FROM {t} WHERE is_del=0"); return cur.fetchone()['c']
    except Exception as e: return f'ERR({e})'
def sample(t):
    try:
        cur.execute(f"SELECT * FROM {t} WHERE is_del=0 LIMIT 1")
        r=cur.fetchone(); return {k:(str(v)[:38]) for k,v in r.items()} if r else None
    except Exception as e: return f'ERR({e})'
for t in ['t_warehouse_operate_platform','t_warehouse_agency_employee','t_warehouse_distributor_maker','t_warehouse_site']:
    print(f'\n===== {t} (rows={cnt(t)}) =====')
    print(' COLS:', cols(t))
    s=sample(t)
    if isinstance(s,dict):
        for k,v in s.items(): print(f'   {k} = {v}')
print('\n===== 流通记录表 =====')
for t in ['t_battery_circulate_log','t_battery_circulation_log']:
    print(f'\n--- {t} (rows={cnt(t)}) ---')
    print(' COLS:', cols(t))
    s=sample(t)
    if isinstance(s,dict):
        for k,v in s.items(): print(f'   {k} = {v}')
print('\n===== 调度/换电订单表（dispatch 30d 来源）=====')
cur.execute("SELECT TABLE_NAME,TABLE_COMMENT FROM information_schema.tables WHERE table_schema=DATABASE() AND (TABLE_NAME LIKE '%exchange_order%' OR TABLE_NAME LIKE '%swap%' OR TABLE_NAME LIKE '%dispatch%' OR TABLE_NAME LIKE '%t_order%')")
for r in cur.fetchall(): print('  ',r['TABLE_NAME'],'|',r['TABLE_COMMENT'])
conn.close(); print('\nDONE-DEV-B')
