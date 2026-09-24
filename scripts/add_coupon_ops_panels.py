#!/usr/bin/env python3
"""
第33轮：新增优惠券板块(6子菜单) + 设备资产扩展(3子菜单) + 运维看板重写(4子菜单)
对 template.html 做精确插入改造
"""
import re

TEMPLATE = r'D:\workboddy file\dudu分析\citybike_backup\html\template.html'

with open(TEMPLATE, 'r', encoding='utf-8') as f:
    html = f.read()

# ============================================================
# 1. 导航栏：在 device 和 ops 之间插入 coupon 导航项
# ============================================================
nav_ops = '''    <div class="navitem" data-v="ops">'''
html = html.replace(
    nav_ops,
    '''    <div class="navitem" data-v="coupon">
      <svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 12v6a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h6"/><path d="m14 7-3 3"/><path d="m18 11-3 3"/><path d="m9.5 13.5 3 3"/><path d="m7 17 3-3"/></svg>
      <span>优惠券看板</span></div>
''' + nav_ops
)

# ============================================================
# 2. 设备资产看板：在 dispatch 后追加3个子菜单按钮 + 3个面板
# ============================================================
old_dev_tabs = '''        <button type="button" class="stab" data-devsub="dispatch">📊 区域电池调度分析</button>
      </div>
      <div class="filterbar" id="fb-device"></div>'''

new_dev_tabs = '''        <button type="button" class="stab" data-devsub="dispatch">📊 区域电池调度分析</button>
        <button type="button" class="stab" data-devsub="inventory">📦 设备出入库管理</button>
        <button type="button" class="stab" data-devsub="fault">⚠️ 故障设备管理</button>
        <button type="button" class="stab" data-devsub="transfer">🔄 设备调拨记录</button>
      </div>
      <div class="filterbar" id="fb-device"></div>'''

html = html.replace(old_dev_tabs, new_dev_tabs)

# 在 panel-dev-dispatch 结束后、</div>(v-device结束)前 插入3个新面板
old_dispatch_end = '''      </div>
    </div>

    <!-- OPS -->'''

new_panels = '''      </div>

      <!-- 10 设备出入库管理 -->
      <div class="devsub-panel" id="panel-dev-inventory" style="display:none">
        <div class="kpis" id="w-inv-kpis"></div>
        <div class="toolbar" style="margin:8px 0">
          <button type="btn sm" id="btn-batch-in" class="btn sm">📥 批量入库</button>
          <button type="btn sm" id="btn-batch-out" class="btn sm">📤 批量出库</button>
          <span style="flex:1"></span>
          <button type="button" class="btn sm" id="btn-export-inv">导出</button>
        </div>
        <div class="panel">
          <h3>设备出入库列表（换电柜 / 电池）</h3>
          <div class="tbl-wrap"><table id="w-inv-list"><thead></thead><tbody></tbody></table></div>
        </div>
        <div class="note">⚠️ 数据待连接数据库后抽取（设备出入库表）；支持换电柜/电池批量入库出库操作。</div>
      </div>

      <!-- 11 故障设备管理 -->
      <div class="devsub-panel" id="panel-dev-fault" style="display:none">
        <div class="kpis" id="w-fault-kpis"></div>
        <div class="panel">
          <h3>故障设备仓库列表</h3>
          <div class="tbl-wrap"><table id="w-fault-list"><thead></thead><tbody></tbody></table></div>
        </div>
        <div class="note">⚠️ 数据待连接数据库后抽取；用于存放损坏的换电柜和电池。</div>
      </div>

      <!-- 12 设备调拨记录 -->
      <div class="devsub-panel" id="panel-dev-transfer" style="display:none">
        <div class="single-search" style="margin:6px 0">
          <input type="text" id="tf-q-op" placeholder="操作人ID/名称" />
          <select id="tf-f-type"><option value="">操作类型（全部）</option><option value="入库">入库</option><option value="出库">出库</option><option value="调拨">调拨</option><option value="回收">回收</option></select>
          <select id="tf-f-dtype"><option value="">设备类型（全部）</option><option value="换电柜">换电柜</option><option value="电池">电池</option></select>
          <input type="text" id="tf-q-start" placeholder="开始时间" />
          <input type="text" id="tf-q-end" placeholder="结束时间" />
          <button type="button" class="btn" id="tf-search-btn">🔍 搜索</button>
          <button type="button" class="btn btn-ghost" id="btn-export-tf">📥 导出</button>
        </div>
        <div class="panel">
          <h3>设备出入库调拨回收记录<span id="tf-count"></span></h3>
          <div class="tbl-wrap"><table id="w-tf-list"><thead></thead><tbody></tbody></table></div>
        </div>
        <div class="note">⚠️ 数据待连接数据库后抽取；含操作人ID/名称/时间、设备类型/ID、操作类型、运营结果、流出/流入对象。</div>
      </div>
    </div>

    <!-- OPS -->'''

html = html.replace(old_dispatch_end, new_panels)

