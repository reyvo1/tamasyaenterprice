from runtime_tools import mysql_binary, mysqldump_binary, background_process_options, python_command
from pathlib import Path
import os,json,subprocess,shutil,secrets
b=Path(__file__).resolve().parent
mysql=mysql_binary()
def root(sql):
 p=subprocess.run([mysql,'--defaults-file='+str(b/'client.ini'),'--batch','--raw','--skip-column-names'],input=sql,text=True,capture_output=True);p.check_returncode();return p.stdout.strip()
assert root('SELECT @@port')=='33384'
assert Path(root('SELECT @@datadir')).resolve()==(b/'mysql-data').resolve()
root('CREATE DATABASE IF NOT EXISTS tamasya_hq_h1_sim CHARACTER SET utf8mb4 COLLATE utf8mb4_bin; GRANT ALL ON tamasya_hq_h1_sim.* TO \'tamasya_sim\'@\'127.0.0.1\';')
shutil.copytree(b.parent/'enterprise',b/'site',dirs_exist_ok=True)
c=json.loads((b/'credentials.json').read_text())
configfile=b/'hq-config.json'
if not configfile.exists():
 secret=secrets.token_hex(32); viewer=secrets.token_urlsafe(36)
 import hashlib
 config={'dsn':'mysql:host=127.0.0.1;port=33384;dbname=tamasya_hq_h1_sim;charset=utf8mb4','username':c['user'],'password':c['password'],'properties':{'sim-company':{'simulation-hotel':{'enabled':True,'secret':secret},'hotel-b':{'enabled':True,'secret':secrets.token_hex(32)},'hotel-c':{'enabled':True,'secret':secrets.token_hex(32)}},'other-company':{'hotel-z':{'enabled':True,'secret':secrets.token_hex(32)}}},'viewers':[{'enabled':True,'tokenSha256':hashlib.sha256(viewer.encode()).hexdigest(),'companyId':'sim-company','propertyIds':['simulation-hotel','hotel-b','hotel-c']}]}
 configfile.write_text(json.dumps(config));(b/'hq-test-token').write_text(viewer)
config=json.loads(configfile.read_text())
e=os.environ.copy();e.update(json.loads((b/'environment.json').read_text()));e['TAMASYA_HQ_CONFIG_FILE']=str(configfile)
e['TAMASYA_COMPANY_ID']='sim-company';e['TAMASYA_MULTI_PROPERTY_FOUNDATION_ENABLED']='1';e['TAMASYA_HQ_BRIDGE_ENABLED']='1'
e['TAMASYA_HQ_HUB_URL']='https://localhost:38186';e['TAMASYA_HQ_SHARED_SECRET']=config['properties']['sim-company']['simulation-hotel']['secret']
outbox=b/'hybrid-outbox';outbox.mkdir(exist_ok=True);e['TAMASYA_HYBRID_OUTBOX_DIR']=str(outbox)
root("UPDATE tamasya_sim.property_settings SET company_id='sim-company';")
if root('SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=\'tamasya_hq_h1_sim\'')=='0':
 p=subprocess.run(['php',str(b/'site/hq/install.php'),'--apply-empty-hq-database'],env=e,capture_output=True,text=True);print(p.stdout,p.stderr);p.check_returncode()
for port,folder,pidfile in [(38184,b/'site','php.pid'),(38185,b/'site/hq','hq-php.pid')]:
 f=open(b/f'logs/hybrid-{port}.log','ab');p=subprocess.Popen(['php','-d','curl.cainfo='+str(b/'tls-ca.pem'),'-d','openssl.cafile='+str(b/'tls-ca.pem'),'-S',f'127.0.0.1:{port}','-t',str(folder)],env=e,stdout=f,stderr=f,**background_process_options())
 (b/pidfile).write_text(str(p.pid));print('Started PHP staging',port,p.pid)
(b/'hybrid-environment.json').write_text(json.dumps({k:v for k,v in e.items() if k.startswith(('TAMASYA_','APP_'))}))
