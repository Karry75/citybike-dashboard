# -*- coding: utf-8 -*-
"""
抽取 t_exchange_order 全量 → 按月切片 v2 列式包（全量存本地）+ 近 90 天包（面板部署）。

输出：
  data/exo_monthly/exo_YYYY-MM.dict.json.gz + .0.json.gz     每月一份（parts=1，约 6-26MB）
  data/exo_near/exo.dict.json.gz + .0.json.gz [+ .1.json.gz] 近 90 天（parts=1/2，约 58.6MB）
  data/exo_manifest.json                                     月份清单 + near，供面板「加载更早月份」

包格式（v2，与 build_package_order_pack.py 完全一致）：
  dict 包 {"v":2,"ts":...,"n":总行数,"parts":K,"counts":[...],"c":[列名],"e":{编码列:[值...]}}
  行体段 {"v":2,"part":i,"n":段行数,"r":[[编码行],...]}     编码列值为全局字典下标；其余列原值

JOIN 口径（用户 2026-08-11 确认）：
  协议类型      <- t_exchange_agreement.type        (exchange_agreement_id)
  车辆名称      <- t_bike.name                      (bike_id)
  借出/归还网点 <- t_exchange.site_id → t_site.name (take/back_exchange_id)
  借出/归还代理商<- t_exchange.site_id → t_site.agency_id
  签约代理商    <- 主表 agency_name（直存）
  电量卡实付金额/电费 <- use_power_fee（同量级占位）
  电量卡套餐id  <- ""（招小充外部单 ADB 内无对应表，占位）
  预计耗电度数  <- use_power/1000；行驶里程 <- mileage/1000；订单金额 <- real_pay_price/100

内存安全：用服务端游标(SSCursor)流式读取，先写临时 JSONL，再两遍流式打包（与 build_package_order_pack.py 同款），
不把整月/近90天全量行驻留内存。

ADB 注意：IN 子句上限 4000，多值查询必须分批（batch_in）。

可调环境变量：
  EXO_MONTHS=2026-08           只抽指定月份（多个用逗号），用于单月试跑
  EXO_NEAR=0                  跳过近 90 天包（只出月度包）
  EXO_FULL=0                  跳过全量月度包（只出近 90 天）
"""
import os, sys, json, gzip, time, datetime, math, tempfile, atexit
import pymysql

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = json.load(open(os.path.join(ROOT, "config", "backup_config.json"), encoding="utf-8"))
# 输出目录可配置：默认 data/exo_monthly、data/exo_near；可指向独立目录（如 data/exo_monthly2）
# 以避免与卡死的旧进程（无权限终止）并发写同一批 gz 导致损坏。
MONTHLY_DIR = os.environ.get("EXO_MONTHLY_DIR", os.path.join(ROOT, "data", "exo_monthly"))
NEAR_DIR = os.environ.get("EXO_NEAR_DIR", os.path.join(ROOT, "data", "exo_near"))
CFG.pop("workers", None)
DB = dict(host=CFG["host"], port=CFG["port"], user=CFG["user"], password=CFG["password"],
          database=CFG["database"], charset="utf8mb4", connect_timeout=20, read_timeout=600)

# ── 36 输出列（顺序即包内列顺序，前后端必须一致）──
OUT_COLS = ["订单编号", "协议编号", "协议类型", "车辆名称", "车主用户id", "车主用户手机号", "电池产品", "签约网点", "签约代理商",
            "订单状态", "借出电池SN", "借出方式", "借出换电柜", "借出网点", "借出代理商", "借出用户id", "借出用户手机号",
            "借出电量", "借出时间", "归还电池SN", "归还方式", "归还换电柜", "归还网点", "归还代理商", "归还用户id", "归还用户手机号",
            "归还电量", "归还时间", "消耗电量", "预计耗电度数(kw/h)", "行驶里程（千米）", "订单金额", "电量卡实付金额", "电费",
            "电量卡服务单购买订单id", "电量卡套餐id"]

