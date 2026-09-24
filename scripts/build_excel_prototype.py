# -*- coding: utf-8 -*-
"""构建网点价值+电池风险 Excel 原型（xlsx skill 规范：公式驱动 + 配色 + 零错误）"""
import json
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

D = json.load(open("data/dashboard_data.json", encoding="utf-8"))
br = D["device"]["battery_risk"]
sv = D["site"]["value"]
bat_stats = br["stats"]
site_stats = sv["stats"]
tier_dist = sv["tier_dist"]
gen_at = br.get("generated_at", "")
OPEX = site_stats.get("opex_per_site_month", 2000)

# ---- styles ----
FNT = "Arial"
HDR_FILL = PatternFill("solid", fgColor="1F4E78")
HDR_FONT = Font(name=FNT, bold=True, color="FFFFFF", size=11)
TITLE_FONT = Font(name=FNT, bold=True, size=14, color="1F4E78")
SUB_FONT = Font(name=FNT, bold=True, size=11, color="1F4E78")
BLUE = Font(name=FNT, color="0000FF")          # 硬编码输入
BLACK = Font(name=FNT, color="000000")         # 公式
GREEN = Font(name=FNT, color="008000")         # 跨表引用
YEL_FILL = PatternFill("solid", fgColor="FFFF00")  # 假设项
INPUT_FILL = PatternFill("solid", fgColor="DDEBF7")
thin = Side(style="thin", color="BFBFBF")
BORDER = Border(left=thin, right=thin, top=thin, bottom=thin)
CTR = Alignment(horizontal="center", vertical="center")
LEFT = Alignment(horizontal="left", vertical="center", wrap_text=True)

wb = Workbook()

def style_header(ws, row, cols):
    for c in cols:
        cell = ws.cell(row=row, column=c)
        cell.fill = HDR_FILL; cell.font = HDR_FONT; cell.alignment = CTR; cell.border = BORDER

def put_table(ws, start_row, headers, rows, start_col=1, widths=None):
    for j, h in enumerate(headers):
        ws.cell(row=start_row, column=start_col+j, value=h)
    style_header(ws, start_row, range(start_col, start_col+len(headers)))
    for i, r in enumerate(rows):
        for j, v in enumerate(r):
            cell = ws.cell(row=start_row+1+i, column=start_col+j, value=v)
            cell.border = BORDER; cell.font = BLACK; cell.alignment = LEFT if j==0 else CTR
    if widths:
        for j, w in enumerate(widths):
            ws.column_dimensions[get_column_letter(start_col+j)].width = w
    return start_row + 1 + len(rows)

# ===================== Sheet1: 模型说明 =====================
ws = wb.active; ws.title = "模型说明"
ws.column_dimensions['A'].width = 26; ws.column_dimensions['B'].width = 16
ws.column_dimensions['C'].width = 60
ws['A1'] = "嘟嘟换电 · 数据分析原型 · 模型说明与假设"; ws['A1'].font = TITLE_FONT
ws['A2'] = "数据快照生成时间: %s" % gen_at; ws['A2'].font = Font(name=FNT, italic=True, size=9, color="808080")
ws['A3'] = "数据源: dashboard_data.json (device.battery_risk / site.value)"; ws['A3'].font = Font(name=FNT, italic=True, size=9, color="808080")

