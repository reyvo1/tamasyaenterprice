"""Continue the isolated release fixture with HQ, queue, delivery and storage tests."""
from pathlib import Path
import json, os, shutil, signal, socket, subprocess, sys, time

work=Path(__file__).resolve().parent
run=Path(sys.argv[1]).resolve()
assert run.parent==work and run.name.startswith('release-local-')
sim=run/'simulation'; source=run/'enterprise'
tmp=Path((run/'mysql-runtime-path.txt').read_text())
assert tmp.parent==Path('/tmp') and tmp.name.startswith('tamasya-mysql-')
children=[]; results=[]; env=os.environ.copy()
for path in (work/'simulation').iterdir():
    if path.is_file() and path.suffix in ('.py','.php') and 'credentials' not in path.name:
        shutil.copy2(path,sim/path.name)
credential=json.loads((sim/'credentials.json').read_text())
(sim/'db_credentials.php').write_text("<?php return ['host'=>'127.0.0.1','port'=>23384,'name'=>'tamasya_sim','user'=>'tamasya_sim','pass'=>'"+credential['password']+"'];")

def start(args, environment=env):
    log=open(sim/'logs/enterprise-gate-processes.log','ab')
    p=subprocess.Popen(args,env=environment,stdout=log,stderr=log);children.append(p);return p
def ready(port):
    for _ in range(200):
        try:
            with socket.create_connection(('127.0.0.1',port),timeout=.2):return
        except OSError:time.sleep(.1)
    raise RuntimeError('Port unavailable: '+str(port))
def script(name):
    print('RUN',name,flush=True)
    r=subprocess.run([sys.executable,'-u',str(sim/name)],env=env,capture_output=True,text=True,timeout=900)
    (sim/'logs'/('gate-'+name+'.txt')).write_text(r.stdout+r.stderr)
    print((r.stdout+r.stderr)[-1800:],flush=True)
    results.append({'script':name,'exitCode':r.returncode})
    (run/'enterprise-gate-progress.json').write_text(json.dumps(results,indent=2))
    r.check_returncode()
def stop(pidfile, root):
    if not pidfile.exists():return
    pid=int(pidfile.read_text());proc=Path('/proc')/str(pid)/'cmdline'
    if not proc.exists():return
    args=proc.read_bytes().split(b'\0')
    if not any(args):return
    if b'-S' not in args or str(root).encode() not in args:raise RuntimeError('Unrecognized process')
    os.kill(pid,signal.SIGTERM);time.sleep(.2)
try:
    for port in [23384,28184,28185,28186,28187,28200]:
        try:
            with socket.create_connection(('127.0.0.1',port),timeout=.2):
                raise RuntimeError('Port already occupied: '+str(port))
        except (ConnectionRefusedError, TimeoutError):pass
    start(['mysqld','--no-defaults','--datadir='+str(tmp/'data'),'--socket='+str(tmp/'mysql.sock'),
           '--pid-file='+str(tmp/'mysql.pid'),'--port=23384','--bind-address=127.0.0.1','--mysqlx=OFF',
           '--skip-log-bin','--secure-file-priv='+str(tmp),'--log-error='+str(tmp/'mysql.log')])
    ready(23384)
    if '--currency-only' in sys.argv:
        script('scenario_currency.py')
        sys.exit(0)
    start([sys.executable,str(sim/'hybrid_tls.py')]);ready(28186)
    script('start_hybrid.py');ready(28184);ready(28185)
    finishing='--finish' in sys.argv
    if not finishing:
        script('scenario_hybrid.py')
        script('scenario_hq_permissions.py')
    stop(sim/'php.pid',sim/'site');stop(sim/'hq-php.pid',sim/'site/hq')
    script('start_enterprise.py');ready(28184);ready(28185);ready(28200)
    if finishing:
        env.update(json.loads((sim/'enterprise-environment.json').read_text()))
        for name in ['scenario_delivery.py','scenario_object_storage.py','scenario_hq_permissions.py']:
            script(name)
        r=subprocess.run(['php',str(sim/'scenario_ha_commit.php')],env=env,capture_output=True,text=True)
        (sim/'logs/gate-ha-commit.txt').write_text(r.stdout+r.stderr);r.check_returncode()
    else:
        script('second_property.py')
        script('run_enterprise_extras.py')
    script('scenario_deployment.py')
    script('scenario_read_performance.py')
    script('scenario_currency.py')
    print('ENTERPRISE GATES PASSED',run,flush=True)
finally:
    for pidfile,root in [(sim/'php.pid',sim/'site'),(sim/'hq-php.pid',sim/'site/hq'),
                         (run/'simulation-secondary/php.pid',sim/'site')]:stop(pidfile,root)
    rt=sim/'realtime.pid'
    if rt.exists():
        pid=int(rt.read_text());proc=Path('/proc')/str(pid)/'cmdline'
        if proc.exists() and str(sim/'site/services/realtime/server.mjs').encode() in proc.read_bytes().split(b'\0'):os.kill(pid,signal.SIGTERM)
    for p in reversed(children):
        if Path(p.args[0]).name=='mysqld':
            subprocess.run(['mysqladmin','--defaults-file='+str(sim/'client.ini'),'shutdown'],check=True)
        else:p.terminate()
        p.wait(timeout=30)
    print('Evidence retained:',run,flush=True)
