from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import subprocess,json,re,sys
b=Path(__file__).resolve().parent;root=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else b/'enterprise';out=Path(sys.argv[2]).resolve() if len(sys.argv)>2 else b/'simulation/enterprise-current-checks.json'
tasks=[('php',p) for p in root.rglob('*.php')]+[('node',p) for p in root.rglob('*.js')]+[('node',p) for p in root.rglob('*.mjs')]
def lint(task):
 exe,p=task;r=subprocess.run([exe,'-l' if exe=='php' else '--check',str(p)],capture_output=True,text=True,encoding='utf-8');return {'file':p.relative_to(root).as_posix(),'pass':r.returncode==0,'error':(r.stdout+r.stderr) if r.returncode else None}
def assertion_count(output):
 count=len(re.findall(r'^PASS ',output,re.M))
 if count:return count
 try:
  payload=json.loads(output)
  if isinstance(payload,dict) and isinstance(payload.get('passed'),int):return payload['passed']
 except (TypeError,ValueError):pass
 match=re.search(r'assertions passed:\s*(\d+)',output,re.I)
 return int(match.group(1)) if match else 0
with ThreadPoolExecutor(max_workers=4) as pool:checks=list(pool.map(lint,tasks))
result={'syntax':checks,'units':[]};out.write_text(json.dumps(result,indent=2),encoding='utf-8');bad=[r for r in checks if not r['pass']];print('Syntax',len(checks),'failures',len(bad),flush=True)
if bad:raise RuntimeError(str(bad))
for exe,file in [('php','regression.php'),('node','regression.mjs'),('php','finance-regression.php'),('php','hybrid-regression.php'),('php','hq-v3-regression.php'),('php','growth-input-regression.php'),('php','provider-bridge-regression.php'),('node','realtime-regression.mjs'),('php','device-contract-regression.php'),('php','database-tls-regression.php'),('node','growth-failover-regression.mjs')]:
 r=subprocess.run([exe,str(root/'tests'/file)],capture_output=True,text=True,encoding='utf-8');entry={'suite':file,'passed':assertion_count(r.stdout),'pass':r.returncode==0,'output':r.stdout+r.stderr};result['units'].append(entry);out.write_text(json.dumps(result,indent=2),encoding='utf-8');print(file,entry['passed'],'PASS' if entry['pass'] else 'FAIL',flush=True);r.check_returncode()
