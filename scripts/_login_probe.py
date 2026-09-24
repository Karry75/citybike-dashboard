import urllib.request, urllib.error, json, http.cookiejar
BASE='http://localhost:8097'
cj=http.cookiejar.CookieJar()
op=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
def call(method,path,data=None):
    kw={}
    if data is not None:
        kw['data']=json.dumps(data).encode(); kw['headers']={'Content-Type':'application/json'}
    req=urllib.request.Request(BASE+path, method=method, **kw)
    try:
        r=op.open(req); return r.status, r.read().decode()
    except urllib.error.HTTPError as e: return e.code, e.read().decode()

print('login       ', call('POST','/login',{'phone':'139****5353','pwd'***'}))
print('cookies     ', [(c.name, c.value[:15]+'...') for c in cj])
print('session     ', call('GET','/api/session'))
r=op.open(BASE+'/')
cnt=0; total=0
while True:
    ch=r.read(1<<20)
    if not ch: break
    cnt+=ch.count(b'boot-loading'); total+=len(ch)
print('GET / size MB', round(total/1e6,1), '| boot-loading(dashboard) count =', cnt)
