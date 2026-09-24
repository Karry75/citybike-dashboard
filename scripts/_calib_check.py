s = open('html/template.html', encoding='utf-8').read()

def grab(name, closer):
    i = s.index(name)
    j = s.index(closer, i)
    return s[i + len(name): j + len(closer)]

def norm(body):
    body = body.strip()
    if body.endswith('};'):
        body = body[:-2]
    elif body.endswith(']'):
        pass
    elif body.endswith('}'):
        body = body[:-1]
    return body

C = norm(grab('const CALIBER = ', '\n};'))
K = norm(grab('const KPI_CALIBER = ', '\n};'))
A = norm(grab('const CHART_IDS = ', '];'))

js = ('const CALIBER = ' + C + ';\n'
      'const KPI_CALIBER = ' + K + ';\n'
      'const CHART_IDS = ' + A + ';\n')
validate = (
    'let p=[];'
    'Object.keys(KPI_CALIBER).forEach(m=>KPI_CALIBER[m].forEach(k=>{'
    'if(k&&!CALIBER[k])p.push("KPI "+m+" missing "+k);}));'
    'CHART_IDS.forEach(id=>{if(!CALIBER[id])p.push("CHART missing "+id);});'
    'console.log("CALIBER:",Object.keys(CALIBER).length,'
    '" KPI_cards:",Object.values(KPI_CALIBER).reduce((a,b)=>a+b.length,0),'
    '" CHARTS:",CHART_IDS.length);'
    'console.log("PROBLEMS:",p.length?JSON.stringify(p):"NONE");'
)
open('_calib_check.js', 'w', encoding='utf-8').write(js + validate)
print('ok')
