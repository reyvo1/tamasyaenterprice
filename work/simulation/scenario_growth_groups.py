from growth_client import request,base
from pathlib import Path
import json,secrets,subprocess,urllib.parse
from runtime_tools import mysql_binary
b=Path(__file__).resolve().parent;e=json.loads((base/'environment.json').read_text(encoding='utf-8'));db=e['APP_EXPECTED_DB_NAME'];assert db.startswith('tamasya_growth_test_')
args=[mysql_binary(),'--defaults-file='+str(b/'client.ini'),'--batch','--skip-column-names',db]
def sql(q):
 r=subprocess.run(args,input=q,capture_output=True,text=True,encoding='utf-8');r.check_returncode();return r.stdout.strip()
assert sql('SELECT @@port')=='23384'
results=[];prefix='group_'+secrets.token_hex(5)
def check(name,ok,detail=None):
 results.append({'name':name,'pass':bool(ok),'detail':detail});(b/'growth-group-results.json').write_text(json.dumps(results,indent=2),encoding='utf-8');print('PASS' if ok else 'FAIL',name,flush=True)
 if not ok:raise AssertionError(str(detail))
def post(command,data=None,action='enterprise-suite',expected=True):
 payload={'command':command,**(data or {}),'operationId':prefix+'_'+secrets.token_hex(7)};s,d=request(action,'POST',payload,payload['operationId']);check(command+' '+('accepted' if expected else 'rejected'),(s==200 and d.get('success') is True)==expected and (expected or s in [400,409,422,500]),{'status':s,'error':d.get('error',d.get('message'))});return d
def get(command,id):
 s,d=request('enterprise-suite&'+urllib.parse.urlencode({'command':command,'id':id}));check(command,s==200 and d.get('success') is True,d.get('error'));return d['data']
row=sql("SELECT b.id,b.checkIn,b.checkOut,b.roomCharge FROM bookings b WHERE b.guestName LIKE 'pay_%' AND b.amountPaid=20000 AND NOT EXISTS(SELECT 1 FROM growth_group_booking_links l WHERE l.booking_id=b.id) AND NOT EXISTS(SELECT 1 FROM growth_folio_charge_allocations a WHERE a.booking_id=b.id) ORDER BY b.id LIMIT 1")
assert row,'Run payment scenario first to create a paid fixture booking'
booking,arrival,departure,charge=row.split('\t');charge=float(charge)
tx=sql("SELECT id FROM transactions WHERE bookingId='"+booking+"' AND type='income' AND amount=10000 ORDER BY id LIMIT 1")
before=sql('SELECT CONCAT(COUNT(*),"|",SUM(amount)) FROM transactions')
company=post('company-save',{'code':prefix,'name':'Local Company'},'growth-suite')['id']
company2=post('company-save',{'code':prefix+'_2','name':'Other Company'},'growth-suite')['id']
groupdata={'name':prefix,'groupCode':prefix,'companyId':company,'arrivalDate':arrival,'departureDate':departure,'status':'confirmed','billingMode':'split'}
group=post('group-save',groupdata,'growth-suite')['id']
link=post('group-link-booking',{'groupId':group,'bookingId':booking,'billingMode':'split','routedPercent':60},'growth-suite')['data']['id']
master=post('folio-create',{'folioType':'master','groupId':group,'name':'Fixture master'})['data']['id']
guest=post('folio-create',{'folioType':'guest','bookingId':booking,'name':'Fixture guest'})['data']['id']
post('folio-route-save',{'targetFolioId':master},expected=False)
post('folio-route-save',{'targetFolioId':master,'groupId':group,'bookingId':booking},expected=False)
post('folio-route-save',{'targetFolioId':guest,'groupId':group},expected=False)
post('folio-route-save',{'targetFolioId':master,'groupId':'missing-group'},expected=False)
post('folio-route-save',{'targetFolioId':master,'groupId':group,'transactionKindPattern':'room_charge','routePercent':60})
post('folio-route-apply',{'bookingId':booking})
post('folio-sync-booking-charges',{'folioId':guest,'percent':100})
detail=get('folio-detail',master);check('Master receives sixty percent',float(detail['chargeTotal'])==round(charge*.6,2))
guestdetail=get('folio-detail',guest);check('Guest receives remaining forty percent',float(guestdetail['chargeTotal'])==round(charge*.4,2))
invoice=post('folio-invoice-issue',{'folioId':master})['data']['id']
hash_before=sql("SELECT source_hash FROM growth_folio_invoices WHERE id='"+invoice+"'")
pa=post('folio-allocation-save',{'folioId':master,'transactionId':tx,'amount':6000})['data']['id']
post('folio-allocation-save',{'folioId':guest,'transactionId':tx,'amount':4000})
post('folio-allocation-save',{'folioId':master,'transactionId':tx,'amount':0.01},expected=False)
check('Settlement preserves immutable invoice snapshot',hash_before==sql("SELECT source_hash FROM growth_folio_invoices WHERE id='"+invoice+"'"))
post('group-unlink-booking',{'id':link},'growth-suite',False)
post('group-save',{**groupdata,'id':group,'companyId':company2},'growth-suite',False)
allocation=detail['chargeAllocations'][0]['id']
post('folio-charge-allocation-delete',{'id':allocation},expected=False)
post('folio-invoice-void',{'id':invoice,'reason':'Audited local reassignment'})
post('folio-charge-allocation-delete',{'id':allocation})
post('group-unlink-booking',{'id':link},'growth-suite',False)
post('folio-allocation-delete',{'id':pa})
post('group-unlink-booking',{'id':link},'growth-suite')
post('folio-route-apply',{'bookingId':booking})
check('Unlinked booking no longer routed to master',sql("SELECT COUNT(*) FROM growth_folio_charge_allocations WHERE folio_id='"+master+"' AND booking_id='"+booking+"'")=='0')
check('Group and folio operations preserve canonical ledger',before==sql('SELECT CONCAT(COUNT(*),"|",SUM(amount)) FROM transactions'))
print('Group integration assertions:',len(results))