# 不进字典的列：唯一列 + 高基数数值/时间列（编码无意义且字典会爆）。
# 仅保留低基数分类列参与编码（协议类型/车辆名称/电池产品/网点/代理商/状态/方式），
# 保证 near 包与每个月度包的「编码列集合」100% 一致 —— 否则 loadMore 重编码会错位。
# 注：车辆名称全库 166835 个 < DICT_MAX_UNIQ，任何子集都不会触发自动禁，故各包一致。
NO_ENCODE = {"订单编号", "协议编号", "车主用户id", "借出用户id", "归还用户id", "电量卡服务单购买订单id",
             "借出电池SN", "归还电池SN", "借出换电柜", "归还换电柜",
             "车主用户手机号", "借出用户手机号", "归还用户手机号",
             "借出电量", "借出时间", "归还电量", "归还时间", "消耗电量",
             "预计耗电度数(kw/h)", "行驶里程（千米）", "订单金额", "电量卡实付金额", "电费",
             "电量卡套餐id"}
DICT_MAX_UNIQ = 300000
PACK_VERSION = 2

# 固定编码列集合：所有包（near + 月度）必须一致，否则 loadMore 重编码错位。
EXPECTED_ENC = [c for c in OUT_COLS if c not in NO_ENCODE]

# 主表抽取列
SEL_COLS = ["id", "exchange_agreement_id", "order_status", "battery_product_name", "site_name", "agency_name",
            "take_battery_sn", "take_battery_way", "take_exchange_sn", "take_user_id", "take_user_phone",
            "take_battery_power", "take_battery_time", "back_battery_sn", "back_battery_way", "back_exchange_sn",
            "back_site_name", "back_user_id", "back_user_phone", "back_battery_power", "back_battery_time",
            "use_power", "mileage", "real_pay_price", "use_power_fee", "busi_rel_order_no",
            "bike_user_id", "bike_user_phone", "take_exchange_id", "back_exchange_id", "bike_id", "create_time"]


def human(b):
    for u in ("B", "KB", "MB", "GB"):
        if b < 1024:
            return "%.2f %s" % (b, u)
        b /= 1024.0
    return "%.2f TB" % b


def batch_in(cur, sql_prefix, ids, getter):
    """ADB IN 上限 4000，分批查询。"""
    out = {}
    items = list(ids)
    n = len(items)
    for i in range(0, n, 4000):
        chunk = items[i:i + 4000]
        if not chunk:
            continue
        ph = ",".join(["%s"] * len(chunk))
        cur.execute(sql_prefix % ph, chunk)
        for row in cur.fetchall():
            getter(out, row)
    return out


def ms_of_month(y, m):
    return int(datetime.datetime(y, m, 1).timestamp() * 1000)


def month_range(create_min_ms, create_max_ms):
    d0 = datetime.datetime.fromtimestamp(create_min_ms / 1000, datetime.timezone.utc)
    d1 = datetime.datetime.fromtimestamp(create_max_ms / 1000, datetime.timezone.utc)
    out = []
    y, m = d0.year, d0.month
    while (y, m) <= (d1.year, d1.month):
        out.append((y, m))
        m += 1
        if m > 12:
            m = 1
            y += 1
    return out