# ============================================================
# 3. 新增 #v-coupon 优惠券看板（插在 v-device 之后、OPS之前）
# ============================================================
coupon_html = '''
    <!-- COUPON -->
    <div class="view" id="v-coupon">
      <h2 class="title">优惠券看板</h2>
      <p class="desc">优惠券全生命周期管理：总览KPI · 发券统计 · 领券中心资源 · 用户明细。按优惠券类型/状态/时间联动筛选。</p>
      <div class="subtabs" id="coup-sub">
        <button type="button" class="stab active" data-coupsub="overview">📊 优惠券总览</button>
        <button type="button" class="stab" data-coupsub="agent-issue">🏢 代理商发券统计</button>
        <button type="button" class="stab" data-coupsub="merchant-issue">🏪 商户端发券统计</button>
        <button type="button" class="stab" data-coupsub="contract-purchase">📋 合约份额采购统计</button>
        <button type="button" class="stab" data-coupsub="user-detail">👤 用户优惠券明细</button>
        <button type="button" class="stab" data-coupsub="resource">🎫 优惠券资源（领券中心）</button>
      </div>
      <div class="filterbar" id="fb-coupon"></div>

      <!-- C1 优惠券总览 -->
      <div class="coupsub-panel" id="panel-coup-overview">
        <div class="kpis" id="cp-over-kpis"></div>
        <div class="grid2">
          <div class="panel"><h3>各优惠券状态占比（全量）</h3><div id="cp-status-pie" class="chart sm"></div></div>
          <div class="panel"><h3>各优惠券购买数量分布（TOP15）</h3><div id="cp-buy-bar" class="chart sm"></div></div>
        </div>
        <div class="grid2">
          <div class="panel"><h3>购买优惠券最多的门店 TOP5</h3><div id="cp-top-site" class="chart sm"></div></div>
          <div class="panel"><h3>购买优惠券最多的商户 TOP5</h3><div id="cp-top-merchant" class="chart sm"></div></div>
        </div>
        <div class="panel">
          <h3>各优惠券购买明细汇总<span id="cp-count"></span></h3>
          <div class="tbl-wrap"><table id="cp-over-list"><thead></thead><tbody></tbody></table></div>
        </div>
        <div class="note">⚠️ 数据待连接数据库后抽取（优惠券相关表）；当前为框架演示。</div>
      </div>

      <!-- C2 代理商发券统计 -->
      <div class="coupsub-panel" id="panel-coup-agent-issue" style="display:none">
        <div class="filterbar" style="margin-bottom:12px">
          <div class="fb-row">
            <div class="fitem"><label>发放人</label><select id="cpai-f-issuer"><option value="">请选择</option></select></div>
            <div class="fitem"><label>签约网点</label><select id="cpai-f-site"><option value="">请选择</option></select></div>
            <div class="fitem"><label>代理商</label><select id="cpai-f-agent"><option value="">请选择</option></select></div>
            <div class="fitem"><label>使用状态</label><select id="cpai-f-usestatus"><option value="">全部</option><option value="已使用">已使用</option><option value="未使用">未使用</option></select></div>
            <div class="fitem"><label>电池产品</label><select id="cpai-f-batprod"><option value="">请选择</option></select></div>
          </div>
          <div class="fb-row">
            <div class="fitem"><label>用户信息</label><select id="cpai-f-userinfo"><option value="">请选择</option></select></div>
            <div class="fitem"><label>付款状态</label><select id="cpai-f-paystatus"><option value="">全部</option><option value="已付款">已付款</option><option value="未付款">未付款</option></select></div>
            <div class="fitem"><label>发放时间</label>
              <input type="date" id="cpai-f-start" /> ~ <input type="date" id="cpai-f-end" />
            </div>
            <div class="hit" id="cpai-hit"></div>
            <button type="button" class="btn" id="cpai-search-btn">🔍 搜索</button>
            <button type="button" class="btn btn-ghost" id="cpai-reset-btn">⟲ 重置</button>
            <button type="button" class="btn btn-ghost" id="btn-export-cpai">📥 导出</button>
          </div>
        </div>
        <div class="panel">
          <div class="phead"><h3>代理商发券统计表<span id="cpai-count"></span></h3></div>
          <div class="tbl-wrap"><table id="cpai-list"><thead></thead><tbody></tbody></table></div>
        </div>
        <div class="note">⚠️ 数据待连接数据库后抽取；筛选条件：发放人/签约网点/代理商/使用状态/电池产品/用户信息/付款状态/发放时间。</div>
      </div>

      <!-- C3 商户端发券统计 -->
      <div class="coupsub-panel" id="panel-coup-merchant-issue" style="display:none">
        <div class="coup-tabs" style="margin:8px 0">
          <button type="button" class="stab active" id="cptab-redeem" onclick="switchCpMerchantTab('redeem')">兑换码中心</button>
          <button type="button" class="stab" id="cptab-purchase" onclick="switchCpMerchantTab('purchase')">兑换码购买记录</button>
        </div>
        <div class="filterbar" style="margin-bottom:12px">
          <div class="fb-row">
            <div class="fitem"><label>兑换码</label><input type="text" id="cpmi-f-code" placeholder="请输入" /></div>
            <div class="fitem"><label>订单ID</label><input type="text" id="cpmi-f-orderid" placeholder="请输入" /></div>
            <div class="fitem"><label>用户信息</label><select id="cpmi-f-user"><option value="">请选择</option></select></div>
            <div class="fitem"><label>兑换码id</label><input type="text" id="cpmi-f-codeid" placeholder="请输入" /></div>
          </div>
          <div class="fb-row">
            <div class="fitem"><label>订单类型</label><select id="cpmi-f-ordertype"><option value="">全部</option></select></div>
            <div class="fitem"><label>商户信息</label><select id="cpmi-f-merchant"><option value="">请选择</option></select></div>
            <div class="fitem"><label>是否兑换</label><select id="cpai-f-redeemed"><option value="">全部</option><option value="是">是</option><option value="否">否</option></select></div>
            <div class="fitem"><label>是否发货</label><select id="cpmi-f-shipped"><option value="">全部</option><option value="是">是</option><option value="否">否</option></select></div>
            <div class="fitem"><label>是否支付</label><select id="cpmi-f-paid"><option value="">全部</option><option value="是">是</option><option value="否">否</option></select></div>
          </div>
          <div class="fb-row">
            <div class="fitem"><label>是否退款</label><select id="cpmi-f-refund"><option value="">全部</option><option value="是">是</option><option value="否">否</option></select></div>
            <div class="fitem"><label>是否作废</label><select id="cpmi-f-cancel"><option value="">全部</option><option value="是">是</option><option value="否">否</option></select></div>
            <div class="fitem"><label>是否使用</label><select id="cpmi-f-used"><option value="">全部</option><option value="是">是</option><option value="否">否</option></select></div>
            <div class="fitem"><label>优惠券信息</label><select id="cpmi-f-coupon"><option value="">请选择</option></select></div>
            <div class="fitem"><label>创建时间</label>
              <input type="date" id="cpmi-f-cstart" /> ~ <input type="date" id="cpmi-f-cend" />
            </div>
          </div>
          <div class="fb-row">
            <div class="fitem"><label>兑换时间</label>
              <input type="date" id="cpmi-f-rstart" /> ~ <input type="date" id="cpmi-f-rend" />
            </div>
            <div class="fitem"><label>支付时间</label>
              <input type="date" id="cpmi-f-pstart" /> ~ <input type="date" id="cpmi-f-pend" />
            </div>
            <div class="hit" id="cpmi-hit"></div>
            <button type="button" class="btn" id="cpmi-search-btn">🔍 搜索</button>
            <button type="button" class="btn btn-ghost" id="cpmi-reset-btn">⟲ 重置</button>
            <button type="button" class="btn btn-ghost" id="btn-export-cpmi">📥 导出</button>
          </div>
        </div>
        <div class="panel">
          <div class="phead"><h3>商户端发券统计表<span id="cpmi-count"></span></h3></div>
          <div class="tbl-wrap"><table id="cpmi-list"><thead></thead><tbody></tbody></table></div>
        </div>
        <div class="note">⚠️ 数据待连接数据库后抽取；含兑换码中心/购买记录双tab。</div>
      </div>

      <!-- C4 合约份额采购统计 -->
      <div class="coupsub-panel" id="panel-coup-contract-purchase" style="display:none">
        <div class="kpis" id="cppc-kpis"></div>
        <div class="panel">
          <h3>合约份额采购统计<span id="cppc-count"></span></h3>
          <div class="tbl-wrap"><table id="cppc-list"><thead></thead><tbody></tbody></table></div>
        </div>
        <div class="note">⚠️ 数据待连接数据库后抽取。</div>
      </div>

      <!-- C5 用户优惠券明细 -->
      <div class="coupsub-panel" id="panel-coup-user-detail" style="display:none">
        <div class="filterbar" style="margin-bottom:12px">
          <div class="fb-row">
            <div class="fitem"><label>发放人</label><select id="cpud-f-issuer"><option value="">请选择</option></select></div>
            <div class="fitem"><label>签约网点</label><select id="cpud-f-site"><option value="">请选择</option></select></div>
            <div class="fitem"><label>代理商</label><select id="cpud-f-agent"><option value="">请选择</option></select></div>
            <div class="fitem"><label>使用状态</label><select id="cpud-f-usestatus"><option value="">全部</option><option value="已使用">已使用</option><option value="未使用">未使用</option></select></div>
            <div class="fitem"><label>电池产品</label><select id="cpud-f-batprod"><option value="">请选择</option></select></div>
          </div>
          <div class="fb-row">
            <div class="fitem"><label>用户信息</label><select id="cpud-f-userinfo"><option value="">请选择</option></select></div>
            <div class="fitem"><label>付款状态</label><select id="cpud-f-paystatus"><option value="">全部</option><option value="已付款">已付款</option><option value="未付款">未付款</option></select></div>
            <div class="fitem"><label>发放时间</label>
              <input type="date" id="cpud-f-start" /> ~ <input type="date" id="cpud-f-end" />
            </div>
            <div class="hit" id="cpud-hit"></div>
            <button type="button" class="btn" id="cpud-search-btn">🔍 搜索</button>
            <button type="button" class="btn btn-ghost" id="cpud-reset-btn">⟲ 重置</button>
            <button type="button" class="btn btn-ghost" id="btn-export-cpud">📥 导出</button>
          </div>
        </div>
        <div class="panel">
          <div class="phead"><h3>用户优惠券明细表<span id="cpud-count"></span></h3></div>
          <div class="tbl-wrap"><table id="cpud-list"><thead></thead><tbody></tbody></table></div>
        </div>
        <div class="note">⚠️ 数据待连接数据库后抽取；字段同代理商发券统计（发放人/网点/代理/状态/产品/用户/付款/时间）。</div>
      </div>

      <!-- C6 优惠券资源（领券中心） -->
      <div class="coupsub-panel" id="panel-coup-resource" style="display:none">
        <div class="toolbar" style="margin:8px 0">
          <button type="button" class="btn sm" id="btn-add-cpres">＋ 添加资源</button>
        </div>
        <div class="filterbar" style="margin-bottom:12px">
          <div class="fb-row">
            <div class="fitem"><label>资源ID</label><input type="text" id="cpr-f-id" placeholder="请输入" /></div>
            <div class="fitem"><label>城市区域</label><select id="cpr-f-city"><option value="">请选择</option></select></div>
            <div class="fitem"><label>电池产品</label><select id="cpr-f-batprod"><option value="">请选择电池产品</option></select></div>
            <div class="fitem"><label>获取方式</label><select id="cpr-f-gettype"><option value="">全部</option><option value="领券中心">领券中心</option><option value="采购">采购</option><option value="发放">发放</option></select></div>
          </div>
          <div class="fb-row">
            <div class="fitem"><label>优惠券标题</label><input type="text" id="cpr-f-title" placeholder="请输入" /></div>
            <div class="fitem"><label>抵扣类型</label><select id="cpr-f-disctype"><option value="">全部</option><option value="金额券">金额券</option><option value="折扣券">折扣券</option><option value="租金券">租金券</option></select></div>
            <div class="fitem"><label>适用产品</label><select id="cpr-f-product"><option value="">全部</option></select></div>
            <div class="fitem"><label>禁用状态</label><select id="cpr-f-disabled"><option value="">全部</option><option value="正常">正常</option><option value="禁用">禁用</option></select></div>
            <div class="hit" id="cpr-hit"></div>
            <button type="button" class="btn" id="cpr-search-btn">🔍 搜索</button>
            <button type="button" class="btn btn-ghost" id="cpr-reset-btn">⟲ 重置</button>
            <button type="button" class="btn btn-ghost" id="btn-export-cpr">📥 导出</button>
          </div>
        </div>
        <div class="panel">
          <div class="phead"><h3>优惠券资源（领券中心）<span id="cpr-count"></span></h3><button type="button" class="btn sm" id="btn-cpr-page-prev">◀</button><button type="button" class="btn sm" id="btn-cpr-page-next">▶</button></div>
          <div class="tbl-wrap"><table id="cpr-list"><thead></thead><tbody></tbody></table></div>
          <div style="text-align:center;font-size:12px;color:var(--muted);padding:8px 0" id="cpr-pagination"></div>
        </div>
        <div class="note">⚠️ 数据待连接数据库后抽取；支持添加/编辑/删除资源，分页展示。</div>
      </div>
    </div>
'''

