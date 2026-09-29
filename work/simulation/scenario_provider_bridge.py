from growth_client import request,base
from pathlib import Path
import json,secrets,time,base64,hmac,hashlib,subprocess,sqlite3,tempfile
from runtime_tools import mysql_binary
b=Path(__file__).resolve().parent
env=json.loads((base/'environment.json').read_text(encoding='utf-8'));secret=env['TAMASYA_TEST_BRIDGE_KEY'];results=[]
def check(name,ok):
 results.append({'name':name,'pass':bool(ok)});(b/'provider-bridge-results.json').write_text(json.dumps(results,indent=2),encoding='utf-8');print('PASS' if ok else 'FAIL',name,flush=True)
 assert ok,name
def post(command,data):
 return request('enterprise-suite','POST',{'command':command,'operationId':'bridge_'+secrets.token_hex(12),**data})
def signed(body):
 encoded=base64.b64encode(json.dumps(body,separators=(',',':')).encode()).decode()
 return {'version':'tamasya-provider-bridge-v1','body':encoded,'signature':hmac.new(secret.encode(),('tamasya-provider-bridge-v1\n'+encoded).encode(),hashlib.sha256).hexdigest()}
s,d=request('enterprise-suite&command=bootstrap');assert s==200 and d['success'];identity=d['data']['identity']
db=env['APP_EXPECTED_DB_NAME'];assert db.startswith('tamasya_growth_test_')
args=[mysql_binary(),'--defaults-file='+str(b/'client.ini'),'--batch','--skip-column-names',db]
def sql(q):
 r=subprocess.run(args,input=q,capture_output=True,text=True,encoding='utf-8');r.check_returncode();return r.stdout.strip()
assert sql('SELECT @@port')=='33384'
before=sql('SELECT (SELECT COUNT(*) FROM transactions),(SELECT COUNT(*) FROM bookings),(SELECT COUNT(*) FROM journal_entries)')
now=int(time.time());ids={}
for kind in ['payment','channel']:
 s,d=post('provider-adapter-save',{'adapterType':kind,'providerCode':'local-bridge-fixture','mode':'sandbox','active':True,'credentialReference':'env:TAMASYA_TEST_BRIDGE_KEY','webhookVerifier':'hmac_sha256'})
 check(kind+' sandbox configuration',s==200 and d.get('success'));ids[kind]=d['data']['id']
body={k:identity[k] for k in ['companyId','propertyId','currency']}
body.update(providerCode='local-bridge-fixture',adapterType='payment',eventId='evt-'+secrets.token_hex(8),issuedAt=now,expiresAt=now+120,eventType='payment.status',payload={'intentId':'pi-fixture','status':'paid','amountMinor':12345})
def validate(body,kind='payment'):
 return post('provider-bridge-validate',{'adapterId':ids[kind],'envelope':signed(body)})
s,d=validate(body);check('signed payment HTTP validation',s==200 and d.get('success'));ack=d['data']
check('HTTP validation explicitly is not durable ACK',ack['status']=='validated_only' and not ack['durablyAccepted'] and not ack['providerSignatureVerified'])
s,d=validate(body);check('repeat validation retains key and hash',d['data']['eventKey']==ack['eventKey'] and d['data']['contentHash']==ack['contentHash'])
changed={**body,'payload':{**body['payload'],'amountMinor':12346}};s,d=validate(changed)
check('conflicting replay is identifiable',s==200 and d['data']['eventKey']==ack['eventKey'] and d['data']['contentHash']!=ack['contentHash']);conflict=d['data']
# Local durable inbox simulation: an ACK follows COMMIT; restart/redelivery preserves evidence.
path=b/'logs'/('bridge-inbox-'+secrets.token_hex(8)+'.sqlite')
try:
 con=sqlite3.connect(path);con.execute('CREATE TABLE inbox(event_key TEXT PRIMARY KEY,content_hash TEXT NOT NULL,status TEXT NOT NULL)');con.commit();con.close()
 def accept(event):
  with sqlite3.connect(path) as con:
   con.execute('BEGIN IMMEDIATE');row=con.execute('SELECT content_hash FROM inbox WHERE event_key=?',(event['eventKey'],)).fetchone()
   if row:
    if row[0]!=event['contentHash']:return 'conflict'
    return 'duplicate'
   con.execute('INSERT INTO inbox VALUES (?,?,?)',(event['eventKey'],event['contentHash'],'pending_review'));con.commit();return 'accepted'
 check('simulator durably accepts before ACK',accept(ack)=='accepted')
 check('lost ACK and restarted connection do not duplicate',accept(ack)=='duplicate')
 check('simulator rejects event ID content conflict',accept(conflict)=='conflict')
 with sqlite3.connect(path) as con:check('one immutable inbox item after retries',con.execute('SELECT COUNT(*) FROM inbox').fetchone()[0]==1)
finally:
 # Keep the local fixture as evidence; it contains only synthetic event hashes.
 pass
for name,change in [('wrong property',{'propertyId':'another-hotel'}),('expired',{'expiresAt':now-1}),('fractional cents',{'payload':{**body['payload'],'amountMinor':123.45}})]:
 s,d=validate({**body,**change});check(name+' rejected through HTTP '+str(s),s in [400,422] and d.get('success') is False)
channel={**body,'adapterType':'channel','eventType':'reservation.created','payload':{'externalReservationId':'OTA-fixture','externalRoomType':'DELUXE','checkIn':'2026-10-01','checkOut':'2026-10-02','totalMinor':30000000}}
s,d=validate(channel,'channel');check('signed channel HTTP validation',s==200 and d.get('success') and not d['data']['bookingMutation'])
check('validation and inbox simulation leave canonical ledger untouched',before==sql('SELECT (SELECT COUNT(*) FROM transactions),(SELECT COUNT(*) FROM bookings),(SELECT COUNT(*) FROM journal_entries)'))
print('Provider bridge assertions:',len(results))
