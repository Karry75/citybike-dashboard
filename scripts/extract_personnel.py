# -*- coding: utf-8 -*-
# 人员看板抽取：代理商/渠道商/代理商员工/商户/导购 5 类实体（单次 O(N) 扫描，高效）
# 数据底牌（已探明 schema，不臆测）：
#  - 协议(签约)主表 = t_exchange_agreement（非 t_user）。带 agency_id / site_id / status / user_id；distributor_id/merchant_id/business_id/store_manager_maker_id 经 site 取。
#  - 网点主表 t_site 带 agency_id / distributor_id / merchant_id / business_id / store_manager_maker_id / site_status / is_promoter。
#  - 主表：t_distributor(id,name,agency_id,level,status,maker_id) / t_merchant(id,name,agency_id,maker_id) / t_promoter(id,name,agency_id,agency_employee_id,maker_id,phone,share_count)。
#  - 员工靠关系表：t_warehouse_agency_employee(agency_id,employee_id,name) / t_site_store_employee(maker_id,serve_site_id,merchant_id,name,is_manager)。
#  - 导购→用户：t_promoter_relation(promoter_id,user_id,agreement_id,is_valid)。
#  - 代理商无主表，名称从 t_exchange_order.agency_name(DISTINCT) 取，缺失回退「代理商#ID」。
# 分成金额：用户指定先留 ⚠️ 占位，不臆测来源表。
import json, pymysql, sys, traceback
from collections import defaultdict
P=r'D:/workboddy file/dudu分析/citybike_backup/config/backup_config.json'
DB=json.load(open(P,encoding='utf-8'))
conn=pymysql.connect(host=DB['host'],port=DB['port'],user=DB['user'],password=DB['password'],
                     database=DB['database'],connect_timeout=15,read_timeout=600,charset='utf8mb4')
cur=conn.cursor()
def q(sql,label,many=True):
    try:
        cur.execute(sql); return cur.fetchall() if many else (cur.fetchone() or ())
    except Exception as e:
        print('  [WARN]',label,'失败:',e,flush=True); return [] if many else ()

def cat(s):
    s=(s or '').lower()
    if s in ('working','active','生效','normal','ongoing'): return 'working'
    if 'owe' in s or 'arrear' in s or '欠' in s: return 'owe'
    if s in ('cancel','cancelled','refunded','unsubscribing','退订','退款','退订中') or 'cancel' in s or 'refund' in s or 'unsubscrib' in s: return 'cancel'
    if s in ('terminate','terminated','closed','stop','终止','停用') or 'terminat' in s or 'clos' in s or 'stop' in s: return 'terminate'
    return 'other'

