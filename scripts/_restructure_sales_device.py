# -*- coding: utf-8 -*-
"""
_restructure_sales_device.py
对 citybike_backup/html/template.html 做两件事：
  A) 销售看板新增「协议签约」「套餐购买明细」两个子菜单面板
  B) 设备资产看板子菜单重组为 3 个一级分组（嵌套 tab）

流程：
  1) 先 neutralize <script> / <style> 块（替换为占位符，避免 HTML 操作误伤/偏移）
  2) 做 HTML 操作（销售按钮/面板、设备分组重组）
  3) 在已 neutral 的文本上做 JS 文本替换（因为脚本块此时是占位符，不影响）
  4) 恢复 script/style 块
  5) 校验：div 平衡、新面板 ID 存在、旧面板 ID 已嵌套/移除、py_compile

注意：销售子菜单沿用现有 convention（data-ssub / s-sub-*），而非任务里示例的
data-wsub / w-sub-*，否则 switchSalesSub 无法定位面板。设备系统保留 DEVSUB=leaf，
新增一级 group 层（最低风险方案）。
"""
import re
import sys
import py_compile
import os

PATH = r"D:/workboddy file/dudu分析/citybike_backup/html/template.html"
BAK = PATH + ".bak_restructure"

text = open(PATH, encoding="utf-8").read()
open(BAK, "w", encoding="utf-8").write(text)  # 备份

# ---------------------------------------------------------------------------
# 0) neutralize <script> / <style>
# ---------------------------------------------------------------------------
blocks = []  # (placeholder, original)
def _neutralize(m):
    idx = len(blocks)
    ph = "__SB%d__" % idx
    blocks.append((ph, m.group(0)))
    return ph

working = re.sub(r"<script[^>]*>.*?</script>", _neutralize, text, flags=re.S)
working = re.sub(r"<style[^>]*>.*?</style>", _neutralize, working, flags=re.S)

# ===========================================================================
# 1) HTML 操作
# ===========================================================================

# ---- A) 销售看板：新增两个子菜单按钮（插入到 siterperf 按钮之前） ----
SALES_BTN_ANCHOR = '<button type="button" class="stab" data-ssub="siterperf">🏪 网点销售业绩</button>'
assert SALES_BTN_ANCHOR in working, "销售 siterperf 按钮锚点未找到"
NEW_SALES_BTNS = (
    '<button type="button" class="stab" data-ssub="agreement_sign">📋 协议签约</button>\n'
    '        <button type="button" class="stab" data-ssub="package_purchase">🛒 套餐购买明细</button>\n'
    '        ' + SALES_BTN_ANCHOR
)
working = working.replace(SALES_BTN_ANCHOR, NEW_SALES_BTNS, 1)

# ---- A) 销售看板：新增两个面板（插入到 s-sub-siterperf 面板之前） ----
SALES_PANEL_ANCHOR = '<div class="ssub-panel" id="s-sub-siterperf">'
assert SALES_PANEL_ANCHOR in working, "销售 siterperf 面板锚点未找到"

AGREEMENT_PANEL = '''<div class="ssub-panel" id="s-sub-agreement_sign">
      <div class="panel">
        <h3>协议签约明细（全量 · DATA.user.agreement_detail）</h3>
        <div class="filterbar" style="flex-wrap:wrap">
          <div class="fb-row">
            <div class="fitem"><label>协议ID</label><input id="agq-id" class="pop-in" placeholder="协议ID"></div>
            <div class="fitem"><label>用户搜索</label><input id="agq-user" class="pop-in" placeholder="用户ID/手机号"></div>
            <div class="fitem"><label>协议状态</label><select id="agq-status"><option value="">全部</option><option>待激活</option><option>生效中</option><option>已停用</option><option>欠租</option></select></div>
            <div class="fitem"><label>型号风格</label><input id="agq-model" class="pop-in" placeholder="型号风格"></div>
            <div class="fitem"><label>电池产品</label><input id="agq-battery" class="pop-in" placeholder="电池产品"></div>
            <div class="fitem"><label>协议类型</label><input id="agq-type" class="pop-in" placeholder="协议类型"></div>
          </div>
          <div class="fb-row">
            <div class="fitem"><label>套餐方案</label><input id="agq-pkg" class="pop-in" placeholder="套餐/方案"></div>
            <div class="fitem"><label>网点信息</label><input id="agq-site" class="pop-in" placeholder="网点名称/ID"></div>
            <div class="fitem"><label>是否推广协议</label><select id="agq-promo"><option value="">全部</option><option value="是">是</option><option value="否">否</option></select></div>
            <div class="fitem"><label>创建时间起</label><input id="agq-cfrom" type="date"></div>
            <div class="fitem"><label>创建时间止</label><input id="agq-cto" type="date"></div>
          </div>
          <div class="fb-row">
            <div class="fitem"><label>购买时间起</label><input id="agq-bfrom" type="date"></div>
            <div class="fitem"><label>购买时间止</label><input id="agq-bto" type="date"></div>
            <div class="fitem"><label>结束时间起</label><input id="agq-efrom" type="date"></div>
            <div class="fitem"><label>结束时间止</label><input id="agq-eto" type="date"></div>
            <button type="button" class="btn" id="agq-go">🔍 查询</button>
            <button type="button" class="btn btn-ghost" id="agq-reset">⟲ 重置</button>
          </div>
        </div>
        <div class="kpis" id="ag-kpis"></div>
        <div class="tbl-wrap"><table id="ag-table"><thead></thead><tbody></tbody></table></div>
        <div class="pager" id="ag-foot"></div>
        <div class="note">✅ 协议签约明细已接入：来自 <code>DATA.user.agreement_detail</code>（全量 ~12 万行，含协议/用户/渠道/电池/车辆/租金/城市/网点/代理商/业务员/状态/时间等 30+ 字段）。前端实时筛选 + 分页（每页 50），不请求后端。</div>
      </div>
      <div class="modal-mask" id="row-detail-modal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:9999;align-items:center;justify-content:center" onclick="if(event.target===this)this.style.display='none'">
        <div style="background:#fff;border-radius:8px;max-width:720px;width:92%;max-height:82vh;overflow:auto;box-shadow:0 10px 40px rgba(0,0,0,.3)">
          <div style="display:flex;justify-content:space-between;align-items:center;padding:12px 16px;border-bottom:1px solid #eee"><b id="rd-title">详情</b><button class="fbtn sm" onclick="document.getElementById('row-detail-modal').style.display='none'">✕</button></div>
          <div id="rd-body" style="padding:16px"></div>
        </div>
      </div>
    </div>
'''

