import json, pymysql

cfg = json.load(open('config/backup_config.json', encoding='utf-8'))
conn = pymysql.connect(host=cfg['host'], port=cfg['port'], user=cfg['user'],
                       password=cfg['password'], database=cfg['database'],
                       charset='utf8mb4', connect_timeout=15, read_timeout=600)
cur = conn.cursor(pymysql.cursors.DictCursor)
def q(sql, n=None):
    cur.execute(sql)
    return cur.fetchmany(n) if n else cur.fetchall()

# find tables matching keywords
cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema=%s", (cfg['database'],))
allt = [r['table_name'] for r in cur.fetchall()]
import re
for kw in ['agency','industry','site_type','type','maker']:
    matches = [t for t in allt if kw in t]
    print(f'TABLES containing "{kw}":', matches)

print('\n=== sample t_exchange_last_upload cols+1row ===')
cur.execute("SELECT * FROM t_exchange_last_upload LIMIT 1")
row = cur.fetchone()
print('COLUMNS:', [d[0] for d in cur.description])
if row:
    for k,v in row.items():
        print(f'  {k} = {repr(v)[:80]}')

print('\n=== sample t_site_device_statistics cols+1row ===')
cur.execute("SELECT * FROM t_site_device_statistics LIMIT 1")
row = cur.fetchone()
print('COLUMNS:', [d[0] for d in cur.description])
if row:
    for k,v in row.items():
        print(f'  {k} = {repr(v)[:80]}')

print('\n=== sample t_battery_last_upload cols+1row ===')
cur.execute("SELECT * FROM t_battery_last_upload LIMIT 1")
row = cur.fetchone()
print('COLUMNS:', [d[0] for d in cur.description])
if row:
    for k,v in row.items():
        print(f'  {k} = {repr(v)[:80]}')

print('\n=== sample t_battery_status cols+1row ===')
cur.execute("SELECT * FROM t_battery_status LIMIT 1")
row = cur.fetchone()
print('COLUMNS:', [d[0] for d in cur.description])
if row:
    for k,v in row.items():
        print(f'  {k} = {repr(v)[:80]}')

print('\n=== t_exchange_model sample ===')
cur.execute("SELECT * FROM t_exchange_model LIMIT 2")
for r in cur.fetchall():
    print(' ', {k:r[k] for k in ['device_type_id','show_name','name','code']})

print('\n=== t_exchange_agreement distinct status/type/is_first ===')
for col in ['status','type','is_first','is_auto_pay','is_contract','is_replacement','is_bike_share','is_rent_permanent_valid']:
    try:
        vals = [r[col] for r in q(f"SELECT DISTINCT {col} FROM t_exchange_agreement WHERE {col} IS NOT NULL LIMIT 15")]
        print(f'  {col}:', vals)
    except Exception as e:
        print(f'  {col}: ERR {e}')

conn.close()
