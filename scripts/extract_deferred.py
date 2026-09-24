# -*- coding: utf-8 -*-
# 延期清单抽取（白名单已开）。每段独立 try/except，每段后即时 dump 全量 JSON。
import json, time, pymysql
BASE=r'D:/workboddy file/dudu分析/citybike_backup'
P=f'{BASE}/config/backup_config.json'
DB=json.load(open(P,encoding='utf-8'))
conn=pymysql.connect(host=DB['host'],port=DB['port'],user=DB['user'],password=DB['password'],
                     database=DB['database'],connect_timeout=20,read_timeout=300,charset='utf8mb4')
cur=conn.cursor(pymysql.cursors.DictCursor)
JPATH=f'{BASE}/data/dashboard_data.json'

def q1(sql,*a):
    cur.execute(sql,a); return cur.fetchone()

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

# ---------- T6 仓库列表 ----------
def t6():
    cur.execute("SELECT id,name,inventory_type,creator_employee_id,creator_employee_name,remark,create_time FROM t_warehouse_operate_platform WHERE is_del=0")
    platform=[{'id':r['id'],'name':r['name'],'inventory_type':r['inventory_type'],'creator':r['creator_employee_name'] or '','remark':r['remark'] or '','create_time':str(r['create_time'])[:10]} for r in cur.fetchall()]
    cur.execute("SELECT id,agency_id,employee_id,name,inventory_type,inventory_limit,create_time FROM t_warehouse_agency_employee WHERE is_del=0")
    ag1=[{'id':r['id'],'agency_id':r['agency_id'],'owner_id':r['employee_id'],'name':r['name'],'inventory_type':r['inventory_type'],'type':'代理商员工仓','limit':r['inventory_limit'],'create_time':str(r['create_time'])[:10]} for r in cur.fetchall()]
    cur.execute("SELECT id,agency_id,distributor_id,name,inventory_type,inventory_limit,create_time FROM t_warehouse_distributor_maker WHERE is_del=0")
    ag2=[{'id':r['id'],'agency_id':r['agency_id'],'owner_id':r['distributor_id'],'name':r['name'],'inventory_type':r['inventory_type'],'type':'渠道商仓','limit':r['inventory_limit'],'create_time':str(r['create_time'])[:10]} for r in cur.fetchall()]
    agent=ag1+ag2
    D=load()
    wh={}
    wh['platform']=platform
    wh['agent']=agent
    wh['_counts']={'platform':len(platform),'agent':len(agent)}
    wh['_note']='平台仓库=t_warehouse_operate_platform；代理商仓库=代理商员工仓(t_warehouse_agency_employee)+渠道商仓(t_warehouse_distributor_maker)。全量。'
    D['warehouse']=wh
    print('   平台仓:',len(platform),' 代理商仓(含渠道商):',len(agent),flush=True)

# ---------- T3 电池6类 ----------
def t3():
    total=q1("SELECT COUNT(*) c FROM t_battery WHERE is_del=0")
    online=q1("SELECT COUNT(*) c FROM t_battery WHERE is_del=0 AND online_status='online'")
    cur.execute("SELECT belong_type,COUNT(DISTINCT battery_id) c FROM t_battery_belong_relation WHERE is_del=0 GROUP BY belong_type")
    by_type={r['belong_type']:r['c'] for r in cur.fetchall()}
    recognized=q1("SELECT COUNT(DISTINCT battery_id) c FROM t_battery_belong_relation WHERE is_del=0")
    unrecognized=total['c']-recognized['c']
    scrap=q1("SELECT COUNT(*) c FROM t_battery WHERE is_del=0 AND battery_status='scrap'")
    classes={}
    classes['车辆仓库']=by_type.get('bike',0)
    classes['换电柜仓库']=by_type.get('exchange',0)
    classes['运营平台仓库']=by_type.get('operate_platform',0)
    classes['代理商员工仓库']=by_type.get('agency_employee',0)
    classes['网点仓库']=by_type.get('site',0)
    classes['故障电池(=scrap报废)']=scrap['c']
    classes['未识别到位']=unrecognized
    cur.execute("SELECT b.device_sn,b.battery_status,b.online_status,b.last_location_address,b.type,b.agency_id,br.belong_type FROM t_battery b LEFT JOIN t_battery_belong_relation br ON b.id=br.battery_id AND br.is_del=0 WHERE b.is_del=0 LIMIT 3000")
    detail=[{'device_sn':r['device_sn'],'battery_status':r['battery_status'],'online_status':r['online_status'],'last_location_address':r['last_location_address'] or '','type':r['type'],'belong_type':r['belong_type'] or '未识别'} for r in cur.fetchall()]
    D=load()
    dev=D.setdefault('device',{})
    dev['battery_total']=total['c']
    dev['battery_online']=online['c']
    dev['battery_classes']=classes
    dev['battery_detail']=detail
    dev['_battery_note']='6类来自 t_battery_belong_relation.belong_type 聚合；故障电池=t_battery.battery_status=scrap（数据源无独立故障标记，以报废近似）；未识别=总电池−归属关系去重数。'
    print('   总电池:',total['c'],' 在线:',online['c'],' 6类:',classes,flush=True)

