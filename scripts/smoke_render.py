# -*- coding: utf-8 -*-
import re
# 用轻量自包含版（应用逻辑与全量版一致，DATA 仅数 MB）做渲染回归，
# 避免把 297MB 全量 DATA 塞进 _smoke2.js 导致 node 解析 OOM/极慢。
html = open('citybike_selfcontained/index.html', encoding='utf-8').read()
scripts = re.findall(r'<script>(.*?)</script>', html, re.DOTALL)
main = max(scripts, key=len)

harness = r"""
function makeEl(){
  return {
    _html:'', set innerHTML(v){this._html=v;}, get innerHTML(){return this._html;},
    textContent:'', value:'', style:{}, dataset:{},
    classList:{ _s:new Set(), add(){}, remove(){}, toggle(){}, contains(){return false;} },
    addEventListener(){}, appendChild(){}, removeChild(){}, setAttribute(){}, getAttribute(){return null;},
    insertAdjacentHTML(){},
    querySelectorAll(){return [];}, querySelector(){return makeEl();},
    children:[], parentNode:null, focus(){}, click(){}, offsetWidth:100, offsetHeight:100,
    closest(){return makeEl();}, remove(){}, setAttribute(){}
  };
}
const _els = {};
function getEl(id){ if(!_els[id]) _els[id]=makeEl(); return _els[id]; }
global.document = {
  getElementById(id){ return getEl(id); },
  querySelector(s){ return makeEl(); },
  querySelectorAll(s){ return []; },
  createElement(){ return makeEl(); },
  addEventListener(){}, body:makeEl()
};
global.window = global;
global.addEventListener = ()=>{};
global.removeEventListener = ()=>{};
global.scrollTo = ()=>{};
global.localStorage = { _m:{}, getItem(k){return this._m[k]||null;}, setItem(k,v){this._m[k]=v;} };
global.setTimeout = (f)=>{};
global.console = console;
function _chart(){ return { setOption(){}, resize(){}, dispose(){}, on(){}, off(){}, clear(){}, renderToCanvas(){} }; }
global.echarts = {
  init(){ return _chart(); },
  getInstanceByDom(){ return null; },
  registerMap(){}, registerTheme(){}, connect(){}, graphic:{}
};
global.alert = (m)=>{ console.log('ALERT:', m); };
global.location = { search:'?demo=1', href:'http://localhost/', reload(){}, assign(){} };
"""

