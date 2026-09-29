from growth_client import request,base
from pathlib import Path
import json,secrets,subprocess,datetime,os,hashlib,hmac,time,socket,urllib.request,urllib.error
from runtime_tools import background_process_options,mysql_binary,mysql_datadir
b=Path(__file__).resolve().parent;e=json.loads((base/'environment.json').read_text(encoding='utf-8'));db=e['APP_EXPECTED_DB_NAME'];assert db.startswith('tamasya_growth_test_')
args=[mysql_binary(),'--defaults-file='+str(b/'client.ini'),'--batch','--skip-column-names']
def sql(q,database=db):
 r=subprocess.run(args+[database],input=q,capture_output=True,text=True,encoding='utf-8');r.check_returncode();return r.stdout.strip()
port,datadir=sql('SELECT @@port,@@datadir').split('\t');assert port=='33384' and Path(datadir).resolve()==mysql_datadir(b/'mysql-data')
results=[];prefix='v3_'+secrets.token_hex(5);today=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).date().isoformat();start=today[:7]+'-01'
def check(name,ok,detail=None):
 results.append({'name':name,'pass':bool(ok),'detail':detail});(b/'growth-hq-v3-results.json').write_text(json.dumps(results,indent=2),encoding='utf-8');print('PASS' if ok else 'FAIL',name,flush=True)
 if not ok:raise AssertionError(str(detail))
sql("UPDATE property_settings SET company_id='growth-fixture-company'")
def snapshot(version):
 s,d=request('multi-property&command=snapshot-'+version+'&from='+start+'&to='+today);check('Read '+version+' canonical snapshot',s==200 and d.get('success') is True,d.get('error'));return d['data']
v2=snapshot('v2');v3=snapshot('v3');check('v2 and v3 use same revision',v2['sourceRevision']==v3['sourceRevision'])
def metric(account,period=False):
 date="e.entry_date BETWEEN '"+start+"' AND '"+today+"'" if period else "e.entry_date<='"+today+"'"
 return str(int(sql("SELECT ROUND(COALESCE(SUM(l.debit-l.credit),0)*100,0) FROM journal_entries e JOIN journal_lines l ON l.journal_entry_id=e.id WHERE e.status='posted' AND "+date+" AND l.account_code='"+account+"'")))
