import pymysql
import sys

CONFIG = {
    "host": "db.example.com",
    "port": 3306,
    "user": "citybike_pro",
    "password":"***",
    "database": "citybike_pro",
    "connect_timeout": 12,
    "read_timeout": 20,
    "charset": "utf8mb4",
}

def main():
    try:
        conn = pymysql.connect(**CONFIG)
    except Exception as e:
        print("CONNECT_ERROR:", type(e).__name__, str(e)[:600])
        sys.exit(2)

    try:
        cur = conn.cursor()
        cur.execute("SELECT VERSION()")
        ver = cur.fetchone()
        print("CONNECTED version=", ver[0] if ver else None)

        cur.execute("SHOW TABLES")
        tables = [r[0] for r in cur.fetchall()]
        print("TABLE_COUNT=", len(tables))
        for t in tables:
            try:
                cur.execute(f"SELECT COUNT(*) FROM `{t}`")
                cnt = cur.fetchone()[0]
            except Exception as ce:
                cnt = f"ERR:{ce}"
            print(f"TABLE\t{t}\tROWS\t{cnt}")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