# Insert coupon view before OPS comment
html = html.replace(
    '\n    <!-- OPS -->',
    '\n' + coupon_html + '\n    <!-- OPS -->'
)

# ============================================================
# 4. 重写 v-ops 为4子菜单模式
# ============================================================
old_ops = '''    <!-- OPS -->
    <div class="view" id="v-ops">
      <h2 class="title">运维看板</h2>
      <p class="desc">换电柜 / 电池异常预警（未解除）。按预警等级、代理商联动筛选。</p>
      <div class="filterbar" id="fb-ops"></div>
      <div class="kpis" id="o-kpis"></div>
      <div class="panel"><h3>未解除预警按等级（全量）</h3><div id="o-level" class="chart sm"></div></div>
      <div class="panel">
        <h3>最近未解除预警（样本上限 <span id="o-cap"></span>）</h3>
        <div class="tbl-wrap"><table id="o-detail"><thead></thead><tbody></tbody></table></div>
      </div>
      <h2 class="title" style="margin-top:26px">工单概况</h2>
      <p class="desc">来源 t_work_order（全量 is_del=0）：状态/优先级/城市/事项类型分布与近30天趋势；明细可按城市/代理商/搜索筛选。</p>
      <div class="kpis" id="wo-kpis"></div>
      <div class="panel"><h3>工单状态分布（全量）</h3><div id="wo-status" class="chart sm"></div></div>
      <div class="panel"><h3>优先级分布（全量）</h3><div id="wo-priority" class="chart sm"></div></div>
      <div class="panel"><h3>城市工单 TOP20（柱：工单数）</h3><div id="wo-city" class="chart"></div></div>
      <div class="panel"><h3>事项类型 TOP20</h3><div id="wo-event" class="chart"></div></div>
      <div class="panel"><h3>近30天 创建 / 完成 趋势</h3><div id="wo-trend" class="chart"></div></div>
      <div class="panel">
        <h3>工单明细（可按城市/代理商/搜索筛选，样本上限 <span id="wo-cap"></span>）</h3>
        <div class="tbl-wrap"><table id="wo-detail"><thead></thead><tbody></tbody></table></div>
      </div>
    </div>'''

new_ops = '''    <!-- OPS -->
    <div class="view" id="v-ops">
      <h2 class="title">运维看板</h2>
      <p class="desc">换电柜告警 / 电池告警 / 运维工单 / 网点拜访记录。按预警等级、工单状态、城市联动筛选。</p>
      <div class="subtabs" id="ops-sub">
        <button type="button" class="stab active" data-opssub="cab-alarm">🔴 换电柜告警总览</button>
        <button type="button" class="stab" data-opssub="bat-alarm">🔋 电池告警总览</button>
        <button type="button" class="stab" data-opssub="workorder">📋 运维工单</button>
        <button type="button" class="stab" data-opssub="site-visit">📍 网点拜访记录</button>
      </div>
      <div class="filterbar" id="fb-ops"></div>

      <!-- O1 换电柜告警总览 -->
      <div class="opssub-panel" id="panel-ops-cab-alarm">
        <div class="kpis" id="oca-kpis"></div>
        <div class="grid2">
          <div class="panel"><h3>告警等级分布（全量）</h3><div id="oca-level" class="chart sm"></div></div>
          <div class="panel"><h3>告警类型 TOP15</h3><div id="oca-type" class="chart sm"></div></div>
        </div>
        <div class="panel">
          <div class="phead"><h3>换电柜告警明细<span id="oca-cap"></span></h3><button type="button" class="btn sm" id="btn-export-oca">导出</button></div>
          <div class="tbl-wrap"><table id="oca-detail"><thead></thead><tbody></tbody></table></div>
        </div>
        <div class="note">⚠️ 数据待连接数据库后抽取（换电柜告警日志表）；当前复用 DATA.ops.warn_recent 字段骨架。</div>
      </div>

      <!-- O2 电池告警总览 -->
      <div class="opssub-panel" id="panel-ops-bat-alarm" style="display:none">
        <div class="kpis" id="oba-kpis"></div>
        <div class="grid2">
          <div class="panel"><h3>告警等级分布（全量）</h3><div id="oba-level" class="chart sm"></div></div>
          <div class="panel"><h3>告警类型 TOP15</h3><div id="oba-type" class="chart sm"></div></div>
        </div>
        <div class="panel">
          <div class="phead"><h3>电池告警明细<span id="oba-cap"></span></h3><button type="button" class="btn sm" id="btn-export-oba">导出</button></div>
          <div class="tbl-wrap"><table id="oba-detail"><thead></thead><tbody></tbody></table></div>
        </div>
        <div class="note">⚠️ 数据待连接数据库后抽取（电池告警日志表）。</div>
      </div>

      <!-- O3 运维工单 -->
      <div class="opssub-panel" id="panel-ops-workorder" style="display:none">
        <div class="kpis" id="owo-kpis"></div>
        <div class="grid2">
          <div class="panel"><h3>工单状态分布（全量）</h3><div id="owo-status" class="chart sm"></div></div>
          <div class="panel"><h3>优先级分布（全量）</h3><div id="owo-priority" class="chart sm"></div></div>
        </div>
        <div class="grid2">
          <div class="panel"><h3>城市工单 TOP20</h3><div id="owo-city" class="chart"></div></div>
          <div class="panel"><h3>事项类型 TOP20</h3><div id="owo-event" class="chart"></div></div>
        </div>
        <div class="panel"><h3>近30天 创建 / 完成 趋势</h3><div id="owo-trend" class="chart"></div></div>
        <div class="panel">
          <div class="phead"><h3>工单明细（样本上限 <span id="owo-cap"></span>）</h3><button type="button" class="btn sm" id="btn-export-owo">导出</button></div>
          <div class="tbl-wrap"><table id="owo-detail"><thead></thead><tbody></tbody></table></div>
        </div>
      </div>

      <!-- O4 网点拜访记录 -->
      <div class="opssub-panel" id="panel-ops-site-visit" style="display:none">
        <div class="kpis" id="osv-kpis"></div>
        <div class="single-search" style="margin:6px 0">
          <input type="text" id="osv-q-staff" placeholder="拜访人" />
          <input type="text" id="osv-q-site" placeholder="网点名称" />
          <select id="osv-f-city"><option value="">城市（全部）</option></select>
          <input type="text" id="osv-q-start" placeholder="开始日期" />
          <input type="text" id="osv-q-end" placeholder="结束日期" />
          <button type="button" class="btn" id="osv-search-btn">🔍 搜索</button>
          <button type="button" class="btn btn-ghost" id="btn-export-osv">📥 导出</button>
        </div>
        <div class="panel">
          <h3>网点拜访记录<span id="osv-cap"></span></h3>
          <div class="tbl-wrap"><table id="osv-detail"><thead></thead><tbody></tbody></table></div>
        </div>
        <div class="note">⚠️ 数据待连接数据库后抽取（网点拜访/巡检记录表）；含拜访人/网点/时间/问题描述/处理结果等。</div>
      </div>
    </div>'''

html = html.replace(old_ops, new_ops)

# ============================================================
# 5. CSS: 新增样式
# ============================================================
css_insert = '''.note{background:linear-gradient(135deg,#fffbeb,#fef3c7);border:1px solid #fcd34d;border-radius:10px;padding:10px 14px;margin:12px 0;font-size:12px;color:#92400e;line-height:1.6}
.note.hl{background:linear-gradient(135deg,#eff6ff,#dbeafe);border-color:#93c5fd;color:#1e40af}'''

new_css = css_insert + '''
/* ---------- coupon panels ---------- */
.coupsub-panel{display:block}
.coup-tabs{display:flex;gap:6px;margin:8px 0;flex-wrap:wrap}
.coup-tabs .stab{padding:8px 20px;border:1px solid var(--line);background:var(--card);color:var(--txt);font-size:13px;font-weight:600;cursor:pointer;border-radius:9px 9px 0 0;transition:.15s}
.coup-tabs .stab.active{background:var(--blue);color:#fff;border-color:var(--blue)}
.coup-tabs .stab:hover:not(.active){background:var(--bg)}
.opssub-panel{display:block}
.toolbar{display:flex;align-items:center;gap:8px;margin:8px 0;flex-wrap:wrap}
.toolbar .sep{color:var(--muted2);font-size:12px}
.phead{display:flex;align-items:center;justify-content:space-between;margin-bottom:10px}
.phead h3{margin:0;font-size:14px}
'''

