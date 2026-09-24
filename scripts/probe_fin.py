# -*- coding: utf-8 -*-
import json, pymysql
P=r'D:/workboddy file/dudu分析/citybike_backup/config/backup_config.json'
DB=json.load(open(P,encoding='utf-8'))
conn=pymysql.connect(host=DB['host'],port=DB['port'],user=DB['user'],password=DB['password'],
                     database=DB['database'],connect_timeout=15,read_timeout=600,charset='utf8mb4')
cur=conn.cursor(pymysql.cursors.DictCursor)
# 1) t_battery battery_status 分布（故障电池数口径）
cur.execute("SELECT battery_status,COUNT(*) c FROM t_battery WHERE is_del=0 GROUP BY battery_status")
print('t_battery.battery_status 分布:', cur.fetchall())
# 2) t_bike_battery_bind_log schema+sample
cur.execute("SELECT COLUMN_NAME FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='t_bike_battery_bind_log' ORDER BY ORDINAL_POSITION")
print('t_bike_battery_bind_log COLS:', [r['COLUMN_NAME'] for r in cur.fetchall()])
cur.execute("SELECT * FROM t_bike_battery_bind_log WHERE is_del=0 LIMIT 1")
r=cur.fetchone(); print('  SAMPLE:', {k:(str(v)[:30]) for k,v in r.items()} if r else None)
# 3) 现有 dispatch.site[0] 形状
d=json.load(open('data/dashboard_data.json',encoding='utf-8'))
dp=d.get('dispatch',{})
print('dispatch keys:', list(dp.keys()))
s0=(dp.get('site') or [None])[0]
print('dispatch.site[0]:', {k:(str(v)[:30]) for k,v in s0.items()} if s0 else None)
# 4) 现有 rental.rows[0] 形状（看 agreement 字段格式）
rt=d.get('rental',{})
rr=(rt.get('rows') or [None])[0]
print('rental.rows[0]:', {k:(str(v)[:24]) for k,v in rr.items()} if rr else None)
# 5) t_bike_rent.agreement_id 格式
cur.execute("SELECT agreement_id FROM t_bike_rent WHERE is_del=0 LIMIT 3")
print('t_bike_rent.agreement_id 样例:', [r['agreement_id'] for r in cur.fetchall()])
conn.close(); print('DONE-FIN')
