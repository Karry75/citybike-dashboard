# -*- coding: utf-8 -*-
"""把优惠券6 / 设备扩展3 / 运维电池告警+拜访 的 draw 函数接到 DATA（graceful 降级）。"""
import re, io
P = r"D:/workboddy file/dudu分析/citybike_backup/html/template.html"
s = open(P, encoding="utf-8").read()

def repl_func(name, new):
    pat = r"function " + name + r"\(f\)\{.*?\n\}"
    s2, n = re.subn(pat, new, s, count=1, flags=re.DOTALL)
    assert n == 1, ("FUNC NOT MATCHED:", name, n)
    return s2

# ---------- C1 优惠券总览（全改） ----------
NEW_OVER = """function drawCouponOverview(f){
  const C=DATA.coupon||{};
  const ov=C.overview||{};
  const W='⚠️';
  const has=Object.keys(ov).length>0;
  kpis(document.getElementById('cp-over-kpis'),[
    {l:'优惠券总数量',v:has?fmt(ov.total_count):W,nav:'coupon',preset:{couponSub:'user-detail'},s:has?'':'待抽'},
    {l:'购买总金额(元)',v:has?fmt(ov.total_amount):W,s:has?'':'待抽'},
    {l:'购买总人数',v:has?fmt(ov.total_buyers):W,s:has?'':'待抽'},
    {l:'已核销数量',v:has?fmt(ov.used_count):W,nav:'coupon',preset:{couponSub:'user-detail'},s:has?'跳转明细':'待抽'},
    {l:'未使用数量',v:has?fmt(ov.unused_count):W,nav:'coupon',preset:{couponSub:'user-detail'},s:has?'跳转明细':'待抽'},
    {l:'未兑换数量',v:has?fmt(ov.unredeemed_count):W,nav:'coupon',preset:{couponSub:'user-detail'},s:has?'跳转明细':'待抽'},
    {l:'作废数量',v:has?fmt(ov.cancelled_count):W,nav:'coupon',preset:{couponSub:'user-detail'},s:has?'跳转明细':'待抽'},
    {l:'已退款数量',v:has?fmt(ov.refunded_count):W,nav:'coupon',preset:{couponSub:'user-detail'},s:has?'跳转明细':'待抽'},
    {l:'未付款数量',v:has?fmt(ov.unpaid_count):W,nav:'coupon',preset:{couponSub:'user-detail'},s:has?'跳转明细':'待抽'}
  ]);
  const bc=C.by_coupon||[];
  pie('cp-status-pie',[
    {name:'已核销',value:ov.used_count||0},{name:'未使用',value:ov.unused_count||0},
    {name:'未兑换',value:ov.unredeemed_count||0},{name:'作废',value:ov.cancelled_count||0},
    {name:'已退款',value:ov.refunded_count||0},{name:'未付款',value:ov.unpaid_count||0}
  ],null,has?'':'⚠️ 待抽数据');
  bar('cp-buy-bar',bc.map(d=>d.coupon_name),bc.map(d=>d.buy_count),'购买数量',true);
  const ts=(C.top_site||[]).slice(0,5), tm=(C.top_merchant||[]).slice(0,5);
  bar('cp-top-site',ts.map(d=>d.name),ts.map(d=>d.count),'门店',true);
  bar('cp-top-merchant',tm.map(d=>d.name),tm.map(d=>d.count),'商户',true);
  buildTable('cp-over-list',[
    {k:'coupon_name',h:'优惠券名称'},{k:'buy_count',h:'购买数量'},{k:'buy_amount',h:'购买金额'},
    {k:'used_count',h:'已核销',nav:'coupon',preset:{couponSub:'user-detail'}},
    {k:'unused_count',h:'未使用'},{k:'unredeemed_count',h:'未兑换'},
    {k:'cancelled_count',h:'作废'},{k:'refunded_count',h:'已退款'},{k:'unpaid_count',h:'未付款'}
  ],bc);
  document.getElementById('cp-count').textContent=bc.length?('（'+bc.length+'）'):'';
}"""
s = repl_func("drawCouponOverview", NEW_OVER)