r = 5
ws.cell(r,1,"电池风险评分阈值（已批准）").font = SUB_FONT
r += 1
put_table(ws, r, ["维度","临界阈值","权重/分值"], [
    ["SOC 电量","<10% → +30；<20% → +15","安全故障"],
    ["BMS 最高温",">55℃ → +25；>45℃ → +12","安全故障"],
    ["循环次数",">800 → +20；>500 → +10","安全故障"],
    ["电芯压差(max-min)",">300mV → +15；>150mV → +8","安全故障"],
    ["在线状态","非'在线' → +10","连接维度"],
    ["等级判定","score≥40 高危；≥20 预警；其余 正常",""],
    ["性质分类","命中任一健康临界=安全故障型；仅离线+低SOC=失联亏电型",""],
], widths=[20,40,16])
r += 9
ws.cell(r,1,"网点价值评分阈值（已批准）").font = SUB_FONT
r += 1
put_table(ws, r, ["维度","规则","分值"], [
    ["换电效益(40)","swap30≥500→40；≥200→28；≥50→16；≥10→8；else 0",""],
    ["用户粘性(25)","net=sign-unsub ≥20→25；≥5→18；≥0→12；else 4",""],
    ["设备健康(20)","柜状态正常且离线率0→20；<0.3→14；<0.7→8；else 2",""],
    ["成长性(15)","growth=(swap30*3-swap90)/swap90 >0.2→15；>0→10；>-0.2→6；else 2",""],
    ["等级","S≥75 / A≥50 / B≥25 / C<25",""],
    ["淘汰标准","C级 + audit_status=已开业 + swap_30d<10",""],
], widths=[20,55,12])
r += 9
ws.cell(r,1,"关键假设（可编辑·黄色）").font = SUB_FONT
r += 1
ws.cell(r,1,"单点月运维成本(元/网点/月)").font = BLACK
c = ws.cell(r,2, OPEX); c.font = BLUE; c.fill = YEL_FILL; c.border = BORDER; c.alignment = CTR
ws.cell(r,3,"⚠️ 估算假设：依据《运维费用管理标准制度 DD-YW-230208》口径，待财务校准；改此值→'网点价值_汇总'年节省自动重算").font = Font(name=FNT, size=9, color="808080")
OPEX_CELL = "模型说明!B%d" % r

# ===================== Sheet2: 电池风险_汇总 =====================
ws2 = wb.create_sheet("电池风险_汇总")
ws2.column_dimensions['A'].width = 22; ws2.column_dimensions['B'].width = 14; ws2.column_dimensions['C'].width = 12
ws2['A1'] = "电池风险评分 · 汇总"; ws2['A1'].font = TITLE_FONT
ws2['A2'] = "数据源: device.battery_risk.stats (生成 %s)" % gen_at; ws2['A2'].font = Font(name=FNT, italic=True, size=9, color="808080")
put_table(ws2, 4, ["风险等级","数量","占比"],[
    ["高危", bat_stats["高危"], "=B5/$B$8"],
    ["预警", bat_stats["预警"], "=B6/$B$8"],
    ["正常", bat_stats["正常"], "=B7/$B$8"],
    ["合计", "=SUM(B5:B7)", "=B8/$B$8"],
], widths=[16,12,10])
for rr in (5,6,7,8):
    ws2.cell(rr,3).number_format = "0.0%"; ws2.cell(rr,3).font = BLACK
ws2.cell(8,1).font = Font(name=FNT, bold=True)
# category block
ws2['A10'] = "风险性质拆解"; ws2['A10'].font = SUB_FONT
put_table(ws2, 11, ["性质","数量"],[
    ["安全故障型(断电核心关注)", bat_stats["安全故障型"]],
    ["失联亏电型(可回收/未激活)", bat_stats["失联亏电型"]],
    ["高危中-安全故障型", bat_stats["安全故障_高危"]],
    ["高危中-失联亏电型", bat_stats["失联亏电_高危"]],
], widths=[30,12])
ws2['A17'] = "说明: 安全故障型=命中温度>45℃/压差>0.15V/循环>500/SOC<10 任一健康临界阈值，为锰铁锂骑行中断电的直接前兆，应优先锁定召回。"
ws2['A17'].font = Font(name=FNT, size=9, color="808080"); ws2['A17'].alignment = LEFT
ws2.merge_cells('A17:C18')

# ===================== Sheet3: 电池风险_明细 =====================
ws3 = wb.create_sheet("电池风险_明细")
ws3['A1'] = "安全故障型高危电池清单 (Top200, 断电风险最高)"; ws3['A1'].font = TITLE_FONT
hdr = ["电池SN","城市","区域","SOC%","温度℃","循环","压差mV","在线","评分","等级","性质","风险原因"]
rows = []
for x in br["top_safety_fault"][:200]:
    rows.append([x["sn"], x["city"], x["area"], x["soc"], x["temp"], x["cycle"], x["imb_mv"], x["online"], x["score"], x["level"], x["category"], "；".join(x["reasons"])])
end = put_table(ws3, 3, hdr, rows, widths=[20,10,10,8,8,8,9,8,7,8,12,40])

