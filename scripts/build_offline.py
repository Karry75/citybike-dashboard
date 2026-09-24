#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""构建单文件离线看板 citybike_offline.html（无网络/无防火墙/无隧道）。

- 复用 server.py 的 STRIP 改造：掏空内联 DATA，注入引导脚本
- 把 dashboard_data_lite.json.gz（~2MB）base64 内联进 HTML
- 引导脚本优先读内嵌数据（atob -> DecompressionStream 解压），失败才尝试 fetch（联网兜底）
- 输出单文件 citybike_offline.html，手机用浏览器打开 file:// 即可
"""
import re, os, gzip, base64

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DASHBOARD = os.path.join(BASE, 'citybike_dashboard', 'index.html')
LITE = os.path.join(BASE, 'data', 'dashboard_data_lite.json')
OUT = os.path.join(BASE, 'citybike_offline.html')

assert os.path.exists(DASHBOARD), 'citybike_dashboard/index.html 不存在'
assert os.path.exists(LITE), 'data/dashboard_data_lite.json 不存在'

html = open(DASHBOARD, encoding='utf-8').read()

# 1) 掏空内联 DATA（与 STRIP 模式一致）
html = re.sub(r'const DATA = (\{[\s\S]*?\});\n// ── 数据净化',
              'const DATA = {};\n// ── 数据净化', html, count=1)

# 2) 内联 gz 数据（base64）
with open(LITE, 'rb') as f:
    raw = f.read()
gz = gzip.compress(raw, compresslevel=9)
b64 = base64.b64encode(gz).decode('ascii')
print('gz 大小: %d 字节 (%.2f MB) | base64: %d 字符' % (len(gz), len(gz)/1024/1024, len(b64)))

# 3) 引导脚本：优先内嵌数据，失败回退 fetch
boot = (
    '<div id="boot-loading" style="position:fixed;inset:0;z-index:99999;'
    'display:flex;flex-direction:column;align-items:center;justify-content:center;gap:16px;'
    'background:#0d1b2e;color:#a8c4ee;font-family:-apple-system,\'PingFang SC\',\'Microsoft YaHei\',sans-serif;font-size:15px">'
    '<div style="width:44px;height:44px;border:4px solid #1a3a5c;border-top-color:#3895ff;'
    'border-radius:50%;animation:bootspin 1s linear infinite"></div>'
    '<div>正在加载看板数据…（离线版）</div></div>'
    '<style>@keyframes bootspin{to{transform:rotate(360deg)}}</style>'
    '<script>window.__BACKEND=true;'
    'var __GZ__="' + b64 + '";'
    'window.__EMBEDDED_GZ=__GZ__;'
    '(function(){'
    'var el=document.getElementById("boot-loading");'
    'function fail(msg){if(el)el.innerHTML="\\u26a0\\ufe0f "+msg+"\\uff0c\\u8bf7\\u68c0\\u67e5\\u540e\\u5237\\u65b0";}'
    # ⚠️ 顶层 const DATA 不挂 window，必须逐 key 回填对象本身，否则全看板空白且不报错
    'function start(d){try{for(var k in d){if(Object.prototype.hasOwnProperty.call(d,k)){DATA[k]=d[k];}}window.DATA=DATA;if(el)el.remove();if(typeof bootApp==="function")bootApp();}catch(e){fail("\\u6e32\\u67d3\\u5f02\\u5e38");console.error(e);}}'
    'function gunzip(buf){'
    'if(typeof DecompressionStream==="undefined")return Promise.resolve(buf);'
    'try{var ds=new DecompressionStream("gzip");var s=new Response(buf).body.pipeThrough(ds);return new Response(s).arrayBuffer();}catch(e){return Promise.resolve(buf);}'
    '}'
    'function embedded(){'
    'try{var bin=atob(window.__EMBEDDED_GZ);var bytes=new Uint8Array(bin.length);'
    'for(var i=0;i<bin.length;i++)bytes[i]=bin.charCodeAt(i);'
    'return gunzip(bytes.buffer).then(function(ab){return JSON.parse(new TextDecoder("utf-8").decode(ab));}).then(start);}'
    'catch(e){return Promise.reject(e);}'
    '}'
    'embedded().catch(function(e){console.warn("embedded failed, try fetch",e);'
    'fetch("./dashboard_data_lite.json.gz",{cache:"no-store"}).then(function(r){if(!r.ok)throw new Error("gz "+r.status);return r.arrayBuffer();})'
    '.then(gunzip).then(function(ab){return JSON.parse(new TextDecoder("utf-8").decode(ab));}).then(start)'
    '.catch(function(e2){fetch("./dashboard_data_lite.json",{cache:"no-store"}).then(function(r){if(!r.ok)throw new Error("json "+r.status);return r.json();}).then(start)'
    '.catch(function(e3){fail("\\u6570\\u636e\\u52a0\\u8f7d\\u5931\\u8d25");console.error(e3);});});'
    '});'
    '})();</script>\n</body>'
)
# ⚠️ 替换「最后一个」</body>（ECharts 内部有 </body> 字面量，replace 首个会切坏 HTML）
last_body = html.rfind('</body>')
if last_body < 0:
    raise Exception('找不到 </body>')
html = html[:last_body] + boot + html[last_body + len('</body>'):]

with open(OUT, 'w', encoding='utf-8') as f:
    f.write(html)

sz = os.path.getsize(OUT)
print('构建完成:')
print('  citybike_offline.html : %d 字节 (%.2f MB)' % (sz, sz/1024/1024))
print('  DATA 已掏空          : %s' % ('const DATA = {}' in html))
print('  内嵌 gz 数据          : %s' % ('window.__EMBEDDED_GZ' in html))
print('  __BACKEND=true        : %s' % ('window.__BACKEND=true' in html))
print('输出: %s' % OUT)