PACKAGE_PANEL = '''<div class="ssub-panel" id="s-sub-package_purchase">
      <div class="panel">
        <h3>套餐购买明细（全量 · DATA.user.deposit_package_detail + DATA.sales.package_purchase_stats）</h3>
        <div class="filterbar" style="flex-wrap:wrap">
          <div class="fb-row">
            <div class="fitem"><label>订单编号</label><input id="pkq-order" class="pop-in" placeholder="订单编号"></div>
            <div class="fitem"><label>货品人</label><input id="pkq-buyer" class="pop-in" placeholder="货品人/购买人"></div>
            <div class="fitem"><label>用户搜索</label><input id="pkq-user" class="pop-in" placeholder="用户ID/手机号"></div>
            <div class="fitem"><label>协议编号</label><input id="pkq-agr" class="pop-in" placeholder="协议编号"></div>
            <div class="fitem"><label>城市区域</label><input id="pkq-city" class="pop-in" placeholder="城市区域"></div>
            <div class="fitem"><label>商户门店</label><input id="pkq-merchant" class="pop-in" placeholder="商户/门店"></div>
          </div>
          <div class="fb-row">
            <div class="fitem"><label>商品类型</label><input id="pkq-ptype" class="pop-in" placeholder="商品类型"></div>
            <div class="fitem"><label>商铺编号</label><input id="pkq-shop" class="pop-in" placeholder="商铺编号"></div>
            <div class="fitem"><label>支付方式</label><input id="pkq-pay" class="pop-in" placeholder="支付方式"></div>
            <div class="fitem"><label>订单状态</label><select id="pkq-status"><option value="">全部</option><option>待支付</option><option>已支付</option><option>已退款</option></select></div>
            <div class="fitem"><label>创建时间起</label><input id="pkq-cfrom" type="date"></div>
            <div class="fitem"><label>创建时间止</label><input id="pkq-cto" type="date"></div>
            <div class="fitem"><label>支付时间起</label><input id="pkq-pfrom" type="date"></div>
            <div class="fitem"><label>支付时间止</label><input id="pkq-pto" type="date"></div>
            <button type="button" class="btn" id="pkq-go">🔍 查询</button>
            <button type="button" class="btn btn-ghost" id="pkq-reset">⟲ 重置</button>
          </div>
        </div>
        <div class="kpis" id="pk-kpis" style="font-size:15px"></div>
        <div class="tbl-wrap"><table id="pk-table"><thead></thead><tbody></tbody></table></div>
        <div class="pager" id="pk-foot"></div>
        <div class="note">✅ 套餐购买明细已接入：来自 <code>DATA.user.deposit_package_detail</code>（匹配图片2格式：订单号/城市/购买人/手机/电池产品/数量/金额/支付方式/时间/状态）。汇总金额取自 <code>DATA.sales.package_purchase_stats</code>。前端实时筛选 + 分页（每页 50），不请求后端。</div>
      </div>
    </div>
'''

working = working.replace(SALES_PANEL_ANCHOR,
                          AGREEMENT_PANEL + "\n      " + PACKAGE_PANEL + "\n      " + SALES_PANEL_ANCHOR,
                          1)

# ---- B) 设备资产看板：分组重组 ----
# 设备区域起始：dev-sub 子菜单；结束：最后一个叶子面板 panel-dev-health 的闭合 </div>
DEV_SUB_ANCHOR = '<div class="subtabs" id="dev-sub">'
assert DEV_SUB_ANCHOR in working, "dev-sub 锚点未找到"

def find_block(t, start):
    """start = index of '<div' (opening tag). 返回 (inner_start, close_start, block_end)。"""
    assert t[start:start+4] == '<div'
    open_end = t.find('>', start)
    stack = 1
    j = open_end + 1
    n = len(t)
    last_close_start = -1
    while j < n and stack > 0:
        di = t.find('<div', j)
        ci = t.find('</div', j)
        cand = []
        if di != -1:
            cand.append((di, 'open'))
        if ci != -1:
            cand.append((ci, 'close'))
        if not cand:
            break
        cand.sort(key=lambda x: x[0])
        pos, kind = cand[0]
        if kind == 'open':
            if t[pos+4] in ' \t>\n\r':
                stack += 1
                j = t.find('>', pos) + 1
            else:
                j = pos + 4
        else:
            if t[pos+5] in ' \t>\n\r':
                stack -= 1
                last_close_start = pos
                j = t.find('>', pos) + 1
            else:
                j = pos + 5
    block_end = j
    inner_start = open_end + 1
    close_start = last_close_start if last_close_start != -1 else t.rfind('</div', inner_start, block_end)
    return inner_start, close_start, block_end

region_start = working.find(DEV_SUB_ANCHOR)

# 叶子面板顺序（与原文一致），用于抽取内容
ORIG_IDS = ['cabinet', 'battery', 'cablist', 'batlist', 'warehouse',
            'circulation', 'rental', 'anomaly', 'inventory', 'fault', 'transfer', 'health']
