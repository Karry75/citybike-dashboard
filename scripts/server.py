# -*- coding: utf-8 -*-
"""
城市换电看板 · 后端级登录鉴权服务（含注册）
====================================
在“前端演示级登录”基础上，升级到服务端鉴权 + 自助注册：
  1. 用户/角色/密码哈希仅存于服务端（config/users_db.json），前端不再携带任何凭据；
  2. /register 自助注册：手机号严格校验 11 位中国大陆手机号，密码≥6 位，
     首位注册用户自动为管理员，其余默认“访客”，由管理员通过 /api/set_role 开通权限；
  3. 未登录访问 / 只会拿到登录页，绝不返回看板 HTML 与数据；
  4. 登录成功后由服务端写 HttpOnly 会话 Cookie，后续请求凭 Cookie 鉴权；
  5. /api/session 返回当前角色与可见模块；前端据此做板块隐藏（纵深防御）；
  6. /api/data 可按角色裁剪返回模块，启用 STRIP_DATA=True 后前端改为按需拉取，
     实现真正的“按角色隔离数据”（默认 False，便于与现有静态链接并存）。

密码存储：pbkdf2_hmac(sha256, 100k 轮) + 随机盐，绝不存明文。
“真实手机”说明：注册/登录以 11 位手机号为主键并做格式校验；若需“真机收码验证”，
再接入短信服务（阿里云/腾讯云 SMS）并在 /register 增加验证码步骤即可，本版不含外部短信依赖。

运行：
  pip install flask
  python scripts/server.py            # 默认 http://0.0.0.0:5000（需登录）
  CB_STRIP_DATA=1 python scripts/server.py   # 开启按角色隔离数据
  CB_DEMO=1 python scripts/server.py         # 演示模式：免登录+实时接口开放（局域网/手机预览用）
  CB_PORT=8080 CB_SECRET=强随机串 python scripts/server.py
生产建议：
  - 用 gunicorn/uwsgi 托管，置于 Nginx 反向代理之后（强制 HTTPS）；
  - 设置强随机 CB_SECRET，并开启 Secure/HttpOnly/SameSite Cookie 属性；
  - 本服务需独立部署（静态托管如 CloudStudio 无法运行后端逻辑）。
"""
import json, os, re, time, hashlib, secrets, pymysql, threading, gzip
from flask import Flask, request, session, jsonify, Response, redirect

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)
DASHBOARD = os.path.join(ROOT, 'citybike_dashboard', 'index.html')
USERS_FILE = os.path.join(ROOT, 'config', 'server_users.json')   # 旧演示账号（仅用于首次种子）
USERS_DB = os.path.join(ROOT, 'config', 'users_db.json')          # 真实用户库（哈希）
DATA_FILE = os.path.join(ROOT, 'data', 'dashboard_data.json')
LITE_FILE = os.path.join(ROOT, 'data', 'dashboard_data_lite.json')  # 手机极速版：明细表裁剪到前 500 行
MOBILE_FILE = os.path.join(ROOT, 'data', 'dashboard_data_mobile.json')  # 手机极速版(再瘦身)：结构不变仅截断长明细，gzip~0.4MB

def _is_mobile():
    """粗略识别移动端 UA（手机/平板），用于自动切换到极速数据包。"""
    ua = (request.headers.get('User-Agent') or '').lower()
    return any(k in ua for k in ('mobile', 'android', 'iphone', 'ipad', 'ipod', 'windows phone', 'harmony', 'micromessenger'))

STRIP_DATA = os.environ.get('CB_STRIP_DATA', '0') == '1'
# 实时模式：后台周期性调用 extract_dashboard.py 重建 dashboard_data.json，
# 主看板 /api/data 因此持续同步生产库（而非静态快照）。配合缓存 mtime 失效即时生效。
LIVE_MODE = os.environ.get('CB_LIVE', '0') == '1'
LIVE_REFRESH = int(os.environ.get('CB_LIVE_REFRESH', '180'))  # 秒；可按需调小（如 60）
# 演示模式：局域网/手机免登录直接以管理员身份进入，并开放实时接口（/api/geo/sites 等）。
# 仅用于本机/局域网预览，等同原 ?demo=1 的威胁模型；公网部署请勿开启。
DEMO = os.environ.get('CB_DEMO', '0') == '1'

app = Flask(__name__)
app.secret_key = os.environ.get('CB_SECRET', 'change-me-in-prod-8f3a2b')
app.permanent_session_lifetime = 8 * 3600  # 8 小时

ROLE_MODULES = {
    'admin':   ['overview','user','sales','site','device','ops','personnel','finance','service','analytics'],
    'finance': ['overview','finance','sales','user','analytics'],
    'ops':     ['overview','device','ops','site','analytics'],
    'sales':   ['overview','sales','user','site','device','analytics'],
    'service': ['overview','service','user','analytics'],
    'viewer':  ['overview'],
}
ROLE_CN = {'admin':'管理员','finance':'财务','ops':'运维','sales':'销售','service':'客服','viewer':'访客'}

PHONE_RE = re.compile(r'^1[3-9]\d{9}$')

# ---------- 密码哈希 ----------
def hash_pwd(pwd):
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac('sha256', pwd.encode('utf-8'), bytes.fromhex(salt), 100000)
    return salt + ':' + dk.hex()

def verify_pwd(pwd, stored):
    try:
        salt, dk = stored.split(':', 1)
        nd = hashlib.pbkdf2_hmac('sha256', pwd.encode('utf-8'), bytes.fromhex(salt), 100000)
        return secrets.compare_digest(nd.hex(), dk)
    except Exception:
        return False

# ---------- 用户库 ----------
def load_db():
    if not os.path.exists(USERS_DB):
        return []
    try:
        return json.load(open(USERS_DB, encoding='utf-8'))
    except Exception:
        return []

def save_db(db):
    with open(USERS_DB, 'w', encoding='utf-8') as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

def find_user(phone):
    return next((u for u in load_db() if u.get('phone') == phone), None)

def add_user(phone, name, pwd, role):
    db = load_db()
    db.append({'phone': phone, 'name': name or phone, 'role': role,
               'pwd': hash_pwd(pwd), 'created_at': time.strftime('%Y-%m-%d %H:%M:%S')})
    save_db(db)

def seed_from_demo():
    """首次启动：若用户库为空且存在旧演示账号，则转为哈希用户库，保留可直接登录体验。"""
    if os.path.exists(USERS_DB):
        return
    if not os.path.exists(USERS_FILE):
        save_db([])
        return
    try:
        arr = json.load(open(USERS_FILE, encoding='utf-8'))
        db = [{'phone': u['phone'], 'name': u.get('name', u['phone']),
               'role': u.get('role', 'viewer'), 'pwd': hash_pwd(u['pwd']),
               'created_at': 'seed-from-demo'} for u in arr]
        # 生产加固：若设置环境变量 CB_ADMIN_PWD，则覆盖管理员(138****5daa)密码，
        # 避免仓库内 server_users.json 的演示弱口令(admin123)被直接登录。
        env_admin_pwd = os.environ.get('CB_ADMIN_PWD')
        if env_admin_pwd:
            for u in db:
                if u.get('phone') == '138****5daa' or u.get('role') == 'admin':
                    u['pwd'] = hash_pwd(env_admin_pwd)
            print('[seed] 管理员密码已由环境变量 CB_ADMIN_PWD 覆盖（已弃用演示弱口令）')
        save_db(db)
        print('[seed] 已从 server_users.json 初始化 %d 个用户（密码已哈希）' % len(db))
    except Exception as e:
        print('[seed] 失败:', e)
        save_db([])

seed_from_demo()

