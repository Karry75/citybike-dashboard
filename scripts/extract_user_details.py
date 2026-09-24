# -*- coding: utf-8 -*-
# #2 用户看板明细抽取：消费者换电订单明细 + 消费者退订申请明细 + 退款佐证
# 白名单已开（内网）。每段独立 try/except，每段后即时 dump 全量 JSON。
import json, time, pymysql
BASE=r'D:/workboddy file/dudu分析/citybike_backup'
P=f'{BASE}/config/backup_config.json'
DB=json.load(open(P,encoding='utf-8'))
conn=pymysql.connect(host=DB['host'],port=DB['port'],user=DB['user'],password=DB['password'],
                     database=DB['database'],connect_timeout=20,read_timeout=1800,charset='utf8mb4')
cur=conn.cursor(pymysql.cursors.DictCursor)
JPATH=f'{BASE}/data/dashboard_data.json'
NOW=int(time.time()*1000)
D60=NOW-60*86400*1000
D365=NOW-365*86400*1000

def load(): return json.load(open(JPATH,encoding='utf-8'))
def save(D,tag):
    json.dump(D,open(JPATH,'w',encoding='utf-8'),ensure_ascii=False)
    print('  [dump:'+tag+'] 已写回',flush=True)
def sec(title, fn):
    print('=== '+title+' ===',flush=True)
    try:
        fn(); D=load(); save(D,title)
    except Exception as e:
        print('  [WARN] '+title+' 失败: '+repr(e),flush=True)
def mask(p):
    if not p: return ''
    p=str(p).strip()
    return p[:3]+'****'+p[-4:] if len(p)>=7 else (p[:1]+'***' if p else '')
def yuan(fen):
    try: return round(float(fen)/100,2)
    except: return 0.0

# ---------- 换电订单明细（按网点/城市，订单表无 user_id） ----------
def t_orders():
    cols="id,site_id,site_name,site_city,site_area,site_street,site_union_address,"\
          "order_status,exchange_order_status,battery_status,exchange_status,pay_status,"\
          "take_status,back_status,pre_pay_price,pay_price,price_discount,real_pay_price,"\
          "use_power,expend_power,mileage,take_battery_sn,take_battery_power,create_time,update_time"
    cur.execute(f"SELECT {cols} FROM t_exchange_order WHERE is_del=0 AND create_time>%s ORDER BY create_time DESC LIMIT 25000",(D60,))
    rows=cur.fetchall()
    detail=[]
    for r in rows:
        detail.append({
            'id':r['id'],'site_id':r['site_id'],'site_name':r['site_name'] or '',
            'city':r['site_city'] or '', 'area':r['site_area'] or '', 'street':r['site_street'] or '',
            'addr':r['site_union_address'] or '',
            'order_status':r['order_status'],'exch_status':r['exchange_order_status'],
            'bat_status':r['battery_status'],'pay_status':r['pay_status'],
            'take_status':r['take_status'],'back_status':r['back_status'],
            'pre_pay':yuan(r['pre_pay_price']),'pay':yuan(r['pay_price']),
            'discount':yuan(r['price_discount']),'real_pay':yuan(r['real_pay_price']),
            'use_power':r['use_power'],'expend_power':r['expend_power'],
            'mileage':r['mileage'],'bat_sn':r['take_battery_sn'] or '',
            'bat_power':r['take_battery_power'],
            'create':str(r['create_time'])[:10],'update':str(r['update_time'])[:10]
        })
    # 抽样聚合（近60天样本，避免对 1100 万行做 GROUP BY）
    from collections import defaultdict
    city=defaultdict(lambda:[0,0.0]); daily=defaultdict(int); st=defaultdict(int)
    for d in detail:
        city[d['city']][0]+=1; city[d['city']][1]+=d['real_pay']
        daily[d['create']]+=1; st[d['order_status']]+=1
    city_top=sorted([{'city':k,'cnt':v[0],'pay':round(v[1],2)} for k,v in city.items() if k],key=lambda x:-x['cnt'])[:30]
    daily_s=sorted([{'date':k,'cnt':v} for k,v in daily.items()],key=lambda x:x['date'])
    status_s=sorted([{'status':k,'cnt':v} for k,v in st.items()],key=lambda x:-x['cnt'])
    # 总有效行（轻量 COUNT，不加时间窗以反映全量）
    cur.execute("SELECT COUNT(*) c FROM t_exchange_order WHERE is_del=0")
    total=cur.fetchone()['c']
    cur.execute("SELECT COUNT(*) c FROM t_exchange_order WHERE is_del=0 AND create_time>%s",(D60,))
    recent=cur.fetchone()['c']
    D=load()
    U=D.setdefault('user',{})
    U['exchange_orders']={
        'detail':detail,'city_top':city_top,'daily':daily_s,'status':status_s,
        'total':total,'recent60':recent,'sample_n':len(detail),
        '_note':'t_exchange_order 近60天抽样 2.5 万条（全量 '+format(total,',')+' 条）。订单表无 user_id，按网点/城市维度呈现。金额已 分→元。聚合基于抽样，非全量。'
    }
    print('   换电订单 抽样:',len(detail),' 全量:',total,' 近60天:',recent,flush=True)

