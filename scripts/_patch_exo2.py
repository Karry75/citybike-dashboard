# -*- coding: utf-8 -*-
"""补丁2：修复单遍抽取时原始行含 Decimal/datetime 导致 json.dumps 失败。"""
P = r"D:/workboddy file/dudu分析/citybike_backup/scripts/extract_exo_package.py"
s = open(P, encoding="utf-8").read()

# 在 extract_window 内注入 _jval 转换助手
old1 = '    ci = {c: i for i, c in enumerate(SEL_COLS)}\n    raw_path = tmp_path + ".raw"'
new1 = ('    from decimal import Decimal as _Dec\n'
        '    def _jval(v):\n'
        '        if isinstance(v, _Dec):\n'
        '            return float(v)\n'
        '        if isinstance(v, (datetime.datetime, datetime.date)):\n'
        '            return v.isoformat()\n'
        '        if isinstance(v, bytes):\n'
        '            return v.decode("utf-8", "replace")\n'
        '        return v\n'
        '    ci = {c: i for i, c in enumerate(SEL_COLS)}\n'
        '    raw_path = tmp_path + ".raw"')
assert old1 in s, "old1 not found"
s = s.replace(old1, new1, 1)

# 原始行 dump 时套用 _jval
old2 = 'fo.write(json.dumps({c: r[ci[c]] for c in SEL_COLS}, ensure_ascii=False, separators=(",", ":")))'
new2 = 'fo.write(json.dumps({c: _jval(r[ci[c]]) for c in SEL_COLS}, ensure_ascii=False, separators=(",", ":")))'
assert old2 in s, "old2 not found"
s = s.replace(old2, new2, 1)

open(P, "w", encoding="utf-8").write(s)
print("PATCH2 OK")
