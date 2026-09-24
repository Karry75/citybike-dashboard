# -*- coding: utf-8 -*-
# 人员看板 · 分成金额接入（实体真实映射，非单一数字）
# 数据底牌（已探明，不臆测）：
#   代理商: 27 套费用方案 t_exchange_fee_scheme(fee/electric_fee/..._*_ratio)，
#           经 t_site.scheme_id 按 agency_id 聚合（11064 网点有 scheme_id，21 distinct）。
#   渠道商: t_distributor 四级比例 first/second/third/third_Inviter_ratio（全 2991 有值，多为 0=未配置）。
#   商户:   t_goods_site_relation.promote_rebate_fee/sale_rebate_fee，经 site_id→t_site.merchant_id 聚合。
#   导购:   t_promoter.share_count + t_goods_order.promote_rebate_fee/sale_rebate_fee，
#           经 promote_maker_user_id→t_promoter_relation.user_id→promoter_id。
#   代理商员工: 继承所属代理商方案（agency_id→代理商方案）。
# 金额单位：库内金额字段以「分」计（方案 fee=390 分=¥3.90 与方案名"3.9元"吻合）→ ÷100 为元；
#           *_ratio 列为百分比（已是 %，不除）。
import json, pymysql, sys, traceback
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
def yuan(v): return round(float(v or 0)/100.0, 2)   # 分 -> 元

