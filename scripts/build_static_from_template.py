#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""快速通道：直接从 html/template.html 构建静态壳（DATA 掏空版）。

与 build_static.py 产物等价，但**不读 citybike_dashboard/index.html**（那是 600MB+ 全量版，
正则掏空极慢且吃内存）。适用于「只改了前端模板、要快速重出轻量版/公网版」的场景。

产物：
  citybike_static/index.html                 掏空 DATA + boot fetch 引导（与 build_static 一致）
  citybike_static/dashboard_data_lite.json   兜底数据
  citybike_static/dashboard_data_lite.json.gz 主数据（gzip -9）

后续接 build_selfcontained.py 即可产出公网单文件轻量版。
⚠️ 若数据(dashboard_data.json)有变更，桌面全量版仍需跑 build_html.py。
"""
import os, gzip, shutil

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TPL = os.path.join(BASE, 'html', 'template.html')
ECHARTS = os.path.join(BASE, 'html', 'assets', 'echarts.min.js')
GEO = os.path.join(BASE, 'assets', 'geo', 'china_jsd.json')
LITE = os.path.join(BASE, 'data', 'dashboard_data_lite.json')
OUTDIR = os.path.join(BASE, 'citybike_static')

assert os.path.exists(TPL), 'html/template.html 不存在'
assert os.path.exists(LITE), 'data/dashboard_data_lite.json 不存在，请先 build_lite_data.py'

tpl = open(TPL, encoding='utf-8').read()
echarts = open(ECHARTS, encoding='utf-8').read()
china_geo = 'null'
if os.path.exists(GEO):
    china_geo = open(GEO, encoding='utf-8').read().strip()

# 1) 填充占位符：DATA 留空壳
html = (tpl.replace('{{ECHARTS}}', echarts)
           .replace('{{DATA}}', '{}')
           .replace('{{CHINA_GEO}}', china_geo))
assert 'const DATA = {};' in html, '占位符替换后未得到 const DATA = {};'

# 1.5) ⚠️ 必须在所有 app 脚本执行前就置位 __BACKEND=true，
# 否则 app 尾部 IIFE `if(window.__BACKEND && dataEmpty)` 会误判为「非 STRIP 模式」，
# 在 DATA 还是空壳 {} 时立即 bootApp()，触发 drawUser 等函数里 `rows.length`
# 对 undefined 抛 TypeError，并中断后续菜单事件绑定 → 看板空白且点击无反应。
# （参考 build_selfcontained.py：__BACKEND 注入在 </head> 之后）
assert '</head>' in html, '模板缺少 </head>'
html = html.replace('</head>', '</head>\n<script>window.__BACKEND=true;</script>', 1)

# 2) 注入 boot 引导
# ⚠️⚠️ 两条铁律（2026-08-08 线上事故根因，改动前必读）：
#   ① 顶层 `const DATA = {}` **不会**挂到 window 上。只写 window.DATA=d 会导致
#      所有渲染函数读到的裸标识符 DATA 永远是空对象 → 全看板空白且**不报任何错**。
#      必须逐 key 回填 DATA 对象本身：for(var k in d){DATA[k]=d[k];}
#   ② lite 解压后 ~96MB，**禁用 TextDecoder+JSON.parse**（会产生 96M 字符的中间字符串，
#      手机端必 OOM）。必须走 new Response(stream).json() 流式解析。
boot = (
    '<div id="boot-loading" style="position:fixed;inset:0;z-index:99999;'
    'display:flex;flex-direction:column;align-items:center;justify-content:center;gap:16px;'
    'background:#0d1b2e;color:#a8c4ee;font-family:-apple-system,\'PingFang SC\',\'Microsoft YaHei\',sans-serif;font-size:15px">'
    '<div style="width:44px;height:44px;border:4px solid #1a3a5c;border-top-color:#3895ff;'
    'border-radius:50%;animation:bootspin 1s linear infinite"></div>'
    '<div>正在加载看板数据…</div>'
    '<div id="boot-pct" style="color:#6d86a8;font-size:12px">准备中…</div></div>'
    '<style>@keyframes bootspin{to{transform:rotate(360deg)}}</style>'
    '<script>'
    '(function(){'
    'var el=document.getElementById("boot-loading");'
    'var pct=document.getElementById("boot-pct");'
    'var lastProg=Date.now();'
    'function bump(t){lastProg=Date.now();if(pct)pct.textContent=t;}'
    'setTimeout(function(){if(el&&Date.now()-lastProg>45000){if(pct)pct.textContent="\\u52a0\\u8f7d\\u8f83\\u6162\\uff0c\\u8bf7\\u8010\\u5fc3\\u7b49\\u5f85\\u6216\\u5237\\u65b0\\u91cd\\u8bd5";}},50000);'
    'function fail(t,e){'
        'if(!el)return;'
        'var d=e?(e.message||String(e)).slice(0,200):"";'
        'el.innerHTML=`<div style="padding:30px;max-width:520px;text-align:center;color:#a8c4ee;font-size:14px;line-height:1.8">'
            '<div style="color:#ff8b8b;font-size:20px;margin-bottom:14px">\\u26a0\\ufe0f ${t}</div>'
            '<div style="color:#8fa5c4;font-size:12px;margin-bottom:18px;font-family:monospace;word-break:break-all">${d}</div>'
            '<div style="margin-bottom:20px">\\u5efa\\u8bae\\uff1a<br>\\u2460 \\u68c0\\u67e5\\u7f51\\u7edc\\u540e\\u5237\\u65b0<br>'
            '\\u2461 \\u4f7f\\u7528 Chrome / Edge / Safari \\u6700\\u65b0\\u7248<br>\\u2462 \\u5173\\u95ed\\u5176\\u4ed6\\u5360\\u5185\\u5b58\\u7684\\u6807\\u7b7e\\u9875</div>'
            '<button onclick="location.reload()" style="padding:10px 28px;background:#3895ff;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:15px">\\ud83d\\udd04 \\u91cd\\u8bd5</button>'
            '</div>`;'
        'if(e)console.error(e);'
    '}'
    # ★ 核心修复：回填 const DATA 对象本身，而非只设 window.DATA
    'function start(d){try{'
        'if(!d||typeof d!=="object")throw new Error("\\u6570\\u636e\\u4e3a\\u7a7a");'
        'for(var k in d){if(Object.prototype.hasOwnProperty.call(d,k)){DATA[k]=d[k];}}'
        'window.DATA=DATA;'
        'if(!Object.keys(DATA).length)throw new Error("DATA \\u56de\\u586b\\u540e\\u4ecd\\u4e3a\\u7a7a");'
        'if(el)el.remove();'
        'if(typeof bootApp==="function"){bootApp();}else{fail("\\u6e32\\u67d3\\u51fd\\u6570\\u7f3a\\u5931",null);}'
    '}catch(e){fail("\\u6e32\\u67d3\\u5f02\\u5e38",e);}}'
    # ★ 核心修复：流式解压 + 流式 JSON 解析，不产生 96MB 中间字符串
    'function loadGz(){return fetch("./dashboard_data_lite.json.gz",{cache:"no-store"}).then(function(r){'
        'if(!r.ok)throw new Error("gz HTTP "+r.status);'
        'if(typeof DecompressionStream==="undefined")throw new Error("\\u6d4f\\u89c8\\u5668\\u4e0d\\u652f\\u6301 DecompressionStream\\uff0c\\u8bf7\\u5347\\u7ea7\\u81f3 Chrome/Edge 80+ \\u6216 Safari 16.4+");'
        'if(!r.body)throw new Error("\\u65e0 ReadableStream");'
        'bump("\\u4e0b\\u8f7d\\u4e2d\\u2026");'
        'var got=0;'
        'var tin=new TransformStream({transform:function(c,ct){got+=c.length;bump("\\u4e0b\\u8f7d\\u4e2d "+(got/1048576).toFixed(1)+" MB");ct.enqueue(c);}});'
        'var db=0;'
        'var tout=new TransformStream({transform:function(c,ct){db+=c.length;if(db%(8*1048576)<c.length){bump("\\u89e3\\u538b\\u4e2d "+(db/1048576).toFixed(0)+" MB");}ct.enqueue(c);}});'
        'var s=r.body.pipeThrough(tin).pipeThrough(new DecompressionStream("gzip")).pipeThrough(tout);'
        'return new Response(s).json();'
    '});}'
    'bump("\\u6b63\\u5728\\u8fde\\u63a5\\u2026");'
    'loadGz().then(start).catch(function(e){'
        'console.warn("gz failed, fallback json",e);'
        'bump("\\u56de\\u9000\\u672a\\u538b\\u7f29\\u6570\\u636e\\u2026");'
        'fetch("./dashboard_data_lite.json",{cache:"no-store"}).then(function(r){'
            'if(!r.ok)throw new Error("json HTTP "+r.status);return r.json();'
        '}).then(start).catch(function(e2){fail("\\u6570\\u636e\\u52a0\\u8f7d\\u5931\\u8d25",e2);});'
    '});'
    '})();</script>\n</body>'
)
# ⚠️ 必须替换「最后一个」</body>（ECharts 库内部含 </body> 字面量）
last_body = html.rfind('</body>')
assert last_body >= 0, '找不到 </body>'
html = html[:last_body] + boot + html[last_body + len('</body>'):]

# 3) 结构校验
opens, closes = html.count('<script'), html.count('</script>')
assert opens == closes, '脚本标签失衡: %d/%d' % (opens, closes)
assert html.rstrip().endswith('</html>'), '未以 </html> 结尾'

os.makedirs(OUTDIR, exist_ok=True)
with open(os.path.join(OUTDIR, 'index.html'), 'w', encoding='utf-8') as f:
    f.write(html)
shutil.copy(LITE, os.path.join(OUTDIR, 'dashboard_data_lite.json'))

gz_path = os.path.join(OUTDIR, 'dashboard_data_lite.json.gz')
with open(LITE, 'rb') as f_in, open(gz_path, 'wb') as f_out:
    f_out.write(gzip.compress(f_in.read(), compresslevel=9))

print('构建完成（快速通道 template -> static）:')
print('  index.html          : %d 字节 (%.2f MB)' % (len(html.encode('utf-8')), len(html.encode('utf-8')) / 1024 / 1024))
print('  DATA 已掏空         : %s' % ('const DATA = {};' in html))
print('  boot fetch gz       : %s' % ('./dashboard_data_lite.json.gz' in html))
print('  脚本标签平衡        : %d/%d' % (opens, closes))
print('  lite json (兜底)    : %.2f MB' % (os.path.getsize(os.path.join(OUTDIR, 'dashboard_data_lite.json')) / 1024 / 1024))
print('  lite json.gz (主)   : %.2f MB' % (os.path.getsize(gz_path) / 1024 / 1024))
print('输出目录: %s' % OUTDIR)
