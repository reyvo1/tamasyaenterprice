from growth_client import request,base
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import json,secrets,subprocess,os,collections
from runtime_tools import mysql_binary
b=Path(__file__).resolve().parent;e=json.loads((base/'environment.json').read_text(encoding='utf-8'));db=e['APP_EXPECTED_DB_NAME'];assert db.startswith('tamasya_growth_test_')
args=[mysql_binary(),'--defaults-file='+str(b/'client.ini'),'--batch','--skip-column-names',db]
def sql(q):
 r=subprocess.run(args,input=q,capture_output=True,text=True,encoding='utf-8');r.check_returncode();return r.stdout.strip()
assert sql('SELECT @@port')=='23384'
results=[];prefix='delivery_'+secrets.token_hex(5)
def check(name,ok,detail=None):
 results.append({'name':name,'pass':bool(ok),'detail':detail});(b/'growth-crm-delivery-results.json').write_text(json.dumps(results,indent=2),encoding='utf-8');print('PASS' if ok else 'FAIL',name,flush=True)
 if not ok:raise AssertionError(str(detail))
def post(command,data=None,action='enterprise-suite'):
 payload={'command':command,**(data or {}),'operationId':prefix+'_'+secrets.token_hex(7)};s,d=request(action,'POST',payload,payload['operationId']);check(command,s==200 and d.get('success') is True,{'status':s,'error':d.get('error')});return d
before=sql('SELECT CONCAT(COUNT(*),"|",SUM(amount)) FROM transactions')
guests={}
for mode in ['success','false','throw','revoke','changed']:
 guest=prefix+'_'+mode;guests[mode]=guest
 post('guest-profile-save',{'id':guest,'name':guest,'email':guest+'@example.invalid'},'operations-center')
 post('consent-save',{'guestProfileId':guest,'consentType':'email_marketing','status':'granted','evidenceReference':'simulated-delivery'})
campaign=post('crm-campaign-save',{'name':prefix,'channel':'email','subject':'Mock only','messageTemplate':'Hello {{guest_name}}'})['data']['id']
post('crm-campaign-approve',{'id':campaign});post('crm-campaign-snapshot',{'id':campaign})
post('consent-save',{'guestProfileId':guests['revoke'],'consentType':'email_marketing','status':'revoked'})
post('guest-profile-save',{'id':guests['changed'],'name':guests['changed'],'email':guests['changed']+'_new@example.invalid'},'operations-center')
log=base/'logs'/('delivery-'+prefix+'.jsonl')
def run(_):
 r=subprocess.run(['php',str(b/'crm_delivery_probe.php'),campaign,str(log)],env={**os.environ,**e},capture_output=True,text=True,encoding='utf-8');return {'code':r.returncode,'out':r.stdout,'error':r.stderr}
with ThreadPoolExecutor(max_workers=2) as pool:out=list(pool.map(run,range(2)))
check('Two real PHP processes finish safely',all(r['code']==0 for r in out),out)
s,d=request('enterprise-suite&command=crm-campaign-recipients&id='+campaign)
check('Operator can review per-recipient delivery outcomes',s==200 and d.get('success') is True and d['data']['automaticRetry'] is False and any(x['status']=='uncertain' for x in d['data']['recipients']),{'status':s,'error':d.get('error')})
calls=[json.loads(line)['destination'] for line in log.read_text(encoding='utf-8').splitlines()]
counts=collections.Counter(calls)
check('Parallel senders claim each recipient at most once',all(v==1 for v in counts.values()),dict(counts))
check('Revoked consent and changed address never sent',not any(guests['revoke'] in v or guests['changed'] in v for v in calls))
for mode,status in [('success','sent'),('false','uncertain'),('throw','uncertain'),('revoke','blocked'),('changed','blocked')]:
 check(mode+' has durable '+status,sql("SELECT status FROM growth_crm_campaign_recipients WHERE campaign_id='"+campaign+"' AND guest_profile_id='"+guests[mode]+"'")==status)
post('crm-campaign-snapshot',{'id':campaign})
again=run(0);check('Sender can resume after snapshot',again['code']==0,again)
after=[json.loads(line)['destination'] for line in log.read_text(encoding='utf-8').splitlines()]
for mode in ['success','false','throw']:
 check(mode+' is never automatically resent',after.count(guests[mode]+'@example.invalid')==1)
check('Uncertain deliveries keep campaign open for review',sql("SELECT status FROM growth_crm_campaigns WHERE id='"+campaign+"'")=='ready')
check('Delivery preserves canonical money',before==sql('SELECT CONCAT(COUNT(*),"|",SUM(amount)) FROM transactions'))
print('CRM delivery assertions:',len(results))