def assemble(rec_out, d):
    """把主表一行 d(列名->值) 组装成 36 列 rec（rec_out 为结果 dict，需外部预建键）。"""
    rec_out["订单编号"] = d["id"]
    rec_out["协议编号"] = d["exchange_agreement_id"]
    rec_out["协议类型"] = d["_agr_type"]
    rec_out["车辆名称"] = d["_bike_name"]
    rec_out["车主用户id"] = d["bike_user_id"]
    rec_out["车主用户手机号"] = d["bike_user_phone"]
    rec_out["电池产品"] = d["battery_product_name"]
    rec_out["签约网点"] = d["site_name"]
    rec_out["签约代理商"] = d["agency_name"]
    rec_out["订单状态"] = d["order_status"]
    rec_out["借出电池SN"] = d["take_battery_sn"]
    rec_out["借出方式"] = d["take_battery_way"]
    rec_out["借出换电柜"] = d["take_exchange_sn"]
    rec_out["借出网点"] = d["_t_site"]
    rec_out["借出代理商"] = d["_t_agency"]
    rec_out["借出用户id"] = d["take_user_id"]
    rec_out["借出用户手机号"] = d["take_user_phone"]
    rec_out["借出电量"] = d["take_battery_power"]
    rec_out["借出时间"] = d["take_battery_time"]
    rec_out["归还电池SN"] = d["back_battery_sn"]
    rec_out["归还方式"] = d["back_battery_way"]
    rec_out["归还换电柜"] = d["back_exchange_sn"]
    rec_out["归还网点"] = d["back_site_name"]
    rec_out["归还代理商"] = d["_b_agency"]
    rec_out["归还用户id"] = d["back_user_id"]
    rec_out["归还用户手机号"] = d["back_user_phone"]
    rec_out["归还电量"] = d["back_battery_power"]
    rec_out["归还时间"] = d["back_battery_time"]
    rec_out["消耗电量"] = d["use_power"]
    rec_out["预计耗电度数(kw/h)"] = round((d["use_power"] or 0) / 1000.0, 3) if d["use_power"] is not None else None
    rec_out["行驶里程（千米）"] = round((d["mileage"] or 0) / 1000.0, 3) if d["mileage"] is not None else None
    rec_out["订单金额"] = round((d["real_pay_price"] or 0) / 100.0, 2) if d["real_pay_price"] is not None else None
    rec_out["电量卡实付金额"] = float(d["use_power_fee"]) if d["use_power_fee"] is not None else None
    rec_out["电费"] = float(d["use_power_fee"]) if d["use_power_fee"] is not None else None
    rec_out["电量卡服务单购买订单id"] = d["busi_rel_order_no"]
    rec_out["电量卡套餐id"] = ""


