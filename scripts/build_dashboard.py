# -*- coding: utf-8 -*-
import json, time
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.chart import BarChart, Reference
from openpyxl.utils import get_column_letter

BASE = r"D:/workboddy file/dudu分析/citybike_backup"
M = json.load(open(f"{BASE}/data/metrics.json", encoding="utf-8"))
NOW_STR = time.strftime("%Y-%m-%d %H:%M", time.localtime())

# ---------- 样式 ----------
NAVY = "1F4E79"; BLUE = "2E75B6"; LBLUE = "DDEBF7"; GREY = "F2F2F2"
HDR = Font(bold=True, color="FFFFFF", size=11)
TITLE = Font(bold=True, color="FFFFFF", size=14)
SUB = Font(bold=True, color=NAVY, size=12)
BOLD = Font(bold=True, size=11)
NORM = Font(size=10)
fill_navy = PatternFill("solid", fgColor=NAVY)
fill_blue = PatternFill("solid", fgColor=BLUE)
fill_lb = PatternFill("solid", fgColor=LBLUE)
fill_grey = PatternFill("solid", fgColor=GREY)
thin = Side(style="thin", color="BFBFBF")
border = Border(left=thin, right=thin, top=thin, bottom=thin)
center = Alignment(horizontal="center", vertical="center", wrap_text=True)
left = Alignment(horizontal="left", vertical="center", wrap_text=True)

def money(x):
    if x is None: return "—"
    try: return round(float(x)/100, 2)
    except: return x

def num(x):
    if x is None: return "—"
    try: return int(x)
    except: return x

def is_err(v):
    return isinstance(v, dict) and "_error" in v

wb = Workbook()

def title_bar(ws, text, span=8):
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=span)
    c = ws.cell(1, 1, text); c.font = TITLE; c.fill = fill_navy; c.alignment = left
    ws.row_dimensions[1].height = 26

def section(ws, row, text, span=8):
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=span)
    c = ws.cell(row, 1, text); c.font = SUB; c.fill = fill_lb
    return row + 1

def kpi_grid(ws, start_row, cards, per_row=4, w=2):
    """Lay KPI (label,value) cards in a grid band, per_row per line."""
    r = start_row
    for i, (lab, val) in enumerate(cards):
        col = 1 + (i % per_row) * 2
        if i > 0 and i % per_row == 0:
            r += 2
        lc = ws.cell(r, col, lab)
        lc.font = Font(bold=True, color="FFFFFF", size=10); lc.fill = fill_blue
        lc.alignment = center; lc.border = border
        ws.merge_cells(start_row=r, start_column=col, end_row=r, end_column=col+w-1)
        vc = ws.cell(r+1, col, val)
        vc.font = Font(bold=True, color=NAVY, size=14); vc.alignment = center; vc.border = border
        ws.merge_cells(start_row=r+1, start_column=col, end_row=r+1, end_column=col+w-1)
    return r + 2

def table(ws, row, headers, rows, start_col=1, widths=None):
    for j, h in enumerate(headers):
        c = ws.cell(row, start_col+j, h); c.font = HDR; c.fill = fill_blue; c.alignment = center; c.border = border
    r = row + 1
    for i, rec in enumerate(rows):
        for j, val in enumerate(rec):
            c = ws.cell(r, start_col+j, val); c.font = NORM; c.border = border
            c.alignment = left if j == 0 else center
            if i % 2 == 1: c.fill = fill_grey
        r += 1
    if widths:
        for j, w in enumerate(widths):
            ws.column_dimensions[get_column_letter(start_col+j)].width = w
    return r

