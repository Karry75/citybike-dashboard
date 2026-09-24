import json, pymysql, sys

cfg = json.load(open('config/backup_config.json', encoding='utf-8'))
conn = pymysql.connect(host=cfg['host'], port=cfg['port'], user=cfg['user'],
                       password=cfg['password'], database=cfg['database'],
                       charset='utf8mb4', connect_timeout=15, read_timeout=600)
cur = conn.cursor(pymysql.cursors.DictCursor)

def q(sql, n=None):
    cur.execute(sql)
    if n:
        return cur.fetchmany(n)
    return cur.fetchall()

out = {}

# 1. row counts
for t in ['t_exchange_agreement','t_user_exchange_deposit','t_site','t_exchange','t_battery','t_exchange_store','t_exchange_last_upload','t_site_device_statistics','t_battery_last_upload','t_battery_status']:
    try:
        r = q(f"SELECT COUNT(*) c FROM {t}")
        out[f'count:{t}'] = r[0]['c'] if r else None
    except Exception as e:
        out[f'count:{t}'] = f'ERR {e}'

# 2. site status enums
try:
    out['site.site_status'] = [r['site_status'] for r in q("SELECT DISTINCT site_status FROM t_site WHERE site_status IS NOT NULL LIMIT 20")]
except Exception as e:
    out['site.site_status'] = f'ERR {e}'
try:
    out['site.audit_progress'] = [r['audit_progress'] for r in q("SELECT DISTINCT audit_progress FROM t_site WHERE audit_progress IS NOT NULL LIMIT 20")]
except Exception as e:
    out['site.audit_progress'] = f'ERR {e}'
try:
    out['site.is_show'] = [r['is_show'] for r in q("SELECT DISTINCT is_show FROM t_site WHERE is_show IS NOT NULL LIMIT 20")]
except Exception as e:
    out['site.is_show'] = f'ERR {e}'
try:
    out['site.is_promoter'] = [r['is_promoter'] for r in q("SELECT DISTINCT is_promoter FROM t_site WHERE is_promoter IS NOT NULL LIMIT 20")]
except Exception as e:
    out['site.is_promoter'] = f'ERR {e}'

# 3. dimension tables existence + name col
for t in ['t_agency','t_distributor','t_merchant','t_industry','t_site_type','t_promoter','t_exchange_package','t_battery_model','t_battery_product','t_exchange_model','t_site_store_employee']:
    try:
        cur.execute(f"SELECT * FROM {t} LIMIT 1")
        cols = [d[0] for d in cur.description]
        out[f'dim:{t}'] = cols
    except Exception as e:
        out[f'dim:{t}'] = f'ERR {e}'

# 4. sample rows of count/realtime tables
try:
    out['sample:t_exchange_last_upload'] = q("SELECT * FROM t_exchange_last_upload LIMIT 1")
except Exception as e:
    out['sample:t_exchange_last_upload'] = f'ERR {e}'
try:
    out['sample:t_site_device_statistics'] = q("SELECT * FROM t_site_device_statistics LIMIT 1")
except Exception as e:
    out['sample:t_site_device_statistics'] = f'ERR {e}'
try:
    out['sample:t_battery_last_upload'] = q("SELECT * FROM t_battery_last_upload LIMIT 1")
except Exception as e:
    out['sample:t_battery_last_upload'] = f'ERR {e}'
try:
    out['sample:t_battery_status'] = q("SELECT * FROM t_battery_status LIMIT 1")
except Exception as e:
    out['sample:t_battery_status'] = f'ERR {e}'

print(json.dumps(out, ensure_ascii=False, default=str, indent=1))
conn.close()
