#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""构建纯静态轻量看板（无后端、无隧道、无需局域网 IP）。

- 复用 server.py 的 STRIP 改造逻辑：掏空内联 DATA，注入引导脚本
- 引导脚本 fetch 同目录 gz 压缩数据 ./dashboard_data_lite.json.gz（浏览器原生解压），
  失败时回退到未压缩 ./dashboard_data_lite.json
- 输出到 citybike_static/，连同两个数据文件一起静态托管
"""
import re, shutil, os, gzip

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DASHBOARD = os.path.join(BASE, 'citybike_dashboard', 'index.html')
LITE = os.path.join(BASE, 'data', 'dashboard_data_lite.json')
OUTDIR = os.path.join(BASE, 'citybike_static')

assert os.path.exists(DASHBOARD), 'citybike_dashboard/index.html 不存在，请先 build_html.py'
assert os.path.exists(LITE), 'data/dashboard_data_lite.json 不存在，请先 build_lite_data.py'

html = open(DASHBOARD, encoding='utf-8').read()

# 1) 掏空内联 DATA（与 server.py STRIP 模式一致的正则）
html = re.sub(r'const DATA = (\{[\s\S]*?\});\n// ── 数据净化',
              'const DATA = {};\n// ── 数据净化', html, count=1)

# 2) 注入 boot 引导脚本：优先拉 gz（小），失败回退未压缩 json
# ⚠️ 必须替换「最后一个」</body>（ECharts 库内部含 </body> 字面量，
#    普通 replace 会命中错误的第一个，导致 HTML 结构崩坏！）
boot = (
    '<div id="boot-loading" style="position:fixed;inset:0;z-index:99999;'
    'display:flex;flex-direction:column;align-items:center;justify-content:center;gap:16px;'
    'background:#0d1b2e;color:#a8c4ee;font-family:-apple-system,\'PingFang SC\',\'Microsoft YaHei\',sans-serif;font-size:15px">'
    '<div style="width:44px;height:44px;border:4px solid #1a3a5c;border-top-color:#3895ff;'
    'border-radius:50%;animation:bootspin 1s linear infinite"></div>'
    '<div>正在加载看板数据…（极速版约几秒）</div></div>'
    '<style>@keyframes bootspin{to{transform:rotate(360deg)}}</style>'
    '<script>window.__BACKEND=true;'
    '(function(){'
    'var el=document.getElementById("boot-loading");'
    'function fail(msg){if(el)el.innerHTML="\\u26a0\\ufe0f "+msg+"\\uff0c\\u8bf7\\u68c0\\u67e5\\u7f51\\u7edc\\u540e\\u5237\\u65b0";}'
    # ⚠️ 顶层 const DATA 不挂 window，必须逐 key 回填对象本身，否则全看板空白且不报错
    'function start(d){try{for(var k in d){if(Object.prototype.hasOwnProperty.call(d,k)){DATA[k]=d[k];}}window.DATA=DATA;if(el)el.remove();if(typeof bootApp==="function")bootApp();}catch(e){fail("\\u6e32\\u67d3\\u5f02\\u5e38");console.error(e);}}'
    'function gunzip(buf){'
    'if(typeof DecompressionStream==="undefined")return Promise.resolve(buf);'
    'try{var ds=new DecompressionStream("gzip");var s=new Response(buf).body.pipeThrough(ds);return new Response(s).arrayBuffer();}catch(e){return Promise.resolve(buf);}'
    '}'
    'fetch("./dashboard_data_lite.json.gz",{cache:"no-store"}).then(function(r){'
    'if(!r.ok)throw new Error("gz "+r.status);return r.arrayBuffer();'
    '}).then(gunzip).then(function(ab){return JSON.parse(new TextDecoder("utf-8").decode(ab));}).then(start)'
    '.catch(function(e){console.warn("gz failed, fallback json",e);'
    'fetch("./dashboard_data_lite.json",{cache:"no-store"}).then(function(r){if(!r.ok)throw new Error("json "+r.status);return r.json();}).then(start)'
    '.catch(function(e2){fail("\\u6570\\u636e\\u52a0\\u8f7d\\u5931\\u8d25");console.error(e2);});'
    '});'
    '})();</script>\n</body>'
)
# ⚠️ 必须替换「最后一个」</body>（ECharts 库内部含 </body> 字面量，
#    普通 replace 会命中错误的第一个，导致 HTML 结构崩坏！）
last_body = html.rfind('</body>')
if last_body < 0:
    raise Exception('找不到 </body>')
html = html[:last_body] + boot + html[last_body + len('</body>'):]

os.makedirs(OUTDIR, exist_ok=True)
with open(os.path.join(OUTDIR, 'index.html'), 'w', encoding='utf-8') as f:
    f.write(html)
shutil.copy(LITE, os.path.join(OUTDIR, 'dashboard_data_lite.json'))

# 3) 生成 gzip 版（最大压缩，供移动端快速加载）
gz_path = os.path.join(OUTDIR, 'dashboard_data_lite.json.gz')
with open(LITE, 'rb') as f_in, open(gz_path, 'wb') as f_out:
    f_out.write(gzip.compress(f_in.read(), compresslevel=9))

# 报告
idx = html.find('const DATA = {}')
gz_size = os.path.getsize(gz_path)
lite_size = os.path.getsize(os.path.join(OUTDIR, 'dashboard_data_lite.json'))
print('构建完成:')
print('  index.html          : %d 字节 (%.2f MB)' % (len(html), len(html)/1024/1024))
print('  DATA 已掏空         : %s' % (idx >= 0))
print('  boot fetch gz       : %s' % ('./dashboard_data_lite.json.gz' in html))
print('  __BACKEND=true      : %s' % ('window.__BACKEND=true' in html))
print('  lite json (兜底)    : %d 字节 (%.1f MB)' % (lite_size, lite_size/1024/1024))
print('  lite json.gz (主)   : %d 字节 (%.2f MB)' % (gz_size, gz_size/1024/1024))
print('输出目录: %s' % OUTDIR)
