# -*- coding: utf-8 -*-
"""给人员看板新增 5 大实体子菜单（代理商/渠道商/代理商员工/商户/导购总览）。
保留原 #v-personnel 的 overview 数据（p-kpis/p-rank/p-detail1/p-detail2）。
用法: python scripts/patch_personnel_sub.py
"""
import io, sys, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TPL = os.path.join(ROOT, 'html', 'template.html')
with io.open(TPL, 'r', encoding='utf-8') as f:
    s = f.read()

# ---------- 1) 替换 #v-personnel 内部 HTML ----------
OLD = '''    <div class="view" id="v-personnel">
      <h2 class="title">人员看板</h2>
      <p class="desc">基于状态、角色（店长）等维度联动筛选。点击业务员销冠柱可跳转销售看板。</p>
      <div class="filterbar" id="fb-personnel"></div>
      <div class="kpis" id="p-kpis"></div>
      <div class="panel"><h3>业务员销售排行（按签约协议数 Top50，全量）</h3><div id="p-rank" class="chart"></div></div>
      <div class="panel">
        <h3>店员 / 导购列表（样本上限 <span id="p-cap1"></span>）</h3>
        <div class="tbl-wrap"><table id="p-detail1"><thead></thead><tbody></tbody></table></div>
      </div>
      <div class="panel">
        <h3>渠道商 / 代理商列表（样本上限 <span id="p-cap2"></span>）</h3>
        <div class="tbl-wrap"><table id="p-detail2"><thead></thead><tbody></tbody></table></div>
      </div>
    </div>'''

