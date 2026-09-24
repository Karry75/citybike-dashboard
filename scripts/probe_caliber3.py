import pymysql, json
cfg = json.load(open('config/backup_config.json'))
c = pymysql.connect(host=cfg['host'], port=cfg['port'], user=cfg['user'],
                    password=cfg['password'], database=cfg['database'],
                    connect_timeout=cfg.get('connect_timeout', 15),
                    read_timeout=cfg.get('read_timeout', 600), charset='utf8mb4')
cur = c.cursor()
DB = cfg['database']
out = {}
def q(sql, args=None):
    cur.execute(sql, args)
    return cur.fetchall()

# 设备主表是否存在
for t in ['t_device', 't_cabinet', 't_exchange_cabinet', 't_device_type', 't_battery_brand']:
    try:
        rows = q("SELECT column_name,column_comment,data_type FROM information_schema.columns "
                 "WHERE table_schema=%s AND table_name=%s", (DB, t))
        out.setdefault('struct', {})[t] = [{'col': r[0], 'comment': r[1] or '', 'type': r[2]} for r in rows]
    except Exception as e:
        out.setdefault('struct', {})[t] = 'ERR:' + repr(e)

# t_exchange_store / t_battery 完整列
out['store_cols'] = []
try:
    rows = q("SELECT column_name,column_comment,data_type FROM information_schema.columns "
             "WHERE table_schema=%s AND table_name='t_exchange_store'", (DB,))
    out['store_cols'] = [{'col': r[0], 'comment': r[1] or '', 'type': r[2]} for r in rows]
except Exception as e:
    out['store_cols'] = 'ERR:' + repr(e)

# t_device_type 数据：id -> name (设备类型中文)
try:
    rows = q("SELECT id, name, comment FROM t_device_type LIMIT 100")
    out['device_type_data'] = [list(r) for r in rows]
except Exception as e:
    out['device_type_data'] = 'ERR:' + repr(e)

# t_battery_brand 数据
try:
    rows = q("SELECT id, name FROM t_battery_brand LIMIT 50")
    out['battery_brand_data'] = [list(r) for r in rows]
except Exception as e:
    out['battery_brand_data'] = 'ERR:' + repr(e)

# t_exchange_store 中找 device / cabinet / site / city 关联列
rel = []
for x in (out['store_cols'] if isinstance(out['store_cols'], list) else []):
    if any(w in x['col'].lower() for w in ['device', 'cabinet', 'store', 'site', 'city', 'code', 'sn', 'name', 'model', 'type', 'lng', 'lat', 'addr']):
        rel.append(x)
out['store_rel'] = rel

# 网点类型映射尝试：搜含 'site_type' 或 '网点类型' 的配置
try:
    rows = q("SELECT table_name, column_name, column_comment FROM information_schema.columns "
             "WHERE table_schema=%s AND (column_name LIKE '%%site_type%%' OR column_comment LIKE '%%网点类型%%')", (DB,))
    out['site_type_refs'] = [list(r) for r in rows]
except Exception as e:
    out['site_type_refs'] = 'ERR:' + repr(e)

json.dump(out, open('data/probe_caliber3.json', 'w'), ensure_ascii=False, indent=2)

print('=== t_exchange_store REL cols (device/cabinet/site/city/code/sn/name/model/type) ===')
for x in rel:
    print('  ', x['col'], '|', x['comment'], '|', x['type'])
print('=== device_type_data ===', out['device_type_data'][:30])
print('=== battery_brand_data ===', out['battery_brand_data'])
print('=== site_type_refs ===', out['site_type_refs'])
print('=== store_cols total:', len(out['store_cols']) if isinstance(out['store_cols'], list) else out['store_cols'])
c.close()
