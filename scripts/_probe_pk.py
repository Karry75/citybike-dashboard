# -*- coding: utf-8 -*-
import json, pymysql, os
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB=json.load(open(os.path.join(ROOT,'config','backup_config.json'),encoding='utf-8')); DB.pop('workers',None)
conn=pymysql.connect(host=DB['host'],port=DB['port'],user=DB['user'],password=DB['password'],database=DB['database'],connect_timeout=15,read_timeout=600,charset='utf8mb4')
cur=conn.cursor()
def q(s,many=False):
    cur.execute(s); return cur.fetchall() if many else (cur.fetchone()[0] if cur.rowcount else None)
D=json.load(open(os.path.join(ROOT,'data','dashboard_data.json'),encoding='utf-8'))
print('t_exchange count:', q('SELECT COUNT(*) FROM t_exchange'))
print('t_battery count:', q('SELECT COUNT(*) FROM t_battery'))
print('t_work_order count:', q('SELECT COUNT(*) FROM t_work_order'))
print('t_expense_bill count:', q('SELECT COUNT(*) FROM t_expense_bill'))
wo=D['workorder']['detail']
print('workorder.detail n=',len(wo),'sample order_id:',[r.get('order_id') for r in wo[:3]])
oids=[r['order_id'] for r in wo[:50] if r.get('order_id') is not None]
print('t_work_order.id match for 50 oids:', q('SELECT COUNT(*) FROM t_work_order WHERE id IN (%s)'%','.join(map(str,oids))) if oids else 'none')
ud=D['coupon']['user_detail']
print('coupon.user_detail n=',len(ud),'sample record_id:',[r.get('record_id') for r in ud[:3]])
rids=[r['record_id'] for r in ud[:50] if r.get('record_id') is not None]
for t in ['t_coupon_convert_code_order','t_coupon_center_log','t_user_coupon','t_coupon_convert_code']:
    try:
        c=q('SELECT COUNT(*) FROM %s WHERE id IN (%s)'%(t,','.join(map(str,rids))) if rids else 'SELECT 0')
        print('  %s match for user_detail record_id:'%t, c)
    except Exception as e:
        print('  %s ERR'%t, str(e)[:80])
# agent_issue record_id mapping too
ai=D['coupon']['agent_issue']
rids2=[r['record_id'] for r in ai[:50] if r.get('record_id') is not None]
for t in ['t_coupon_convert_code_order','t_coupon_center_log']:
    try:
        c=q('SELECT COUNT(*) FROM %s WHERE id IN (%s)'%(t,','.join(map(str,rids2))) if rids2 else 'SELECT 0')
        print('  [agent_issue] %s match:'%t, c)
    except Exception as e:
        print('  [agent_issue] %s ERR'%t, str(e)[:80])
conn.close()
print('PROBE DONE')
