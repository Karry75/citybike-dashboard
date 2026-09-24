# -*- coding: utf-8 -*-
"""运营总览专项快速回归（比 smoke_render.py 快得多）。

真正模拟浏览器引导：
  1. 从构建产物抽出 B64 -> node 内 gunzip -> 填 global.DATA
  2. 置 window.__BACKEND=true，使 app 尾部 IIFE 走“等待”分支
  3. 显式调用 bootApp()（包裹 try/catch），覆盖全 15 视图渲染
  4. 再跑 drawDashOps / donutList / 趋势等靶向检查

用法：
    python scripts/smoke_ops.py            # 生成 _smoke_ops.js
    node _smoke_ops.js                     # 执行，看 NO RUNTIME ERRORS
"""
import re, io, os

ROOT = r"D:/workboddy file/dudu分析/citybike_backup"
SRC = ROOT + "/citybike_minimal/index.html"

html = io.open(SRC, encoding="utf-8").read()

# 抓最后一个 </body> 之前的主脚本
scripts = re.findall(r"<script\b[^>]*>([\s\S]*?)</script>", html)
print("script blocks: %d, sizes: %s" % (len(scripts), [len(s) for s in scripts]))
# 主脚本 = 含 bootApp/render 定义的块（不用“最大块”，避免选中 ECharts）
main = next((s for s in scripts if 'function bootApp' in s or 'function render' in s), None)
if not main:
    main = max(scripts, key=len)
print("main chars:", len(main))

# 当前构建为 gz-fetch 引导（const DATA={} + fetch ./dashboard_data_lite.json.gz），
# 故直接读本地 gz 文件回填 DATA（与浏览器 boot 引导等价），不再依赖内联 B64。
LITE_GZ = ROOT + "/citybike_minimal/dashboard_data_lite.json.gz"
assert os.path.exists(LITE_GZ), '未找到 ' + LITE_GZ
print("lite gz: %s (%.2f MB)" % (LITE_GZ, os.path.getsize(LITE_GZ)/1024/1024))

harness = r"""
// ── 最小 DOM / ECharts 桩 ──
const _els = {};
function mkEl(id){
  return {
    id:id, innerHTML:'', textContent:'', style:{}, className:'', dataset:{},
    children:[], classList:{add(){},remove(){},toggle(){},contains(){return false}},
    appendChild(c){this.children.push(c);return c;},
    removeChild(){}, insertAdjacentHTML(){}, setAttribute(){}, getAttribute(){return null;},
    addEventListener(){}, removeEventListener(){}, click(){},
    querySelector(sel){ return mkEl(id+sel); },
    querySelectorAll(){ return []; },
    closest(){ return null; },
    getBoundingClientRect(){ return {width:300,height:200,top:0,left:0}; },
    offsetWidth:300, offsetHeight:200, scrollTop:0, value:'', checked:false,
  };
}
global.document = {
  getElementById(id){ if(!_els[id]) _els[id]=mkEl(id); return _els[id]; },
  querySelector(sel){ return mkEl(sel); },
  querySelectorAll(){ return []; },
  createElement(t){ return mkEl('<'+t+'>'); },
  addEventListener(){}, body: mkEl('body'), head: mkEl('head'),
};
global.window = { addEventListener(){}, removeEventListener(){}, innerWidth:1440, innerHeight:900,
                  __BACKEND:true, location:{href:'',search:''}, localStorage:{getItem(){return null},setItem(){}},
                  matchMedia(){return {matches:false,addListener(){}}}, devicePixelRatio:1 };
global.location = global.window.location;
global.navigator = { userAgent:'node' };
global.echarts = {
  init(){ return { setOption(){}, resize(){}, dispose(){}, on(){}, off(){},
                   getWidth(){return 300}, getHeight(){return 200}, showLoading(){}, hideLoading(){} }; },
  getInstanceByDom(){ return null; },
  registerMap(){}, getMap(){ return null; }, graphic:{ LinearGradient:function(){} },
};
global.fetch = function(){ return Promise.resolve({ok:true,json(){return Promise.resolve({})},text(){return Promise.resolve('')}}); };
global.alert = function(){};
global.requestAnimationFrame = function(f){ return 0; };
global.setTimeout = function(){ return 0; };   // 阻断异步链，避免挂起
global.setInterval = function(){ return 0; };
// 全局错误兜底捕获
const __uncaught = [];
process.on('uncaughtException', e=>{ __uncaught.push('uncaught: '+(e&&e.message||e)); });
"""

