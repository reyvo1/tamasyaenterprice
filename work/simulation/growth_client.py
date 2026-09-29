from pathlib import Path
import json,urllib.request,urllib.error,secrets
base=Path(__file__).resolve().parent.parent/'simulation-growth'
def request(action,method='GET',data=None,operation=None,auth=True):
 headers={'Origin':'http://127.0.0.1:38189','Content-Type':'application/json','X-Device-ID':'growth-integration-test','X-Device-Name':'Growth integration fixture'}
 if auth:headers['Authorization']='Bearer '+json.loads((base/'session.json').read_text(encoding='utf-8'))['token']
 if method!='GET':headers['X-Tamasya-Operation-ID']=operation or (data or {}).get('operationId') or 'growth_'+secrets.token_hex(12)
 req=urllib.request.Request('http://127.0.0.1:38189/api.php?action='+action,data=json.dumps(data).encode() if data is not None else None,method=method,headers=headers)
 try:r=urllib.request.urlopen(req,timeout=90)
 except urllib.error.HTTPError as e:r=e
 raw=r.read().decode('utf-8-sig')
 try:payload=json.loads(raw)
 except ValueError:payload={'invalidJson':raw[:600]}
 return r.status,payload
if __name__=='__main__':
 e=json.loads((base/'environment.json').read_text(encoding='utf-8'));status,data=request('login','POST',{'username':e['APP_BOOTSTRAP_ADMIN_USERNAME'],'password':e['APP_BOOTSTRAP_ADMIN_PASSWORD']},auth=False)
 assert status==200 and data.get('token'),(status,data.get('error'));(base/'session.json').write_text(json.dumps(data),encoding='utf-8');print('Growth fixture login successful')
 for action in ['growth-suite&command=overview','enterprise-suite&command=status']:
  s,d=request(action);print(action,s,json.dumps(d))
