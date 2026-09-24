# -*- coding: utf-8 -*-
"""稳健复核：对大表用「子集 SQL 聚合」重算行宽（避免大 OFFSET / 全表扫描导致的连接崩溃）。"""
import json, sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
import pymysql

CFG = json.load(open('D:/workboddy file/dudu分析/citybike_backup/config/backup_config.json', encoding='utf-8'))
DB = CFG['database']
REP = 'D:/workboddy file/dudu分析/citybike_backup/data/_db_size_report.json'
LOG = 'D:/workboddy file/dudu分析/citybike_backup/data/_recheck2_progress.json'
rep = json.load(open(REP, encoding='utf-8'))
tables = rep['tables']
SUBSET = 20000


def connect():
    return pymysql.connect(host=CFG['host'], port=CFG['port'], user=CFG['user'],
                           password=CFG['password'], database=DB, charset='utf8mb4',
                           connect_timeout=15, read_timeout=120)


conn = connect()
cur = conn.cursor()
cur.execute(f"""SELECT table_name, column_name FROM information_schema.columns
                WHERE table_schema='{DB}' ORDER BY table_name, ordinal_position""")
colmap = {}
for t, c in cur.fetchall():
    colmap.setdefault(t, []).append(c)

# 复核对象：估算 >0.5GB 的表（这些决定总量）
cand = [t for t, v in tables.items() if v.get('est_csv_bytes', 0) > 0.5 * 1024**3]
cand.sort(key=lambda t: -tables[t]['est_csv_bytes'])
print(f'复核 {len(cand)} 张大表（子集 {SUBSET} 行 SQL 聚合）\n')

done = 0
for t in cand:
    v = tables[t]
    n = v['exact_rows'] or 0
    cols = colmap.get(t, [])
    if not cols or n == 0:
        continue
    expr = ' + '.join([f"COALESCE(LENGTH(CAST(`{c}` AS CHAR)),0)" for c in cols])
    sel = ', '.join([f"`{c}`" for c in cols])
    q = f"SELECT AVG({expr}) FROM (SELECT {sel} FROM `{t}` LIMIT {SUBSET}) x"
    old = v.get('csv_bpr', 0)
    try:
        cur.execute(q)
        raw = cur.fetchone()[0]
        bpr = float(raw or 0) + len(cols)  # 分隔符+换行
    except Exception as e:
        print(f'  ! {t:<44} 聚合失败({str(e)[:40]}) 保留原估算')
        try:
            conn.close()
        except Exception:
            pass
        conn = connect(); cur = conn.cursor()
        continue
    v['csv_bpr_sql'] = bpr
    v['est_csv_bytes'] = int(n * bpr)
    v['est_json_bytes'] = int(n * bpr * 1.55)
    flag = '⚠修正' if old and abs(bpr - old) / old > 0.25 else '  一致'
    print(f'{flag} {t:<44} {old:>8.0f}→{bpr:>8.0f} B/行  {n*bpr/1024**3:>7.2f}GB')
    done += 1
    if done % 10 == 0:
        json.dump(rep, open(REP, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

# 未复核的小表沿用抽样估算
est_csv = sum(v.get('est_csv_bytes', 0) for v in tables.values())
est_json = sum(v.get('est_json_bytes', 0) for v in tables.values())
rep['summary']['est_csv_bytes'] = est_csv
rep['summary']['est_json_bytes'] = est_json
rep['summary']['rechecked_big_tables'] = done
json.dump(rep, open(REP, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

print(f'\n===== 修正后总量 =====')
print(f'总行数        = {rep["summary"]["total_exact_rows"]:,}')
print(f'CSV 导出估算  = {est_csv/1024**3:.2f} GB')
print(f'JSON 导出估算 = {est_json/1024**3:.2f} GB')
print(f'gzip 压缩后约 = {est_csv*0.18/1024**3:.2f} GB (按 CSV 压缩比 ~5.5:1)')
print('\nTOP20 导出体积:')
top = sorted(tables.items(), key=lambda kv: -kv[1].get('est_csv_bytes', 0))[:20]
for t, v in top:
    bpr = v.get('csv_bpr_sql', v.get('csv_bpr', 0))
    print(f"  {t:<44}{v['exact_rows']:>13,} 行 {bpr:>8.0f}B/行 {v['est_csv_bytes']/1024**3:>8.2f}GB")
conn.close()