RENAME = {'anomaly': 'anomaly12'}  # 避免与一级分组 panel-dev-anomaly 冲突
leaf_inner = {}
for oid in ORIG_IDS:
    nl = RENAME.get(oid, oid)
    open_tag = '<div class="devsub-panel" id="panel-dev-%s"' % oid
    oi = working.find(open_tag, region_start)
    assert oi != -1, "叶子面板未找到: %s" % oid
    istart, cstart, bend = find_block(working, oi)
    leaf_inner[nl] = working[istart:cstart].strip()

# 区域结束 = panel-dev-health 块的闭合位置
health_open = '<div class="devsub-panel" id="panel-dev-health"'
hoi = working.find(health_open, region_start)
_, _, region_end = find_block(working, hoi)

# 分组结构
GROUPS = {
    'basic':   ['cabinet', 'cablist', 'battery', 'batlist', 'warehouse', 'rental'],
    'flow':    ['circulation', 'transfer', 'inventory'],
    'anomaly': ['fault', 'anomaly12', 'health'],
}
LEAF_LABEL = {
    'cabinet': '换电柜总览', 'cablist': '换电柜明细', 'battery': '电池总览',
    'batlist': '电池明细', 'warehouse': '仓库列表', 'rental': '车辆租赁列表',
    'circulation': '电池流通记录', 'transfer': '设备调拨记录',
    'inventory': '设备出入库管理', 'fault': '故障设备管理',
    'anomaly12': '异常分类统计', 'health': '电池健康评估',
}

lines = []
lines.append('<div class="subtabs" id="dev-sub">')
lines.append('        <button type="button" class="stab active" data-devgroup="basic">📦 设备基础表</button>')
lines.append('        <button type="button" class="stab" data-devgroup="flow">🔄 调拨流通记录</button>')
lines.append('        <button type="button" class="stab" data-devgroup="anomaly">⚠️ 异常分类统计</button>')
lines.append('      </div>')
lines.append('      <div class="filterbar" id="fb-device"></div>')

for gi, (group, leaves) in enumerate(GROUPS.items()):
    g_active = (gi == 0)
    g_style = '' if g_active else ' style="display:none"'
    lines.append('      <div class="devsub-panel%s" id="panel-dev-%s">' % (g_style, group))
    lines.append('        <div class="subtabs dtab-bar" id="dev-%s-sub" data-group="%s">' % (group, group))
    for li, leaf in enumerate(leaves):
        t_active = (g_active and li == 0)
        t_cls = 'stab active' if t_active else 'stab'
        lines.append('          <button type="button" class="%s" data-devsub="%s">%s</button>' % (t_cls, leaf, LEAF_LABEL[leaf]))
    lines.append('        </div>')
    for li, leaf in enumerate(leaves):
        t_active = (g_active and li == 0)
        t_style = '' if t_active else ' style="display:none"'
        lines.append('        <div class="devtab-panel%s" id="dtab-%s">' % (t_style, leaf))
        lines.append(leaf_inner[leaf])
        lines.append('        </div>')
    lines.append('      </div>')

new_device_html = '\n'.join(lines)
working = working[:region_start] + new_device_html + working[region_end:]

# 更新设备 desc 文案（车辆/仓库/流通/租赁 已接入）
DEV_DESC_OLD = '含明细导出。按在线状态 / 设备 SN / 归属网点 等维度联动筛选（车辆/仓库/流通/租赁待数据接入）。'
DEV_DESC_NEW = '含明细导出。换电柜 / 电池 / 车辆 / 仓库 / 流通 / 调拨 / 出入库 / 故障 已全量接入（DATA.device.*），支持嵌套分组 + 维度联动筛选。'
if DEV_DESC_OLD in working:
    working = working.replace(DEV_DESC_OLD, DEV_DESC_NEW, 1)

# 更新「电池流通记录」note（现已接入 device.battery_flow）
CIRC_NOTE_OLD = ('<div class="note">⚠️ 电池流通记录（<code>t_battery_circulate_log</code> 839万条 / '
                 '<code>t_battery_circulate_log</code> 2253万条）因数据量过大未全量抽取；当前可用「设备调拨」'
                 '(<code>device.transfer</code> 9,800 条)查看电池流转记录。</div>')
CIRC_NOTE_NEW = ('<div class="note">✅ 电池流通记录已接入：<code>DATA.device.battery_flow</code>（采样 1 万条）+ '
                 '设备调拨 <code>DATA.device.transfer_log</code>（全量 1 万条）。下方为流通记录明细，'
                 '可按时段 / 方式 / 方向 / 对象筛选并导出。</div>')
if CIRC_NOTE_OLD in working:
    working = working.replace(CIRC_NOTE_OLD, CIRC_NOTE_NEW, 1)

# 更新「设备调拨记录」note（现已接入 device.transfer_log）
TF_NOTE_OLD = '<div class="note">⚠️ 数据待连接数据库后抽取；含操作人ID/名称/时间、设备类型/ID、操作类型、运营结果、流出/流入对象。</div>'
TF_NOTE_NEW = '<div class="note">✅ 设备调拨记录已接入：来自 <code>DATA.device.transfer_log</code>（全量 1 万条），含操作人ID/名称/时间、设备类型/ID、操作类型、运营结果、流出/流入对象。可筛选并导出。</div>'
if TF_NOTE_OLD in working:
    working = working.replace(TF_NOTE_OLD, TF_NOTE_NEW, 1)

# ---------------------------------------------------------------------------
# 3) 恢复 script/style（JS 编辑需在真实脚本上进行）
# ---------------------------------------------------------------------------
for ph, orig in blocks:
    working = working.replace(ph, orig, 1)
leftover = re.findall(r"__SB\d+__", working)
assert not leftover, "存在未恢复的占位符: %s" % leftover

# ===========================================================================
# 2) JS 文本替换（script 已恢复，可直接编辑）
# ===========================================================================