# ============ 1. 说明 ============
ws = wb.active; ws.title = "说明"
title_bar(ws, "城市换电业务数据看板 · 说明与口径", span=2)
ws.column_dimensions["A"].width = 26; ws.column_dimensions["B"].width = 92
info = [
 ("数据来源", "AnalyticDB MySQL：am-...ads.aliyuncs.com / 数据库 sharing-citybike-pro（生产只读查询）"),
 ("生成时间", NOW_STR),
 ("覆盖模块", "数据总览、用户、销售、网点、设备资产、运维、人员、财务、客服服务台（共9页）"),
 ("指标口径", "用户/电池/网点等总数取 is_del=0；金额字段单位为“分”，看板统一÷100展示为“元”"),
 ("时间口径", "时间戳为13位毫秒(bigint)；“近N天”以生成时间为基准向前推算"),
 ("换电柜口径", "数据库无独立换电柜主表，本看板“换电柜总数”以 t_battery.device_sn 去重近似在网柜机数，待你确认是否有更权威来源"),
 ("活跃用户", "“近7天活跃”基于 t_exchange_order.take_user_id 去重，属较重查询，若超时则显示“—”"),
 ("刷新方式", "运行 scripts/metrics.py 重新拉取并写入 metrics.json，再运行本脚本重建看板"),
 ("明细导出", "各看板“明细表/排行榜”可在源库按需查询；本看板聚焦聚合指标与排行榜"),
 ("数据备份", "已配置每日增量(最新一天)自动化备份至本地 data/incremental，并保留最新全量快照，可离线/跨设备查看"),
 ("重要提示", "本看板为只读聚合分析，不写回生产库；如字段含义有出入请告知，我将校正中文映射"),
]
r = 3
for k, v in info:
    a = ws.cell(r, 1, k); a.font = BOLD; a.fill = fill_lb; a.alignment = left; a.border = border
    b = ws.cell(r, 2, v); b.font = NORM; b.alignment = left; b.border = border
    ws.row_dimensions[r].height = 30
    r += 1

# ============ 2. 数据总览 ============
ws = wb.create_sheet("数据总览")
title_bar(ws, "数据总览（默认全部数据）", span=8)
ov = M.get("overview", {})
r = 3
r = kpi_grid(ws, r, [
    ("用户人数", num(ov.get("user_total"))),
    ("换电柜总数(近似)", num(ov.get("cabinet_total_proxy"))),
    ("电池总数", num(ov.get("battery_total"))),
    ("网点总数", num(ov.get("site_total"))),
    ("协议总数", num(ov.get("agreement_total"))),
    ("近30天新增用户", num(ov.get("user_new_30d"))),
])

r = section(ws, r, "网点套餐销量排行榜（TOP15，按签约网点）")
sp = ov.get("site_package_sales_top15", [])
if is_err(sp):
    ws.cell(r, 1, "查询失败/超时：" + str(sp.get("_error"))).font = NORM; r += 2
else:
    rows = [[i+1, x[0], num(x[1]), money(x[2])] for i, x in enumerate(sp)]
    end = table(ws, r, ["排名","网点名称","销量(笔)","销售额(元)"], rows, widths=[8,40,14,16])
    if rows:
        chart = BarChart(); chart.type="bar"; chart.title="网点套餐销量 TOP15"; chart.height=9; chart.width=18
        data = Reference(ws, min_col=3, min_row=r, max_row=r+len(rows))
        cats = Reference(ws, min_col=2, min_row=r+1, max_row=r+len(rows))
        chart.add_data(data, titles_from_data=True); chart.set_categories(cats); chart.legend=None
        ws.add_chart(chart, f"F{r}")
    r = end + 2

r = section(ws, r, "区域业务员销冠排行榜（TOP15，按城市+业务员签约协议数）")
sm = ov.get("salesman_top15", [])
if is_err(sm):
    ws.cell(r, 1, "查询失败/超时：" + str(sm.get("_error"))).font = NORM; r += 2
else:
    rows = [[i+1, x[0], x[1], num(x[2])] for i, x in enumerate(sm)]
    end = table(ws, r, ["排名","城市","业务员","签约协议数"], rows, widths=[8,16,24,14])
    r = end + 1

