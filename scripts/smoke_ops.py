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
SRC = ROOT + "/citybike_selfcontained/index.html"

html = io.open(SRC, encoding="utf-8").read()

# 抓最后一个 </body> 之前的主脚本
scripts = re.findall(r"<script\b[^>]*>([\s\S]*?)</script>", html)
print("script blocks: %d, sizes: %s" % (len(scripts), [len(s) for s in scripts]))
# 主脚本 = 含 bootApp/render 定义的块（不用“最大块”，避免选中 ECharts）
main = next((s for s in scripts if 'function bootApp' in s or 'function render' in s), None)
if not main:
    main = max(scripts, key=len)
print("main chars:", len(main))

# 抽出 B64 数据（gzip+base64 内联）
m = re.search(r'var B64="([A-Za-z0-9+/=]+)";', html)
assert m, '未从构建产物找到 B64 数据块'
B64 = m.group(1)
print("B64 chars: %d (约 %.0f KB)" % (len(B64), len(B64)/1024))

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
// ── 解压 B64 -> 填 DATA（模拟浏览器引导）──
const zlib = require('zlib');
const __B64 = "{{B64}}";
let __bootData = null;
try {
  const buf = Buffer.from(__B64, 'base64');
  const txt = zlib.gunzipSync(buf).toString('utf-8');
  __bootData = JSON.parse(txt);
} catch(e){ console.log('解压 B64 失败: '+e.message); process.exitCode=1; }

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

if (__uncaught.length){ errs.push.apply(errs, __uncaught); }
if (errs.length){ console.log('\n==== RUNTIME ERRORS ('+errs.length+') ===='); errs.forEach(e=>console.log(' - '+e)); process.exitCode=1; }
else { console.log('\nNO RUNTIME ERRORS — 运营总览专项通过'); }
"""

footer = footer.replace("{{B64}}", B64)

out = ROOT + "/_smoke_ops.js"
io.open(out, "w", encoding="utf-8").write(harness + main + footer)
print("wrote _smoke_ops.js:", os.path.getsize(out))
