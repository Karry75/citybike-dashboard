# -*- coding: utf-8 -*-
"""人员看板 · 分成金额真实接入：把 5 类实体的 ⚠️ 占位替换为真实数据。
依赖 extract_personnel_share.py 写入的 DATA.personnel.share。
策略：emoji-free 部分用精确字符串替换；含 ⚠️ 的占位单元格用正则(避免硬编码 emoji 字形差异)。
"""
import io, os, re
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TPL = os.path.join(ROOT, 'html', 'template.html')
with io.open(TPL, 'r', encoding='utf-8') as f:
    s = f.read()

# ---- 1) desc ----
OLD = '<p class="desc">按 代理商 / 渠道商 / 代理商员工 / 商户 / 导购 维度总览其名下网点状态与签约用户（用户数已按 user_id 去重）。点击行内「跳转」可联动用户看板；「分成金额」⚠️ 待接入来源。</p>'
NEW = '<p class="desc">按 代理商 / 渠道商 / 代理商员工 / 商户 / 导购 维度总览其名下网点状态与签约用户（用户数已按 user_id 去重）。点击行内「跳转」可联动用户看板；「分成」已按实体真实映射接入：代理商=费用方案、渠道商=四级比例、商户=推广/销售返利、导购=分享数+订单返利、员工=继承代理商方案。</p>'
assert OLD in s, 'desc not found'
s = s.replace(OLD, NEW, 1)

# ---- 2) agency 面板增加方案子面板 ----
OLD = '''        <div class="panel"><h3>选中代理商 · 用户 / 协议明细（样本上限 <span id="pe-agency-scap"></span>）</h3><div class="tbl-wrap"><table id="pe-agency-sample"><thead></thead><tbody></tbody></table></div></div>
      </div>'''
NEW = '''        <div class="panel"><h3>选中代理商 · 用户 / 协议明细（样本上限 <span id="pe-agency-scap"></span>）</h3><div class="tbl-wrap"><table id="pe-agency-sample"><thead></thead><tbody></tbody></table></div></div>
        <div class="panel"><h3>选中代理商 · 费用分成方案（来自 t_exchange_fee_scheme，经 t_site.scheme_id 归集）</h3><div class="tbl-wrap"><table id="pe-agency-share"><thead></thead><tbody></tbody></table></div></div>
      </div>'''
assert OLD in s, 'agency panel sample block not found'
s = s.replace(OLD, NEW, 1)

# ---- 3) 3 个 banner 改为真实口径说明 ----
b1 = ('<div class="note hl">★ 分成金额 ⚠️ 占位待接入来源（代理商员工分成为独立核算字段，当前看板未接入）。</div>',
       '<div class="note hl">★ 分成方案：代理商员工继承其所属代理商的费用分成方案（见下方「代理商总览」的方案明细）。</div>')
b2 = ('<div class="note hl">★ 分成金额 ⚠️ 占位待接入来源（商户分成为独立核算字段，当前看板未接入）。</div>',
       '<div class="note hl">★ 分成（返利）：推广返利 / 销售返利来自商品站点关系（t_goods_site_relation），单位元（库内分÷100）。</div>')
b3 = ('<div class="note hl">★ 分成金额 ⚠️ 占位待接入来源（导购分成为独立核算字段，当前看板未接入）。</div>',
       '<div class="note hl">★ 分成：分享次数来自 t_promoter；订单推广/销售返利来自商品订单（按 maker_id 关联导购）。</div>')
for o, n in (b1, b2, b3):
    assert o in s, 'banner not found: ' + o[:20]
    s = s.replace(o, n, 1)