# ============ 3. 中文表名字典 ============
ws = wb.create_sheet("中文表名字典")
title_bar(ws, "数据库表 → 中文业务名称映射（核心表）", span=5)
TABLE_CN = [
 ("用户主表","t_user","用户/会员档案（手机号、城市、状态、注册时间）","用户/客服"),
 ("用户租金卡","t_user_exchange_rent","用户租赁/租金卡记录","用户/财务"),
 ("用户套餐购买订单","t_user_exchange_package_order","换电套餐购买订单（金额、退款、支付方式）","销售/财务/用户"),
 ("用户电量包订单","t_user_exchange_rent_package_order","租金/电量包购买订单","用户/财务"),
 ("换电协议(合同)","t_exchange_agreement","用户与网点签约的换电服务协议（个人/企业、状态、激活/终止时间、业务员）","用户/销售/客服"),
 ("换电柜/电池","t_battery","电池主表（状态、在线、SN、归属柜机）","设备资产"),
 ("换电柜类型","t_device_type","换电柜设备型号分类","设备资产"),
 ("网点主表","t_site","线下换电/售车网点（城市、类型、状态、业务员、店长、商户）","网点"),
 ("换电门店","t_exchange_store","换电门店经营数据","网点"),
 ("换电套餐","t_exchange_package","可购买的换电套餐（电量、价格、有效期）","销售"),
 ("租金套餐","t_exchange_rent_package","租金/租期卡套餐","销售/财务"),
 ("优惠券","t_coupon","平台优惠券模板","销售/财务"),
 ("用户优惠券","t_user_coupon","发放到用户的优惠券","销售/财务"),
 ("换电订单","t_exchange_order","每一次换电/借还操作订单（含网点、用户、电池）","运维/客服"),
 ("换电服务订单","t_exchange_service_order","换电服务类订单","运维"),
 ("渠道商/经销商","t_distributor","多级经销商/渠道商","人员/销售"),
 ("推广员","t_promoter","推广员（含业务员关联）","人员/销售"),
 ("网点店员","t_site_store_employee","网点店员/导购（在职状态）","人员"),
 ("代理商员工","t_warehouse_agency_employee","代理商侧员工","人员"),
 ("工单","t_work_order","运维/业务工单（事项、状态、处理人、超期）","运维"),
 ("监控异常事件","t_monitor_ex_event","换电柜/电池等预警事件（等级、解除状态）","运维"),
 ("电池预警事件","t_monitor_ex_event_battery","电池专项预警","运维"),
 ("费用账单","t_expense_bill","收支费用账单（支出方/收入方/金额/结算状态）","财务"),
 ("电费结算","t_exchange_electric_settlement","网点换电柜电费结算单","财务/网点"),
 ("用户反馈","t_feedback","用户对服务的评价/反馈（评分、场景）","客服服务台"),
 ("接待记录","t_reception_log","客服接待记录（协议/消费者/接待人）","客服服务台"),
 ("车辆主表","t_bike","车辆档案","设备/销售"),
 ("车辆销售关系","t_bike_sale_relation","车辆销售归属（经销商/创客/网点/返佣）","销售/人员"),
 ("电池产品","t_battery_product","电池产品/型号定义","设备/销售"),
 ("代理商","t_agency","代理商（结构未单列，见渠道商/员工表）","人员/销售"),
]
r = 3
end = table(ws, r, ["中文表名","数据库表名","业务含义","所属模块"],
            [[a,b,c,d] for a,b,c,d in TABLE_CN],
            widths=[18,34,52,16])
ws.cell(end+1,1,"说明：本字典覆盖看板使用的核心表；全部422张表结构见 data/schema_report.json。字段级中文名已内置数据库 COLUMN_COMMENT，看板指标均按注释命名。").font = Font(italic=True, size=9, color="808080")

# ============ 模块通用渲染 ============
def module_sheet(name, title, kpis, tables_def):
    ws = wb.create_sheet(name)
    title_bar(ws, title, span=8)
    r = 3
    # KPI cards in a clean grid band
    r = kpi_grid(ws, r, kpis, per_row=4)
    for (sec, headers, rows, w) in tables_def:
        r = section(ws, r, sec)
        if is_err(rows):
            ws.cell(r, 1, "查询失败/超时：" + str(rows.get("_error"))).font = NORM; r += 2; continue
        if not rows:
            ws.cell(r, 1, "（无数据）").font = NORM; r += 2; continue
        rows = [[ (i+1 if j==0 and isinstance(x[0],int)==False and sec.startswith("排")==False else x[j]) for j,x in enumerate([rec]) ][0] if False else rec for rec in rows]
        end = table(ws, r, headers, rows, widths=w)
        r = end + 2
    return ws

# ---- 用户看板 ----
u = M.get("user", {})
kpis = [("用户总人数", num(u.get("total"))),
         ("近30天新增", num(u.get("new_30d"))),
         ("近7天活跃", num(u.get("active_7d"))),
         ("协议状态数", len(u.get("agreement_status", [])) if not is_err(u.get("agreement_status")) else "—")]
