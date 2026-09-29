from client import request,base
import json,urllib.request
results=[]
def check(name,ok):
 results.append({'test':name,'pass':bool(ok)});print('PASS' if ok else 'FAIL',name)
 if not ok:raise AssertionError(name)
st,b=request('multi-property&command=outbox');first=b['data']
st,b=request('multi-property&command=outbox&offset=1');page=b['data']
check('Outbox pagination excludes earlier item',st==200 and page['offset']==1 and page['jobs'][0]['job_id']==first['jobs'][1]['job_id'])
st,b=request('multi-property&command=outbox&offset=1000');check('Outbox exhausted page returns empty without changing total',st==200 and b['data']['jobs']==[] and b['data']['total']==first['total'])
req=urllib.request.Request('http://127.0.0.1:38184/api.php',method='OPTIONS',headers={'Origin':'http://127.0.0.1:38184','Access-Control-Request-Method':'GET','Access-Control-Request-Headers':'X-Tamasya-Company-ID,X-Tamasya-Property-ID,If-None-Match'})
r=urllib.request.urlopen(req);headers=dict(r.headers)
check('CORS supports explicit company/property and conditional reads',all(x in headers.get('Access-Control-Allow-Headers','') for x in ['X-Tamasya-Company-ID','X-Tamasya-Property-ID','If-None-Match']) and 'ETag' in headers.get('Access-Control-Expose-Headers',''))
(base/'logs/hybrid-pagination-results.json').write_text(json.dumps(results,indent=2))
