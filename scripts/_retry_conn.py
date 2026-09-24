# -*- coding: utf-8 -*-
import json, pymysql, time
P=r'D:/workboddy file/dudu分析/citybike_backup/config/backup_config.json'
DB=json.load(open(P,encoding='utf-8'))
print('host:', DB['host'], 'port:', DB['port'])
for i in range(1,4):
    try:
        t=time.time()
        conn=pymysql.connect(host=DB['host'],port=DB['port'],user=DB['user'],password=DB['password'],
                             database=DB['database'],connect_timeout=30,read_timeout=60,charset='utf8mb4')
        cur=conn.cursor(); cur.execute("SELECT 1"); 
        print(f'  尝试{i}: OK ({time.time()-t:.1f}s) -> SELECT 1 = {cur.fetchone()}')
        conn.close(); break
    except Exception as e:
        print(f'  尝试{i}: FAIL ({time.time()-t:.1f}s) -> {e}')