try:
    share={'agency':{}, 'distributor':{}, 'merchant':{}, 'promoter':{}, 'agency_emp':{}, '_note':''}

    # ---------- 1) 代理商：方案经 t_site.scheme_id 聚合 ----------
    print('① 代理商方案聚合 (t_site.scheme_id -> agency) ...',flush=True)
    # 先取 27 套方案定义
    schemes={}
    for r in q("SELECT id,name,fee,electric_fee,electric_fee_ratio,service_fee,service_fee_ratio,device_fee,device_fee_ratio,unit_fee,scheme_status FROM t_exchange_fee_scheme WHERE is_del=0","sch"):
        schemes[r[0]]={'scheme_id':r[0],'name':r[1] or '方案#%s'%r[0],
            'fee':yuan(r[2]),'electric_fee':yuan(r[3]),'electric_fee_ratio':float(r[4] or 0),
            'service_fee':yuan(r[5]),'service_fee_ratio':float(r[6] or 0),
            'device_fee':yuan(r[7]),'device_fee_ratio':float(r[8] or 0),'unit_fee':yuan(r[9]),
            'status':r[10] or ''}
    # 网点 -> (agency, scheme)
    aid_schemes={}
    for r in q("SELECT agency_id,scheme_id FROM t_site WHERE is_del=0 AND scheme_id IS NOT NULL AND agency_id IS NOT NULL","sitesch"):
        aid, sid = r[0], r[1]
        if sid in schemes:
            aid_schemes.setdefault(aid, {})
            aid_schemes[aid][sid]=schemes[sid]
    for aid, sd in aid_schemes.items():
        share['agency'][str(aid)]=[sd[k] for k in sorted(sd.keys())]
    print('   命中代理商方案:',len(share['agency']),' / 方案库:',len(schemes),flush=True)

    # ---------- 2) 渠道商：四级比例 ----------
    print('② 渠道商四级比例 (t_distributor) ...',flush=True)
    nz=0
    for r in q("SELECT id,first_level_ratio,second_level_ratio,third_level_ratio,third_level_Inviter_ratio FROM t_distributor WHERE is_del=0","disr"):
        vals=[float(r[1] or 0),float(r[2] or 0),float(r[3] or 0),float(r[4] or 0)]
        share['distributor'][str(r[0])]={'first':vals[0],'second':vals[1],'third':vals[2],'third_inviter':vals[3]}
        if any(v>0 for v in vals): nz+=1
    print('   渠道商:',len(share['distributor']),' 其中比例非0:',nz,flush=True)

    # ---------- 3) 商户：返利经 site->merchant ----------
    print('③ 商户返利 (goods_site_relation -> t_site.merchant_id) ...',flush=True)
    for r in q("""SELECT s.merchant_id, SUM(g.promote_rebate_fee), SUM(g.sale_rebate_fee)
                 FROM t_goods_site_relation g JOIN t_site s ON g.site_id=s.id AND s.is_del=0
                 WHERE g.is_del=0 AND s.merchant_id IS NOT NULL
                 GROUP BY s.merchant_id""","mchreb"):
        share['merchant'][str(r[0])]={'promote':yuan(r[1]),'sale':yuan(r[2])}
    print('   商户返利命中:',len(share['merchant']),flush=True)

    # ---------- 4) 导购：share_count + 订单返利 ----------
    print('④ 导购 share_count + 订单返利 ...',flush=True)
    sc={}
    for r in q("SELECT id,share_count FROM t_promoter WHERE is_del=0","psc"):
        sc[str(r[0])]=int(r[1] or 0)
    reb={}
    # 正确关联：goods_order.promote_maker_id = t_promoter.maker_id（已探明，user_id 路径不命中）
    for r in q("""SELECT p.id, SUM(go.promote_rebate_fee), SUM(go.sale_rebate_fee)
                 FROM t_goods_order go JOIN t_promoter p
                   ON go.promote_maker_id=p.maker_id AND p.is_del=0
                 WHERE go.is_del=0
                 GROUP BY p.id""","prreb"):
        reb[str(r[0])]={'promote':yuan(r[1]),'sale':yuan(r[2])}
    print('   导购返利经 relation 命中:',len(reb),flush=True)
    # 合并
    allp=set(sc.keys())|set(reb.keys())
    for pid in allp:
        share['promoter'][pid]={'share_count':sc.get(pid,0),
                                'rebate_promote':reb.get(pid,{}).get('promote',0.0),
                                'rebate_sale':reb.get(pid,{}).get('sale',0.0)}

    # ---------- 5) 代理商员工：继承代理商方案 ----------
    print('⑤ 代理商员工继承方案 ...',flush=True)
    ne=0
    for r in q("SELECT employee_id,agency_id FROM t_warehouse_agency_employee WHERE is_del=0 AND agency_id IS NOT NULL","aempsch"):
        aid=str(r[1])
        if aid in share['agency']:
            share['agency_emp'][str(r[0])]=share['agency'][aid]; ne+=1
    # 也补 t_site_store_employee 的 maker_id -> agency_id 路径
    for r in q("SELECT maker_id,agency_id FROM t_site_store_employee WHERE is_del=0 AND agency_id IS NOT NULL","aemp2sch"):
        aid=str(r[1])
        if aid in share['agency'] and str(r[0]) not in share['agency_emp']:
            share['agency_emp'][str(r[0])]=share['agency'][aid]; ne+=1
    print('   员工继承方案命中:',ne,flush=True)

    # ---------- 6) 收支对账单真实分成金额（用户指正：渠道商/导购真实分成在对账单，需汇总）----------
    # 关键：同一渠道商/导购在账单里可能以多种结算码收款(swapSite/signSite/swapSiteChannel/
    #   signSiteChannel/bank / promoter/l2_promoter 等)，故【不限 in_unit 码】，直接按
    #   in_unit_id 是否落在 t_distributor.id / t_promoter.id 来汇总其全部收款流水。
    #   金额 fee 单位「分」；SQL 端 GROUP BY 汇总，仅返回实体级小表，JSON 增量可忽略。
    print('⑥ 收支对账单 真实分成金额 (t_expense_bill 按实体汇总 fee，全结算码) ...',flush=True)
    bill={'distributor':{}, 'promoter':{}}
    for r in q("""SELECT in_unit_id, MAX(in_unit_name), SUM(fee), COUNT(*)
                 FROM t_expense_bill
                 WHERE is_del=0 AND in_unit_id IN (SELECT id FROM t_distributor WHERE is_del=0)
                 GROUP BY in_unit_id""","billdis"):
        if r[0] is None: continue
        bill['distributor'][str(r[0])]={'fen':int(r[2] or 0),'cnt':int(r[3] or 0),'name':r[1] or ''}
    for r in q("""SELECT in_unit_id, MAX(in_unit_name), SUM(fee), COUNT(*)
                 FROM t_expense_bill
                 WHERE is_del=0 AND in_unit_id IN (SELECT id FROM t_promoter WHERE is_del=0)
                 GROUP BY in_unit_id""","billpro"):
        if r[0] is None: continue
        bill['promoter'][str(r[0])]={'fen':int(r[2] or 0),'cnt':int(r[3] or 0),'name':r[1] or ''}
    print('   渠道商真实分成(全码汇总):',len(bill['distributor']),' 导购真实返利:',len(bill['promoter']),flush=True)

    # 回写
    J=r'D:/workboddy file\dudu分析\citybike_backup\data/dashboard_data.json'
    D=json.load(open(J,encoding='utf-8'))
    P_=D.setdefault('personnel',{})
    P_['share']=share
    P_['bill']=bill
    P_['_note']='5 类实体总览(代理商/渠道商/代理商员工/商户/导购)；网点数×site_status 与 用户数×协议status 取真实表。分成金额已按实体真实映射接入：代理商=费用方案(fee分÷100+4比例)，渠道商/导购=收支对账单(t_expense_bill)按实体汇总真实金额(分÷100)+笔数，渠道商另含四级比例(多为0=未配)，商户=推广/销售返利(分÷100)，导购另含分享数+订单返利，员工=继承代理商方案。'
    json.dump(D,open(J,'w',encoding='utf-8'),ensure_ascii=False)
    print('=== 分成抽取完成 ===',flush=True)
    print('代理商方案:',len(share['agency']),' 渠道商比例:',len(share['distributor']),' 商户返利:',len(share['merchant']),' 导购:',len(share['promoter']),' 员工继承:',len(share['agency_emp']),flush=True)
    conn.close()
except Exception as e:
    print('FATAL:',e,flush=True); traceback.print_exc(); conn.close(); sys.exit(2)
