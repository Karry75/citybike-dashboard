# -*- coding: utf-8 -*-
"""Round 36: add '换电订单' submenu to 网点看板 (#v-site).
Inserts: tab button, panel, switchSiteSub branch, drawSiteExchange fn,
search/export bindings in bindSiteSub, and updates the view desc (6->7).
Data source: DATA.site.exchange (missing -> graceful ? placeholder)."""
import io, re

P = r"D:\workboddy file\dudu分析\citybike_backup\html\template.html"
html = open(P, encoding="utf-8").read()

def patch(anchor, new, label):
    if anchor not in html:
        raise SystemExit("ANCHOR NOT FOUND: " + label)
    if new in html.split(anchor)[0] or html.count(new) > 0 and new[:40] in html:
        # naive dup guard for our own injected unique markers
        pass
    return html.replace(anchor, new, 1)

# ---- 1) tab button (after salesperf) ----
anchor1 = '''        <button type="button" class="stab" data-wsub="salesperf">\U0001F4C8 网点销售业绩</button>
      </div>'''
new1 = '''        <button type="button" class="stab" data-wsub="salesperf">\U0001F4C8 网点销售业绩</button>
        <button type="button" class="stab" data-wsub="exchange">\U0001F504 换电订单</button>
      </div>'''
html = patch(anchor1, new1, "tab button")

# ---- 2) panel (after salesperf panel close, before outer </div>) ----
anchor2 = '''      </div>
    </div>

    <!-- DEVICE -->'''
new2 = '''      </div>

      <!-- 换电订单 -->
      <div class="wsub-panel" id="w-sub-exchange">
        <div class="note">本子菜单展示换电订单明细（订单 / 用户 / 网点 / 电池 / 费用 / 状态）。数据源为 production 库 exchange_order 类表，需接通 ADB 后由 extract_site_ext.py 抽取注入 <code>DATA.site.exchange</code>。当前为框架，数据缺失时显示 ⚠️。</div>
        <div class="single-search">
          <input type="text" id="wse-q" class="pop-in" placeholder="输入 订单号 / 手机号 / 用户名 / 网点名">
          <button type="button" class="btn" id="wse-go">查询</button>
          <button type="button" class="btn ghost" id="wse-export">导出CSV</button>
        </div>
        <div class="kpis" id="wse-kpis"></div>
        <div class="grid2">
          <div class="panel"><h3>各城市换电订单分布</h3><div id="wse-city" class="chart sm"></div></div>
          <div class="panel"><h3>订单状态占比</h3><div id="wse-status" class="chart sm"></div></div>
        </div>
        <div class="panel">
          <h3>换电订单明细（样本上限 <span id="wse-cap"></span>）</h3>
          <div class="tbl-wrap"><table id="wse-list"><thead></thead><tbody></tbody></table></div>
        </div>
      </div>

    </div>

    <!-- DEVICE -->'''
html = patch(anchor2, new2, "panel")

# ---- 3) switchSiteSub branch ----
anchor3 = '''  else if(WSUB==='salesperf'){ drawSiteSalesPerf(); }
  setTimeout(()=>window.dispatchEvent(new Event('resize')),30);'''
new3 = '''  else if(WSUB==='salesperf'){ drawSiteSalesPerf(); }
  else if(WSUB==='exchange'){ drawSiteExchange(); }
  setTimeout(()=>window.dispatchEvent(new Event('resize')),30);'''
html = patch(anchor3, new3, "switch branch")

# ---- 4a) bindSiteSub: add exchange search/export bindings ----
anchor4 = '''  const sq=document.getElementById('w-sp-q'); if(sq) sq.addEventListener('keydown',e=>{ if(e.key==='Enter'){ SPQ=sq.value; drawSiteSalesPerf(); }});
}'''
new4 = '''  const sq=document.getElementById('w-sp-q'); if(sq) sq.addEventListener('keydown',e=>{ if(e.key==='Enter'){ SPQ=sq.value; drawSiteSalesPerf(); }});
  const eq=document.getElementById('wse-q');
  if(eq) eq.addEventListener('keydown',e=>{ if(e.key==='Enter'){ drawSiteExchange(); }});
  const eg=document.getElementById('wse-go'); if(eg) eg.addEventListener('click',()=>{ drawSiteExchange(); });
  const exb=document.getElementById('wse-export'); if(exb) exb.addEventListener('click',()=>{ exportCSV('wse-list','换电订单'); });
}'''
html = patch(anchor4, new4, "bindSiteSub bindings")

# ---- 4b) drawSiteExchange function (before drawSiteList) ----
anchor5 = '''function drawSiteList(){
  const W=DATA.site||{};'''
