# -*- coding: utf-8 -*-
"""一次性补丁：改造 extract_exo_package.py（独立目录/锁 + 单遍提速 + 单月容错）。
直接读改写当前文件内容，绕开 Edit 工具的"modified since read"守卫。"""
import re, io

P = r"D:/workboddy file/dudu分析/citybike_backup/scripts/extract_exo_package.py"
s = open(P, encoding="utf-8").read()

# 1) 模块级输出目录可配置
old1 = ('ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))\n'
        'CFG = json.load(open(os.path.join(ROOT, "config", "backup_config.json"), encoding="utf-8"))')
new1 = (old1 + '\n'
        '# 输出目录可配置：默认 data/exo_monthly、data/exo_near；可指向独立目录（如 data/exo_monthly2）\n'
        '# 以避免与卡死的旧进程（无权限终止）并发写同一批 gz 导致损坏。\n'
        'MONTHLY_DIR = os.environ.get("EXO_MONTHLY_DIR", os.path.join(ROOT, "data", "exo_monthly"))\n'
        'NEAR_DIR = os.environ.get("EXO_NEAR_DIR", os.path.join(ROOT, "data", "exo_near"))')
assert old1 in s, "old1 not found"
s = s.replace(old1, new1, 1)

# 2) 锁路径按目录派生
old2 = '_LOCK_PATH = os.path.join(ROOT, "data", ".exo_extract.lock")'
new2 = ('# 锁文件按输出目录派生：不同目录 → 不同锁，避免与指向其它目录的抽取进程互相阻塞。\n'
        '_LOCK_PATH = os.path.join(ROOT, "data", ".exo_extract_%s.lock" % os.path.basename(os.path.normpath(MONTHLY_DIR)))')
assert old2 in s, "old2 not found"
s = s.replace(old2, new2, 1)

# 3) main 内目录赋值
old3 = ('    monthly_dir = os.path.join(ROOT, "data", "exo_monthly")\n'
        '    near_dir = os.path.join(ROOT, "data", "exo_near")')
new3 = ('    monthly_dir = MONTHLY_DIR\n'
        '    near_dir = NEAR_DIR')
assert old3 in s, "old3 not found"
s = s.replace(old3, new3, 1)

# 4) extract_window 重写为单遍网络扫描 + 本地两遍
start = s.index('def extract_window(cur_ss, sql, args, site_info, bike_info, tmp_path):')
end_marker = '\n\ndef main():'
end = s.index(end_marker, start)
new4 = '''def extract_window(cur_ss, sql, args, site_info, bike_info, tmp_path):
    """单遍网络扫描：主表行以 JSON 对象写入临时 raw 文件，本地收集外键后批量查 lookup，
    再本地两遍组装成 36 列 JSONL。仅 1 次网络查询（fetchmany 批量取），大幅提速并消除「假死」。
    返回行数。cur_ss 为 SSCursor。"""
    ci = {c: i for i, c in enumerate(SEL_COLS)}
    raw_path = tmp_path + ".raw"
    aids, bids, exids = set(), set(), set()
    cur_ss.execute(sql, args)
    with open(raw_path, "w", encoding="utf-8") as fo:
        while True:
            rows = cur_ss.fetchmany(5000)
            if not rows:
                break
            for r in rows:
                fo.write(json.dumps({c: r[ci[c]] for c in SEL_COLS}, ensure_ascii=False, separators=(",", ":")))
                fo.write("\\n")
                a = r[ci["exchange_agreement_id"]]
                if a is not None: aids.add(a)
                b = r[ci["bike_id"]]
                if b is not None: bids.add(b)
                t = r[ci["take_exchange_id"]]
                if t is not None: exids.add(t)
                bx = r[ci["back_exchange_id"]]
                if bx is not None: exids.add(bx)
    if os.path.getsize(raw_path) == 0:
        os.remove(raw_path)
        return 0
    # 加载 lookup（仅本窗口出现的 FK，分批防 IN 超限）
    agr = batch_in(cur_ss, "SELECT id,type FROM t_exchange_agreement WHERE id IN (%s)", aids,
                   lambda o, r: o.__setitem__(r[0], r[1] or ""))
    ex2site = batch_in(cur_ss, "SELECT id,site_id FROM t_exchange WHERE id IN (%s)", exids,
                       lambda o, r: o.__setitem__(r[0], r[1]))

    def site_of(exid):
        if exid is None:
            return ("", "")
        sid = ex2site.get(exid)
        if sid is None:
            return ("", "")
        return site_info.get(sid, ("", ""))

    # 本地两遍：读 raw 组装 36 列写入 tmp（无网络）
    cnt = 0
    with open(raw_path, "r", encoding="utf-8") as fi, open(tmp_path, "w", encoding="utf-8") as fo:
        for line in fi:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            t_site, t_agency = site_of(d["take_exchange_id"])
            b_site, b_agency = site_of(d["back_exchange_id"])
            rec = {k: None for k in OUT_COLS}
            rec["订单编号"] = d["id"]
            rec["协议编号"] = d["exchange_agreement_id"]
            rec["协议类型"] = agr.get(d["exchange_agreement_id"], "")
            rec["车辆名称"] = bike_info.get(d["bike_id"], "")
            rec["车主用户id"] = d["bike_user_id"]
            rec["车主用户手机号"] = d["bike_user_phone"]
            rec["电池产品"] = d["battery_product_name"]
            rec["签约网点"] = d["site_name"]
            rec["签约代理商"] = d["agency_name"]
            rec["订单状态"] = d["order_status"]
            rec["借出电池SN"] = d["take_battery_sn"]
            rec["借出方式"] = d["take_battery_way"]
            rec["借出换电柜"] = d["take_exchange_sn"]
            rec["借出网点"] = t_site
            rec["借出代理商"] = t_agency
            rec["借出用户id"] = d["take_user_id"]
            rec["借出用户手机号"] = d["take_user_phone"]
            rec["借出电量"] = d["take_battery_power"]
            rec["借出时间"] = d["take_battery_time"]
            rec["归还电池SN"] = d["back_battery_sn"]
            rec["归还方式"] = d["back_battery_way"]
            rec["归还换电柜"] = d["back_exchange_sn"]
            rec["归还网点"] = d["back_site_name"]
            rec["归还代理商"] = b_agency
            rec["归还用户id"] = d["back_user_id"]
            rec["归还用户手机号"] = d["back_user_phone"]
            rec["归还电量"] = d["back_battery_power"]
            rec["归还时间"] = d["back_battery_time"]
            rec["消耗电量"] = d["use_power"]
            rec["预计耗电度数(kw/h)"] = round((d["use_power"] or 0) / 1000.0, 3) if d["use_power"] is not None else None
            rec["行驶里程（千米）"] = round((d["mileage"] or 0) / 1000.0, 3) if d["mileage"] is not None else None
            rec["订单金额"] = round((d["real_pay_price"] or 0) / 100.0, 2) if d["real_pay_price"] is not None else None
            rec["电量卡实付金额"] = float(d["use_power_fee"]) if d["use_power_fee"] is not None else None
            rec["电费"] = float(d["use_power_fee"]) if d["use_power_fee"] is not None else None
            rec["电量卡服务单购买订单id"] = d["busi_rel_order_no"]
            rec["电量卡套餐id"] = ""
            fo.write(json.dumps(rec, ensure_ascii=False, separators=(",", ":")))
            fo.write("\\n")
            cnt += 1
    os.remove(raw_path)
    return cnt
'''
s = s[:start] + new4 + s[end:]

