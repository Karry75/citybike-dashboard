# -*- coding: utf-8 -*-
"""CAB（换电柜明细）/ DEV（设备基础表）/ BAT（电池明细）引擎专项回归。

直接把 cabinet.json.gz / devicebase.json.gz / battery.json.gz 注入 GEngine 实例，验证：
  - install 解码（n / cols 数 / dict 解码）
  - rowAt(0) 解码出关键列
  - apply(true) 全量筛选 → _idxs 长度 == n
  - quick preset 命中逻辑
  - renderPage() 不抛错（buildTable + 分页 + 计数）
不依赖 indexedDB / fetch / Promise（走同步 install+apply 路径）。
"""
import re, io, os

ROOT = r"D:/workboddy file/dudu分析/citybike_backup"
SRC = ROOT + "/citybike_minimal/index.html"

html = io.open(SRC, encoding="utf-8").read()
scripts = re.findall(r"<script\b[^>]*>([\s\S]*?)</script>", html)
main = next((s for s in scripts if 'function bootApp' in s or 'function render' in s), None)
if not main:
    main = max(scripts, key=len)

CAB_GZ = ROOT + "/citybike_minimal/cabinet.json.gz"
DEV_GZ = ROOT + "/citybike_minimal/devicebase.json.gz"
BAT_GZ = ROOT + "/citybike_minimal/battery.json.gz"
assert os.path.exists(CAB_GZ), '未找到 ' + CAB_GZ
assert os.path.exists(DEV_GZ), '未找到 ' + DEV_GZ
assert os.path.exists(BAT_GZ), '未找到 ' + BAT_GZ

harness = r"""
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
global.setTimeout = function(){ return 0; };
global.setInterval = function(){ return 0; };
global.Blob = function(parts,opts){ this.parts=parts; this.opts=opts; this.size=(parts||[]).join('').length; };
global.URL = { createObjectURL:function(){return 'blob:mock';}, revokeObjectURL:function(){} };
const __uncaught = [];
process.on('uncaughtException', e=>{ __uncaught.push('uncaught: '+(e&&e.message||e)); });
"""