tabs = []
ast = u.get("agreement_status", [])
if not is_err(ast): tabs.append(("不同协议状态用户数", ["协议状态","用户数"], [[x[0], num(x[1])] for x in ast], [18,14]))
t50 = u.get("top50_value", [])
if not is_err(t50): tabs.append(("用户价值 TOP50（按累计实付金额）", ["排名","用户ID","手机号","累计实付(元)","订单数"],
        [[i+1, x[0], x[1], money(x[2]), num(x[3])] for i,x in enumerate(t50)], [8,14,16,16,12]))
c30 = u.get("city_top30", [])
if not is_err(c30): tabs.append(("各城市用户数 TOP30", ["排名","城市","用户数"],
        [[i+1, x[0], num(x[1])] for i,x in enumerate(c30)], [8,18,14]))
module_sheet("用户看板", "一、用户看板", kpis, tabs)

# ---- 销售看板 ----
s = M.get("sales", {})
po = s.get("package_order", [[]])
po = po[0] if po and not is_err(po) else [None,None,None]
kpis = [("套餐订单数", num(po[0])),
         ("套餐销售额(元)", money(po[1])),
         ("套餐退款额(元)", money(po[2])),
         ("签约业务员TOP", (s.get("salesman_sign_top10",[[]]) or [[]]) and len([x for x in s.get("salesman_sign_top10",[]) if not is_err(x)]) or "—")]
tabs = []
pn = s.get("package_by_name_top15", [])
if not is_err(pn): tabs.append(("套餐销量排行 TOP15", ["排名","套餐名称","销量(笔)","销售额(元)"],
        [[i+1, x[0], num(x[1]), money(x[2])] for i,x in enumerate(pn)], [8,34,14,16]))
ss = s.get("site_sales_30d_top10", [])
if not is_err(ss): tabs.append(("网点近30天销售排行 TOP10", ["排名","网点","销量(笔)","销售额(元)"],
        [[i+1, x[0], num(x[1]), money(x[2])] for i,x in enumerate(ss)], [8,34,14,16]))
st = s.get("salesman_sign_top10", [])
if not is_err(st): tabs.append(("业务员签约协议数排行 TOP10", ["排名","业务员","协议数"],
        [[i+1, x[0], num(x[1])] for i,x in enumerate(st)], [8,24,14]))
module_sheet("销售看板", "二、销售看板", kpis, tabs)

# ---- 网点看板 ----
si = M.get("site", {})
kpis = [("网点总数", num(si.get("total"))),
         ("换电排行维度", "近30天换电次数"),
         ("售车排行维度", "累计销量"),
         ("状态分类数", len(si.get("status",[])) if not is_err(si.get("status")) else "—")]
tabs = []
stt = si.get("status", [])
if not is_err(stt): tabs.append(("不同网点状态数量", ["网点状态","数量"], [[x[0], num(x[1])] for x in stt], [16,14]))
ex = si.get("exchange_30d_top30", [])
if not is_err(ex): tabs.append(("网点近30天换电次数排行 TOP30", ["排名","网点","换电次数"],
        [[i+1, x[0], num(x[1])] for i,x in enumerate(ex)], [8,36,14]))
sl = si.get("sale_top15", [])
if not is_err(sl): tabs.append(("网点售车排行 TOP15", ["排名","网点","销量(笔)","金额(元)"],
        [[i+1, x[0], num(x[1]), money(x[2])] for i,x in enumerate(sl)], [8,34,14,16]))
module_sheet("网点看板", "三、网点看板", kpis, tabs)

# ---- 设备资产看板 ----
dv = M.get("device", {})
kpis = [("电池总数", num(dv.get("battery_total"))),
         ("换电柜(近似)", num(M.get("overview",{}).get("cabinet_total_proxy"))),
         ("电池状态分类", len(dv.get("battery_status",[])) if not is_err(dv.get("battery_status")) else "—"),
         ("在线状态分类", len(dv.get("battery_online",[])) if not is_err(dv.get("battery_online")) else "—")]
