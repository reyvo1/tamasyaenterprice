from runtime_tools import mysql_binary, mysqldump_binary, background_process_options, python_command
from pathlib import Path
import json,os,shutil,subprocess,socket,time,uuid,concurrent.futures,statistics,platform
from client import request
b=Path(__file__).resolve().parent;shutil.copytree(b.parent/'enterprise',b/'site',dirs_exist_ok=True)
env={**os.environ,**json.loads((b/'enterprise-environment.json').read_text())};env['TAMASYA_WORKER_BATCH']='20';checks=[];children=[]
def check(name,ok,detail=None):
 checks.append({'name':name,'pass':bool(ok),'detail':detail})
 (b/'enterprise-worker-results.json').write_text(json.dumps(checks,indent=2),encoding='utf-8')
 if not ok:raise AssertionError(name+' '+str(detail))
def process(args,environment):
 log=open(b/'logs/enterprise-worker-test.log','ab');p=subprocess.Popen(args,env=environment,stdout=log,stderr=log,**background_process_options());children.append(p);return p
def ready(port):
 for _ in range(50):
  try:
   with socket.create_connection(('127.0.0.1',port),timeout=.1):return
  except OSError:time.sleep(.1)
 raise RuntimeError('No listener '+str(port))
def worker(environment=env):return subprocess.run(['php','-d','curl.cainfo='+str(b/'tls-ca.pem'),'-d','openssl.cafile='+str(b/'tls-ca.pem'),str(b/'site/service_worker.php'),'once'],env=environment,capture_output=True,text=True,timeout=80)
try:
 try:
  with socket.create_connection(('127.0.0.1',28186),timeout=.2):pass
 except OSError:process([python_command(),str(b/'hybrid_tls.py')],os.environ.copy());ready(28186)
 (b/'hybrid-proxy-mode').write_text('')
 operation='worker_'+uuid.uuid4().hex
 status,data=request('multi-property','POST',{'command':'queue-snapshot','operationId':operation,'from':'2026-09-01','to':'2026-09-30'})
 check('Canonical API queues immutable worker job',status==202,data.get('message'))
 with concurrent.futures.ThreadPoolExecutor(2) as pool:runs=list(pool.map(lambda _:worker(),range(2)))
 check('Two workers complete without crash',all(r.returncode==0 for r in runs),[r.stderr for r in runs])
 status,data=request('multi-property&command=outbox');job=next(j for j in data['data']['jobs'] if j['operation_id']==operation)
 check('Worker receives durable matching HQ receipt',job['status']=='acknowledged' and job['receipt']==job['checksum'],job['status'])
 before=job['attempts'];r=worker();status,data=request('multi-property&command=outbox');job=next(j for j in data['data']['jobs'] if j['operation_id']==operation)
 check('Worker restart does not redeliver acknowledged job',r.returncode==0 and job['attempts']==before)
 r=worker({**env,'TAMASYA_NODE_ROLE':'local_backup'});payload=json.loads(r.stdout)
 check('Standby worker suppresses outgoing side effects',r.returncode==0 and payload['data']['writer'] is False)
 process(['php','-S','127.0.0.1:28188','-t',str(b/'site')],env);ready(28188)
 def read(i):
  started=time.perf_counter();status,data=request('multi-property&command=snapshot-v3&from=2026-09-01&to=2026-09-30',port=28184 if i%2==0 else 28188);return (time.perf_counter()-started)*1000,status,data.get('data',{}).get('checksumSha256')
 with concurrent.futures.ThreadPoolExecutor(4) as pool:reads=list(pool.map(read,range(40)))
 check('Two PHP API processes return successful scoped snapshots',all(r[1]==200 for r in reads))
 check('Two API processes agree on canonical snapshot',len({r[2] for r in reads})==1)
 values=sorted(r[0] for r in reads);metrics={'requests':40,'concurrency':4,'apiProcesses':2,'p50Ms':round(statistics.median(values),2),'p95Ms':round(values[37],2),'maxMs':round(max(values),2),'scope':'Local '+platform.system()+' PHP development servers; synthetic simulation dataset; not a production SLA'}
 (b/'enterprise-load-results.json').write_text(json.dumps(metrics,indent=2));print(json.dumps(metrics))
finally:
 for p in reversed(children):p.terminate();p.wait(timeout=10)
print('Worker assertions passed:',len(checks))
