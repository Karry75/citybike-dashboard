import os, sys, shutil
os.environ['CB_STRIP_DATA'] = '1'
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import server

# 避免读取 431MB 真实看板，monkeypatch 成一个小文件
tiny = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_tiny_test.html')
open(tiny, 'w', encoding='utf-8').write(
    '<!doctype html><html><head></head><body><div id="boot-loading"></div>'
    '<script>function bootApp(){}</script></body></html>')
server.DASHBOARD = tiny

c = server.app.test_client()
src = server.USERS_DB
bak = src + '.bak_test'
shutil.copy(src, bak)
try:
    # 注册测试账号（非首位->viewer，role 在 ROLE_MODULES 内）
    r = c.post('/register', json={'phone': '139****5353', 'name': '测试', 'pwd'***'})
    print('REGISTER', r.status_code, r.get_json())
    # 登录
    r2 = c.post('/login', json={'phone': '139****5353', 'pwd'***'})
    print('LOGIN', r2.status_code, r2.get_json())
    print('SET-COOKIE:', r2.headers.get('Set-Cookie'))
    cookie = r2.headers.get('Set-Cookie')
    # 带 cookie 访问 /
    r3 = c.get('/', headers={'Cookie': cookie})
    body = r3.get_data(as_text=True)
    print('GET / status', r3.status_code, 'len', len(body))
    print('  -> 含看板(boot-loading):', 'boot-loading' in body, '| 含登录表单(au-login):', 'au-login' in body)
    # 不带 cookie 访问 /（应回登录页）
    r3b = c.get('/')
    bodyb = r3b.get_data(as_text=True)
    print('GET / (无cookie) 含登录表单(au-login):', 'au-login' in bodyb)
    # /api/session 带 cookie
    r4 = c.get('/api/session', headers={'Cookie': cookie})
    print('SESSION', r4.status_code, r4.get_json())
finally:
    shutil.move(bak, src)
    os.remove(tiny)