# ---- A) switchSalesSub 增加新子菜单绘制 ----
OLD_SWITCH_SALES = '''function switchSalesSub(ssub){
  SSUB=ssub;
  const box=document.getElementById('s-sub'); if(box) box.querySelectorAll('.stab').forEach(x=>x.classList.toggle('active', x.dataset.ssub===SSUB));
  document.querySelectorAll('.ssub-panel').forEach(p=>p.classList.remove('active'));
  const panel=document.getElementById('s-sub-'+SSUB);
  if(panel) panel.classList.add('active');
  applyFilters('sales');
  setTimeout(()=>window.dispatchEvent(new Event('resize')),30);
}'''
NEW_SWITCH_SALES = '''function switchSalesSub(ssub){
  SSUB=ssub;
  const box=document.getElementById('s-sub'); if(box) box.querySelectorAll('.stab').forEach(x=>x.classList.toggle('active', x.dataset.ssub===SSUB));
  document.querySelectorAll('.ssub-panel').forEach(p=>p.classList.remove('active'));
  const panel=document.getElementById('s-sub-'+SSUB); if(panel) panel.classList.add('active');
  if(SSUB==='agreement_sign'){ drawAgreementSignTable(); }
  else if(SSUB==='package_purchase'){ drawPackagePurchaseTable(); }
  applyFilters('sales');
  setTimeout(()=>window.dispatchEvent(new Event('resize')),30);
}'''
assert OLD_SWITCH_SALES in working, "switchSalesSub 锚点未找到"
working = working.replace(OLD_SWITCH_SALES, NEW_SWITCH_SALES, 1)

