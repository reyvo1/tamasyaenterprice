from pathlib import Path
import json,urllib.request,urllib.error,uuid,sys
base=Path(__file__).resolve().parent
if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
def request(action,method='GET',data=None,operation=None,auth=True,port=28184):
 headers={'Origin':'http://127.0.0.1:28184','X-Device-ID':'simulation-browser-01','X-Device-Name':'Integration test','Content-Type':'application/json'}
 if auth and (base/'session.json').exists():headers['Authorization']='Bearer '+json.loads((base/'session.json').read_text())['token']
 if method!='GET':headers['X-Tamasya-Operation-ID']=operation or 'sim_'+uuid.uuid4().hex
 req=urllib.request.Request(f'http://127.0.0.1:{port}/api.php?action='+action,data=json.dumps(data).encode() if data is not None else None,method=method,headers=headers)
 try:r=urllib.request.urlopen(req,timeout=90)
 except urllib.error.HTTPError as e:r=e
 raw=r.read().decode('utf-8-sig');status=r.status
 try:body=json.loads(raw)
 except:body={'raw':raw[:3000]}
 (base/'last-response.json').write_text(json.dumps(body,ensure_ascii=False,indent=2),encoding='utf-8')
 return status,body
def show(action,status,body):
 print(action,status,json.dumps({k:v for k,v in body.items() if 'token' not in k.lower() and k not in ['db','data','staff','user']},ensure_ascii=False)[:3500])
if __name__=='__main__':
 if sys.argv[1]=='login':
  e=json.loads((base/'environment.json').read_text());status,body=request('login','POST',{'username':'sim_admin','password':e['APP_BOOTSTRAP_ADMIN_PASSWORD']},auth=False)
  show('login',status,body);print('response keys',list(body))
  if body.get('token'):(base/'session.json').write_text(json.dumps(body),encoding='utf8')
 else:
  action=sys.argv[1];method=sys.argv[2] if len(sys.argv)>2 else 'GET';data=json.loads(sys.argv[3]) if len(sys.argv)>3 else None
  status,body=request(action,method,data);show(action,status,body)
