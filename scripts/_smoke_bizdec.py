# -*- coding: utf-8 -*-
"""针对「经营决策 (bizdec)」模块的轻量回归测试。
读取单文件自包含构建（citybike_selfcontained/index.html），提取主脚本，
用 mock DOM/echarts 跑一遍所有模块 + bizdec 三个子绘制函数，捕获运行时错误。
"""
import re, os
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(BASE, 'citybike_selfcontained', 'index.html')
html = open(SRC, encoding='utf-8').read()
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
// 经营决策模块依赖的全局状态
global.state = global.state || {};
global.state.bizdecSub = 'pkg';
global.BDSUB = 'pkg';
"""

footer = r"""
const mods = ['overview','user','sales','site','device','ops','personnel','finance','service','analytics','coupon','bizdec'];
let errs = [];
try { render(); } catch(e){ errs.push('render(): '+e.message+'\n'+(e.stack||'').split('\n').slice(0,5).join('\n')); }
for (const m of mods){
  try { applyFilters(m); } catch(e){ errs.push('applyFilters('+m+'): '+e.message); }
  try { if (typeof navigate==='function') navigate(m); } catch(e){ errs.push('navigate('+m+'): '+e.message); }
}
// 经营决策三子模块显式钻取
try { if(typeof drawBizDec==='function') drawBizDec(); } catch(e){ errs.push('drawBizDec: '+e.message); }
try { if(typeof drawBizDecPkg==='function') drawBizDecPkg(); } catch(e){ errs.push('drawBizDecPkg: '+e.message); }
try { if(typeof drawBizDecOps==='function') drawBizDecOps(); } catch(e){ errs.push('drawBizDecOps: '+e.message); }
try { if(typeof drawBizDecSite==='function') drawBizDecSite(); } catch(e){ errs.push('drawBizDecSite: '+e.message); }
console.log('MODULES TESTED:', mods.length);
if (errs.length){ console.log('\n==== RUNTIME ERRORS ('+errs.length+') ===='); errs.forEach(e=>console.log(' - '+e)); }
else { console.log('\nNO RUNTIME ERRORS — all modules + bizdec sub-draws rendered clean.'); }
"""

open('_smoke_bizdec.js','w',encoding='utf-8').write(harness + main + footer)
print("wrote _smoke_bizdec.js, main chars:", len(main))