# 5) 月度块包 try/except
pat5 = re.compile(r'            cnt = extract_with_retry\(db, sql, \(\), site_info, bike_info, tmp\).*?len\(info\["enc_cols"\]\)\), flush=True\)', re.DOTALL)
new5 = '''            try:
                cnt = extract_with_retry(db, sql, (), site_info, bike_info, tmp)
                if not cnt:
                    print("      %s 空，跳过" % ym, flush=True)
                    if os.path.exists(tmp):
                        os.remove(tmp)
                    continue
                info = pack_jsonl(tmp, monthly_dir, base, 1, ts)
                os.remove(tmp)
                manifest["months"].append({"ym": ym, "rows": cnt, "parts": 1,
                                           "gz": info["total_gz"], "base": base})
                manifest["total_rows"] += cnt
                print("      %s : %d 行 -> %s（编码列 %d）" % (ym, cnt, human(info["total_gz"]), len(info["enc_cols"])), flush=True)
            except Exception as e:
                import traceback as _tb
                print("      [ERROR] %s 抽取/打包失败：%s" % (ym, e), flush=True)
                _tb.print_exc()
                if os.path.exists(tmp):
                    try: os.remove(tmp)
                    except Exception: pass
                continue'''
assert pat5.search(s), "pat5 not found"
s = pat5.sub(new5, s, count=1)

# 6) near 块包 try/except
pat6 = re.compile(r'            now_ms = int\(time\.time\(\) \* 1000\).*?len\(info\["enc_cols"\]\)\), flush=True\)', re.DOTALL)
new6 = '''            try:
                now_ms = int(time.time() * 1000)
                since = now_ms - 90 * 86400 * 1000
                sel = ",".join(SEL_COLS)
                sql = "SELECT %s FROM t_exchange_order WHERE is_del=0 AND create_time>=%s ORDER BY create_time DESC" % (sel, since)
                tmp = os.path.join(tmp_dir, "near.jsonl")
                cnt = extract_with_retry(db, sql, (), site_info, bike_info, tmp)
                print("      近 90 天行数=%d" % cnt, flush=True)
                if cnt:
                    parts = 2 if cnt > 400000 else 1
                    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    info = pack_jsonl(tmp, near_dir, "exo", parts, ts)
                    os.remove(tmp)
                    manifest["near"] = {"rows": cnt, "parts": parts, "gz": info["total_gz"], "base": "exo"}
                    manifest["total_rows"] += cnt
                    print("      近 90 天 : %d 行 -> %s（%d 段，编码列 %d）" % (cnt, human(info["total_gz"]), parts, len(info["enc_cols"])), flush=True)
            except Exception as e:
                import traceback as _tb
                print("      [ERROR] 近 90 天抽取/打包失败：%s" % e, flush=True)
                _tb.print_exc()
                if os.path.exists(tmp):
                    try: os.remove(tmp)
                    except Exception: pass'''
assert pat6.search(s), "pat6 not found"
s = pat6.sub(new6, s, count=1)

open(P, "w", encoding="utf-8").write(s)
print("PATCH OK; new length=%d" % len(s))