# ───────────────────────── 流式 v2 打包（读 JSONL 两遍，内存安全） ─────────────────────────
def pack_jsonl(jsonl_path, out_dir, base, parts, ts):
    """jsonl 每行一个 dict（键为 OUT_COLS）。两遍流式：Pass1 建字典，Pass2 编码+分段写 gz。"""
    n = 0
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                n += 1
    if n == 0:
        return None
    os.makedirs(out_dir, exist_ok=True)
    enc_cols = [c for c in OUT_COLS if c not in NO_ENCODE]
    # Pass1：统计全局字典
    dicts = {c: {} for c in enc_cols}
    dict_arr = {c: [] for c in enc_cols}
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            for c in enc_cols:
                if dicts[c] is None:
                    continue
                v = r.get(c)
                if v is None:
                    v = ""
                if not isinstance(v, str):
                    v = str(v)
                if v not in dicts[c]:
                    if len(dict_arr[c]) >= DICT_MAX_UNIQ:
                        dicts[c] = None
                        dict_arr[c] = None
                        continue
                    dicts[c][v] = len(dict_arr[c])
                    dict_arr[c].append(v)
    for c in enc_cols:
        if dicts.get(c) is None:
            dict_arr[c] = None
    real_enc = [c for c in enc_cols if dict_arr.get(c)]
    e_global = {c: dict_arr[c] for c in real_enc}
    enc_set = set(real_enc)

    # Pass2：编码 + 分段流式写 gz
    k = parts if n >= parts else 1
    rows_per_part = int(math.ceil(n / float(k))) if n else 0
    out_paths = [os.path.join(out_dir, "%s.%d.json.gz" % (base, i)) for i in range(k)]
    dict_path = os.path.join(out_dir, "%s.dict.json.gz" % base)
    gfs = [gzip.GzipFile(p, "wb", compresslevel=9, mtime=0) for p in out_paths]
    expect = [max(0, min(rows_per_part, n - pid * rows_per_part)) for pid in range(k)]
    for pid, gi in enumerate(gfs):
        gi.write(('{"v":%d,"part":%d,"n":%d,"r":[' % (PACK_VERSION, pid, expect[pid])).encode("utf-8"))
    first = [True] * k
    cnt = 0
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            row = []
            for c in OUT_COLS:
                v = r.get(c)
                if c in enc_set:
                    if v is None:
                        v = ""
                    if not isinstance(v, str):
                        v = str(v)
                    ix = dicts[c].get(v)
                    if ix is None:
                        raise AssertionError("字典缺失: 列 %s 值 %r 未收录" % (c, v))
                    row.append(ix)
                else:
                    row.append(v)
            pid = min(cnt // rows_per_part, k - 1) if n > 1 else 0
            buf = ("" if first[pid] else ",") + json.dumps(row, ensure_ascii=False, separators=(",", ":"))
            gfs[pid].write(buf.encode("utf-8"))
            first[pid] = False
            cnt += 1
    for gi in gfs:
        gi.write(b"]}")
        gi.close()
    dict_obj = {"v": PACK_VERSION, "ts": ts, "n": n, "parts": k,
                "counts": expect, "c": OUT_COLS, "e": e_global}
    with gzip.GzipFile(dict_path, "wb", compresslevel=9, mtime=0) as gd:
        gd.write(json.dumps(dict_obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    gz = [os.path.getsize(p) for p in out_paths]
    ds = os.path.getsize(dict_path)
    return {"base": base, "rows": n, "parts": k, "enc_cols": real_enc,
            "part_gz": gz, "dict_gz": ds, "total_gz": sum(gz) + ds,
            "dict_path": dict_path, "out_paths": out_paths}


def _existing_pkg(out_dir, base):
    """若已存在且编码口径与当前一致，则返回包信息；否则返回 None（需重抽）。"""
    dict_path = os.path.join(out_dir, "%s.dict.json.gz" % base)
    if not os.path.exists(dict_path):
        return None
    try:
        with gzip.GzipFile(dict_path, "rb") as g:
            dobj = json.loads(g.read().decode("utf-8"))
    except Exception:
        return None
    enc = set(dobj.get("e", {}).keys())
    if enc != set(EXPECTED_ENC):
        return None  # 编码口径变了（旧包）→ 强制重抽
    parts = dobj.get("parts", 1)
    n = dobj.get("n", 0)
    if not all(os.path.exists(os.path.join(out_dir, "%s.%d.json.gz" % (base, i))) for i in range(parts)):
        return None
    # 完整性校验：整段流式解压（丢弃输出）。可捕获截断 / 并发写入交错 / 尾部残留。
    for i in range(parts):
        pp = os.path.join(out_dir, "%s.%d.json.gz" % (base, i))
        try:
            with gzip.GzipFile(pp, "rb") as g:
                while True:
                    chunk = g.read(1 << 20)
                    if not chunk:
                        break
        except Exception:
            return None  # 包已损坏 → 重抽
    ds = os.path.getsize(dict_path)
    part_gz = [os.path.getsize(os.path.join(out_dir, "%s.%d.json.gz" % (base, i))) for i in range(parts)]
    return {"rows": n, "parts": parts, "gz": sum(part_gz) + ds, "base": base}


# ───────────────────────── 单实例锁（防止并发写坏 gz 包） ─────────────────────────
# 锁文件按输出目录派生：不同目录 → 不同锁，避免与指向其它目录的抽取进程互相阻塞。
_LOCK_PATH = os.path.join(ROOT, "data", ".exo_extract_%s.lock" % os.path.basename(os.path.normpath(MONTHLY_DIR)))


def acquire_lock():
    """独占创建锁文件。若已存在且持有进程仍活着，则拒绝启动。"""
    os.makedirs(os.path.dirname(_LOCK_PATH), exist_ok=True)
    if os.path.exists(_LOCK_PATH):
        try:
            old = int(open(_LOCK_PATH, encoding="utf-8").read().strip().split("|")[0])
        except Exception:
            old = -1
        alive = False
        if old > 0:
            try:
                import ctypes
                h = ctypes.windll.kernel32.OpenProcess(0x1000, False, old)
                if h:
                    ctypes.windll.kernel32.CloseHandle(h)
                    alive = True
            except Exception:
                alive = os.name != "nt"
        if alive:
            print("!! 已有抽取进程在运行（PID %s），本次拒绝启动，避免并发写坏 gz 包。" % old)
            print("   如确认前一进程已死，删除锁文件后重试： %s" % _LOCK_PATH)
            sys.exit(3)
        print("   （发现残留锁文件，持有进程 PID %s 已不存在，接管）" % old)
    with open(_LOCK_PATH, "w", encoding="utf-8") as f:
        f.write("%d|%s" % (os.getpid(), time.strftime("%Y-%m-%d %H:%M:%S")))
    atexit.register(release_lock)


def release_lock():
    try:
        if os.path.exists(_LOCK_PATH):
            os.remove(_LOCK_PATH)
    except Exception:
        pass


def _conn_dead(e):
    """判断异常是否为 ADB 连接断开（需重连）。"""
    if isinstance(e, (ConnectionResetError, BrokenPipeError, OSError)):
        return True
    if isinstance(e, pymysql.OperationalError):
        code = e.args[0] if e.args else None
        return code in (0, 2006, 2013, 2055)
    return False


class DBConn:
    """带自动重连的 ADB 连接包装。长连接被 ADB 超时断开时重建。"""
    def __init__(self):
        self.open()
    def open(self):
        _kw = dict(DB)
        _kw.update(connect_timeout=30, read_timeout=900, write_timeout=120)
        self.cn = pymysql.connect(**_kw)
        self.cur = self.cn.cursor()
        self.cur_ss = self.cn.cursor(pymysql.cursors.SSCursor)
    def reconnect(self):
        print("     [重连] ADB 连接断开，重建连接…", flush=True)
        try:
            self.cn.close()
        except Exception:
            pass
        time.sleep(3)
        self.open()
        print("     [重连] 连接已恢复", flush=True)


def extract_with_retry(db, sql, args, site_info, bike_info, tmp, max_retry=6):
    """抽取一个窗口，遇连接中断自动重连并重试（保护整月进度）。"""
    last = None
    for attempt in range(1, max_retry + 1):
        try:
            if attempt == 1:
                # 主动保活：空闲期被 ADB 断开的连接先自愈
                try:
                    db.cn.ping(reconnect=True)
                except Exception:
                    db.reconnect()
            else:
                db.reconnect()
            return extract_window(db.cur_ss, sql, args, site_info, bike_info, tmp)
        except Exception as e:
            if _conn_dead(e) and attempt < max_retry:
                last = e
                print("     [重试 %d/%d] 抽取遇连接中断: %s" % (attempt, max_retry, e), flush=True)
                db.reconnect()
                continue
            raise
    raise (last if last else RuntimeError("extract_with_retry 耗尽重试"))


def extract_window(cur_ss, sql, args, site_info, bike_info, tmp_path):
    """单遍网络扫描：主表行以 JSON 对象写入临时 raw 文件，本地收集外键后批量查 lookup，
    再本地两遍组装成 36 列 JSONL。仅 1 次网络查询（fetchmany 批量取），大幅提速并消除「假死」。
    返回行数。cur_ss 为 SSCursor。"""
    from decimal import Decimal as _Dec
    def _jval(v):
        if isinstance(v, _Dec):
            return float(v)
        if isinstance(v, (datetime.datetime, datetime.date)):
            return v.isoformat()
        if isinstance(v, bytes):
            return v.decode("utf-8", "replace")
        return v
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
                fo.write(json.dumps({c: _jval(r[ci[c]]) for c in SEL_COLS}, ensure_ascii=False, separators=(",", ":")))
                fo.write("\n")
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
            fo.write("\n")
            cnt += 1
    os.remove(raw_path)
    return cnt


def main():
    t0 = time.time()
    do_full = os.environ.get("EXO_FULL", "1") != "0"
    do_near = os.environ.get("EXO_NEAR", "1") != "0"
    force = os.environ.get("EXO_FORCE", "0") == "1"
    only_months = os.environ.get("EXO_MONTHS")
    only_set = None
    if only_months:
        only_set = set(only_months.split(","))

    acquire_lock()  # 单实例保护：并发运行会把同名 gz 包写成交错流

    db = DBConn()
    cur = db.cur
    cur_ss = db.cur_ss
    print("[0] 连接 ADB %s 成功" % CFG["host"], flush=True)

    print("[1] 加载 t_site / t_bike 全局字典…", flush=True)
    site_info = {}
    cur.execute("SELECT id,name,agency_id FROM t_site")
    for r in cur.fetchall():
        site_info[r[0]] = (r[1] or "", r[2] if r[2] is not None else "")
    bike_info = {}
    cur.execute("SELECT id,name FROM t_bike")
    for r in cur.fetchall():
        bike_info[r[0]] = r[1] or ""
    print("      site=%d, bike=%d" % (len(site_info), len(bike_info)), flush=True)

    monthly_dir = MONTHLY_DIR
    near_dir = NEAR_DIR
    tmp_dir = tempfile.mkdtemp(prefix="exo_tmp_")
    manifest = {"generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "total_rows": 0, "months": [], "near": None}

    if do_full:
        cur.execute("SELECT MIN(create_time),MAX(create_time) FROM t_exchange_order WHERE is_del=0")
        mn, mx = cur.fetchone()
        months = month_range(mn, mx)
        print("[2] 全量月度包：共 %d 个月（%s ~ %s）" % (len(months), months[0], months[-1]), flush=True)
        for (y, m) in months:
            ym = "%04d-%02d" % (y, m)
            if only_set and ym not in only_set:
                continue
            base = "exo_%s" % ym
            if not force:
                existing = _existing_pkg(monthly_dir, base)
                if existing:
                    manifest["months"].append({"ym": ym, "rows": existing["rows"], "parts": existing["parts"],
                                               "gz": existing["gz"], "base": base})
                    manifest["total_rows"] += existing["rows"]
                    print("      %s 已存在（%d 行），跳过" % (ym, existing["rows"]), flush=True)
                    continue
            start = ms_of_month(y, m)
            end = ms_of_month(y + 1, 1) if m == 12 else ms_of_month(y, m + 1)
            sel = ",".join(SEL_COLS)
            sql = "SELECT %s FROM t_exchange_order WHERE is_del=0 AND create_time>=%s AND create_time<%s" % (sel, start, end)
            tmp = os.path.join(tmp_dir, "m_%s.jsonl" % ym)
            ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            try:
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
                continue

    if do_near:
        print("[3] 近 90 天包…", flush=True)
        existing = _existing_pkg(near_dir, "exo") if not force else None
        if existing:
            manifest["near"] = {"rows": existing["rows"], "parts": existing["parts"], "gz": existing["gz"], "base": "exo"}
            manifest["total_rows"] += existing["rows"]
            print("      近 90 天已存在（%d 行），跳过" % existing["rows"], flush=True)
        else:
            try:
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
                    except Exception: pass

    import shutil
    shutil.rmtree(tmp_dir, ignore_errors=True)
    json.dump(manifest, open(os.path.join(ROOT, "data", "exo_manifest.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("")
    print("=" * 60)
    print(" 月度包目录 : %s" % monthly_dir)
    print(" 近90天目录 : %s" % near_dir)
    print(" 总写入行数 : %d" % manifest["total_rows"])
    print(" 清单       : data/exo_manifest.json")
    print(" 耗时       : %.1fs" % (time.time() - t0))
    print("=" * 60)
    db.cur_ss.close()
    db.cn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
