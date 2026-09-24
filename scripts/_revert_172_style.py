"""Revert #172 deep-blue tech style from template.html - CSS + HTML + JS"""
import re

with open('html/template.html', 'r', encoding='utf-8') as f:
    content = f.read()

original_len = len(content)
print(f'Original size: {original_len} chars')
changes = 0

# === STEP 1: Remove #v-overview KPI glow + dims-bar CSS block ===
old_block = """/* 深蓝科技风增强：KPI 发光 + 底部维度栏 */
#v-overview .kpigrid .kcard{border:1px solid rgba(56,149,255,.12);
  box-shadow:0 4px 20px rgba(0,0,0,.3),inset 0 1px 0 rgba(255,255,255,.04)}
#v-overview .kpigrid .kcard:hover{border-color:rgba(56,149,255,.45);
  box-shadow:0 8px 30px rgba(0,0,0,.4),0 0 20px rgba(56,149,255,.1),inset 0 1px 0 rgba(255,255,255,.06)}
#v-overview .kpigrid .kcard-user{border-left:3px solid #3895ff;
  background:linear-gradient(145deg,rgba(56,149,255,.08),rgba(56,149,255,.02))}
#v-overview .kpigrid .kcard-money{border-left:3px solid #f59e0b;
  background:linear-gradient(145deg,rgba(245,158,11,.08),rgba(245,158,11,.02))}
#v-overview .kpigrid .kcard-site{border-left:3px solid #22c997;
  background:linear-gradient(145deg,rgba(34,201,151,.08),rgba(34,201,151,.02))}
#v-overview .kpigrid .kcard-device{border-left:3px solid #a855f7;
  background:linear-gradient(145deg(rgba(168,92,247,.08),rgba(168,92,247,.02)))}
#v-overview .cockpit-section{position:relative;z-index:2}
#v-overview .cpanel{border-color:rgba(56,149,255,.1);
  background:linear-gradient(145deg,rgba(255,255,255,.03),rgba(255,255,255,.005))}
#v-overview .dash-panel{border-color:rgba(56,149,255,.1);
  background:linear-gradient(145deg,rgba(255,255,255,.04),rgba(255,255,255,.005))}

/* 底部维度快捷切换栏 */
.dims-bar{display:flex;align-items:center;gap:6px;margin-top:20px;padding:12px 16px;
  background:rgba(10,18,35,.8);border:1px solid rgba(56,149,255,.12);border-radius:12px;
  flex-wrap:wrap;position:relative;z-index:2}
.dims-bar::before{content:'\U0001f4ca 快捷维度';font-size:11.5px;color:#5a6b82;font-weight:700;margin-right:6px;letter-spacing:.5px}
.dim-chip{padding:5px 13px;border:1px solid rgba(255,255,255,.1);border-radius:16px;
  background:rgba(255,255,255,.04);color:#8899b8;cursor:pointer;font-size:11.5px;font-weight:600;
  transition:.2s;white-space:nowrap}
.dim-chip:hover{border-color:rgba(56,149,255,.4);color:#a8c4ee;background:rgba(56,149,255,.06)}
.dim-chip.active{background:linear-gradient(135deg,#3895ff,#2560d8);color:#fff;border-color:transparent;
  box-shadow:0 3px 10px rgba(56,149,255,.25)}"""

if old_block in content:
    content = content.replace(old_block, '')
    changes += 1
    print(f'STEP 1 OK: Removed KPI glow + dims-bar CSS')
else:
    print('STEP 1 FAIL: Block not found!')

# === STEP 2: Revert cockpit-section to clean style ===
old_cs = """.cockpit-section{margin-bottom:28px}
.cockpit-section .cs-head{display:flex;align-items:center;gap:10px;margin-bottom:16px;padding-bottom:10px;border-bottom:1px solid rgba(255,255,255,.08)}
.cockpit-section .cs-head .cs-icon{width:32px;height:32px;border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:16px}
.cockpit-section .cs-head .cs-title{font-size:16px;font-weight:800;color:#f0f4ff;letter-spacing:.5px}
.cockpit-section .cs-head .cs-sub{font-size:11.5px;color:#5a6b82;margin-left:auto}"""

new_cs = """/* 驾驶舱板块 */
.cockpit-section{margin-bottom:24px}
.cockpit-section .cs-head{display:flex;align-items:center;gap:8px;margin-bottom:12px}
.cockpit-section .cs-head .cs-icon{width:28px;height:28px;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:14px}
.cockpit-section .cs-head .cs-title{font-size:15px;font-weight:700;color:var(--text-primary)}
.cockpit-section .cs-head .cs-sub{font-size:11.5px;color:var(--muted);margin-left:auto}"""

