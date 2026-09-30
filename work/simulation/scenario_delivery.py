from pathlib import Path
import os,json,shutil,ssl,threading,subprocess,secrets,hashlib,hmac,urllib.request,urllib.error
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
b=Path(__file__).resolve().parent;shutil.copytree(b.parent/'enterprise',b/'site',dirs_exist_ok=True)
original=(b/'hq-config.json').read_text();config=json.loads(original);secret=secrets.token_hex(32);token=(b/'hq-test-token').read_text();results=[];mode='ack';received=[]
def check(name,ok):
 results.append({'name':name,'pass':bool(ok)})
 if not ok:raise AssertionError(name)
class Bridge(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_POST(self):
  raw=self.rfile.read(int(self.headers['Content-Length']));p=json.loads(raw);received.append(p)
  signature=hmac.new(secret.encode(),(self.headers['X-Tamasya-Timestamp']+'\n'+p['jobId']+'\n'+hashlib.sha256(raw).hexdigest()).encode(),hashlib.sha256).hexdigest()
  valid=hmac.compare_digest(signature,self.headers['X-Tamasya-Signature'])
  data={'success':valid,'status':'delivered','jobId':p['jobId'],'reportId':p['reportId'] if mode!='wrong-report' else 'wrong'}
  body=json.dumps(data).encode();self.send_response(202 if mode=='accepted' else 200);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
server=ThreadingHTTPServer(('127.0.0.1',28202),Bridge);tls=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);tls.load_cert_chain(b/'tls-ca.pem',b/'tls-key.pem');server.socket=tls.wrap_socket(server.socket,server_side=True);threading.Thread(target=server.serve_forever,daemon=True).start()
def api(action,body=None):
 req=urllib.request.Request('http://127.0.0.1:28185/api.php?action='+action,data=None if body is None else json.dumps(body).encode(),headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
 try:
  with urllib.request.urlopen(req) as r:return r.status,json.load(r)
 except urllib.error.HTTPError as e:return e.code,json.load(e)
def worker():
 r=subprocess.run(['php','-d','curl.cainfo='+str(b/'tls-ca.pem'),'-d','openssl.cafile='+str(b/'tls-ca.pem'),str(b/'site/hq/delivery_worker.php'),'once'],env={**os.environ,'TAMASYA_HQ_CONFIG_FILE':str(b/'hq-config.json')},capture_output=True,text=True);assert r.returncode==0,r.stderr;return json.loads(r.stdout)
try:
 config['viewers'][0]['role']='finance';config['deliveryDestinations']={'sim-company':{'test-email':{'enabled':True,'channel':'email','label':'Simulated only','bridgeUrl':'https://localhost:28202/deliver','secret':secret}}};(b/'hq-config.json').write_text(json.dumps(config))
 status,data=api('report-snapshot',{'from':'2026-09-01','to':'2026-09-30','properties':['simulation-hotel']});check('Delivery references frozen canonical report',status==200);rid=data['data']['reportId']
 for mode in ['ack','accepted','wrong-report']:
  body={'operationId':secrets.token_hex(16),'reportId':rid,'destinationId':'test-email'}
  status,first=api('queue-delivery',body);check(mode+' queue accepted',status==200)
  status,retry=api('queue-delivery',body);check(mode+' same operation yields same job',status==200 and retry['data']['jobId']==first['data']['jobId'])
  outcome=worker();check(mode+' requires matching delivered ACK',outcome['status']==('delivered' if mode=='ack' else 'uncertain'))
  count=len(received);again=worker();check(mode+' completed/uncertain job not sent twice',again['status']=='idle' and len(received)==count)
  check(mode+' message and attachment reference same report',received[-1]['reportId']==rid and rid in received[-1]['text'] and rid in received[-1]['html'])
 status,data=api('delivery-jobs');check('Delivery states visible to authorized viewer',status==200 and len(data['data']['jobs'])>=3)
 config['viewers'][0]['role']='viewer';(b/'hq-config.json').write_text(json.dumps(config));status,data=api('queue-delivery',{'operationId':secrets.token_hex(16),'reportId':rid,'destinationId':'test-email'});check('Read-only viewer cannot dispatch messages',status==403)
finally:
 (b/'hq-config.json').write_text(original);server.shutdown();server.server_close();(b/'delivery-results.json').write_text(json.dumps(results,indent=2))
print('Local delivery assertions passed:',len(results))
