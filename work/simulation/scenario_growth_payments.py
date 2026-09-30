from growth_client import request,base
from pathlib import Path
import json,secrets,subprocess,datetime
from runtime_tools import mysql_binary
b=Path(__file__).resolve().parent;e=json.loads((base/'environment.json').read_text(encoding='utf-8'));db=e['APP_EXPECTED_DB_NAME'];assert db.startswith('tamasya_growth_test_')
args=[mysql_binary(),'--defaults-file='+str(b/'client.ini'),'--batch','--skip-column-names',db]
def sql(q):
 r=subprocess.run(args,input=q,capture_output=True,text=True,encoding='utf-8');r.check_returncode();return r.stdout.strip()
assert sql('SELECT @@port')=='23384'
results=[];prefix='pay_'+secrets.token_hex(5)
def check(name,ok,detail=None):
 results.append({'name':name,'pass':bool(ok),'detail':detail});(b/'growth-payment-results.json').write_text(json.dumps(results,indent=2),encoding='utf-8');print('PASS' if ok else 'FAIL',name,flush=True)
 if not ok:raise AssertionError(str(detail))
def post(command,data=None,action='growth-suite',expected=True):
 payload={'command':command,**(data or {}),'operationId':prefix+'_'+secrets.token_hex(7)};s,d=request(action,'POST',payload,payload['operationId']);check(command+' '+('accepted' if expected else 'rejected'),(s==200 and d.get('success') is True)==expected and (expected or s in [400,409,422,500]),{'status':s,'error':d.get('error',d.get('message'))});return d
start=datetime.date.fromisoformat(sql("SELECT DATE_FORMAT(GREATEST(CURRENT_DATE,COALESCE(MAX(checkOut),CURRENT_DATE)),'%Y-%m-%d') FROM bookings"))+datetime.timedelta(days=3)
if sql("SELECT COUNT(*) FROM shift_sessions WHERE status='open'")=='0':post('shift-open',{'openingCash':100000,'shiftTime':'malam','notes':'Local Growth integration'},'operations-center')
room=sql("SELECT number FROM rooms WHERE status='available' ORDER BY number LIMIT 1");assert room
booking=post('create fixture booking',{'guestName':prefix,'roomNumber':room,'checkIn':str(start),'checkOut':str(start+datetime.timedelta(days=1)),'totalAmount':100000,'paymentStatus':'unpaid','bookingSource':'Direct','broadcast':False},'bookings')['bookingId']
intents=[]
for amount in [10000,10000,10000.01,10000]:
 intents.append(post('payment-intent-create',{'bookingId':booking,'providerCode':'fixture','amount':amount})['data']['id'])
post('payment-intent-create',{'bookingId':booking,'providerCode':'fixture','amount':100000.01},expected=False)
event={'intentId':intents[0],'providerEventId':prefix+'_event','status':'paid','amount':10000,'payload':{'reference':'fixture'}}
post('payment-event-register',event);post('payment-event-register',event)
check('Event replay remains one record',sql("SELECT COUNT(*) FROM growth_payment_events WHERE provider_event_id='"+prefix+"_event'")=='1')
for changed in [{'amount':10000.01},{'intentId':intents[1]},{'status':'failed'},{'payload':{'reference':'different'}}]:post('payment-event-register',{**event,**changed},expected=False)
check('Provider event cannot mutate canonical ledger',sql("SELECT COUNT(*) FROM transactions WHERE bookingId='"+booking+"'")=='0')
post('pay fixture booking',{'bookingId':booking,'amount':10000,'paymentMethod':'cash'},'booking-payments')
tx=sql("SELECT id FROM transactions WHERE bookingId='"+booking+"' AND type='income' ORDER BY createdAt,id LIMIT 1");assert tx
before=sql('SELECT CONCAT(COUNT(*),"|",SUM(amount)) FROM transactions')
post('payment-link-transaction',{'intentId':intents[2],'transactionId':tx},expected=False)
post('payment-link-transaction',{'intentId':intents[0],'transactionId':tx})
post('payment-link-transaction',{'intentId':intents[0],'transactionId':tx})
post('payment-link-transaction',{'intentId':intents[1],'transactionId':tx},expected=False)
check('Intent metadata does not duplicate cash or tax',before==sql('SELECT CONCAT(COUNT(*),"|",SUM(amount)) FROM transactions'))
post('second fixture payment',{'bookingId':booking,'amount':10000,'paymentMethod':'cash'},'booking-payments')
tx2=sql("SELECT id FROM transactions WHERE bookingId='"+booking+"' AND id<>'"+tx+"' AND type='income' LIMIT 1")
post('payment-link-transaction',{'intentId':intents[0],'transactionId':tx2},expected=False)
post('payment-link-transaction',{'intentId':intents[3],'transactionId':tx2})
check('Confirmed intent preserves original transaction',sql("SELECT confirmed_transaction_id FROM growth_payment_intents WHERE id='"+intents[0]+"'")==tx)
check('Canonical booking paid exactly twice',sql("SELECT amountPaid FROM bookings WHERE id='"+booking+"'")=='20000.00')
check('Every journal remains balanced',sql('SELECT COUNT(*) FROM (SELECT journal_entry_id FROM journal_lines GROUP BY journal_entry_id HAVING ABS(SUM(debit)-SUM(credit))>0.001) x')=='0')
print('Payment integration assertions:',len(results))