new5 = '''function drawSiteExchange(){
  const W=DATA.site||{}, EX=(W.exchange)||[];
  const has=EX.length>0;
  const mp=v=>{ v=String(v==null?'':v); return v.length>=7? v.slice(0,3)+'****'+v.slice(-4):(v||'⚠️'); };
  const stCN=s=>({done:'已完成',completed:'已完成',abnormal:'异常',failed:'失败',refunded:'已退款',pending:'待支付',paying:'支付中'}[s]||s);
  const stTone=s=>({refunded:'red',abnormal:'amber',failed:'amber',pending:'amber',paying:'amber'}[s]||'green');
  const doneN=EX.filter(r=>r.status==='done'||r.status==='completed').length;
  const abnN=EX.filter(r=>r.status==='abnormal'||r.status==='failed').length;
  const refN=EX.filter(r=>r.status==='refunded').length;
  const rev=EX.reduce((a,b)=>a+(+b.amount||0),0);
  const sites=new Set(EX.map(r=>r.site_id||r.site_name).filter(Boolean)).size;
  kpis(document.getElementById('wse-kpis'),[
    {l:'换电订单总数', v: has? fmt(EX.length):'⚠️ 待接入'},
    {l:'已完成', v: has? fmt(doneN):'⚠️', tone:'green'},
    {l:'异常订单', v: has? fmt(abnN):'⚠️', tone:'amber'},
    {l:'换电总收入', v: has? money(rev):'⚠️'},
    {l:'退款订单', v: has? fmt(refN):'⚠️', tone:'red'},
    {l:'涉及网点', v: has? fmt(sites):'⚠️'}
  ]);
  bar('wse-city', has? Object.entries(EX.reduce((m,r)=>{const c=r.city||'未知';m[c]=(m[c]||0)+1;return m;},{})).map(([k,v])=>({name:k,value:v})):[{name:'⚠️ 待接入',value:1}], '订单数');
  pie('wse-status', has? ['done','completed','abnormal','failed','refunded','pending','paying','other'].map(s=>({name:stCN(s),value:EX.filter(r=>r.status===s).length})).filter(x=>x.value>0):[{name:'⚠️ 待接入',value:1}]);
  const ql=(document.getElementById('wse-q')||{}).value||''; const q=ql.trim().toLowerCase();
  const rows=EX.filter(r=> !q || String(r.order_id||'').toLowerCase().includes(q) || String(r.phone||'').includes(q) || String(r.user_name||'').toLowerCase().includes(q) || String(r.site_name||'').toLowerCase().includes(q));
  const cap=document.getElementById('wse-cap'); if(cap) cap.textContent=rows.length+(CAP.site?'（样本上限 '+CAP.site+'）':'');
  buildTable('wse-list',[
    {k:'order_id',h:'订单号'},{k:'user_name',h:'用户'},{k:'phone',h:'手机号',f:v=>mp(v)},
    {k:'city',h:'城市'},{k:'site_name',h:'网点'},{k:'cabinet_sn',h:'换电柜SN'},
    {k:'battery_sn',h:'电池SN'},{k:'soc_before',h:'换电前%'},{k:'soc_after',h:'换电后%'},
    {k:'swap_time',h:'换电时间'},{k:'amount',h:'费用(元)',f:v=>money(v)},
    {k:'pay_type',h:'支付方式'},{k:'status',h:'状态',f:v=>tag(stCN(v),stTone(v))}
  ], rows);
}

function drawSiteList(){
  const W=DATA.site||{};'''
html = patch(anchor5, new5, "drawSiteExchange fn")

# ---- 5) update view desc (6 -> 7 submenus) ----
anchor6 = '''      <p class="desc">网点维度总入口，含 6 个子菜单：\U0001F3EC网点总览 / \U0001F4B0网点收益收入 / ⚡网点电费 / \U0001F4CB网点列表 / \U0001F50B网点设备 / \U0001F4C8网点销售业绩。销售·用户·电费类指标基于样本明细（上限 5000/表）实时聚合，金额与逐行地址需接通生产库后精确。</p>'''
new6 = '''      <p class="desc">网点维度总入口，含 7 个子菜单：\U0001F3EC网点总览 / \U0001F4B0网点收益收入 / ⚡网点电费 / \U0001F4CB网点列表 / \U0001F50B网点设备 / \U0001F4C8网点销售业绩 / \U0001F504换电订单。销售·用户·电费·换电订单类指标基于样本明细（上限 5000/表）实时聚合，金额与逐行地址需接通生产库后精确。</p>'''
if anchor6 not in html:
    raise SystemExit("ANCHOR NOT FOUND: desc")
html = html.replace(anchor6, new6, 1)

open(P, "w", encoding="utf-8").write(html)
print("OK: site-exchange inserted")