tabs = []
bs = dv.get("battery_status", [])
if not is_err(bs): tabs.append(("电池状态分布", ["状态","数量"], [[x[0], num(x[1])] for x in bs], [16,14]))
bo = dv.get("battery_online", [])
if not is_err(bo): tabs.append(("电池在线状态分布", ["在线状态","数量"], [[x[0], num(x[1])] for x in bo], [16,14]))
ct = dv.get("cabinet_by_type_top10", [])
if not is_err(ct): tabs.append(("换电柜按型号分布 TOP10（按device_sn去重）", ["排名","设备类型ID","柜机数"],
        [[i+1, x[0], num(x[1])] for i,x in enumerate(ct)], [8,16,14]))
module_sheet("设备资产看板", "四、设备资产看板（换电柜/电池）", kpis, tabs)

# ---- 运维看板 ----
op = M.get("ops", {})
kpis = [("监控事件(等级类)", len(op.get("monitor_level",[])) if not is_err(op.get("monitor_level")) else "—"),
         ("监控事件(状态类)", len(op.get("monitor_status",[])) if not is_err(op.get("monitor_status")) else "—"),
         ("电池预警数", num(op.get("battery_alert"))),
         ("工单超期数", num(op.get("work_order_overdue")))]
tabs = []
ml = op.get("monitor_level", [])
if not is_err(ml): tabs.append(("监控事件-紧急程度", ["等级","数量"], [[x[0], num(x[1])] for x in ml], [14,14]))
ms = op.get("monitor_status", [])
if not is_err(ms): tabs.append(("监控事件-解除状态", ["状态","数量"], [[x[0], num(x[1])] for x in ms], [14,14]))
wos = op.get("work_order_status", [])
if not is_err(wos): tabs.append(("工单状态分布", ["状态","数量"], [[x[0], num(x[1])] for x in wos], [16,14]))
we = op.get("work_order_event_top10", [])
if not is_err(we): tabs.append(("工单事项 TOP10", ["排名","事项名称","数量"],
        [[i+1, x[0], num(x[1])] for i,x in enumerate(we)], [8,30,14]))
module_sheet("运维看板", "五、运维看板（换电柜/电池预警·工单）", kpis, tabs)

# ---- 人员看板 ----
pe = M.get("personnel", {})
kpis = [("推广员数", num(pe.get("promoter"))),
         ("网点店员(在职)", num(pe.get("store_employee_on"))),
         ("渠道商(可用)", num(pe.get("distributor_on"))),
         ("代理商员工", num(pe.get("agency_employee")))]
tabs = []
module_sheet("人员看板", "六、人员看板（推广员/店员/渠道商/代理商员工）", kpis, tabs)

# ---- 财务看板 ----
fi = M.get("finance", {})
pir = fi.get("package_income_refund", [[]]); pir = pir[0] if pir and not is_err(pir) else [None,None]
kpis = [("套餐实收(元)", money(pir[0])),
         ("套餐退款(元)", money(pir[1])),
         ("已结算费用(元)", money(fi.get("expense_settled"))),
         ("费用类型数", len(fi.get("expense_by_type_top12",[])) if not is_err(fi.get("expense_by_type_top12")) else "—")]
tabs = []
eb = fi.get("expense_by_type_top12", [])
if not is_err(eb): tabs.append(("费用支出按类型 TOP12", ["排名","费用类型","笔数","金额(元)"],
        [[i+1, x[0], num(x[1]), money(x[2])] for i,x in enumerate(eb)], [8,24,12,16]))
module_sheet("财务看板", "七、财务看板（收入·支出）", kpis, tabs)

# ---- 客服服务台 ----
sv = M.get("service", {})
kpis = [("用户反馈数", num(sv.get("feedback_count"))),
         ("客服接待数", num(sv.get("reception_count"))),
         ("反馈场景数", len(sv.get("feedback_by_scene",[])) if not is_err(sv.get("feedback_by_scene")) else "—"),
         ("评分维度", "见下表")]
tabs = []
fbs = sv.get("feedback_by_scene", [])
if not is_err(fbs): tabs.append(("各场景反馈量与平均评分", ["场景","反馈数","平均评分"],
        [[x[0], num(x[1]), x[2]] for x in fbs], [24,14,14]))
module_sheet("客服服务台", "九、客服服务台（反馈·接待）", kpis, tabs)

# freeze header rows
for ws in wb.worksheets:
    ws.sheet_view.showGridLines = False
    ws.freeze_panes = "A2"

out = f"{BASE}/看板.xlsx"
wb.save(out)
print("SAVED", out)