html = html.replace(css_insert, new_css)

# ============================================================
# 6. JS: 扩展 applyDevice (加3路) + 新增 applyCoupon + applyOps
# ============================================================

# 6a. 扩展 applyDevice
old_apply_device = '''function applyDevice(f){
  const sub=DEVSUB;
  document.querySelectorAll('[id^="panel-dev-"]').forEach(p=>p.style.display='none');
  const panel=document.getElementById('panel-dev-'+sub); if(panel)panel.style.display='';
  if(sub==='cabinet') return drawDevCabinet(f);
  if(sub==='battery') return drawDevBattery(f);
  if(sub==='vehicle') return drawDevVehicle(f);
  if(sub==='cablist') return drawDevCabList(f);
  if(sub==='batlist') return drawDevBatList(f);
  if(sub==='warehouse') return drawDevWarehouse(f);
  if(sub==='circulation') return drawDevCirculation(f);
  if(sub==='rental') return drawDevRental(f);
  if(sub==='dispatch') return drawDevDispatch(f);
}'''

new_apply_device = '''function applyDevice(f){
  const sub=DEVSUB;
  document.querySelectorAll('[id^="panel-dev-"]').forEach(p=>p.style.display='none');
  const panel=document.getElementById('panel-dev-'+sub); if(panel)panel.style.display='';
  if(sub==='cabinet') return drawDevCabinet(f);
  if(sub==='battery') return drawDevBattery(f);
  if(sub==='vehicle') return drawDevVehicle(f);
  if(sub==='cablist') return drawDevCabList(f);
  if(sub==='batlist') return drawDevBatList(f);
  if(sub==='warehouse') return drawDevWarehouse(f);
  if(sub==='circulation') return drawDevCirculation(f);
  if(sub==='rental') return drawDevRental(f);
  if(sub==='dispatch') return drawDevDispatch(f);
  if(sub==='inventory') return drawDevInventory(f);
  if(sub==='fault') return drawDevFault(f);
  if(sub==='transfer') return drawDevTransfer(f);
}

// 10 设备出入库管理 ⚠️ 待抽
function drawDevInventory(f){
  kpis(document.getElementById('w-inv-kpis'),[
    {l:'待入库设备数',v:'⚠️',s:'待抽'},
    {l:'今日入库',v:'⚠️',s:'待抽'},
    {l:'今日出库',v:'⚠️',s:'待抽'},
    {l:'库存总量',v:'⚠️',s:'待抽'}
  ]);
  buildTable('w-inv-list',[
    {k:'record_id',h:'记录ID'},{k:'device_type',h:'设备类型'},{k:'device_id',h:'设备SN/ID'},
    {k:'op_type',h:'操作类型'},{k:'operator',h:'操作人'},{k:'op_time',h:'操作时间'},
    {k:'from_obj',h:'流出对象'},{k:'to_obj',h:'流入对象'},{k:'result',h:'运营结果'}
  ],[]);
}

// 11 故障设备管理 ⚠️ 待抽
function drawDevFault(f){
  kpis(document.getElementById('w-fault-kpis'),[
    {l:'故障换电柜数',v:'⚠️',s:'待抽'},
    {l:'故障电池数',v:'⚠️',s:'待抽'},
    {l:'已维修',v:'⚠️',s:'待抽'},
    {l:'已报废',v:'⚠️',s:'待抽'}
  ]);
  buildTable('w-fault-list',[
    {k:'device_id',h:'设备ID/SN'},{k:'device_type',h:'设备类型'},{k:'fault_type',h:'故障类型'},
    {k:'fault_time',h:'故障时间'},{k:'location',h:'所在位置'},{k:'status',h:'处理状态'},
    {k:'handler',h:'处理人'},{k:'handle_time',h:'处理时间'}
  ],[]);
}

// 12 设备调拨记录 ⚠️ 待抽
function drawDevTransfer(f){
  buildTable('w-tf-list',[
    {k:'record_id',h:'记录ID'},{k:'operator_id',h:'操作人ID'},{k:'operator_name',h:'操作人名称'},
    {k:'op_time',h:'操作时间'},{k:'device_type',h:'设备类型'},{k:'device_id',h:'操作设备ID'},
    {k:'op_type',h:'操作类型'},{k:'result',h:'运营结果'},{k:'from_obj',h:'流出对象'},
    {k:'to_obj',h:'流入对象'}
  ],[]);
  document.getElementById('tf-count').textContent='';
}'''

html = html.replace(old_apply_device, new_apply_device)

# ============================================================
# 7. JS: 新增优惠券所有函数 (applyCoupon + 6个draw函数)
# ============================================================

