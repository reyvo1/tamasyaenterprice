from client import request,base
from scenario_core import db
import json,hashlib,hmac,time,uuid,urllib.request,urllib.error,copy,subprocess
results=[]
def check(name,ok,detail=None):
 results.append({'test':name,'pass':bool(ok),'details':detail});print('PASS' if ok else 'FAIL',name, str(detail or '')[:200],flush=True)
 (base/'logs/hybrid-results.json').write_text(json.dumps(results,indent=2),encoding='utf8')
 if not ok:raise AssertionError(name)
def encode(data):return json.dumps(data,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def checksum(s):return hashlib.sha256(encode({k:v for k,v in s.items() if k!='checksumSha256'}).encode()).hexdigest()
def http(url,method='GET',data=None,headers=None):
 req=urllib.request.Request(url,data=data,headers=headers or {},method=method)
 try:r=urllib.request.urlopen(req,timeout=90)
 except urllib.error.HTTPError as error:r=error
 raw=r.read();body=json.loads(raw) if raw else None
 return r.status,body,dict(r.headers)
config=json.loads((base/'hq-config.json').read_text());token=(base/'hq-test-token').read_text()
prefix='h1_'+uuid.uuid4().hex[:12]
def send(s,op=None,nonce=None,corrupt=False,ts=None):
 body=encode(s).encode();op=op or prefix+'_'+uuid.uuid4().hex[:8];nonce=nonce or 'hq_'+uuid.uuid4().hex;ts=str(ts or int(time.time()))
 headers={'Content-Type':'application/json','X-Tamasya-Company-ID':s['companyId'],'X-Tamasya-Property-ID':s['propertyId'],'X-Tamasya-Operation-ID':op,'X-Tamasya-Timestamp':ts,'X-Tamasya-Nonce':nonce}
 secret=config['properties'][s['companyId']][s['propertyId']]['secret']
 canonical='\n'.join([ts,nonce,s['companyId'],s['propertyId'],op,hashlib.sha256(body).hexdigest()])
 headers['X-Tamasya-Signature']=hmac.new(secret.encode(),canonical.encode(),hashlib.sha256).hexdigest() if not corrupt else '0'*64
 return http('http://127.0.0.1:38185/api.php?action=property-snapshot','POST',body,headers)
today=__import__('datetime').datetime.now(__import__('datetime').timezone(__import__('datetime').timedelta(hours=8))).date()
fromdate=str(today.replace(day=1));todate=str(today)
status,body=request(f'multi-property&command=snapshot-v3&from={fromdate}&to={todate}')
check('Property snapshot reads real canonical MySQL data',status==200 and body.get('success') is True,body.get('error'));s=body['data']
check('Checksum interoperates with Python canonical JSON',checksum(s)==s['checksumSha256'])
check('Snapshot has explicit company/property',s['companyId']=='sim-company' and s['propertyId']=='simulation-hotel')
check('Snapshot contains no rows/guest/staff data',set(s)=={'contractVersion','companyId','propertyId','propertyName','currency','timezone','period','sourceRevision','metricsMinor','roomNights','integrity','checksumSha256'})
st,canonical=request(f'canonical-report&type=financial_summary&from={fromdate}&to={todate}&format=json')
check('Canonical financial report available for reconciliation',st==200 and 'summary' in canonical)
labels={'revenue':'Pendapatan Operasional Diakui','expense':'Beban Operasional Diakui','profit':'Laba/Rugi Operasional','taxAccrued':'PBJT Terbentuk','taxPaid':'PBJT Dibayar','incomeTaxPaid':'PPh Dibayar','cashMovement':'Kas Bersih','bankMovement':'Bank/QRIS Bersih','liquidMovement':'Total Likuid Bersih'}
for key,label in labels.items():check('Source reconciliation '+key,int(s['metricsMinor'][key])==round(canonical['summary'][label]*100))
for f,t in [('2026-02-30','2026-03-01'),('2026-09-15','2026-09-01'),('2025-01-01','2026-09-15')]:
 st,_=request(f'multi-property&command=snapshot-v3&from={f}&to={t}');check('Reject invalid snapshot date range '+f+' '+t,st==400)
auth={'Authorization':'Bearer '+json.loads((base/'session.json').read_text())['token'],'X-Device-ID':'simulation-browser-01'}
for key,value in [('X-Tamasya-Company-ID','other-company'),('X-Tamasya-Property-ID','hotel-b'),('X-Tamasya-Property-ID','')]:
 st,b,_=http('http://127.0.0.1:38184/api.php?action=multi-property',headers={**auth,key:value});check('Property API rejects explicit foreign/malformed scope '+key+value,st==409 and b['code']=='PROPERTY_SCOPE_MISMATCH')
st,b,h=http(f'http://127.0.0.1:38184/api.php?action=multi-property&command=snapshot-v3&from={fromdate}&to={todate}',headers=auth)
st,b2,h2=http(f'http://127.0.0.1:38184/api.php?action=multi-property&command=snapshot-v3&from={fromdate}&to={todate}',headers={**auth,'If-None-Match':h['ETag']});check('Property snapshot conditional GET 304',st==304)
st,b,_=send(s,corrupt=True);check('HQ rejects forged signature',st==401 and b['code']=='SIGNATURE_INVALID')
st,b,_=send(s,ts=int(time.time())-600);check('HQ rejects expired signature',st==401)
bad=copy.deepcopy(s);bad['metricsMinor']['revenue']='1';st,b,_=send(bad);check('HQ rejects corrupted checksum',st==422)
bad=copy.deepcopy(s);bad['guestName']='must not export';bad['checksumSha256']=checksum(bad);st,b,_=send(bad);check('HQ rejects extra PII fields even with valid checksum',st==422)
op=prefix+'_receipt';nonce='hq_'+uuid.uuid4().hex
st,b,_=send(s,op,nonce);check('Signed snapshot durably ACKed',st==200 and b['receipt']==s['checksumSha256'],b)
st,b,_=send(s,op);check('Retry same operation returns original receipt',st==200 and b['duplicate'] is True)
bad=copy.deepcopy(s);bad['sourceRevision']+=1;bad['checksumSha256']=checksum(bad)
st,b,_=send(bad,op);check('Operation ID cannot change immutable payload',st==409 and b['code']=='OPERATION_PAYLOAD_CONFLICT')
st,b,_=send(s,nonce=nonce);check('Nonce cannot be reused for a new operation',st==409 and b['code']=='NONCE_REPLAY')
bad=copy.deepcopy(s);bad['sourceRevision']=max(0,s['sourceRevision']-1);bad['checksumSha256']=checksum(bad)
st,b,_=send(bad);check('Older source revision cannot replace HQ head',st==409 and b['code']=='STALE_SOURCE_REVISION')
bad=copy.deepcopy(s);bad['propertyName']='Different source at same revision';bad['checksumSha256']=checksum(bad)
st,b,_=send(bad);check('Equal revision different snapshot fails closed',st==409 and b['code']=='SOURCE_REVISION_CONFLICT')
# Synthetic independent property/organization fixtures exercise HQ isolation and weighted consolidation.
second=copy.deepcopy(s);second['propertyId']='hotel-b';second['propertyName']='Hotel B';second['roomNights']={'sold':1,'available':10};second['checksumSha256']=checksum(second)
st,b,_=send(second);check('Second authorized property accepted',st==200,b)
third=copy.deepcopy(second);third['propertyId']='hotel-c';third['currency']='USD';third['checksumSha256']=checksum(third)
st,b,_=send(third);check('Different currency property accepted without FX conversion',st==200,b)
foreign=copy.deepcopy(s);foreign['companyId']='other-company';foreign['propertyId']='hotel-z';foreign['checksumSha256']=checksum(foreign)
st,b,_=send(foreign);check('Separate company stored independently',st==200,b)
viewer={'Authorization':'Bearer '+token}
st,b,_=http('http://127.0.0.1:38185/api.php');check('Anonymous HQ read denied',st==401)
st,b,_=http('http://127.0.0.1:38185/api.php',headers={'Authorization':'Bearer '+'x'*40});check('Unknown HQ viewer denied',st==403)
url=f'http://127.0.0.1:38185/api.php?action=consolidated&from={fromdate}&to={todate}'
st,b,_=http(url+'&properties=hotel-z',headers=viewer);check('Company viewer cannot query foreign property',st==403)
st,b,h=http(url,headers=viewer);check('Consolidation reads stored aggregate model',st==200,b.get('message'));report=b['data']['report']
check('HQ report checksum verifiable',checksum(report)==report['checksumSha256'])
check('HQ source set excludes foreign company',set(x['propertyId'] for x in report['sources'])=={'simulation-hotel','hotel-b','hotel-c'})
check('Currencies never silently combined',set(report['currencies'])=={'IDR','USD'})
for key in labels:check('HQ exact sum '+key,int(report['currencies']['IDR']['metricsMinor'][key])==int(s['metricsMinor'][key])*2)
expected=round((s['roomNights']['sold']+1)/(s['roomNights']['available']+10)*100,2)
check('Occupancy weighted by total room nights',report['currencies']['IDR']['occupancyPct']==expected)
st,b2,_=http(url,headers={**viewer,'If-None-Match':h['ETag']});check('HQ authorized ETag returns 304',st==304)
st,b,_=http(url.replace(todate,'2026-08-31').replace(fromdate,'2026-08-01'),headers=viewer)
check('Missing snapshots yield INCOMPLETE instead of fabricated zero',st==200 and b['data']['report']['integrityStatus']=='INCOMPLETE' and len(b['data']['report']['missingProperties'])==3)
queueop=prefix+'_queued'
st,b=request('multi-property','POST',{'command':'queue-snapshot','from':fromdate,'to':todate,'operationId':queueop});check('Outbox persists before returning pending',st==202 and b['data']['status']=='pending',b)
st,b=request('multi-property','POST',{'command':'queue-snapshot','from':fromdate,'to':todate,'operationId':queueop});check('Enqueue retry retains same operation',st==202 and b['data']['operation_id']==queueop)
st,b=request('multi-property','POST',{'command':'queue-snapshot','from':'2026-08-01','to':'2026-08-31','operationId':queueop});check('Queue operation cannot change requested period',st==400)
st,b=request('multi-property','POST',{'command':'deliver-snapshot','operationId':queueop});check('Real HTTPS outbox delivery gets matching durable ACK',st==200 and b['data']['status']=='acknowledged',b)
st,b=request('multi-property','POST',{'command':'deliver-snapshot','operationId':queueop});check('ACKed job delivery is idempotent',st==200 and b['data']['attempts']==1,b)
st,b=request('multi-property&command=outbox');check('Outbox status exposes ACK without raw snapshot',st==200 and any(j['operation_id']==queueop and j['status']=='acknowledged' and 'snapshot' not in j for j in b['data']['jobs']))
(base/'logs/hybrid-source-snapshot.json').write_text(json.dumps(s,indent=2));print('HYBRID CHECKS PASSED',len(results))