# ---------- C4 合约份额采购（KPI+表） ----------
NEW_CP = """function drawCouponContractPurchase(f){
  const CT=(DATA.coupon&&DATA.coupon.contract)||[];
  const CThas=CT.length>0;
  kpis(document.getElementById('cppc-kpis'),[
    {l:'采购总额(元)',v:CThas?fmt(CT.reduce((a,b)=>a+(+b.total_amount||0),0)):'⚠️',s:CThas?'':'待抽'},
    {l:'采购单数',v:CThas?fmt(CT.length):'⚠️',s:CThas?'':'待抽'},
    {l:'涉及代理商数',v:CThas?fmt(new Set(CT.map(b=>b.agent_name)).size):'⚠️',s:CThas?'':'待抽'},
    {l:'待付款金额',v:'⚠️',s:'待抽'}
  ]);
  buildTable('cppc-list',[
    {k:'contract_id',h:'合约ID'},{k:'agent_name',h:'代理商'},{k:'coupon_name',h:'优惠券'},
    {k:'quota',h:'份额数量'},{k:'unit_price',h:'单价'},{k:'total_amount',h:'总金额'},
    {k:'purchase_count',h:'已采购量'},{k:'status',h:'状态'},{k:'create_time',h:'创建时间'}
  ],CT);
  document.getElementById('cppc-count').textContent=CThas?('（'+CT.length+'）'):'';
}"""
s = repl_func("drawCouponContractPurchase", NEW_CP)

# ---------- 设备·出入库（KPI+表） ----------
NEW_INV = """function drawDevInventory(f){
  const INV=(DATA.device&&DATA.device.inventory)||{};
  const IL=INV.list||[];
  const IK=INV.kpis||{};
  const INVhas=IL.length>0||Object.keys(IK).length>0;
  kpis(document.getElementById('w-inv-kpis'),[
    {l:'待入库设备数',v:('pending_in' in IK)?fmt(IK.pending_in):'⚠️',s:INVhas?'':'待抽'},
    {l:'今日入库',v:('today_in' in IK)?fmt(IK.today_in):'⚠️',s:INVhas?'':'待抽'},
    {l:'今日出库',v:('today_out' in IK)?fmt(IK.today_out):'⚠️',s:INVhas?'':'待抽'},
    {l:'库存总量',v:('total' in IK)?fmt(IK.total):'⚠️',s:INVhas?'':'待抽'}
  ]);
  buildTable('w-inv-list',[
    {k:'record_id',h:'记录ID'},{k:'device_type',h:'设备类型'},{k:'device_id',h:'设备SN/ID'},
    {k:'op_type',h:'操作类型'},{k:'operator',h:'操作人'},{k:'op_time',h:'操作时间'},
    {k:'from_obj',h:'流出对象'},{k:'to_obj',h:'流入对象'},{k:'result',h:'运营结果'}
  ],IL);
}"""
s = repl_func("drawDevInventory", NEW_INV)

# ---------- 设备·故障（KPI+表） ----------
NEW_FAULT = """function drawDevFault(f){
  const FD=DATA.device&&DATA.device.fault||{};
  const FL=FD.list||[];
  const FK=FD.kpis||{};
  const Fhas=FL.length>0||Object.keys(FK).length>0;
  kpis(document.getElementById('w-fault-kpis'),[
    {l:'故障换电柜数',v:('cabinet' in FK)?fmt(FK.cabinet):'⚠️',s:Fhas?'':'待抽'},
    {l:'故障电池数',v:('battery' in FK)?fmt(FK.battery):'⚠️',s:Fhas?'':'待抽'},
    {l:'已维修',v:('repaired' in FK)?fmt(FK.repaired):'⚠️',s:Fhas?'':'待抽'},
    {l:'已报废',v:('scrapped' in FK)?fmt(FK.scrapped):'⚠️',s:Fhas?'':'待抽'}
  ]);
  buildTable('w-fault-list',[
    {k:'device_id',h:'设备ID/SN'},{k:'device_type',h:'设备类型'},{k:'fault_type',h:'故障类型'},
    {k:'fault_time',h:'故障时间'},{k:'location',h:'所在位置'},{k:'status',h:'处理状态'},
    {k:'handler',h:'处理人'},{k:'handle_time',h:'处理时间'}
  ],FL);
}"""
s = repl_func("drawDevFault", NEW_FAULT)

# ---------- 运维·电池告警（KPI+图+表） ----------
NEW_BAT = """function drawOpsBatAlarm(f){
  const BA=(DATA.ops&&DATA.ops.bat_alarm)||[];
  const BAhas=BA.length>0;
  const lvl=BAhas?BA.reduce((m,r)=>{const k=(r.level==='high'||r.level==='紧急')?'high':'normal';m[k]=(m[k]||0)+1;return m;},{}):{};
  kpis(document.getElementById('oba-kpis'),[
    {l:'告警总数',v:BAhas?fmt(BA.length):'⚠️',s:BAhas?'':'待抽'},
    {l:'紧急告警',v:BAhas?fmt(lvl.high||0):'⚠️',tone:'red',s:BAhas?'':'待抽'},
    {l:'一般告警',v:BAhas?fmt(lvl.normal||0):'⚠️',tone:'amber',s:BAhas?'':'待抽'},
    {l:'未解决',v:BAhas?fmt(BA.filter(r=>!r.status||r.status==='未解决'||r.status==='open'||r.status==='pending').length):'⚠️',tone:'red',s:BAhas?'':'待抽'}
  ]);
  pie('oba-level',[{name:'紧急',value:lvl.high||0},{name:'一般',value:lvl.normal||0}],null,BAhas?'':'⚠️ 待抽');
  bar('oba-type',BAhas?BA.map(r=>r.type||'其他'):['⚠️'],BAhas?BA.map(r=>1):[0],'告警数',true);
  buildTable('oba-detail',[
    {k:'warn_id',h:'告警ID'},{k:'battery_sn',h:'电池SN'},{k:'level',h:'等级',f:v=>tag(v,(v==='high'||v==='紧急')?'red':'amber')},
    {k:'type',h:'告警类型'},{k:'msg',h:'告警内容'},{k:'location',h:'位置'},
    {k:'city',h:'城市'},{k:'created_at',h:'触发时间'},{k:'status',h:'状态'}
  ],BA);
  var capEl=document.getElementById('oba-cap'); if(capEl)capEl.textContent=BAhas?('（'+BA.length+'）'):'';
}"""
s = repl_func("drawOpsBatAlarm", NEW_BAT)