LOGIN_HTML = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>城市换电看板 · 登录</title>
<style>
  *{box-sizing:border-box} body{margin:0;font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;
  background:linear-gradient(135deg,#1b2a4a,#22335c);min-height:100vh;display:flex;align-items:center;justify-content:center;color:#1d2942}
  .card{background:#fff;border-radius:16px;padding:30px 34px;width:372px;box-shadow:0 20px 60px rgba(0,0,0,.35)}
  h1{font-size:19px;margin:0 0 4px;letter-spacing:.5px} .sub{color:#7c879b;font-size:12.5px;margin-bottom:14px}
  .tabs{display:flex;gap:8px;margin-bottom:16px}
  .tab{flex:1;text-align:center;padding:9px 0;border-radius:9px;background:#eef3fe;color:#5b6b86;font-size:13.5px;font-weight:600;cursor:pointer}
  .tab.on{background:#2f6fed;color:#fff}
  label{display:block;font-size:12.5px;color:#1d2942;font-weight:600;margin:12px 0 6px}
  input{width:100%;padding:11px 13px;border:1px solid #dbe2ef;border-radius:10px;font-size:14px;outline:none}
  input:focus{border-color:#2f6fed}
  .btn{margin-top:20px;width:100%;padding:12px;border:none;border-radius:10px;background:#2f6fed;color:#fff;font-size:14.5px;font-weight:700;cursor:pointer}
  .btn:hover{background:#265fce}
  .err{color:#e8543f;font-size:12.5px;margin-top:12px;min-height:16px}
  .hint{color:#2f6fed;font-size:12px;margin-top:8px;min-height:14px}
  .demo{margin-top:16px;background:#f6f8fc;border-radius:11px;padding:11px 13px;font-size:11.5px;color:#5b6b86;line-height:1.8}
  .demo b{color:#2f6fed}
</style></head>
<body><div class="card">
  <h1>城市换电数据看板</h1>
  <div class="sub">仅限授权人员访问 · 手机号即账号</div>
  <div class="tabs"><div class="tab on" id="tab-login">登 录</div><div class="tab" id="tab-reg">注 册</div></div>

  <div id="p-login">
    <label>手机号</label><input id="au-phone" type="tel" inputmode="numeric" maxlength="11" placeholder="11位手机号，如 138****5daa" autocomplete="username">
    <label>密码</label><input id="au-pwd" type="password" placeholder="登录密码" autocomplete="current-password">
    <button class="btn" id="au-login">登 录</button>
    <div class="err" id="au-err"></div>
  </div>

  <div id="p-reg" style="display:none">
    <label>手机号</label><input id="rg-phone" type="tel" inputmode="numeric" maxlength="11" placeholder="11位真实手机号" autocomplete="username">
    <label>姓名/备注</label><input id="rg-name" placeholder="选填，如 运维-王" autocomplete="name">
    <label>密码</label><input id="rg-pwd" type="password" placeholder="至少6位" autocomplete="new-password">
    <button class="btn" id="rg-submit">注 册</button>
    <div class="err" id="rg-err"></div>
    <div class="hint" id="rg-hint"></div>
  </div>

  <div class="demo"><b>已初始化账号（演示）</b><br>管理员 138****5daa / admin123　财务 138****4d00 / fin123<br>
  运维 138****cd96 / ops123　销售 138****e910 / sal123<br>客服 138****5fb3 / svc123　访客 138****4c68 / view123<br>
  <span style="color:#8a94a8">新注册用户默认角色为“访客”，由管理员在后台开通对应权限。</span></div>
</div>
<script>
function postJSON(url,body,cb){fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),credentials:'same-origin'}).then(function(r){return r.json().then(function(j){return{ok:r.ok,j:j};});}).then(cb).catch(function(){cb({ok:false,j:{error:'网络异常，请重试'}});});}
document.getElementById('tab-login').onclick=function(){this.classList.add('on');document.getElementById('tab-reg').classList.remove('on');document.getElementById('p-login').style.display='';document.getElementById('p-reg').style.display='none';};
document.getElementById('tab-reg').onclick=function(){this.classList.add('on');document.getElementById('tab-login').classList.remove('on');document.getElementById('p-reg').style.display='';document.getElementById('p-login').style.display='none';};
document.getElementById('au-login').onclick=function(){
  var phone=document.getElementById('au-phone').value.trim(),pwd=document.getElementById('au-pwd').value,err=document.getElementById('au-err');
  postJSON('/login',{phone:phone,pwd:pwd},function(res){if(!res.ok){err.textContent=(res.j&&res.j.error)||'手机号或密码错误';return;}location.href='/';});
};
['au-phone','au-pwd'].forEach(function(id){document.getElementById(id).addEventListener('keydown',function(e){if(e.key==='Enter')document.getElementById('au-login').click();});});
document.getElementById('rg-submit').onclick=function(){
  var phone=document.getElementById('rg-phone').value.trim(),name=document.getElementById('rg-name').value.trim(),pwd=document.getElementById('rg-pwd').value,err=document.getElementById('rg-err'),hint=document.getElementById('rg-hint');
  err.textContent='';hint.textContent='';
  postJSON('/register',{phone:phone,name:name,pwd:pwd},function(res){
    if(!res.ok){err.textContent=(res.j&&res.j.error)||'注册失败';return;}
    hint.textContent=(res.j.note||'注册成功')+'，正在跳转登录…';
    setTimeout(function(){location.href='/';},1200);
  });
};
['rg-phone','rg-pwd'].forEach(function(id){document.getElementById(id).addEventListener('keydown',function(e){if(e.key==='Enter')document.getElementById('rg-submit').click();});});
</script>
</body></html>"""

LOADER_HTML = """<!doctype html>
<html lang="zh-CN">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>城市换电看板</title>
<style>html,body{margin:0;height:100%;background:#0d1b2e;color:#a8c4ee;font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif}
#wrap{height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:14px}
#spin{width:42px;height:42px;border:4px solid #1a3a5c;border-top-color:#3895ff;border-radius:50%;animation:sp 1s linear infinite}
@keyframes sp{to{transform:rotate(360deg)}}
#tip{font-size:14px;opacity:.85}</style></head>
<body><div id="wrap"><div id="spin"></div><div id="tip">正在加载看板界面…（首屏约 5~10 秒）</div></div>
<script>(function(){var t=document.getElementById('tip');fetch('/__dash',{credentials:'same-origin'}).then(function(r){if(!r.ok){t.textContent='加载失败('+r.status+')，请刷新';return;}return r.arrayBuffer();}).then(async function(b){if(!b)return;var u=new Uint8Array(b),s;if(u[0]===0x1f&&u[1]===0x8b){var ds=new DecompressionStream('gzip');s=await new Response(new Response(b).body.pipeThrough(ds)).text();}else{s=new TextDecoder().decode(b);}document.open();document.write(s);document.close();}).catch(function(e){t.textContent='网络异常，请检查网络后刷新';console.error(e);});})();</script>
</body></html>"""

_DASH_HTML = {}  # 内存缓存：看板 HTML 原文（13:29 前纯净版，直出文本）
def serve_dashboard():
    key = 'strip' if STRIP_DATA else 'full'
    if key not in _DASH_HTML:
        html = open(DASHBOARD, encoding='utf-8').read()
        # 去除前端演示凭据，避免密码随页面下发
        html = re.sub(r'const USERS = \{.*?\};', 'const USERS = {};', html, count=1, flags=re.S)
        if STRIP_DATA:
            # 真正的轻量模式：内嵌 410MB 数据清空，前端打开后异步 fetch('/api/data')。
            # 注入全屏 loading 遮罩 + 引导脚本：数据到达后设 window.DATA 并调用前端 bootApp()。
            # 注意：只掏空 DATA JSON 本身（到其专属的"数据净化"注释为止），
            # 不可贪心吞掉其后的 CHINA_GEO / const CN，否则地图与常量全部 undefined。
            html = re.sub(r'const DATA = (\{[\s\S]*?\});\n// ── 数据净化',
                          'const DATA = {};\n// ── 数据净化', html, count=1)
            boot = (
                '<div id="boot-loading" style="position:fixed;inset:0;z-index:99999;'
                'display:flex;flex-direction:column;align-items:center;justify-content:center;gap:16px;'
                'background:#0d1b2e;color:#a8c4ee;font-family:-apple-system,\'PingFang SC\',\'Microsoft YaHei\',sans-serif;font-size:15px">'
                '<div id="boot-spin" style="width:44px;height:44px;border:4px solid #1a3a5c;border-top-color:#3895ff;'
                'border-radius:50%;animation:bootspin 1s linear infinite"></div>'
                '<div id="boot-msg">正在连接服务器…</div></div>'
                '<style>@keyframes bootspin{to{transform:rotate(360deg)}}</style>'
                '<script>window.__BACKEND=true;window.onerror=function(m,s,l,c,e){var el=document.getElementById("boot-loading");if(el){el.querySelector("#boot-spin").style.display="none";el.querySelector("#boot-msg").innerHTML="<b>\\u26a0\\ufe0f JS \\u6e32\\u67d3\\u62a5\\u9519</b><br><span style=\\\"font-size:13px\\\">"+(m||"")+"<br><span style=\\\"opacity:.6;font-size:12px\\\">"+(l||"")+":"+(c||"")+"</span><br><a href=\\\"/\\\" style=\\\"color:#3895ff\\\">[\\u5237\\u65b0\\u91cd\\u8bd5]</a></span>";}console.error("onerror:",m,s,l,c,e);return true;};'
                '(function(){'
                'var el=document.getElementById("boot-loading"),msg=function(t){if(el)el.querySelector("#boot-msg").textContent=t;};'
                'var TMR=setTimeout(function(){if(el){el.querySelector("#boot-spin").style.display="none";msg("\\u26a0\\ufe0f \\u52a0\\u8d7d\\u8d85\\u65f6(30s)\\uff0c\\u8bf7\\u68c0\\u67e5\\u7f51\\u7edc\\u540e<a href=\\\"/\\\" style=\\\"color:#3895ff\\\">\\u5237\\u65b0</a>");}},30000);'
                'msg("\\u6b63\\u5728\\u52a0\\u8f7d\\u770b\\u677f\\u6570\\u636e…");'
                'fetch("/api/data?plain=1",{credentials:"same-origin"}).then(function(r){'
                'msg("\\u6570\\u636e\\u5df2\\u8fd4\\u56de\\uff0c\\u6b63\\u5728\\u89e3\\u6790…");'
                'if(!r.ok){clearTimeout(TMR);'
                'if(r.status===401){if(el)el.innerHTML="\\u26a0\\ufe0f <b>\\u672a\\u767b\\u5f55</b> \\u6216\\u767b\\u5f55\\u5df2\\u8fc7\\u671f<br><a href=\\\'/\\\' style=\\\'color:#3895ff\\\'>\\u70b9\\u51fb\\u91cd\\u65b0\\u767b\\u5f55</a>";}'
                'else{if(el)el.innerHTML="\\u26a0\\ufe0f <b>\\u670d\\u52a1\\u5668\\u9519\\u8bef</b> HTTP "+r.status+"<br><a href=\\\"/\\\" style=\\\"color:#3895ff\\\">[\\u5237\\u65b0]</a>";}'
                'return;}'
                'return r.text();'
                '})'
                '.then(function(text){'
                'if(!text)return;'
                'clearTimeout(TMR);'
                'msg("\\u6b63\\u5728\\u6e32\\u67d3\\u770b\\u677f…");'
                'var d=JSON.parse(text);'
                'var modCount=Object.keys(d).length;'
                'window.DATA=d;for(var k in d){if(Object.prototype.hasOwnProperty.call(d,k)){DATA[k]=d[k];}}if(el)el.remove();'
                'if(typeof bootApp==="function")bootApp();'
                '})'
                '.catch(function(e){clearTimeout(TMR);if(el){el.querySelector("#boot-spin").style.display="none";msg("\\u26a0\\ufe0f "+(e.message||String(e)));}console.error(e);});'
                '})();</script>\n</body>'
            )
            # ⚠️ 必须替换「最后一个」</body>（ECharts 库内部含 </body> 字面量，
            #    replace 首个会命中错误位置，导致 HTML 结构崩坏、浏览器显示源码）
            _lb = html.rfind('</body>')
            if _lb >= 0:
                html = html[:_lb] + boot + html[_lb + len('</body>'):]
        else:
            _lb = html.rfind('</body>')
            if _lb >= 0:
                html = html[:_lb] + '<script>window.__BACKEND=true;</script>\n</body>' + html[_lb + len('</body>'):]
        _DASH_HTML[key] = html
    # 临时调试：?autosingle=<phone>&autoby=<phone|uid|agreement> 自动跳到单用户视图并查询
    auto_key = (request.args.get('autosingle') or '').strip()
    if auto_key:
        auto_by = (request.args.get('autoby') or 'phone').strip()
        auto_script = (
            '<script>(function(){'
            'function boot(){'
            ' try{ var ni=document.querySelector(".navitem[data-v=\\"user\\"]"); if(ni)ni.click(); }catch(e){}'
            ' setTimeout(function(){'
            ' try{ if(typeof switchUserSub==="function"){ switchUserSub("single"); }'
            '      var inp=document.getElementById("u-single-phone"); if(inp){inp.value="'+auto_key+'";}'
            '      var sel=document.getElementById("u-single-by"); if(sel){sel.value="'+auto_by+'";}'
            '      if(typeof drawSingleUser==="function"){ drawSingleUser("'+auto_key+'"); }'
            ' }catch(e){console.error("autosingle err",e)}'
            ' },1500);'
            '}'
            'if(document.readyState!=="loading") boot();'
            'else document.addEventListener("DOMContentLoaded",boot);'
            '})();</script>'
        )
        _lb2 = _DASH_HTML[key].rfind('</body>')
        if _lb2 >= 0:
            _DASH_HTML[key] = _DASH_HTML[key][:_lb2] + auto_script + _DASH_HTML[key][_lb2 + len('</body>'):]
    return Response(_DASH_HTML[key], mimetype='text/html',
                    headers={'Cache-Control': 'no-store'})

def authed():
    return bool(session.get('phone') and session.get('role') in ROLE_MODULES)

@app.route('/test')
def diag_test():
    html = (
        '<!DOCTYPE html><html lang="zh-CN"><head>'
        '<meta charset="utf-8"><title>诊断测试</title>'
        '<meta name="viewport" content="width=device-width,initial-scale=1"></head>'
        '<body style="font-family:sans-serif;padding:24px;background:#f5f7fa">'
        '<h1 style="color:#1677ff">✅ 测试成功</h1>'
        '<p>如果你看到这行中文且不是代码，说明你的环境能正常渲染网页。</p>'
        '<p id="ua" style="color:#666"></p>'
        '<script>document.getElementById("ua").textContent="当前UA: "+navigator.userAgent;</script>'
        '</body></html>'
    )
    return Response(html, mimetype='text/html')

@app.route('/')
def index():
    if authed() or DEMO:
        return serve_dashboard()
    return Response(LOGIN_HTML, mimetype='text/html')

# [回退] 13:29 前纯净版不含 /__dash gzip 首屏路由，已在回退时移除

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json(silent=True) or {}
    phone = (data.get('phone') or '').strip()
    pwd = data.get('pwd') or ''
    name = (data.get('name') or '').strip()
    if not PHONE_RE.match(phone):
        return jsonify({'error': '手机号格式不正确（需 11 位中国大陆手机号）'}), 400
    if len(pwd) < 6:
        return jsonify({'error': '密码至少 6 位'}), 400
    if find_user(phone):
        return jsonify({'error': '该手机号已注册，请直接登录'}), 409
    db = load_db()
    role = 'admin' if not db else 'viewer'
    add_user(phone, name, pwd, role)
    return jsonify({'ok': True, 'phone': phone, 'role': role, 'name': name or phone,
                   'note': ('您是首位注册用户，已自动设为管理员' if role == 'admin'
                             else '注册成功，默认角色为“访客”，请联系管理员开通对应板块权限')})

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}
    phone = (data.get('phone') or '').strip()
    pwd = data.get('pwd') or ''
    u = find_user(phone)
    if not u or not verify_pwd(pwd, u['pwd']):
        return jsonify({'error': '手机号或密码错误'}), 401
    session['phone'] = phone
    session['role'] = u['role']
    session['name'] = u.get('name', phone)
    session.permanent = True
    return jsonify({'ok': True, 'phone': phone, 'role': u['role'], 'name': u.get('name', phone)})

@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'ok': True})

@app.route('/api/session')
def api_session():
    if DEMO:
        # 演示模式：直接返回管理员会话，前端免登录进入（含 4 套大屏）
        return jsonify({'authed': True, 'phone': '138****5daa', 'name': '管理员',
                        'role': 'admin', 'role_cn': '管理员',
                        'modules': ROLE_MODULES.get('admin', ['overview'])})
    if authed():
        return jsonify({'authed': True, 'phone': session['phone'], 'name': session['name'],
                        'role': session['role'], 'role_cn': ROLE_CN.get(session['role'], session['role']),
                        'modules': ROLE_MODULES.get(session['role'], ['overview'])})
    return jsonify({'authed': False})

@app.route('/api/users', methods=['GET'])
def api_users():
    """管理员查看用户列表（不含密码）。"""
    if not (session.get('role') == 'admin'):
        return jsonify({'error': '无权限'}), 403
    db = load_db()
    return jsonify({'users': [{'phone': u['phone'], 'name': u.get('name', ''), 'role': u.get('role', 'viewer'),
                                'created_at': u.get('created_at', '')} for u in db]})

@app.route('/api/set_role', methods=['POST'])
def set_role():
    """管理员变更用户角色。"""
    if not (session.get('role') == 'admin'):
        return jsonify({'error': '无权限'}), 403
    data = request.get_json(silent=True) or {}
    phone = (data.get('phone') or '').strip()
    role = data.get('role') or ''
    if role not in ROLE_MODULES:
        return jsonify({'error': '角色非法'}), 400
    u = find_user(phone)
    if not u:
        return jsonify({'error': '用户不存在'}), 404
    db = load_db()
    for x in db:
        if x['phone'] == phone:
            x['role'] = role
            break
    save_db(db)
    return jsonify({'ok': True, 'phone': phone, 'role': role})

# ---------- 全量数据（gzip 预压缩缓存，避免每次请求重读 410MB + 重序列化） ----------
_DATA_CACHE = {'gz': None, 'lock': threading.Lock()}

def _get_data_gz():
    """读取 dashboard_data.json 并 gzip。LIVE_MODE 下按文件 mtime 失效缓存，
    使后台实时刷新器重建的快照能立刻穿透到前端。"""
    mtime = os.path.getmtime(DATA_FILE) if os.path.exists(DATA_FILE) else 0
    with _DATA_CACHE['lock']:
        if _DATA_CACHE['gz'] is not None and (not LIVE_MODE or _DATA_CACHE.get('mtime') == mtime):
            return _DATA_CACHE['gz']
    # 锁外执行重活，避免阻塞并发请求（仅首个请求会慢 10~30s）
    full = json.load(open(DATA_FILE, encoding='utf-8'))
    raw = json.dumps(full, ensure_ascii=False).encode('utf-8')
    gz = gzip.compress(raw, 9)
    with _DATA_CACHE['lock']:
        _DATA_CACHE['gz'] = gz
        if LIVE_MODE:
            _DATA_CACHE['mtime'] = mtime
    return gz

# ---------- 手机极速版数据（gzip 字节 + 自定义头，既小又不被隧道吞） ----------
# 关键：localtunnel 代理层只对【标准 Content-Encoding:gzip】响应做处理（会清空 body），
# 故这里返回 gzip 字节但用自定义头 X-Encoding:gzip 提示前端手动解压，
# localtunnel 不识别 → 透明转发 → 437KB 经隧道约 12s 传完（而非明文 4MB 的 110s）。
_LITE_GZ_CACHE = {'gz': None, 'plain': None, 'lock': threading.Lock()}

def _get_lite_gz_bytes():
    src = MOBILE_FILE if os.path.exists(MOBILE_FILE) else (LITE_FILE if os.path.exists(LITE_FILE) else None)
    mtime = os.path.getmtime(src) if src and os.path.exists(src) else 0
    with _LITE_GZ_CACHE['lock']:
        if _LITE_GZ_CACHE['gz'] is not None and (not LIVE_MODE or _LITE_GZ_CACHE.get('mtime') == mtime):
            return _LITE_GZ_CACHE['gz']
    if src is None:
        return _get_data_gz()  # 兜底全量（带标准 gzip 头）
    lite = json.load(open(src, encoding='utf-8'))
    raw = json.dumps(lite, ensure_ascii=False).encode('utf-8')
    gz = gzip.compress(raw, 9)
    with _LITE_GZ_CACHE['lock']:
        _LITE_GZ_CACHE['gz'] = gz
        _LITE_GZ_CACHE['plain'] = raw.decode('utf-8')  # 缓存明文，供 ?plain=1 零开销返回
        if LIVE_MODE:
            _LITE_GZ_CACHE['mtime'] = mtime
    return gz

def _get_lite_plain_text():
    """返回预缓存的明文 JSON 字符串，零序列化开销。"""
    # 触发 gzip 缓存填充（会连带填充 plain 缓存）
    _get_lite_gz_bytes()
    return _LITE_GZ_CACHE.get('plain') or '{}'

@app.route('/api/data')
def api_data():
    if not (authed() or DEMO):
        return jsonify({'error': 'unauthorized'}), 401
    # 移动端或显式 ?lite=1 → 返回 gzip 字节（自定义头，前端手动解压，隧道不吞）
    want_lite = request.args.get('lite') == '1' or _is_mobile()
    # ?plain=1 → 返回明文 JSON（绕过 DecompressionStream 兼容性问题，局域网首选）
    want_plain = request.args.get('plain') == '1'
    if want_plain:
        plain = _get_lite_plain_text()
        return Response(plain, mimetype='application/json',
                        headers={'Cache-Control': 'no-store'})
    if want_lite:
        gz = _get_lite_gz_bytes()
        return Response(gz, mimetype='application/json',
                        headers={'X-Encoding': 'gzip', 'Cache-Control': 'no-store'})
    gz = _get_data_gz()
    return Response(gz, mimetype='application/json',
                    headers={'Content-Encoding': 'gzip', 'Cache-Control': 'no-store'})

# ---------- 实时用户查询（直连 ADB，全量 + 分页 + 鉴权，无 5000 上限） ----------
def _adbc():
    cfg = json.load(open(os.path.join(ROOT, 'config', 'backup_config.json'), encoding='utf-8'))
    return pymysql.connect(host=cfg['host'], port=cfg['port'], user=cfg['user'], password=cfg['password'],
                           database=cfg['database'], connect_timeout=20, read_timeout=600, charset='utf8mb4')

def _ms2str(ms):
    try:
        from datetime import datetime
        return datetime.utcfromtimestamp(int(ms) / 1000).strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return ''

@app.route('/api/users/search')
def api_users_search():
    """实时直连生产库查询用户（协议级），支持 手机号/姓名/协议ID/代理商 模糊搜 + 城市/状态过滤，分页返回。"""
    if not authed() and not DEMO:
        return jsonify({'error': 'unauthorized'}), 401
    if not DEMO and 'user' not in ROLE_MODULES.get(session.get('role'), []):
        return jsonify({'error': '无权限（该角色无用户模块）'}), 403
    q = (request.args.get('q') or '').strip()
    city = (request.args.get('city') or '').strip()
    status = (request.args.get('status') or '').strip()
    try:
        page = max(1, int(request.args.get('page', '1') or 1))
        size = min(200, max(1, int(request.args.get('size', '50') or 50)))
    except Exception:
        page, size = 1, 50
    try:
        conn = _adbc()
        cur = conn.cursor(pymysql.cursors.DictCursor)
        where, params = [], []
        if q:
            where.append('(u.phone LIKE %s OR u.username LIKE %s OR a.id LIKE %s OR ao.agency_name LIKE %s)')
            like = '%' + q + '%'
            params += [like, like, like, like]
        if city:
            where.append('a.sys_city_name LIKE %s'); params.append('%' + city + '%')
        if status:
            where.append('a.status=%s'); params.append(status)
        wsql = (' WHERE ' + ' AND '.join(where)) if where else ''
        cur.execute(
            'SELECT COUNT(DISTINCT a.id) c FROM t_exchange_agreement a LEFT JOIN t_user u ON a.user_id=u.id '
            'LEFT JOIN (SELECT agency_id, ANY_VALUE(agency_name) agency_name FROM t_exchange_order WHERE agency_name IS NOT NULL GROUP BY agency_id) ao ON a.agency_id=ao.agency_id '
            'LEFT JOIN t_distributor d ON a.distributor_id=d.id ' + wsql,
            params)
        total = cur.fetchone()['c']
        cur.execute(
            'SELECT a.id, u.phone, u.username, a.sys_city_name, bp.name AS bpn, ag.name AS agn, a.type, a.status, '
            'a.activation_time, a.rent_expire_time, a.deposit_fee, a.user_rent_id, a.agency_id, ao.agency_name, d.name AS distributor_name '
            'FROM t_exchange_agreement a LEFT JOIN t_user u ON a.user_id=u.id '
            'LEFT JOIN t_battery_product bp ON a.battery_product_id=bp.id '
            'LEFT JOIN t_exchange_rent_package ag ON a.rent_package_id=ag.id '
            'LEFT JOIN (SELECT agency_id, ANY_VALUE(agency_name) agency_name FROM t_exchange_order WHERE agency_name IS NOT NULL GROUP BY agency_id) ao ON a.agency_id=ao.agency_id '
            'LEFT JOIN t_distributor d ON a.distributor_id=d.id '
            + wsql + ' ORDER BY a.activation_time DESC LIMIT %s OFFSET %s',
            params + [size, (page - 1) * size])
        rows = cur.fetchall()
        conn.close()
        out = [{
            'agreement_id': r['id'], 'phone': r['phone'] or '', 'name': r['username'] or '',
            'city': r['sys_city_name'] or '', 'battery_product': r['bpn'] or '', 'package': r['agn'] or '',
            'type': r['type'], 'status': r['status'], 'activate': _ms2str(r['activation_time']),
            'expire': _ms2str(r['rent_expire_time']), 'deposit_fee': round((r['deposit_fee'] or 0) / 100.0, 2),
            'rent_id': r['user_rent_id'], 'agency_id': r['agency_id'],
            'agency': (r['agency_name'] or ('代理商#' + str(r['agency_id'] or '?'))),
            'distributor_name': r['distributor_name'] or '—', 'activate_date': _ms2str(r['activation_time'])[:10]
        } for r in rows]
        return jsonify({'mode': 'realtime', 'total': total, 'page': page, 'size': size, 'rows': out,
                        'q': q, 'city': city, 'status': status,
                        '_note': '实时直连生产库 t_exchange_agreement（全量 + 分页，无 5000 上限）。'})
    except Exception as e:
        return jsonify({'error': '查询失败：' + str(e)[:300]}), 500

# ---------- 实时站点坐标（直连 ADB，大屏地图实时同步） ----------
_geo_cache = {'ts': 0, 'data': None, 'lock': threading.Lock()}

@app.route('/api/geo/sites')
def api_geo_sites():
    """实时直连生产库 t_site 抽取网点坐标+状态，用于大屏地图每 60s 实时同步。支持 ?city= 过滤。"""
    if not DEMO and not authed():
        return jsonify({'error': 'unauthorized'}), 401
    city = (request.args.get('city') or '').strip()
    now = time.time()
    with _geo_cache['lock']:
        cached = (now - _geo_cache['ts'] < 60) and (_geo_cache['data'] is not None)
        payload = _geo_cache['data'] if (cached and not city) else None
    if payload is None:
        try:
            conn = _adbc()
            cur = conn.cursor(pymysql.cursors.DictCursor)
            w = "WHERE is_del=0 AND longitude IS NOT NULL AND latitude IS NOT NULL"
            params = []
            if city:
                w += " AND city LIKE %s"; params.append('%' + city + '%')
            cur.execute(
                "SELECT id, name, city, area, street, community, longitude, latitude, site_status "
                "FROM t_site " + w, params)
            rows = cur.fetchall()
            conn.close()
            sites = [{
                'id': r['id'], 'name': r['name'], 'city': r['city'] or '',
                'area': r['area'] or '', 'street': r['street'] or '', 'community': r['community'] or '',
                'lng': float(r['longitude']), 'lat': float(r['latitude']),
                'status': r['site_status'] or ''
            } for r in rows]
            payload = {'mode': 'realtime', 'source': 't_site', 'count': len(sites), 'sites': sites,
                       '_note': '实时直连生产库 t_site（is_del=0 且含经纬度）。'}
            if not city:
                with _geo_cache['lock']:
                    _geo_cache['data'] = payload; _geo_cache['ts'] = now
        except Exception as e:
            return jsonify({'error': '查询失败：' + str(e)[:300]}), 500
    return jsonify(payload)

# ============ 单用户实时聚合视图（直连 ADB，全量、无 5000 上限） ============
def _haversine(lat1, lng1, lat2, lng2):
    import math
    try:
        R = 6371000.0
        p1 = math.radians(float(lat1)); p2 = math.radians(float(lat2))
        dphi = math.radians(float(lat2) - float(lat1))
        dl = math.radians(float(lng2) - float(lng1))
        a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
        return int(R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))
    except Exception:
        return None

def _cell_light(st):
    """仓体状态 -> 可视化灯色：green=有电池满电, red=充电中未达满, dark=无电池, fault=故障/锁仓"""
    status = (st.get('status') or '').lower()
    soft = (st.get('soft_lock_status') or '').lower()
    if soft == 'on' or status == 'error':
        return 'fault'
    if status == 'charging':
        return 'red'
    if status == 'full':
        return 'green'
    if status == 'none' or not st.get('battery_sn'):
        return 'dark'
    return 'green'

def _count_cells(cells):
    c = {'green': 0, 'red': 0, 'dark': 0, 'fault': 0}
    for x in cells:
        c[_cell_light(x)] += 1
    return c

def _resolve_user(conn, key, by):
    cur = conn.cursor(pymysql.cursors.DictCursor)
    uid = None
    if by == 'agreement':
        cur.execute('SELECT user_id FROM t_exchange_agreement WHERE id=%s AND is_del=0', (key,))
        r = cur.fetchone(); uid = r['user_id'] if r else None
    elif by == 'uid':
        cur.execute('SELECT id FROM t_user WHERE id=%s AND is_del=0', (key,)); r = cur.fetchone(); uid = r['id'] if r else None
    else:  # phone
        cur.execute('SELECT id FROM t_user WHERE phone=%s AND is_del=0', (key,)); r = cur.fetchone(); uid = r['id'] if r else None
    if uid is None:
        return None
    cur.execute(
        'SELECT u.id,u.username,u.phone,u.avatar,u.gender,u.city,u.area,u.user_status,u.create_time,'
        'a.id AS agreement_id,a.status AS agreement_status,a.activation_time,a.rent_expire_time,a.deposit_fee,'
        'a.battery_product_id,a.rent_package_id,a.sys_city_name,a.agency_id,a.site_id,'
        'a.promoter_id,a.distributor_id,a.sign_site_store_employee_id,'
        'a.company_name,a.company_super_admin_consumer_name,a.sign_site_business_name,a.sign_site_business_id,'
        'bp.name AS battery_product,rp.name AS package_name,s.name AS sign_site_name,'
        'p.name AS promoter_name,p.phone AS promoter_phone,'
        'd.name AS distributor_name,'
        'se.name AS store_employee_name,se.phone AS store_employee_phone,se.is_manager AS store_employee_is_manager '
        'FROM t_user u '
        'LEFT JOIN t_exchange_agreement a ON a.user_id=u.id AND a.is_del=0 '
        'LEFT JOIN t_battery_product bp ON a.battery_product_id=bp.id '
        'LEFT JOIN t_exchange_rent_package rp ON a.rent_package_id=rp.id '
        'LEFT JOIN t_site s ON a.site_id=s.id '
        'LEFT JOIN t_promoter p ON a.promoter_id=p.id '
        'LEFT JOIN t_distributor d ON a.distributor_id=d.id '
        'LEFT JOIN t_site_store_employee se ON a.sign_site_store_employee_id=se.id '
        'WHERE u.id=%s ORDER BY a.activation_time DESC LIMIT 1', (uid,))
    return cur.fetchone()

@app.route('/api/user/realtime')
def api_user_realtime():
    """单用户实时聚合：个人信息 + 常去网点 + 换电习惯 + 主用柜机仓体实时状态 + 当前点位 + 附近可换电点位推荐。直连 ADB，全量无 5000 上限。"""
    if not (authed() or DEMO):
        return jsonify({'error': 'unauthorized'}), 401
    key = (request.args.get('key') or '').strip()
    by = (request.args.get('by') or 'phone').strip()
    try:
        radius = max(200, min(20000, int(request.args.get('radius') or 5000)))
    except Exception:
        radius = 5000
    if not key:
        return jsonify({'error': '缺少 key 参数（手机号/协议ID/用户ID），可用 by=phone|agreement|uid 指定类型'}), 400
    try:
        conn = _adbc()
        cur = conn.cursor(pymysql.cursors.DictCursor)
        # 1) 解析用户
        u = _resolve_user(conn, key, by)
        if not u:
            return jsonify({'error': '未找到该用户：%s (by=%s)' % (key, by)}), 404
        uid = u['id']
        # 2) 常去网点 / 习惯 / 最近订单
        cur.execute(
            'SELECT site_id, site_name, COUNT(*) c,'
            "SUM(CASE WHEN order_status='success' THEN 1 ELSE 0 END) ok,"
            "SUM(CASE WHEN order_status='fail' THEN 1 ELSE 0 END) fail,"
            'MAX(create_time) last_t '
            'FROM t_exchange_order WHERE consume_user_id=%s AND is_del=0 AND site_id IS NOT NULL '
            'GROUP BY site_id, site_name ORDER BY c DESC LIMIT 5', (uid,))
        freq_sites = cur.fetchall()
        cur.execute(
            'SELECT COUNT(*) total,'
            "SUM(CASE WHEN order_status='success' THEN 1 ELSE 0 END) ok,"
            "SUM(CASE WHEN order_status='fail' THEN 1 ELSE 0 END) fail,"
            'AVG(mileage) avg_mileage, MIN(create_time) first_t, MAX(create_time) last_t '
            'FROM t_exchange_order WHERE consume_user_id=%s AND is_del=0', (uid,))
        habit = cur.fetchone()
        cur.execute(
            'SELECT id, order_status, exchange_order_status, pay_status, site_id, site_name, take_exchange_id, take_exchange_sn,'
            'back_exchange_id, take_battery_sn, take_battery_power, back_battery_sn, back_battery_power, mileage,'
            'real_pay_price, pay_price, pre_pay_price, is_refund, pay_way, take_user_phone, back_user_phone,'
            'consume_user_phone, bike_sn, bike_battery_sn, agency_name, exchange_error_message, create_time '
            'FROM t_exchange_order WHERE consume_user_id=%s AND is_del=0 '
            'ORDER BY create_time DESC LIMIT 200', (uid,))
        orders = cur.fetchall()
        # 2.5) 订单金额聚合（全量，不限 15 条）—— 供前端 6 张 KPI 卡使用真实财务数据
        order_stats = {}
        agency_name = None
        try:
            cur.execute(
                'SELECT COUNT(*) total,'
                "SUM(CASE WHEN is_refund=1 THEN 1 ELSE 0 END) refund_cnt,"
                "SUM(CASE WHEN is_refund=1 THEN real_pay_price ELSE 0 END) refund_amt,"
                "SUM(CASE WHEN is_refund=0 AND order_status='success' THEN 1 ELSE 0 END) success_cnt,"
                "SUM(CASE WHEN is_refund=0 AND order_status='success' THEN real_pay_price ELSE 0 END) success_amt,"
                'SUM(real_pay_price) total_amt,'
                "SUM(CASE WHEN order_status='fail' THEN 1 ELSE 0 END) fail_cnt,"
                'SUM(expend_power_fee) power_fee, SUM(mileage) total_mileage_m,'
                'MAX(agency_name) agency_name '
                'FROM t_exchange_order WHERE consume_user_id=%s AND is_del=0', (uid,))
            osr = cur.fetchone() or {}
            order_stats = {
                'total': int(osr.get('total') or 0),
                'total_amt': float(osr.get('total_amt') or 0),
                'success_cnt': int(osr.get('success_cnt') or 0),
                'success_amt': float(osr.get('success_amt') or 0),
                'refund_cnt': int(osr.get('refund_cnt') or 0),
                'refund_amt': float(osr.get('refund_amt') or 0),
                'fail_cnt': int(osr.get('fail_cnt') or 0),
                'power_fee': float(osr.get('power_fee') or 0),
                'total_mileage': float(osr.get('total_mileage_m') or 0) / 1000.0,
            }
            agency_name = osr.get('agency_name') or None
        except Exception:
            order_stats = {'total': 0, 'total_amt': 0, 'success_cnt': 0, 'success_amt': 0,
                           'refund_cnt': 0, 'refund_amt': 0, 'fail_cnt': 0, 'power_fee': 0, 'total_mileage': 0}
        # 2.6) 在管车辆 + 关联电池（真实归属关系）
        vehicles = []; batteries = []
        try:
            cur.execute(
                'SELECT ub.id, ub.user_id, ub.own_type, ub.bike_id, ub.bike_name, ub.bike_vin, ub.bike_images,'
                'ub.is_selected, ub.active_time, b.bike_sn, b.brand_id '
                'FROM zc_user_bike ub LEFT JOIN zc_bike b ON ub.bike_id=b.id '
                'WHERE ub.user_id=%s AND ub.is_del=0', (uid,))
            vehicles = cur.fetchall() or []
        except Exception:
            vehicles = []
        try:
            cur.execute(
                'SELECT br.battery_id, br.battery_device_sn, br.belong_type, br.bike_sn, br.bike_user_phone,'
                'b.battery_status, b.online_status, b.last_location_address, bs.power, bs.cycle '
                'FROM t_battery_belong_relation br '
                'LEFT JOIN t_battery b ON br.battery_id=b.id '
                'LEFT JOIN t_battery_status bs ON b.id=bs.battery_id '
                'WHERE br.belong_phone=%s AND br.is_del=0', (u.get('phone'),))
            batteries = cur.fetchall() or []
        except Exception:
            batteries = []
        # 小时分布 + 用过的柜机统计（Python 计算，规避 ADB 时间函数差异）
        hour_dist = [0] * 24
        used_cabs = {}
        from datetime import datetime
        for o in orders:
            ct = o.get('create_time')
            if ct:
                try:
                    hour_dist[datetime.utcfromtimestamp(int(ct) / 1000).hour] += 1
                except Exception:
                    pass
            for ex in (o.get('take_exchange_id'), o.get('back_exchange_id')):
                if ex:
                    used_cabs[ex] = used_cabs.get(ex, 0) + 1
        # 3) 主用柜机 + 当前点位
        primary_cab = max(used_cabs, key=used_cabs.get) if used_cabs else None
        current_cab = None
        if orders:
            current_cab = orders[0].get('take_exchange_id') or orders[0].get('back_exchange_id')
        # 4) 全量柜机坐标 + 实时可用（一次取，Python 端按距离过滤）
        cur.execute('SELECT id, lat, lng, site_id, device_sn, online_status, device_type_id '
                    'FROM t_exchange WHERE is_del=0 AND lat IS NOT NULL AND lng IS NOT NULL')
        cab_coords = {r['id']: r for r in cur.fetchall()}
        cur.execute(
            'SELECT exchange_id,'
            "SUM(CASE WHEN status IN ('full','charging') THEN 1 ELSE 0 END) avail,"
            "SUM(CASE WHEN status='error' OR soft_lock_status='on' THEN 1 ELSE 0 END) fault,"
            'COUNT(*) total FROM t_exchange_store WHERE is_del=0 GROUP BY exchange_id')
        avail_map = {r['exchange_id']: r for r in cur.fetchall()}
        cur.execute('SELECT id, name, address, images, city, area, street FROM t_site WHERE is_del=0')
        site_map = {r['id']: r for r in cur.fetchall()}

        def cab_detail(cab_id):
            if not cab_id or cab_id not in cab_coords:
                return None
            c = cab_coords[cab_id]
            cur.execute(
                'SELECT id, site_id, device_sn, online_status, lat, lng, device_type_id, last_upload_time '
                'FROM t_exchange WHERE id=%s AND is_del=0', (cab_id,))
            c = cur.fetchone()
            if not c:
                return None
            cur.execute('SELECT image, show_name, store_num FROM t_exchange_model WHERE id=%s', (c.get('device_type_id'),))
            model = cur.fetchone() or {}
            cur.execute(
                'SELECT number, status, soft_lock_status, battery_sn, door_status, lock_status, error, touch_status '
                'FROM t_exchange_store WHERE exchange_id=%s AND is_del=0 ORDER BY number', (cab_id,))
            cells = cur.fetchall()
            site = site_map.get(c.get('site_id')) or {}
            return {
                'cabinet_id': cab_id, 'device_sn': c.get('device_sn'),
                'online_status': c.get('online_status'), 'lat': c.get('lat'), 'lng': c.get('lng'),
                'site_name': site.get('name'), 'site_address': site.get('address'),
                'site_images': site.get('images'),
                'model_image': model.get('image'), 'model_name': model.get('show_name'),
                'last_upload_time': c.get('last_upload_time'),
                'cells': [{'number': x.get('number'), 'light': _cell_light(x), 'status': x.get('status'),
                           'battery_sn': x.get('battery_sn'), 'soft_lock': x.get('soft_lock_status'),
                           'error': x.get('error')} for x in cells],
                'cell_counts': _count_cells(cells),
            }

        primary_detail = cab_detail(primary_cab)
        used_cab_list = []
        for cid, cnt in sorted(used_cabs.items(), key=lambda kv: -kv[1])[:10]:
            d = cab_detail(cid)
            if d:
                d['use_count'] = cnt
                used_cab_list.append(d)
        # 5) 推荐附近可换电点位
        cur_pt = None
        if current_cab and current_cab in cab_coords:
            cc = cab_coords[current_cab]; cur_pt = (cc.get('lat'), cc.get('lng'))
        if not cur_pt and primary_cab and primary_cab in cab_coords:
            cc = cab_coords[primary_cab]; cur_pt = (cc.get('lat'), cc.get('lng'))
        recs = []
        if cur_pt:
            for cid, c in cab_coords.items():
                av = avail_map.get(cid, {})
                if (av.get('avail') or 0) <= 0 or cid == current_cab:
                    continue
                d = _haversine(cur_pt[0], cur_pt[1], c.get('lat'), c.get('lng'))
                if d is None or d > radius:
                    continue
                site = site_map.get(c.get('site_id')) or {}
                recs.append({
                    'cabinet_id': cid, 'device_sn': c.get('device_sn'),
                    'site_name': site.get('name'), 'address': site.get('address'),
                    'site_images': site.get('images'),
                    'distance_m': d, 'avail': av.get('avail'), 'fault': av.get('fault'),
                    'lat': c.get('lat'), 'lng': c.get('lng'),
                    'nav_url': 'https://uri.amap.com/navigation?to=%s,%s,%s&mode=car&policy=1&src=citybike&coordinate=gaode&callnative=1'
                               % (c.get('lng'), c.get('lat'), (site.get('name') or '换电柜')),
                })
            recs.sort(key=lambda r: r['distance_m'])
            recs = recs[:10]
        conn.close()
        last_fail = bool(orders and orders[0].get('order_status') == 'fail')
        # 代理商名补到 user 上（agreement 无 name 列，取自在订单表）
        if agency_name and u:
            u['agency_name'] = agency_name
        return jsonify({
            'mode': 'realtime', 'source': 'ADB sharing-citybike-pro',
            'user': u, 'freq_sites': freq_sites, 'habit': habit, 'hour_dist': hour_dist,
            'order_stats': order_stats, 'agency_name': agency_name,
            'recent_orders': orders[:15], 'vehicles': vehicles, 'batteries': batteries,
            'primary_cabinet': primary_detail,
            'used_cabinets': used_cab_list, 'current_cabinet_id': current_cab,
            'current_point': cur_pt, 'recommend': recs, 'radius_m': radius,
            'last_order_failed': last_fail,
            '_note': '单用户实时聚合：直连生产库，全量无 5000 上限。cell 灯色 green=有电池满电, red=充电中, dark=无电池, fault=故障/锁仓。人员/渠道字段(推广员/分销商/网点导购/企业主/签约商务)均为生产库真实关联，缺失则标「待接入」。',
        })
    except Exception as e:
        return jsonify({'error': '查询失败：' + str(e)[:400]}), 500

@app.route('/api/site/realtime')
def api_site_realtime():
    """单网点实时聚合：网点基本信息 + 设备(柜机SN/电池SN/历史柜) + 经营设置(电表/结算/商户分成) + 按套餐销量(当天/3/7/30天/累计)。
    直连 ADB，全量无 5000 上限。干净字段实时取；模糊字段(导购/创客手机外、分成比例·余额·提现·电费单价等)标 pending 待补，绝不编造。"""
    if not (authed() or DEMO):
        return jsonify({'error': 'unauthorized'}), 401
    key = (request.args.get('key') or '').strip()
    by = (request.args.get('by') or 'name').strip()  # id | name
    bp = (request.args.get('battery_product') or '').strip()    # 可选：电池产品ID 过滤
    mer = (request.args.get('merchant') or '').strip()          # 可选：商户ID 或 名称 过滤
    if not key:
        return jsonify({'error': '缺少 key 参数（网点ID 或 网点名称），可用 by=id|name 指定类型'}), 400
    try:
        import time as _time
        conn = _adbc()
        cur = conn.cursor(pymysql.cursors.DictCursor)
        # 1) 解析网点（含可选 电池产品 / 商户 过滤）
        where = 's.is_del=0'
        params = []
        if by == 'id':
            where += ' AND s.id=%s'; params.append(int(key) if key.isdigit() else key)
        else:
            where += ' AND s.name LIKE %s'; params.append('%' + key + '%')
        if bp:
            where += ' AND s.battery_product_id=%s'; params.append(int(bp) if bp.isdigit() else bp)
        if mer:
            if mer.isdigit():
                where += ' AND s.merchant_id=%s'; params.append(int(mer))
            else:
                where += ' AND m.name LIKE %s'; params.append('%' + mer + '%')
        cur.execute(
            'SELECT s.id,s.name,s.logo,s.images,s.site_status,s.create_time,s.start_open_time,s.close_time,'
            's.merchant_id,m.name AS merchant_name,m.lp_phone AS merchant_phone,'
            's.business_id,s.business_name,'
            's.store_manager_maker_id,s.store_manager_name,s.store_manager_tel,'
            's.alone_meter_status,s.alone_meter_number,s.electric_settle_way,s.electric_settle_cycle,'
            's.battery_product_id '
            'FROM t_site s LEFT JOIN t_merchant m ON s.merchant_id=m.id '
            'WHERE ' + where + ' ORDER BY s.id LIMIT 1', params)
        site = cur.fetchone()
        if not site:
            return jsonify({'error': '未找到该网点：%s (by=%s)' % (key, by)}), 404
        sid = site['id']
        # 2) 设备：柜机SN + 电池SN + 历史柜（site_unbind_time 非空=曾绑定现已解绑）
        cur.execute('SELECT id,device_sn,online_status,site_bind_time,site_unbind_time '
                    'FROM t_exchange WHERE site_id=%s AND is_del=0', (sid,))
        cabs = cur.fetchall()
        # 当前绑定判定：site_unbind_time 为空/0，或 最近一次事件为绑定(bind>=unbind) → 视为当前在网；
        # 仅当 unbind 时间晚于 bind（最近被解绑且未再绑定）才归为历史柜。
        def _is_current(c):
            ub = c.get('site_unbind_time')
            if ub is None or ub == 0:
                return True
            return (c.get('site_bind_time') or 0) >= ub
        cur_cabs = [c for c in cabs if _is_current(c)]
        hist_cabs = [c for c in cabs if not _is_current(c)]
        cur_ids = [c['id'] for c in cur_cabs]
        bat_sn = []
        if cur_ids:
            ph = ','.join(['%s'] * len(cur_ids))
            cur.execute('SELECT DISTINCT battery_sn FROM t_exchange_store '
                        'WHERE exchange_id IN (' + ph + ') AND is_del=0 AND battery_sn IS NOT NULL AND battery_sn<>%s',
                        cur_ids + [''])
            bat_sn = [r['battery_sn'] for r in cur.fetchall() if r['battery_sn']]
        # 3) 经营设置：商户分成（t_profit_config 仅金额，无比例/名称列）
        cur.execute('SELECT id,profit_fee FROM t_profit_config WHERE site_id=%s AND is_del=0 ORDER BY id', (sid,))
        profit = cur.fetchall()
        # 4) 销售 by 套餐（当天/近3/7/30天/累计，仅 success 计为销量）
        now = int(_time.time() * 1000)
        import datetime as _dt
        # ADB create_time 为 UTC 毫秒（全库统一 utcfromtimestamp+8h 展示），今日零点须用 UTC 零点
        utc_mid = _dt.datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        day0 = int(_dt.datetime.timestamp(utc_mid) * 1000)
        d3 = now - 3 * 86400000
        d7 = now - 7 * 86400000
        d30 = now - 30 * 86400000
        # 套餐维度：t_exchange_order.user_package_id 与 t_exchange_package.id 不匹配、battery_product_id 关联会扇出，
        # 故按 battery_product_name（电池产品，即用户侧"套餐"口径，无扇出、恒有值）分组；精确套餐名映射标 pending 待补。
        cur.execute(
            'SELECT o.battery_product_name AS pkg,'
            'SUM(CASE WHEN o.create_time>=%s AND o.exchange_order_status=%s THEN 1 ELSE 0 END) d0,'
            'SUM(CASE WHEN o.create_time>=%s AND o.exchange_order_status=%s THEN 1 ELSE 0 END) d3,'
            'SUM(CASE WHEN o.create_time>=%s AND o.exchange_order_status=%s THEN 1 ELSE 0 END) d7,'
            'SUM(CASE WHEN o.create_time>=%s AND o.exchange_order_status=%s THEN 1 ELSE 0 END) d30,'
            'SUM(CASE WHEN o.exchange_order_status=%s THEN 1 ELSE 0 END) total '
            'FROM t_exchange_order o '
            'WHERE o.site_id=%s AND o.is_del=0 AND o.battery_product_name IS NOT NULL AND o.battery_product_name<>%s '
            'GROUP BY o.battery_product_name ORDER BY total DESC',
            (day0, 'success', d3, 'success', d7, 'success', d30, 'success', 'success', sid, ''))
        sales = cur.fetchall()
        conn.close()
        pending = [
            '导购ID#名称：t_site 无独立导购字段，需接 t_site_store_employee',
            '网点电费单价：t_site 无站点级单价列，单价在 t_exchange_electric_settlement.settle_price(按结算单)',
            '商户分成比例 / 各项累计分成 / 取消分成：t_profit_config 仅金额(profit_fee)，需聚合 t_maker_earning_subsidy_log',
            '导购分成费用/比例/累计/取消：待接入',
            '网点创客余额：需聚合 t_user_score_earning(按 maker/user)',
            '已提现金额：需聚合 t_withdraw_notify_send_log(按提现流水)',
            '套餐精确名称映射：user_package_id 与 t_exchange_package.id 不匹配、battery_product_id 关联会扇出；本期销售按 battery_product_name(电池产品) 口径展示，精确套餐名待补',
        ]
        return jsonify({
            'mode': 'realtime', 'source': 'ADB sharing-citybike-pro',
            'site': site,
            'cabinets': [{'device_sn': c.get('device_sn'), 'online': c.get('online_status')}
                         for c in cur_cabs],
            'battery_sns': bat_sn[:300],
            'historical_cabinets': [c.get('device_sn') for c in hist_cabs],
            'profit_config': profit,
            'sales_by_package': sales,
            'pending': pending,
            '_note': '单网点实时聚合：直连生产库，全量无 5000 上限。导购/创客手机外、分成比例·余额·提现·电费单价等分散流水表，本期标 pending 待补，绝不编造。',
        })
    except Exception as e:
        return jsonify({'error': '查询失败：' + str(e)[:400]}), 500

@app.route('/site')
def site_view():
    """单网点实时视图页（独立、离线可用、不依赖快照数据），仿照单用户视图。"""
    if not (authed() or DEMO):
        return redirect('/login')
    p = os.path.join(ROOT, 'html', 'site_view.html')
    if os.path.exists(p):
        return Response(open(p, encoding='utf-8').read(), mimetype='text/html')
    return 'site_view.html not found', 404

@app.route('/user')
def user_view():
    """单用户实时视图页（独立、离线可用、不依赖快照数据）"""
    if not (authed() or DEMO):
        return redirect('/login')
    p = os.path.join(ROOT, 'html', 'user_view.html')
    if os.path.exists(p):
        return Response(open(p, encoding='utf-8').read(), mimetype='text/html')
    return 'user_view.html not found', 404

# ---------- 城市区域分布：常驻面板的实时聚合接口 ----------
@app.route('/api/ops/region', methods=['GET'])
def api_ops_region():
    """按城市聚合各区数据：users/sites/cabinets/batteries/swap30/riding_km。
    数据源：t_exchange_order（site_area/site_city 冗余字段直取）、t_exchange→t_site.area、
    t_battery→t_exchange.device_sn 关联、t_user.city+area、t_site.city+area。
    单点查询失败不影响整体（try/except 隔离）。"""
    if not (authed() or DEMO):
        return jsonify({'error': 'unauthorized'}), 401
    city = (request.args.get('city') or '').strip()
    if not city:
        return jsonify({'error': '缺少 city 参数（例：深圳市）', 'areas': [], 'summary': {}}), 400
    try:
        import time as _time
        conn = _adbc()
        cur = conn.cursor(pymysql.cursors.DictCursor)
        area_map = {}  # area -> dict

        def _ensure(area):
            if area and area not in area_map:
                area_map[area] = {
                    'area': area, 'users': 0, 'sites': 0, 'cabinets': 0,
                    'batteries': 0, 'swap30': 0, 'riding_km': 0.0,
                }
            return area_map.get(area)

        now_ms = int(_time.time() * 1000)
        d30_ms = now_ms - 30 * 24 * 3600 * 1000
        # 自适应：以 DB 最新订单时间锚定 30 天窗口（避免生产 DB 无近期数据时窗口落空）
        try:
            cur.execute("SELECT MAX(create_time) mx FROM t_exchange_order")
            mx = (cur.fetchone() or {}).get('mx')
            if mx and int(mx) > 0:
                d30_ms = int(mx) - 30 * 24 * 3600 * 1000
        except Exception:
            pass

        # 1) t_user 按 area 聚合
        try:
            cur.execute(
                "SELECT area, COUNT(*) c FROM t_user "
                "WHERE city=%s AND area IS NOT NULL AND area<>'' AND is_del=0 "
                "GROUP BY area", (city,))
            for r in cur.fetchall() or []:
                row = _ensure(r['area']); 
                if row: row['users'] = int(r['c'] or 0)
        except Exception as e:
            print('[ops/region] users err:', e)

        # 2) t_site 按 area 聚合
        try:
            cur.execute(
                "SELECT area, COUNT(*) c FROM t_site "
                "WHERE city=%s AND area IS NOT NULL AND area<>'' AND is_del=0 "
                "GROUP BY area", (city,))
            for r in cur.fetchall() or []:
                row = _ensure(r['area']); 
                if row: row['sites'] = int(r['c'] or 0)
        except Exception as e:
            print('[ops/region] sites err:', e)

        # 3) t_exchange 通过 site_id 关联 t_site.area 聚合
        try:
            cur.execute(
                "SELECT s.area area, COUNT(*) c FROM t_exchange e "
                "JOIN t_site s ON e.site_id=s.id "
                "WHERE s.city=%s AND s.area IS NOT NULL AND s.area<>'' "
                "AND s.is_del=0 AND e.is_del=0 "
                "GROUP BY s.area", (city,))
            for r in cur.fetchall() or []:
                row = _ensure(r['area']); 
                if row: row['cabinets'] = int(r['c'] or 0)
        except Exception as e:
            print('[ops/region] cabinets err:', e)

        # 4) t_battery 通过 last_upload_exchange_sn/last_back_exchange_sn/last_take_exchange_sn
        #    关联 t_exchange.device_sn → t_site.area
        try:
            cur.execute(
                "SELECT s.area area, COUNT(DISTINCT b.id) c FROM t_battery b "
                "JOIN t_exchange e ON e.device_sn IN (b.last_upload_exchange_sn, b.last_back_exchange_sn, b.last_take_exchange_sn) "
                "JOIN t_site s ON e.site_id=s.id "
                "WHERE s.city=%s AND s.area IS NOT NULL AND s.area<>'' "
                "AND b.is_del=0 AND e.is_del=0 AND s.is_del=0 "
                "GROUP BY s.area", (city,))
            for r in cur.fetchall() or []:
                row = _ensure(r['area']); 
                if row: row['batteries'] = int(r['c'] or 0)
        except Exception as e:
            print('[ops/region] batteries err:', e)

        # 5) t_exchange_order 30 天换电次数 + 骑行距离（site_area/site_city 冗余字段直取）
        # 注：exchange_order_status='success' = 实际成功换电（更准），order_status 业务结算可能滞后
        try:
            cur.execute(
                "SELECT site_area area, COUNT(*) swap30, "
                "COALESCE(SUM(mileage),0)/1000.0 riding_km "
                "FROM t_exchange_order "
                "WHERE site_city=%s AND site_area IS NOT NULL AND site_area<>'' "
                "AND is_del=0 AND exchange_order_status='success' AND create_time>=%s "
                "GROUP BY site_area", (city, d30_ms))
            for r in cur.fetchall() or []:
                row = _ensure(r['area']); 
                if row:
                    row['swap30'] = int(r['swap30'] or 0)
                    row['riding_km'] = float(r['riding_km'] or 0.0)
        except Exception as e:
            print('[ops/region] orders err:', e)

        conn.close()

        # 按用户数降序排（无用户数按 area 名兜底）
        areas = sorted(area_map.values(), key=lambda x: (-(x['users'] or 0), x['area']))
        # 总览
        summary = {
            'city': city,
            'areas': len(areas),
            'users': sum(a['users'] for a in areas),
            'sites': sum(a['sites'] for a in areas),
            'cabinets': sum(a['cabinets'] for a in areas),
            'batteries': sum(a['batteries'] for a in areas),
            'swap30': sum(a['swap30'] for a in areas),
            'riding_km': round(sum(a['riding_km'] for a in areas), 1),
        }
        return jsonify({
            'mode': 'realtime',
            'source': 'ADB sharing-citybike-pro',
            'city': city,
            'areas': areas,
            'summary': summary,
            '_note': '区域聚合：users=t_user 按区，sites=t_site 按区，cabinets=t_exchange→site.area，batteries=t_battery 经 t_exchange.device_sn 桥接 site.area，swap30/riding_km=t_exchange_order.site_area 冗余字段直取 30 天成功单。',
        })
    except Exception as e:
        return jsonify({'error': '聚合失败', 'detail': str(e), 'areas': [], 'summary': {}}), 500

if __name__ == '__main__':
    port = int(os.environ.get('CB_PORT', 5000))
    # ---------- 实时刷新器：后台周期性重建 dashboard_data.json（主看板实时同步库） ----------
    if LIVE_MODE:
        import sys as _sys, time as _time, subprocess as _sp
        _ex = os.path.join(ROOT, 'scripts', 'extract_dashboard.py')
        _mb = os.path.join(ROOT, 'scripts', 'build_mobile_data.py')
        def _run_extract():
            try:
                _sp.run([_sys.executable, _ex], cwd=ROOT,
                        stdout=_sp.DEVNULL, stderr=_sp.DEVNULL, timeout=1800)
                _sp.run([_sys.executable, _mb], cwd=ROOT,
                        stdout=_sp.DEVNULL, stderr=_sp.DEVNULL, timeout=1800)
            except Exception as e:
                print('[live-refresh] 重建失败:', e)
        def _live_loop():
            while True:
                _run_extract()
                _time.sleep(LIVE_REFRESH)
        threading.Thread(target=_live_loop, daemon=True).start()
        threading.Thread(target=_run_extract, daemon=True).start()  # 启动即首建
        print('[live-refresh] 已启用：每 %d 秒重建一次实时快照（提取脚本 + 手机版）' % LIVE_REFRESH)
    print('城市换电看板后端鉴权服务已启动： http://0.0.0.0:%d  (STRIP_DATA=%s, LIVE=%s)' % (port, STRIP_DATA, LIVE_MODE))
    app.run(host='0.0.0.0', port=port, debug=False)
