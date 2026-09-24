# -*- coding: utf-8 -*-
"""探测 ADB 库规模：表数量、总行数、存储占用。"""
import json, sys, time, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import pymysql

CFG = json.load(open('D:/workboddy file/dudu分析/citybike_backup/config/backup_config.json', encoding='utf-8'))
DB = CFG['database']

conn = pymysql.connect(host=CFG['host'], port=CFG['port'], user=CFG['user'],
                       password=CFG['password'], database=DB,
                       charset=CFG.get('charset', 'utf8mb4'),
                       connect_timeout=CFG.get('connect_timeout', 15),
                       read_timeout=CFG.get('read_timeout', 600))
cur = conn.cursor()
print('CONN_OK', DB)

def try_sql(label, sql):
    try:
        t = time.time()
        cur.execute(sql)
        rows = cur.fetchall()
        print(f'--- {label} OK ({time.time()-t:.2f}s) rows={len(rows)}')
        return rows
    except Exception as e:
        print(f'--- {label} FAIL: {type(e).__name__}: {str(e)[:200]}')
        return None

# 1. 表清单
rows = try_sql('TABLE_LIST', f"SELECT table_name FROM information_schema.tables WHERE table_schema='{DB}'")
tables = [r[0] for r in rows] if rows else []
print('TABLE_COUNT =', len(tables))

# 2. information_schema 自带大小/行数
r2 = try_sql('IS_TABLES_SIZE', f"""SELECT table_name, table_rows, data_length, index_length
    FROM information_schema.tables WHERE table_schema='{DB}'""")
if r2:
    tot_rows = sum((x[1] or 0) for x in r2)
    tot_data = sum((x[2] or 0) for x in r2)
    tot_idx = sum((x[3] or 0) for x in r2)
    print(f'IS_SUM rows={tot_rows:,} data={tot_data/1024**3:.3f}GB index={tot_idx/1024**3:.3f}GB')
    nz = [x for x in r2 if (x[2] or 0) > 0]
    print('IS_nonzero_data_tables =', len(nz))

# 3. ADB 专有元数据视图
for v in ['information_schema.kepler_meta_table_space',
          'information_schema.table_space',
          'information_schema.kepler_meta_shard_space']:
    try_sql('PROBE_' + v, f"SELECT * FROM {v} LIMIT 3")

json.dump(tables, open('D:/workboddy file/dudu分析/citybike_backup/data/_tables_probe.json', 'w', encoding='utf-8'), ensure_ascii=False)
print('TABLES_SAVED')
conn.close()
