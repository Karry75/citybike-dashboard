import urllib.request, json, http.cookiejar, sys

def log(*a):
    print(*a, flush=True)

URL = open("tunnel_url.txt").read().strip()
BASE = URL
log("TUNNEL:", BASE)

cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

PHONE = "137****e38e"
PWD"***"

log("-> register ...")
try:
    reg = urllib.request.Request(BASE + "/register",
        data=json.dumps({"phone":PHONE,"name":"t","pwd":PWD}).encode(),
        headers={"Content-Type":"application/json"})
    r = op.open(reg, timeout=45)
    log("register:", r.status, r.read().decode()[:80])
except Exception as e:
    log("register ERR:", repr(e))

log("-> login ...")
try:
    login = urllib.request.Request(BASE + "/login",
        data=json.dumps({"phone":PHONE,"pwd":PWD}).encode(),
        headers={"Content-Type":"application/json"})
    r = op.open(login, timeout=45)
    log("login:", r.status, r.read().decode()[:160])
except Exception as e:
    log("login ERR:", repr(e))

log("-> session ...")
try:
    r = op.open(BASE + "/api/session", timeout=20)
    log("session:", r.read().decode()[:200])
except Exception as e:
    log("session ERR:", repr(e))

log("-> GET / WITH cookie ...")
try:
    r = op.open(BASE + "/", timeout=60)
    body = r.read().decode("utf-8","replace")
    mk = [m for m in ["au-login","boot-loading"] if m in body]
    log(f"GET /: HTTP {r.status} len={len(body)} markers={mk}")
except Exception as e:
    log("GET / ERR:", repr(e))

# cleanup
try:
    p = "D:/workboddy file/dudu分析/citybike_backup/config/users_db.json"
    users = json.load(open(p))
    users = [u for u in users if u["phone"] != PHONE]
    json.dump(users, open(p,"w"), ensure_ascii=False, indent=2)
    log("cleaned; accounts:", [u["phone"] for u in users])
except Exception as e:
    log("cleanup ERR:", repr(e))
log("DONE")
