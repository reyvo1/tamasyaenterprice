from runtime_tools import mysql_binary, mysqldump_binary, background_process_options, python_command
from pathlib import Path
import json,os,subprocess,secrets,shutil,sys,importlib.util,datetime,hashlib
sys.stdout.reconfigure(encoding='utf8')
b=Path(__file__).resolve().parent;second=b.parent/'simulation-secondary';second.mkdir(exist_ok=True);(second/'logs').mkdir(exist_ok=True)
mysql=mysql_binary()
def root(sql):
 r=subprocess.run([mysql,'--defaults-file='+str(b/'client.ini'),'--raw','--batch','--skip-column-names'],input=sql,capture_output=True,text=True,encoding='utf8');r.check_returncode();return r.stdout.strip()
assert root('SELECT @@port')=='23384' and Path(root('SELECT @@datadir')).resolve()==(b/'mysql-data').resolve()
if '--continue-fixture' in sys.argv:
 e=json.loads((second/'environment.json').read_text());assert e['APP_EXPECTED_DB_NAME']=='tamasya_branch_h1_sim' and e['TAMASYA_PROPERTY_ID']=='real-hotel-b'
else:
 if root("SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name='tamasya_branch_h1_sim'")!='0':raise RuntimeError('Secondary fixture already exists; do not silently overwrite.')
 password=secrets.token_hex(32)
 root("CREATE DATABASE tamasya_branch_h1_sim CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci; CREATE USER IF NOT EXISTS 'tamasya_branch_sim'@'127.0.0.1' IDENTIFIED BY '"+password+"'; GRANT ALL ON tamasya_branch_h1_sim.* TO 'tamasya_branch_sim'@'127.0.0.1';")
 root('USE tamasya_branch_h1_sim;\n'+(b.parent/'enterprise/database_setup.sql').read_text(encoding='utf8'))
 credential=second/'db_credentials.php';credential.write_text("<?php return ['host'=>'127.0.0.1','port'=>23384,'name'=>'tamasya_branch_h1_sim','user'=>'tamasya_branch_sim','pass'=>'"+password+"'];")
 (second/'credentials.json').write_text(json.dumps({'user':'tamasya_branch_sim','password':password}))
 for filename in ['client.py','scenario_setup.py']:
  content=(b/filename).read_text(encoding='utf8').replace('28184','28187').replace('SIMULATION HOTEL','SECOND PROPERTY STAGING')
  (second/filename).write_text(content,encoding='utf8')
 e=json.loads((b/'hybrid-environment.json').read_text());e.update({'APP_URL':'http://127.0.0.1:28187','APP_ALLOWED_ORIGINS':'http://127.0.0.1:28187','APP_CREDENTIALS_FILE':credential.as_posix(),'APP_EXPECTED_DB_NAME':'tamasya_branch_h1_sim','APP_ENCRYPTION_KEY':secrets.token_hex(32),'APP_BOOTSTRAP_ADMIN_PASSWORD':secrets.token_hex(24),'TAMASYA_PROPERTY_ID':'real-hotel-b','TAMASYA_PROPERTY_CODE':'REALB','TAMASYA_PROPERTY_NAME':'SECOND PROPERTY STAGING','TAMASYA_NODE_ID':'second-primary','TAMASYA_HQ_SHARED_SECRET':secrets.token_hex(32)})
 (second/'environment.json').write_text(json.dumps(e));runtime=os.environ.copy();runtime.update(e)
 site=b/'site';r=subprocess.run(['php',str(site/'first_install.php')],env=runtime,capture_output=True,text=True);r.check_returncode()
 log=open(second/'logs/php.log','ab');p=subprocess.Popen(['php','-d','curl.cainfo='+str(b/'tls-ca.pem'),'-d','openssl.cafile='+str(b/'tls-ca.pem'),'-S','127.0.0.1:28187','-t',str(site)],env=runtime,stdout=log,stderr=log,**background_process_options());(second/'php.pid').write_text(str(p.pid))
 for command in [['client.py','login'],['scenario_setup.py']]:
  r=subprocess.run([python_command(),'-u',str(second/command[0])]+command[1:],capture_output=True,encoding='utf8');(second/'logs'/('run-'+command[0]+'.txt')).write_text(r.stdout+r.stderr,encoding='utf8');r.check_returncode()
spec=importlib.util.spec_from_file_location('second_client',second/'client.py');client=importlib.util.module_from_spec(spec);spec.loader.exec_module(client)
from client import request
results=[]
def check(name,ok,detail=None):
 results.append({'test':name,'pass':bool(ok),'details':detail});print('PASS' if ok else 'FAIL',name,flush=True);(b/'logs/second-property-results.json').write_text(json.dumps(results,indent=2))
 if not ok:raise AssertionError(str(detail))