# ---- 4) 注入 peShareStr 助手（在 drawPersonnelOv 之前）----
ANCHOR = 'function drawPersonnelOv(sub){'
assert ANCHOR in s, 'drawPersonnelOv anchor not found'
HELPER = '''function peShareStr(t,id){
  var S=(DATA.personnel&&DATA.personnel.share)||{}; var m=(S[t]||{})[String(id)];
  if(!m) return '—';
  if(t==='distributor'){ return '一'+fmt(m.first)+'% · 二'+fmt(m.second)+'% · 三'+fmt(m.third)+'% · 邀'+fmt(m.third_inviter)+'%'; }
  if(t==='merchant'){ return '推广¥'+fmt(m.promote)+' / 销售¥'+fmt(m.sale); }
  if(t==='promoter'){ return '分享'+fmt(m.share_count)+'次 · 返利¥'+fmt(Math.round((m.rebate_promote+m.rebate_sale)*100)/100); }
  if(t==='agency_emp'){ return '继承代理商方案('+(m.length||0)+'套)'; }
  if(t==='agency'){ return (m.length||0)+'套方案'; }
  return '—';
}
'''
s = s.replace(ANCHOR, HELPER + ANCHOR, 1)

# ---- 5) agency 分支：加「分成方案」列 + 方案面板 ----
OLD_A_ROW = '''    var rows=arr.map(function(e){return ['<button class="btn btn-ghost pe-sel" data-sub="agency" data-id="'+e.id+'">'+peEsc(e.name)+'</button>',peSites(e.sites),fmt(e.users.total),fmt(e.users.working),fmt(e.users.owe),fmt(e.users.cancel),fmt(e.users.terminate),'<button class="btn pe-jump" data-type="agency" data-key="'+e.id+'">跳转用户列表</button>'];});'''
NEW_A_ROW = '''    var rows=arr.map(function(e){return ['<button class="btn btn-ghost pe-sel" data-sub="agency" data-id="'+e.id+'">'+peEsc(e.name)+'</button>',peSites(e.sites),fmt(e.users.total),fmt(e.users.working),fmt(e.users.owe),fmt(e.users.cancel),fmt(e.users.terminate),peShareStr('agency',e.id),'<button class="btn pe-jump" data-type="agency" data-key="'+e.id+'">跳转用户列表</button>'];});'''
assert OLD_A_ROW in s, 'agency row not found'
s = s.replace(OLD_A_ROW, NEW_A_ROW, 1)

OLD_A_TBL = "    peTable('pe-agency-detail',['代理商','网点数(营业中/关闭)','签约总','生效','欠租','退订','协议终止','操作'],rows);"
NEW_A_TBL = "    peTable('pe-agency-detail',['代理商','网点数(营业中/关闭)','签约总','生效','欠租','退订','协议终止','分成方案','操作'],rows);"
assert OLD_A_TBL in s, 'agency peTable not found'
s = s.replace(OLD_A_TBL, NEW_A_TBL, 1)

OLD_A_SAMPLE = "    peRenderSample('pe-agency-sample','pe-agency-scap',arr,PE_SEL.agency);"
NEW_A_SAMPLE = '''    peRenderSample('pe-agency-sample','pe-agency-scap',arr,PE_SEL.agency);
    var asel=(arr||[]).filter(function(e){return String(e.id)===String(PE_SEL.agency);})[0];
    var ash=(asel&&(DATA.personnel.share||{}).agency)?((DATA.personnel.share).agency)[String(asel.id)]||[]:[];
    peTable('pe-agency-share',['方案ID','方案名','基础费(元)','电费(元)·比例%','服务费(元)·比例%','设备费(元)·比例%','单费(元)','状态'],
      ash.map(function(x){return [x.scheme_id,peEsc(x.name),fmt(x.fee),fmt(x.electric_fee)+'·'+fmt(x.electric_fee_ratio),fmt(x.service_fee)+'·'+fmt(x.service_fee_ratio),fmt(x.device_fee)+'·'+fmt(x.device_fee_ratio),fmt(x.unit_fee),x.status];}));'''
assert OLD_A_SAMPLE in s, 'agency sample render not found'
s = s.replace(OLD_A_SAMPLE, NEW_A_SAMPLE, 1)