# ---- A) 插入销售新面板绘制函数（紧跟 switchSalesSub 之后） ----
SALES_DRAW_JS = r'''
// ---------- 销售看板：协议签约 / 套餐购买明细 ----------
let AG_ROWS=[], PKG_ROWS=[]; const _TBL={};
function _esc(v){ if(v===null||v===undefined) return ''; return String(v).replace(/[&<>"]/g,function(c){return ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]);}); }
function _colVal(r,c){ const ks=(c[1]||[]); for(let i=0;i<ks.length;i++){ const v=r[ks[i]]; if(v!==undefined&&v!==null&&v!=='') return v; } return ''; }
function _iso(s){ if(!s) return null; const m=String(s).replace(/[^0-9]/g,''); return m? m.slice(0,14):null; }
function _inRange(s,from,to){ if((!from)&&(!to)) return true; const d=_iso(s); if(d==null) return false; if(from&&d<_iso(from)) return false; if(to&&d>_iso(to)) return false; return true; }
function _dateStr(s){ if(!s) return ''; return String(s).replace(/-/g,'/').slice(0,10); }
function showRowDetail(title, cols, row){
  const m=document.getElementById('row-detail-modal'); if(!m) return;
  document.getElementById('rd-title').textContent=title||'详情';
  let h='<table class="rd-tbl" style="width:100%;border-collapse:collapse">';
  cols.forEach(c=>{ if(c[2]==='action') return; h+='<tr><th style="text-align:left;padding:4px 8px;border-bottom:1px solid #eee;color:#7c879b;white-space:nowrap">'+_esc(c[0])+'</th><td style="padding:4px 8px;border-bottom:1px solid #eee">'+_esc(_colVal(row,c))+'</td></tr>'; });
  h+='</table>';
  document.getElementById('rd-body').innerHTML=h;
  m.style.display='flex';
}
function _drawTable(tid){
  const st=_TBL[tid]; if(!st) return;
  if(st.sortIdx!=null){
    const c=st.cols[st.sortIdx]; const dir=(st.sortDir==='desc')?-1:1;
    st.rows=st.rows.slice().sort(function(a,b){ const x=_colVal(a,c),y=_colVal(b,c); const xn=parseFloat(x),yn=parseFloat(y); if(!isNaN(xn)&&!isNaN(yn)) return (xn-yn)*dir; return String(x).localeCompare(String(y),'zh')*dir; });
  }
  const total=st.rows.length, ps=st.pageSize, pages=Math.max(1,Math.ceil(total/ps));
  st.page=Math.min(Math.max(1,st.page),pages);
  const start=(st.page-1)*ps; const pr=st.rows.slice(start,start+ps);
  const tbl=document.getElementById(tid); if(!tbl) return;
  let h='<thead><tr>';
  st.cols.forEach(function(c,i){ if(c[2]==='action'){ h+='<th>操作</th>'; } else { h+='<th'+(c[2]==='num'?' class="num"':'')+' data-sort="'+i+' style="cursor:pointer">'+_esc(c[0])+(st.sortIdx===i?((st.sortDir==='desc')?' ▼':' ▲'):'')+'</th>'; } });
  h+='</tr></thead><tbody>';
  pr.forEach(function(r,idx){ h+='<tr>'; const rid=start+idx; st.cols.forEach(function(c){ if(c[2]==='action'){ h+='<td><button type="button" class="btn sm" data-act="detail" data-rid="'+rid+'">详情</button></td>'; } else { h+='<td'+(c[2]==='num'?' class="num"':'')+'>'+_esc(_colVal(r,c))+'</td>'; } }); h+='</tr>'; });
  if(!pr.length) h+='<tr><td colspan="'+st.cols.length+'" class="empty">无匹配数据</td></tr>';
  h+='</tbody>';
  tbl.innerHTML=h;
  tbl.querySelectorAll('th[data-sort]').forEach(function(th){ th.onclick=function(){ const i=+th.dataset.sort; if(st.sortIdx===i){ st.sortDir=(st.sortDir==='desc')?'asc':'desc'; } else { st.sortIdx=i; st.sortDir='asc'; } _drawTable(tid); }; });
  tbl.querySelectorAll('button[data-act]').forEach(function(b){ b.onclick=function(){ const rid=+b.dataset.rid; const row=st.rows[rid]; if(row) showRowDetail('协议 / 订单详情', st.cols, row); }; });
  const foot=document.getElementById(st.footId);
  if(foot){
    let fh='共 '+total+' 条 · 第 '+st.page+'/'+pages+' 页 ';
    if(pages>1){
      fh+='<button type="button" class="pg" data-pg="'+(st.page-1)+'">上一页</button>';
      for(let p=1;p<=pages;p++){ if(p===1||p===pages||Math.abs(p-st.page)<=2){ fh+='<button type="button" class="pg'+(p===st.page?' cur':'')+'" data-pg="'+p+'">'+p+'</button>'; } }
      fh+='<button type="button" class="pg" data-pg="'+(st.page+1)+'">下一页</button>';
    }
    foot.innerHTML=fh;
    foot.querySelectorAll('button[data-pg]').forEach(function(pb){ pb.onclick=function(){ const p=+pb.dataset.pg; if(p<1||p>pages) return; st.page=p; _drawTable(tid); }; });
  }
}
const AG_COLS=[
 ['协议ID',['agreement_id','agreementId','id','协议ID']],
 ['协议类型',['agreement_type','type','协议类型']],
 ['销售渠道',['sales_channel','channel','渠道','销售渠道']],
 ['用户ID',['user_id','userId','用户ID']],
 ['手机号',['phone','mobile','user_phone','手机号']],
 ['电池产品',['battery_product','battery','电池产品']],
 ['车辆数',['vehicle_count','car_count','车辆数'],'num'],
 ['车辆SN',['vehicle_sn','car_sn','车辆SN']],
 ['电池型号',['battery_model','bat_model','电池型号']],
 ['标准租金',['standard_rent','rent','标准租金'],'num'],
 ['方案费',['plan_fee','scheme_fee','方案费'],'num'],
 ['套餐名',['package_name','pkg_name','套餐','套餐名']],
 ['城市',['city','城市']],
 ['网点',['site','site_name','网点','网点名称']],
 ['代理商',['agent','agent_name','代理商']],
 ['渠道商',['channel_merchant','渠道商']],
 ['业务员',['salesman','sales_person','业务员']],
 ['公司',['company','公司']],
 ['激活时间',['active_time','activate_time','激活时间']],
 ['到期时间',['expire_time','到期时间']],
 ['是否长期',['is_long_term','long_term','是否长期']],
 ['押金',['deposit','押金'],'num'],
 ['状态',['status','state','状态']],
 ['创建时间',['create_time','created_at','创建时间']],
 ['操作',null,'action']
];
const PKG_COLS=[
 ['订单编号',['order_no','order_id','订单编号','订单号']],
 ['城市区域',['city','city_area','城市区域']],
 ['购买人',['buyer','purchaser','购买人','购买人姓名']],
 ['购买人手机号',['buyer_phone','phone','购买人手机号']],
 ['电池产品',['battery_product','battery','电池产品']],
 ['商品数量',['product_qty','qty','商品数量'],'num'],
 ['订单金额',['order_amount','订单金额'],'num'],
 ['缴费金额',['pay_amount','缴费金额'],'num'],
 ['应付实付金额',['actual_paid','paid_amount','应付实付金额','实付'],'num'],
 ['支付方式',['pay_method','pay_type','支付方式']],
 ['支付时间',['pay_time','支付时间']],
 ['型号网店',['model_site','型号网店']],
 ['套餐代理商',['pkg_agent','套餐代理商']],
 ['创建时间',['create_time','created_at','创建时间']],
 ['订单状态',['order_status','status','订单状态']],
 ['操作',null,'action']
];
function _g(id){ const e=document.getElementById(id); return e?e.value.trim():''; }
function drawAgreementSignTable(){
  const all=(DATA.user&&DATA.user.agreement_detail)||[];
  const f={ id:_g('agq-id'), user:_g('agq-user'), status:_g('agq-status'), model:_g('agq-model'), battery:_g('agq-battery'), type:_g('agq-type'), pkg:_g('agq-pkg'), site:_g('agq-site'), promo:_g('agq-promo'), cfrom:_g('agq-cfrom'), cto:_g('agq-cto'), bfrom:_g('agq-bfrom'), bto:_g('agq-bto'), efrom:_g('agq-efrom'), eto:_g('agq-eto') };
  const colOf=function(key){ return AG_COLS.find(function(c){ return (c[1]||[]).indexOf(key)>=0; }); };
  const getv=function(r,key){ const c=colOf(key); return c?_colVal(r,c):''; };
  const rows=all.filter(function(r){
    if(f.id && String(getv(r,'agreement_id')).indexOf(f.id)<0) return false;
    if(f.user){ const uv=String(getv(r,'user_id'))+' '+String(getv(r,'phone')); if(uv.indexOf(f.user)<0) return false; }
    if(f.status){ const mp={'待激活':'待激活','生效中':'生效','已停用':'停用','欠租':'欠租'}; const sv=String(getv(r,'status')); if(sv.indexOf(mp[f.status]||f.status)<0) return false; }
    if(f.model && String(getv(r,'model_style')||getv(r,'battery_model')).indexOf(f.model)<0) return false;
    if(f.battery && String(getv(r,'battery_product')).indexOf(f.battery)<0) return false;
    if(f.type && String(getv(r,'agreement_type')).indexOf(f.type)<0) return false;
    if(f.pkg && String(getv(r,'package_name')).indexOf(f.pkg)<0) return false;
    if(f.site && String(getv(r,'site')).indexOf(f.site)<0) return false;
    if(f.promo){ const pv=String(r.is_promo||r.promo||r['是否推广']||''); const yes=(pv==='是'||pv==='1'||pv==='true'); if(f.promo==='是'?!yes:yes) return false; }
    if(!_inRange(getv(r,'create_time'), f.cfrom, f.cto)) return false;
    if(!_inRange(getv(r,'buy_time')||getv(r,'active_time'), f.bfrom, f.bto)) return false;
    if(!_inRange(getv(r,'expire_time'), f.efrom, f.eto)) return false;
    return true;
  });
  const td=_dateStr(new Date());
  let cntToday=0,cntActive=0,cntStop=0;
  rows.forEach(function(r){ const ct=String(getv(r,'create_time')); if(_dateStr(ct)===td) cntToday++; const sv=String(getv(r,'status')); if(sv.indexOf('生效')>=0) cntActive++; else if(sv.indexOf('停用')>=0) cntStop++; });
  const cancelN=(DATA.user&&DATA.user.cancel_detail&&DATA.user.cancel_detail.length)||0;
  const rate=rows.length? (cancelN/Math.max(1,rows.length)*100):0;
  if(window.kpis) kpis(document.getElementById('ag-kpis'),[
    {l:'总协议数',v:fmt(rows.length)},
    {l:'今日新增',v:fmt(cntToday)},
    {l:'生效中',v:fmt(cntActive)},
    {l:'已停用',v:fmt(cntStop)},
    {l:'退订率',v:rate.toFixed(1)+'%'}
  ]);
  _TBL['ag-table']={rows:rows, cols:AG_COLS, page:1, pageSize:50, footId:'ag-foot', sortIdx:null, sortDir:'asc'};
  _drawTable('ag-table');
  AG_ROWS=rows;
  const go=document.getElementById('agq-go'); if(go) go.onclick=drawAgreementSignTable;
  const re=document.getElementById('agq-reset'); if(re) re.onclick=function(){ ['agq-id','agq-user','agq-model','agq-battery','agq-type','agq-pkg','agq-site','agq-cfrom','agq-cto','agq-bfrom','agq-bto','agq-efrom','agq-eto'].forEach(function(id){ const e=document.getElementById(id); if(e) e.value=''; }); const ps=document.getElementById('agq-status'); if(ps) ps.value=''; const pp=document.getElementById('agq-promo'); if(pp) pp.value=''; drawAgreementSignTable(); };
}
function _statVal(stats, keys){ if(!stats) return 0; for(let i=0;i<keys.length;i++){ if(stats[keys[i]]!==undefined&&stats[keys[i]]!==null) return stats[keys[i]]; } return 0; }
function drawPackagePurchaseTable(){
  const all=(DATA.user&&DATA.user.deposit_package_detail)||[];
  const f={ order:_g('pkq-order'), buyer:_g('pkq-buyer'), user:_g('pkq-user'), agr:_g('pkq-agr'), city:_g('pkq-city'), merchant:_g('pkq-merchant'), ptype:_g('pkq-ptype'), shop:_g('pkq-shop'), pay:_g('pkq-pay'), status:_g('pkq-status'), cfrom:_g('pkq-cfrom'), cto:_g('pkq-cto'), pfrom:_g('pkq-pfrom'), pto:_g('pkq-pto') };
  const colOf=function(key){ return PKG_COLS.find(function(c){ return (c[1]||[]).indexOf(key)>=0; }); };
  const getv=function(r,key){ const c=colOf(key); return c?_colVal(r,c):''; };
  const rows=all.filter(function(r){
    if(f.order && String(getv(r,'order_no')).indexOf(f.order)<0) return false;
    if(f.buyer && String(getv(r,'buyer')).indexOf(f.buyer)<0) return false;
    if(f.user){ const uv=String(getv(r,'user_id')||'')+' '+String(getv(r,'phone')||''); if(uv.indexOf(f.user)<0) return false; }
    if(f.agr && String(getv(r,'agreement_no')||getv(r,'agreement_id')).indexOf(f.agr)<0) return false;
    if(f.city && String(getv(r,'city')).indexOf(f.city)<0) return false;
    if(f.merchant && String(getv(r,'merchant_site')||getv(r,'merchant')).indexOf(f.merchant)<0) return false;
    if(f.ptype && String(getv(r,'product_type')||getv(r,'battery_product')).indexOf(f.ptype)<0) return false;
    if(f.shop && String(getv(r,'shop_no')||getv(r,'shop')).indexOf(f.shop)<0) return false;
    if(f.pay && String(getv(r,'pay_method')).indexOf(f.pay)<0) return false;
    if(f.status){ const sv=String(getv(r,'order_status')); if(sv.indexOf(f.status)<0) return false; }
    if(!_inRange(getv(r,'create_time'), f.cfrom, f.cto)) return false;
    if(!_inRange(getv(r,'pay_time'), f.pfrom, f.pto)) return false;
    return true;
  });
  const stats=(DATA.sales&&DATA.sales.package_purchase_stats)||{};
  const oc=_statVal(stats,['order_count','orderCount','订单数量','count']);
  const ta=_statVal(stats,['total_order_amount','totalOrderAmount','订单总金额','total_amount']);
  const pa=_statVal(stats,['total_paid_amount','totalPaidAmount','实收总金额','paid_amount','实付总金额']);
  const ra=_statVal(stats,['total_refund_amount','totalRefundAmount','退回总金额','refund_amount']);
  if(window.kpis) kpis(document.getElementById('pk-kpis'),[
    {l:'订单数量',v:fmt(oc)+' 笔',num:true},
    {l:'订单总金额',v:'¥'+fmt(ta),num:true},
    {l:'实收总金额',v:'¥'+fmt(pa),num:true},
    {l:'退回总金额',v:'¥'+fmt(ra),num:true}
  ]);
  _TBL['pk-table']={rows:rows, cols:PKG_COLS, page:1, pageSize:50, footId:'pk-foot', sortIdx:null, sortDir:'asc'};
  _drawTable('pk-table');
  PKG_ROWS=rows;
  const go=document.getElementById('pkq-go'); if(go) go.onclick=drawPackagePurchaseTable;
  const re=document.getElementById('pkq-reset'); if(re) re.onclick=function(){ ['pkq-order','pkq-buyer','pkq-user','pkq-agr','pkq-city','pkq-merchant','pkq-ptype','pkq-shop','pkq-pay','pkq-cfrom','pkq-cto','pkq-pfrom','pkq-pto'].forEach(function(id){ const e=document.getElementById(id); if(e) e.value=''; }); const ps=document.getElementById('pkq-status'); if(ps) ps.value=''; drawPackagePurchaseTable(); };
}
'''

