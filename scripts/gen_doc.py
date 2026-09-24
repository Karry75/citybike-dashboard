import json, os, datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA = os.path.join(BASE, "data", "schema_report.json")
OUT = os.path.join(BASE, "docs", "DATABASE_BACKUP_KNOWLEDGE.md")

with open(SCHEMA, encoding="utf-8") as f:
    rep = json.load(f)

total_rows = sum(v["rows"] for v in rep.values())
total_tables = len(rep)
giant = {k: v["rows"] for k, v in rep.items() if v["rows"] >= 5_000_000}

CAT = {
    "换电/订单(t_exchange*)": lambda t: t.startswith("t_exchange"),
    "车辆(t_bike*)": lambda t: t.startswith("t_bike"),
    "电池(t_battery*)": lambda t: t.startswith("t_battery"),
    "站点/门店(t_site*)": lambda t: t.startswith("t_site"),
    "用户(t_user*)": lambda t: t.startswith("t_user"),
    "监控事件(t_monitor*)": lambda t: t.startswith("t_monitor"),
    "财务/结算(t_pay/t_expense/t_profit/t_contract*)": lambda t: t.startswith(("t_pay", "t_expense", "t_profit", "t_contract")),
    "营销/客服(t_coupon/t_score/t_banner/t_feedback/t_reception*)": lambda t: t.startswith(("t_coupon", "t_score", "t_banner", "t_feedback", "t_reception")),
    "设备(t_device*)": lambda t: t.startswith("t_device"),
    "基础/租赁(zc_*)": lambda t: t.startswith("zc_"),
}
cats = {c: [] for c in CAT}
other = []
for t, v in rep.items():
    placed = False
    for c, fn in CAT.items():
        if fn(t):
            cats[c].append((t, v["rows"]))
            placed = True
            break
    if not placed:
        other.append((t, v["rows"]))

L = []
L.append("# citybike_pro 数据库备份知识库")
L.append("")
L.append(f"> 生成时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ")
L.append(f"> 用途: 跨设备/离线查看的数据库备份说明；当源库不可达时作为恢复依据。")
L.append("")
L.append("## 1. 数据库连接信息（源库）")
L.append("")
L.append("| 项 | 值 |")
L.append("|---|---|")
L.append("| 类型 | 阿里云 AnalyticDB MySQL（兼容 MySQL 5.6）|")
L.append("| host | db.example.com |")
L.append("| port | 3306 |")
L.append("| user | citybike_pro |")
L.append("| database | sharing-citybike-pro |")
L.append("| 密码 | **本地 config 中保存，不在此文档** |")
L.append("")
L.append("## 2. 规模概览")
L.append("")
L.append(f"- 表总数: **{total_tables}**")
L.append(f"- 总行数: **{total_rows:,}** （约 {total_rows/1e8:.2f} 亿行）")
L.append(f"- 时间戳字段: 全部为 13 位毫秒(ms) 的 bigint（create_time / update_time 等）")
L.append("")
L.append("### 巨型表（>=500 万行，已从“全量快照”中排除，但“增量”按天仍覆盖）")
L.append("")
L.append("| 表 | 行数 |")
L.append("|---|---:|")
for t, r in sorted(giant.items(), key=lambda x: -x[1]):
    L.append(f"| {t} | {r:,} |")
L.append("")
L.append("## 3. 表分类（业务视角）")
L.append("")
for c, items in cats.items():
    if not items:
        continue
    L.append(f"### {c}（{len(items)} 张表）")
    L.append("")
    L.append("| 表 | 行数 | 增量列 |")
    L.append("|---|---:|---|")
    for t, r in sorted(items, key=lambda x: -x[1]):
        inc = rep[t]["inc_col"] or "-"
        L.append(f"| {t} | {r:,} | {inc} |")
    L.append("")
if other:
    L.append(f"### 其他（{len(other)} 张表）")
    L.append("")
    for t, r in sorted(other, key=lambda x: -x[1])[:30]:
        L.append(f"- {t} ({r:,})")
    if len(other) > 30:
        L.append(f"- ... 共 {len(other)} 张")
    L.append("")

L.append("## 4. 备份策略")
L.append("")
L.append("- **全量快照(full_snapshot)**: 导出 389 张业务核心表（排除约 33 张巨型遥测/日志表），作为“数据库权限关闭后的最新完整数据”安全副本。")
L.append("- **增量(incremental)**: 每天导出**全部 422 张表**“最新一天”的数据（按 inc_col 毫秒范围分区），满足“数据持续更新则永远保留最新一天”。")
L.append("- **保留策略**: 仅保留**最新一份**全量快照 + 仅保留**最新一天**的增量；更早的自动清理。")
L.append("")
L.append("## 5. 本地目录结构")
L.append("")
L.append("```")
L.append("citybike_backup/")
L.append("├─ data/")
L.append("│  ├─ full_snapshot/<日期>/<表>.csv.gz   # 全量核心表(最新一份保留)")
L.append("│  ├─ incremental/<日期>/<表>.csv.gz     # 全表最新一天增量(仅保留最新一天)")
L.append("│  ├─ schema_report.json                 # 表结构清单(行数/字段/增量列)")
L.append("│  └─ *_run.log                           # 运行日志")
L.append("├─ docs/DATABASE_BACKUP_KNOWLEDGE.md      # 本文件(ima 知识库用)")
L.append("└─ scripts/backup.py                      # 备份管道(可重跑/可调度)")
L.append("```")
L.append("")
L.append("## 6. 灾备恢复（源库不可达时）")
L.append("")
L.append("1. **最新完整数据**: 取 `data/full_snapshot/` 下最新日期目录，解压 `*.csv.gz` 即得各表全量。")
L.append("2. **最新一天数据**: 取 `data/incremental/` 下最新日期目录，含全部表当天变更。")
L.append("3. **离线查询**: 用 DuckDB / pandas 直接读 csv.gz，例如：")
L.append("   ```python")
L.append("   import duckdb")
L.append("   duckdb.sql(\"SELECT * FROM read_csv_auto('data/full_snapshot/2026-07-25/t_exchange_order.csv.gz') LIMIT 10\")")
L.append("   ```")
L.append("4. **回写数据库**: 将 csv 通过 `LOAD DATA` / `INSERT` 导入目标实例（需按目标表结构建表）。")
L.append("")
L.append("## 7. 云盘 / ima 知识库 上传指引")
L.append("")
L.append("- **云盘（跨设备/离线查看）**: 将 `data/` 整个目录压缩上传至任意云盘（百度网盘/微云/腾讯文档等）。")
L.append("- **ima 知识库**: 本 Markdown 文档 + 各表 `MANIFEST.json` 可作为知识条目上传，支持全文检索。")
L.append("- 当前 WorkBuddy 的 ima / 云盘连接器为断开状态；启用连接器后，可由本管道一键补推。")
L.append("")
L.append("---")
L.append("> 本文件由备份管道自动生成，仅含结构与恢复说明，不含敏感凭据。")

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(L))
print("WROTE", OUT, "bytes=", os.path.getsize(OUT))
