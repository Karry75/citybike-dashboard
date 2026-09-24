import pymysql

CONFIG = {
    "host": "db.example.com",
    "port": 3306,
    "user": "citybike_pro",
    "password":"***",
    "connect_timeout": 12,
    "read_timeout": 20,
    "charset": "utf8mb4",
}

conn = pymysql.connect(**CONFIG)
cur = conn.cursor()
cur.execute("SHOW DATABASES")
for r in cur.fetchall():
    print("DB:", r[0])
conn.close()