# Find insertion point - after drawDevTransfer function, before the next major section
# Insert before "// ==================== 数据大屏"
coupon_js = '''
// ==================== 优惠券看板 ====================
let COUPSUB = state.couponSub || 'overview';
function applyCoupon(f){
  const sub=COUPSUB;
  document.querySelectorAll('[id^="panel-coup-"]').forEach(p=>p.style.display='none');
  const panel=document.getElementById('panel-coup-'+sub); if(panel)panel.style.display='';
  if(sub==='overview') return drawCouponOverview(f);
  if(sub==='agent-issue') return drawCouponAgentIssue(f);
  if(sub==='merchant-issue') return drawCouponMerchantIssue(f);
  if(sub==='contract-purchase') return drawCouponContractPurchase(f);
  if(sub==='user-detail') return drawCouponUserDetail(f);
  if(sub==='resource') return drawCouponResource(f);
}

// C1 优惠券总览
function drawCouponOverview(f){
  kpis(document.getElementById('cp-over-kpis'),[
    {l:'优惠券总数量',v:'⚠️',nav:'coupon',preset:{couponSub:'user-detail'},s:'待抽'},
    {l:'购买总金额(元)',v:'⚠️',s:'待抽'},
    {l:'购买总人数',v:'⚠️',s:'待抽'},
    {l:'已核销数量',v:'⚠️',nav:'coupon',preset:{couponSub:'user-detail'},s:'跳转明细'},
    {l:'未使用数量',v:'⚠️',nav:'coupon',preset:{couponSub:'user-detail'},s:'跳转明细'},
    {l:'未兑换数量',v:'⚠️',nav:'coupon',preset:{couponSub:'user-detail'},s:'跳转明细'},
    {l:'作废数量',v:'⚠️',nav:'coupon',preset:{couponSub:'user-detail'},s:'跳转明细'},
    {l:'已退款数量',v:'⚠️',nav:'coupon',preset:{couponSub:'user-detail'},s:'跳转明细'},
    {l:'未付款数量',v:'⚠️',nav:'coupon',preset:{couponSub:'user-detail'},s:'跳转明细'}
  ]);
  pie('cp-status-pie',[{name:'已核销',value:0},{name:'未使用',value:0},{name:'未兑换',value:0},{name:'作废',value:0},{name:'已退款',value:0},{name:'未付款',value:0}],null,'⚠️ 待抽数据');
  bar('cp-buy-bar',['⚠️'],[0],'购买数量',true);
  bar('cp-top-site',['⚠️'],[0],'门店',true);
  bar('cp-top-merchant',['⚠️'],[0],'商户',true);
  buildTable('cp-over-list',[
    {k:'coupon_name',h:'优惠券名称'},{k:'buy_count',h:'购买数量'},{k:'buy_amount',h:'购买金额'},
    {k:'used_count',h:'已核销',nav:'coupon',preset:{couponSub:'user-detail'}},
    {k:'unused_count',h:'未使用'},{k:'unredeemed_count',h:'未兑换'},
    {k:'cancelled_count',h:'作废'},{k:'refunded_count',h:'已退款'},{k:'unpaid_count',h:'未付款'}
  ],[]);
  document.getElementById('cp-count').textContent='';
}

// C2 代理商发券统计
function drawCouponAgentIssue(f){
  buildTable('cpai-list',[
    {k:'record_id',h:'发券记录ID'},{k:'coupon_name',h:'优惠券名称'},
    {k:'redeem_code',h:'优惠券兑换码'},{k:'issuer',h:'发放人'},{k:'issue_date',h:'发放日期'},
    {k:'max_purchase',h:'最高需业员券购买'},{k:'user_info',h:'用户信息'},
    {k:'use_status',h:'使用状态',f:v=>v==='已使用'?tag(v,'green'):tag(v||'未使用','amber')},
    {k:'pay_status',h:'付款状态',f:v=>v==='已付款'?tag(v,'blue'):tag(v||'未付款','red')},
    {k:'protocol_id',h:'换电协议ID'},{k:'battery_product',h:'电池产品'},
    {k:'site_name',h:'签约网点'},{k:'package',h:'签约套餐'},{k:'vehicle_brand',h:'车辆品牌'},
    {k:'pay_amount_due',h:'业务员应付金额'},{k:'pay_amount_real',h:'业务员实付金额'},
    {k:'pay_date',h:'业务员支付日期'},{k:'pay_method',h:'业务员支付方式'}
  ],[]);
  document.getElementById('cpai-count').textContent='';
}

// C3 商户端发券统计
function drawCouponMerchantIssue(f){
  buildTable('cpmi-list',[
    {k:'redeem_id',h:'兑换码id'},{k:'batch_no',h:'批次号'},{k:'redeem_code',h:'兑换码',f:v=>v?'📱':''},
    {k:'coupon_info',h:'优惠券信息'},{k:'order_id',h:'订单ID'},{k:'ship_info',h:'发货信息'},
    {k:'redeem_user',h:'兑换用户信息'},{k:'redeem_status',h:'兑换状态',f:v=>tag(v||'—','gray')},
    {k:'cancel_info',h:'作废信息',f:v=>v?tag(v,'red'):''},
    {k:'use_info',h:'使用信息'},{k:'site_name',h:'签约网点'},
    {k:'issuer_info',h:'发放人信息'},{k:'agreement_no',h:'协议编号'},
    {k:'pay_info',h:'付款信息'},{k:'merchant_info',h:'商户信息'},
    {k:'ops',h:'操作',f:v=>'<span class="ops">作废补发 | 发放 | 详情</span>'}
  ],[]);
  document.getElementById('cpmi-count').textContent='';
}

// C4 合约份额采购统计
function drawCouponContractPurchase(f){
  kpis(document.getElementById('cppc-kpis'),[
    {l:'采购总额(元)',v:'⚠️',s:'待抽'},
    {l:'采购单数',v:'⚠️',s:'待抽'},
    {l:'涉及代理商数',v:'⚠️',s:'待抽'},
    {l:'待付款金额',v:'⚠️',s:'待抽'}
  ]);
  buildTable('cppc-list',[
    {k:'contract_id',h:'合约ID'},{k:'agent_name',h:'代理商'},{k:'coupon_name',h:'优惠券'},
    {k:'quota',h:'份额数量'},{k:'unit_price',h:'单价'},{k:'total_amount',h:'总金额'},
    {k:'purchase_count',h:'已采购量'},{k:'status',h:'状态'},{k:'create_time',h:'创建时间'}
  ],[]);
  document.getElementById('cppc-count').textContent='';
}

// C5 用户优惠券明细
function drawCouponUserDetail(f){
  // 同代理商发券统计字段结构
  buildTable('cpud-list',[
    {k:'record_id',h:'发券记录ID'},{k:'coupon_name',h:'优惠券名称'},
    {k:'redeem_code',h:'优惠券兑换码'},{k:'issuer',h:'发放人'},{k:'issue_date',h:'发放日期'},
    {k:'max_purchase',h:'最高需业员券购买'},{k:'user_info',h:'用户信息'},
    {k:'use_status',h:'使用状态',f:v=>v==='已使用'?tag(v,'green'):tag(v||'未使用','amber')},
    {k:'pay_status',h:'付款状态',f:v=>v==='已付款'?tag(v,'blue'):tag(v||'未付款','red')},
    {k:'protocol_id',h:'换电协议ID'},{k:'battery_product',h:'电池产品'},
    {k:'site_name',h:'签约网点'},{k:'package',h:'签约套餐'},{k:'vehicle_brand',h:'车辆品牌'},
    {k:'pay_amount_due',h:'业务员应付金额'},{k:'pay_amount_real',h:'业务员实付金额'},
    {k:'pay_date',h:'业务员支付日期'},{k:'pay_method',h:'业务员支付方式'}
  ],[]);
  document.getElementById('cpud-count').textContent='';
}

// C6 优惠券资源（领券中心）
function drawCouponResource(f){
  buildTable('cpr-list',[
    {k:'resource_id',h:'资源ID'},{k:'coupon_title',h:'优惠券标题'},
    {k:'discount_type',h:'抵扣类型'},{k:'apply_product',h:'适用产品'},
    {k:'discount_value',h:'优惠额度值'},{k:'city_area',h:'城市区域'},
    {k:'battery_model',h:'电池型号'},{k:'get_type',h:'获取方式'},
    {k:'disabled',h:'禁用状态',f:v=>v==='禁用'?tag(v,'red'):tag(v||'正常','green')},
    {k:'creator',h:'创建员工'},{k:'created_at',h:'创建时间'},
    {k:'ops',h:'操作',f:v=>'<span class="ops">编辑 | 删除</span>'}
  ],[]);
  document.getElementById('cpr-count').textContent='';
  document.getElementById('cpr-pagination').textContent='共 0 条/页';
}

function switchCpMerchantTab(tab){
  CP_MERCHANT_TAB=tab;
  document.querySelectorAll('#panel-coup-merchant-issue .coup-tabs .stab').forEach(x=>x.classList.toggle('active', x.id==='cptab-'+tab));
}

'''

html = html.replace(
    '// ==================== 数据大屏',
    coupon_js + '// ==================== 数据大屏'
)

# ============================================================
# 8. JS: 新增运维看板4子菜单函数 applyOps + 4个draw函数
# ============================================================

ops_js = '''
// ==================== 运维看板（4子菜单）====================
let OPSSUB = state.opsSub || 'cab-alarm';
function applyOps(f){
  const sub=OPSSUB;
  document.querySelectorAll('[id^="panel-ops-"]').forEach(p=>p.style.display='none');
  const panel=document.getElementById('panel-ops-'+sub); if(panel)panel.style.display='';
  if(sub==='cab-alarm') return drawOpsCabAlarm(f);
  if(sub==='bat-alarm') return drawOpsBatAlarm(f);
  if(sub==='workorder') return drawOpsWorkorder(f);
  if(sub==='site-visit') return drawOpsSiteVisit(f);
}

// O1 换电柜告警总览
function drawOpsCabAlarm(f){
  const O=DATA.ops||{};
  kpis(document.getElementById('oca-kpis'),[
    {l:'告警总数',v:fmt((O.warn_by_level||[]).reduce((a,b)=>a+(b.count||0),0))},
    {l:'紧急告警',v:fmt((O.warn_by_level||[]).filter(x=>x.level==='high').reduce((a,b)=>a+b.count,0)),tone:'red'},
    {l:'一般告警',v:fmt((O.warn_by_level||[]).filter(x=>x.level==='normal').reduce((a,b)=>a+b.count,0)),tone:'amber'},
    {l:'未解决',v:fmt((O.warn_recent||[]).length),tone:'red'}
  ]);
  pie('oca-level',(O.warn_by_level||[]).map(d=>({name:CN.level[d.level]||d.level,value:d.count})));
  bar('oca-type',['⚠️ 待抽告警类型'],[0],'告警数',true);
  buildTable('oca-detail',[
    {k:'warn_id',h:'告警ID'},{k:'cabinet_sn',h:'换电柜SN'},{k:'level',h:'等级',f:v=>tag(v,v==='high'?'red':'amber')},
    {k:'type',h:'告警类型'},{k:'msg',h:'告警内容'},{k:'site_name',h:'网点'},
    {k:'city',h:'城市'},{k:'created_at',h:'触发时间'},{k:'status',h:'状态'}
  ], O.warn_recent||[]);
  var capEl=document.getElementById('oca-cap'); if(capEl)capEl.textContent='（'+(O.warn_recent||[]).length+'）';
}

// O2 电池告警总览 ⚠️ 待抽
function drawOpsBatAlarm(f){
  kpis(document.getElementById('oba-kpis'),[
    {l:'告警总数',v:'⚠️',s:'待抽'},
    {l:'紧急告警',v:'⚠️',tone:'red',s:'待抽'},
    {l:'一般告警',v:'⚠️',tone:'amber',s:'待抽'},
    {l:'未解决',v:'⚠️',tone:'red',s:'待抽'}
  ]);
  pie('oba-level',[{name:'紧急',value:0},{name:'一般',value:0}],null,'⚠️ 待抽');
  bar('oba-type',['⚠️'],[0],'告警数',true);
  buildTable('oba-detail',[
    {k:'warn_id',h:'告警ID'},{k:'battery_sn',h:'电池SN'},{k:'level',h:'等级'},
    {k:'type',h:'告警类型'},{k:'msg',h:'告警内容'},{k:'location',h:'位置'},
    {k:'city',h:'城市'},{k:'created_at',h:'触发时间'},{k:'status',h:'状态'}
  ],[]);
  var capEl=document.getElementById('oba-cap'); if(capEl)capEl.textContent='';
}

// O3 运维工单（原v-ops工单部分迁移）
function drawOpsWorkorder(f){
  const O=DATA.ops||{}; const WO=DATA.workorder||{};
  const woList=WO.detail||(O.order_detail||[]);
  kpis(document.getElementById('owo-kpis'),[
    {l:'工单总数',v:fmt(woList.length)},
    {l:'待处理',v:fmt(woList.filter(r=>r.status==='pending').length),tone:'amber'},
    {l:'处理中',v:fmt(woList.filter(r=>r.status==='processing').length),tone:'blue'},
    {l:'已完成',v:fmt(woList.filter(r=>r.status==='done').length),tone:'green'},
    {l:'近30天新建',v:'⚠️',s:'待抽趋势'}
  ]);
  pie('owo-status',(WO.by_status||[]).map(d=>({name:d.status,value:d.count})));
  pie('owo-priority',(WO.by_priority||[]).map(d=>({name:d.priority,value:d.count})));
  bar('owo-city',(WO.city_rank||[]).slice(0,20).map(d=>d.city),(WO.city_rank||[]).slice(0,20).map(d=>d.count),'工单数',true);
  bar('owo-event',(WO.event_type||[]).slice(0,20).map(d=>d.type),(WO.event_type||[]).slice(0,20).map(d=>d.count),'数量',true);
  lineTrend('owo-trend',[],[],'创建','完成');
  buildTable('owo-detail',[
    {k:'order_id',h:'工单ID'},{k:'type',h:'事项类型'},{k:'priority',h:'优先级',f:v=>tag(v,v==='urgent'?'red':v==='normal'?'amber':'gray')},
    {k:'status',h:'状态',f:v=>stTag(v)},{k:'city',h:'城市'},{k:'agency',h:'代理商'},
    {k:'site',h:'网点'},{k:'assignee',h:'处理人'},{k:'create_time',h:'创建时间'},{k:'finish_time',h:'完成时间'},
    {k:'desc',h:'描述'}
  ], woList);
  var capEl=document.getElementById('owo-cap'); if(capEl)capEl.textContent='（'+woList.length+'）';
}

// O4 网点拜访记录 ⚠️ 待抽
function drawOpsSiteVisit(f){
  kpis(document.getElementById('osv-kpis'),[
    {l:'拜访记录总数',v:'⚠️',s:'待抽'},
    {l:'本周拜访',v:'⚠️',s:'待抽'},
    {l:'问题数',v:'⚠️',tone:'red',s:'待抽'},
    {l:'已解决',v:'⚠️',tone:'green',s:'待抽'}
  ]);
  buildTable('osv-detail',[
    {k:'visit_id',h:'拜访ID'},{k:'staff_name',h:'拜访人'},{k:'staff_id',h:'拜访人ID'},
    {k:'site_name',h:'网点名称'},{k:'city',h:'城市'},{k:'visit_time',h:'拜访时间'},
    {k:'problem_desc',h:'问题描述'},{k:'handle_result',h:'处理结果'},
    {k:'photos',h:'拍照记录'},{k:'status',h:'状态'}
  ],[]);
  var capEl=document.getElementById('osv-cap'); if(capEl)capEl.textContent='';
}

'''