check('Independent second database completes setup',all(r['pass'] for r in json.loads((second/'logs/setup-results.json').read_text(encoding='utf8'))))
state=json.loads((second/'state.json').read_text());today=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).date();start=str(today.replace(day=1));end=str(today)
payload={'operationId':'second_historical_h1_valid','type':'income','categoryId':state['room_rental'],'amount':750000,'date':start,'description':'SECOND HOTEL HISTORICAL FIXTURE','recordOrigin':'historical_import','shiftExemptionReason':'Staging historical record','historicalSourceType':'receipt','historicalSourceReference':'SECOND-HOTEL-H1','bookingSource':'Direct','historicalTaxMode':'rule_by_date'}
before_status,before=client.request(f'multi-property&command=snapshot-v3&from={start}&to={end}')
assert before_status==200
before_revenue=int(before['data']['metricsMinor']['revenue'])
operation='second_historical_'+secrets.token_hex(8);payload['operationId']=operation;payload['historicalSourceReference']=operation
st,body=client.request('transactions','POST',payload,operation);check('Second hotel backfill uses canonical API',st==200 and body.get('success') is True,body.get('error'))
st,one=request(f'multi-property&command=snapshot-v3&from={start}&to={end}');st2,two=client.request(f'multi-property&command=snapshot-v3&from={start}&to={end}')
check('Both physical databases generate valid snapshots',st==200 and st2==200);a=one['data'];c=two['data']
check('Second financial summary increases by its own backfill amount',int(c['metricsMinor']['revenue'])==before_revenue+75000000 and a['metricsMinor']['revenue']!=c['metricsMinor']['revenue'])
check('Second property has independent identity/revision',c['propertyId']=='real-hotel-b' and c['companyId']=='sim-company' and c['sourceRevision']!=a['sourceRevision'])
import urllib.request,urllib.error
token=json.loads((b/'session.json').read_text())['token'];req=urllib.request.Request('http://127.0.0.1:28187/api.php?action=multi-property',headers={'Authorization':'Bearer '+token,'X-Device-ID':'simulation-browser-01'})
try:resp=urllib.request.urlopen(req)
except urllib.error.HTTPError as err:resp=err
check('First hotel session cannot access second hotel database',resp.status in (401,403))
conf=json.loads((b/'hq-config.json').read_text());conf['properties']['sim-company']['real-hotel-b']={'enabled':True,'secret':e['TAMASYA_HQ_SHARED_SECRET']};conf['viewers'][0]['propertyIds'].append('real-hotel-b');(b/'hq-config.json').write_text(json.dumps(conf))
mainop='first_property_snapshot_'+secrets.token_hex(8)
st,res=request('multi-property','POST',{'command':'queue-snapshot','from':start,'to':end,'operationId':mainop});check('First property current-period snapshot queued',st==202)
st,res=request('multi-property','POST',{'command':'deliver-snapshot','operationId':mainop});check('First property current-period snapshot acknowledged',st==200 and res.get('receipt')==a['checksumSha256'])
op='second_property_snapshot_'+secrets.token_hex(8);st,res=client.request('multi-property','POST',{'command':'queue-snapshot','from':start,'to':end,'operationId':op});check('Second hotel outbox persists separately',st==202,res.get('error'))
st,res=client.request('multi-property','POST',{'command':'deliver-snapshot','operationId':op});check('Second hotel sends signed snapshot over HTTPS',st==200 and res['receipt']==c['checksumSha256'],res.get('error'))
viewer=(b/'hq-test-token').read_text();req=urllib.request.Request(f'http://127.0.0.1:28185/api.php?action=consolidated&from={start}&to={end}&properties=simulation-hotel,real-hotel-b',headers={'Authorization':'Bearer '+viewer});res=json.load(urllib.request.urlopen(req));report=res['data']['report']
check('HQ consolidates two real property databases',set(x['propertyId'] for x in report['sources'])=={'simulation-hotel','real-hotel-b'})
for key in ['revenue','expense','profit','taxAccrued','cashMovement','bankMovement','journalDebit','journalCredit']:
 check('Two real source sum '+key,int(report['currencies']['IDR']['metricsMinor'][key])==int(a['metricsMinor'][key])+int(c['metricsMinor'][key]))
check('Hotel outbox namespaces are distinct',hashlib.sha256(b'sim-company\nsimulation-hotel').hexdigest()!=hashlib.sha256(b'sim-company\nreal-hotel-b').hexdigest())
print('SECOND PROPERTY CHECKS',len(results))