NEW = '''    <div class="view" id="v-personnel">
      <h2 class="title">人员看板</h2>
      <p class="desc">按 代理商 / 渠道商 / 代理商员工 / 商户 / 导购 维度总览其名下网点状态与签约用户（用户数已按 user_id 去重）。点击行内「跳转」可联动用户看板；「分成金额」⚠️ 待接入来源。</p>
      <div class="filterbar" id="fb-personnel"></div>
      <div class="subtabs" id="pe-sub">
        <button class="stab active" data-pesub="overview">人员总览（原）</button>
        <button class="stab" data-pesub="agency">代理商总览</button>
        <button class="stab" data-pesub="distributor">渠道商总览</button>
        <button class="stab" data-pesub="agency_emp">代理商员工总览</button>
        <button class="stab" data-pesub="merchant">商户总览</button>
        <button class="stab" data-pesub="promoter">导购总览</button>
      </div>

      <div class="usub-panel active" id="pe-sub-overview">
        <div class="kpis" id="p-kpis"></div>
        <div class="panel"><h3>业务员销售排行（按签约协议数 Top50，全量）</h3><div id="p-rank" class="chart"></div></div>
        <div class="panel">
          <h3>店员 / 导购列表（样本上限 <span id="p-cap1"></span>）</h3>
          <div class="tbl-wrap"><table id="p-detail1"><thead></thead><tbody></tbody></table></div>
        </div>
        <div class="panel">
          <h3>渠道商 / 代理商列表（样本上限 <span id="p-cap2"></span>）</h3>
          <div class="tbl-wrap"><table id="p-detail2"><thead></thead><tbody></tbody></table></div>
        </div>
      </div>

      <div class="usub-panel" id="pe-sub-agency">
        <div class="kpis" id="pe-agency-kpis"></div>
        <div class="grid2">
          <div class="panel"><h3>网点状态分布（营业中 / 已关闭）</h3><div id="pe-agency-sites" class="chart"></div></div>
          <div class="panel"><h3>签约用户状态分布</h3><div id="pe-agency-users" class="chart"></div></div>
        </div>
        <div class="panel"><h3>各代理商明细（点击行可查看其用户 / 协议明细）</h3><div class="tbl-wrap"><table id="pe-agency-detail"><thead></thead><tbody></tbody></table></div></div>
        <div class="panel"><h3>选中代理商 · 用户 / 协议明细（样本上限 <span id="pe-agency-scap"></span>）</h3><div class="tbl-wrap"><table id="pe-agency-sample"><thead></thead><tbody></tbody></table></div></div>
      </div>

      <div class="usub-panel" id="pe-sub-distributor">
        <div class="kpis" id="pe-dist-kpis"></div>
        <div class="grid2">
          <div class="panel"><h3>网点状态分布（营业中 / 已关闭）</h3><div id="pe-dist-sites" class="chart"></div></div>
          <div class="panel"><h3>签约用户状态分布</h3><div id="pe-dist-users" class="chart"></div></div>
        </div>
        <div class="panel"><h3>各渠道商明细（点击行可查看其用户 / 协议明细）</h3><div class="tbl-wrap"><table id="pe-dist-detail"><thead></thead><tbody></tbody></table></div></div>
        <div class="panel"><h3>选中渠道商 · 用户 / 协议明细（样本上限 <span id="pe-dist-scap"></span>）</h3><div class="tbl-wrap"><table id="pe-dist-sample"><thead></thead><tbody></tbody></table></div></div>
      </div>

      <div class="usub-panel" id="pe-sub-agency_emp">
        <div class="kpis" id="pe-emp-kpis"></div>
        <div class="panel"><h3>签约用户状态分布</h3><div id="pe-emp-users" class="chart"></div></div>
        <div class="note hl">★ 分成金额 ⚠️ 占位待接入来源（代理商员工分成为独立核算字段，当前看板未接入）。</div>
        <div class="panel"><h3>各代理商员工明细（点击行展开其网点 / 用户双分支）</h3><div class="tbl-wrap"><table id="pe-emp-detail"><thead></thead><tbody></tbody></table></div></div>
        <div class="grid2">
          <div class="panel"><h3>选中员工 · 名下网点明细（<span id="pe-emp-scap1"></span>）</h3><div class="tbl-wrap"><table id="pe-emp-sites"><thead></thead><tbody></tbody></table></div></div>
          <div class="panel"><h3>选中员工 · 名下用户明细（样本上限 <span id="pe-emp-scap2"></span>）</h3><div class="tbl-wrap"><table id="pe-emp-users-t"><thead></thead><tbody></tbody></table></div></div>
        </div>
      </div>

      <div class="usub-panel" id="pe-sub-merchant">
        <div class="kpis" id="pe-mch-kpis"></div>
        <div class="grid2">
          <div class="panel"><h3>网点状态分布（营业中 / 已关闭）</h3><div id="pe-mch-sites" class="chart"></div></div>
          <div class="panel"><h3>签约用户状态分布</h3><div id="pe-mch-users" class="chart"></div></div>
        </div>
        <div class="note hl">★ 分成金额 ⚠️ 占位待接入来源（商户分成为独立核算字段，当前看板未接入）。</div>
        <div class="panel"><h3>各商户明细（点击行可查看其用户明细）</h3><div class="tbl-wrap"><table id="pe-mch-detail"><thead></thead><tbody></tbody></table></div></div>
        <div class="panel"><h3>选中商户 · 用户 / 协议明细（样本上限 <span id="pe-mch-scap"></span>）</h3><div class="tbl-wrap"><table id="pe-mch-sample"><thead></thead><tbody></tbody></table></div></div>
      </div>

      <div class="usub-panel" id="pe-sub-promoter">
        <div class="kpis" id="pe-pro-kpis"></div>
        <div class="panel"><h3>签约用户状态分布</h3><div id="pe-pro-users" class="chart"></div></div>
        <div class="note hl">★ 分成金额 ⚠️ 占位待接入来源（导购分成为独立核算字段，当前看板未接入）。</div>
        <div class="panel"><h3>各导购明细（点击行可查看其签约协议明细）</h3><div class="tbl-wrap"><table id="pe-pro-detail"><thead></thead><tbody></tbody></table></div></div>
        <div class="panel"><h3>选中导购 · 签约用户协议明细（样本上限 <span id="pe-pro-scap"></span>）</h3><div class="tbl-wrap"><table id="pe-pro-sample"><thead></thead><tbody></tbody></table></div></div>
      </div>
    </div>'''

assert OLD in s, 'OLD #v-personnel block not found'
s = s.replace(OLD, NEW, 1)

