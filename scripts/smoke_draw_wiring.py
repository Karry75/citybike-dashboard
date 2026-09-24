# -*- coding: utf-8 -*-
"""冒烟测试：用合成数据跑 11 个 draw 函数，确认数据分支不抛错。"""
import re, subprocess, os
HTML = r"D:/workboddy file/dudu分析/citybike_backup/citybike_dashboard/index.html"
html = open(HTML, encoding="utf-8").read()
script = max(re.findall(r"<script>(.*?)</script>", html, re.DOTALL), key=len)

FUNCS = ["drawCouponOverview", "drawCouponAgentIssue", "drawCouponMerchantIssue",
          "drawCouponContractPurchase", "drawCouponUserDetail", "drawCouponResource",
          "drawDevInventory", "drawDevFault", "drawDevTransfer",
          "drawOpsBatAlarm", "drawOpsSiteVisit"]
extracted = []
for fn in FUNCS:
    m = re.search(r"function " + fn + r"\(f\)\{.*?\n\}", script, re.DOTALL)
    assert m, "extract fail: " + fn
    extracted.append(m.group(0))

stub = r"""
var DATA = {
  coupon: {
    overview:{total_count:123,total_amount:4567,total_buyers:89,used_count:50,unused_count:30,unredeemed_count:10,cancelled_count:5,refunded_count:3,unpaid_count:2},
    by_coupon:[{coupon_name:'券A',buy_count:100,buy_amount:2000,used_count:50,unused_count:30,unredeemed_count:10,cancelled_count:5,refunded_count:3,unpaid_count:2}],
    top_site:[{name:'门店X',count:20},{name:'门店Y',count:15}],
    top_merchant:[{name:'商户M',count:30},{name:'商户N',count:25}],
    agent_issue:[{record_id:1,coupon_name:'券A',redeem_code:'RC1',issuer:'张三',issue_date:'2026-07-01',max_purchase:5,user_info:'用户1',use_status:'已使用',pay_status:'已付款',protocol_id:'P1',battery_product:'电池B',site_name:'网点Z',package:'套餐C',vehicle_brand:'品牌D',pay_amount_due:100,pay_amount_real:90,pay_date:'2026-07-02',pay_method:'微信'}],
    merchant_issue:[{redeem_id:1,batch_no:'B1',redeem_code:'RC2',coupon_info:'券A',order_id:'O1',ship_info:'快递',redeem_user:'用户2',redeem_status:'已兑换',cancel_info:'',use_info:'已用',site_name:'网点Z',issuer_info:'李四',agreement_no:'A1',pay_info:'已付',merchant_info:'商户M'}],
    contract:[{contract_id:1,agent_name:'代理商A',coupon_name:'券A',quota:100,unit_price:20,total_amount:2000,purchase_count:50,status:'生效',create_time:'2026-07-01'}],
    user_detail:[{record_id:2,coupon_name:'券B',redeem_code:'RC3',issuer:'王五',issue_date:'2026-07-03',max_purchase:3,user_info:'用户3',use_status:'未使用',pay_status:'未付款',protocol_id:'P2',battery_product:'电池C',site_name:'网点W',package:'套餐D',vehicle_brand:'品牌E',pay_amount_due:80,pay_amount_real:0,pay_date:'',pay_method:''}],
    resource:[{resource_id:1,coupon_title:'标题',discount_type:'满减',apply_product:'电池',discount_value:10,city_area:'深圳',battery_model:'M1',get_type:'领取',disabled:'正常',creator:'员工1',created_at:'2026-07-01'}]
  },
  device: {
    inventory:{kpis:{pending_in:5,today_in:3,today_out:2,total:100}, list:[{record_id:1,device_type:'换电柜',device_id:'D1',op_type:'入库',operator:'op',op_time:'2026-07-01',from_obj:'工厂',to_obj:'仓库',result:'成功'}]},
    fault:{kpis:{cabinet:2,battery:3,repaired:1,scrapped:1}, list:[{device_id:'D2',device_type:'电池',fault_type:'鼓包',fault_time:'2026-07-01',location:'网点',status:'待处理',handler:'张三',handle_time:''}]},
    transfer:[{record_id:1,operator_id:10,operator_name:'李四',op_time:'2026-07-01',device_type:'换电柜',device_id:'D3',op_type:'调拨',result:'成功',from_obj:'A',to_obj:'B'}]
  },
  ops: {
    bat_alarm:[{warn_id:1,battery_sn:'B1',level:'high',type:'过温',msg:'高温',location:'网点',city:'深圳',created_at:'2026-07-01',status:'open'}],
    site_visit:[{visit_id:1,staff_name:'王五',staff_id:20,site_name:'网点',city:'深圳',visit_time:'2026-07-20',problem_desc:'问题',handle_result:'已解决',photos:'',status:'done'}]
  }
};
function fmt(x){ return (x==null||x==='')?'':(''+x); }
function tag(v,c){ return v==null?'':(''+v); }
function stTag(v){ return v==null?'':(''+v); }
function kpis(el,arr){ if(!Array.isArray(arr)) throw new Error('kpis arr not array'); arr.forEach(function(o){ if(o.v===undefined) throw new Error('KPI v undefined: '+JSON.stringify(o)); }); }
function buildTable(id,cols,rows){ if(!Array.isArray(cols)) throw new Error('cols not array '+id); if(!Array.isArray(rows)) throw new Error('rows not array '+id); }
function pie(id,data){ if(!Array.isArray(data)) throw new Error('pie data not array '+id); }
function bar(id,labels,vals){ if(!Array.isArray(labels)) throw new Error('bar labels not array'); if(!Array.isArray(vals)) throw new Error('bar vals not array'); }
function lineTrend(){}
var document={ getElementById:function(){ return {textContent:'',style:{},classList:{toggle:function(){},add:function(){},remove:function(){}},querySelectorAll:function(){return [];},appendChild:function(){},addEventListener:function(){}}; }, querySelectorAll:function(){return [];}, addEventListener:function(){}, querySelector:function(){return null;} };
var window={ scrollTo:function(){} };
"""

caller = "\n" + "\n".join(f + "({});" for f in FUNCS) + "\nconsole.log('ALL 11 DRAWS OK');\n"

harness = stub + "\n".join(extracted) + caller
open(r"D:/workboddy file/dudu分析/citybike_backup/_smoke.js", "w", encoding="utf-8").write(harness)
r = subprocess.run(["C:/Users/Karry/.workbuddy/binaries/node/versions/22.22.2/node.exe", r"D:/workboddy file/dudu分析/citybike_backup/_smoke.js"], capture_output=True, text=True)
print("STDOUT:", r.stdout.strip())
print("STDERR:", r.stderr.strip()[:2000])
print("RC:", r.returncode)
os.remove(r"D:/workboddy file/dudu分析/citybike_backup/_smoke.js")
