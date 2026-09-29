from client import request,base
import json,uuid,hashlib,datetime
results=[]
def check(name,ok,details=None):
 results.append({'test':name,'pass':bool(ok),'details':details});print('PASS' if ok else 'FAIL',name,flush=True)
 (base/'logs/hybrid-failure-results.json').write_text(json.dumps(results,indent=2))
 if not ok:raise AssertionError(str(details))
now=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).date();start=str(now.replace(day=1));end=str(now)
def call(command,operation,extra={}):return request('multi-property','POST',{'command':command,'operationId':operation,**extra})
def fixture_due(operation):
 # Only the isolated staging queue clock is advanced; payload/id/checksum are preserved.
 scope=hashlib.sha256(b'sim-company\nsimulation-hotel').hexdigest();p=base/'hybrid-outbox'/scope/(hashlib.sha256(operation.encode()).hexdigest()+'.json');j=json.loads(p.read_text());j['next_attempt_at']=0;p.write_text(json.dumps(j));return j
modefile=base/'hybrid-proxy-mode'
try:
 for mode in ['accepted','wrong_ack','drop_after_commit','permanent']:
  op='failure_'+uuid.uuid4().hex
  st,b=call('queue-snapshot',op,{'from':start,'to':end});check(mode+' durable enqueue',st==202,b)
  original=b['data']['checksum'];modefile.write_text(mode)
  st,b=call('deliver-snapshot',op);j=b.get('data',{})
  check(mode+' never misclassified as ACK',st==202 and j.get('status')==('dead_letter' if mode=='permanent' else 'pending'),b)
  check(mode+' retains original immutable identity',j.get('checksum')==original and j.get('operation_id')==op and j.get('receipt') is None)
  modefile.write_text('')
  if mode=='permanent':
   st,b=call('requeue-snapshot',op);check('Dead-letter redrive preserves operation and attempts',st==202 and b['data']['operation_id']==op and b['data']['attempts']==1,b)
  else:fixture_due(op)
  st,b=call('deliver-snapshot',op);check(mode+' recovers with same operation receipt',st==200 and b['data']['status']=='acknowledged' and b['data']['receipt']==original,b)
  check(mode+' retry counted exactly once',b['data']['attempts']==2)
 # Exhaust retries, preserving each durable attempt.
 op='exhaust_'+uuid.uuid4().hex;st,b=call('queue-snapshot',op,{'from':start,'to':end});modefile.write_text('accepted')
 for attempt in range(1,6):
  fixture_due(op);st,b=call('deliver-snapshot',op);check('Bounded retry attempt '+str(attempt),b['data']['attempts']==attempt and b['data']['status']==('dead_letter' if attempt==5 else 'pending'),b)
finally:modefile.write_text('')
print('HYBRID FAILURE CHECKS',len(results))
