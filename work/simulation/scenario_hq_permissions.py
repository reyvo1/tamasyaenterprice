from runtime_tools import mysql_binary, mysqldump_binary, background_process_options, python_command
from client import request,base
import json,secrets,subprocess,datetime,uuid
mysql=mysql_binary()
def run(file,sql):return subprocess.run([mysql,'--defaults-file='+str(file),'--batch','--raw','--skip-column-names'],input=sql,capture_output=True,text=True)
r=run(base/'client.ini','SELECT @@port');assert r.returncode==0 and r.stdout.strip()=='23384'
username='tamasya_hq_limited_sim';existing=json.loads((base/'hq-config.json').read_text());password=existing['password'] if existing['username']==username else secrets.token_hex(32)
sql="CREATE USER IF NOT EXISTS '"+username+"'@'127.0.0.1' IDENTIFIED BY '"+password+"';"
for table in ['hq_property_locks','hq_snapshots','hq_receipts','hq_nonces']:
 sql+="GRANT SELECT,INSERT ON tamasya_hq_h1_sim."+table+" TO '"+username+"'@'127.0.0.1';"
sql+="GRANT SELECT,INSERT,UPDATE ON tamasya_hq_h1_sim.hq_heads TO '"+username+"'@'127.0.0.1'; GRANT UPDATE ON tamasya_hq_h1_sim.hq_property_locks TO '"+username+"'@'127.0.0.1';"
r=run(base/'client.ini',sql);r.check_returncode()
config=json.loads((base/'hq-config.json').read_text());config['username']=username;config['password']=password;(base/'hq-config.json').write_text(json.dumps(config))
ini=base/'hq-limited-client.ini';ini.write_text('[client]\nhost=127.0.0.1\nport=23384\nuser='+username+'\npassword='+password+'\n')
results=[]
def check(name,ok):
 results.append({'test':name,'pass':bool(ok)});print('PASS' if ok else 'FAIL',name,flush=True)
 if not ok:raise AssertionError(name)
check('HQ runtime can read its aggregate snapshots',run(ini,'SELECT COUNT(*) FROM tamasya_hq_h1_sim.hq_snapshots').returncode==0)
for name,sql in [('HQ cannot read hotel ledger','SELECT * FROM tamasya_sim.transactions LIMIT 0'),('HQ cannot update hotel ledger','UPDATE tamasya_sim.transactions SET amount=amount WHERE 1=0'),('HQ cannot overwrite immutable snapshot','UPDATE tamasya_hq_h1_sim.hq_snapshots SET body=body WHERE 1=0'),('HQ cannot delete receipt','DELETE FROM tamasya_hq_h1_sim.hq_receipts WHERE 1=0')]:
 r=run(ini,sql);check(name,r.returncode!=0 and '1142' in r.stderr)
now=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).date();op='limited_'+uuid.uuid4().hex
st,b=request('multi-property','POST',{'command':'queue-snapshot','from':str(now.replace(day=1)),'to':str(now),'operationId':op});check('Aggregate enqueue for limited HQ account',st==202)
st,b=request('multi-property','POST',{'command':'deliver-snapshot','operationId':op});check('Least privilege HQ user can durably receive snapshot',st==200 and b.get('status')=='acknowledged')
(base/'logs/hq-permission-results.json').write_text(json.dumps(results,indent=2));print('HQ PERMISSION CHECKS',len(results))
