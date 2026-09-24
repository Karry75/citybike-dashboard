# -*- coding: utf-8 -*-
"""Round 37: 5 fixes per user request.
1) #113 优惠券板块：加醒目横幅（代码层本可显示，强化"板块存在感"）
2) #115 车辆总览 从设备看板 迁移到 用户看板（作为子菜单）
3) #116 数据总览时间维度 支持自定义日期范围
4) #114 用户总人数 随时间/筛选变化（用 U.detail 样本 + activate 过滤去重）
5) #117 用户看板 新增 押金明细表 子菜单
"""
P = r"D:\workboddy file\dudu分析\citybike_backup\html\template.html"
html = open(P, encoding="utf-8").read()

def patch(anchor, new, label):
    if anchor not in html:
        raise SystemExit("ANCHOR NOT FOUND: " + label)
    return html.replace(anchor, new, 1)

# ---------- #115 删设备看板 vehicle tab ----------
html = patch(
  '        <button type="button" class="stab" data-devsub="vehicle">\U0001F697 车辆总览</button>\n',
  '',
  "del device vehicle tab")

# ---------- #115 删设备看板 panel-dev-vehicle ----------
html = patch(
  '      <div class="devsub-panel" id="panel-dev-vehicle" style="display:none">\n'
  '        <div class="kpis" id="w-veh-kpis"></div>\n'
  '        <div class="panel"><h3>消费者车辆列表</h3><div class="tbl-wrap"><table id="w-veh-list"><thead></thead><tbody></tbody></table></div></div>\n'
  '        <div class="note">\u26a0\ufe0f 车辆数据待抽取（当前 dashboard_data.json 无车辆表）。需新增车辆表抽取脚本（依赖 ADB 白名单）。字段：车辆ID / SN / 图片 / 车架号 / 城市区域街道地址 / 协议ID / 电池数 / 电池SN / 流通记录 / 当前定位。</div>\n'
  '      </div>\n',
  '',
  "del device vehicle panel")

# ---------- #115/#117 用户看板 u-sub 加 vehicle + deposit ----------
html = patch(
  '        <button type="button" class="stab" data-usub="traj">\U0001F6E3\ufe0f 骑行轨迹</button>\n      </div>',
  '        <button type="button" class="stab" data-usub="traj">\U0001F6E3\ufe0f 骑行轨迹</button>\n'
  '        <button type="button" class="stab" data-usub="vehicle">\U0001F697 车辆总览</button>\n'
  '        <button type="button" class="stab" data-usub="deposit">\U0001F4B0 押金明细表</button>\n      </div>',
  "user tabs +vehicle+deposit")

# ---------- #115/#117 用户看板加 vehicle + deposit 面板 ----------
html = patch(
  '      </div>\n    </div>\n\n    <!-- SALES -->',
  '      </div>\n\n'
  '      <!-- 子模块6：车辆总览（从设备看板迁移） -->\n'
  '      <div class="usub-panel" id="u-sub-vehicle">\n'
  '        <div class="kpis" id="u-veh-kpis"></div>\n'
  '        <div class="panel"><h3>消费者车辆列表</h3><div class="tbl-wrap"><table id="w-veh-list"><thead></thead><tbody></tbody></table></div></div>\n'
  '        <div class="note">\u26a0\ufe0f 车辆数据待抽取（当前 dashboard_data.json 无车辆表）。需新增车辆表抽取脚本（依赖 ADB 白名单）。字段：车辆ID / SN / 图片 / 车架号 / 城市区域街道地址 / 协议ID / 电池数 / 电池SN / 流通记录 / 当前定位。</div>\n'
  '      </div>\n\n'
  '      <!-- 子模块7：押金明细表 -->\n'
  '      <div class="usub-panel" id="u-sub-deposit">\n'
  '        <div class="kpis" id="u-dep-kpis"></div>\n'
  '        <div class="panel"><h3>押金明细表（样本上限 <span id="u-dep-cap"></span>）</h3><div class="tbl-wrap"><table id="w-dep-list"><thead></thead><tbody></tbody></table></div></div>\n'
  '        <div class="note">\u26a0\ufe0f 押金明细数据待接通数据库抽取（押金表）；当前为字段规划预览。</div>\n'
  '      </div>\n\n    </div>\n\n    <!-- SALES -->',
  "user panels vehicle+deposit")

# ---------- #116 period-bar 加自定义按钮 ----------
html = patch(
  '        <span class="period-btn" data-period="year">本年</span>\n      </div>',
  '        <span class="period-btn" data-period="year">本年</span>\n'
  '        <span class="period-btn" data-period="custom">自定义</span>\n      </div>',
  "period custom btn")

