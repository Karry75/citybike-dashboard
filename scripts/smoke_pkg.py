# -*- coding: utf-8 -*-
"""PKG（套餐购买订单明细）引擎专项回归 —— 多段包 v2（字典外置）版。

CloudStudio 有两道限制：单文件约 50MB，且部署目录总量约 95,000,000 字节。
故 package_order 拆成「1 份外置字典 + 4 段纯行体」：
  package_order.dict.json.gz   c / e / n / parts / counts（全局，唯一一份）
  package_order.0..3.json.gz   {"v":2,"part":i,"n":N,"r":[...]}
v1 时代每段各存一份字典（gz 2.4MB），4 段白占 5.6MB，目录顶到 93.84MB 被拒。

本 smoke 覆盖两层：

- Python 侧：
  整包读 dict（明文仅 11MB），逐段流式读到 '"r":[' 解析头部，断言
  4 段 n 之和 = 2225590 = dict.n、dict.counts 与各段 n 一一对应、
  列 32 / 字典列 29、且**段内不再残留 c/e**（残留 = 白白多占体积）。
  再校验 index.html 里的 PKG_COLS 与包列同序一致、parts:4 已生效。
  然后用「括号走查」从每段切出前 7500 行，生成 1 个 dict 包 + 4 个截断行体小包喂 node。

- node 侧（真实代码路径）：
  mock fetch 返回真 Response（node22 自带 DecompressionStream/TransformStream），
  直接驱动产物里的 E.load()，验证 dict + 4 段共 5 个文件确实被拉取、
  _merge 用外置字典正确解码、拼接顺序正确、段边界行无误，
  再跑 apply / renderPage / 预设筛选 / 导出。

用法：python scripts/smoke_pkg.py
"""
import re, io, os, gzip, json, subprocess, sys

ROOT = r"D:/workboddy file/dudu分析/citybike_backup"
SRC = ROOT + "/citybike_minimal/index.html"
PARTS = 4
TRUNC_PER = 7500
EXPECT_TOTAL = 2225590
EXPECT_COLS = 32
EXPECT_DICT_COLS = 29
NODE = r'C:\Users\Karry\.workbuddy\binaries\node\versions\22.22.2\node.exe'


def read_part_head_and_rows(path, trunc_n):
    """流式读一段：返回 (header_dict, 前 trunc_n 行的原始文本片段, 实际切出行数)。"""
    f = gzip.open(path, 'rt', encoding='utf-8')
    try:
        buf = ''
        while '"r":[' not in buf:
            chunk = f.read(1 << 20)
            if not chunk:
                raise RuntimeError('%s 未找到 "r":[' % path)
            buf += chunk
        cut = buf.index('"r":[')
        hdr = json.loads(buf[:cut].rstrip().rstrip(',') + '}')

        start = cut + len('"r":[')
        pos = start
        depth = 0
        in_str = False
        esc = False
        rows = 0
        end = None
        while end is None:
            while pos < len(buf):
                c = buf[pos]
                if in_str:
                    if esc:
                        esc = False
                    elif c == '\\':
                        esc = True
                    elif c == '"':
                        in_str = False
                elif c == '"':
                    in_str = True
                elif c == '[' or c == '{':
                    depth += 1
                elif c == ']' or c == '}':
                    depth -= 1
                    if depth == 0:
                        rows += 1
                        if rows == trunc_n:
                            end = pos + 1
                            pos += 1
                            break
                pos += 1
            if end is not None:
                break
            chunk = f.read(1 << 20)
            if not chunk:
                end = len(buf.rstrip().rstrip(']}').rstrip().rstrip(','))
                break
            buf += chunk
        return hdr, buf[start:end], rows
    finally:
        f.close()


