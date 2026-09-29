from pathlib import Path
import subprocess,json,secrets,yaml
b=Path(__file__).resolve().parent;src=b.parent/'enterprise';rows=[]
def check(name,ok):
 rows.append({'name':name,'pass':bool(ok)})
 (b/'deployment-results.json').write_text(json.dumps(rows,indent=2))
 assert ok,name
for filename in ['compose.yaml','compose.saas.yaml','compose.hq.yaml']:
 data=yaml.safe_load((src/'deploy'/filename).read_text())
 check(filename+' parses as YAML with services',isinstance(data.get('services'),dict))
target=b/('private-provision-'+secrets.token_hex(4))
request={'companyId':'fixture-company','propertyId':'fixture-property','url':'https://fixture.example.test','databaseHost':'mysql.internal','databasePort':3306,'databaseUserHost':'10.0.%'}
def run(output,payload):
 return subprocess.run(['php',str(src/'deploy/provision_property.php'),str(output)],input=json.dumps(payload),capture_output=True,text=True,encoding='utf-8')
r=run(target,request);check('Provisioning generates a private bundle',r.returncode==0 and json.loads(r.stdout)['status']=='bundle_created_not_applied')
sql=(target/'provision.sql').read_text();check('Generated grant is property-scoped CRUD', 'GRANT SELECT,INSERT,UPDATE,DELETE ON `tm_' in sql and 'ON *.*' not in sql)
check('Bundle refuses overwrite',run(target,request).returncode!=0)
check('Bundle refuses application-tree output',run(src/'provision-test-invalid',request).returncode!=0)
check('Provisioning rejects non-HTTPS origin',run(b/('invalid-'+secrets.token_hex(4)),{**request,'url':'http://fixture.example.test'}).returncode!=0)
check('No generated secret emitted on stdout','APP_ENCRYPTION_KEY' not in r.stdout and 'pass' not in r.stdout.lower())
print('Deployment artifact checks passed:',len(rows),'(YAML syntax only; Docker/nginx runtime not available)')
