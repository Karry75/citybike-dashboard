# -*- coding: utf-8 -*-
"""生成数据库规模评估 Markdown 报告。"""
import json, io, sys, datetime
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

REP = 'D:/workboddy file/dudu分析/citybike_backup/data/_db_size_report.json'
OUT = 'D:/workboddy file/dudu分析/数据库规模与备份体积评估.md'
rep = json.load(open(REP, encoding='utf-8'))
S, T = rep['summary'], rep['tables']
GB = 1024 ** 3
MB = 1024 ** 2
ratio = S.get('gzip_ratio_measured', 8.06)

top = sorted(T.items(), key=lambda kv: -kv[1].get('est_csv_bytes', 0))[:25]
top_rows = sorted(T.items(), key=lambda kv: -(kv[1].get('exact_rows') or 0))[:15]

csv_b, json_b = S['est_csv_bytes'], S['est_json_bytes']
lines = []
A = lines.append

A('# 城市换电数据库 · 规模与备份体积评估')
A('')
A(f"> 探测时间：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} (+0800)　"
  f"库：`{S['db']}`　实例：AnalyticDB MySQL（阿里云）")
A('')
A('## 一、核心结论')
A('')
A('| 指标 | 数值 |')
A('|---|---|')
A(f"| 表总数 | **{S['table_count']} 张**（其中 {S['tables_with_rows']} 张有数据，{S['table_count']-S['tables_with_rows']} 张空表） |")
A(f"| 总数据行数 | **{S['total_exact_rows']:,} 行**（约 8.05 亿，全表精确 COUNT） |")
A(f"| 云端存储占用 | 数据 {S['adb_data_length_bytes']/GB:.1f} GB ＋ 索引 {S['adb_index_length_bytes']/GB:.1f} GB ＝ **{(S['adb_data_length_bytes']+S['adb_index_length_bytes'])/GB:.1f} GB** |")
A(f"| 备份为 CSV（未压缩） | **≈ {csv_b/GB:.0f} GB** |")
A(f"| 备份为 CSV + gzip | **≈ {csv_b/ratio/GB:.0f} GB** ✅ 推荐 |")
A(f"| 备份为 JSON（未压缩） | ≈ {json_b/GB:.0f} GB |")
A(f"| 备份为 JSON + gzip | ≈ {json_b/ratio/GB:.0f} GB |")
A(f"| 实测 gzip 压缩比 | {ratio:.2f} : 1（按体积加权，6 张主力表实测） |")
A('')
A('**一句话回答**：全量备份到本地，未压缩约 **500 GB**，压缩后约 **62 GB**。')
A('')
A('## 二、磁盘容量校验（关键约束）')
A('')
A('| 方案 | 体积 | D 盘可用 388.6 GB | 判定 |')
A('|---|---|---|---|')
A(f"| CSV 未压缩 | {csv_b/GB:.0f} GB | 缺口 {(csv_b/GB-388.6):.0f} GB | ❌ **装不下** |")
A(f"| JSON 未压缩 | {json_b/GB:.0f} GB | 缺口 {(json_b/GB-388.6):.0f} GB | ❌ 装不下 |")
A(f"| CSV + gzip | {csv_b/ratio/GB:.0f} GB | 余 {(388.6-csv_b/ratio/GB):.0f} GB | ✅ 可行 |")
A(f"| JSON + gzip | {json_b/ratio/GB:.0f} GB | 余 {(388.6-json_b/ratio/GB):.0f} GB | ✅ 可行 |")
A('')
A('> 结论：**必须边导出边 gzip 压缩**，不能先落地未压缩文件再压缩，否则中途撑爆 D 盘。')
A('')
A('## 三、体积分布高度集中')
A('')
c1 = T['t_scan_log']['est_csv_bytes']
A(f"- `t_scan_log` 一张表占 **{c1/GB:.0f} GB**，即全库导出量的 **{c1/csv_b*100:.0f}%**。")
A(f"  - 原因：单行平均 {T['t_scan_log'].get('csv_bpr_sql', 0):,.0f} 字节，其中 `check_result` 字段平均约 15 KB JSON、`exchange_upload_info` 约 3.6 KB。")
A(f"  - 它只有 {T['t_scan_log']['exact_rows']:,} 行（行数排第 11），却是体积第 1。")
A(f"- 前 5 张表合计约 {sum(v['est_csv_bytes'] for _, v in top[:5])/GB:.0f} GB，占 "
  f"{sum(v['est_csv_bytes'] for _, v in top[:5])/csv_b*100:.0f}%。")
