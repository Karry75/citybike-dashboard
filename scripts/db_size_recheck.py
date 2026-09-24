# -*- coding: utf-8 -*-
"""复核异常大行宽的表：多点分散抽样，修正体积估算。"""
import json, sys, io, csv, random
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import pymysql

CFG = json.load(open('D:/workboddy file/dudu分析/citybike_backup/config/backup_config.json', encoding='utf-8'))
REP = 'D:/workboddy file/dudu分析/citybike_backup/data/_db_size_report.json'
rep = json.load(open(REP, encoding='utf-8'))
tables = rep['tables']

conn = pymysql.connect(host=CFG['host'], port=CFG['port'], user=CFG['user'],
                       password=CFG['password'], database=CFG['database'],
                       charset='utf8mb4', connect_timeout=15, read_timeout=900)
cur = conn.cursor()

# 挑出估算体积 >1GB 或行宽 >2000B 的表复核
cand = [t for t, v in tables.items()
        if v.get('est_csv_bytes', 0) > 1 * 1024**3 or v.get('csv_bpr', 0) > 2000]
cand.sort(key=lambda t: -tables[t]['est_csv_bytes'])
print(f'RECHECK {len(cand)} tables (multi-offset sampling)\n', flush=True)

def sample_width(t, n_rows):
    """三点分散抽样：头/中/尾各取 300 行"""
    widths, total_rows, colnames = [], 0, None
    offsets = [0]
    if n_rows > 1000:
        offsets = [0, max(0, n_rows // 2 - 150), max(0, n_rows - 400)]
    for off in offsets:
        try:
            cur.execute(f'SELECT * FROM `{t}` LIMIT 300 OFFSET {off}')
            rows = cur.fetchall()
        except Exception as e:
            continue
        if not rows:
            continue
        if colnames is None:
            colnames = [d[0] for d in cur.description]
        buf = io.StringIO()
        w = csv.writer(buf, lineterminator='\n')
        for r in rows:
            w.writerow(['' if v is None else str(v) for v in r])
        widths.append(len(buf.getvalue().encode('utf-8')))
        total_rows += len(rows)
    if not total_rows:
        return None, None, 0
    csv_bpr = sum(widths) / total_rows
    return csv_bpr, colnames, total_rows

changed = []
for t in cand:
    v = tables[t]
    n = v['exact_rows'] or 0
    old = v.get('csv_bpr', 0)
    new, colnames, ns = sample_width(t, n)
    if new is None:
        continue
    v['csv_bpr_recheck'] = new
    v['recheck_sampled'] = ns
    v['est_csv_bytes'] = int(n * new)
    v['est_json_bytes'] = int(n * new * (v.get('json_bpr', 1) / max(old, 1) if old else 1.5))
    if old and abs(new - old) / old > 0.3:
        changed.append((t, old, new, n))
        print(f'  ⚠ {t:<44} {old:>9.0f} → {new:>9.0f} B/行  ({n:,} 行)  修正后 {n*new/1024**3:.2f}GB', flush=True)

print(f'\n显著修正表数：{len(changed)}')

# 重算总量
est_csv = sum(v.get('est_csv_bytes', 0) for v in tables.values())
est_json = sum(v.get('est_json_bytes', 0) for v in tables.values())
rep['summary']['est_csv_bytes'] = est_csv
rep['summary']['est_json_bytes'] = est_json
rep['summary']['rechecked_tables'] = len(cand)
json.dump(rep, open(REP, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

print(f'\n===== 修正后总量 =====')
print(f'EST_CSV  = {est_csv/1024**3:.2f} GB')
print(f'EST_JSON = {est_json/1024**3:.2f} GB')
print(f'ADB data_length = {rep["summary"]["adb_data_length_bytes"]/1024**3:.2f} GB')
print('\nTOP15 BY EXPORT SIZE:')
top = sorted(tables.items(), key=lambda kv: -kv[1].get('est_csv_bytes', 0))[:15]
for t, v in top:
    bpr = v.get('csv_bpr_recheck', v.get('csv_bpr', 0))
    print(f"  {t:<44} {v['exact_rows']:>12,} 行  {bpr:>7.0f}B/行  {v['est_csv_bytes']/1024**3:>7.2f}GB")
conn.close()
