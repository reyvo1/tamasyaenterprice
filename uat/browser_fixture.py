"""Reopen only the disposable growth DB for browser and Telegram tests."""
from pathlib import Path
import json,os,socket,subprocess,sys,time
root=Path(__file__).resolve().parents[1];run=Path(sys.argv[1]).resolve()
assert run.parent==root/'work' and run.name.startswith('release-local-')
sim=run/'simulation';growth=run/'simulation-growth';tmp=Path((run/'mysql-runtime-path.txt').read_text())
assert tmp.parent==Path('/tmp') and tmp.name.startswith('tamasya-mysql-')
children=[]
def ready(port):
    for _ in range(200):
        try:
            with socket.create_connection(('127.0.0.1',port),timeout=.2):return
        except OSError:time.sleep(.1)
    raise RuntimeError('Fixture unavailable')
def start(args,env=None):
    p=subprocess.Popen(args,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);children.append(p);return p
try:
    for port in (23384,28189):
        try:
            with socket.create_connection(('127.0.0.1',port),timeout=.2):raise RuntimeError('Port occupied')
        except ConnectionRefusedError:pass
    start(['mysqld','--no-defaults','--datadir='+str(tmp/'data'),'--socket='+str(tmp/'mysql.sock'),
      '--pid-file='+str(tmp/'mysql.pid'),'--port=23384','--bind-address=127.0.0.1','--mysqlx=OFF',
      '--skip-log-bin','--secure-file-priv='+str(tmp),'--log-error='+str(tmp/'mysql.log')]);ready(23384)
    e=json.loads((growth/'environment.json').read_text());e['TELEGRAM_SIMULATION_ENABLED']='1'
    # Only a dedicated local fixture; no bot token and no live outbound transport.
    start(['php','-S','127.0.0.1:28189','-t',str(growth/'site')],{**os.environ,**e});ready(28189)
    testenv={**os.environ,'TAMASYA_UAT_FIXTURE':str(growth),'TAMASYA_UAT_RUN':str(run)}
    subprocess.run([sys.executable,str(root/'uat/telegram_simulator.py')],env=testenv,check=True)
    subprocess.run(['npx','playwright','test'],cwd=root,env=testenv,check=True)
finally:
    for p in reversed(children):
        if p.args[0]=='mysqld':subprocess.run(['mysqladmin','--defaults-file='+str(sim/'client.ini'),'shutdown'],check=True,capture_output=True)
        else:p.terminate()
        p.wait(timeout=30)
