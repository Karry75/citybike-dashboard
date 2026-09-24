import urllib.request, json
def probe(phone):
    try:
        req = urllib.request.Request(
            'http://localhost:8097/register',
            data=json.dumps({'phone':phone,'name':'t','pwd'***'}).encode(),
            headers={'Content-Type':'application/json'}, method='POST')
        r = urllib.request.urlopen(req)
        return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()
for p in ['139****5353','138****5daa']:
    print(p, '->', probe(p))
