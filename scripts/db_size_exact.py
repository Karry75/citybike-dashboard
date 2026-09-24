# -*- coding: utf-8 -*-
"""精确统计：全表 COUNT(*) + 抽样估算导出体积。"""
import json, sys, time, io, csv
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import pymysql

CFG = json.load(open('D:/workboddy file/dudu分析/citybike_backup/config/backup_config.json', encoding='utf-8'))
DB = CFG['database']
OUT = 'D:/workboddy file/dudu分析/citybike_backup/data/_db_size_report.json'

conn = pymysql.connect(host=CFG['host'], port=CFG['port'], user=CFG['user'],
                       password=CFG['password'], database=DB,
                       charset=CFG.get('charset', 'utf8mb4'),
                       connect_timeout=15, read_timeout=1200)
cur = conn.cursor()

cur.execute(f"""SELECT table_name, table_rows, data_length, index_length
                FROM information_schema.tables WHERE table_schema='{DB}'""")
meta = {r[0]: {'meta_rows': r[1] or 0, 'data_len': r[2] or 0, 'idx_len': r[3] or 0}
        for r in cur.fetchall()}
tables = sorted(meta.keys())
print(f'TABLES={len(tables)}', flush=True)

# 列数
cur.execute(f"""SELECT table_name, COUNT(*) FROM information_schema.columns
                WHERE table_schema='{DB}' GROUP BY table_name""")
cols = dict(cur.fetchall())

report = {}
t0 = time.time()
fails = []
for i, t in enumerate(tables, 1):
    rec = dict(meta[t]); rec['cols'] = cols.get(t, 0)
    try:
        cur.execute(f'SELECT COUNT(*) FROM `{t}`')
        rec['exact_rows'] = cur.fetchone()[0]
    except Exception as e:
        rec['exact_rows'] = None
        rec['err'] = f'{type(e).__name__}:{str(e)[:80]}'
        fails.append(t)
    report[t] = rec
    if i % 50 == 0:
        print(f'  counted {i}/{len(tables)}  {time.time()-t0:.0f}s', flush=True)

total_exact = sum(v['exact_rows'] or 0 for v in report.values())
print(f'COUNT_DONE {time.time()-t0:.0f}s  TOTAL_EXACT_ROWS={total_exact:,}  fails={len(fails)}', flush=True)

# --- 抽样估算导出行宽（CSV utf-8 与 JSON）---
ranked = sorted([t for t in tables if (report[t]['exact_rows'] or 0) > 0],
                key=lambda t: -(report[t]['exact_rows'] or 0))
print('SAMPLING top tables for byte-width...', flush=True)
SAMPLE_N = 200
for t in ranked:
    r = report[t]
    try:
        cur.execute(f'SELECT * FROM `{t}` LIMIT {SAMPLE_N}')
        rows = cur.fetchall()
        if not rows:
            continue
        colnames = [d[0] for d in cur.description]
        buf = io.StringIO()
        w = csv.writer(buf, lineterminator='\n')
        for row in rows:
            w.writerow(['' if v is None else str(v) for v in row])
        csv_bytes = len(buf.getvalue().encode('utf-8'))
        json_bytes = len(json.dumps(
            [dict(zip(colnames, ['' if v is None else str(v) for v in row])) for row in rows],
            ensure_ascii=False).encode('utf-8'))
        r['csv_bpr'] = csv_bytes / len(rows)
        r['json_bpr'] = json_bytes / len(rows)
        r['sampled'] = len(rows)
    except Exception as e:
        r['sample_err'] = f'{type(e).__name__}:{str(e)[:60]}'

# 全局平均行宽（按已抽样表加权），用于未抽到样的表兜底
sampled = [v for v in report.values() if v.get('csv_bpr')]
avg_csv = sum(v['csv_bpr'] for v in sampled) / len(sampled) if sampled else 200
avg_json = sum(v['json_bpr'] for v in sampled) / len(sampled) if sampled else 500

est_csv = est_json = 0
for t, v in report.items():
    n = v['exact_rows'] or 0
    c = v.get('csv_bpr', avg_csv)
    j = v.get('json_bpr', avg_json)
    v['est_csv_bytes'] = int(n * c)
    v['est_json_bytes'] = int(n * j)
    est_csv += v['est_csv_bytes']
    est_json += v['est_json_bytes']

summary = {
    'db': DB,
    'table_count': len(tables),
    'tables_with_rows': len([t for t in tables if (report[t]['exact_rows'] or 0) > 0]),
    'total_exact_rows': total_exact,
    'total_meta_rows': sum(v['meta_rows'] for v in report.values()),
    'adb_data_length_bytes': sum(v['data_len'] for v in report.values()),
    'adb_index_length_bytes': sum(v['idx_len'] for v in report.values()),
    'est_csv_bytes': est_csv,
    'est_json_bytes': est_json,
    'avg_csv_bytes_per_row': round(avg_csv, 1),
    'avg_json_bytes_per_row': round(avg_json, 1),
    'count_failed_tables': fails,
    'sampled_tables': len(sampled),
}
json.dump({'summary': summary, 'tables': report},
          open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

print('\n===== SUMMARY =====')
for k, v in summary.items():
    if k == 'count_failed_tables':
        print(f'{k}: {len(v)} {v[:5]}')
    else:
        print(f'{k}: {v:,}' if isinstance(v, int) else f'{k}: {v}')
print(f"EST_CSV = {est_csv/1024**3:.2f} GB")
print(f"EST_JSON = {est_json/1024**3:.2f} GB")
print('TOP20 BY ROWS:')
for t in ranked[:20]:
    v = report[t]
    print(f"  {t:<42} rows={v['exact_rows']:>12,}  csv≈{v['est_csv_bytes']/1024**3:>7.2f}GB")
conn.close()