print("── Python 侧：外置字典 + %d 段行体断言 ──" % PARTS)
DICT_PATH = ROOT + "/citybike_minimal/package_order.dict.json.gz"
assert os.path.exists(DICT_PATH), '缺外置字典包 %s' % DICT_PATH
D = json.loads(gzip.open(DICT_PATH, 'rb').read().decode('utf-8'))
c0, e0 = D['c'], D['e']
dict_gz = os.path.getsize(DICT_PATH)
assert len(c0) == EXPECT_COLS, '列数=%d 期望 %d' % (len(c0), EXPECT_COLS)
assert len(e0) == EXPECT_DICT_COLS, '字典列=%d 期望 %d' % (len(e0), EXPECT_DICT_COLS)
assert D['n'] == EXPECT_TOTAL, 'dict.n=%d 期望 %d' % (D['n'], EXPECT_TOTAL)
assert D['parts'] == PARTS, 'dict.parts=%d 期望 %d' % (D['parts'], PARTS)
assert sum(D['counts']) == EXPECT_TOTAL, 'dict.counts 求和=%d 期望 %d' % (sum(D['counts']), EXPECT_TOTAL)
print("  字典包: n=%d parts=%d 列=%d 字典列=%d gz=%.2fMB" % (
    D['n'], D['parts'], len(c0), len(e0), dict_gz / 1048576))

heads, subs, first_ids = [], [], []
total = 0
seg_gz = 0
for p in range(PARTS):
    path = "%s/citybike_minimal/package_order.%d.json.gz" % (ROOT, p)
    assert os.path.exists(path), '缺段文件 %s' % path
    hdr, r_sub, got = read_part_head_and_rows(path, TRUNC_PER)
    assert got == TRUNC_PER, '段%d 只切出 %d 行' % (p, got)
    # v2 铁律：段内不得再带 c/e。带了 = 每段重复 2.4MB 字典，目录必然超限被拒 400
    assert 'c' not in hdr and 'e' not in hdr, \
        '段%d 仍内嵌 c/e（v1 布局），会让部署目录多占 %d 份字典' % (p, PARTS - 1)
    assert hdr.get('part') == p, '段%d 头部 part=%r 不符' % (p, hdr.get('part'))
    assert hdr['n'] == D['counts'][p], \
        '段%d n=%d 与 dict.counts[%d]=%d 不符' % (p, hdr['n'], p, D['counts'][p])
    heads.append(hdr)
    subs.append(r_sub)
    total += hdr['n']
    seg_gz += os.path.getsize(path)
    print("  段%d: part=%d n=%-7d gz=%.2fMB（纯行体，无 c/e）" % (
        p, hdr['part'], hdr['n'], os.path.getsize(path) / 1048576))

assert total == EXPECT_TOTAL, '4 段合计 n=%d 期望 %d' % (total, EXPECT_TOTAL)
print("  ✅ 合计 n=%d（=%d）/ 列=%d / 字典列=%d" % (total, EXPECT_TOTAL, len(c0), len(e0)))
print("  ✅ 字典仅 1 份外置，4 段 counts 与 dict 逐一对齐")
print("  ✅ 包总量 %.2fMB（字典 %.2f + 行体 %.2f）" % (
    (dict_gz + seg_gz) / 1048576, dict_gz / 1048576, seg_gz / 1048576))

# 每段首行的订单ID（解码后），用于 node 侧校验合并顺序
oid_i = c0.index('purchase_order_id')
for p in range(PARTS):
    row = json.loads(subs[p][:subs[p].index(']') + 1])
    v = row[oid_i]
    first_ids.append(e0[c0[oid_i]][v] if c0[oid_i] in e0 else v)

html = io.open(SRC, encoding='utf-8').read()
m = re.search(r'var PKG_COLS=\[(.*?)\];', html, re.S)
assert m, 'index.html 未找到 var PKG_COLS'
keys = re.findall(r"\{k:'([^']+)'", m.group(1))
assert keys == c0, 'PKG_COLS 与 pack 列不一致\n PKG_COLS=%s\n pack=%s' % (keys, c0)
assert html.count('var PKG_COLS=') == 1, 'PKG_COLS 重复声明（会 SyntaxError 整站白屏）'
assert "url:'package_order'" in html and 'parts:4' in html, 'PKG_OPT 未切到多段模式'
print("  ✅ PKG_COLS 32 列同序对齐 / 唯一声明 / PKG_OPT parts=4 已生效")

# ── 生成 1 个 dict 包 + 4 个截断行体小包 ─────────────────────────────────
trunc_files = {}
_dobj = {"v": D.get('v'), "ts": D.get('ts'), "n": PARTS * TRUNC_PER, "parts": PARTS,
         "counts": [TRUNC_PER] * PARTS, "c": c0, "e": e0}
