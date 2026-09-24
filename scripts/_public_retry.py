import urllib.request, json, http.cookiejar, re, sys, urllib.parse

URL = open("tunnel_url.txt").read().strip()
BASE = URL
print("TUNNEL:", BASE)

cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

PHONE = "137****2b85"
PWD"***"

# register (ok if already exists from prior run)
reg = urllib.request.Request(BASE + "/register", data=json.dumps({"phone":PHONE,"name":"t","pwd":PWD}).encode(), headers={"Content-Type":"application/json"})
try:
    r = op.open(reg, timeout=60); print("register:", r.status, r.read().decode()[:80])
except Exception as e:
    print("register err:", e)

# login (long timeout for tunnel cold start)
login = urllib.request.Request(BASE + "/login", data=json.dumps({"phone":PHONE,"pwd":PWD}).encode(), headers={"Content-Type":"application/json"})
try:
    r = op.open(login, timeout=60); print("login:", r.status, r.read().decode()[:160])
except Exception as e:
    print("login ERR:", e); sys.exit(1)

# session
r = op.open(BASE + "/api/session", timeout=30); print("session:", r.read().decode()[:200])

# GET / with cookie -> dashboard?
r = op.open(BASE + "/", timeout=180)
body = r.read().decode("utf-8","replace")
mk = [m for m in ["au-login","boot-loading"] if m in body]
print(f"GET / WITH cookie: HTTP {r.status} len={len(body)} markers={mk}")

# /api/data with cookie
r = op.open(BASE + "/api/data", timeout=240)
data = r.read()
print(f"/api/data WITH cookie: HTTP {r.status} size={len(data)} gzip={data[:2]==b'\\x1f\\x8b'}")

# cleanup
p = "D:/workboddy file/dudu分析/citybike_backup/config/users_db.json"
users = json.load(open(p))
users = [u for u in users if u["phone"] != PHONE]
json.dump(users, open(p,"w"), ensure_ascii=False, indent=2)
print("cleaned; accounts:", [u["phone"] for u in users])