ANCHOR_AFTER_SWITCH = "function bindSalesSub(){"
assert ANCHOR_AFTER_SWITCH in working, "bindSalesSub 锚点未找到"
working = working.replace(ANCHOR_AFTER_SWITCH, SALES_DRAW_JS + "\n" + ANCHOR_AFTER_SWITCH, 1)

# ---- B) bindDeviceSub 第一层绑定改写（保留导出/搜索绑定） ----
OLD_BIND_DEV = '''  const box=document.getElementById('dev-sub'); if(!box)return;
  const withFilter=['cabinet','battery','cablist','batlist'];
  box.querySelectorAll('.stab').forEach(b=>{
    b.addEventListener('click',()=>{
      DEVSUB=b.dataset.devsub; state.deviceSub=DEVSUB;
      box.querySelectorAll('.stab').forEach(x=>x.classList.toggle('active', x.dataset.devsub===DEVSUB));
      document.querySelectorAll('[id^="panel-dev-"]').forEach(p=>p.style.display='none');
      const panel=document.getElementById('panel-dev-'+DEVSUB); if(panel)panel.style.display='';
      const fb=document.getElementById('fb-device'); if(fb) fb.style.display = withFilter.includes(DEVSUB)?'':'none';
      if(DEVSUB==='anomaly'){ drawDevAnomaly(); return; }
      DEVCAB_FILTER='';
      if(withFilter.includes(DEVSUB)) buildFilterBar('device');
      applyDevice(state.device||{});
    });
  });'''