m=v3['metricsMinor'];check('Payroll equals canonical journal account 5101',m['payrollExpense']==metric('5101',True))
check('Guest receivable equals canonical account 1104',m['guestReceivableBalance']==metric('1104'))
check('OTA receivable equals canonical account 1103',m['otaReceivableBalance']==metric('1103'))
check('AP equals credit balance of account 2103',m['accountsPayableBalance']==str(-int(metric('2103'))))
def stable(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def rehash(s):
 s.pop('checksumSha256',None);s['checksumSha256']=hashlib.sha256(stable(s).encode()).hexdigest();return s
try:
 with socket.create_connection(('127.0.0.1',38190),timeout=.3):raise RuntimeError('Test port 38190 already in use')
except OSError:pass
hqdb='tamasya_hq_growth_test_'+secrets.token_hex(4)
sql('CREATE DATABASE `'+hqdb+'` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci; USE `'+hqdb+'`;\n'+(base/'site/hq/schema.sql').read_text(encoding='utf-8'))
sql("GRANT ALL ON `"+hqdb+"`.* TO 'tamasya_sim'@'127.0.0.1'")
creds=json.loads((b/'credentials.json').read_text(encoding='utf-8'));token=secrets.token_urlsafe(32);company=v3['companyId'];prop=v3['propertyId'];other='other-fixture-hotel'
cfg={'dsn':'mysql:host=127.0.0.1;port=33384;dbname='+hqdb+';charset=utf8mb4','username':'tamasya_sim','password':creds['password'],'properties':{company:{prop:{'enabled':True,'secret':secrets.token_hex(32)},other:{'enabled':True,'secret':secrets.token_hex(32)}}},'viewers':[{'enabled':True,'companyId':company,'propertyIds':[prop,other],'tokenSha256':hashlib.sha256(token.encode()).hexdigest()}]}
path=base/(prefix+'-hq.private.json');path.write_text(json.dumps(cfg),encoding='utf-8')
def http(action,body=None,headers=None):
 req=urllib.request.Request('http://127.0.0.1:38190/api.php?action='+action,data=body,headers=headers or {},method='POST' if body is not None else 'GET')
 try:r=urllib.request.urlopen(req,timeout=60)
 except urllib.error.HTTPError as x:r=x
 raw=r.read().decode('utf-8-sig')
 try:d=json.loads(raw)
 except ValueError:d={'raw':raw[:300]}
 return r.status,d
def push(s,op=None):
 body=stable(s).encode();ts=str(int(time.time()));nonce=secrets.token_hex(16);op=op or prefix+'_'+secrets.token_hex(7)
 canonical='\n'.join([ts,nonce,company,s['propertyId'],op,hashlib.sha256(body).hexdigest()])
 headers={'Content-Type':'application/json','X-Tamasya-Timestamp':ts,'X-Tamasya-Nonce':nonce,'X-Tamasya-Company-ID':company,'X-Tamasya-Property-ID':s['propertyId'],'X-Tamasya-Operation-ID':op,'X-Tamasya-Signature':hmac.new(cfg['properties'][company][s['propertyId']]['secret'].encode(),canonical.encode(),hashlib.sha256).hexdigest()}
 return http('property-snapshot',body,headers)
log=open(base/'logs'/('hq-'+prefix+'.log'),'ab');p=subprocess.Popen(['php','-S','127.0.0.1:38190','-t',str(base/'site/hq')],env={**os.environ,**e,'TAMASYA_HQ_CONFIG_FILE':str(path)},stdout=log,stderr=log,**background_process_options())
try:
 for i in range(30):
  try:
   with socket.create_connection(('127.0.0.1',38190),timeout=.2):break
  except OSError:time.sleep(.1)
 op=prefix+'_original';s,d=push(v2,op);check('Signed v2 ingest accepted',s==200 and d.get('status')=='acknowledged',d)
 s,d=push(v3);check('Signed additive v3 upgrade at same revision accepted',s==200 and d.get('status')=='acknowledged',d)
 s,d=push(v2,op);check('Original v2 receipt replay remains idempotent',s==200 and d.get('duplicate') is True,d)
 s,d=push(v2);check('New v2 write cannot downgrade v3 head',s==409,d)
 bad=json.loads(json.dumps(v3));bad['metricsMinor']['payrollExpense']=str(int(m['payrollExpense'])+1);rehash(bad);s,d=push(bad);check('Same revision cannot replace v3 payroll amount',s==409,d)
 oldother=json.loads(json.dumps(v2));oldother['propertyId']=other;rehash(oldother);s,d=push(oldother);check('Second property v2 accepted',s==200,d)
 auth={'Authorization':'Bearer '+token}
 s,d=http('report-snapshot',json.dumps({'from':start,'to':today,'properties':[prop,other]}).encode(),{**auth,'Content-Type':'application/json'});check('Freeze mixed-version report',s==200,d.get('message'))
 report_id=d['data']['reportId'];s,d=http('export&format=json&id='+report_id,headers=auth);check('Mixed payroll explicitly unavailable',s==200 and d['report']['integrityStatus'] in ['INCOMPLETE','FAIL'] and 'payrollExpense' not in d['report']['currencies'][v3['currency']]['metricsMinor'])
 newother=json.loads(json.dumps(v3));newother['propertyId']=other;rehash(newother);s,d=push(newother);check('Second property upgrades to v3',s==200,d)
 s,d=http('report-snapshot',json.dumps({'from':start,'to':today,'properties':[prop,other]}).encode(),{**auth,'Content-Type':'application/json'});check('Freeze complete v3 report',s==200,d.get('message'));new_id=d['data']['reportId']
 s,d=http('export&format=json&id='+new_id,headers=auth);check('HQ payroll equals both property source journals',s==200 and d['report']['currencies'][v3['currency']]['metricsMinor']['payrollExpense']==str(2*int(m['payrollExpense'])))
 s,d=http('export&format=json&id='+report_id,headers=auth);check('Earlier frozen report remains immutable',s==200 and 'payrollExpense' not in d['report']['currencies'][v3['currency']]['metricsMinor'])
finally:p.terminate();p.wait(timeout=10);log.close()
print('HQ v3 integration assertions:',len(results))
