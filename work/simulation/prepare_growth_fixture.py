from pathlib import Path
import os,json,subprocess,secrets,re,shutil,socket,time
from runtime_tools import background_process_options,mysql_binary,mysql_datadir
b=Path(__file__).resolve().parent;g=b.parent/'simulation-growth';g.mkdir(exist_ok=True);(g/'logs').mkdir(exist_ok=True)
args=[mysql_binary(),'--defaults-file='+str(b/'client.ini'),'--batch','--skip-column-names']
def sql(statement):
 r=subprocess.run(args,input=statement,capture_output=True,text=True,encoding='utf-8');r.check_returncode();return r.stdout.strip()
port,datadir=sql('SELECT @@port,@@datadir').split('\t');assert port=='33384' and Path(datadir).resolve()==mysql_datadir(b/'mysql-data')
try:
 with socket.create_connection(('127.0.0.1',38189),timeout=.3):raise RuntimeError('Growth fixture already listening; reuse it rather than replacing its identity.')
except OSError:pass
backup=json.loads((b/'logs/backup-result.json').read_text(encoding='utf-8'));dump=(b/'backups'/backup['file']).read_text(encoding='utf-8');assert not re.search(r'^USE\s|^CREATE DATABASE',dump,re.M|re.I)
name='tamasya_growth_test_'+secrets.token_hex(4)
sql('CREATE DATABASE `'+name+'` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci; USE `'+name+'`;\n'+dump)
sql("GRANT ALL ON `"+name+"`.* TO 'tamasya_sim'@'127.0.0.1';")
creds=json.loads((b/'credentials.json').read_text(encoding='utf-8'));credential=g/'db_credentials.php'
credential.write_text("<?php return ['host'=>'127.0.0.1','port'=>33384,'name'=>'"+name+"','user'=>'tamasya_sim','pass'=>'"+creds['password']+"'];",encoding='utf-8')
e=json.loads((b/'environment.json').read_text(encoding='utf-8'));e.update({'APP_CREDENTIALS_FILE':str(credential),'APP_EXPECTED_DB_NAME':name,'APP_URL':'http://127.0.0.1:38189','APP_ALLOWED_ORIGINS':'http://127.0.0.1:38189','TAMASYA_GROWTH_SUITE_ENABLED':'1','TAMASYA_ENTERPRISE_COMPLETION_ENABLED':'1','TAMASYA_ENTERPRISE_PROVIDER_ADAPTERS_ENABLED':'1','TAMASYA_ENTERPRISE_CRM_CAMPAIGN_SEND_ENABLED':'0','TAMASYA_HQ_BRIDGE_ENABLED':'0','BACKUP_DIR':str(g/'backups')})
e['TAMASYA_COMPANY_ID']='growth-fixture-company';e['TAMASYA_TEST_BRIDGE_KEY']=secrets.token_urlsafe(48)
sql("UPDATE `"+name+"`.property_settings SET company_id='growth-fixture-company'")
for key in ['KPI','RATE_MANAGER','GROUP_CORPORATE','ADVANCED_FOLIO','PROCUREMENT','CHANNEL_FOUNDATION','PAYMENT_FOUNDATION']:e['TAMASYA_GROWTH_'+key+'_ENABLED']='1'
(g/'environment.json').write_text(json.dumps(e),encoding='utf-8');shutil.copytree(b.parent/'enterprise',g/'site',dirs_exist_ok=True)
env={**os.environ,**e};r=subprocess.run(['php',str(g/'site/optional_modules_install.php'),'--apply','--target=all','--backup-confirmed='+backup['file']],env=env,capture_output=True,text=True,encoding='utf-8');(g/'logs/install.txt').write_text(r.stdout+r.stderr,encoding='utf-8');r.check_returncode()
with open(g/'logs/php-server.log','ab') as log:p=subprocess.Popen(['php','-S','127.0.0.1:38189','-t',str(g/'site')],env=env,stdout=log,stderr=log,**background_process_options())
(g/'php.pid').write_text(str(p.pid));print('Dedicated Growth fixture installed:',name,'on localhost:38189; original databases unchanged.')
