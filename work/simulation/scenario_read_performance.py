"""Measure authenticated local reads and conditional reads; no SLA claim."""
from pathlib import Path
import json, platform, statistics, time, urllib.request, urllib.error

base=Path(__file__).resolve().parent
token=json.loads((base/'session.json').read_text())['token']
headers={'Authorization':'Bearer '+token,'Origin':'http://127.0.0.1:38184',
         'X-Device-ID':'simulation-browser-01'}
rows=[]
for action in ['server-revision','hotel-data']:
    elapsed=[];statuses=[];sizes=[];etag=None
    for index in range(12):
        request=urllib.request.Request('http://127.0.0.1:38184/api.php?action='+action,headers=headers)
        begin=time.perf_counter()
        with urllib.request.urlopen(request,timeout=90) as response:
            raw=response.read();statuses.append(response.status);etag=response.headers.get('ETag');sizes.append(len(raw))
        elapsed.append((time.perf_counter()-begin)*1000)
        assert json.loads(raw).get('success') is not False
    row={'action':action,'requests':12,'concurrency':1,'statuses':sorted(set(statuses)),
         'p50Ms':round(statistics.median(elapsed),2),'p95Ms':round(sorted(elapsed)[-1],2),
         'maxResponseBytes':max(sizes),'etagPresent':bool(etag)}
    if etag:
        request=urllib.request.Request('http://127.0.0.1:38184/api.php?action='+action,headers={**headers,'If-None-Match':etag})
        begin=time.perf_counter()
        try:response=urllib.request.urlopen(request,timeout=90)
        except urllib.error.HTTPError as error:response=error
        raw=response.read();row['conditionalRead']={'status':response.status,'bytes':len(raw),'ms':round((time.perf_counter()-begin)*1000,2)}
        assert response.status==304 and not raw
    rows.append(row)
report={'scope':platform.system()+' PHP development server; synthetic fixture; sequential local reads, not PHP-FPM capacity or production SLA','results':rows}
(base/'read-performance-results.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