# Insert ops JS before the navigate function
html = html.replace(
    'function navigate(mod, preset){',
    ops_js + 'function navigate(mod, preset){'
)

# ============================================================
# 9. JS: 更新 bindDeviceSub (withFilter加入新3项)
# ============================================================

old_bind_device = '''function bindDeviceSub(){
  const box=document.getElementById('dev-sub'); if(!box)return;
  box.querySelectorAll('.stab').forEach(b=>{ b.addEventListener('click',()=>{
    DEVSUB=b.dataset.devsub; state.deviceSub=DEVSUB;
    box.querySelectorAll('.stab').forEach(x=>x.classList.toggle('active', x.dataset.devsub===DEVSUB));
    document.querySelectorAll('[id^="panel-dev-"]').forEach(p=>p.style.display='none');
    const panel=document.getElementById('panel-dev-'+DEVSUB); if(panel)panel.style.display='';
    const fb=document.getElementById('fb-device'); if(fb) fb.style.display = withFilter.includes(DEVSUB)?'':'none';
    if(withFilter.includes(DEVSUB)) buildFilterBar('device');
    applyDevice(state.device||{});
  }); });
}'''

new_bind_device = '''const withFilter=['cabinet','battery','cablist','batlist'];
function bindDeviceSub(){
  const box=document.getElementById('dev-sub'); if(!box)return;
  box.querySelectorAll('.stab').forEach(b=>{ b.addEventListener('click',()=>{
    DEVSUB=b.dataset.devsub; state.deviceSub=DEVSUB;
    box.querySelectorAll('.stab').forEach(x=>x.classList.toggle('active', x.dataset.devsub===DEVSUB));
    document.querySelectorAll('[id^="panel-dev-"]').forEach(p=>p.style.display='none');
    const panel=document.getElementById('panel-dev-'+DEVSUB); if(panel)panel.style.display='';
    const fb=document.getElementById('fb-device'); if(fb) fb.style.display = withFilter.includes(DEVSUB)?'':'none';
    if(withFilter.includes(DEVSUB)) buildFilterBar('device');
    applyDevice(state.device||{});
  }); });

  // 出入库按钮
  var btnIn=document.getElementById('btn-batch-in'); if(btnIn) btnIn.onclick=function(){ alert('⚠️ 批量入库功能待连接数据库后实现'); };
  var btnOut=document.getElementById('btn-batch-out'); if(btnOut) btnOut.onclick=function(){ alert('⚠️ 批量出库功能待连接数据库后实现'); };

  // 调拨搜索
  var tfSearch=document.getElementById('tf-search-btn'); if(tfSearch) tfSearch.onclick=function(){ alert('⚠️ 调拨记录查询待连接数据库'); };
  var tfReset=document.getElementById('tf-reset-btn'); if(tfReset) tfReset.onclick=function(){
    ['tf-q-op','tf-q-start','tf-q-end'].forEach(function(id){ var el=document.getElementById(id); if(el)el.value=''; });
    ['tf-f-type','tf-f-dtype'].forEach(function(id){ var el=document.getElementById(id); if(el)el.value=''; });
  };

  // 导出绑定
  bindExport('btn-export-inv','w-inv-list','设备出入库');
  bindExport('btn-export-tf','w-tf-list','设备调拨记录');
}'''

html = html.replace(old_bind_device, new_bind_device)

# ============================================================
# 10. JS: 新增 bindCouponSub + bindOpsSub
# ============================================================

bind_subs_js = '''
let CP_MERCHANT_TAB='redeem';
function bindCouponSub(){
  const box=document.getElementById('coup-sub'); if(!box)return;
  box.querySelectorAll('.stab').forEach(b=>{ b.addEventListener('click',()=>{
    COUPSUB=b.dataset.coupsub; state.couponSub=COUPSUB;
    box.querySelectorAll('.stab').forEach(x=>x.classList.toggle('active', x.dataset.coupsub===COUPSUB));
    document.querySelectorAll('[id^="panel-coup-"]').forEach(p=>p.style.display='none');
    const panel=document.getElementById('panel-coup-'+COUPSUB); if(panel)panel.style.display='';
    applyCoupon(state.coupon||{});
  }); });

  // 代理商发券搜索
  var cpaiS=document.getElementById('cpai-search-btn'); if(cpaiS) cpaiS.onclick=function(){ alert('⚠️ 查询待连接数据库'); };
  var cpaiR=document.getElementById('cpai-reset-btn'); if(cpaiR) cpaiR.onclick=function(){ resetFilters('cpai-f-'); };
  bindExport('btn-export-cpai','cpai-list','代理商发券统计');

  // 商户端发券搜索
  var cpmiS=document.getElementById('cpmi-search-btn'); if(cpmiS) cpmiS.onclick=function(){ alert('⚠️ 查询待连接数据库'); };
  var cpmiR=document.getElementById('cpmi-reset-btn'); if(cpmiR) cpmiR.onclick=function(){ resetFilters('cpmi-f-'); };
  bindExport('btn-export-cpmi','cpmi-list','商户端发券统计');

  // 用户明细搜索
  var cpudS=document.getElementById('cpud-search-btn'); if(cpudS) cpudS.onclick=function(){ alert('⚠️ 查询待连接数据库'); };
  var cpudR=document.getElementById('cpud-reset-btn'); if(cpudR) cpudR.onclick=function(){ resetFilters('cpud-f-'); };
  bindExport('btn-export-cpud','cpud-list','用户优惠券明细');

  // 领券中心搜索
  var cprS=document.getElementById('cpr-search-btn'); if(cprS) cprS.onclick=function(){ alert('⚠️ 查询待连接数据库'); };
  var cprR=document.getElementById('cpr-reset-btn'); if(cprR) cprR.onclick=function(){ resetFilters('cpr-f-'); };
  bindExport('btn-export-cpr','cpr-list','优惠券资源');
  var addRes=document.getElementById('btn-add-cpres'); if(addRes) addRes.onclick=function(){ alert('⚠️ 添加资源功能待连接数据库后实现'); };
}

function bindOpsSub(){
  const box=document.getElementById('ops-sub'); if(!box)return;
  box.querySelectorAll('.stab').forEach(b=>{ b.addEventListener('click',()=>{
    OPSSUB=b.dataset.opssub; state.opsSub=OPSSUB;
    box.querySelectorAll('.stab').forEach(x=>x.classList.toggle('active', x.dataset.opssub===OPSSUB));
    document.querySelectorAll('[id^="panel-ops-"]').forEach(p=>p.style.display='none');
    const panel=document.getElementById('panel-ops-'+OPSSUB); if(panel)panel.style.display='';
    applyOps(state.ops||{});
  }); });

  // 导出绑定
  bindExport('btn-export-oca','oca-detail','换电柜告警');
  bindExport('btn-export-oba','oba-detail','电池告警');
  bindExport('btn-export-owo','owo-detail','运维工单');

  // 网点拜访搜索
  var osvS=document.getElementById('osv-search-btn'); if(osvS) osvS.onclick=function(){ alert('⚠️ 查询待连接数据库'); };
  bindExport('btn-export-osv','osv-detail','网点拜访记录');
}

function resetFilters(prefix){
  document.querySelectorAll('[id^="'+prefix+'"]').forEach(function(el){
    if(el.tagName==='SELECT'||el.tagName==='INPUT') el.value='';
  });
}

function bindExport(btnId, tableId, name){
  var btn=document.getElementById(btnId); if(btn) btn.onclick=function(){ exportCSV(tableId, name); };
}

'''