# ---- 6) distributor 分支：加「分成比例」列 ----
OLD_D_ROW = '''    var rows=arr.map(function(e){return ['<button class="btn btn-ghost pe-sel" data-sub="distributor" data-id="'+e.id+'">'+peEsc(e.name)+'</button>',(e.agency_id?('代理商#'+e.agency_id):'—'),peSites(e.sites),fmt(e.users.total),fmt(e.users.working),fmt(e.users.owe),fmt(e.users.cancel),fmt(e.users.terminate),'<button class="btn pe-jump" data-type="distributor" data-key="'+e.id+'">跳转用户列表</button>'];});'''
NEW_D_ROW = '''    var rows=arr.map(function(e){return ['<button class="btn btn-ghost pe-sel" data-sub="distributor" data-id="'+e.id+'">'+peEsc(e.name)+'</button>',(e.agency_id?('代理商#'+e.agency_id):'—'),peSites(e.sites),fmt(e.users.total),fmt(e.users.working),fmt(e.users.owe),fmt(e.users.cancel),fmt(e.users.terminate),peShareStr('distributor',e.id),'<button class="btn pe-jump" data-type="distributor" data-key="'+e.id+'">跳转用户列表</button>'];});'''
assert OLD_D_ROW in s, 'distributor row not found'
s = s.replace(OLD_D_ROW, NEW_D_ROW, 1)

OLD_D_TBL = "    peTable('pe-dist-detail',['渠道商','所属代理商','网点数(营业中/关闭)','签约总','生效','欠租','退订','协议终止','操作'],rows);"
NEW_D_TBL = "    peTable('pe-dist-detail',['渠道商','所属代理商','网点数(营业中/关闭)','签约总','生效','欠租','退订','协议终止','分成比例(一/二/三/邀)','操作'],rows);"
assert OLD_D_TBL in s, 'distributor peTable not found'
s = s.replace(OLD_D_TBL, NEW_D_TBL, 1)

# ---- 7) 三个含 ⚠️ 的占位单元格：用正则替换（不硬编码 emoji）----
# agency_emp / merchant / promoter 行：fmt(e.users.terminate),'任意分成待接入', -> peShareStr(...)
s = re.sub(r"fmt\(e\.users\.terminate\),'[^']*分成待接入',",
            "fmt(e.users.terminate),peShareStr('agency_emp',e.employee_id),", s)
s = re.sub(r"fmt\(e\.users\.terminate\),'[^']*分成待接入',",
            "fmt(e.users.terminate),peShareStr('merchant',e.id),", s)
s = re.sub(r"fmt\(e\.users\.terminate\),'[^']*分成待接入',",
            "fmt(e.users.terminate),peShareStr('promoter',e.id),", s)
# 同步更新这三张表的表头（无 emoji，精确替换）
s = s.replace("peTable('pe-emp-detail',['员工','所属代理商','关联商户','网点数(营业中/关闭)','签约总','生效','欠租','退订','协议终止','分成金额','操作'],rows);",
                "peTable('pe-emp-detail',['员工','所属代理商','关联商户','网点数(营业中/关闭)','签约总','生效','欠租','退订','协议终止','分成方案','操作'],rows);", 1)
s = s.replace("peTable('pe-mch-detail',['商户','所属代理商','网点数(营业中/关闭)','签约总','生效','欠租','退订','协议终止','分成金额','操作'],rows);",
                "peTable('pe-mch-detail',['商户','所属代理商','网点数(营业中/关闭)','签约总','生效','欠租','退订','协议终止','分成(推广/销售返利)','操作'],rows);", 1)
s = s.replace("peTable('pe-pro-detail',['导购','所属代理商','手机号','签约总','生效','欠租','退订','协议终止','分成金额','操作'],rows);",
                "peTable('pe-pro-detail',['导购','所属代理商','手机号','签约总','生效','欠租','退订','协议终止','分成(分享/返利)','操作'],rows);", 1)

with io.open(TPL, 'w', encoding='utf-8') as f:
    f.write(s)
print('PATCH OK: 分成金额真实接入（5 实体 + 代理商方案面板）')
