from runtime_tools import mysql_binary, mysqldump_binary, background_process_options, python_command
from pathlib import Path
import os,json,subprocess,secrets,socket,time,shutil,re
b=Path(__file__).resolve().parent;shutil.copytree(b.parent/'enterprise',b/'site',dirs_exist_ok=True)
mysql=mysql_binary();args=[mysql,'--defaults-file='+str(b/'client.ini'),'--batch','--skip-column-names']
def sql(statement):
 r=subprocess.run(args,input=statement,capture_output=True,text=True,encoding='utf-8');r.check_returncode();return r.stdout.strip()
port,datadir=sql('SELECT @@port,@@datadir').split('\t');assert port=='33384' and Path(datadir).resolve()==(b/'mysql-data').resolve()
backup=json.loads((b/'logs/backup-result.json').read_text());dump=(b/'backups'/backup['file']).read_text(encoding='utf-8');assert not re.search(r'^USE\s|^CREATE DATABASE',dump,re.M|re.I)
growthenv=json.loads((b.parent/'simulation-growth/environment.json').read_text(encoding='utf-8'));growthdb=growthenv['APP_EXPECTED_DB_NAME'];assert re.fullmatch(r'tamasya_growth_test_[a-f0-9]+',growthdb)
r=subprocess.run([mysqldump_binary(),'--defaults-file='+str(b/'client.ini'),'--no-tablespaces','--single-transaction',growthdb],capture_output=True,text=True,encoding='utf-8');r.check_returncode();dump=r.stdout
assert not re.search(r'^USE\s|^CREATE DATABASE',dump,re.M|re.I)
suffix=secrets.token_hex(4);secret=secrets.token_hex(32);creds=json.loads((b/'credentials.json').read_text());baseenv={**os.environ,**json.loads((b/'environment.json').read_text())};children=[];envs={};results=[]
def check(name,ok,detail=None):
 results.append({'name':name,'pass':bool(ok),'detail':detail});(b/'ha-pair-results.json').write_text(json.dumps(results,indent=2))
 if not ok:raise AssertionError(name+' '+str(detail))
def run(node,command):
 r=subprocess.run(['php',str(b/'ha_command.php'),command],env=envs[node],capture_output=True,text=True,encoding='utf-8',timeout=120)
 (b/'logs'/('ha-'+node+'-'+command+'.log')).write_text(r.stdout+r.stderr,encoding='utf-8')
 if r.returncode:raise RuntimeError((r.stdout+r.stderr)[-1800:])
 return json.loads(r.stdout)