if old_cs in content:
    content = content.replace(old_cs, new_cs)
    changes += 1
    print(f'STEP 2 OK: Reverted cockpit-section styles')
else:
    print('STEP 2 FAIL: cockpit-section not found!')

# === STEP 3: Revert kcard/kpigrid to clean light theme ===
old_kcard = """/* KPI 卡片网格 */
.kpigrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:12px}
.kcard{background:linear-gradient(145deg,rgba(255,255,255,.06),rgba(255,255,255,.02));border:1px solid rgba(255,255,255,.08);border-radius:12px;padding:16px 14px;position:relative;overflow:hidden;transition:.2s}
.kcard:hover{border-color:rgba(56,149,255,.3);transform:translateY(-2px);box-shadow:0 8px 25px rgba(0,0,0,.3)}
.kcard .kc-label{font-size:11.5px;color:#6b7a94;font-weight:600;text-transform:uppercase;letter-spacing:.5px;margin-bottom:8px}
.kcard .kc-value{font-size:26px;font-weight:800;color:#f0f4ff;line-height:1.1;text-shadow:0 0 20px rgba(56,149,255,.2)}
.kcard .kc-delta{display:flex;align-items:center;gap:6px;margin-top:8px;font-size:11.5px;font-weight:600}
.kcard .kc-delta.up{color:#22c997}
.kcard .kc-delta.down{color:#f0544f}
.kcard .kc-delta.neutral{color:#6b7a94}
.kcard .kc-delta .arrow{font-size:13px}
.kcard .kc-sub{font-size:11px;color:#4a5a70;margin-top:6px}
.kcard .kc-ring{position:absolute;top:12px;right:12px;width:44px;height:44px}
.kcard.kcard-user{border-left:3px solid #3895ff}
.kcard.kcard-site{border-left:3px solid #22c997}
.kcard.kcard-device{border-left:3px solid #a855f7}
.kcard.kcard-money{border-left:3px solid #f59e0b}
.kcard.kcard-todo{border-left:3px dashed #f59e0b;background:repeating-linear-gradient(-45deg,rgba(245,158,11,.03),rgba(245,158,11,.03) 4px,transparent 4px,8px)}
.kcard.kcard-todo .kc-value{color:#fbbf24;font-size:20px}
.kcard.kcard-todo .kc-label{color:#92400e}
.kcard.kcard-nav{cursor:pointer}
.kcard.kcard-nav:hover{border-color:rgba(56,149,255,.5);box-shadow:0 8px 30px rgba(56,149,255,.15)}"""

new_kcard = """/* KPI 卡片网格 */
.kpigrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:10px}
.kcard{background:#fff;border:1px solid var(--border);border-radius:10px;padding:14px 12px;position:relative;transition:.15s}
.kcard:hover{border-color:var(--primary);box-shadow:0 2px 12px rgba(0,0,0,.06)}
.kcard .kc-label{font-size:11.5px;color:var(--muted);font-weight:600;margin-bottom:6px}
.kcard .kc-value{font-size:24px;font-weight:800;color:var(--text-primary);line-height:1.1}
.kcard .kc-delta{display:flex;align-items:center;gap:4px;margin-top:6px;font-size:11.5px;font-weight:600}
.kcard .kc-delta.up{color:var(--green)}
.kcard .kc-delta.down{color:var(--red)}
.kcard .kc-delta.neutral{color:var(--muted)}
.kcard .kc-delta .arrow{font-size:12px}
.kcard .kc-sub{font-size:11px;color:var(--muted);margin-top:4px}
.kcard .kc-ring{position:absolute;top:10px;right:10px;width:40px;height:40px}
.kcard.kcard-user{border-left:3px solid var(--primary)}
.kcard.kcard-site{border-left:3px solid var(--green)}
.kcard.kcard-device{border-left:3px solid var(--purple)}
.kcard.kcard-money{border-left:3px solid var(--amber)}
.kcard.kcard-todo{border-left:3px dashed var(--amber);background:#fffbeb}
.kcard.kcard-todo .kc-value{color:var(--amber);font-size:18px}
.kcard.kcard-todo .kc-label{color:#92400e}
.kcard.kcard-nav{cursor:pointer}
.kcard.kcard-nav:hover{border-color:var(--primary);box-shadow:0 2px 8px rgba(0,0,0,.08)}"""

if old_kcard in content:
    content = content.replace(old_kcard, new_kcard)
    changes += 1
    print(f'STEP 3 OK: Reverted kcard/kpigrid to clean light theme')
else:
    print('STEP 3 FAIL: kcard block not found!')