footer = r"""
const zlib = require('zlib');
const fs = require('fs');
function _loadPack(p){
  const buf = fs.readFileSync(p);
  const txt = zlib.gunzipSync(buf).toString('utf-8');
  return JSON.parse(txt);
}
const errs = [];
function T(name, fn){ try{ fn(); }catch(e){ errs.push(name+': '+e.message+'\n'+(e.stack||'')); } }

// ===== CAB（换电柜明细）=====
T('CAB 引擎挂载', function(){
  if(!window.CAB) throw new Error('window.CAB 未挂载');
  console.log('  CAB 挂载 OK');
});
T('CAB 注入 cabinet.json.gz', function(){
  const P=_loadPack("{{CAB_GZ}}");
  if(!window.CAB.install(P)) throw new Error('install 返回 false');
  if(window.CAB.n!==8607) console.log('  ⚠ CAB.n='+window.CAB.n+'（期望 8607）');
  if(window.CAB.cols.length!==58) throw new Error('CAB 列数='+window.CAB.cols.length+'（期望 58）');
  console.log('  CAB 注入 OK：n='+window.CAB.n+'，cols='+window.CAB.cols.length+'，dict 列='+Object.keys(window.CAB.dicts||{}).length);
});
T('CAB rowAt(0) 解码', function(){
  const o=window.CAB.rowAt(0);
  ['设备ID','换电柜ID','换电柜SN','在线状态','城市','总仓位数'].forEach(function(k){ if(!(k in o)) throw new Error('缺列 '+k); });
  console.log('  rowAt(0): 设备ID='+(o['设备ID']||'—')+' 换电柜SN='+(o['换电柜SN']||'—')+' 在线状态='+(o['在线状态']||'—')+' 总仓位数='+(o['总仓位数']||'—'));
});
T('CAB 全量筛选 apply(true)', function(){
  window.CAB._preset=null; window.CAB.apply(true);
  const idxs=window.CAB._idxs||[];
  if(idxs.length!==window.CAB.n) throw new Error('_idxs='+idxs.length+' ≠ n='+window.CAB.n);
  console.log('  CAB 全量筛选 OK：_idxs='+idxs.length);
});
T('CAB renderPage 渲染', function(){
  window.CAB._pageSize=200; window.CAB._page=1; window.CAB.renderPage();
  const t=document.getElementById('w-cablist');
  console.log('  CAB renderPage OK，#w-cablist._maxRender='+(t?t._maxRender:'n/a'));
});
T('CAB 在线状态=在线 命中', function(){
  window.CAB._preset=window.CAB._opt.quick.online; window.CAB.apply(true);
  const idxs=window.CAB._idxs||[];
  if(!idxs.length) throw new Error('在线命中为空');
  let allok=true; idxs.forEach(function(i){ if(window.CAB.rowAt(i)['在线状态']!=='在线') allok=false; });
  if(!allok) throw new Error('存在非在线行');
  console.log('  CAB 在线命中 '+idxs.length+' 行，全部 在线状态=在线');
});
T('CAB 故障仓>0 命中', function(){
  window.CAB._preset=window.CAB._opt.quick.fault; window.CAB.apply(true);
  const idxs=window.CAB._idxs||[];
  if(!idxs.length) throw new Error('故障柜命中为空');
  let allok=true; idxs.forEach(function(i){ if((+window.CAB.rowAt(i)['故障仓']||0)<=0) allok=false; });
  if(!allok) throw new Error('存在非故障柜');
  console.log('  CAB 故障柜命中 '+idxs.length+' 行，全部 故障仓>0');
});
T('CAB 复位', function(){
  window.CAB._preset=null; window.CAB.apply(true);
  if((window.CAB._idxs||[]).length!==window.CAB.n) throw new Error('复位后未恢复全量');
  console.log('  CAB 复位 OK');
});

// ===== DEV（设备基础表）=====
T('DEV 引擎挂载', function(){
  if(!window.DEV) throw new Error('window.DEV 未挂载');
  console.log('  DEV 挂载 OK');
});
T('DEV 注入 devicebase.json.gz', function(){
  const P=_loadPack("{{DEV_GZ}}");
  if(!window.DEV.install(P)) throw new Error('install 返回 false');
  if(window.DEV.n!==39983) console.log('  ⚠ DEV.n='+window.DEV.n+'（期望 39983）');
  if(window.DEV.cols.length!==39) throw new Error('DEV 列数='+window.DEV.cols.length+'（期望 39）');
  console.log('  DEV 注入 OK：n='+window.DEV.n+'，cols='+window.DEV.cols.length+'，dict 列='+Object.keys(window.DEV.dicts||{}).length);
});
T('DEV rowAt(0) 解码', function(){
  const o=window.DEV.rowAt(0);
  ['换电柜ID','设备ID','设备SN','在线状态','省','市','仓位编号','电池SN','锁仓状态'].forEach(function(k){ if(!(k in o)) throw new Error('缺列 '+k); });
  console.log('  rowAt(0): 换电柜ID='+(o['换电柜ID']||'—')+' 设备SN='+(o['设备SN']||'—')+' 省='+(o['省']||'—')+' 市='+(o['市']||'—')+' 仓位编号='+(o['仓位编号']||'—'));
});
T('DEV 全量筛选 apply(true)', function(){
  window.DEV._preset=null; window.DEV.apply(true);
  const idxs=window.DEV._idxs||[];
  if(idxs.length!==window.DEV.n) throw new Error('_idxs='+idxs.length+' ≠ n='+window.DEV.n);
  console.log('  DEV 全量筛选 OK：_idxs='+idxs.length);
});
T('DEV renderPage 渲染', function(){
  window.DEV._pageSize=200; window.DEV._page=1; window.DEV.renderPage();
  const t=document.getElementById('w-devbase');
  console.log('  DEV renderPage OK，#w-devbase._maxRender='+(t?t._maxRender:'n/a'));
});
T('DEV 在线状态=离线 命中', function(){
  window.DEV._preset=function(r){return r['在线状态']==='离线';}; window.DEV.apply(true);
  const idxs=window.DEV._idxs||[];
  if(!idxs.length) throw new Error('离线命中为空');
  let allok=true; idxs.forEach(function(i){ if(window.DEV.rowAt(i)['在线状态']!=='离线') allok=false; });
  if(!allok) throw new Error('存在非离线行');
  console.log('  DEV 离线命中 '+idxs.length+' 行，全部 在线状态=离线');
});
T('DEV 复位', function(){
  window.DEV._preset=null; window.DEV.apply(true);
  if((window.DEV._idxs||[]).length!==window.DEV.n) throw new Error('复位后未恢复全量');
  console.log('  DEV 复位 OK');
});

// ===== BAT（电池明细）=====
T('BAT 引擎挂载', function(){
  if(!window.BAT) throw new Error('window.BAT 未挂载');
  console.log('  BAT 挂载 OK');
});
T('BAT 注入 battery.json.gz', function(){
  const P=_loadPack("{{BAT_GZ}}");
  if(!window.BAT.install(P)) throw new Error('install 返回 false');
  if(window.BAT.n!==74817) console.log('  ⚠ BAT.n='+window.BAT.n+'（期望 74817）');
  if(window.BAT.cols.length!==46) throw new Error('BAT 列数='+window.BAT.cols.length+'（期望 46）');
  console.log('  BAT 注入 OK：n='+window.BAT.n+'，cols='+window.BAT.cols.length+'，dict 列='+Object.keys(window.BAT.dicts||{}).length);
});
T('BAT rowAt(0) 解码', function(){
  const o=window.BAT.rowAt(0);
  ['电池SN','设备ID','设备型号','设备状态','换电柜SN','网点名称','城市','30天借出'].forEach(function(k){ if(!(k in o)) throw new Error('缺列 '+k); });
  console.log('  rowAt(0): 电池SN='+(o['电池SN']||'—')+' 设备状态='+(o['设备状态']||'—')+' 换电柜SN='+(o['换电柜SN']||'—')+' 城市='+(o['城市']||'—'));
});
T('BAT 全量筛选 apply(true)', function(){
  window.BAT._preset=null; window.BAT.apply(true);
  const idxs=window.BAT._idxs||[];
  if(idxs.length!==window.BAT.n) throw new Error('_idxs='+idxs.length+' ≠ n='+window.BAT.n);
  console.log('  BAT 全量筛选 OK：_idxs='+idxs.length);
});
T('BAT renderPage 渲染', function(){
  window.BAT._pageSize=200; window.BAT._page=1; window.BAT.renderPage();
  const t=document.getElementById('w-batlist');
  console.log('  BAT renderPage OK，#w-batlist._maxRender='+(t?t._maxRender:'n/a'));
});
T('BAT 在线状态=在线 命中', function(){
  window.BAT._preset=window.BAT._opt.quick.online; window.BAT.apply(true);
  const idxs=window.BAT._idxs||[];
  if(!idxs.length) throw new Error('在线命中为空');
  let allok=true; idxs.forEach(function(i){ if(window.BAT.rowAt(i)['在线状态']!=='在线') allok=false; });
  if(!allok) throw new Error('存在非在线行');
  console.log('  BAT 在线命中 '+idxs.length+' 行，全部 在线状态=在线');
});
T('BAT 使用中 命中', function(){
  window.BAT._preset=window.BAT._opt.quick.using; window.BAT.apply(true);
  const idxs=window.BAT._idxs||[];
  if(!idxs.length) throw new Error('使用中命中为空');
  let allok=true; idxs.forEach(function(i){ if(window.BAT.rowAt(i)['设备状态']!=='使用中') allok=false; });
  if(!allok) throw new Error('存在非使用中行');
  console.log('  BAT 使用中命中 '+idxs.length+' 行，全部 设备状态=使用中');
});
T('BAT 复位', function(){
  window.BAT._preset=null; window.BAT.apply(true);
  if((window.BAT._idxs||[]).length!==window.BAT.n) throw new Error('复位后未恢复全量');
  console.log('  BAT 复位 OK');
});

function finish(){
  if (__uncaught.length){ errs.push.apply(errs, __uncaught); }
  if (errs.length){ console.log('\n==== CAB/DEV/BAT RUNTIME ERRORS ('+errs.length+') ===='); errs.forEach(e=>console.log(' - '+e)); process.exitCode=1; }
  else { console.log('\nNO RUNTIME ERRORS — CAB（换电柜明细）+ DEV（设备基础表）+ BAT（电池明细）引擎通过'); }
}
finish();
"""

footer = footer.replace("{{CAB_GZ}}", CAB_GZ)
footer = footer.replace("{{DEV_GZ}}", DEV_GZ)
footer = footer.replace("{{BAT_GZ}}", BAT_GZ)

out = ROOT + "/_smoke_cabdev.js"
io.open(out, "w", encoding="utf-8").write(harness + main + footer)
print("wrote _smoke_cabdev.js:", os.path.getsize(out))