_dpath = "%s/_pkg_trunc.dict.json.gz" % ROOT
with open(_dpath, 'wb') as f:
    f.write(gzip.compress(json.dumps(_dobj, ensure_ascii=False).encode('utf-8'), compresslevel=6))
trunc_files['package_order.dict.json.gz'] = _dpath
for p in range(PARTS):
    obj = {"v": heads[p].get('v'), "part": p, "n": TRUNC_PER,
           "r": json.loads('[' + subs[p] + ']')}
    path = "%s/_pkg_trunc.%d.json.gz" % (ROOT, p)
    with open(path, 'wb') as f:
        f.write(gzip.compress(json.dumps(obj, ensure_ascii=False).encode('utf-8'), compresslevel=6))
    trunc_files['package_order.%d.json.gz' % p] = path
print("  ✅ 截断包生成：1 dict + %d 行体段（每段 %d 行，合计 %d 行）" % (
    PARTS, TRUNC_PER, PARTS * TRUNC_PER))

# ── 抽取主脚本 ───────────────────────────────────────────────────────────
scripts = re.findall(r"<script\b[^>]*>([\s\S]*?)</script>", html)
main = next((s for s in scripts if 'function bootApp' in s or 'function render' in s), None)
if not main:
    main = max(scripts, key=len)

harness = r"""
global.__realSetTimeout = setTimeout;
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
    offsetWidth:300, offsetHeight:200, scrollTop:0, value:'', checked:false, disabled:false,
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
global.alert = function(){};
global.requestAnimationFrame = function(f){ return 0; };
global.setTimeout = function(){ return 0; };   // 默认 no-op；导出测试前临时改为同步
global.setInterval = function(){ return 0; };
global.Blob = function(parts,opts){ this.parts=parts; this.opts=opts; this.size=(parts||[]).join('').length; };
global.URL = { createObjectURL:function(){return 'blob:mock';}, revokeObjectURL:function(){} };
const __uncaught = [];
process.on('uncaughtException', e=>{ console.error('UNCAUGHT_EXCEPTION: '+(e&&e.stack||e)); __uncaught.push('uncaught: '+(e&&e.message||e)); });
"""