# ---------- 运维·拜访记录（KPI+表） ----------
NEW_VIS = """function drawOpsSiteVisit(f){
  const SV=(DATA.ops&&DATA.ops.site_visit)||[];
  const SVhas=SV.length>0;
  kpis(document.getElementById('osv-kpis'),[
    {l:'拜访记录总数',v:SVhas?fmt(SV.length):'⚠️',s:SVhas?'':'待抽'},
    {l:'本周拜访',v:SVhas?fmt(SV.filter(r=>{try{const d=new Date(r.visit_time);const n=new Date();const onew=n-new Date(n.getFullYear(),n.getMonth(),n.getDate()-7);return d>=onew;}catch(e){return false;}}).length):'⚠️',s:SVhas?'':'待抽'},
    {l:'问题数',v:SVhas?fmt(SV.filter(r=>r.problem_desc).length):'⚠️',tone:'red',s:SVhas?'':'待抽'},
    {l:'已解决',v:SVhas?fmt(SV.filter(r=>r.status==='已解决'||r.status==='done'||r.status==='resolved').length):'⚠️',tone:'green',s:SVhas?'':'待抽'}
  ]);
  buildTable('osv-detail',[
    {k:'visit_id',h:'拜访ID'},{k:'staff_name',h:'拜访人'},{k:'staff_id',h:'拜访人ID'},
    {k:'site_name',h:'网点名称'},{k:'city',h:'城市'},{k:'visit_time',h:'拜访时间'},
    {k:'problem_desc',h:'问题描述'},{k:'handle_result',h:'处理结果'},
    {k:'photos',h:'拍照记录'},{k:'status',h:'状态'}
  ],SV);
  var capEl=document.getElementById('osv-cap'); if(capEl)capEl.textContent=SVhas?('（'+SV.length+'）'):'';
}"""
s = repl_func("drawOpsSiteVisit", NEW_VIS)

# ---------- 简单表尾：把 ],[]); 换成读取 DATA ----------
def tail(table_id, count_id, data_expr):
    old = "  ],[]);\n  document.getElementById('%s').textContent='';" % count_id
    new = ("  ],(%s)||[]);\n  document.getElementById('%s').textContent=((%s)||[]).length?('（'+(%s||[]).length+'）'):'';"
           % (data_expr, count_id, data_expr, data_expr))
    assert old in s, ("TAIL NOT FOUND:", table_id, count_id)
    return s.replace(old, new, 1)

s = tail('cpai-list', 'cpai-count', "(DATA.coupon&&DATA.coupon.agent_issue)")
s = tail('cpmi-list', 'cpmi-count', "(DATA.coupon&&DATA.coupon.merchant_issue)")
s = tail('cpud-list', 'cpud-count', "(DATA.coupon&&DATA.coupon.user_detail)")
s = tail('w-tf-list', 'tf-count', "(DATA.device&&DATA.device.transfer)")

# 领券中心：表尾 + 分页
old_r = "  ],[]);\n  document.getElementById('cpr-count').textContent='';\n  document.getElementById('cpr-pagination').textContent='共 0 条/页';"
new_r = ("  ],(DATA.coupon&&DATA.coupon.resource)||[]);\n"
       "  document.getElementById('cpr-count').textContent=((DATA.coupon&&DATA.coupon.resource)||[]).length?('（'+((DATA.coupon&&DATA.coupon.resource)||[]).length+'）'):'';\n"
       "  document.getElementById('cpr-pagination').textContent='共 '+((DATA.coupon&&DATA.coupon.resource)||[]).length+' 条/页';")
assert old_r in s, "RESOURCE TAIL NOT FOUND"
s = s.replace(old_r, new_r, 1)

open(P, "w", encoding="utf-8").write(s)
print("PATCHED template.html OK")
print("len:", len(s))