# ===================== Sheet4: 网点价值_汇总 =====================
ws4 = wb.create_sheet("网点价值_汇总")
ws4.column_dimensions['A'].width = 22; ws4.column_dimensions['B'].width = 14; ws4.column_dimensions['C'].width = 12
ws4['A1'] = "网点价值评估 · 汇总"; ws4['A1'].font = TITLE_FONT
ws4['A2'] = "数据源: site.value.stats (生成 %s)" % gen_at; ws4['A2'].font = Font(name=FNT, italic=True, size=9, color="808080")
put_table(ws4, 4, ["价值等级","数量","占比"],[
    ["S 明星(保留扩张)", tier_dist["S"], "=B5/$B$9"],
    ["A 潜力(优化提升)", tier_dist["A"], "=B6/$B$9"],
    ["B 边际(观察考核)", tier_dist["B"], "=B7/$B$9"],
    ["C 低价值(建议淘汰)", tier_dist["C"], "=B8/$B$9"],
    ["合计", "=SUM(B5:B8)", "=B9/$B$9"],
], widths=[20,12,10])
for rr in (5,6,7,8,9):
    ws4.cell(rr,3).number_format = "0.0%"; ws4.cell(rr,3).font = BLACK
ws4.cell(9,1).font = Font(name=FNT, bold=True)
# elimination block
ws4['A11'] = "淘汰候选（C级 + 已开业 + 30天换电<10）"; ws4['A11'].font = SUB_FONT
put_table(ws4, 12, ["指标","值"],[
    ["候选网点数", site_stats["eliminate_candidates"]],
    ["单点月运维成本(元)", "='%s'" % OPEX_CELL],
    ["预计年节省(元)", "=B13*B14*12"],
], widths=[20,16])
ws4.cell(14,2).font = GREEN; ws4.cell(14,2).fill = YEL_FILL   # B14 单点月运维成本(跨表引用·黄色假设)
ws4.cell(15,2).font = BLACK; ws4.cell(15,2).number_format = "#,##0"  # B15 预计年节省(公式)
ws4['A16'] = "注: 年节省 = 候选数 × 单点月运维成本 × 12；单点月运维成本为估算假设(见模型说明)，改之自动重算。"
ws4['A16'].font = Font(name=FNT, size=9, color="808080"); ws4['A16'].alignment = LEFT
ws4.merge_cells('A16:C17')

# ===================== Sheet5: 网点价值_明细 =====================
ws5 = wb.create_sheet("网点价值_明细")
ws5['A1'] = "淘汰候选网点明细 (C级+已开业+30天换电<10, 共%d个)" % len(sv["eliminate_candidates"]); ws5['A1'].font = TITLE_FONT
hdr = ["网点ID","名称","城市","区域","audit_status","30天换电","柜数","柜状态","评分","等级","建议动作"]
rows = []
for x in sv["eliminate_candidates"]:
    rows.append([x["id"], (x["name"] or "")[:24], x["city"], x["area"], x["audit_status"], x["swap_30d"], x["cabinet_count"], x["cabinet_status"], x["score"], x["tier"], x["action"]])
end = put_table(ws5, 3, hdr, rows, widths=[12,24,10,10,14,10,7,10,7,7,20])
# top S sites appended for contrast
ws5.cell(end+2, 1, "明星网点 Top15 (S级, 保留扩张)").font = SUB_FONT
hdr2 = ["网点ID","名称","城市","30天换电","柜数","评分"]
rows2 = []
for x in sv["top_sites"][:15]:
    rows2.append([x["id"], (x["name"] or "")[:24], x["city"], x["swap_30d"], x["cabinet_count"], x["score"]])
put_table(ws5, end+3, hdr2, rows2, widths=[12,24,10,10,7,7])

# freeze header rows
for s in (ws3, ws5):
    s.freeze_panes = "A4"

wb.calculation.fullCalcOnLoad = True
OUT = "docs/分析原型_网点价值与电池风险.xlsx"
wb.save(OUT)
print("SAVED", OUT)
print("电池: 高危=%d 预警=%d 正常=%d | 安全故障型=%d 失联亏电型=%d" % (
    bat_stats["高危"], bat_stats["预警"], bat_stats["正常"], bat_stats["安全故障型"], bat_stats["失联亏电型"]))
print("网点: S=%d A=%d B=%d C=%d | 淘汰候选=%d | 年节省估算=%s" % (
    tier_dist["S"], tier_dist["A"], tier_dist["B"], tier_dist["C"],
    site_stats["eliminate_candidates"], format(site_stats["eliminate_candidates"]*OPEX*12, ",")))