NEW_BIND_DEV = '''  const box=document.getElementById('dev-sub'); if(!box)return;
  const withFilter=['cabinet','battery','cablist','batlist'];
  box.querySelectorAll('.stab').forEach(b=>{
    b.addEventListener('click',()=>{ switchDeviceSub(b.dataset.devgroup); });
  });
  document.querySelectorAll('.dtab-bar').forEach(bar=>{
    bar.querySelectorAll('.stab').forEach(b=>{
      b.addEventListener('click',()=>{ switchDevTab(bar.dataset.group, b.dataset.devsub); });
    });
  });'''
assert OLD_BIND_DEV in working, "bindDeviceSub 首段锚点未找到"
working = working.replace(OLD_BIND_DEV, NEW_BIND_DEV, 1)

# ---- B) applyDevice 改写（按 dtab 显示，DEVSUB=leaf） ----
OLD_APPLY_DEV = '''function applyDevice(f){
  const sub=DEVSUB;
  document.querySelectorAll('[id^="panel-dev-"]').forEach(p=>p.style.display='none');
  const panel=document.getElementById('panel-dev-'+sub); if(panel)panel.style.display='';
  if(sub==='cabinet') return drawDevCabinet(f);
  if(sub==='battery') return drawDevBattery(f);
  if(sub==='cablist') return drawDevCabList(f);
  if(sub==='batlist') return drawDevBatList(f);
  if(sub==='warehouse') return drawDevWarehouse(f);
  if(sub==='circulation') return drawDevCirculation(f);
  if(sub==='rental') return drawDevRental(f);
  if(sub==='inventory') return drawDevInventory(f);
  if(sub==='fault') return drawDevFault(f);
  if(sub==='transfer') return drawDevTransfer(f);
  if(sub==='health') return drawDevBatteryHealth(f);
}'''
NEW_APPLY_DEV = '''function applyDevice(f){
  const sub=DEVSUB;
  document.querySelectorAll('.devtab-panel').forEach(p=>p.style.display='none');
  const tp=document.getElementById('dtab-'+sub); if(tp)tp.style.display='';
  if(sub==='cabinet') return drawDevCabinet(f);
  if(sub==='cablist') return drawDevCabList(f);
  if(sub==='battery') return drawDevBattery(f);
  if(sub==='batlist') return drawDevBatList(f);
  if(sub==='warehouse') return drawDevWarehouse(f);
  if(sub==='circulation') return drawDevCirculation(f);
  if(sub==='rental') return drawDevRental(f);
  if(sub==='inventory') return drawDevInventory(f);
  if(sub==='fault') return drawDevFault(f);
  if(sub==='transfer') return drawDevTransfer(f);
  if(sub==='anomaly12') return drawDevAnomaly(f);
  if(sub==='health') return drawDevBatteryHealth(f);
}'''
assert OLD_APPLY_DEV in working, "applyDevice 锚点未找到"
working = working.replace(OLD_APPLY_DEV, NEW_APPLY_DEV, 1)

