# -*- coding: utf-8 -*-
# 电池流通记录：t_battery_circulate_log 22.5M 行，取最近样本 3000（id 倒序≈时间倒序）。
# 字段映射到前端 drawDevCirculation 期望：id,bat_sn,method,from_obj,to_obj,from_type,to_type,create_time
import json, pymysql
BASE=r'D:/workboddy file/dudu分析/citybike_backup'
P=f'{BASE}/config/backup_config.json'
DB=json.load(open(P,encoding='utf-8'))
conn=pymysql.connect(host=DB['host'],port=DB['port'],user=DB['user'],password=DB['password'],
                     database=DB['database'],connect_timeout=20,read_timeout=300,charset='utf8mb4')
cur=conn.cursor(pymysql.cursors.DictCursor)
METHOD={'take_battery':'换电','back_battery':'还电','transfer':'调拨','allocate':'调拨',
         'inbound':'入库','stock_in':'入库','outbound':'出库','stock_out':'出库','deliver':'出库'}
cur.execute("SELECT id,battery_device_sn,business_type_first,business_type_second,inflow_name,inflow_type,outflow_name,outflow_type,create_time FROM t_battery_circulate_log WHERE is_del=0 ORDER BY id DESC LIMIT 3000")
rows=[]
for r in cur.fetchall():
    rows.append({'id':r['id'],'bat_sn':r['battery_device_sn'],
        'method':METHOD.get(r['business_type_second'], r['business_type_second'] or '—'),
        'from_obj':r['outflow_name'],'to_obj':r['inflow_name'],
        'from_type':r['outflow_type'],'to_type':r['inflow_type'],
        'create_time':str(r['create_time'])[:10]})
D=json.load(open(f'{BASE}/data/dashboard_data.json',encoding='utf-8'))
D['circulation']=rows
D['_circulation_note']='来源 t_battery_circulate_log（全量 2250 万行）；此处为最近 id 倒序样本 3000 条。method 由 business_type_second 映射（take_battery→换电 / back_battery→还电 / transfer→调拨 / inbound→入库 / outbound→出库），未覆盖类型保留原值。完整字段口径待用户确认「字段待发图」。'
json.dump(D,open(f'{BASE}/data/dashboard_data.json','w',encoding='utf-8'),ensure_ascii=False)
conn.close()
print('流通记录样本:',len(rows))
print('DONE-CIRC')
