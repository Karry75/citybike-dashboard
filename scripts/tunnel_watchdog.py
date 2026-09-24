import subprocess, time, urllib.request, re, sys, os, signal

PORT = 8097
URL_RE = re.compile(r'https://[^\s\'"<>]+\.loca\.lt')
HERE = os.path.dirname(os.path.abspath(__file__))
URL_FILE = os.path.join(HERE, "tunnel_url.txt")
PID_FILE = os.path.join(HERE, "watchdog.pid")

NPX = r"C:\Users\Karry\.workbuddy\binaries\node\versions\22.22.2\npx.cmd"

# 优先抢用固定子域（地址稳定不变）。被占用/冷却期则等待后重试。
# 全部失败才回退随机子域（仍可用，只是地址会变）。
PREFERRED = [
    "citybike-dash",
    "citybike-dashboard",
    "dudu-citybike",
    "citybike-karry",
    "cb-dash-2026",
]
COOLDOWN = 60  # 子域冷却等待秒数
# 健康检查只查本地 server（127.0.0.1:8097），不查隧道 URL，
# 避免 localtunnel 公网侧抖动(502/503)误判导致频繁重抢漂移。
HEALTH_LOCAL = f"http://127.0.0.1:{PORT}/"


def _stop_old():
    """若旧看门狗实例存活，先结束它（基于 PID 文件）。"""
    try:
        if os.path.exists(PID_FILE):
            with open(PID_FILE) as f:
                old = int(f.read().strip())
            if old != os.getpid():
                os.kill(old, signal.SIGTERM)
                print(f"[watchdog] 结束旧实例 PID={old}")
                time.sleep(2)
    except Exception as e:
        print("[watchdog] 旧实例清理:", e)


def start_lt(subdomain=None):
    cmd = f'"{NPX}" -y localtunnel --port {PORT}'
    if subdomain:
        cmd += f" --subdomain {subdomain}"
    return subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1, shell=True, cwd=os.path.dirname(HERE),
    )


def _kill(p):
    try:
        p.terminate()
    except Exception:
        pass
    try:
        p.wait(timeout=5)
    except Exception:
        try:
            p.kill()
        except Exception:
            pass


def extract_url(p, timeout=45):
    t0 = time.time()
    while time.time() - t0 < timeout:
        line = p.stdout.readline()
        if not line:
            return None
        sys.stdout.write("[lt] " + line)
        sys.stdout.flush()
        m = URL_RE.search(line)
        if m:
            return m.group(0)
    return None


def health_ok():
    """只检查本地 server 是否存活。"""
    try:
        r = urllib.request.urlopen(HEALTH_LOCAL, timeout=5)
        return r.status == 200
    except Exception:
        return False


def acquire():
    """循环抢固定子域，抢到偏好子域才返回；否则冷却后重试。
    若整轮固定子域都不可用，回退随机子域兜底保证可用。"""
    while True:
        for cand in PREFERRED:
            print(f"[watchdog] 尝试固定子域: {cand}.loca.lt")
            p = start_lt(cand)
            u = extract_url(p)
            if u and cand in u:
                return p, u, cand
            print(f"[watchdog] 未抢到 {cand}（可能冷却期/被占用），换下一个")
            _kill(p)
            time.sleep(5)
        # 全部偏好子域本轮都没抢到 → 回退随机子域兜底（立即可用）
        print("[watchdog] 固定子域暂不可用，回退随机子域兜底")
        p = start_lt()
        u = extract_url(p)
        if u:
            return p, u, None
        _kill(p)
        print(f"[watchdog] 等待 {COOLDOWN}s 冷却后重试…")
        time.sleep(COOLDOWN)


def main():
    _stop_old()
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))
    while True:
        p, url, sub = acquire()
        print("[watchdog] TUNNEL UP:", url, f"(subdomain={sub})")
        with open(URL_FILE, "w") as f:
            f.write(url)
        # 健康检查只看本地 server；隧道偶发 502/503 不触发重抢（前端刷新即可）
        while True:
            time.sleep(20)
            if p.poll() is not None:
                print("[watchdog] lt 进程退出 -> 重新抢子域")
                break
            if not health_ok():
                print("[watchdog] 本地 server 不可达，重启隧道")
                _kill(p)
                break
        time.sleep(2)


if __name__ == "__main__":
    main()