try:
 for node,port,peerport,peer in [('a',38190,38191,'b'),('b',38191,38190,'a')]:
  name='tamasya_ha_test_'+node+'_'+suffix
  sql('CREATE DATABASE `'+name+'` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci; USE `'+name+'`;\n'+dump)
  sql("GRANT ALL ON `"+name+"`.* TO 'tamasya_sim'@'127.0.0.1';")
  credential=b/('ha-'+node+'-credentials.php');credential.write_text("<?php return ['host'=>'127.0.0.1','port'=>33384,'name'=>'"+name+"','user'=>'tamasya_sim','pass'=>'"+creds['password']+"'];")
  env={**baseenv,'APP_URL':f'http://127.0.0.1:{port}','APP_CREDENTIALS_FILE':str(credential),'APP_EXPECTED_DB_NAME':name,'NODE_CLUSTER_ENABLED':'1','TAMASYA_NODE_MODE':'flexible','NODE_SYNC_ENABLED':'1','TAMASYA_NODE_ID':'ha-'+node,'TAMASYA_CLUSTER_ID':'ha-test-'+suffix,'TAMASYA_NODE_ROLE':'online_primary' if node=='a' else 'local_backup','TAMASYA_NODE_INITIAL_ROLE':'primary' if node=='a' else 'standby','NODE_CLUSTER_PEER_ID':'ha-'+peer,'NODE_CLUSTER_PEER_URL':f'http://127.0.0.1:{peerport}','NODE_CLUSTER_PUBLIC_URL':f'http://127.0.0.1:{port}','NODE_SYNC_PRIMARY_URL':'http://127.0.0.1:38190','NODE_SYNC_SHARED_SECRET':secret,'NODE_CLUSTER_PROBE_BEFORE_WRITE':'0'}
  env.update({'TAMASYA_NODE_KIND':'local','TAMASYA_ALLOWED_NODE_IDS':'ha-'+peer,'NODE_SYNC_ALLOW_HTTP_LOCAL':'1'})
  env['TAMASYA_COMPANY_ID']='growth-fixture-company'
  envs[node]=env;(b/('ha-'+node+'-environment.json')).write_text(json.dumps({k:v for k,v in env.items() if k.startswith(('APP_','TAMASYA_','NODE_'))}))
  log=open(b/'logs'/('ha-server-'+node+'.log'),'ab');p=subprocess.Popen(['php','-S',f'127.0.0.1:{port}','-t',str(b/'site')],env=env,stdout=log,stderr=log,**background_process_options());children.append(p)
  for _ in range(50):
   try:
    with socket.create_connection(('127.0.0.1',port),timeout=.2):break
   except OSError:time.sleep(.1)
 check('Primary starts as only writer',run('a','status')['isPrimaryWriter'] is True)
 check('Standby starts without write authority',run('b','status')['isPrimaryWriter'] is False)
 run('b','adopt')
 # Intentional fixture differences prove copy and deletion, not just equal clones.
 sql("INSERT INTO `tamasya_ha_test_a_"+suffix+"`.public_room_types(id,slug,name) VALUES('ha-source','ha-source','Primary mirror fixture'); INSERT INTO `tamasya_ha_test_b_"+suffix+"`.public_room_types(id,slug,name) VALUES('ha-stale','ha-stale','Stale standby fixture');")
 for node,fixture in [('a','source'),('b','stale')]:
  sql("INSERT INTO `tamasya_ha_test_"+node+'_'+suffix+"`.growth_rate_plans(id,code,name,currency,base_rate) VALUES('ha-"+fixture+"','HA-"+fixture+"','HA optional mirror fixture','IDR',123.45)")
 # Canonical mirror handles all tables and retained local-only identity metadata.
 r=subprocess.run(['php',str(b/'site/node_sync_agent.php')],env=envs['b'],capture_output=True,text=True,encoding='utf-8',timeout=180);(b/'logs/ha-mirror.log').write_text(r.stdout+r.stderr,encoding='utf-8');check('Standby canonical mirror completes',r.returncode==0,(r.stdout+r.stderr)[-700:])
 mirror=json.loads(r.stdout)['mirror'];check('Mirror actually transfers tables and rows',not mirror['skipped'] and mirror['tables']>0 and mirror['rows']>0)
 check('Standby receives source and removes stale fixture',sql("SELECT GROUP_CONCAT(id ORDER BY id) FROM `tamasya_ha_test_b_"+suffix+"`.public_room_types WHERE id IN ('ha-source','ha-stale')")=='ha-source')
 check('Optional rate data copied and stale standby data removed',sql("SELECT GROUP_CONCAT(id ORDER BY id) FROM `tamasya_ha_test_b_"+suffix+"`.growth_rate_plans WHERE id IN ('ha-source','ha-stale')")=='ha-source')
 check('Mirror preserves absolute transaction timestamps across host timezones',sql("SELECT MAX(createdAt) FROM `tamasya_ha_test_a_"+suffix+"`.transactions")==sql("SELECT MAX(createdAt) FROM `tamasya_ha_test_b_"+suffix+"`.transactions"))
 for table in ['growth_folios','growth_folio_charge_allocations','growth_crm_campaign_recipients','growth_supplier_invoice_payments','growth_interproperty_transfers']:
  ca=int(sql('SELECT COUNT(*) FROM `tamasya_ha_test_a_'+suffix+'`.'+table));cb=int(sql('SELECT COUNT(*) FROM `tamasya_ha_test_b_'+suffix+'`.'+table))
  check('Optional mirror count '+table,ca==cb and (ca>0 or table=='growth_interproperty_transfers'))
 a=run('a','checksum');bb=run('b','checksum');check('Two databases agree before promotion',a['sha256']==bb['sha256'])
 switched=run('a','switch');check('Planned switchover completes',switched.get('success') is True)
 check('Old primary rejects new mutations',run('a','guard')['blocked'] is True)
 check('New primary accepts authority guard',run('b','guard')['blocked'] is False)
 old=run('a','status');new=run('b','status');check('Exactly one writer and same epoch',not old['isPrimaryWriter'] and new['isPrimaryWriter'] and old['leadershipEpoch']==new['leadershipEpoch'])
finally:
 for p in reversed(children):p.terminate();p.wait(timeout=10)
print('HA pair assertions passed:',len(results))
