from pathlib import Path
import json,shutil,urllib.request,urllib.error,io,zipfile,hashlib,time
b=Path(__file__).resolve().parent
shutil.copytree(b.parent/'enterprise',b/'site',dirs_exist_ok=True)
token=(b/'hq-test-token').read_text();results=[]
def check(name,ok):
 results.append({'name':name,'pass':bool(ok)})
 (b/'enterprise-report-results.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
 if not ok:raise AssertionError(name)
def req(query,body=None,bearer=token):
 request=urllib.request.Request('http://127.0.0.1:28185/api.php?'+query,data=None if body is None else json.dumps(body).encode(),headers={'Authorization':'Bearer '+bearer,'Content-Type':'application/json'})
 try:
  with urllib.request.urlopen(request,timeout=30) as r:return r.status,r.read(),dict(r.headers)
 except urllib.error.HTTPError as e:return e.code,e.read(),dict(e.headers)
status,raw,_=req('action=report-snapshot',{'from':'2026-09-01','to':'2026-09-30','properties':['simulation-hotel']})
check('HQ report snapshot created',status==200);reportid=json.loads(raw)['data']['reportId']
status,raw,_=req('action=export&format=json&id='+reportid);data=json.loads(raw);check('HQ frozen JSON retrieved',status==200)
report=data['report'];without={k:v for k,v in report.items() if k!='checksumSha256'}
check('Report includes actual hotel database snapshot',len(report['sources'])==1 and report['sources'][0]['propertyId']=='simulation-hotel')
check('Frozen report checksum verified',hashlib.sha256(json.dumps(without,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()==reportid)
for fmt in ['csv','xlsx','pdf','email','telegram']:
 status,raw,headers=req('action=export&format='+fmt+'&id='+reportid)
 check(fmt+' successfully rendered',status==200)
 if fmt=='xlsx':
  z=zipfile.ZipFile(io.BytesIO(raw));check('XLSX carries same immutable report ID',any(reportid.encode() in z.read(n) for n in z.namelist()))
 else:check(fmt+' carries same immutable report ID',reportid.encode() in raw)
 if fmt=='pdf':check('PDF signature',raw.startswith(b'%PDF-'))
 check(fmt+' no PHP warning leaked',b'<b>Warning' not in raw and b'Fatal error' not in raw)
status,_,_=req('action=export&format=json&id='+reportid,bearer='invalid');check('Frozen report anonymous access rejected',status==401)
status,_,_=req('action=report-snapshot',{'from':'2026-09-01','to':'2026-09-30','properties':['hotel-z']});check('Foreign company report freeze denied',status==403)
status,raw,_=req('action=realtime-ticket');ticket=json.loads(raw)['data'];check('Short lived realtime ticket issued',status==200 and 0<ticket['expiresAt']-int(time.time())<=60)
(b/'realtime-test-ticket.json').write_text(json.dumps(ticket))
status,raw,_=req('action=event-revision');rev=json.loads(raw)['data'];check('Revision endpoint has no financial or guest payload',status==200 and set(rev)=={'contractVersion','companyId','revisions'})
print('Enterprise report/realtime assertions passed:',len(results))
