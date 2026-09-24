import json

with open('data/dashboard_data.json', 'rb') as f:
    b = f.read().decode('utf-8')

n = len(b)

def err(msg, pos):
    print('STRUCT ERROR:', msg, 'at', pos)
    print('context:', repr(b[max(0, pos - 80):pos + 80]))
    raise SystemExit

def ws(p):
    while p < n and b[p] in ' \t\r\n':
        p += 1
    return p

def parse_value(p, depth):
    p = ws(p)
    c = b[p]
    if c == '{':
        return parse_obj(p, depth)
    if c == '[':
        return parse_arr(p, depth)
    if c == '"':
        return parse_str(p)
    if c in '-0123456789':
        return parse_num(p)
    if b[p:p + 4] == 'true':
        return p + 4
    if b[p:p + 5] == 'false':
        return p + 5
    if b[p:p + 4] == 'null':
        return p + 4
    err('unexpected char in value', p)

def parse_str(p):
    p += 1
    while p < n:
        c = b[p]
        if c == '\\':
            nxt = b[p + 1] if p + 1 < n else ''
            if nxt in '"\\/bfnrt':
                p += 2
                continue
            if nxt == 'u':
                if p + 6 > n or not all(x in '0123456789abcdefABCDEF' for x in b[p + 2:p + 6]):
                    err('bad \\u escape', p)
                p += 6
                continue
            err('invalid escape seq', p)
        if c == '"':
            return p + 1
        if ord(c) < 0x20:
            err('unescaped control char in string', p)
        p += 1
    err('unterminated string', p)

def parse_num(p):
    start = p
    if b[p] == '-':
        p += 1
    while p < n and (b[p].isdigit() or b[p] in '+.eE'):
        p += 1
    return p

def parse_obj(p, depth):
    p += 1
    p = ws(p)
    if b[p] == '}':
        return p + 1
    while True:
        p = ws(p)
        if b[p] != '"':
            err('obj key not string', p)
        p = parse_str(p)
        p = ws(p)
        if b[p] != ':':
            err('obj missing colon', p)
        p = parse_value(p + 1, depth + 1)
        p = ws(p)
        if b[p] == ',':
            p += 1
            continue
        if b[p] == '}':
            return p + 1
        err('obj bad after value', p)

def parse_arr(p, depth):
    p += 1
    p = ws(p)
    if b[p] == ']':
        return p + 1
    while True:
        p = parse_value(p, depth + 1)
        p = ws(p)
        if b[p] == ',':
            p += 1
            continue
        if b[p] == ']':
            return p + 1
        err('arr bad after value', p)

try:
    end = parse_value(0, 0)
    print('parsed ok, end at', end, 'of', n)
except SystemExit:
    pass