# footer：先解压 B64 填 DATA，再显式 bootApp + 靶向检查
footer = r"""
// ── 读 lite gz -> 填 DATA（模拟浏览器 boot 引导）──
const zlib = require('zlib');
const fs = require('fs');
let __bootData = null;
try {
  const buf = fs.readFileSync("{{LITE_GZ}}");
  const txt = zlib.gunzipSync(buf).toString('utf-8');
  __bootData = JSON.parse(txt);
} catch(e){ console.log('读 lite gz 失败: '+e.message); process.exitCode=1; }

if (__bootData){
  // 关键：main 里有顶层 const DATA={}，是词法绑定，不能靠 global.DATA 赋值改到。
  // 必须像浏览器引导那样“原地改属性”，否则裸 DATA 仍是空对象。
  for (var k in __bootData){ DATA[k] = __bootData[k]; }
  global.window.DATA = DATA;
}

const errs = [];
function T(name, fn){ try{ fn(); }catch(e){ errs.push(name+': '+e.message); } }

console.log('DATA keys:', Object.keys(typeof DATA!=='undefined'?DATA:{}).join(','));
if (typeof DATA!=='undefined'){
  console.log('  analytics.daily :', ((DATA.analytics||{}).daily||[]).length, '天');
  console.log('  user.city_rank  :', ((DATA.user||{}).city_rank||[]).length, '城');
  console.log('  dashboard.ops   :', Object.keys(((DATA.dashboard||{}).ops)||{}).join(','));
}

// 显式调用 bootApp（已在 harness 置 __BACKEND=true，app 尾部 IIFE 不会空跑）
T('bootApp (全15视图渲染)', function(){
  if(typeof bootApp!=='function') throw new Error('未定义');
  bootApp();
});
T('buildMonthlyTrendFromDaily', function(){
  if(typeof buildMonthlyTrendFromDaily!=='function') throw new Error('未定义');
  const tr=buildMonthlyTrendFromDaily();
  console.log('  月度趋势:', tr.length, '个月', tr.length?(tr[0].month+' ~ '+tr[tr.length-1].month):'');
  if(tr.length){ const l=tr[tr.length-1]; console.log('  末月:', JSON.stringify(l)); }
});
T('fmtShort', function(){
  if(typeof fmtShort!=='function') throw new Error('未定义');
  [[7535,'7,535'],[74717,'7.5万'],[10874274,'1087.4万']].forEach(c=>console.log('  fmtShort('+c[0]+') =', fmtShort(c[0])));
});
T('donutList', function(){
  if(typeof donutList!=='function') throw new Error('未定义');
  donutList('t-donut', [{name:'换电网点',value:7535},{name:'租车网点',value:3026},
    {name:'售车网点',value:506},{name:'其他',value:15},{name:'车吧',value:2}],
    {unit:' 个',centerLabel:'网点总数',topN:6});
  const h=document.getElementById('t-donut').innerHTML;
  console.log('  donutList 渲染 HTML 长度:', h.length, '含 dl-wrap:', h.indexOf('dl-wrap')>=0);
});
T('donutList-空数据', function(){ donutList('t-donut3', []); });
T('drawDashOps', function(){
  if(typeof drawDashOps!=='function') throw new Error('未定义');
  drawDashOps();
});
T('drawDevCabList (换电柜明细分页)', function(){
  if(typeof drawDevCabList!=='function') throw new Error('未定义');
  drawDevCabList({});
  const pg=document.getElementById('w-cablist-pager').innerHTML;
  console.log('  pager 文本:', pg.replace(/<[^>]+>/g,''));
  console.log('  CABLIST_ALL.length:', (typeof CABLIST_ALL!=='undefined')?CABLIST_ALL.length:'n/a', '| CABLIST_SIZE:', CABLIST_SIZE);
  console.log('  cabinet_detail 原长:', ((DATA.device||{}).cabinet_detail||[]).length);
});
T('syncDeviceCabinet (静态模式弹窗)', function(){
  if(typeof syncDeviceCabinet!=='function') throw new Error('未定义');
  syncDeviceCabinet(); // 公网静态模式 -> openModal，不应抛错
  console.log('  syncDeviceCabinet 调用完成（静态分支）');
});
T('drawDevBatList (电池明细分页)', function(){
  if(typeof drawDevBatList!=='function') throw new Error('未定义');
  drawDevBatList({});
  const pg=document.getElementById('w-batlist-pager').innerHTML;
  console.log('  pager 文本:', pg.replace(/<[^>]+>/g,''));
  console.log('  BATLIST_ALL.length:', (typeof BATLIST_ALL!=='undefined')?BATLIST_ALL.length:'n/a', '| BATLIST_SIZE:', BATLIST_SIZE);
  console.log('  battery_detail 原长:', ((DATA.device||{}).battery_detail||[]).length);
});
T('syncDeviceBattery (静态模式弹窗)', function(){
  if(typeof syncDeviceBattery!=='function') throw new Error('未定义');
  syncDeviceBattery(); // 公网静态模式 -> openModal，不应抛错
  console.log('  syncDeviceBattery 调用完成（静态分支）');
});
T('drawSiteList (网点列表全量+四级筛选)', function(){
  if(typeof drawSiteList!=='function') throw new Error('未定义');
  drawSiteList({});
  var sd=((DATA.site||{}).detail||[]);
  console.log('  site.detail 原长:', sd.length);
  if(sd.length<10000) throw new Error('site.detail 未达全量: '+sd.length);
  var k=Object.keys(sd[0]||{});
  ['street','community','city','area','agency','agency_id','merchant','business','battery_product','open','create']
    .forEach(function(f){ if(k.indexOf(f)<0) throw new Error('缺字段 '+f); });
  console.log('  字段齐全: street/community/city/area/agency(_id)/merchant/business/battery_product/open/create');
  var pg=document.getElementById('sl-pagination');
  console.log('  分页文本:', pg? pg.innerHTML.replace(/<[^>]+>/g,'').slice(0,80):'n/a');
  var rc=document.getElementById('sl-result-count');
  console.log('  结果计数:', rc? rc.textContent:'n/a');
  console.log('  _slFiltered:', (window._slFiltered||[]).length, '| _slPageSize:', window._slPageSize);
  var t=document.getElementById('w-sitelist');
  console.log('  当前页渲染行数:', t&&t._filtered? t._filtered.length:'n/a');
});
T('slGeoCascade (城市→区域→街道→社区级联)', function(){
  if(typeof window.slGeoCascade!=='function') throw new Error('window.slGeoCascade 未导出');
  if(typeof window.slRenderPage!=='function') throw new Error('window.slRenderPage 未导出');
  window.slGeoCascade(0);
  ['sl-f-city','sl-f-area','sl-f-street','sl-f-community'].forEach(function(id){
    var el=document.getElementById(id); if(!el) throw new Error('缺下拉 '+id);
  });
  console.log('  四级下拉均存在');
});
T('syncSiteList (静态模式弹窗)', function(){
  if(typeof syncSiteList!=='function') throw new Error('未定义');
  syncSiteList();
  console.log('  syncSiteList 调用完成（静态分支）');
});
T('导出按钮 → 全量筛选结果（非当前页）', function(){
  var btn=document.getElementById('btn-export-sitelist');
  if(!btn||typeof btn.onclick!=='function') throw new Error('导出按钮未绑定');
  window._slLastExportCount=-1;
  btn.onclick();
  var seen=window._slLastExportCount;
  console.log('  导出行数(全量筛选结果):', seen);
  if(seen<10000) throw new Error('导出仍只含当前页: '+seen);
  var t=document.getElementById('w-sitelist');
  console.log('  导出后 _filtered 已还原为当前页:', t&&t._filtered? t._filtered.length:'n/a');
});

// ── Blob / URL 桩（供导出 CSV 模拟）──
global.Blob = function(parts,opts){ this.parts=parts; this.opts=opts; this.size=(parts||[]).join('').length; };
global.URL = { createObjectURL:function(){return 'blob:mock';}, revokeObjectURL:function(){} };

// ===== 协议明细全量专项 =====
T('AGP 引擎挂载 + 关键函数导出', function(){
  ['agpLoad','agpApply','agpRenderPage','agpExport','agpGeoCascade','agpFillFilters','agpUseSample','agpBind'].forEach(function(fn){
    if(typeof window[fn]!=='function') throw new Error('window.'+fn+' 未导出');
  });
  if(!window.AGP) throw new Error('AGP 对象未挂载');
  console.log('  AGP 挂载 OK，state='+window.AGP.state);
});

T('样本模式降级（DecompressionStream 缺失）', function(){
  global.DecompressionStream = undefined;
  agpUseSample();
  if(window.AGP.state!=='sample') throw new Error('应降级为 sample，实际 '+window.AGP.state);
  if(window.AGP.n<=0) throw new Error('样本条数为 0');
  console.log('  降级 sample OK，样本 '+window.AGP.n+' 条');
});

T('注入真实全量包 → full 模式', function(){
  var fs=require('fs');
  var gz=fs.readFileSync("{{ROOT}}/citybike_minimal/agreement.json.gz");
  var PACK=JSON.parse(zlib.gunzipSync(gz).toString('utf-8'));
  AGP.cols=PACK.c; AGP.dicts=PACK.e||{}; AGP.rows=PACK.r;
  AGP.n=PACK.n||PACK.r.length; AGP.ts=PACK.ts||''; AGP.err='';
  AGP.ci={}; for(var i=0;i<AGP.cols.length;i++) AGP.ci[AGP.cols[i]]=i;
  AGP.state='full';
  if(AGP.n!==121806) console.log('  ⚠ 全量条数='+AGP.n+'（用户口径 119667 为 2026-06-29 快照，实时 121806）');
  console.log('  注入全量 OK，n='+AGP.n+'，列数='+AGP.cols.length);
  var o0=AGP.rowAt(0);
  if(!o0 || !o0.agreement_id) throw new Error('rowAt(0) 解码失败');
  console.log('  rowAt(0): agreement_id='+o0.agreement_id+' city='+(o0.city||'—')+' user_id='+(o0.user_id||'—'));
});

T('agpFillFilters 填充下拉 + agpGeoCascade 级联', function(){
  agpFillFilters();
  window.agpGeoCascade(0);
  ['ag-f-city','ag-f-area','ag-f-street'].forEach(function(id){ if(!document.getElementById(id)) throw new Error('缺下拉 '+id); });
  console.log('  agpFillFilters + agpGeoCascade OK，三级地理下拉存在');
});

T('agpApply 全量筛选（无过滤=全部）', function(){
  agpApply(true);
  var f=window._agpFiltered||[];
  if(f.length!==AGP.n) throw new Error('筛选结果应='+AGP.n+'，实际 '+f.length);
  console.log('  全量筛选 OK，_agpFiltered='+f.length);
});

T('agpRenderPage 分页渲染', function(){
  window._agpPageSize=200; window._agpPage=1; agpRenderPage();
  var pg=document.getElementById('ag-pagination');
  console.log('  分页文本:', pg?pg.innerHTML.replace(/<[^>]+>/g,'').slice(0,120):'n/a');
  var rc=document.getElementById('ag-result-count');
  console.log('  结果计数:', rc?rc.textContent:'n/a');
  var cap=document.getElementById('u-agr-cap');
  console.log('  条数标注(cap):', cap?cap.textContent:'n/a');
  var t=document.getElementById('u-agreement-detail');
  console.log('  当前页渲染行数:', t&&t._filtered?t._filtered.length:'n/a', '(期望 200)');
});

T('13 维筛选逐个命中', function(){
  var o=AGP.rowAt(0);
  var dims=[
    ['ag-f-city','city'],['ag-f-area','area'],['ag-f-street','street'],
    ['ag-f-batprod','battery_product'],['ag-f-status','status'],['ag-f-type','type'],
    ['ag-f-agency','agency_name'],['ag-f-site','site_name'],['ag-f-business','business_name'],
    ['ag-f-user','user_id'],['ag-f-merchant','merchant_phone'],['ag-f-guide','guide_name'],
    ['ag-f-agid','agreement_id']
  ];
  var hit=0;
  dims.forEach(function(pair){
    var id=pair[0], col=pair[1], val=o[col];
    if(val==null||val==='') return;
    var el=document.getElementById(id); if(!el) throw new Error('缺筛选框 '+id);
    el.value=String(val); agpApply(true);
    var f=window._agpFiltered||[];
    if(f.length<1) throw new Error('维度 '+col+' 筛选后为空');
    console.log('  '+col+'='+String(val).slice(0,16)+' → 筛出 '+f.length+' 条');
    el.value=''; hit++;
  });
  if(!hit) throw new Error('无任一维度可命中');
  agpApply(true);
  console.log('  13 维筛选命中 '+hit+' 维，逻辑通过');
});

T('分页跳转（第 3 页 201-400）', function(){
  window._agpPageSize=200; window._agpPage=3; agpApply(false);
  var t=document.getElementById('u-agreement-detail');
  var rendered=t&&t._filtered?t._filtered.length:'n/a';
  console.log('  第3页渲染行数:', rendered);
  if(rendered!==200) throw new Error('第3页应渲染 200 行，实际 '+rendered);
});

T('syncUserAgreement 静态模式弹窗', function(){
  syncUserAgreement();
  console.log('  syncUserAgreement 调用完成（静态分支）');
});

T('一键导出（全量筛选结果，同步桩）', function(){
  var o=AGP.rowAt(0); var city=o.city;
  var el=document.getElementById('ag-f-city'); el.value=String(city); agpApply(true);
  var expect=(window._agpFiltered||[]).length;
  window._agpLastExportCount=-1;
  var prevST=global.setTimeout;
  global.setTimeout=function(cb){ try{ cb(); }catch(e){ console.log('  [导出分片异常] '+e.message); } return 0; };
  try { agpExport(); } finally { global.setTimeout=prevST; }
  var seen=window._agpLastExportCount;
  console.log('  导出城市='+String(city).slice(0,12)+'，期望='+expect+'，实际='+seen);
  if(seen!==expect) throw new Error('导出条数 '+seen+' ≠ 期望 '+expect);
  el.value=''; agpApply(true);
});

T('drawAgreementSignTable 接入全量包（销售看板·协议签约）', function(){
  if(typeof drawAgreementSignTable!=='function') throw new Error('未定义');
  if(AGP.state!=='full') throw new Error('AGP 非 full，无法验证：'+AGP.state);
  drawAgreementSignTable();
  var full=window._AG_FULL_ROWS;
  if(!full || full.length!==AGP.n) throw new Error('_AG_FULL_ROWS 应为 '+AGP.n+'，实际 '+(full?full.length:'null'));
  var t=document.getElementById('ag-table');
  console.log('  _AG_FULL_ROWS:', full.length, '| #ag-table 已渲染（_filtered='+(t&&t._filtered?t._filtered.length:'n/a')+'）');
  var title=document.getElementById('ag-sign-title');
  console.log('  标题:', title?title.textContent:'n/a');
  var note=document.getElementById('ag-sign-note');
  console.log('  说明含 agreement.json.gz:', note?(note.innerHTML.indexOf('agreement.json.gz')>=0):'n/a');
});

// ===== 押金明细全量专项（DEP 引擎）=====
T('DEP 引擎挂载 + 关键函数导出', function(){
  ['depLoad','depApply','depRenderPage','depExport','depGeoCascade','depFillFilters','depUseSample','depBind','depEnter'].forEach(function(fn){
    if(typeof window[fn]!=='function') throw new Error('window.'+fn+' 未导出');
  });
  if(!window.DEP) throw new Error('DEP 对象未挂载');
  console.log('  DEP 挂载 OK，state='+window.DEP.state);
});

T('注入真实全量包 → full 模式', function(){
  var fs=require('fs');
  var gz=fs.readFileSync("{{ROOT}}/citybike_minimal/deposit.json.gz");
  var PACK=JSON.parse(zlib.gunzipSync(gz).toString('utf-8'));
  DEP.cols=PACK.c; DEP.dicts=PACK.e||{}; DEP.rows=PACK.r;
  DEP.n=PACK.n||PACK.r.length; DEP.ts=PACK.ts||''; DEP.err='';
  DEP.ci={}; for(var i=0;i<DEP.cols.length;i++) DEP.ci[DEP.cols[i]]=i;
  DEP.state='full';
  if(DEP.n!==175002) console.log('  ⚠ 全量条数='+DEP.n+'（期望 175002）');
  console.log('  注入全量 OK，n='+DEP.n+'，列数='+DEP.cols.length);
  var o0=DEP.rowAt(0);
  if(!o0 || !o0.order_id) throw new Error('rowAt(0) 解码失败');
  console.log('  rowAt(0): order_id='+(o0.order_id||'—')+' city='+(o0.city||'—')+' user_id='+(o0.user_id||'—'));
});

T('depFillFilters 填充下拉 + depGeoCascade 级联', function(){
  depFillFilters();
  window.depGeoCascade(0);
  ['dp-f-city','dp-f-area','dp-f-street'].forEach(function(id){ if(!document.getElementById(id)) throw new Error('缺下拉 '+id); });
  console.log('  depFillFilters + depGeoCascade OK，三级地理下拉存在');
});

T('depApply 全量筛选（无过滤=全部）', function(){
  depApply(true);
  var f=window._depFiltered||[];
  if(f.length!==DEP.n) throw new Error('筛选结果应='+DEP.n+'，实际 '+f.length);
  console.log('  全量筛选 OK，_depFiltered='+f.length);
});

T('10 维筛选逐个命中', function(){
  var o=DEP.rowAt(0);
  var dims=[
    ['dp-f-city','city'],['dp-f-area','area'],['dp-f-street','street'],
    ['dp-f-batprod','battery_product'],['dp-f-agency','agency_name'],['dp-f-site','site_name'],
    ['dp-f-agid','agreement_id'],['dp-f-user','user_id'],['dp-f-ostatus','order_status'],['dp-f-payway','pay_way']
  ];
  var hit=0;
  dims.forEach(function(pair){
    var id=pair[0], col=pair[1], val=o[col];
    if(val==null||val==='') return;
    var el=document.getElementById(id); if(!el) throw new Error('缺筛选框 '+id);
    el.value=String(val); depApply(true);
    var f=window._depFiltered||[];
    if(f.length<1) throw new Error('维度 '+col+' 筛选后为空');
    console.log('  '+col+'='+String(val).slice(0,16)+' → 筛出 '+f.length+' 条');
    el.value=''; hit++;
  });
  if(!hit) throw new Error('无任一维度可命中');
  depApply(true);
  console.log('  10 维筛选命中 '+hit+' 维，逻辑通过');
});

T('depRenderPage 分页渲染', function(){
  window._depPageSize=200; window._depPage=1; depRenderPage();
  var pg=document.getElementById('dp-pagination');
  if(!pg || !pg.innerHTML) throw new Error('分页条未渲染');
  console.log('  分页文本:', pg.innerHTML.replace(/<[^>]+>/g,'').slice(0,80));
  var rc=document.getElementById('dp-result-count');
  console.log('  结果计数:', rc?rc.textContent:'n/a');
  var mode=document.getElementById('dp-mode-badge');
  console.log('  模式标记:', mode?mode.innerHTML.slice(0,60):'n/a');
});

T('押金分页跳转（第 3 页，每页 200）', function(){
  window._depPageSize=200; window._depPage=3; depApply(false);
  if(window._depPage!==3) throw new Error('应停留在第3页，实际 '+window._depPage);
  var rc=document.getElementById('dp-result-count');
  console.log('  第3页结果计数:', rc?rc.textContent:'n/a', '| _depPage='+window._depPage);
});

T('syncUserDeposit 静态模式弹窗', function(){
  syncUserDeposit();
  console.log('  syncUserDeposit 调用完成（静态分支）');
});

T('押金一键导出（全量筛选结果，同步桩）', function(){
  var o=DEP.rowAt(0); var city=o.city;
  var el=document.getElementById('dp-f-city'); el.value=String(city); depApply(true);
  var expect=(window._depFiltered||[]).length;
  window._depLastExportCount=-1;
  var prevST=global.setTimeout;
  global.setTimeout=function(cb){ try{ cb(); }catch(e){ console.log('  [导出分片异常] '+e.message); } return 0; };
  try { depExport(); } finally { global.setTimeout=prevST; }
  var seen=window._depLastExportCount;
  console.log('  导出城市='+String(city).slice(0,12)+'，期望='+expect+'，实际='+seen);
  if(seen!==expect) throw new Error('导出条数 '+seen+' ≠ 期望 '+expect);
  el.value=''; depApply(true);
});

function finish(){
  if (__uncaught.length){ errs.push.apply(errs, __uncaught); }
  if (errs.length){ console.log('\n==== RUNTIME ERRORS ('+errs.length+') ===='); errs.forEach(e=>console.log(' - '+e)); process.exitCode=1; }
  else { console.log('\nNO RUNTIME ERRORS — 运营总览 + 网点列表 + 协议明细 + 押金明细全量专项通过'); }
}
finish();
"""

footer = footer.replace("{{LITE_GZ}}", LITE_GZ)
footer = footer.replace("{{ROOT}}", ROOT)

out = ROOT + "/_smoke_ops.js"
io.open(out, "w", encoding="utf-8").write(harness + main + footer)
print("wrote _smoke_ops.js:", os.path.getsize(out))