footer = r"""
const fs = require('fs');
const errs = [];
function T(name, fn){ try{ fn(); }catch(e){ errs.push(name+': '+e.message+'\n'+(e.stack||'')); } }

const PART_FILES = __PART_FILES__;
const FIRST_IDS  = __FIRST_IDS__;
const TRUNC_PER  = __TRUNC_PER__;
const PARTS      = __PARTS__;
const __fetched  = [];

global.fetch = function(u){
  const p = PART_FILES[u];
  if(!p) return Promise.reject(new Error('意外的 fetch url: '+u));
  __fetched.push(u);
  const buf = fs.readFileSync(p);
  return Promise.resolve(new Response(buf, {headers:{'content-length':String(buf.length)}}));
};

T('1 PKG 引擎挂载', function(){
  if(!window.PKG) throw new Error('window.PKG 未挂载');
  if(window.PKG.url!=='package_order') throw new Error('E.url='+window.PKG.url+'（期望 package_order）');
  console.log('  PKG 挂载 OK，url='+window.PKG.url);
});

// 隔离 IndexedDB：本用例只验证多段拉取 + 合并
window.PKG.cacheSave = function(){ return Promise.resolve(); };

function waitLoad(cb){
  let tries=0;
  (function poll(){
    if(window.PKG.state!=='loading' || tries>1200){ cb(); return; }
    tries++; global.__realSetTimeout(poll, 20);
  })();
}

let __loadThrew=null;
try { window.PKG.load(); } catch(e){ __loadThrew=e; }

waitLoad(function(){
  T('2 ★ 外置字典 + 多段 load() 真实路径（真 DecompressionStream）', function(){
    if(__loadThrew) throw new Error('load() 同步抛错: '+(__loadThrew.message||__loadThrew));
    if(window.PKG.state!=='full') throw new Error('state='+window.PKG.state+'（期望 full），err='+(window.PKG.err||'—'));
    if(__fetched.length!==PARTS+1) throw new Error('实际 fetch '+__fetched.length+' 次（期望 '+(PARTS+1)+' = 1 dict + '+PARTS+' 段）');
    if(__fetched[0]!=='package_order.dict.json.gz') throw new Error('首个请求应为字典包，实际 '+__fetched[0]+'（_merge 靠位置 0 区分 v2 头）');
    for(let p=0;p<PARTS;p++){
      if(__fetched.indexOf('package_order.'+p+'.json.gz')<0) throw new Error('段'+p+' 未被拉取');
    }
    console.log('  1 字典 + '+PARTS+' 段全部拉取解压合并 OK：'+__fetched.join(', '));
  });
  T('3 ★ 合并后行数/列/字典（字典来自外置包）', function(){
    const want=PARTS*TRUNC_PER;
    if(window.PKG.n!==want) throw new Error('PKG.n='+window.PKG.n+'（期望 '+want+'）');
    if(window.PKG.rows.length!==want) throw new Error('rows.length='+window.PKG.rows.length);
    if(window.PKG.cols.length!==32) throw new Error('列数='+window.PKG.cols.length);
    // 段内已无 e，这 29 个字典只可能来自外置 dict 包 —— 拿到 = 外置链路打通
    if(Object.keys(window.PKG.dicts||{}).length!==29) throw new Error('dict 列='+Object.keys(window.PKG.dicts||{}).length+'（期望 29，段内无 e，只能来自外置字典包）');
    console.log('  合并 OK：n='+window.PKG.n+'，cols=32，dict 列=29（全部由外置包提供）');
  });
  T('4 ★ 段边界行解码 & 拼接顺序', function(){
    for(let p=0;p<PARTS;p++){
      const i=p*TRUNC_PER;
      const got=String(window.PKG.rowAt(i)['purchase_order_id']||'');
      const want=String(FIRST_IDS[p]);
      if(got!==want) throw new Error('rowAt('+i+') 订单ID='+got+'，期望段'+p+'首行 '+want+'（拼接顺序或字典错位）');
    }
    console.log('  段边界 rowAt('+[0,TRUNC_PER,2*TRUNC_PER,3*TRUNC_PER].join('/')+') 订单ID 与各段首行一致');
  });
  T('5 rowAt(0) 字段完整', function(){
    const o=window.PKG.rowAt(0);
    ['purchase_order_id','order_type','user_phone','battery_product','sign_site_name','order_status','order_payable_amount','is_paid','create_time'].forEach(function(k){ if(!(k in o)) throw new Error('缺列 '+k); });
    console.log('  rowAt(0): 订单ID='+(o['purchase_order_id']||'—')+' 类型='+(o['order_type']||'—')+' 手机='+(o['user_phone']||'—')+' 电池='+(o['battery_product']||'—')+' 网点='+(o['sign_site_name']||'—')+' 实付='+(o['order_payable_amount']||'—')+' 已支付='+(o['is_paid']||'—'));
  });
  T('6 全量筛选 apply(true)', function(){
    window.PKG._preset=null; window.PKG.apply(true);
    const idxs=window.PKG._idxs||[];
    if(idxs.length!==window.PKG.n) throw new Error('_idxs='+idxs.length+' ≠ n='+window.PKG.n);
    console.log('  全量筛选 OK：_idxs='+idxs.length);
  });
  T('7 renderPage 渲染', function(){
    window.PKG._pageSize=200; window.PKG._page=1; window.PKG.renderPage();
    const t=document.getElementById('s-pkglist');
    console.log('  renderPage OK，#s-pkglist._maxRender='+(t?t._maxRender:'n/a'));
  });
  T('8 末页渲染（跨段取行）', function(){
    const pages=Math.ceil(window.PKG._idxs.length/window.PKG._pageSize);
    window.PKG._page=pages; window.PKG.renderPage();
    const last=window.PKG.rowAt(window.PKG._idxs[window.PKG._idxs.length-1]);
    if(!last['purchase_order_id']) throw new Error('末行订单ID 为空');
    console.log('  末页(第'+pages+'页) OK，末行订单ID='+last['purchase_order_id']);
  });
  T('9 预设 order_type=电量卡 命中', function(){
    window.PKG._page=1;
    window.PKG._preset=function(r){return r['order_type']==='电量卡';}; window.PKG.apply(true);
    const idxs=window.PKG._idxs||[];
    if(!idxs.length) throw new Error('电量卡命中为空');
    let allok=true; idxs.forEach(function(i){ if(window.PKG.rowAt(i)['order_type']!=='电量卡') allok=false; });
    if(!allok) throw new Error('存在非电量卡行');
    console.log('  电量卡命中 '+idxs.length+' 行，全部 order_type=电量卡');
  });
  T('10 预设 is_paid=是 命中', function(){
    window.PKG._preset=function(r){return r['is_paid']==='是';}; window.PKG.apply(true);
    const idxs=window.PKG._idxs||[];
    if(!idxs.length) throw new Error('已支付命中为空');
    let allok=true; idxs.forEach(function(i){ if(window.PKG.rowAt(i)['is_paid']!=='是') allok=false; });
    if(!allok) throw new Error('存在未支付行');
    console.log('  已支付命中 '+idxs.length+' 行，全部 is_paid=是');
  });
  T('11 复位', function(){
    window.PKG._preset=null; window.PKG.apply(true);
    if((window.PKG._idxs||[]).length!==window.PKG.n) throw new Error('复位后未恢复全量');
    console.log('  复位 OK');
  });
  T('12 ★ 字典编码后数值列格式化（字符串化回归）', function(){
    // 字典编码把 0 / 39.0 存成 "0" / "39.0"，判空若只写 v===0 会让「无优惠券」显示成 0
    const by={}; PKG_COLS.forEach(function(c){ by[c.k]=c; });
    [['coupon_id','0'],['coupon_id',0],['coupon_id',''],['sign_agency_id','0'],['coupon_center_id','0'],['sign_site_id','0']].forEach(function(t){
      const out=by[t[0]].f(t[1]);
      if(out!=='—') throw new Error(t[0]+'.f('+JSON.stringify(t[1])+') = '+out+'，期望 —');
    });
    [['order_total_amount','39.0','¥39'],['order_payable_amount','35.0','¥35'],['refund_amount','0.0','¥0'],['coupon_amount','0','¥0']].forEach(function(t){
      const out=by[t[0]].f(t[1]);
      if(out!==t[2]) throw new Error(t[0]+'.f("'+t[1]+'") = '+out+'，期望 '+t[2]);
    });
    if(by['sign_site_id'].f('24011866')!=='24011866') throw new Error('正常网点ID 被误判为空');
    console.log('  数值列判空/金额格式化 OK（"0"→— ，"39.0"→¥39）');
  });
  T('13 导出(同步 setTimeout)无异常', function(){
    global.setTimeout = function(f){ try{f();}catch(e){throw e;} return 0; };
    let thrown=null;
    try { window.PKG.export(); } catch(e){ thrown=e; }
    global.setTimeout = function(){ return 0; };
    if(thrown) throw new Error('export 抛错: '+(thrown.message||thrown));
    console.log('  export() 执行无异常');
  });

  if (__uncaught.length){ errs.push.apply(errs, __uncaught); }
  if (errs.length){ console.log('\n==== PKG RUNTIME ERRORS ('+errs.length+') ===='); errs.forEach(e=>console.log(' - '+e)); process.exitCode=1; }
  else { console.log('\nNO RUNTIME ERRORS — PKG（套餐购买订单明细）多段 v2 引擎通过（13 项，含外置字典链路）'); }
});
"""

footer = (footer
          .replace('__PART_FILES__', json.dumps(trunc_files, ensure_ascii=False))
          .replace('__FIRST_IDS__', json.dumps(first_ids, ensure_ascii=False))
          .replace('__TRUNC_PER__', str(TRUNC_PER))
          .replace('__PARTS__', str(PARTS)))

out = ROOT + "/_smoke_pkg.js"
io.open(out, "w", encoding="utf-8").write(harness + main + footer)
print("── node 侧：驱动产物里的 E.load() 走多段路径 ──")
print("  wrote _smoke_pkg.js: %d 字节" % os.path.getsize(out))

if os.environ.get("SKIP_NODE"):
    print("SKIP_NODE set: 仅生成文件，未运行 node")
    sys.exit(0)

p = subprocess.run([NODE, out], capture_output=True, text=True, encoding='utf-8')
print(p.stdout)
if p.stderr.strip():
    print('--- node stderr ---')
    print(p.stderr)
rc = p.returncode
try:
    os.remove(out)
    for f in trunc_files.values():
        if os.path.exists(f):
            os.remove(f)
except OSError:
    pass
sys.exit(rc)