try:
    # 网点字典
    sites={}
    for r in q("SELECT id,agency_id,distributor_id,merchant_id,business_id,store_manager_maker_id,site_status,name FROM t_site WHERE is_del=0","site"):
        sites[r[0]]={'agency_id':r[1],'distributor_id':r[2],'merchant_id':r[3],'business_id':r[4],
                     'store_manager_maker_id':r[5],'site_status':r[6],'name':r[7] or '未知网点'}

    # 协议主表（全量富化）
    print('拉取 t_exchange_agreement ...',flush=True)
    agr=[]
    for r in q("SELECT id,user_id,agency_id,site_id,status,activation_time,rent_expire_time,deposit_fee,sys_city_name,type,user_rent_id FROM t_exchange_agreement WHERE is_del=0","agr"):
        st=sites.get(r[3],{})
        agr.append({'id':r[0],'user_id':r[1],'agency_id':st.get('agency_id'),'site_id':r[3],'status':r[4] or '',
                    'activate':str(r[5] or '')[:10],'expire':str(r[6] or '')[:10],'deposit':r[7] or 0,
                    'city':r[8] or '','type':r[9] or '','user_rent_id':r[10],
                    'distributor_id':st.get('distributor_id'),'merchant_id':st.get('merchant_id'),
                    'business_id':st.get('business_id'),'store_manager_maker_id':st.get('store_manager_maker_id'),
                    'site_status':st.get('site_status'),'site_name':st.get('name')})
    print('  协议行数:',len(agr),flush=True)

    # 导购→协议
    prom_map={}
    for r in q("SELECT promoter_id,agreement_id,is_valid FROM t_promoter_relation WHERE is_del=0","promrel"):
        if r[2]==1 or str(r[2])=='1': prom_map[r[1]]=r[0]
    print('  导购关系数:',len(prom_map),flush=True)

    # 主表
    distributors=[{'id':r[0],'name':r[1] or '渠道商#%s'%r[0],'agency_id':r[2],'level':r[3],'status':r[4],'maker_id':r[5]} for r in q("SELECT id,name,agency_id,level,status,maker_id FROM t_distributor WHERE is_del=0","dis")]
    merchants=[{'id':r[0],'name':r[1] or '商户#%s'%r[0],'agency_id':r[2],'maker_id':r[3]} for r in q("SELECT id,name,agency_id,maker_id FROM t_merchant WHERE is_del=0","mch")]
    promoters=[{'id':r[0],'name':r[1] or '导购#%s'%r[0],'agency_id':r[2],'agency_employee_id':r[3],'maker_id':r[4],'phone':r[5],'share_count':r[6]} for r in q("SELECT id,name,agency_id,agency_employee_id,maker_id,phone,share_count FROM t_promoter WHERE is_del=0","pro")]
    agency_names={r[0]:r[1] for r in q("SELECT DISTINCT agency_id,agency_name FROM t_exchange_order WHERE agency_name IS NOT NULL AND agency_id IS NOT NULL","agn")}
    agency_ids=set(r[0] for r in q("SELECT DISTINCT agency_id FROM t_exchange_agreement WHERE agency_id IS NOT NULL","agid"))
    for s in sites.values():
        if s['agency_id']: agency_ids.add(s['agency_id'])
    agencies=[{'id':a,'name':agency_names.get(a) or '代理商#%s'%a} for a in agency_ids]
    # 代理商员工（关系表合集）
    agency_emps={}
    for r in q("SELECT agency_id,employee_id,name FROM t_warehouse_agency_employee WHERE is_del=0","aemp1"):
        if r[1]: agency_emps.setdefault(r[1],{'employee_id':r[1],'agency_id':r[0],'name':r[2] or '员工#%s'%r[1],'serve_sites':[],'merchant_id':None})
    for r in q("SELECT maker_id,name,serve_site_id,merchant_id FROM t_site_store_employee WHERE is_del=0","aemp2"):
        if r[0]:
            e=agency_emps.setdefault(r[0],{'employee_id':r[0],'agency_id':None,'name':r[1] or '员工#%s'%r[0],'serve_sites':[],'merchant_id':r[3]})
            if r[2]: e['serve_sites'].append(r[2])
    agency_emp_list=list(agency_emps.values())

    # status 枚举
    status_map={r[0]:(cat(r[0]),r[1]) for r in q("SELECT DISTINCT status,COUNT(*) FROM t_exchange_agreement WHERE status IS NOT NULL GROUP BY status","diststat")}

    # ---------- 单次 O(N) 聚合（用户级去重） ----------
    STAT=['working','owe','cancel','terminate','other']
    def newmap(): return {s:set() for s in STAT}
    agency_uids=defaultdict(newmap); dist_uids=defaultdict(newmap); merch_uids=defaultdict(newmap)
    emp_uids=defaultdict(newmap); prom_uids=defaultdict(newmap)
    agency_sites=defaultdict(lambda: defaultdict(int)); dist_sites=defaultdict(lambda: defaultdict(int))
    merch_sites=defaultdict(lambda: defaultdict(int)); emp_sites=defaultdict(lambda: defaultdict(int))
    agency_samp=defaultdict(list); dist_samp=defaultdict(list); merch_samp=defaultdict(list)
    emp_usamp=defaultdict(list); prom_samp=defaultdict(list); emp_ssamp=defaultdict(list)
    CAP=2000
    def add(uidmap,k,uid): uidmap[k].add(uid)
    def counts(uidmap):
        allu=set()
        for s in STAT: allu|=uidmap[s]
        return {'total':len(allu),'working':len(uidmap['working']),'owe':len(uidmap['owe']),
                'cancel':len(uidmap['cancel']),'terminate':len(uidmap['terminate']),'other':len(uidmap['other'])}

    # 网点 pass：按实体统计 site_status
    for sid,s in sites.items():
        st=s['site_status']
        if s['agency_id']: agency_sites[s['agency_id']][st]+=1
        if s['distributor_id']: dist_sites[s['distributor_id']][st]+=1
        if s['merchant_id']: merch_sites[s['merchant_id']][st]+=1
        if s['store_manager_maker_id']: emp_sites[s['store_manager_maker_id']][st]+=1
    # 协议 pass：按实体统计用户状态(去重) + 采样
    for a in agr:
        k=cat(a['status']); uid=a['user_id']; aid=a['agency_id']; did=a['distributor_id']; mid=a['merchant_id']; smid=a['store_manager_maker_id']
        pid=prom_map.get(a['id'])
        row={'agreement_id':a['id'],'user':uid,'city':a['city'],'type':a['type'],'status':a['status'],
             'activate':a['activate'],'expire':a['expire'],'deposit':a['deposit'],'site':a['site_name'] or '—','promoter':pid}
        if aid:
            add(agency_uids[aid],k,uid)
            if len(agency_samp[aid])<CAP: agency_samp[aid].append(row)
        if did:
            add(dist_uids[did],k,uid)
            if len(dist_samp[did])<CAP: dist_samp[did].append(row)
        if mid:
            add(merch_uids[mid],k,uid)
            if len(merch_samp[mid])<CAP: merch_samp[mid].append(row)
        if smid:
            add(emp_uids[smid],k,uid)
            if len(emp_usamp[smid])<CAP: emp_usamp[smid].append(row)
        if pid:
            add(prom_uids[pid],k,uid)
            if len(prom_samp[pid])<CAP: prom_samp[pid].append(row)
    # 员工网点明细
    for sid,s in sites.items():
        if s['store_manager_maker_id']:
            if len(emp_ssamp[s['store_manager_maker_id']])<CAP:
                emp_ssamp[s['store_manager_maker_id']].append({'site':s['name'],'site_status':s['site_status']})

    agency_ov=[{'id':a['id'],'name':a['name'],'sites':dict(agency_sites[a['id']]),'users':counts(agency_uids[a['id']]),'sample':agency_samp[a['id']]} for a in agencies]
    dist_ov=[{'id':d['id'],'name':d['name'],'agency_id':d['agency_id'],'level':d.get('level'),'status':d.get('status'),'sites':dict(dist_sites[d['id']]),'users':counts(dist_uids[d['id']]),'sample':dist_samp[d['id']]} for d in distributors]
    merch_ov=[{'id':m['id'],'name':m['name'],'agency_id':m['agency_id'],'sites':dict(merch_sites[m['id']]),'users':counts(merch_uids[m['id']]),'sample':merch_samp[m['id']]} for m in merchants]
    prom_ov=[{'id':p['id'],'name':p['name'],'agency_id':p['agency_id'],'agency_employee_id':p.get('agency_employee_id'),'phone':p.get('phone'),'users':counts(prom_uids[p['id']]),'sample':prom_samp[p['id']]} for p in promoters]
    agency_emp_ov=[{'employee_id':e['employee_id'],'name':e['name'],'agency_id':e['agency_id'],'merchant_id':e.get('merchant_id'),
        'sites':dict(emp_sites[e['employee_id']]),'users':counts(emp_uids[e['employee_id']]),
        'site_sample':emp_ssamp[e['employee_id']],'user_sample':emp_usamp[e['employee_id']]} for e in agency_emp_list]

    # 回写（保留原 personnel.employees/distributors）
    J=r'D:/workboddy file/dudu分析/citybike_backup/data/dashboard_data.json'
    D=json.load(open(J,encoding='utf-8'))
    P_=D.setdefault('personnel',{})
    P_['agencies']=agency_ov; P_['distributors_ov']=dist_ov; P_['merchants']=merch_ov
    P_['promoters']=prom_ov; P_['agency_employees']=agency_emp_ov; P_['status_map']=status_map
    P_['_note']='5 类实体总览(代理商/渠道商/代理商员工/商户/导购)；网点数×site_status 与 用户数×协议status(签约总/生效/欠租/退订/终止) 均取自真实表。分成金额 ⚠️ 占位待指定来源。'
    json.dump(D,open(J,'w',encoding='utf-8'),ensure_ascii=False)
    print('=== 抽取完成 ===',flush=True)
    print('代理商:',len(agency_ov),' 渠道商:',len(dist_ov),' 商户:',len(merch_ov),' 导购:',len(prom_ov),' 代理商员工:',len(agency_emp_ov),flush=True)
    print('协议总行:',len(agr),' 网点字典:',len(sites),' 导购关系:',len(prom_map),flush=True)
    print('status 归类(原始->类别,计数):',flush=True)
    for kk,vv in status_map.items(): print('   ',repr(kk),'->',vv,flush=True)
    conn.close()
except Exception as e:
    print('FATAL:',e,flush=True); traceback.print_exc(); conn.close(); sys.exit(2)
