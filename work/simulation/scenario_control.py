from runtime_tools import mysql_binary, mysqldump_binary, background_process_options, python_command
from pathlib import Path
import json,os,subprocess,shutil,secrets,urllib.request,urllib.error,hashlib
b=Path(__file__).resolve().parent
shutil.copytree(b.parent/'enterprise',b/'site',dirs_exist_ok=True)
env={**os.environ,**json.loads((b/'enterprise-environment.json').read_text(encoding='utf-8'))}
original=(b/'hq-config.json').read_text(encoding='utf-8');config=json.loads(original)
installer=json.loads((b/'hq-installer.json').read_text(encoding='utf-8'))
env['TAMASYA_HQ_CONFIG_FILE']=str(b/'hq-installer.json')
subprocess.run(['php',str(b/'site/hq/upgrade_h2.php'),'--apply-hq-only'],env=env,check=True)
mysql=mysql_binary()
sql="SELECT @@port;"+''.join(f"GRANT SELECT,INSERT,UPDATE ON tamasya_hq_h1_sim.{t} TO 'tamasya_hq_limited_sim'@'127.0.0.1';" for t in ['hq_companies','hq_properties','hq_principals'])+"GRANT SELECT,INSERT ON tamasya_hq_h1_sim.hq_control_audit TO 'tamasya_hq_limited_sim'@'127.0.0.1';"
r=subprocess.run([mysql,'--defaults-file='+str(b/'client.ini'),'--batch','--skip-column-names'],input=sql,capture_output=True,text=True,check=True);assert r.stdout.strip()=='23384'
tokenfile=b/'control-test-token'
if tokenfile.exists():root=tokenfile.read_text()
else:
 root=secrets.token_urlsafe(32)
 subprocess.run(['php',str(b/'site/hq/bootstrap_control.php'),'--initialize-empty-principals'],env=env,input=json.dumps({'id':'platform-test','token':root}),text=True,check=True)
 tokenfile.write_text(root)
config['controlPlane']={'enabled':True,'encryptionKey':secrets.token_hex(32)}
# Preserve the key across runs so existing encrypted registry entries remain readable.
keyfile=b/'control-test-key'
if keyfile.exists():config['controlPlane']['encryptionKey']=keyfile.read_text()
else:keyfile.write_text(config['controlPlane']['encryptionKey'])
results=[]
def check(name,condition):
 results.append({'name':name,'pass':bool(condition)})
 if not condition:raise AssertionError(name)
def call(token,body=None,query='',api='control_api.php'):
 req=urllib.request.Request('http://127.0.0.1:28185/'+api+query,data=None if body is None else json.dumps(body).encode(),headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
 try:
  with urllib.request.urlopen(req,timeout=20) as r:return r.status,json.load(r)
 except urllib.error.HTTPError as e:return e.code,json.load(e)
suffix=secrets.token_hex(4);company='control-'+suffix;other='other-'+suffix;admin=secrets.token_urlsafe(32);viewer=secrets.token_urlsafe(32)
def mutate(bearer,command,**args):return call(bearer,{'operationId':secrets.token_hex(16),'command':command,'companyId':company,**args})
try:
 (b/'hq-config.json').write_text(json.dumps(config),encoding='utf-8')
 check('Unauthenticated control rejected',call('invalid')[0]==401)
 check('Platform creates company',mutate(root,'company-create',name='Test company')[0]==200)
 check('Platform creates second company',mutate(root,'company-create',companyId=other,name='Other company')[0]==200)
 check('Property registration encrypts secret',mutate(root,'property-register',propertyId='hotel-a',secret=secrets.token_urlsafe(40))[0]==200)
 check('Grant company admin',mutate(root,'principal-grant',principalId='admin-'+suffix,token=admin,role='company_admin',propertyIds=[])[0]==200)
 check('Grant scoped viewer',mutate(admin,'principal-grant',principalId='viewer-'+suffix,token=viewer,role='viewer',propertyIds=['hotel-a'])[0]==200)
 check('Viewer cannot mutate',mutate(viewer,'property-status',propertyId='hotel-a',enabled=False)[0]==403)
 check('Cross-company admin denied',mutate(admin,'property-register',companyId=other,propertyId='bad',secret='x'*40)[0]==403)
 check('Unknown property grant denied',mutate(admin,'principal-grant',principalId='bad-'+suffix,token=secrets.token_urlsafe(32),role='viewer',propertyIds=['missing'])[0]==403)
 status,data=call(viewer,query='?action=overview',api='api.php');check('Dashboard reads database grant',status==200 and data['companyId']==company and data['propertyIds']==['hotel-a'])
 status,data=call(admin,query='?company='+company);check('Control list excludes secrets',status==200 and 'secret' not in json.dumps(data) and 'token_hash' not in json.dumps(data))
 operation={'operationId':secrets.token_hex(16),'command':'property-status','companyId':company,'propertyId':'hotel-a','enabled':False}
 first=call(admin,operation);check('Property suspension',first[0]==200)
 check('Idempotent receipt retry',call(admin,operation)==first)
 check('Operation payload conflict',call(admin,{**operation,'enabled':True})[0]==409)
 check('Suspended property loses dashboard access',call(viewer,query='?action=overview',api='api.php')[0]==403)
 check('Property activation',mutate(admin,'property-status',propertyId='hotel-a',enabled=True)[0]==200)
 check('Principal revocation',mutate(admin,'principal-revoke',principalId='viewer-'+suffix)[0]==200)
 check('Revoked principal rejected',call(viewer,query='?action=overview',api='api.php')[0]==403)
 check('Self-revocation rejected',mutate(admin,'principal-revoke',principalId='admin-'+suffix)[0]==422)
 check('Platform role cannot be granted through company API',mutate(admin,'principal-grant',principalId='escalate-'+suffix,token=secrets.token_urlsafe(32),role='platform_admin',propertyIds=[])[0]==422)
finally:
 (b/'hq-config.json').write_text(original,encoding='utf-8')
 (b/'control-results.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
print('Control plane assertions passed:',len(results))
