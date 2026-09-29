from growth_client import request,base
from pathlib import Path
import json,secrets,subprocess,datetime,urllib.parse
from runtime_tools import mysql_binary
b=Path(__file__).resolve().parent;e=json.loads((base/'environment.json').read_text(encoding='utf-8'));db=e['APP_EXPECTED_DB_NAME'];assert db.startswith('tamasya_growth_test_')
args=[mysql_binary(),'--defaults-file='+str(b/'client.ini'),'--batch','--skip-column-names',db]
def sql(q):
 r=subprocess.run(args,input=q,capture_output=True,text=True,encoding='utf-8');r.check_returncode();return r.stdout.strip()
assert sql('SELECT @@port')=='33384'
results=[];prefix='f'+secrets.token_hex(5);today=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).date().isoformat()
def check(name,ok,detail=None):
 results.append({'name':name,'pass':bool(ok),'detail':detail});(b/'growth-folio-rate-results.json').write_text(json.dumps(results,indent=2),encoding='utf-8');print('PASS' if ok else 'FAIL',name,flush=True)
 if not ok:raise AssertionError(str(detail))
def post(command,data=None,action='enterprise-suite',expected=True,op=None):
 payload={'command':command,**(data or {}),'operationId':op or prefix+'_'+secrets.token_hex(7)};s,d=request(action,'POST',payload,payload['operationId']);check(command+' '+('accepted' if expected else 'rejected'),(s==200 and d.get('success') is True)==expected,{'status':s,'error':d.get('error',d.get('message'))});return d
def get(action,**query):
 s,d=request(action+'&'+urllib.parse.urlencode(query));check(query.get('command','read')+' read',s==200 and d.get('success') is True,d.get('error'));return d['data']
before=sql('SELECT CONCAT(COUNT(*),"|",SUM(amount)) FROM transactions')
rate=post('rate-plan-save',{'code':prefix,'name':'Integration rate','baseRate':100000,'minRate':80000,'maxRate':150000,'active':True},'growth-suite')['id']
post('rate-rule-save',{'planId':rate,'name':'Direct stay','condition':{'source_in':['Direct']},'adjustmentType':'percent','adjustmentValue':10},'growth-suite')
quote=get('growth-suite',command='rate-suggestion',planId=rate,stayDate=today,bookingSource='Direct');check('Rate applies configured percentage',float(quote['rate'])==110000)
post('rate-rule-save',{'planId':rate,'name':'Malformed condition','condition':{'not_a_condition':True},'adjustmentValue':90},'growth-suite',expected=False)
post('rate-plan-save',{'code':prefix+'bad','name':'Malformed money','baseRate':'abc'},'growth-suite',expected=False)
post('rate-override-save',{'planId':rate,'stayDate':today,'rate':-1},'growth-suite',expected=False)
post('rate-override-save',{'planId':rate,'stayDate':today,'rate':125000,'stopSell':True},'growth-suite')
quote=get('growth-suite',command='rate-suggestion',planId=rate,stayDate=today);check('Calendar override retains stop-sell',float(quote['rate'])==125000 and quote['stopSell'] is True)
booking=sql("SELECT b.id FROM bookings b WHERE b.roomCharge>0 AND NOT EXISTS(SELECT 1 FROM growth_folios f WHERE f.booking_id=b.id) ORDER BY b.id LIMIT 1");assert booking
charge=float(sql("SELECT roomCharge FROM bookings WHERE id='"+booking+"'"))
f=post('folio-create',{'bookingId':booking,'name':'Integration folio'})['data']['id']
allocation=post('folio-charge-allocation-save',{'folioId':f,'bookingId':booking,'chargeType':'room_charge','amount':charge})['data']['id']
other=post('folio-create',{'bookingId':booking,'name':'Other split folio'})['data']['id']
post('folio-charge-allocation-save',{'folioId':other,'bookingId':booking,'chargeType':'room_charge','amount':0.01},expected=False)
invoice=post('folio-invoice-issue',{'folioId':f})['data']['id']
post('folio-charge-allocation-delete',{'id':allocation},expected=False)
post('folio-invoice-issue',{'folioId':f},expected=False)
post('folio-invoice-void',{'id':invoice,'reason':'Integration void before reallocation'})
post('folio-charge-allocation-delete',{'id':allocation})
check('Folio/rate metadata preserves canonical money',before==sql('SELECT CONCAT(COUNT(*),"|",SUM(amount)) FROM transactions'))
print('Folio/rate assertions passed:',len(results))
