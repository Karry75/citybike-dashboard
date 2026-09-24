import urllib.request, json, http.cookiejar, re, sys, urllib.parse

URL = open("tunnel_url.txt").read().strip()
print("TUNNEL:", URL)
BASE = URL

cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

def show(tag, resp, body):
    marker = []
    for m in ["au-login", "boot-loading", "localtunnel", "点击", "continue", "Tunnel"]:
        if m in body:
            marker.append(m)
    print(f"[{tag}] HTTP {resp.status} len={len(body)} markers={marker}")

# 1) GET / (may be interstitial)
req = urllib.request.Request(BASE + "/")
r = op.open(req, timeout=20)
body = r.read().decode("utf-8", "replace")
show("GET / no-cookie", r, body)

# if interstitial, try to click through: find form action and POST
if "localtunnel" in body.lower() or "点击" in body or "continue" in body.lower():
    print("  -> interstitial detected, attempting click-through")
    m = re.search(r'action="([^"]+)"', body)
    action = m.group(1) if m else "/"
    if action.startswith("/"):
        target = BASE + action
    else:
        target = action
    # copy hidden inputs
    fields = dict(re.findall(r'name="([^"]+)"[^>]*value="([^"]*)"', body))
    data = urllib.parse.urlencode(fields).encode()
    req2 = urllib.request.Request(target, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        r2 = op.open(req2, timeout=20)
        b2 = r2.read().decode("utf-8", "replace")
        show("interstitial POST", r2, b2)
    except Exception as e:
        print("  interstitial POST err:", e)

# 2) login with existing admin account (we don't know pwd -> register temp instead)
reg = urllib.request.Request(BASE + "/register", data=json.dumps({"phone":"137****17d3","name":"t","pwd"***"}).encode(), headers={"Content-Type":"application/json"})
try:
    r = op.open(reg, timeout=20); print("register:", r.status, r.read().decode()[:80])
except Exception as e:
    print("register err:", e)

login = urllib.request.Request(BASE + "/login", data=json.dumps({"phone":"137****17d3","pwd"***"}).encode(), headers={"Content-Type":"application/json"})
r = op.open(login, timeout=20); print("login:", r.status, r.read().decode()[:120])

# 3) session
r = op.open(BASE + "/api/session", timeout=10); print("session:", r.read().decode()[:200])

# 4) GET / with cookie -> should be dashboard
r = op.open(BASE + "/", timeout=120)
body = r.read().decode("utf-8", "replace")
show("GET / WITH cookie", r, body)

# 5) /api/data with cookie
r = op.open(BASE + "/api/data", timeout=180)
data = r.read()
print(f"/api/data WITH cookie: HTTP {r.status} size={len(data)} gzip_magic={data[:2]==b'\\x1f\\x8b'}")

# cleanup temp user
p = "D:/workboddy file/dudu分析/citybike_backup/config/users_db.json"
users = json.load(open(p))
users = [u for u in users if u["phone"] != "137****17d3"]
json.dump(users, open(p, "w"), ensure_ascii=False, indent=2)
print("cleaned; accounts:", [u["phone"] for u in users])
