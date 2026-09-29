from pathlib import Path
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
import ssl,datetime,urllib.request,urllib.error,json,socket
b=Path(__file__).resolve().parent
if not (b/'tls-ca.pem').exists() or x509.load_pem_x509_certificate((b/'tls-ca.pem').read_bytes()).not_valid_after_utc<=datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(hours=1):
 key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
 name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'TAMASYA local staging only')])
 now=datetime.datetime.now(datetime.timezone.utc)
 cert=x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-datetime.timedelta(minutes=5)).not_valid_after(now+datetime.timedelta(days=3)).add_extension(x509.SubjectAlternativeName([x509.DNSName('localhost')]),False).add_extension(x509.BasicConstraints(ca=True,path_length=None),True).sign(key,hashes.SHA256())
 (b/'tls-ca.pem').write_bytes(cert.public_bytes(serialization.Encoding.PEM));(b/'tls-key.pem').write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
class Proxy(BaseHTTPRequestHandler):
 def do_POST(self):
  headers={k:v for k,v in self.headers.items() if k.lower() not in ['host','connection','content-length']}
  data=self.rfile.read(int(self.headers.get('Content-Length',0)))
  mode=(b/'hybrid-proxy-mode').read_text().strip() if (b/'hybrid-proxy-mode').exists() else ''
  if mode in ['accepted','wrong_ack','permanent']:
   payload={'success':True,'status':'acknowledged','operation_id':self.headers.get('X-Tamasya-Operation-ID'),'receipt':'0'*64}
   if mode=='permanent':payload={'success':False,'code':'SIMULATED_CONFIG_ERROR'}
   content=json.dumps(payload).encode();self.send_response(202 if mode=='accepted' else 409 if mode=='permanent' else 200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(content)));self.end_headers();self.wfile.write(content);return
  req=urllib.request.Request('http://127.0.0.1:38185'+self.path,data=data,headers=headers,method='POST')
  try: r=urllib.request.urlopen(req,timeout=30)
  except urllib.error.HTTPError as error:r=error
  content=r.read()
  if mode=='drop_after_commit':self.connection.shutdown(socket.SHUT_RDWR);self.connection.close();return
  self.send_response(r.status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(content)));self.end_headers();self.wfile.write(content)
 def log_message(self,*args):pass
server=ThreadingHTTPServer(('127.0.0.1',38186),Proxy)
context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.load_cert_chain(b/'tls-ca.pem',b/'tls-key.pem');server.socket=context.wrap_socket(server.socket,server_side=True)
print('TLS staging proxy localhost:38186 ready',flush=True);server.serve_forever()
