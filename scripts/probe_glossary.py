# -*- coding: utf-8 -*-
"""探查每个筛选维度背后的真实表.字段含义 + 真实取值样例，用于建立名词字典。"""
import pymysql, json
cfg=json.load(open('config/backup_config.json',encoding='utf-8'))
c=pymysql.connect(host=cfg['host'],port=int(cfg.get('port',3306)),user=cfg['user'],
    password=cfg.get('password',''),database=cfg.get('database',''),
    connect_timeout=15,read_timeout=600,charset='utf8mb4')
cur=c.cursor()

def comments(table):
    cur.execute("""SELECT COLUMN_NAME, COLUMN_TYPE, COLUMN_COMMENT
                   FROM information_schema.COLUMNS
                   WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s ORDER BY ORDINAL_POSITION""",
                 (cfg['database'], table))
    return {r[0]:{'type':r[1],'comment':r[2] or ''} for r in cur.fetchall()}

def distinct(sql, lim=15):
    try:
        cur.execute(sql)
        return [r[0] for r in cur.fetchall()[:lim]]
    except Exception as e:
        return ['<ERR %s>'%str(e)[:80]]

out={}
# ---- 字段注释（关键表）----
tables=['t_exchange_agreement','t_user','t_battery_product','t_site','t_exchange',
        't_exchange_store','t_exchange_device','t_device_type','t_battery','t_battery_brand',
        't_monitor_ex_event','t_site_store_employee','t_distributor','t_expense_bill',
        't_exchange_rent_package','t_exchange_order']
for t in tables:
    try:
        out['comment__'+t]=comments(t)
    except Exception as e:
        out['comment__'+t]={'__err__':str(e)[:200]}

# ---- 筛选字段真实取值 ----
out['vals']={
 't_exchange_agreement.status': distinct("SELECT status, COUNT(*) c FROM t_exchange_agreement GROUP BY status ORDER BY c DESC"),
 't_exchange_agreement.sys_city_name': distinct("SELECT sys_city_name FROM t_exchange_agreement WHERE sys_city_name IS NOT NULL AND sys_city_name<>'' GROUP BY sys_city_name ORDER BY COUNT(*) DESC", 20),
 't_battery_product.name': distinct("SELECT name FROM t_battery_product WHERE is_del=0 GROUP BY name ORDER BY COUNT(*) DESC"),
 't_site.type': distinct("SELECT type, COUNT(*) c FROM t_site WHERE is_del=0 GROUP BY type ORDER BY c DESC"),
 't_site.site_status': distinct("SELECT site_status, COUNT(*) c FROM t_site WHERE is_del=0 GROUP BY site_status ORDER BY c DESC"),
 't_site.business_name': distinct("SELECT business_name FROM t_site WHERE is_del=0 AND business_name IS NOT NULL AND business_name<>'' GROUP BY business_name ORDER BY COUNT(*) DESC", 12),
 't_site.is_promoter': distinct("SELECT is_promoter, COUNT(*) c FROM t_site WHERE is_del=0 GROUP BY is_promoter ORDER BY c DESC"),
 't_exchange.agency_name': distinct("SELECT agency_name FROM t_exchange_order WHERE agency_name IS NOT NULL AND agency_name<>'' GROUP BY agency_name ORDER BY COUNT(*) DESC", 12),
 't_exchange.agency_id': distinct("SELECT agency_id, COUNT(*) c FROM t_exchange_order WHERE agency_id IS NOT NULL GROUP BY agency_id ORDER BY c DESC", 8),
 't_device_type.name': distinct("SELECT id, name FROM t_device_type", 20),
 't_battery_brand.name': distinct("SELECT id, name FROM t_battery_brand WHERE is_del=0", 20),
 't_monitor_ex_event.level': distinct("SELECT level, COUNT(*) c FROM t_monitor_ex_event GROUP BY level ORDER BY c DESC"),
 't_expense_bill.in_unit': distinct("SELECT in_unit, COUNT(*) c FROM t_expense_bill WHERE is_del=0 AND in_unit IS NOT NULL AND in_unit<>'' GROUP BY in_unit ORDER BY c DESC", 20),
 't_expense_bill.bill_status': distinct("SELECT bill_status, COUNT(*) c FROM t_expense_bill WHERE is_del=0 GROUP BY bill_status ORDER BY c DESC"),
 't_site_store_employee.status': distinct("SELECT status, COUNT(*) c FROM t_site_store_employee WHERE is_del=0 GROUP BY status ORDER BY c DESC"),
 't_site_store_employee.is_manager': distinct("SELECT is_manager, COUNT(*) c FROM t_site_store_employee WHERE is_del=0 GROUP BY is_manager ORDER BY c DESC"),
 't_distributor.level': distinct("SELECT level, COUNT(*) c FROM t_distributor WHERE is_del=0 GROUP BY level ORDER BY c DESC"),
 't_distributor.status': distinct("SELECT status, COUNT(*) c FROM t_distributor WHERE is_del=0 GROUP BY status ORDER BY c DESC"),
 't_exchange_agreement.sign_site_business_name': distinct("SELECT sign_site_business_name FROM t_exchange_agreement WHERE sign_site_business_name IS NOT NULL AND sign_site_business_name<>'' GROUP BY sign_site_business_name ORDER BY COUNT(*) DESC", 12),
 't_exchange_agreement.type': distinct("SELECT type, COUNT(*) c FROM t_exchange_agreement GROUP BY type ORDER BY c DESC"),
}
json.dump(out, open('data/probe_glossary.json','w',encoding='utf-8'), ensure_ascii=False, indent=1)
print("OK rows:", sum(len(v) for k,v in out.items() if k.startswith('comment__')), "valgroups:", len(out['vals']))
c.close()