# ---------- #116 period 弹窗 HTML ----------
html = patch(
  '      <div id="ov-banner" class="ov-banner"></div>\n\n      <!-- ===== 用户板块 ===== -->',
  '      <div id="ov-banner" class="ov-banner"></div>\n'
  '      <div class="pop-daterange" id="ov-daterange" style="display:none">\n'
  '        <div class="dr-row"><span>\u8d77</span><input type="date" class="pop-date" id="ov-date-from"></div>\n'
  '        <div class="dr-row"><span>\u6b62</span><input type="date" class="pop-date" id="ov-date-to"></div>\n'
  '        <div class="dr-btns"><button class="pop-apply-range" id="ov-apply-range">\u5e94\u7528</button><button class="pop-clear-range" id="ov-clear-range">\u6e05\u9664</button></div>\n'
  '      </div>\n\n      <!-- 用户板块 -->',
  "period popup html")

# ---------- #113 优惠券 overview 横幅 ----------
html = patch(
  '      <div class="coupsub-panel" id="panel-coup-overview">\n        <div class="kpis" id="cp-over-kpis"></div>',
  '      <div class="coupsub-panel" id="panel-coup-overview">\n'
  '        <div class="data-todo-banner">\u26a0\ufe0f 优惠券数据待接通数据库抽取（coupon 相关表）；当前为框架演示，下列 KPI / 图表 / 明细均为占位。导航入口在左侧「业务域 · 优惠券看板」。</div>\n'
  '        <div class="kpis" id="cp-over-kpis"></div>',
  "coupon banner")

# ---------- #116 CUSTOM 全局变量 ----------
html = patch(
  "let OV_PERIOD = 'total';",
  "let OV_PERIOD = 'total';\nlet CUSTOM_FROM='', CUSTOM_TO='';",
  "custom globals")

# ---------- #116 ovPeriodRange 加 custom 分支 ----------
html = patch(
  "  if(p==='year'){ return [y+'-01-01', y+'-12-31']; }\n  return ['1970-01-01','2999-12-31'];",
  "  if(p==='year'){ return [y+'-01-01', y+'-12-31']; }\n"
  "  if(p==='custom'){ return [CUSTOM_FROM||'1970-01-01', CUSTOM_TO||'2999-12-31']; }\n"
  "  return ['1970-01-01','2999-12-31'];",
  "ovPeriodRange custom")

# ---------- #116 bindPeriodBar：custom 点击 + 弹窗绑定 ----------
html = patch(
  "      bar.querySelectorAll('.period-btn').forEach(b=>b.classList.remove('active'));\n"
  "      btn.classList.add('active');\n"
  "      OV_PERIOD=btn.dataset.period;\n"
  "      applyOverview(state.overview||{});\n"
  "    });\n"
  "})();",
  "      const p=btn.dataset.period;\n"
  "      if(p==='custom'){ const dr=document.getElementById('ov-daterange'); if(dr) dr.style.display=(dr.style.display==='none'||!dr.style.display)?'flex':'none'; return; }\n"
  "      bar.querySelectorAll('.period-btn').forEach(b=>b.classList.remove('active'));\n"
  "      btn.classList.add('active');\n"
  "      OV_PERIOD=p; applyOverview(state.overview||{});\n"
  "    });\n"
  "    const ova=document.getElementById('ov-apply-range'); if(ova) ova.onclick=()=>{\n"
  "      const f=document.getElementById('ov-date-from').value, t=document.getElementById('ov-date-to').value;\n"
  "      if(!f||!t){ if(window.alert)alert('\u8bf7\u9009\u62e9\u8d77\u6b62\u65e5\u671f'); return; }\n"
  "      CUSTOM_FROM=f; CUSTOM_TO=t; OV_PERIOD='custom';\n"
  "      document.querySelectorAll('.period-btn').forEach(b=>b.classList.toggle('active', b.dataset.period==='custom'));\n"
  "      const dr=document.getElementById('ov-daterange'); if(dr)dr.style.display='none';\n"
  "      applyOverview(state.overview||{});\n"
  "    };\n"
  "    const ovc=document.getElementById('ov-clear-range'); if(ovc) ovc.onclick=()=>{\n"
  "      CUSTOM_FROM=''; CUSTOM_TO=''; OV_PERIOD='total';\n"
  "      document.querySelectorAll('.period-btn').forEach(b=>b.classList.toggle('active', b.dataset.period==='total'));\n"
  "      const dr=document.getElementById('ov-daterange'); if(dr)dr.style.display='none';\n"
  "      applyOverview(state.overview||{});\n"
  "    };\n"
  "})();",
  "bindPeriodBar custom+popup")

# ---------- #114 用户总人数 随时间/筛选变化 ----------
html = patch(
  "  const userCnt = cityF? cnt(U.detail,'city') : OV.user_total;",
  "  const timeF = OV_PERIOD!=='total';\n"
  "  const _us=(U.detail||[]).filter(r=>{\n"
  "    if(cityF && !eq(r.city,cityF)) return false;\n"
  "    if(timeF){ const a=(r.activate||'').slice(0,10); if(!a||a<pFrom||a>pTo) return false; }\n"
  "    return true;\n"
  "  });\n"
  "  const userCnt = (cityF||timeF)? new Set(_us.map(r=>r.phone||r.name||r.protocol_id)).size : OV.user_total;",
  "userCnt fix")