# ---- B) 插入设备分组函数（applyDevice 之后） ----
DEV_GROUP_JS = r'''
// ---------- 设备资产看板：一级分组 + 嵌套 tab ----------
const DEV_LEAF_GROUP={cabinet:'basic',cablist:'basic',battery:'basic',batlist:'basic',warehouse:'basic',rental:'basic',circulation:'flow',transfer:'flow',inventory:'flow',fault:'anomaly',anomaly12:'anomaly',health:'anomaly'};
const DEV_GROUP_DEFAULT={basic:'cabinet',flow:'circulation',anomaly:'fault'};
const DEV_WITH_FILTER=['cabinet','battery','cablist','batlist'];
function switchDeviceSub(group){ // 一级子菜单：设备分组
  document.querySelectorAll('[id^="panel-dev-"]').forEach(p=>p.style.display='none');
  const gp=document.getElementById('panel-dev-'+group); if(gp)gp.style.display='';
  const def=DEV_GROUP_DEFAULT[group]||firstLeaf(group);
  switchDevTab(group, def);
}
function firstLeaf(group){ for(const k in DEV_LEAF_GROUP){ if(DEV_LEAF_GROUP[k]===group) return k; } return null; }
function switchDevTab(group, tab){
  DEVSUB=tab; state.deviceSub=tab;
  const bar=document.getElementById('dev-'+group+'-sub');
  if(bar) bar.querySelectorAll('.stab').forEach(x=>x.classList.toggle('active', x.dataset.devsub===tab));
  document.querySelectorAll('[id^="panel-dev-"]').forEach(p=>p.style.display='none');
  const gp=document.getElementById('panel-dev-'+group); if(gp)gp.style.display='';
  document.querySelectorAll('#panel-dev-'+group+' .devtab-panel').forEach(p=>p.style.display='none');
  const tp=document.getElementById('dtab-'+tab); if(tp)tp.style.display='';
  const fb=document.getElementById('fb-device'); if(fb) fb.style.display=DEV_WITH_FILTER.includes(tab)?'':'none';
  DEVCAB_FILTER='';
  if(DEV_WITH_FILTER.includes(tab)) buildFilterBar('device');
  applyDevice(state.device||{});
  setTimeout(()=>window.dispatchEvent(new Event('resize')),30);
}
function showDeviceLeaf(leaf){
  const g=DEV_LEAF_GROUP[leaf]; if(!g) return;
  document.querySelectorAll('#dev-sub .stab').forEach(x=>x.classList.toggle('active', x.dataset.devgroup===g));
  switchDevTab(g, leaf);
}
'''
ANCHOR_AFTER_APPLY = "// 10 设备出入库管理 ⚠️ 待抽"
assert ANCHOR_AFTER_APPLY in working, "applyDevice 后锚点未找到"
working = working.replace(ANCHOR_AFTER_APPLY, DEV_GROUP_JS + "\n" + ANCHOR_AFTER_APPLY, 1)

# ---- B) preset 中 deviceSub 处理改为 showDeviceLeaf ----
OLD_PRESET_DEV = "  if(preset.deviceSub){ DEVSUB=preset.deviceSub; state.deviceSub=DEVSUB; document.querySelectorAll('#dev-sub .stab').forEach(x=>x.classList.toggle('active', x.dataset.devsub===DEVSUB)); document.querySelectorAll('[id^=\"panel-dev-\"]').forEach(p=>p.style.display='none'); const _p=document.getElementById('panel-dev-'+DEVSUB); if(_p)_p.style.display=''; }"
NEW_PRESET_DEV = "  if(preset.deviceSub){ showDeviceLeaf(preset.deviceSub); }"
assert OLD_PRESET_DEV in working, "preset deviceSub 锚点未找到"
working = working.replace(OLD_PRESET_DEV, NEW_PRESET_DEV, 1)

# 初始化时确保默认分组可见（若 DEVSUB 是 leaf，group 可能未显示）——在 bindDeviceSub 调用前兜底
# 通过 switchDeviceSub 重绘默认分组（覆盖原 applyDevice 初始调用）
# 在 init 区域（applyDevice(state.device||{}); 紧跟 bindDeviceSub 后）追加分组首屏
INIT_ANCHOR = "  bindDeviceSub();\n  applyDevice(state.device||{});"
INIT_REPLACE = "  bindDeviceSub();\n  switchDeviceSub(DEV_LEAF_GROUP[DEVSUB]||'basic');"
assert INIT_ANCHOR in working, "init anchor 未找到"
working = working.replace(INIT_ANCHOR, INIT_REPLACE, 1)

# ---------------------------------------------------------------------------
# 4) 写出 + 校验
# ---------------------------------------------------------------------------
open(PATH, "w", encoding="utf-8").write(working)

def check_div_balance(s):
    # 粗略统计 <div ...> 与 </div>（忽略自闭合/注释，足够发现重大不平衡）
    opens = len(re.findall(r"<div[\s>]", s))
    closes = len(re.findall(r"</div\s*>", s))
    return opens, closes

opens, closes = check_div_balance(working)
print("DIV open=%d close=%d" % (opens, closes))
assert opens == closes, "DIV 标签不平衡！open=%d close=%d" % (opens, closes)

# 新面板/分组 ID 必须存在
for needed in ["s-sub-agreement_sign", "s-sub-package_purchase", "panel-dev-basic",
               "panel-dev-flow", "panel-dev-anomaly", "dtab-cabinet", "dtab-battery",
               "dtab-warehouse", "dtab-circulation", "dtab-transfer", "dtab-inventory",
               "dtab-fault", "dtab-anomaly12", "ag-table", "pk-table", "row-detail-modal"]:
    assert ('id="%s"' % needed) in working, "缺少新 ID: %s" % needed

# 旧叶子面板 ID 不应再作为独立 panel-dev-* 存在（已嵌套为 dtab-*）
# 例外：orig id 与一级分组同名（anomaly）时，panel-dev-anomaly 是一级分组容器，允许存在
GROUP_NAMES = set(GROUPS.keys())
for old in ORIG_IDS:
    if old in GROUP_NAMES:
        continue
    assert ('id="panel-dev-%s"' % old) not in working, "旧面板 ID 仍存在: panel-dev-%s" % old

# 旧设备按钮（data-devsub 叶子）不应再出现在 #dev-sub 中
assert 'data-devsub="cabinet"' not in working.split('id="dev-sub">')[1].split('</div>')[0], "dev-sub 内仍含旧叶子按钮"

# JS 函数存在性
for fn in ["function switchSalesSub", "function drawAgreementSignTable", "function drawPackagePurchaseTable",
           "function switchDeviceSub", "function switchDevTab", "function showDeviceLeaf", "function applyDevice"]:
    assert fn in working, "JS 函数缺失: %s" % fn

# py_compile smoke（脚本自身可编译）
py_compile.compile(__file__, doraise=True)
print("py_compile OK")

print("ALL CHECKS PASSED")