# ---------- T2 车辆总览 ----------
def t2():
    total=q1("SELECT COUNT(*) c FROM t_bike WHERE is_del=0")
    online=q1("SELECT COUNT(*) c FROM t_bike WHERE is_del=0 AND online_status='online'")
    rentaln=q1("SELECT COUNT(*) c FROM t_bike_rent WHERE is_del=0")
    cur.execute("SELECT agency_id,COUNT(*) c FROM t_bike WHERE is_del=0 AND agency_id>0 GROUP BY agency_id ORDER BY c DESC LIMIT 10")
    by_agency=[{'agency_id':r['agency_id'],'count':r['c']} for r in cur.fetchall()]
    cur.execute("SELECT b.id,b.device_sn,b.name,b.vin,b.last_location_address,b.exchange_agreement_id,b.site_id,b.online_status,b.images,bs.batter_store FROM t_bike b LEFT JOIN t_bike_status bs ON b.id=bs.bike_id AND bs.is_del=0 WHERE b.is_del=0 LIMIT 2000")
    sample=[]
    for r in cur.fetchall():
        sample.append({'vehicle_id':r['id'],'sn':r['device_sn'],'name':r['name'],'frame':r['vin'] or '','addr':r['last_location_address'] or '','agreement':r['exchange_agreement_id'],'loc':r['site_id'],'flow':r['online_status'],'img':r['images'],'bat_cnt':(1 if r['batter_store']=='on' else 0),'bat_sn':''})
    D=load()
    U=D.setdefault('user',{})
    veh={}
    veh['total']=total['c']
    veh['online']=online['c']
    veh['offline']=total['c']-online['c']
    veh['rental']=rentaln['c']
    veh['by_agency']=by_agency
    veh['sample']=sample
    veh['_note']='t_bike 全量聚合；样本上限2000（含电池在仓标记 batter_store）。车辆=电动换电单车。'
    U['vehicle']=veh
    print('   总车辆:',total['c'],' 在线:',online['c'],' 租赁:',rentaln['c'],' 样本:',len(sample),flush=True)

# ---------- T4 调度精确30/7天（限已知网点）----------
def t4():
    D=load()
    sites=D.get('dispatch',{}).get('site',[]) or []
    ids=[s['sid'] for s in sites if s.get('sid')]
    if not ids:
        print('   无 dispatch.site 网点，跳过',flush=True); return
    now_ms=int(time.time()*1000); d30=now_ms-30*86400*1000; d7=now_ms-7*86400*1000
    ph=','.join(['%s']*len(ids))
    cur.execute("SELECT site_id, SUM(CASE WHEN create_time>%s THEN 1 ELSE 0 END) s30, SUM(CASE WHEN create_time>%s THEN 1 ELSE 0 END) s7 FROM t_exchange_order WHERE is_del=0 AND exchange_order_status='success' AND site_id IN ("+ph+") GROUP BY site_id",(d30,d7)+tuple(ids))
    swap_map={}
    for r in cur.fetchall():
        swap_map[r['site_id']]={'swap30':int(r['s30'] or 0),'swap7':int(r['s7'] or 0)}
    D=load()
    dp=D.setdefault('dispatch',{})
    hit=0
    for s in dp.get('site',[]) or []:
        m=swap_map.get(s.get('sid'))
        if m:
            s['swap30']=m['swap30']; s['swap7']=m['swap7']; hit+=1
    dp['_swap_note']=f'精确30/7天换电次数来自 t_exchange_order（exchange_order_status=success，仅限看板已知网点聚合）；已替代原 Sheet5 近似。命中网点 '+str(hit)+'/'+str(len(dp.get('site',[])))+'。'
    print('   换电订单网点聚合命中:',hit,' 总网点:',len(dp.get('site',[])),flush=True)

# ---------- T5 租赁电池SN·流通 ----------
def t5():
    cur.execute("SELECT agreement_id,bike_id FROM t_bike_rent WHERE is_del=0 AND agreement_id IS NOT NULL AND agreement_id != ''")
    rent_map={str(r['agreement_id']):r['bike_id'] for r in cur.fetchall()}
    cur.execute("SELECT bike_id,battery_sn FROM t_bike_battery_bind_log WHERE is_del=0 AND bind_status='bind'")
    bind_map={}
    for r in cur.fetchall(): bind_map.setdefault(r['bike_id'],r['battery_sn'])
    cur.execute("SELECT id,online_status FROM t_bike WHERE is_del=0")
    bflow={r['id']:r['online_status'] for r in cur.fetchall()}
    D=load()
    rt=D.setdefault('rental',{})
    rows=rt.get('rows',[]) or []
    hb=0
    for r in rows:
        ag=str(r.get('agreement') or '')
        bid=rent_map.get(ag)
        if bid:
            sn=bind_map.get(bid)
            if sn and (not r.get('bat_sn') or str(r.get('bat_sn'))=='None'): r['bat_sn']=sn; hb+=1
            fl=bflow.get(bid)
            if fl and (not r.get('flow') or str(r.get('flow'))=='None'): r['flow']=fl
    rt['_bat_sn_hit']=hb
    rt['_bat_sn_note']=f'电池SN 来自 t_bike_rent.agreement_id→bike_id→t_bike_battery_bind_log.battery_sn；流通状态=t_bike.online_status。命中 '+str(hb)+'/'+str(len(rows))+' 条租赁记录。'
    print('   租赁记录:',len(rows),' 电池SN 命中:',hb,flush=True)

for (t,fn) in [('T6 仓库',t6),('T3 电池6类',t3),('T2 车辆',t2),('T4 调度30天',t4),('T5 租赁SN',t5)]:
    sec(t,fn)

conn.close()
print('DONE-DEFERRED')