# ---------- #114 kpCard sub 文案 ----------
html = patch(
  "sub:cityF?('样本·全量 '+fmt(OV.user_total)):'全量·累计'",
  "sub:(cityF||timeF)?('样本·'+(timeF?pLab:'城市')+' '+fmt(OV.user_total)):'全量·累计'",
  "userCnt sub")

# ---------- #115/#117 switchUserSub 分支 ----------
html = patch(
  "  const panel=document.getElementById('u-sub-'+USUB);\n  if(panel) panel.classList.add('active');",
  "  const panel=document.getElementById('u-sub-'+USUB); if(panel)panel.classList.add('active');\n"
  "  if(USUB==='vehicle') return drawUserVehicle(state.user||{});\n"
  "  if(USUB==='deposit') return drawUserDeposit(state.user||{});",
  "switchUserSub branches")

# ---------- #115 applyDevice 删 vehicle 分支 ----------
html = patch(
  "  if(sub==='vehicle') return drawDevVehicle(f);\n",
  "",
  "del applyDevice vehicle")

# ---------- #115 drawDevVehicle -> drawUserVehicle ----------
html = patch(
  "function drawDevVehicle(f){\n  kpis(document.getElementById('w-veh-kpis'),[\n"
  "    {l:'车辆总数',v:'\u26a0\ufe0f',s:'待抽 车辆表'},\n"
  "    {l:'在租车辆',v:'\u26a0\ufe0f',s:'待抽 生效协议车辆'},\n"
  "    {l:'离线/失联车辆',v:'\u26a0\ufe0f',s:'待抽 网络状态'}\n"
  "  ]);\n  renderRows('w-veh-list', []);\n}",
  "function drawUserVehicle(f){\n"
  "  const V=(DATA.user&&DATA.user.vehicle)||(DATA.device&&DATA.device.vehicle)||[];\n"
  "  const has=V.length>0;\n"
  "  kpis(document.getElementById('u-veh-kpis'),[\n"
  "    {l:'车辆总数',v:has?fmt(V.length):'\u26a0\ufe0f',s:has?'':'待抽 车辆表'},\n"
  "    {l:'在租车辆',v:'\u26a0\ufe0f',s:'待抽 生效协议车辆'},\n"
  "    {l:'离线/失联',v:'\u26a0\ufe0f',s:'待抽 网络状态'}\n"
  "  ]);\n"
  "  renderRows('w-veh-list', V.map(r=>({\n"
  "    vid:r.vid||r.vehicle_id, sn:r.sn, img:r.img?'\U0001F4F7':'', frame:r.frame, addr:r.addr,\n"
  "    agreement:r.agreement, bat_cnt:r.bat_cnt, bat_sn:r.bat_sn, flow:r.flow, loc:r.loc\n"
  "  })));\n}\n"
  "\n// 用户看板·押金明细表\n"
  "function drawUserDeposit(f){\n"
  "  const D=(DATA.user&&DATA.user.deposit)||[];\n"
  "  const has=D.length>0;\n"
  "  kpis(document.getElementById('u-dep-kpis'),[\n"
  "    {l:'押金记录数',v:has?fmt(D.length):'\u26a0\ufe0f',s:has?'':'待抽 押金表'},\n"
  "    {l:'押金总额(元)',v:has?money(D.reduce((a,b)=>a+(+b.deposit_fee||0),0)):'\u26a0\ufe0f',s:has?'':'待抽'},\n"
  "    {l:'已退还',v:has?fmt(D.filter(r=>r.status==='refunded'||r.status==='returned').length):'\u26a0\ufe0f',s:has?'':'待抽'},\n"
  "    {l:'待退还',v:has?fmt(D.filter(r=>r.status==='pending'||r.status==='unreturned').length):'\u26a0\ufe0f',s:has?'':'待抽'}\n"
  "  ]);\n"
  "  buildTable('w-dep-list',[\n"
  "    {k:'agreement_id',h:'协议ID'},{k:'phone',h:'手机号',f:v=>maskPhone(v)},\n"
  "    {k:'name',h:'姓名'},{k:'city',h:'城市'},{k:'site',h:'签约网点'},\n"
  "    {k:'package',h:'套餐'},{k:'deposit_fee',h:'押金(元)',f:v=>money(v)},\n"
  "    {k:'status',h:'押金状态',f:v=>tag(v||'\u2014','gray')},\n"
  "    {k:'pay_time',h:'支付时间'},{k:'refund_status',h:'退款状态'},\n"
  "    {k:'refund_time',h:'退款时间'}\n"
  "  ], D);\n"
  "  const cap=document.getElementById('u-dep-cap'); if(cap)cap.textContent=D.length?('（'+D.length+'）'):'';\n}",
  "drawUserVehicle+Deposit")

open(P, "w", encoding="utf-8").write(html)
print("OK: all patches applied")