# Insert after bindDeviceSub
html = html.replace(
    '  // USER sub\n  function bindUserSub(){',
    bind_subs_js + '  // USER sub\n  function bindUserSub(){'
)

# ============================================================
# 11. JS: navigate 增加 couponSub/opssub 支持
# ============================================================
old_navigate_preset = '''  if(preset.deviceSub){ DEVSUB=preset.deviceSub; state.deviceSub=DEVSUB; document.querySelectorAll('#dev-sub .stab').forEach(x=>x.classList.toggle('active', x.dataset.devsub===DEVSUB)); document.querySelectorAll('[id^="panel-dev-"]').forEach(p=>p.style.display='none'); const _p=document.getElementById('panel-dev-'+DEVSUB); if(_p)_p.style.display=''; }
  if('cabFilter' in preset){ DEVCAB_FILTER=preset.cabFilter; }'''

new_navigate_preset = '''  if(preset.deviceSub){ DEVSUB=preset.deviceSub; state.deviceSub=DEVSUB; document.querySelectorAll('#dev-sub .stab').forEach(x=>x.classList.toggle('active', x.dataset.devsub===DEVSUB)); document.querySelectorAll('[id^="panel-dev-"]').forEach(p=>p.style.display='none'); const _p=document.getElementById('panel-dev-'+DEVSUB); if(_p)_p.style.display=''; }
  if(preset.couponSub){ COUPSUB=preset.couponSub; state.couponSub=COUPSUB; document.querySelectorAll('#coup-sub .stab').forEach(x=>x.classList.toggle('active', x.dataset.coupsub===COUPSUB)); document.querySelectorAll('[id^="panel-coup-"]').forEach(p=>p.style.display='none'); const _cp=document.getElementById('panel-coup-'+COUPSUB); if(_cp)_cp.style.display=''; }
  if(preset.opsSub){ OPSSUB=preset.opsSub; state.opsSub=OPSSUB; document.querySelectorAll('#ops-sub .stab').forEach(x=>x.classList.toggle('active', x.dataset.opssub===OPSSUB)); document.querySelectorAll('[id^="panel-ops-"]').forEach(p=>p.style.display='none'); const _op=document.getElementById('panel-ops-'+OPSSUB); if(_op)_op.style.display=''; }
  if('cabFilter' in preset){ DEVCAB_FILTER=preset.cabFilter; }'''

html = html.replace(old_navigate_preset, new_navigate_preset)

# Also update navigate's sub-switching section
old_nav_sub = '''  if(usub && mod==='user'){ switchUserSub(usub); } // 跳转到用户看板指定子菜单（保留筛选）
  if(ssub && mod==='sales'){ switchSalesSub(ssub); } // 跳转到销售看板指定子菜单（保留筛选）
  if(ssub && mod==='site'){ switchSiteSub(ssub); } // 跳转到网点看板指定子菜单（保留筛选）'''

new_nav_sub = '''  if(usub && mod==='user'){ switchUserSub(usub); }
  if(ssub && mod==='sales'){ switchSalesSub(ssub); }
  if(ssub && mod==='site'){ switchSiteSub(ssub); }
  if(preset.couponSub && mod==='coupon'){ applyCoupon(state.coupon||{}); }
  if(preset.opsSub && mod==='ops'){ applyOps(state.ops||{}); }'''

html = html.replace(old_nav_sub, new_nav_sub)

# ============================================================
# 12. render() 函数：新增优惠券表格预建 + 设备新表格 + Ops/Coupon初始化
# ============================================================

# Add coupon tables and new device tables in render(), after existing device tables
old_render_device_end = '''  bindDeviceSub();
  applyDevice(state.device||{});
  bindUserSub();'''