# === STEP 4: Revert cpanel to clean style ===
old_cpanel = """/* 图表面板（深色内嵌） */
.cpanel{background:linear-gradient(145deg,rgba(255,255,255,.04),rgba(255,255,255,.01));border:1px solid rgba(255,255,255,.07);border-radius:12px;padding:16px;margin-top:12px}
.cpanel .cp-title{font-size:13px;font-weight:700;color:#b8c8e0;margin-bottom:12px;display:flex;align-items:center;gap:8px}
.cpanel .cp-title::before{content:'';width:3px;height:14px;background:linear-gradient(180deg,#3895ff,#a855f7);border-radius:2px}
.cpanel .chart{height:260px;background:transparent}
.cpanel .chart.sm{height:200px}"""

new_cpanel = """/* 图表面板 */
.cpanel{background:#fff;border:1px solid var(--border);border-radius:10px;padding:14px;margin-top:10px}
.cpanel .cp-title{font-size:13px;font-weight:700;color:var(--text-primary);margin-bottom:10px;display:flex;align-items:center;gap:6px}
.cpanel .cp-title::before{content:'';width:3px;height:14px;background:var(--primary);border-radius:2px}
.cpanel .chart{height:260px;background:transparent}
.cpanel .chart.sm{height:200px}"""

if old_cpanel in content:
    content = content.replace(old_cpanel, new_cpanel)
    changes += 1
    print(f'STEP 4 OK: Reverted cpanel to clean style')
else:
    print('STEP 4 FAIL: cpanel not found!')

# === STEP 5: Remove period-bar HTML (time dimension selector) ===
old_period_html = """      <!-- 时间维度切换 -->
      <div class="period-bar">
        <label>时间维度</label>
        <span class="period-btn active" data-period="total">全部</span>
        <span class="period-btn" data-period="today">今日</span>
        <span class="period-btn" data-period="week">本周</span>
        <span class="period-btn" data-period="month">本月</span>
        <span class="period-btn" data-period="year">本年</span>
        <span class="period-btn" data-period="custom">自定义</span>
      </div>"""

if old_period_html in content:
    content = content.replace(old_period_html, '')
    changes += 1
    print(f'STEP 5 OK: Removed period-bar HTML')
else:
    print('STEP 5 FAIL: period-bar HTML not found!')

# === STEP 6: Revert title ===
old_title = '<h2 class="title">\U0001f4ca 数据总览 · 运营驾驶舱</h2>'
new_title = '<h2 class="title">\U0001f4ca 数据总览</h2>'

if old_title in content:
    content = content.replace(old_title, new_title)
    changes += 1
    print(f'STEP 6 OK: Reverted title (removed "· 运营驾驶舱")')
else:
    print('STEP 6 FAIL: title not found!')

# === STEP 7: Remove dims-bar HTML ===
old_dims_html = """      <!-- 底部维度快捷切换栏 -->
      <div class="dims-bar" id="dims-bar">
        <span class="dim-chip active" data-nav="overview">\U0001f4ca 总览</span>
        <span class="dim-chip" data-nav="user">\U0001f464 用户</span>
        <span class="dim-chip" data-nav="site">\U0001f3ea 网点</span>
        <span class="dim-chip" data-nav="device">\U0001f527 设备</span>
        <span class="dim-chip" data-nav="sales">\U0001f4b0 销售</span>
        <span class="dim-chip" data-nav="coupon">\U0001f3ab 优惠券</span>
        <span class="dim-chip" data-nav="ops">\u2699\ufe0f 运维</span>
        <span class="dim-chip" data-nav="personnel">\U0001f465 人员</span>
        <span class="dim-chip" data-nav="finance">\U0001f4c8 财务</span>
      </div>"""

if old_dims_html in content:
    content = content.replace(old_dims_html, '')
    changes += 1
    print(f'STEP 7 OK: Removed dims-bar HTML')
else:
    print('STEP 7 FAIL: dims-bar HTML not found!')

# === STEP 8: Remove dims-bar JS event handler ===
old_js = """  // 底部维度栏点击
  document.querySelectorAll('#dims-bar .dim-chip').forEach(function(chip){
    chip.addEventListener('click',function(){
      document.querySelectorAll('#dims-bar .dim-chip').forEach(function(c){c.classList.remove('active');});
      this.classList.add('active');
      navigate(this.dataset.nav,{});
    });
  });

  // OVERVIEW ——"""

if old_js in content:
    content = content.replace(old_js, '\n  // OVERVIEW ——')
    changes += 1
    print(f'STEP 8 OK: Removed dims-bar JS event handler')
else:
    print('STEP 8 FAIL: dims-bar JS not found!')

with open('html/template.html', 'w', encoding='utf-8') as f:
    f.write(content)

print(f'\n{"="*50}')
print(f'Total changes applied: {changes}/8')
print(f'Final size: {len(content)} chars (removed {original_len - len(content)} chars)')
print(f'{"="*50}')
