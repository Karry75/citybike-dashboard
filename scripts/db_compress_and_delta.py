# -*- coding: utf-8 -*-
"""实测 gzip 压缩比 + 今日增量行数估算。"""
import json, sys, io, csv, gzip, time, datetime
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
import pymysql

CFG = json.load(open('D:/workboddy file/dudu分析/citybike_backup/config/backup_config.json', encoding='utf-8'))
DB = CFG['database']
REP = 'D:/workboddy file/dudu分析/citybike_backup/data/_db_size_report.json'
rep = json.load(open(REP, encoding='utf-8'))
tables = rep['tables']

conn = pymysql.connect(host=CFG['host'], port=CFG['port'], user=CFG['user'],
                       password=CFG['password'], database=DB, charset='utf8mb4',
                       connect_timeout=15, read_timeout=180)
cur = conn.cursor()

# ---------- 1. 实测 gzip 压缩比 ----------
print('=== gzip 压缩比实测 ===')
probe = ['t_scan_log', 't_device_online_log', 't_bike_ride_log',
         't_exchange_order', 't_queue_message', 't_exchange_order_check_log']
ratios = []
for t in probe:
    try:
        cur.execute(f'SELECT * FROM `{t}` LIMIT 2000')
        rows = cur.fetchall()
        if not rows:
            continue
        buf = io.StringIO()
        w = csv.writer(buf, lineterminator='\n')
        for r in rows:
            w.writerow(['' if v is None else str(v) for v in r])
        raw = buf.getvalue().encode('utf-8')
        gz = gzip.compress(raw, compresslevel=6)
        ratio = len(raw) / len(gz)
        weight = tables.get(t, {}).get('est_csv_bytes', 0)
        ratios.append((t, ratio, weight))
        print(f'  {t:<34} 原始{len(raw)/1024:>8.0f}KB → gz{len(gz)/1024:>7.0f}KB  压缩比 {ratio:>5.2f}:1')
    except Exception as e:
        print(f'  {t:<34} FAIL {str(e)[:50]}')

tot_w = sum(r[2] for r in ratios) or 1
w_ratio = sum(r[1] * r[2] for r in ratios) / tot_w
print(f'  → 按体积加权平均压缩比 = {w_ratio:.2f}:1')

est_csv = rep['summary']['est_csv_bytes']
est_json = rep['summary']['est_json_bytes']
print(f'\nCSV  未压缩 {est_csv/1024**3:.1f} GB → gzip 后约 {est_csv/w_ratio/1024**3:.1f} GB')
print(f'JSON 未压缩 {est_json/1024**3:.1f} GB → gzip 后约 {est_json/w_ratio/1024**3:.1f} GB')

# ---------- 2. 今日增量 ----------
print('\n=== 今日增量（create_time >= 今日 UTC 零点）===')
now = datetime.datetime.now(datetime.timezone.utc)
d0 = int(datetime.datetime(now.year, now.month, now.day,
                           tzinfo=datetime.timezone.utc).timestamp() * 1000)
print(f'UTC 零点毫秒戳 = {d0}')

cur.execute(f"""SELECT table_name FROM information_schema.columns
                WHERE table_schema='{DB}' AND column_name='create_time'""")
has_ct = [r[0] for r in cur.fetchall()]
print(f'含 create_time 的表：{len(has_ct)} / {len(tables)}')

# 只统计体积占比大的表（估算 >0.1GB），其余按比例外推
big = [t for t in has_ct if tables.get(t, {}).get('est_csv_bytes', 0) > 0.1 * 1024**3]
big.sort(key=lambda t: -tables[t]['est_csv_bytes'])
print(f'统计 {len(big)} 张主要表的今日增量...')

delta_rows = 0
delta_bytes = 0
detail = []
for t in big:
    try:
        cur.execute(f'SELECT COUNT(*) FROM `{t}` WHERE create_time >= {d0}')
        n = cur.fetchone()[0]
    except Exception as e:
        continue
    v = tables[t]
    bpr = v.get('csv_bpr_sql', v.get('csv_bpr', 0))
    b = n * bpr
    delta_rows += n
    delta_bytes += b
    if n > 0:
        detail.append((t, n, b))

detail.sort(key=lambda x: -x[2])
print(f'\n今日新增（主要表）：{delta_rows:,} 行，CSV ≈ {delta_bytes/1024**3:.2f} GB，'
      f'gzip ≈ {delta_bytes/w_ratio/1024**2:.0f} MB')
print('TOP10 增量表：')
for t, n, b in detail[:10]:
    print(f'  {t:<44}{n:>10,} 行  {b/1024**2:>9.1f} MB')

rep['summary']['gzip_ratio_measured'] = round(w_ratio, 2)
rep['summary']['est_csv_gz_bytes'] = int(est_csv / w_ratio)
rep['summary']['est_json_gz_bytes'] = int(est_json / w_ratio)
rep['summary']['today_delta_rows_major'] = delta_rows
rep['summary']['today_delta_csv_bytes'] = int(delta_bytes)
rep['summary']['today_utc_d0_ms'] = d0
json.dump(rep, open(REP, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('\nSAVED')
conn.close()
