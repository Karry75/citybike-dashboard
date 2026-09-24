# -*- coding: utf-8 -*-
f = 'html/template.html'
lines = open(f, encoding='utf-8').read().split('\n')
anchor = None
for i, l in enumerate(lines):
    if 'id="w-anom-note"' in l:
        anchor = i
        break
assert anchor is not None, 'anchor not found'
# anchor = note line; anchor+1 = anomaly panel close; anchor+2 = blank; anchor+3 = v-site close
panel = [
'',
'      <!-- 网点价值评估（模型驱动） -->',
'      <div class="w-sub-panel" id="w-sub-value">',
'        <div class="panel">',
'          <h3>🏆 网点价值评估阈值（已批准）</h3>',
'          <div class="foot">四维加权评分（满分100）：换电效益40 + 用户粘性25 + 设备健康20 + 成长性15。等级：≥75 S / ≥50 A / ≥25 B / 其余 C。淘汰标准：C级 + 已开业 + 30天换电&lt;10。单点月运维成本 ¥2000 为估算假设（依据 DD-YW-230208）。</div>',
'          <div class="tbl-wrap"><table id="bv-thr"><thead></thead><tbody></tbody></table></div>',
'        </div>',
'        <div class="panel">',
'          <h3>📘 模型说明</h3>',
'          <div id="bv-model"></div>',
'        </div>',
'        <div class="kpis" id="bv-kpis"></div>',
'        <div class="grid2">',
'          <div class="panel"><h3>价值等级分布</h3><div id="bv-tier" class="chart sm"></div></div>',
'          <div class="panel"><h3>城市淘汰候选排行 Top12</h3><div id="bv-elim" class="chart"></div></div>',
'        </div>',
'        <div class="panel"><h3>各城市网点价值汇总</h3><div class="tbl-wrap"><table id="bv-city-tbl"><thead></thead><tbody></tbody></table></div></div>',
'        <div class="panel">',
'          <div class="phead"><h3>低价值待淘汰网点明细（共 <span id="bv-elim-n"></span> 个：C级+已开业+30天换电&lt;10）</h3><button type="button" class="btn sm" id="btn-export-bv">导出</button></div>',
'          <div class="tbl-wrap"><table id="bv-list"><thead></thead><tbody></tbody></table></div>',
'        </div>',
'        <div class="panel"><h3>明星网点 Top30（保留扩张）</h3><div class="tbl-wrap"><table id="bv-top"><thead></thead><tbody></tbody></table></div></div>',
'        <div class="note" id="bv-note"></div>',
'      </div>',
'',
]
# replace the blank line (anchor+2) with panel block; v-site close (anchor+3) remains after
lines[anchor+2:anchor+3] = panel
open(f, 'w', encoding='utf-8').write('\n'.join(lines))
print('INSERTED site value panel after line', anchor+1, '; new total lines', len(lines))
