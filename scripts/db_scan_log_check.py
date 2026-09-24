# -*- coding: utf-8 -*-
"""定向复核 t_scan_log 等宽表：逐列平均字节数（用 SQL 聚合，不拉数据）。"""
import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
import pymysql

CFG = json.load(open('D:/workboddy file/dudu分析/citybike_backup/config/backup_config.json', encoding='utf-8'))
DB = CFG['database']
TARGETS = sys.argv[1:] or ['t_scan_log']

conn = pymysql.connect(host=CFG['host'], port=CFG['port'], user=CFG['user'],
                       password=CFG['password'], database=DB,
                       charset='utf8mb4', connect_timeout=15, read_timeout=600)
cur = conn.cursor()

out = {}
for T in TARGETS:
    print(f'\n===== {T} =====')
    cur.execute(f"""SELECT column_name, data_type FROM information_schema.columns
                    WHERE table_schema='{DB}' AND table_name='{T}' ORDER BY ordinal_position""")
    cols = cur.fetchall()
    print(f'列数: {len(cols)}')

    # 用 SQL 直接算每列平均字节长度（服务端聚合，不传输大数据）
    exprs = [f"AVG(LENGTH(CAST(`{c}` AS CHAR)))" for c, _ in cols]
    total_expr = ' + '.join([f"COALESCE(AVG(LENGTH(CAST(`{c}` AS CHAR))),0)" for c, _ in cols])
    try:
        cur.execute(f"SELECT {total_expr} FROM `{T}`")
        avg_total = float(cur.fetchone()[0] or 0)
    except Exception as e:
        print('全表聚合失败，改用子集:', str(e)[:100])
        cur.execute(f"SELECT {total_expr} FROM (SELECT * FROM `{T}` LIMIT 100000) x")
        avg_total = float(cur.fetchone()[0] or 0)

    # 每列明细（找出巨型字段）
    per_col = []
    for c, dt in cols:
        try:
            cur.execute(f"SELECT COALESCE(AVG(LENGTH(CAST(`{c}` AS CHAR))),0), COALESCE(MAX(LENGTH(CAST(`{c}` AS CHAR))),0) FROM `{T}`")
            a, m = cur.fetchone()
            per_col.append((c, dt, float(a or 0), int(m or 0)))
        except Exception:
            per_col.append((c, dt, -1, -1))
    per_col.sort(key=lambda x: -x[2])
    print(f'{"列名":<34}{"类型":<12}{"平均B":>10}{"最大B":>12}')
    for c, dt, a, m in per_col[:12]:
        print(f'{c:<34}{dt:<12}{a:>10.1f}{m:>12,}')

    csv_bpr = avg_total + len(cols)  # 逗号+换行开销
    cur.execute(f'SELECT COUNT(*) FROM `{T}`')
    n = cur.fetchone()[0]
    print(f'-> 精确行数 {n:,}，SQL 实测平均行宽 {csv_bpr:.1f} B，导出 CSV ≈ {n*csv_bpr/1024**3:.2f} GB')
    out[T] = {'rows': n, 'csv_bpr_sql': csv_bpr, 'est_csv_gb': n * csv_bpr / 1024**3,
              'per_col': [{'col': c, 'type': dt, 'avg': a, 'max': m} for c, dt, a, m in per_col]}

json.dump(out, open('D:/workboddy file/dudu分析/citybike_backup/data/_wide_table_check.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print('\nSAVED')
conn.close()
