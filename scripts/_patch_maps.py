import io
p = "scripts/extract_dashboard.py"
s = open(p, encoding="utf-8").read()
repls = [
    ('"discharge_temp, charging_temp, main_s, main_h, location_type, last_upload_time "',
     '"discharge_temp, charging_temp, main_s, main_h, last_upload_time "'),
    ('user_id uid', 'consume_user_id uid'),
    ("WHERE outflow=1 AND business_type_first='exchange_order'",
     "WHERE outflow_id IS NOT NULL AND business_type_first='exchange_order'"),
]
for a, b in repls:
    n = s.count(a)
    s = s.replace(a, b)
    print("replaced %r -> %d times" % (a, n))
open(p, "w", encoding="utf-8").write(s)
print("patched", p)
