#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""构建单文件自包含看板（手机/弱网友好版）。

改进点（对比旧版「裸 JSON 内联」）：
  旧版把 7.5MB 格式化 JSON 直接 inline 进 HTML → 单文件 9.4MB，
  弱网/手机 WebView 拉不动 → 白屏“打不开”。
  本版改为：gzip 压缩数据(→~600KB) + base64 内联(→~800KB)，
  运行时用浏览器原生 DecompressionStream 解压回填 const DATA，
  单文件体积降到 ~2.7MB，且数据/视图零丢失。

引导流程：
  const DATA = {};          （保留顶层占位符，全局 lexical 绑定）
  → 引导脚本异步解压 → for(k in d) DATA[k]=d[k]; window.DATA=DATA;
  → 移除 loading 遮罩 → bootApp()
"""
import os, sys, gzip, base64, json

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC = os.path.join(BASE, 'citybike_static', 'index.html')
LITE = os.path.join(BASE, 'data', 'dashboard_data_lite.json')
OUTDIR = os.path.join(BASE, 'citybike_selfcontained')
OUT = os.path.join(OUTDIR, 'index.html')

html = open(STATIC, encoding='utf-8').read()
raw = open(LITE, encoding='utf-8').read()

# 0.5) 在 app 脚本执行前就置位 __BACKEND=true，
# 使 app 尾部的 IIFE 走“等待引导”分支（if(__BACKEND && dataEmpty)），
# 避免其在 DATA 尚未解压时空跑 bootApp()（否则白屏/弹红条）。
# 必须在 <head> 之后、app 脚本之前注入。
assert '</head>' in html, '未找到 </head> 锚点'
html = html.replace('</head>', '</head><script>window.__BACKEND=true;</script>', 1)

# 0) 安全校验
assert 'const DATA = {};' in html, '未找到 STRIP 占位符 const DATA = {};'
assert '</script>' not in raw, 'lite 数据含 </script>，需先做转义处理！'

# 1) 压缩 + base64（紧凑 JSON 先去掉空白，进一步减小体积）
compact = json.dumps(json.loads(raw), ensure_ascii=False, separators=(',', ':'))
gz = gzip.compress(compact.encode('utf-8'), 9)
b64 = base64.b64encode(gz).decode('ascii')
assert '</script>' not in b64, 'base64 数据意外含 </script>'

# 2) 用异步解压引导替换 build_static 注入的 fetch 引导块
marker = '<div id="boot-loading'
idx = html.rfind(marker)
assert idx != -1, '未找到 boot-loading 注入块'
end = html.rfind('</body>')
assert end > idx, '结构异常：</body> 在 boot 块之前'

new_boot = (
    '<div id="boot-loading" style="position:fixed;inset:0;z-index:99999;'
    'display:flex;flex-direction:column;align-items:center;justify-content:center;'
    'background:#0d1b2e;color:#a8c4ee;gap:14px;'
    'font-family:-apple-system,\'PingFang SC\',\'Microsoft YaHei\',sans-serif;font-size:15px">'
    '<div style="width:34px;height:34px;border:3px solid #2a3f63;border-top-color:#4f9eff;'
    'border-radius:50%;animation:cbspin .8s linear infinite"></div>'
    '<div id="boot-msg">数据解压中…</div></div>'
    '<style>@keyframes cbspin{to{transform:rotate(360deg)}}</style>'
    '<script>window.__BACKEND=true;'
    '(function(){'
    'var B64="' + b64 + '";'
    'var el=document.getElementById("boot-loading");'
    'var msg=document.getElementById("boot-msg");'
    'function fail(m){if(el){el.style.color="#ff6b6b";el.innerHTML="<div style=\'max-width:80%;text-align:center;line-height:1.6\'>"+m+"</div>";}'
    '  else if(msg){msg.textContent=m;}}'
    'async function run(){'
    ' try{'
    '  if(typeof DecompressionStream==="undefined"){throw new Error("当前浏览器不支持解压，请用 Chrome/Edge/Safari 新版打开");}'
    '  if(typeof atob==="undefined"){throw new Error("当前浏览器缺少 atob，无法解码数据");}'
    '  if(msg)msg.textContent="数据解压中…";'
    '  var bin=atob(B64);'
    '  var bytes=new Uint8Array(bin.length);'
    '  for(var i=0;i<bin.length;i++)bytes[i]=bin.charCodeAt(i);'
    '  var ds=new DecompressionStream("gzip");'
    '  var st=new Blob([bytes]).stream().pipeThrough(ds);'
    '  var txt=await new Response(st).text();'
    '  var d=JSON.parse(txt);'
    '  for(var k in d){DATA[k]=d[k];}'
    '  window.DATA=DATA;'
    '  if(el)el.remove();'
    '  if(typeof bootApp==="function"){bootApp();}'
    '  else{fail("渲染函数缺失，请刷新页面重试");}'
    ' }catch(e){console.error(e);fail("加载失败："+(e&&e.message?e.message:e)+"<br><br>可尝试：①桌面 Chrome 打开 ②本地起服务绕开公网");}'
    '}'
    'run();'
    '})();</script>'
)
html = html[:idx] + new_boot + html[end:]

# 3) 校验结构
opens = html.count('<script'); closes = html.count('</script>')
assert opens == closes, '脚本标签失衡: %d/%d' % (opens, closes)
assert html.rstrip().endswith('</html>'), '未以 </html> 结尾'
assert 'window.__BACKEND=true' in html
assert 'dashboard_data_lite.json' not in html, '仍存在外部数据 fetch 引用！'

os.makedirs(OUTDIR, exist_ok=True)
with open(OUT, 'w', encoding='utf-8') as f:
    f.write(html)

print('构建完成:')
print('  输出: %s' % OUT)
print('  体积: %d 字节 (%.2f MB)' % (len(html.encode('utf-8')), len(html.encode('utf-8'))/1024/1024))
print('  脚本标签平衡: %s/%s' % (opens, closes))
print('  数据已 gzip+base64 内联: %s (原 lite 数据 %.2f MB → base64 %.0f KB)'
      % (True, len(compact.encode('utf-8'))/1024/1024, len(b64)/1024))
print('  无外部数据引用: %s' % ('dashboard_data_lite.json' not in html))
