# -*- coding: utf-8 -*-
"""合并式：抽按月业务量序列（2026 有数据）写入 analytics，供趋势面板 2026 对照。
- user_reg_month  : t_user.create_time 按月（2021-09~2026-07）
- agr_sign_month : t_exchange_agreement.create_time 按月（2023-08~2026-07）
提现额复用已有 finance.withdraw.by_month（2023-08~2026-07）。
不动基底、不重跑其它 enrich。
"""
import json, pymysql, os

BASE = r"D:/workboddy file/dudu分析/citybike_backup"
DB = json.load(open(os.path.join(BASE, "config/backup_config.json"), encoding="utf-8"))
DB.pop("workers", None)
conn = pymysql.connect(host=DB["host"], port=DB["port"], user=DB["user"], password=DB["password"],
                       database=DB["database"], connect_timeout=15, read_timeout=300, charset="utf8mb4")
c = conn.cursor()

def q(sql):
    c.execute(sql)
    return c.fetchall()

user_reg = [{"month": r[0], "count": r[1]} for r in q(
    "SELECT DATE_FORMAT(FROM_UNIXTIME(create_time/1000),'%Y-%m') m, COUNT(*) "
    "FROM t_user WHERE create_time>0 GROUP BY m ORDER BY m")]
agr_sign = [{"month": r[0], "count": r[1]} for r in q(
    "SELECT DATE_FORMAT(FROM_UNIXTIME(create_time/1000),'%Y-%m') m, COUNT(*) "
    "FROM t_exchange_agreement WHERE create_time>0 AND is_del=0 GROUP BY m ORDER BY m")]
conn.close()

D = json.load(open(os.path.join(BASE, "data/dashboard_data.json"), encoding="utf-8"))
A = D.setdefault("analytics", {})
A["user_reg_month"] = user_reg
A["agr_sign_month"] = agr_sign
A["_biz_month_note"] = (
    "运营趋势2026对照：用户注册(t_user,2021-09~)/协议签约(t_exchange_agreement,2023-08~)/"
    "提现额(finance.withdraw.by_month,2023-08~) 均为 live 2026 全量；"
    "换电订单趋势止于2023-10（live 库2024起无成功换电记录，物理上无法延伸到2026）。")

json.dump(D, open(os.path.join(BASE, "data/dashboard_data.json"), "w", encoding="utf-8"),
            ensure_ascii=False, separators=(",", ":"))
print("user_reg_month :", len(user_reg), user_reg[0]["month"], "~", user_reg[-1]["month"])
print("agr_sign_month:", len(agr_sign), agr_sign[0]["month"], "~", agr_sign[-1]["month"])
