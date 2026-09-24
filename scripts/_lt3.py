import urllib.request, json, http.cookiejar, ssl
BASE='https://three-seals-care.loca.lt'
ctx=ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
cj=http.cookiejar.CookieJar()
op=urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx), urllib.request.HTTPCookieProcessor(cj))
def req_json(path, d):
    return op.open(urllib.request.Request(BASE+path, data=json.dumps(d).encode(), headers={'Content-Type':'application/json'}, method='POST'))
try: req_json('/register', {'phone':'139****9e67','name':'t','pwd'***'})
except Exception as e: print('register note:', e)
req_json('/login', {'phone':'139****9e67','pwd'***'})
r=op.open(BASE+'/')
data=r.read().decode()
print('GET / len=%d | boot-loading(dashboard)=%d | au-login(loginpage)=%d' % (len(data), data.count('boot-loading'), data.count('au-login')))
