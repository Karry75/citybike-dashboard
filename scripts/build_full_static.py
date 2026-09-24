#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""电脑全量版（壳 + 全量 gz 异步加载）。

替代「618MB 单文件内联」的旧做法：
  - index.html 仅约 1.8MB（模板 + ECharts + 掏空的 DATA），首屏秒开
  - 全量数据流式 gzip 成 dashboard_data.json.gz（体积仅原始的 ~10%）
  - boot 脚本用 DecompressionStream 流式解压，再用 Response(...).json() 解析
    —— 关键：**不**经过 TextDecoder 生成超大 JS 字符串（751MB 会撞 V8 字符串上限），
       Response.json() 内部流式解析，内存友好得多。
  - 若静态服务器自作主张已解压（无 gzip 魔数），自动回退为直接解析。

产物目录：citybike_full_static/
  index.html
  dashboard_data.json.gz
"""
import os, gzip, time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TPL = os.path.join(BASE, 'html', 'template.html')
ECHARTS = os.path.join(BASE, 'html', 'assets', 'echarts.min.js')
GEO = os.path.join(BASE, 'assets', 'geo', 'china_jsd.json')
FULL = os.path.join(BASE, 'data', 'dashboard_data.json')
OUTDIR = os.path.join(BASE, 'citybike_full_static')

assert os.path.exists(TPL), 'html/template.html 不存在'
assert os.path.exists(FULL), 'data/dashboard_data.json 不存在'

os.makedirs(OUTDIR, exist_ok=True)

# ── 1) 生成壳 ────────────────────────────────────────────────
tpl = open(TPL, encoding='utf-8').read()
echarts = open(ECHARTS, encoding='utf-8').read()
china_geo = 'null'
if os.path.exists(GEO):
    china_geo = open(GEO, encoding='utf-8').read().strip()

html = (tpl.replace('{{ECHARTS}}', echarts)
           .replace('{{DATA}}', '{}')
           .replace('{{CHINA_GEO}}', china_geo))
assert 'const DATA = {};' in html, '占位符替换后未得到 const DATA = {};'

boot = (
    '<div id="boot-loading" style="position:fixed;inset:0;z-index:99999;'
    'display:flex;flex-direction:column;align-items:center;justify-content:center;gap:16px;'
    'background:#0d1b2e;color:#a8c4ee;font-family:-apple-system,\'PingFang SC\',\'Microsoft YaHei\',sans-serif;font-size:15px">'
    '<div style="width:44px;height:44px;border:4px solid #1a3a5c;border-top-color:#3895ff;'
    'border-radius:50%;animation:bootspin 1s linear infinite"></div>'
    '<div id="boot-msg">正在加载<b>全量</b>数据…（首次约需十几秒，请用桌面浏览器）</div>'
    '<div id="boot-pct" style="font-size:13px;color:#6f8fc0"></div></div>'
    '<style>@keyframes bootspin{to{transform:rotate(360deg)}}</style>'
    '<script>window.__BACKEND=true;'
    '(function(){'
    'var el=document.getElementById("boot-loading");'
    'var pct=document.getElementById("boot-pct");'
    'var QS=location.search||"";'
    'var LITE_MODE=QS.indexOf("lite=1")>=0;'
    'var DATA_URL=LITE_MODE?"./dashboard_data_lite.json":"./dashboard_data.json.gz";'
    'if(LITE_MODE){var bm=document.getElementById("boot-msg");if(bm)bm.innerHTML="正在加载<b>轻量</b>数据…（?lite=1）";}'
    'function fail(t,e){'
        'if(!el)return;'
        'var d=e?(e.message||String(e)).slice(0,200):"";'
        'var lite="https://9ef21e3c09704152b131d3b411f909f4.bj10.agentos-app.net";'
        'el.innerHTML=`<div style="padding:30px;max-width:540px;text-align:center;color:#a8c4ee;font-size:14px;line-height:1.8">'
            '<div style="color:#ff8b8b;font-size:20px;margin-bottom:14px">⚠️ ${t}</div>'
            '<div style="color:#8fa5c4;font-size:12px;margin-bottom:18px;font-family:monospace;word-break:break-all">${d}</div>'
            '<div style="margin-bottom:20px">建议：<br>① 关闭其他占内存的标签页后刷新<br>② 使用 Chrome / Edge 最新版桌面浏览器<br>③ 数据过大时可改用 <a href="${lite}" target="_blank" style="color:#3895ff">手机轻量版</a>（每表500行，秒开）</div>'
            '<button onclick="location.reload()" style="padding:10px 28px;background:#3895ff;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:15px">🔄 重试</button>'
            '</div>`;'
        'if(e)console.error(e);'
    '}'
    'function start(d){try{for(var k in d){if(Object.prototype.hasOwnProperty.call(d,k)){DATA[k]=d[k];}}window.DATA=DATA;if(el)el.remove();if(typeof bootApp==="function"){bootApp();}else{fail("渲染函数缺失",null);}}catch(e){fail("渲染异常",e);}}'
    'var lastProg=Date.now();'
    'function bump(t){lastProg=Date.now();if(pct)pct.textContent=t;}'
    'setTimeout(function(){if(el&&Date.now()-lastProg>75000){if(pct)pct.textContent="加载较慢，请耐心等待或刷新重试";}},80000);'
    'function loadOnce(){return fetch(DATA_URL,{cache:"no-store"}).then(function(r){'
        'if(!r.ok)throw new Error("HTTP "+r.status);'
        'var total=parseInt(r.headers.get("content-length")||"0",10);'
        'bump("下载中…");'
        'if(!r.body||typeof ReadableStream==="undefined")return r.arrayBuffer();'
        'var rd=r.body.getReader(),got=0,chunks=[];'
        'return (function pump(){return rd.read().then(function(res){'
            'if(res.done){var n=got,out=new Uint8Array(n),off=0;for(var i=0;i<chunks.length;i++){out.set(chunks[i],off);off+=chunks[i].length;}bump("下载完成 "+(n/1048576).toFixed(1)+" MB，准备解压…");return out.buffer;}'
            'chunks.push(res.value);got+=res.value.length;'
            'bump("下载中 "+(got/1048576).toFixed(1)+(total?" / "+(total/1048576).toFixed(1):"")+" MB");'
            'return pump();'
        '});})();'
    '}).then(function(ab){'
        'var u8=new Uint8Array(ab);'
        'var isGz=u8.length>2&&u8[0]===31&&u8[1]===139;'
        'if(!isGz){bump("解析 JSON…（数据量大，请稍候）");return new Response(ab).json();}'
        'if(typeof DecompressionStream==="undefined"){throw new Error("浏览器不支持 DecompressionStream，请用 Chrome / Edge 最新版");}'
        'var db=0;'
        'var tk=new TransformStream({transform:function(c,ct){db+=c.length;if(db%(8*1048576)<c.length){bump("解压中 "+(db/1048576).toFixed(1)+" MB");}ct.enqueue(c);}});'
        'bump("开始解压 "+(ab.byteLength/1048576).toFixed(1)+" MB…");'
        'var s=new Response(ab).body.pipeThrough(new DecompressionStream("gzip")).pipeThrough(tk);'
        'bump("解压+解析中…（约 30-60 秒）");'
        'return new Response(s).json();'
    '});}'
    'var MAX_RETRY=3;'
    '(function attempt(n){'
        'bump("正在加载数据（第 "+n+" 次尝试）…");'
        'loadOnce().then(start).catch(function(e){'
            'if(n<MAX_RETRY){'
                'var w=n*1500;'
                'bump("连接中断，"+(w/1000)+" 秒后自动重试（"+(n+1)+"/"+MAX_RETRY+"）");'
                'setTimeout(function(){attempt(n+1);},w);'
            '}else{if(!LITE_MODE){var sep=location.search?\'&\':\'?\';location.href=location.pathname+location.search+sep+\'lite=1\';}else{fail("数据加载失败（已重试 "+MAX_RETRY+" 次）",e);}}'
        '});'
    '})(1);'
    '})();</script>\n</body>'
)
last_body = html.rfind('</body>')
assert last_body >= 0, '找不到 </body>'
html = html[:last_body] + boot + html[last_body + len('</body>'):]

opens, closes = html.count('<script'), html.count('</script>')
assert opens == closes, '脚本标签失衡: %d/%d' % (opens, closes)
assert html.rstrip().endswith('</html>'), '未以 </html> 结尾'

with open(os.path.join(OUTDIR, 'index.html'), 'w', encoding='utf-8') as f:
    f.write(html)
print('壳已生成: %.2f MB, script %d/%d' % (len(html.encode('utf-8')) / 1024 / 1024, opens, closes))

# ── 2) 流式 gzip 全量数据 ────────────────────────────────────
src_size = os.path.getsize(FULL)
gz_path = os.path.join(OUTDIR, 'dashboard_data.json.gz')
print('开始压缩全量数据: %.1f MB -> %s' % (src_size / 1024 / 1024, gz_path))
t0 = time.time()
CHUNK = 1 << 23  # 8MB
done = 0
with open(FULL, 'rb') as f_in, open(gz_path, 'wb') as raw_out:
    with gzip.GzipFile(fileobj=raw_out, mode='wb', compresslevel=6) as gz:
        while True:
            buf = f_in.read(CHUNK)
            if not buf:
                break
            gz.write(buf)
            done += len(buf)
            if done % (CHUNK * 16) == 0:
                print('  ...%.0f%% (%.0f MB)' % (done * 100.0 / src_size, done / 1024 / 1024), flush=True)
gz_size = os.path.getsize(gz_path)
print('压缩完成: %.1f MB -> %.1f MB (%.1f%%), 用时 %.0fs'
      % (src_size / 1024 / 1024, gz_size / 1024 / 1024, gz_size * 100.0 / src_size, time.time() - t0))
print('输出目录: %s' % OUTDIR)

# ── 3) 复制 lite 数据，供 ?lite=1 秒开兜底 ──────────────────
LITE_SRC = os.path.join(BASE, 'data', 'dashboard_data_lite.json')
if os.path.exists(LITE_SRC):
    import shutil
    shutil.copy(LITE_SRC, os.path.join(OUTDIR, 'dashboard_data_lite.json'))
    print('lite 兜底数据已复制: %s' % os.path.getsize(os.path.join(OUTDIR, 'dashboard_data_lite.json')))
