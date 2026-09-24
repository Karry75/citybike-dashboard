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
        r=cur.fetchone(); return {k:(str(v)[:32]) for k,v in r.items()} if r else None
    except Exception as e: return f'ERR({e})'
def tbls(kw):
    cur.execute("SELECT TABLE_NAME,TABLE_COMMENT FROM information_schema.tables WHERE table_schema=DATABASE() AND (TABLE_NAME LIKE %s OR TABLE_COMMENT LIKE %s)",(f'%{kw}%',f'%{kw}%'))
    return [(r['TABLE_NAME'],r['TABLE_COMMENT']) for r in cur.fetchall()]

print('===== 1) 换电订单表 t_exchange_order (rows=%s) =====' % cnt('t_exchange_order'))
print(' COLS:', [c[0] for c in cols('t_exchange_order')])
print(' SAMPLE:', sample('t_exchange_order'))

print('\n===== 2) 退订/取消/终止 相关表 =====')
for r in tbls('退订')+tbls('取消')+tbls('终止')+tbls('cancel')+tbls('terminate')+tbls('unsub'):
    print('  ',r)

print('\n===== 3) t_exchange_agreement 状态分布(退订/终止是否在此) =====')
try:
    cur.execute("SELECT status,COUNT(*) c FROM t_exchange_agreement WHERE is_del=0 GROUP BY status")
    print('  ', cur.fetchall())
except Exception as e: print('  ERR',e)

print('\n===== 4) 地理字段探测: t_site / t_user / t_bike 是否有 lat/lng/city =====')
for t in ['t_site','t_user','t_bike','t_user_coupon']:
    cc=[c[0] for c in cols(t)]
    geo=[c for c in cc if any(k in c.lower() for k in ['lat','lng','lon','longitude','latitude','gd_lat','gd_lng','bd_lat','address','city','province','district','region','area','street'])]
    print(f'  {t}: geo类列={geo}')

print('\n===== 5) t_user 结构(单用户视图) =====')
print(' t_user COLS:', [c[0] for c in cols('t_user')])
print(' t_user SAMPLE:', sample('t_user'))

print('\n===== 6) t_site.city 分布 TOP10 (地图聚合用) =====')
try:
    cur.execute("SELECT city,COUNT(*) c FROM t_site WHERE is_del=0 AND city IS NOT NULL GROUP BY city ORDER BY c DESC LIMIT 10")
    print('  ', cur.fetchall())
except Exception as e: print('  ERR',e)
conn.close(); print('\nDONE-NEW')
