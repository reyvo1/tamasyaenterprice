from runtime_tools import mysql_binary, mysqldump_binary, background_process_options, python_command
from pathlib import Path
import json,os,secrets,subprocess,socket,time,urllib.request,urllib.error,datetime,re
b=Path(__file__).resolve().parent;root=b.parent/'enterprise';private=b.parent/'simulation-transfer';private.mkdir(exist_ok=True)
mysql=mysql_binary();args=[mysql,'--defaults-file='+str(b/'client.ini'),'--batch','--skip-column-names']
def sql(q,db=None):
 r=subprocess.run(args+([db] if db else []),input=q,capture_output=True,text=True,encoding='utf-8');r.check_returncode();return r.stdout.strip()
port,datadir=sql('SELECT @@port,@@datadir').split('\t');assert port=='23384' and Path(datadir).resolve()==(b/'mysql-data').resolve()
backup=json.loads((b/'logs/backup-result.json').read_text(encoding='utf-8'));dump=(b/'backups'/backup['file']).read_text(encoding='utf-8');assert not re.search(r'^USE\s|^CREATE DATABASE',dump,re.M|re.I)
baseenv=json.loads((b/'environment.json').read_text(encoding='utf-8'));creds=json.loads((b/'credentials.json').read_text(encoding='utf-8'));suffix=secrets.token_hex(4);key=secrets.token_hex(32);nodes={};children=[];logs=[];results=[]
def check(name,ok,detail=None):
 results.append({'name':name,'pass':bool(ok),'detail':detail});(b/'growth-interproperty-results.json').write_text(json.dumps(results,indent=2),encoding='utf-8');print('PASS' if ok else 'FAIL',name,flush=True)
 if not ok:raise AssertionError(str(detail))
def request(node,action,data=None,method=None,auth=True):
 n=nodes[node];headers={'Origin':n['url'],'Content-Type':'application/json','X-Device-ID':'transfer-fixture-'+node,'X-Device-Name':'Transfer fixture'}
 if auth:headers['Authorization']='Bearer '+n['token']
 if data is not None:headers['X-Tamasya-Operation-ID']=data.get('operationId','transfer_'+secrets.token_hex(12))
 req=urllib.request.Request(n['url']+'/api.php?action='+action,headers=headers,data=json.dumps(data).encode() if data is not None else None,method=method or ('POST' if data is not None else 'GET'))
 try:r=urllib.request.urlopen(req,timeout=90)
 except urllib.error.HTTPError as x:r=x
 raw=r.read().decode('utf-8-sig')
 try:d=json.loads(raw)
 except ValueError:d={'raw':raw[:600]}
 return r.status,d
def post(node,command,data,expected=True,op=None):
 s,d=request(node,'interproperty-transfer',{'command':command,**data,'operationId':op or 'ipt_'+secrets.token_hex(12)})
 check(node+' '+command+(' accepted' if expected else ' rejected'),(s==200 and d.get('success') is True)==expected and (expected or s in [400,403,409,422,500]),{'status':s,'error':d.get('error',d.get('message'))});return d
def snapshot(node):
 today=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).date().isoformat();s,d=request(node,'multi-property&command=snapshot-v3&from='+today[:7]+'-01&to='+today);check(node+' canonical snapshot',s==200 and d.get('success') is True,d.get('error'));return d['data']['metricsMinor']
