# -*- coding: utf-8 -*-
# 探测 ADB(sharing-citybike-pro) 表结构（仅元数据，不拉业务数据）
import json, pymysql
DB = json.load(open(r'D:/workboddy file/dudu分析/citybike_backup/config/backup_config.json', encoding='utf-8'))
conn = pymysql.connect(host=DB['host'], port=DB['port'], user=DB['user'], password=DB['password'],
                      database=DB['database'], connect_timeout=15, read_timeout=600, charset='utf8mb4')
cur = conn.cursor()
cur.execute('SHOW TABLES')
tables = [r[0] for r in cur.fetchall()]
print('TOTAL TABLES:', len(tables))
out = []
KEY = ('agency','distributor','merchant','promoter','employee','guide','sales','user',
        'site','agreement','commission','share','staff','clerk','channel','proxy','agent',
        'customer','member','order','rent','deposit','phone','mobile')
for t in tables:
    tl = t.lower()
    hit = any(k in tl for k in KEY)
    cur.execute('SHOW COLUMNS FROM `%s`' % t)
    cols = [c[0] for c in cur.fetchall()]
    tag = '  <<<' if hit else ''
    out.append('%s%s\n  %s' % (t, tag, ', '.join(cols)))
conn.close()
open(r'D:/workboddy file/dudu分析/citybike_backup/scripts/_schema_probe.txt','w',encoding='utf-8').write('\n'.join(out))
print('wrote _schema_probe.txt; matched tables flagged with <<<')
for line in out:
    if '<<<' in line:
        print(line.split('\n')[0])
