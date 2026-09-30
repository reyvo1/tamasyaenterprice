from runtime_tools import mysql_binary, mysqldump_binary, background_process_options, python_command
from pathlib import Path
import subprocess,os,json,shutil,secrets
b=Path(__file__).resolve().parent
shutil.copytree(b.parent/'enterprise',b/'site',dirs_exist_ok=True)
e=os.environ.copy();e.update(json.loads((b/'hybrid-environment.json').read_text()))
config=json.loads((b/'hq-config.json').read_text());config['realtime']={'enabled':True,'secret':secrets.token_hex(32),'url':'http://127.0.0.1:28200/events'}
(b/'hq-config.json').write_text(json.dumps(config));e['TAMASYA_HQ_CONFIG_FILE']=str(b/'hq-config.json')
c=json.loads((b/'credentials.json').read_text());installer={**config,'username':c['user'],'password':c['password']};(b/'hq-installer.json').write_text(json.dumps(installer));installenv={**e,'TAMASYA_HQ_CONFIG_FILE':str(b/'hq-installer.json')}
r=subprocess.run(['php',str(b/'site/hq/upgrade_h2.php'),'--apply-hq-only'],env=installenv,capture_output=True,text=True);print(r.stdout,r.stderr);r.check_returncode()
mysql=mysql_binary()
r=subprocess.run([mysql,'--defaults-file='+str(b/'client.ini')],input="GRANT SELECT,INSERT ON tamasya_hq_h1_sim.hq_reports TO 'tamasya_hq_limited_sim'@'127.0.0.1'; GRANT SELECT,INSERT,UPDATE ON tamasya_hq_h1_sim.hq_delivery_jobs TO 'tamasya_hq_limited_sim'@'127.0.0.1';",capture_output=True,text=True);r.check_returncode()
for port,folder,pidfile in [(28184,b/'site','php.pid'),(28185,b/'site/hq','hq-php.pid')]:
 f=open(b/f'logs/enterprise-{port}.log','ab');p=subprocess.Popen(['php','-d','curl.cainfo='+str(b/'tls-ca.pem'),'-d','openssl.cafile='+str(b/'tls-ca.pem'),'-S',f'127.0.0.1:{port}','-t',str(folder)],env=e,stdout=f,stderr=f,**background_process_options());(b/pidfile).write_text(str(p.pid));print('PHP started',port,p.pid)
rt={'localTest':True,'host':'127.0.0.1','port':28200,'pollMs':500,'allowedOrigins':['http://127.0.0.1:28185'],'tenants':{'sim-company':{'enabled':True,'secret':config['realtime']['secret'],'propertyIds':config['viewers'][0]['propertyIds'],'readToken':(b/'hq-test-token').read_text(),'apiUrl':'http://127.0.0.1:28185/api.php'}}}
(b/'realtime-config.json').write_text(json.dumps(rt));ne={**os.environ,'TAMASYA_REALTIME_CONFIG_FILE':str(b/'realtime-config.json')};f=open(b/'logs/realtime.log','ab');p=subprocess.Popen(['node',str(b/'site/services/realtime/server.mjs')],env=ne,stdout=f,stderr=f,**background_process_options());(b/'realtime.pid').write_text(str(p.pid))
(b/'enterprise-environment.json').write_text(json.dumps({k:v for k,v in e.items() if k.startswith(('APP_','TAMASYA_'))}))
r=subprocess.run(['php',str(b/'site/service_worker.php'),'health'],env=e,capture_output=True,text=True);(b/'logs/worker-health.txt').write_text(r.stdout+r.stderr,encoding='utf8');print('Worker health exit',r.returncode,'output length',len(r.stdout),r.stderr[:600])
