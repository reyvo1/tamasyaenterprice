from pathlib import Path
import json,os,shutil,subprocess,ssl,threading,hashlib,hmac,base64,secrets,urllib.request
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
b=Path(__file__).resolve().parent;shutil.copytree(b.parent/'enterprise',b/'site',dirs_exist_ok=True)
original=(b/'hq-config.json').read_text(encoding='utf-8');config=json.loads(original);objects={};checks=[];corrupt=False;verified=0
access='TESTONLYACCESSKEY0001';secret=secrets.token_hex(24)
def check(name,ok):
 checks.append({'name':name,'pass':bool(ok)})
 if not ok:raise AssertionError(name)
class Store(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def respond(self,status,body=b''):
  self.send_response(status);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
 def perform(self):
  global verified
  body=self.rfile.read(int(self.headers.get('Content-Length','0')))
  try:
   auth=self.headers['Authorization'];fields=dict(part.strip().split('=',1) for part in auth.split(' ',1)[1].split(','));credential=fields['Credential'].split('/');names=fields['SignedHeaders'].split(';')
   assert credential[0]==access and credential[2:]==['us-east-1','s3','aws4_request']
   payloadhash=hashlib.sha256(body).hexdigest();assert self.headers['x-amz-content-sha256']==payloadhash
   canonicalheaders=''.join(n+':'+ ' '.join(self.headers[n].strip().split())+'\n' for n in names)
   canonical='\n'.join([self.command,self.path,'',canonicalheaders,fields['SignedHeaders'],payloadhash])
   scope='/'.join(credential[1:]);string='AWS4-HMAC-SHA256\n'+self.headers['x-amz-date']+'\n'+scope+'\n'+hashlib.sha256(canonical.encode()).hexdigest()
   key=('AWS4'+secret).encode()
   for value in credential[1:]:key=hmac.new(key,value.encode(),hashlib.sha256).digest()
   assert hmac.compare_digest(hmac.new(key,string.encode(),hashlib.sha256).hexdigest(),fields['Signature'])
   verified+=1
   if self.command=='PUT':
    assert self.headers['If-None-Match']=='*' and self.headers['x-amz-server-side-encryption']=='AES256'
    assert self.headers['x-amz-checksum-sha256']==base64.b64encode(hashlib.sha256(body).digest()).decode()
    if self.path in objects:return self.respond(412)
    objects[self.path]=body;return self.respond(200)
   self.respond(200 if self.path in objects else 404,b'corrupted' if corrupt else objects.get(self.path,b''))
  except Exception:self.respond(403)
 do_PUT=perform
 do_GET=perform
server=ThreadingHTTPServer(('127.0.0.1',38201),Store);context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.load_cert_chain(b/'tls-ca.pem',b/'tls-key.pem');server.socket=context.wrap_socket(server.socket,server_side=True);threading.Thread(target=server.serve_forever,daemon=True).start()
token=(b/'hq-test-token').read_text();request=urllib.request.Request('http://127.0.0.1:38185/api.php?action=report-snapshot',data=json.dumps({'from':'2026-09-01','to':'2026-09-30','properties':['simulation-hotel']}).encode(),headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
with urllib.request.urlopen(request) as r:reportid=json.load(r)['data']['reportId']
config['objectStorage']={'enabled':True,'endpoint':'https://localhost:38201','region':'us-east-1','bucket':'staging-private','accessKey':access,'secretKey':secret}
env={**os.environ,'TAMASYA_HQ_CONFIG_FILE':str(b/'hq-config.json')}
def run(bearer=token):return subprocess.run(['php','-d','curl.cainfo='+str(b/'tls-ca.pem'),'-d','openssl.cafile='+str(b/'tls-ca.pem'),str(b/'site/hq/archive_report.php')],input=json.dumps({'token':bearer,'reportId':reportid}),env=env,capture_output=True,text=True)
try:
 (b/'hq-config.json').write_text(json.dumps(config),encoding='utf-8')
 r=run();check('Private object uploaded and read back over TLS',r.returncode==0)
 first=json.loads(r.stdout);check('Verified receipt returned',first['status']=='verified' and first['reportId']==reportid)
 check('Company-prefixed immutable key',first['objectKey'].startswith('sim-company/reports/'+reportid+'/'))
 r=run();check('Duplicate archive returns existing identical object',r.returncode==0 and json.loads(r.stdout)['duplicate'] is True and len(objects)==1)
 check('Independent server verifies SigV4 on PUT and GET',verified==4)
 before=verified;r=run('invalid');check('Unauthorized caller never contacts object store',r.returncode!=0 and verified==before)
 corrupt=True;r=run();check('Corrupt read-back is rejected',r.returncode!=0 and 'checksum verification' in r.stderr)
finally:
 (b/'hq-config.json').write_text(original,encoding='utf-8');server.shutdown();server.server_close();(b/'object-storage-results.json').write_text(json.dumps(checks,indent=2),encoding='utf-8')
print('Object storage assertions passed:',len(checks))