A('- **优化建议**：若可接受，排除或裁剪 `t_scan_log.check_result` 字段，导出量立降约 60%（→ 约 200 GB 未压缩 / 25 GB 压缩）。')
A('')
A('## 四、今日增量（若做每日增量备份）')
A('')
A('| 口径 | 行数 | CSV 未压缩 | gzip 后 |')
A('|---|---|---|---|')
A(f"| 今日已产生（北京 00:00 至今） | {S.get('bj_today_rows',0):,} | {S.get('bj_today_csv_bytes',0)/GB:.2f} GB | {S.get('bj_today_csv_bytes',0)/ratio/MB:.0f} MB |")
A(f"| 昨日完整 24 小时 | {S.get('bj_yesterday_rows',0):,} | {S.get('bj_yesterday_csv_bytes',0)/GB:.2f} GB | {S.get('bj_yesterday_csv_bytes',0)/ratio/MB:.0f} MB |")
A(f"| 今日全天外推 | ~777,000 | 0.35 GB | ~45 MB |")
A('')
A(f"> 日均增量约 **95 万行 / 0.5 GB 未压缩 / 63 MB 压缩**。按此速率，"
  f"增量备份一年约 23 GB（压缩后），成本可控。")
A('')
A('## 五、体积 TOP 25 表')
A('')
A('| # | 表名 | 行数 | 平均行宽 | CSV 体积 | gzip 后 |')
A('|---:|---|---:|---:|---:|---:|')
for i, (t, v) in enumerate(top, 1):
    bpr = v.get('csv_bpr_sql', v.get('csv_bpr', 0))
    A(f"| {i} | `{t}` | {v['exact_rows']:,} | {bpr:,.0f} B | "
      f"{v['est_csv_bytes']/GB:.2f} GB | {v['est_csv_bytes']/ratio/MB:,.0f} MB |")
A('')
A('## 六、行数 TOP 15 表')
A('')
A('| # | 表名 | 行数 | CSV 体积 |')
A('|---:|---|---:|---:|')
for i, (t, v) in enumerate(top_rows, 1):
    A(f"| {i} | `{t}` | {v['exact_rows']:,} | {v['est_csv_bytes']/GB:.2f} GB |")
A('')
A('## 七、方法与误差说明')
A('')
A('1. **行数为精确值**：对全部 422 张表逐一执行 `COUNT(*)`，0 张失败，耗时 28 秒。'
  f'元数据 `information_schema.table_rows` 报 {S["total_meta_rows"]:,}，'
  f'与精确值偏差 {abs(S["total_meta_rows"]-S["total_exact_rows"])/S["total_exact_rows"]*100:.1f}%（元数据为估算，以精确值为准）。')
A('2. **体积为估算值**：对 35 张大表用服务端 SQL 聚合（`AVG(LENGTH(...))`，2 万行子集）实测平均行宽；'
  '小表用 200 行抽样。复核中仅 3 张表偏差超 25%，已修正。整体误差预计在 ±10% 内。')
A('3. **压缩比为实测值**：对 6 张主力表各取 2000 行做真实 gzip(level 6)，按体积加权得 '
  f'{ratio:.2f}:1。日志类表压缩比高（`t_exchange_order_check_log` 达 12:1），业务表较低（`t_exchange_order` 4.3:1）。')
A('4. **云端 328 GB vs 导出 500 GB 的差异**：AnalyticDB 为列式存储且默认建全列索引，'
  '内部采用字典编码与压缩，故存储占用与文本导出体积无直接可比性。')
A('5. **未计入**：表结构 DDL、视图、存储过程（体积可忽略）。')
A('')

open(OUT, 'w', encoding='utf-8').write('\n'.join(lines))
print('WROTE', OUT, len('\n'.join(lines)), 'chars')