try:
 for node,port,peer in [('a',28192,'b'),('b',28193,'a')]:
  try:
   with socket.create_connection(('127.0.0.1',port),timeout=.2):raise RuntimeError('Port already in use')
  except OSError:pass
  db='tamasya_transfer_test_'+node+'_'+suffix;prop='transfer-hotel-'+node;code='TRANSFER'+node.upper()
  sql('CREATE DATABASE `'+db+'` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;USE `'+db+'`;\n'+dump)
  sql("GRANT ALL ON `"+db+"`.* TO 'tamasya_sim'@'127.0.0.1'")
  sql("UPDATE property_settings SET company_id='transfer-fixture-company',property_id='"+prop+"',property_code='"+code+"'",db)
  credential=private/(node+'-'+suffix+'-db.php');credential.write_text("<?php return ['host'=>'127.0.0.1','port'=>23384,'name'=>'"+db+"','user'=>'tamasya_sim','pass'=>'"+creds['password']+"'];",encoding='utf-8')
  keys=private/(node+'-'+suffix+'-keys.json');keys.write_text(json.dumps({'companyId':'transfer-fixture-company','propertyId':prop,'peers':{'transfer-hotel-'+peer:{'enabled':True,'secret':key}}}),encoding='utf-8')
  url='http://127.0.0.1:'+str(port);env={**baseenv,'APP_CREDENTIALS_FILE':str(credential),'APP_EXPECTED_DB_NAME':db,'APP_URL':url,'APP_ALLOWED_ORIGINS':url,'TAMASYA_PROPERTY_ID':prop,'TAMASYA_PROPERTY_CODE':code,'TAMASYA_COMPANY_ID':'transfer-fixture-company','TAMASYA_NODE_ID':'transfer-'+node,'TAMASYA_INTERPROPERTY_TRANSFER_ENABLED':'1','TAMASYA_INTERPROPERTY_KEYS_FILE':str(keys),'TAMASYA_HQ_BRIDGE_ENABLED':'0','TAMASYA_ENTERPRISE_CRM_CAMPAIGN_SEND_ENABLED':'0'}
  (private/(node+'-'+suffix+'-env.json')).write_text(json.dumps(env),encoding='utf-8')
  r=subprocess.run(['php',str(root/'optional_modules_install.php'),'--apply','--target=all','--backup-confirmed='+backup['file']],env={**os.environ,**env},capture_output=True,text=True,encoding='utf-8');check(node+' installs full optional schema',r.returncode==0,r.stdout[-600:] if r.returncode else None)
  log=open(private/(node+'-'+suffix+'-php.log'),'ab');logs.append(log);p=subprocess.Popen(['php','-S','127.0.0.1:'+str(port),'-t',str(root)],env={**os.environ,**env},stdout=log,stderr=log,**background_process_options());children.append(p);nodes[node]={'db':db,'url':url,'env':env}
  for _ in range(50):
   try:
    with socket.create_connection(('127.0.0.1',port),timeout=.2):break
   except OSError:time.sleep(.1)
  s,d=request(node,'login',{'username':env['APP_BOOTSTRAP_ADMIN_USERNAME'],'password':env['APP_BOOTSTRAP_ADMIN_PASSWORD']},auth=False);check(node+' login',s==200 and bool(d.get('token')),{'status':s,'error':d.get('error')});nodes[node]['token']=d['token']
  nodes[node]['bank']=sql("SELECT id FROM bank_accounts WHERE type='bank' AND isActive=1 ORDER BY id LIMIT 1",db);assert nodes[node]['bank']
 before={node:snapshot(node) for node in nodes}
 outdata={'destinationPropertyId':'transfer-hotel-b','amount':123.45,'reference':'BANK-SOURCE-'+suffix,'bankAccountId':nodes['a']['bank'],'confirmation':'DANA SUDAH DIKIRIM'}
 post('a','create',{**outdata,'destinationPropertyId':'foreign-property'},False)
 op='transfer_source_'+suffix;out=post('a','create',outdata,op=op)['data'];order=out['order'];transfer=out['id']
 post('a','create',outdata,op=op);post('a','create',outdata,False)
 check('Source posts one canonical outgoing leg',sql("SELECT COUNT(*) FROM transactions WHERE sourceEntity='interproperty_transfer' AND sourceEntityId='"+transfer+"'",nodes['a']['db'])=='1')
 check('Source awaits receipt rather than assuming destination success',out['status']=='awaiting_receipt')
 incoming={'document':order,'reference':'BANK-RECEIPT-'+suffix,'bankAccountId':nodes['b']['bank'],'confirmation':'DANA SUDAH DITERIMA'}
 bad=json.loads(json.dumps(order));bad['payload']['amountMinor']='12346';post('b','receive',{**incoming,'document':bad},False)
 post('a','receive',{**incoming,'bankAccountId':nodes['a']['bank']},False)
 received=post('b','receive',incoming)['data'];post('b','receive',incoming)
 check('Destination posts exactly one canonical incoming leg',sql("SELECT COUNT(*) FROM transactions WHERE sourceEntity='interproperty_transfer' AND sourceEntityId='"+transfer+"'",nodes['b']['db'])=='1')
 receipt=received['receipt'];bad=json.loads(json.dumps(receipt));bad['payload']['orderHash']='0'*64;post('a','reconcile',{'document':bad},False)
 post('a','reconcile',{'document':receipt});post('a','reconcile',{'document':receipt})
 check('Source reconciles to signed destination receipt',sql("SELECT status FROM growth_interproperty_transfers WHERE id='"+transfer+"'",nodes['a']['db'])=='reconciled')
 after={node:snapshot(node) for node in nodes}
 for node,diff in [('a',-12345),('b',12345)]:
  check(node+' bank movement matches transfer leg',int(after[node]['bankMovement'])-int(before[node]['bankMovement'])==diff)
  check(node+' transfer does not create revenue expense or tax',all(after[node][k]==before[node][k] for k in ['revenue','expense','profit','taxAccrued','taxPaid']))
  check(node+' journals remain balanced',sql('SELECT COUNT(*) FROM (SELECT journal_entry_id FROM journal_lines GROUP BY journal_entry_id HAVING ABS(SUM(debit)-SUM(credit))>0.001) x',nodes[node]['db'])=='0')
  account='1198' if node=='a' else '2198';check(node+' interproperty balance recorded',sql("SELECT COUNT(*) FROM journal_lines l JOIN journal_entries e ON e.id=l.journal_entry_id JOIN transactions t ON t.id=e.transaction_id WHERE t.sourceEntityId='"+transfer+"' AND l.account_code='"+account+"'",nodes[node]['db'])=='1')
 check('Company net bank movement is zero',sum(int(after[n]['bankMovement'])-int(before[n]['bankMovement']) for n in nodes)==0)
finally:
 for p in reversed(children):p.terminate();p.wait(timeout=10)
 for log in logs:log.close()
print('Interproperty integration assertions:',len(results))
