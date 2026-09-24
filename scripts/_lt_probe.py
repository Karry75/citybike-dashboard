import urllib.request, urllib.error, json, http.cookiejar, ssl
BASE='https://thirty-worms-sniff.loca.lt'
ctx=ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
cj=http.cookiejar.CookieJar()
op=urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx), urllib.request.HTTPCookieProcessor(cj))
def get(p):
    try: r=op.open(BASE+p, timeout=20); return r.status, r.read().decode()
    except Exception as e: return 'ERR', str(e)[:300]
def post(p,d):
    req=urllib.request.Request(BASE+p, data=json.dumps(d).encode(), headers={'Content-Type':'application/json'}, method='POST')
    try:
        r=op.open(req, timeout=20); return r.status, r.read().decode(), r.headers.get('Set-Cookie')
    except urllib.error.HTTPError as e: return e.code, e.read().decode(), None
    except Exception as e: return 'ERR', str(e)[:300], None

print('[1] session(no login):', get('/api/session'))
s,body,sc = post('/login',{'phone':'139****5353','pwd'***'})
print('[2] login status/body:', s, body)
print('[3] Set-Cookie(raw)  :', repr(sc))
print('[4] cookiejar        :', [(c.name, c.value[:15]+'...') for c in cj])
print('[5] session(w cookie):', get('/api/session'))
st,data = get('/')
print('[6] GET / size=%d  boot-loading(dashboard)=%d' % (len(data), data.count(b'boot-loading')))