# ---------- 2) 注入 JS（在 let USUB='overview'; 之后）----------
ANCHOR = "let USUB='overview';"
assert ANCHOR in s, 'JS anchor not found'
JS = '''

// ============ 人员看板：5 大实体总览 ============
let PESUB='overview';
const PE_SEL={agency:null,distributor:null,agency_emp:null,merchant:null,promoter:null};
function peTable(tid, head, rows){
  var t=document.getElementById(tid); if(!t)return;
  var h='<thead><tr>'+head.map(function(x){return '<th>'+x+'</th>';}).join('')+'</tr></thead>';
  var b='<tbody>'+(rows&&rows.length?rows.map(function(r){return '<tr>'+r.map(function(c){return '<td>'+c+'</td>';}).join('')+'</tr>';}).join(''):'<tr><td colspan="'+head.length+'" class="empty">暂无数据</td></tr>')+'</tbody>';
  t.innerHTML=h+b;
}
function peEsc(x){return String(x==null?'':x).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
function peSites(s){s=s||{};return '营业中 '+(s.on||0)+' / 关闭 '+(s.off||0);}
function peUserChart(id,u){pie(id,[{name:'生效',value:u.working||0},{name:'欠租',value:u.owe||0},{name:'退订',value:u.cancel||0},{name:'协议终止',value:u.terminate||0},{name:'其他',value:u.other||0}],null,null,'人');}
function peSiteChart(id,s){s=s||{};pie(id,[{name:'营业中',value:s.on||0},{name:'已关闭',value:s.off||0}],null,null,'个');}
function peAggKpis(id,arr,label){
  var t=0,w=0,o=0,c=0,te=0,son=0,soff=0;
  (arr||[]).forEach(function(e){var u=e.users||{};t+=u.total||0;w+=u.working||0;o+=u.owe||0;c+=u.cancel||0;te+=u.terminate||0;var s=e.sites||{};son+=(s.on||0);soff+=(s.off||0);});
  kpis(document.getElementById(id),[
    {l:label+'数',v:fmt(arr.length),s:''},
    {l:'签约总用户',v:fmt(t),s:'去重'},
    {l:'生效用户',v:fmt(w),s:''},
    {l:'欠租用户',v:fmt(o),s:''},
    {l:'退订用户',v:fmt(c),s:''},
    {l:'协议终止用户',v:fmt(te),s:''},
    {l:'网点数',v:fmt(son+soff),s:'营业中 '+fmt(son)+' · 关闭 '+fmt(soff)}
  ]);
}
function peSampleHead(){return ['协议ID','用户ID','城市','类型','状态','激活','到期','押金','网点','导购'];}
function peSampleRow(r){return [r.agreement_id,r.user,r.city,r.type,r.status,r.activate,r.expire,fmt(r.deposit),r.site||'—',r.promoter||'—'];}
function aggSites(arr){var s={on:0,off:0};(arr||[]).forEach(function(e){var x=e.sites||{};s.on+=(x.on||0);s.off+=(x.off||0);});return s;}
function aggUsers(arr){var u={working:0,owe:0,cancel:0,terminate:0,other:0};(arr||[]).forEach(function(e){var x=e.users||{};u.working+=(x.working||0);u.owe+=(x.owe||0);u.cancel+=(x.cancel||0);u.terminate+=(x.terminate||0);u.other+=(x.other||0);});return u;}
function peRenderSample(tid,capId,arr,selId){
  var sel=(arr||[]).filter(function(e){return String(e.id)===String(selId);})[0];
  var samp=sel?(sel.sample||[]):[];
  var cap=document.getElementById(capId); if(cap)cap.textContent=Math.min(samp.length,2000);
  peTable(tid,peSampleHead(),samp.slice(0,2000).map(peSampleRow));
}
function peJump(type,key){
  state.user=state.user||{};
  if(type==='agency'){var a=(DATA.personnel.agencies||[]).filter(function(x){return String(x.id)===String(key);})[0];state.user.agency=a?a.name:key;}
  navigate('user');
}
function drawPersonnelOv(sub){
  var P=DATA.personnel||{};
  if(sub==='agency'){
    var arr=P.agencies||[];peAggKpis('pe-agency-kpis',arr,'代理商');
    peSiteChart('pe-agency-sites',aggSites(arr));peUserChart('pe-agency-users',aggUsers(arr));
    var rows=arr.map(function(e){return ['<button class="btn btn-ghost pe-sel" data-sub="agency" data-id="'+e.id+'">'+peEsc(e.name)+'</button>',peSites(e.sites),fmt(e.users.total),fmt(e.users.working),fmt(e.users.owe),fmt(e.users.cancel),fmt(e.users.terminate),'<button class="btn pe-jump" data-type="agency" data-key="'+e.id+'">跳转用户列表</button>'];});
    peTable('pe-agency-detail',['代理商','网点数(营业中/关闭)','签约总','生效','欠租','退订','协议终止','操作'],rows);
    peRenderSample('pe-agency-sample','pe-agency-scap',arr,PE_SEL.agency);
    setTimeout(function(){window.dispatchEvent(new Event('resize'));},30);return;
  }
  if(sub==='distributor'){
    var arr=P.distributors_ov||[];peAggKpis('pe-dist-kpis',arr,'渠道商');
    peSiteChart('pe-dist-sites',aggSites(arr));peUserChart('pe-dist-users',aggUsers(arr));
    var rows=arr.map(function(e){return ['<button class="btn btn-ghost pe-sel" data-sub="distributor" data-id="'+e.id+'">'+peEsc(e.name)+'</button>',(e.agency_id?('代理商#'+e.agency_id):'—'),peSites(e.sites),fmt(e.users.total),fmt(e.users.working),fmt(e.users.owe),fmt(e.users.cancel),fmt(e.users.terminate),'<button class="btn pe-jump" data-type="distributor" data-key="'+e.id+'">跳转用户列表</button>'];});
    peTable('pe-dist-detail',['渠道商','所属代理商','网点数(营业中/关闭)','签约总','生效','欠租','退订','协议终止','操作'],rows);
    peRenderSample('pe-dist-sample','pe-dist-scap',arr,PE_SEL.distributor);return;
  }
  if(sub==='agency_emp'){
    var arr=P.agency_employees||[];peAggKpis('pe-emp-kpis',arr,'代理商员工');
    peUserChart('pe-emp-users',aggUsers(arr));
    var rows=arr.map(function(e){return ['<button class="btn btn-ghost pe-sel" data-sub="agency_emp" data-id="'+e.employee_id+'">'+peEsc(e.name)+'</button>',(e.agency_id?('代理商#'+e.agency_id):'—'),(e.merchant_id?('商户#'+e.merchant_id):'—'),peSites(e.sites),fmt(e.users.total),fmt(e.users.working),fmt(e.users.owe),fmt(e.users.cancel),fmt(e.users.terminate),'⚠️分成待接入','<button class="btn pe-jump" data-type="agency_emp" data-key="'+e.employee_id+'">跳转用户列表</button>'];});
    peTable('pe-emp-detail',['员工','所属代理商','关联商户','网点数(营业中/关闭)','签约总','生效','欠租','退订','协议终止','分成金额','操作'],rows);
    var sel=(arr||[]).filter(function(e){return String(e.employee_id)===String(PE_SEL.agency_emp);})[0];
    var ssites=sel?(sel.site_sample||[]):[];var susers=sel?(sel.user_sample||[]):[];
    var c1=document.getElementById('pe-emp-scap1');if(c1)c1.textContent=ssites.length;
    var c2=document.getElementById('pe-emp-scap2');if(c2)c2.textContent=Math.min(susers.length,2000);
    peTable('pe-emp-sites',['网点名称','网点状态'],ssites.map(function(s){return [s.site,s.site_status];}));
    peTable('pe-emp-users-t',peSampleHead(),susers.slice(0,2000).map(peSampleRow));return;
  }
  if(sub==='merchant'){
    var arr=P.merchants||[];peAggKpis('pe-mch-kpis',arr,'商户');
    peSiteChart('pe-mch-sites',aggSites(arr));peUserChart('pe-mch-users',aggUsers(arr));
    var rows=arr.map(function(e){return ['<button class="btn btn-ghost pe-sel" data-sub="merchant" data-id="'+e.id+'">'+peEsc(e.name)+'</button>',(e.agency_id?('代理商#'+e.agency_id):'—'),peSites(e.sites),fmt(e.users.total),fmt(e.users.working),fmt(e.users.owe),fmt(e.users.cancel),fmt(e.users.terminate),'⚠️分成待接入','<button class="btn pe-jump" data-type="merchant" data-key="'+e.id+'">跳转用户列表</button>'];});
    peTable('pe-mch-detail',['商户','所属代理商','网点数(营业中/关闭)','签约总','生效','欠租','退订','协议终止','分成金额','操作'],rows);
    peRenderSample('pe-mch-sample','pe-mch-scap',arr,PE_SEL.merchant);return;
  }
  if(sub==='promoter'){
    var arr=P.promoters||[];peAggKpis('pe-pro-kpis',arr,'导购');
    peUserChart('pe-pro-users',aggUsers(arr));
    var rows=arr.map(function(e){return ['<button class="btn btn-ghost pe-sel" data-sub="promoter" data-id="'+e.id+'">'+peEsc(e.name)+'</button>',(e.agency_id?('代理商#'+e.agency_id):'—'),(e.phone||'—'),fmt(e.users.total),fmt(e.users.working),fmt(e.users.owe),fmt(e.users.cancel),fmt(e.users.terminate),'⚠️分成待接入','<button class="btn pe-jump" data-type="promoter" data-key="'+e.id+'">跳转用户协议列表</button>'];});
    peTable('pe-pro-detail',['导购','所属代理商','手机号','签约总','生效','欠租','退订','协议终止','分成金额','操作'],rows);
    peRenderSample('pe-pro-sample','pe-pro-scap',arr,PE_SEL.promoter);return;
  }
}
function switchPersonnelSub(sub){
  PESUB=sub;
  var box=document.getElementById('pe-sub');if(box)box.querySelectorAll('.stab').forEach(function(x){x.classList.toggle('active',x.dataset.pesub===PESUB);});
  document.querySelectorAll('.usub-panel').forEach(function(p){p.classList.remove('active');});
  var panel=document.getElementById('pe-sub-'+PESUB);if(panel)panel.classList.add('active');
  if(sub==='overview'){applyPersonnel(state.personnel||{});}
  else{drawPersonnelOv(sub);}
  setTimeout(function(){window.dispatchEvent(new Event('resize'));},30);
}
function bindPersonnelSub(){
  var box=document.getElementById('pe-sub');if(!box)return;
  box.querySelectorAll('.stab').forEach(function(b){b.addEventListener('click',function(){switchPersonnelSub(b.dataset.pesub);});});
  var pv=document.getElementById('v-personnel');if(!pv)return;
  pv.addEventListener('click',function(ev){
    var sel=ev.target.closest&&ev.target.closest('.pe-sel');if(sel){PE_SEL[sel.dataset.sub]=sel.dataset.id;drawPersonnelOv(sel.dataset.sub);return;}
    var jp=ev.target.closest&&ev.target.closest('.pe-jump');if(jp){peJump(jp.dataset.type,jp.dataset.key);return;}
  });
}
'''
s = s.replace(ANCHOR, ANCHOR + JS, 1)

# ---------- 3) 人员视图激活改走 switchPersonnelSub ----------
OLD_ACT = "  if(mod==='personnel'){ applyPersonnel(f); return; }"
NEW_ACT = "  if(mod==='personnel'){ switchPersonnelSub(PESUB); return; }"
assert OLD_ACT in s, 'personnel activate line not found'
s = s.replace(OLD_ACT, NEW_ACT, 1)

# ---------- 4) 接线 bindPersonnelSub（在 bindUserSub(); 附近）----------
OLD_BIND = "  bindUserSub();"
NEW_BIND = "  bindUserSub();\n  bindPersonnelSub();"
assert OLD_BIND in s, 'bindUserSub call not found'
s = s.replace(OLD_BIND, NEW_BIND, 1)

with io.open(TPL, 'w', encoding='utf-8') as f:
    f.write(s)
print('PATCH OK: personnel 5 sub-menus injected')