# ---------- 退订申请明细（agreement 退订/终止） ----------
def t_unsub():
    cur.execute("SELECT COUNT(*) c FROM t_exchange_agreement WHERE is_del=0 AND status IN ('unsubscribing','stop','cancelled')")
    total=cur.fetchone()['c']
    cur.execute("SELECT id,user_id,user_name,user_phone,oem_id,agency_id,distributor_id,sys_city_name,"
                "site_id,site_sale_scenario_name,type,rent_package_id,battery_product_id,status,"
                "deposit_status,deposit_fee,deposit_real_fee,is_rent_expire_stop,is_create_stop_expense_bill,"
                "is_create_refund_expense_bill,create_refund_expense_bill_time,stop_time,rent_expire_time,"
                "activation_time,create_time,update_time,promoter_id,is_contract,contract_expire_time,remark "
                "FROM t_exchange_agreement WHERE is_del=0 AND status IN ('unsubscribing','stop','cancelled') "
                "ORDER BY create_time DESC LIMIT 25000")
    rows=cur.fetchall()
    detail=[]
    for r in rows:
        detail.append({
            'id':r['id'],'user_id':r['user_id'],'user_name':r['user_name'] or '',
            'phone':mask(r['user_phone']),'oem':r['oem_id'],'agency':r['agency_id'],
            'distributor':r['distributor_id'],'city':r['sys_city_name'] or '',
            'site_id':r['site_id'],'scenario':r['site_sale_scenario_name'] or '',
            'type':r['type'],'package':r['rent_package_id'],'battery':r['battery_product_id'],
            'status':r['status'],'deposit_status':r['deposit_status'],
            'deposit_fee':yuan(r['deposit_fee']),'deposit_real':yuan(r['deposit_real_fee']),
            'is_expire_stop':r['is_rent_expire_stop'],'is_stop_bill':r['is_create_stop_expense_bill'],
            'is_refund_bill':r['is_create_refund_expense_bill'],
            'refund_bill_time':str(r['create_refund_expense_bill_time'])[:10],
            'stop_time':str(r['stop_time'])[:10],'rent_expire':str(r['rent_expire_time'])[:10],
            'activate':str(r['activation_time'])[:10],'create':str(r['create_time'])[:10],
            'update':str(r['update_time'])[:10],'promoter':r['promoter_id'],
            'is_contract':r['is_contract'],'contract_expire':str(r['contract_expire_time'])[:10],
            'remark':(r['remark'] or '')[:60]
        })
    # 聚合（9.4万行，安全 GROUP BY）
    cur.execute("SELECT status,COUNT(*) c FROM t_exchange_agreement WHERE is_del=0 AND status IN ('unsubscribing','stop','cancelled') GROUP BY status")
    st={r['status']:r['c'] for r in cur.fetchall()}
    cur.execute("SELECT sys_city_name,COUNT(*) c FROM t_exchange_agreement WHERE is_del=0 AND status IN ('unsubscribing','stop','cancelled') GROUP BY sys_city_name ORDER BY c DESC LIMIT 20")
    city=[{'city':(r['sys_city_name'] or '未知'),'cnt':r['c']} for r in cur.fetchall()]
    cur.execute("SELECT type,COUNT(*) c FROM t_exchange_agreement WHERE is_del=0 AND status IN ('unsubscribing','stop','cancelled') GROUP BY type ORDER BY c DESC")
    typ=[{'type':(r['type'] or '未知'),'cnt':r['c']} for r in cur.fetchall()]
    cur.execute("SELECT DATE_FORMAT(FROM_UNIXTIME(create_time/1000),'%%Y-%%m') m,COUNT(*) c FROM t_exchange_agreement WHERE is_del=0 AND status IN ('unsubscribing','stop','cancelled') AND create_time>%s GROUP BY m ORDER BY m",(D365,))
    trend=[{'month':r['m'],'cnt':r['c']} for r in cur.fetchall()]
    D=load()
    U=D.setdefault('user',{})
    U['unsubscribe']={
        'detail':detail,'status':st,'city':city,'type':typ,'trend':trend,
        'total':total,'sample_n':len(detail),
        '_note':'t_exchange_agreement 中 status IN(unsubscribing=退订申请中,stop=已停用,cancelled=已取消) 共 '+format(total,',')+' 条；抽样展示最近 2.5 万。user_phone 已脱敏(138****1234)。金额已 分→元。'
    }
    print('   退订申请 抽样:',len(detail),' 全量:',total,' status:',st,flush=True)

# ---------- 退款佐证（t_pay_refund_log） ----------
def t_refund():
    cur.execute("SELECT COUNT(*) c, SUM(unit_price) s FROM t_pay_refund_log WHERE is_del=0")
    r=cur.fetchone(); total=r['c']; amt=yuan(r['s'] or 0)
    cur.execute("SELECT refund_status,COUNT(*) c FROM t_pay_refund_log WHERE is_del=0 GROUP BY refund_status")
    st={x['refund_status']:x['c'] for x in cur.fetchall()}
    cur.execute("SELECT business_type,COUNT(*) c,SUM(unit_price) s FROM t_pay_refund_log WHERE is_del=0 GROUP BY business_type ORDER BY c DESC LIMIT 12")
    bt=[{'type':(x['business_type'] or '未知'),'cnt':x['c'],'amt':yuan(x['s'] or 0)} for x in cur.fetchall()]
    D=load()
    U=D.setdefault('user',{})
    U.setdefault('unsubscribe',{})['refund']={'total':total,'amt':amt,'status':st,'by_business':bt,
        '_note':'t_pay_refund_log 退款流水佐证：全量 '+format(total,',')+' 笔，退款总额 ¥'+format(round(amt,2),',')+'（分→元）。status 多为 success。'}
    print('   退款流水 笔:',total,' 总额¥:',round(amt,2),flush=True)

for (t,fn) in [('T_ORDERS 换电订单',t_orders),('T_UNSUB 退订申请',t_unsub),('T_REFUND 退款佐证',t_refund)]:
    sec(t,fn)
conn.close()
print('DONE-USER-DETAILS')
