#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""boot 引导专项回归 —— 补上 smoke_minimal/smoke_cabdev 的盲区。

背景（2026-08-08 线上事故）：
  原有 smoke 都是自己 `for(var k in d){DATA[k]=d[k]}` 回填 DATA 后再断言渲染，
  **完全绕过了 index.html 里真实的 boot 代码**。而真实 boot 只写了 `window.DATA=d`，
  顶层 `const DATA` 根本没被赋值 → 全看板空白且不报任何错，smoke 却全绿。

本脚本直接对**构建产物**做两层校验：
  A. 静态：boot 必须回填 DATA 对象本身、必须流式解析、不得用 TextDecoder 解大 JSON
  B. 行为：抽出真实的 start() 函数，在 node 里与 `const DATA = {}` 拼成同一作用域执行，
     断言裸标识符 DATA 确实被填充（浏览器多个 <script> 共享 global lexical environment，
     此模型与真实运行一致）

用法：python scripts/smoke_boot.py [index.html 路径]
"""
import os, re, sys, json, subprocess

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODE = r'C:\Users\Karry\.workbuddy\binaries\node\versions\22.22.2\node.exe'
TARGET = sys.argv[1] if len(sys.argv) > 1 else os.path.join(BASE, 'citybike_static', 'index.html')

fails, oks = [], []


def T(name, cond, extra=''):
    (oks if cond else fails).append(name)
    print(('  [OK]   ' if cond else '  [FAIL] ') + name + (('  ' + str(extra)) if extra else ''))


def brace_match(s, start):
    """从 s[start] 的 '{' 开始做括号平衡匹配，返回结束位置（含 '}'）。"""
    assert s[start] == '{'
    depth, i, n = 0, start, len(s)
    in_str, quote, esc = False, '', False
    while i < n:
        c = s[i]
        if in_str:
            if esc:
                esc = False
            elif c == '\\':
                esc = True
            elif c == quote:
                in_str = False
        else:
            if c in '"\'`':
                in_str, quote = True, c
            elif c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    return i
        i += 1
    raise ValueError('括号不平衡')


print('=' * 64)
print('boot 引导专项回归')
print('目标: %s' % TARGET)
print('=' * 64)

assert os.path.exists(TARGET), '产物不存在: %s' % TARGET
html = open(TARGET, encoding='utf-8').read()
print('文件大小: %.2f MB\n' % (len(html.encode('utf-8')) / 1048576))

# ── 定位 boot script（最后一个 <script>）────────────────────────────────
last_body = html.rfind('</body>')
T('存在 </body>', last_body > 0)
boot_start = html.rfind('<script>', 0, last_body)
T('定位到 boot script', boot_start > 0)
boot = html[boot_start:last_body]

# ── A. 静态校验 ────────────────────────────────────────────────────────
print('\n── A. 静态校验 ──')
T('主脚本含 const DATA = {}（STRIP 模式）', 'const DATA = {};' in html)
T('★ boot 回填 DATA 对象本身（DATA[k]=d[k]）', 'DATA[k]=d[k]' in boot,
  '← 只写 window.DATA=d 会导致全看板空白')
T('★ boot 未用 TextDecoder 解大 JSON', 'TextDecoder' not in boot,
  '← lite 解压后 96MB，TextDecoder 会 OOM')
T('★ boot 走流式 JSON 解析', 'Response(s).json()' in boot or 'Response(s).json' in boot)
T('boot 有 DecompressionStream 缺失显式报错', 'DecompressionStream' in boot and 'undefined' in boot)
T('boot 有进度提示', 'boot-pct' in html and 'bump(' in boot)
T('boot 有错误 UI + 重试按钮', 'location.reload()' in boot)
T('boot 有 stall 看门狗', 'lastProg' in boot)
T('boot 有未压缩 json 兜底', 'dashboard_data_lite.json"' in boot)

# ── B. 行为校验：真实 start() 在 const DATA 同作用域下执行 ───────────────
print('\n── B. 行为校验（node 执行真实 start 函数）──')
m = re.search(r'function start\(d\)\s*\{', boot)
T('抽取到 start(d) 函数', m is not None)
if not m:
    print('\n无法继续行为校验')
    sys.exit(1)
body_start = boot.index('{', m.start())
body_end = brace_match(boot, body_start)
start_fn = boot[m.start():body_end + 1]
print('  start() 长度: %d 字符' % len(start_fn))

# 构造与浏览器同构的执行环境：const DATA 与 start() 在同一全局词法作用域
probe = r'''
// ── 模拟主脚本（STRIP 模式）──
const DATA = {};
// ── 模拟 boot 所需的最小 DOM / 全局桩 ──
var __removed = false, __failMsg = null, __booted = false;
var el = { remove: function(){ __removed = true; }, innerHTML: '' };
function fail(t, e){ __failMsg = String(t) + (e ? (' | ' + (e.message||e)) : ''); }
function bootApp(){ __booted = true; }
globalThis.window = globalThis;

// ── 被测：从产物中原样抽出的 start() ──
__START_FN__

// ── 执行：喂入模拟的 lite 数据 ──
start({ overview: { total: 123 }, device: { cabinet_detail: [1,2,3] }, user: { n: 7 } });

console.log(JSON.stringify({
  dataKeys:      Object.keys(DATA),          // 裸标识符 DATA 是否被回填 ← 核心
  overviewTotal: (DATA.overview && DATA.overview.total) || null,
  windowIsData:  (typeof window !== 'undefined') && window.DATA === DATA,
  booted:        __booted,
  removed:       __removed,
  failMsg:       __failMsg
}));
'''.replace('__START_FN__', start_fn)

tmp = os.path.join(BASE, '_smoke_boot.js')
with open(tmp, 'w', encoding='utf-8') as f:
    f.write(probe)

try:
    r = subprocess.run([NODE, tmp], capture_output=True, text=True, encoding='utf-8', timeout=60)
    if r.returncode != 0:
        T('node 执行 start()', False, r.stderr.strip()[:400])
    else:
        out = json.loads(r.stdout.strip().splitlines()[-1])
        T('node 执行 start() 无异常', True)
        T('★ 裸标识符 DATA 被回填（不是空对象）', len(out['dataKeys']) == 3,
          'keys=%s' % out['dataKeys'])
        T('★ 深层数据可读 DATA.overview.total', out['overviewTotal'] == 123,
          '=%s' % out['overviewTotal'])
        T('window.DATA 与 DATA 指向同一对象', out['windowIsData'] is True)
        T('bootApp() 被调用', out['booted'] is True)
        T('boot 遮罩被移除', out['removed'] is True)
        T('未触发 fail()', out['failMsg'] is None, out['failMsg'] or '')
finally:
    try:
        os.remove(tmp)
    except OSError:
        pass

# ── 汇总 ───────────────────────────────────────────────────────────────
print('\n' + '=' * 64)
if fails:
    print('❌ %d 项失败 / 共 %d 项' % (len(fails), len(fails) + len(oks)))
    for f in fails:
        print('   - ' + f)
    sys.exit(1)
print('✅ NO RUNTIME ERRORS — boot 引导全部通过（%d 项）' % len(oks))
print('=' * 64)
