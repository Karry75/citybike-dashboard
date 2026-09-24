# -*- coding: utf-8 -*-
"""Assemble self-contained citybike dashboard HTML (inline data + inline ECharts)."""
import json, os

BASE = r"D:/workboddy file/dudu分析/citybike_backup"
tpl = open(os.path.join(BASE, "html/template.html"), encoding="utf-8").read()
data = json.load(open(os.path.join(BASE, "data/dashboard_data.json"), encoding="utf-8"))
echarts = open(os.path.join(BASE, "html/assets/echarts.min.js"), encoding="utf-8").read()
# 内嵌中国省级 GeoJSON（离线可用，避免沙箱 fetch CDN 失败）
_geo_path = os.path.join(BASE, "assets/geo/china_jsd.json")
_china_geo = "null"
if os.path.exists(_geo_path):
    _china_geo = open(_geo_path, encoding="utf-8").read().strip()

# embed data safely
data_json = json.dumps(data, ensure_ascii=False)
# 转义会破坏 JS 字符串字面量的字符（即便当前数据没有，未来也需防御）
data_json = data_json.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
# 防止 </script> 提前闭合（即使嵌在字符串里）
data_json = data_json.replace("</", "<\\/")

html = tpl.replace("{{ECHARTS}}", echarts).replace("{{DATA}}", data_json).replace("{{CHINA_GEO}}", _china_geo)

out_dir = os.path.join(BASE, "citybike_dashboard")
os.makedirs(out_dir, exist_ok=True)
out_path = os.path.join(out_dir, "index.html")
open(out_path, "w", encoding="utf-8").write(html)
print("WROTE", out_path, os.path.getsize(out_path), "bytes")