footer = r"""
const mods = ['overview','user','sales','site','device','ops','personnel','finance','service','analytics','coupon','bizdec'];
let errs = [];
try { render(); } catch(e){ errs.push('render(): '+e.message+'\n'+(e.stack||'').split('\n').slice(0,5).join('\n')); }
for (const m of mods){
  try { applyFilters(m); } catch(e){ errs.push('applyFilters('+m+'): '+e.message); }
  try { if (typeof navigate==='function') navigate(m); } catch(e){ errs.push('navigate('+m+'): '+e.message); }
}
// drill into ops submenus + coupon submenus
const subcalls = ['drawOpsCabAlarm','drawOpsBatAlarm','drawOpsWorkorder','drawOpsSiteVisit',
  'drawCouponOverview','drawCouponAgentIssue','drawCouponMerchantIssue','drawCouponContractPurchase','drawCouponUserDetail','drawCouponResource',
  'drawDevInventory','drawDevFault','drawDevTransfer','drawSiteExchange','drawSiteSingle',
  'drawUserVehicle','drawUserDeposit','drawDashExch','drawDashUV','drawSiteExchangeMap','drawUserUvMap',
  'drawUserExchOrders','drawUserUnsub','drawUserTraj'];
for (const fn of subcalls){ try{ if(typeof eval(fn)==='function') eval(fn+'({});'); }catch(e){ errs.push(fn+': '+e.message); } }
// 钻取链路验证（城市→区域→街道），防止参数名 typo 类 bug 漏网
try {
  const _g = (typeof DATA!=='undefined' && DATA.geo) || {};
  if (_g.exch_city_area_street && _g.exch_city_area_street.length){
    const _c=_g.exch_city_area_street[0].city;
    drillExch(_c);
    const _a=_g.exch_city_area_street[0].areas[0];
    if(_a) drillExchStreet(_c,_a.area,_a.streets);
  }
  if (_g.user_city_area && _g.user_city_area.length){ drillUV(_g.user_city_area[0].city); }
} catch(e){ errs.push('drill-chain: '+e.message); }
// 人员看板 5 大实体总览
const peCalls = ['agency','distributor','agency_emp','merchant','promoter'];
for (const sub of peCalls){ try{ if(typeof drawPersonnelOv==='function') drawPersonnelOv(sub); }catch(e){ errs.push('drawPersonnelOv('+sub+'): '+e.message); } }
try{ if(typeof switchPersonnelSub==='function') switchPersonnelSub('overview'); }catch(e){ errs.push('switchPersonnelSub: '+e.message); }
try{ if(typeof switchSiteSub==='function') switchSiteSub('single'); }catch(e){ errs.push('switchSiteSub: '+e.message); }
try{ if(typeof switchSiteSub==='function') switchSiteSub('dist'); }catch(e){ errs.push('switchSiteSub(dist): '+e.message); }
try{ if(typeof switchUserSub==='function') switchUserSub('uvmap'); }catch(e){ errs.push('switchUserSub(uvmap): '+e.message); }
try{ if(typeof switchUserSub==='function') switchUserSub('exchorders'); }catch(e){ errs.push('switchUserSub(exchorders): '+e.message); }
try{ if(typeof switchUserSub==='function') switchUserSub('unsub'); }catch(e){ errs.push('switchUserSub(unsub): '+e.message); }
try{ if(typeof switchUserSub==='function') switchUserSub('traj'); }catch(e){ errs.push('switchUserSub(traj): '+e.message); }
// 财务看板四子菜单钻取
try{ if(typeof switchFinSub==='function') switchFinSub('sitefee'); }catch(e){ errs.push('switchFinSub(sitefee): '+e.message); }
try{ if(typeof switchFinSiteSub==='function') switchFinSiteSub('elec_detail'); }catch(e){ errs.push('switchFinSiteSub(elec_detail): '+e.message); }
try{ if(typeof switchFinSiteSub==='function') switchFinSiteSub('split_overview'); }catch(e){ errs.push('switchFinSiteSub(split_overview): '+e.message); }
try{ if(typeof switchFinSiteSub==='function') switchFinSiteSub('split_detail'); }catch(e){ errs.push('switchFinSiteSub(split_detail): '+e.message); }
try{ if(typeof switchFinSub==='function') switchFinSub('withdraw'); }catch(e){ errs.push('switchFinSub(withdraw): '+e.message); }
try{ if(typeof switchFinSub==='function') switchFinSub('recon'); }catch(e){ errs.push('switchFinSub(recon): '+e.message); }
try{ if(typeof drawFinRecon==='function') drawFinRecon({search:''}, DATA.finance.detail||[], false); }catch(e){ errs.push('drawFinRecon: '+e.message); }
// 模型驱动子菜单：电池健康评估 + 网点价值评估（Task#275/#277）
try{ if(typeof drawDevBatteryHealth==='function') drawDevBatteryHealth(); }catch(e){ errs.push('drawDevBatteryHealth: '+e.message); }
try{ if(typeof drawSiteValue==='function') drawSiteValue(); }catch(e){ errs.push('drawSiteValue: '+e.message); }
// 4 套大屏（Task#278-#281）
try{ if(typeof drawScreen4==='function') drawScreen4(); }catch(e){ errs.push('drawScreen4: '+e.message); }
try{ if(typeof drawScreen1==='function') drawScreen1(); }catch(e){ errs.push('drawScreen1: '+e.message); }
try{ if(typeof drawScreen2==='function') drawScreen2(); }catch(e){ errs.push('drawScreen2: '+e.message); }
try{ if(typeof drawScreen3==='function') drawScreen3(); }catch(e){ errs.push('drawScreen3: '+e.message); }
try{ if(typeof switchScreenTab==='function') switchScreenTab(2); }catch(e){ errs.push('switchScreenTab: '+e.message); }
// 经营决策（bizdec）三子模块钻取
try{ if(typeof drawBizDec==='function') drawBizDec(); }catch(e){ errs.push('drawBizDec: '+e.message); }
try{ if(typeof drawBizDecPkg==='function') drawBizDecPkg(); }catch(e){ errs.push('drawBizDecPkg: '+e.message); }
try{ if(typeof drawBizDecOps==='function') drawBizDecOps(); }catch(e){ errs.push('drawBizDecOps: '+e.message); }
try{ if(typeof drawBizDecSite==='function') drawBizDecSite(); }catch(e){ errs.push('drawBizDecSite: '+e.message); }
// 新增：销售看板 协议签约 + 套餐购买明细（图片1/图片2 格式）
console.log('SMOKE-STEP: switchSalesSub(agreement_sign)');
try{ if(typeof switchSalesSub==='function') switchSalesSub('agreement_sign'); }catch(e){ errs.push('switchSalesSub(agreement_sign): '+e.message); }
console.log('SMOKE-STEP: drawAgreementSignTable');
try{ if(typeof drawAgreementSignTable==='function') drawAgreementSignTable(); }catch(e){ errs.push('drawAgreementSignTable: '+e.message); }
console.log('SMOKE-STEP: switchSalesSub(package_purchase)');
try{ if(typeof switchSalesSub==='function') switchSalesSub('package_purchase'); }catch(e){ errs.push('switchSalesSub(package_purchase): '+e.message); }
console.log('SMOKE-STEP: drawPackagePurchaseTable');
try{ if(typeof drawPackagePurchaseTable==='function') drawPackagePurchaseTable(); }catch(e){ errs.push('drawPackagePurchaseTable: '+e.message); }
console.log('SMOKE-STEP: device groups start');
// 新增：设备资产看板 三组重组（设备基础表/调拨流通记录/异常分类统计）
const _devBasic=['cabinet','cablist','battery','batlist','warehouse','rental'];
const _devFlow=['circulation','transfer','inventory'];
const _devAnomaly=['fault','anomaly12','health'];
for(const t of _devBasic){ console.log('SMOKE-STEP: switchDevTab(basic,'+t+')'); try{ switchDeviceSub('basic'); switchDevTab('basic', t); }catch(e){ errs.push('switchDevTab(basic,'+t+'): '+e.message); } }
for(const t of _devFlow){ console.log('SMOKE-STEP: switchDevTab(flow,'+t+')'); try{ switchDeviceSub('flow'); switchDevTab('flow', t); }catch(e){ errs.push('switchDevTab(flow,'+t+'): '+e.message); } }
for(const t of _devAnomaly){ console.log('SMOKE-STEP: switchDevTab(anomaly,'+t+')'); try{ switchDeviceSub('anomaly'); switchDevTab('anomaly', t); }catch(e){ errs.push('switchDevTab(anomaly,'+t+'): '+e.message); } }
console.log('SMOKE-STEP: device groups done');
console.log('MODULES TESTED:', mods.length, '+', subcalls.length, 'sub-draws + new sales/device panels');
if (errs.length){ console.log('\n==== RUNTIME ERRORS ('+errs.length+') ===='); errs.forEach(e=>console.log(' - '+e)); }
else { console.log('\nNO RUNTIME ERRORS — all modules + sub-draws rendered clean.'); }
"""

open('_smoke2.js','w',encoding='utf-8').write(harness + main + footer)
print("wrote _smoke2.js, main chars:", len(main))
