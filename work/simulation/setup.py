from runtime_tools import mysql_binary, mysqldump_binary, background_process_options, python_command
from pathlib import Path
import os,json,secrets,shutil,subprocess
base=Path(__file__).resolve().parent
site=base/'site'
test_source=Path(os.environ.get('TAMASYA_TEST_SOURCE',str(base.parent/'audit'))).resolve()
assert test_source in [(base.parent/name).resolve() for name in ['audit','hybrid','enterprise','enterprise-release-check']]
shutil.copytree(test_source,site,dirs_exist_ok=True)
creds=json.loads((base/'credentials.json').read_text())
credential_file=base/'db_credentials.php'
credential_file.write_text('<?php\nreturn '+"['host'=>'127.0.0.1','port'=>23384,'name'=>'tamasya_sim','user'=>'tamasya_sim','pass'=>'"+creds['password']+"'];\n",encoding='utf-8')
env={
 'APP_ENV':'staging','APP_DEBUG':'0','APP_TIMEZONE':'Asia/Makassar',
 'APP_URL':'http://127.0.0.1:28184','APP_ALLOWED_ORIGINS':'http://127.0.0.1:28184',
 'APP_ALLOWED_HOSTS':'127.0.0.1','APP_ENFORCE_ALLOWED_HOSTS':'1',
 'APP_CREDENTIALS_FILE':credential_file.as_posix(),'APP_EXPECTED_DB_NAME':'tamasya_sim','APP_REQUIRE_EXPECTED_DB_NAME':'1',
 'APP_ENCRYPTION_KEY':secrets.token_hex(32),'SECURITY_EVENT_HASH_KEY':secrets.token_hex(32),
 'APP_BOOTSTRAP_ADMIN_USERNAME':'sim_admin','APP_BOOTSTRAP_ADMIN_PASSWORD':secrets.token_hex(16),
 'APP_BOOTSTRAP_ADMIN_NAME':'Simulation Administrator','TAMASYA_PROPERTY_NAME':'SIMULATION HOTEL',
 'TAMASYA_PROPERTY_ID':'simulation-hotel','TAMASYA_PROPERTY_CODE':'SIMHOTEL','TAMASYA_PROPERTY_CURRENCY':'IDR',
 'TAMASYA_PROPERTY_COUNTRY':'ID','TAMASYA_PROPERTY_LOCALE':'id-ID','TAMASYA_NODE_ID':'sim-primary',
 'TAMASYA_NODE_ROLE':'online_primary','NODE_SYNC_ENABLED':'0','NODE_CLUSTER_ENABLED':'0',
 'BACKUP_DIR':(base/'backups').as_posix(),'CRON_SECRET':secrets.token_hex(32),
 'PUBLIC_HELP_CHAT_AI_ENABLED':'0','INTERNAL_STAFF_HELP_CHAT_ENABLED':'0',
 'TAMASYA_GROWTH_SUITE_ENABLED':'0','TAMASYA_ENTERPRISE_COMPLETION_ENABLED':'0',
 'TAMASYA_MULTI_PROPERTY_FOUNDATION_ENABLED':'0','TELEGRAM_SIMULATION_ENABLED':'0',
}
(base/'backups').mkdir(exist_ok=True)
(base/'environment.json').write_text(json.dumps(env),encoding='utf-8')
runtime=os.environ.copy();runtime.update(env)
r=subprocess.run(['php',str(site/'first_install.php')],env=runtime,capture_output=True,text=True,encoding='utf-8')
(base/'logs/first-install.txt').write_text(r.stdout+r.stderr,encoding='utf-8')
print('First install:',r.returncode,r.stdout[:3500],r.stderr[:1000])
if r.returncode:raise SystemExit(r.returncode)
log=open(base/'logs/php-server.log','ab')
p=subprocess.Popen(['php','-S','127.0.0.1:28184','-t',str(site)],env=runtime,stdout=log,stderr=log,**background_process_options())
(base/'php.pid').write_text(str(p.pid));print('PHP test server started',p.pid)