new_render_device_end = '''  // Device new tables
  buildTable('w-inv-list',[
    {k:'record_id',h:'记录ID'},{k:'device_type',h:'设备类型'},{k:'device_id',h:'设备SN/ID'},
    {k:'op_type',h:'操作类型'},{k:'operator',h:'操作人'},{k:'op_time',h:'操作时间'},
    {k:'from_obj',h:'流出对象'},{k:'to_obj',h:'流入对象'},{k:'result',h:'运营结果'}
  ],[]);
  buildTable('w-fault-list',[
    {k:'device_id',h:'设备ID/SN'},{k:'device_type',h:'设备类型'},{k:'fault_type',h:'故障类型'},
    {k:'fault_time',h:'故障时间'},{k:'location',h:'所在位置'},{k:'status',h:'处理状态'},
    {k:'handler',h:'处理人'},{k:'handle_time',h:'处理时间'}
  ],[]);
  buildTable('w-tf-list',[
    {k:'record_id',h:'记录ID'},{k:'operator_id',h:'操作人ID'},{k:'operator_name',h:'操作人名称'},
    {k:'op_time',h:'操作时间'},{k:'device_type',h:'设备类型'},{k:'device_id',h:'操作设备ID'},
    {k:'op_type',h:'操作类型'},{k:'result',h:'运营结果'},{k:'from_obj',h:'流出对象'},
    {k:'to_obj',h:'流入对象'}
  ],[]);
  bindDeviceSub();
  applyDevice(state.device||{});

  // COUPON —— 预建表格
  buildTable('cp-over-list',[
    {k:'coupon_name',h:'优惠券名称'},{k:'buy_count',h:'购买数量'},{k:'buy_amount',h:'购买金额'},
    {k:'used_count',h:'已核销'},{k:'unused_count',h:'未使用'},{k:'unredeemed_count',h:'未兑换'},
    {k:'cancelled_count',h:'作废'},{k:'refunded_count',h:'已退款'},{k:'unpaid_count',h:'未付款'}
  ],[]);
  buildTable('cpai-list',[
    {k:'record_id',h:'发券记录ID'},{k:'coupon_name',h:'优惠券名称'},{k:'redeem_code',h:'优惠券兑换码'},
    {k:'issuer',h:'发放人'},{k:'issue_date',h:'发放日期'},{k:'max_purchase',h:'最高需业员券购买'},
    {k:'user_info',h:'用户信息'},{k:'use_status',h:'使用状态'},{k:'pay_status',h:'付款状态'},
    {k:'protocol_id',h:'换电协议ID'},{k:'battery_product',h:'电池产品'},{k:'site_name',h:'签约网点'},
    {k:'package',h:'签约套餐'},{k:'vehicle_brand',h:'车辆品牌'},{k:'pay_amount_due',h:'业务员应付金额'},
    {k:'pay_amount_real',h:'业务员实付金额'},{k:'pay_date',h:'业务员支付日期'},{k:'pay_method',h:'业务员支付方式'}
  ],[]);
  buildTable('cpmi-list',[
    {k:'redeem_id',h:'兑换码id'},{k:'batch_no',h:'批次号'},{k:'redeem_code',h:'兑换码'},
    {k:'coupon_info',h:'优惠券信息'},{k:'order_id',h:'订单ID'},{k:'ship_info',h:'发货信息'},
    {k:'redeem_user',h:'兑换用户信息'},{k:'redeem_status',h:'兑换状态'},{k:'cancel_info',h:'作废信息'},
    {k:'use_info',h:'使用信息'},{k:'site_name',h:'签约网点'},{k:'issuer_info',h:'发放人信息'},
    {k:'agreement_no',h:'协议编号'},{k:'pay_info',h:'付款信息'},{k:'merchant_info',h:'商户信息'},
    {k:'ops',h:'操作'}
  ],[]);
  buildTable('cppc-list',[
    {k:'contract_id',h:'合约ID'},{k:'agent_name',h:'代理商'},{k:'coupon_name',h:'优惠券'},
    {k:'quota',h:'份额数量'},{k:'unit_price',h:'单价'},{k:'total_amount',h:'总金额'},
    {k:'purchase_count',h:'已采购量'},{k:'status',h:'状态'},{k:'create_time',h:'创建时间'}
  ],[]);
  buildTable('cpud-list',[
    {k:'record_id',h:'发券记录ID'},{k:'coupon_name',h:'优惠券名称'},{k:'redeem_code',h:'优惠券兑换码'},
    {k:'issuer',h:'发放人'},{k:'issue_date',h:'发放日期'},{k:'max_purchase',h:'最高需业员券购买'},
    {k:'user_info',h:'用户信息'},{k:'use_status',h:'使用状态'},{k:'pay_status',h:'付款状态'},
    {k:'protocol_id',h:'换电协议ID'},{k:'battery_product',h:'电池产品'},{k:'site_name',h:'签约网点'},
    {k:'package',h:'签约套餐'},{k:'vehicle_brand',h:'车辆品牌'},{k:'pay_amount_due',h:'业务员应付金额'},
    {k:'pay_amount_real',h:'业务员实付金额'},{k:'pay_date',h:'业务员支付日期'},{k:'pay_method',h:'业务员支付方式'}
  ],[]);
  buildTable('cpr-list',[
    {k:'resource_id',h:'资源ID'},{k:'coupon_title',h:'优惠券标题'},{k:'discount_type',h:'抵扣类型'},
    {k:'apply_product',h:'适用产品'},{k:'discount_value',h:'优惠额度值'},{k:'city_area',h:'城市区域'},
    {k:'battery_model',h:'电池型号'},{k:'get_type',h:'获取方式'},{k:'disabled',h:'禁用状态'},
    {k:'creator',h:'创建员工'},{k:'created_at',h:'创建时间'},{k:'ops',h:'操作'}
  ],[]);
  bindCouponSub();
  applyCoupon(state.coupon||{});

  // OPS —— 子菜单模式重写，预建表格
  buildTable('oca-detail',[
    {k:'warn_id',h:'告警ID'},{k:'cabinet_sn',h:'换电柜SN'},{k:'level',h:'等级'},
    {k:'type',h:'告警类型'},{k:'msg',h:'告警内容'},{k:'site_name',h:'网点'},
    {k:'city',h:'城市'},{k:'created_at',h:'触发时间'},{k:'status',h:'状态'}
  ],(DATA.ops||{}).warn_recent||[]);
  buildTable('oba-detail',[
    {k:'warn_id',h:'告警ID'},{k:'battery_sn',h:'电池SN'},{k:'level',h:'等级'},
    {k:'type',h:'告警类型'},{k:'msg',h:'告警内容'},{k:'location',h:'位置'},
    {k:'city',h:'城市'},{k:'created_at',h:'触发时间'},{k:'status',h:'状态'}
  ],[]);
  var _woList=(DATA.workorder||{}).detail||(DATA.ops||{}).order_detail||[];
  buildTable('owo-detail',[
    {k:'order_id',h:'工单ID'},{k:'type',h:'事项类型'},{k:'priority',h:'优先级'},
    {k:'status',h:'状态'},{k:'city',h:'城市'},{k:'agency',h:'代理商'},
    {k:'site',h:'网点'},{k:'assignee',h:'处理人'},{k:'create_time',h:'创建时间'},{k:'finish_time',h:'完成时间'},
    {k:'desc',h:'描述'}
  ],_woList);
  buildTable('osv-detail',[
    {k:'visit_id',h:'拜访ID'},{k:'staff_name',h:'拜访人'},{k:'staff_id',h:'拜访人ID'},
    {k:'site_name',h:'网点名称'},{k:'city',h:'城市'},{k:'visit_time',h:'拜访时间'},
    {k:'problem_desc',h:'问题描述'},{k:'handle_result',h:'处理结果'},
    {k:'photos',h:'拍照记录'},{k:'status',h:'状态'}
  ],[]);
  bindOpsSub();
  applyOps(state.ops||{});

  bindUserSub();'''

html = html.replace(old_render_device_end, new_render_device_end)

# ============================================================
# 13. 替换原 OPS 初始化代码（render中的旧ops块）
# ============================================================
# Remove old OPS init block that draws the old single-view ops
old_ops_init = '''  // OPS
  const O=DATA.ops||{};
  CAP.ops=(O.warn_recent||[]).length; document.getElementById(\'o-cap\').textContent=CAP.ops;
  kpis(document.getElementById(\'o-kpis\'),[
    {l:\'未解除预警总数\',v:fmt((O.warn_by_level||[]).reduce((a,b)=>a+(b.count||0),0))},
    {l:\'紧急\',v:fmt((O.warn_by_level||[]).filter(x=>x.level===\'high\').reduce((a,b)=>a+b.count,0)),tone:\'red\'},
    {l:\'一般\',v:fmt((O.warn_by_level||[]).filter(x=>x.level===\'normal\').reduce((a,b)=>a+b.count,0)),tone:\'amber\'}
  ]);
  pie(\'o-level\',(O.warn_by_level||[]).map(d=>({name:CN.level[d.level]||d.level,value:d.count})));
  buildTable(\'o-detail\',['''

# We need a more robust approach - find and remove the old OPS block in render()
# Let me find it by its start marker
if '// OPS\n  const O=DATA.ops||{};' in html:
    # Find the old OPS block from '// OPS' to '// PERSONNEL'
    import re
    ops_block_match = re.search(r'  // OPS\n  const O=DATA\.ops\|\|\{\};.*?(?=\n  // PERSONNEL)', html, re.DOTALL)
    if ops_block_match:
        html = html[:ops_block_match.start()] + '\n  // OPS (moved to sub-tab mode — see bindOpsSub/applyOps)\n' + html[ops_block_match.end():]

# ============================================================
# 14. 更新 CHART_IDS 加入新图表ID
# ============================================================
# Find CHART_IDS line and append new IDs
old_chart_ids_line = "const CHART_IDS="
idx = html.find(old_chart_ids_line)
if idx >= 0:
    # Find end of this line/array
    bracket_end = html.find('];', idx)
    if bracket_end >= 0:
        before = html[:bracket_end+2]
        after = html[bracket_end+2:]
        new_chart_ids_part = """,'cp-status-pie','cp-buy-bar','cp-top-site','cp-top-merchant','oca-level','oca-type','oba-level','oba-type','owo-status','owo-priority','owo-city','owo-event','owo-trend']"""
        # Actually we need to insert inside the array
        html = before + new_chart_ids_part + after

# ============================================================
# 15. 更新 CALIBER 加入优惠券口径
# ============================================================
caliber_start = "const CALIBER = {"
cal_idx = html.find(caliber_start)
if cal_idx >= 0:
    # Find closing } of CALIBER object
    brace_count = 0
    i = cal_idx + len("const CALIBER = ")
    while i < len(html):
        if html[i] == '{': brace_count += 1
        elif html[i] == '}':
            brace_count -= 1
            if brace_count == 0:
                # Insert new caliber entries before closing brace
                html = html[:i] + """
  ,'cp-total':'优惠券总数量 = SUM(各优惠券发行总量)，来源于优惠券主表聚合'
  ,'cp-amount':'购买总金额 = SUM(实际支付金额)，含已付款+未付款'
  ,'cp-buyers':'购买总人数 = COUNT(DISTINCT user_id)，去重用户数'
  ,'cp-used':'已核销数量 = status=已核销 的优惠券计数'
  ,'cp-unused':'未使用数量 = status=未使用 AND 已过期 的优惠券计数'
  ,'cp-unredeemed':'未兑换数量 = status=未兑换 的优惠券计数（用户领取但未激活）'
  ,'cp-cancelled':'作废数量 = status=作废 的优惠券计数'
  ,'cp-refunded':'已退款数量 = status=已退款 的优惠券计数'
  ,'cp-unpaid':'未付款数量 = pay_status=未付款 的优惠券计数'
  ,'oca-cab':'换电柜告警 = cabinet_alarm_log WHERE resolved=0，按等级(high/normal)分组'
  ,'oba-bat':'电池告警 = battery_alarm_log WHERE resolved=0，按等级分组'
  ,'owo-order':'运维工单 = t_work_order WHERE is_del=0，含状态/优先级/城市/事项类型'
  ,'osv-visit':'网点拜访记录 = site_visit_log 或巡检表，含拜访人/网点/时间/问题/结果'
""" + html[i:]
                break
        i += 1

# Write output
with open(TEMPLATE, 'w', encoding='utf-8') as f:
    f.write(html)

print(f"OK! Template updated. Total lines: {len(html.split(chr(10)))}")
