from growth_client import request,base
from pathlib import Path
import json,secrets,subprocess,datetime
from runtime_tools import mysql_binary
b=Path(__file__).resolve().parent;e=json.loads((base/'environment.json').read_text(encoding='utf-8'));db=e['APP_EXPECTED_DB_NAME'];assert db.startswith('tamasya_growth_test_')
args=[mysql_binary(),'--defaults-file='+str(b/'client.ini'),'--batch','--skip-column-names',db]
def sql(q):
 r=subprocess.run(args,input=q,capture_output=True,text=True,encoding='utf-8');r.check_returncode();return r.stdout.strip()
assert sql('SELECT @@port')=='33384'
results=[];prefix='g'+secrets.token_hex(5);today=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).date().isoformat()
def check(name,ok,detail=None):
 results.append({'name':name,'pass':bool(ok),'detail':detail});(b/'growth-procurement-results.json').write_text(json.dumps(results,indent=2),encoding='utf-8');print('PASS' if ok else 'FAIL',name,flush=True)
 if not ok:raise AssertionError(str(detail))
def post(command,data=None,action='enterprise-suite',expected=True,op=None):
 payload={'command':command,**(data or {}),'operationId':op or prefix+'_'+secrets.token_hex(7)};status,out=request(action,'POST',payload,payload['operationId']);check(command+' '+('accepted' if expected else 'rejected'),(status==200 and out.get('success') is True)==expected,{'status':status,'error':out.get('error',out.get('message'))});return out
vendor=post('vendor-save',{'code':prefix,'name':'Procurement fixture'},'growth-suite')['id']
pr=post('pr-save',{'requestDate':today,'items':[{'itemName':'Fixture towels','quantity':10,'estimatedUnitPrice':10000}]})['data']['request']['id']
post('po-create-from-pr',{'prId':pr,'vendorId':vendor},expected=False)
post('pr-status',{'id':pr,'status':'submitted'});post('pr-status',{'id':pr,'status':'approved'})
po=post('po-create-from-pr',{'prId':pr,'vendorId':vendor,'taxRate':0})['data']['id']
post('po-status',{'id':po,'status':'submitted'},'growth-suite');post('po-status',{'id':po,'status':'approved'},'growth-suite')
post('po-status',{'id':po,'status':'received'},'growth-suite',expected=False)
s,d=request('enterprise-suite&command=po-detail&id='+po);item=d['data']['items'][0]['id'];check('PO equals approved PR amount',d['data']['purchaseOrder']['total_amount']=='100000.00')
product=sql('SELECT id FROM pos_products ORDER BY id LIMIT 1');stock=float(sql("SELECT stock_quantity FROM pos_products WHERE id='"+product+"'"))
receipt=lambda qty:post('grn-save',{'poId':po,'items':[{'poItemId':item,'quantityReceived':qty,'posProductId':product}]})['data']['receipt']['id']
first=receipt(6);stale=receipt(6)
post('grn-post',{'id':first});check('GRN updates canonical stock once',float(sql("SELECT stock_quantity FROM pos_products WHERE id='"+product+"'"))==stock+6)
post('po-status',{'id':po,'status':'cancelled'},'growth-suite',expected=False)
post('grn-post',{'id':first});check('Repeated GRN does not duplicate stock',float(sql("SELECT stock_quantity FROM pos_products WHERE id='"+product+"'"))==stock+6)
post('grn-post',{'id':stale},expected=False);check('Stale GRN leaves received quantity unchanged',float(sql("SELECT received_quantity FROM growth_purchase_order_items WHERE id='"+item+"'"))==6)
remaining=receipt(4);post('grn-post',{'id':remaining});check('Full receipts finish PO',sql("SELECT status FROM growth_purchase_orders WHERE id='"+po+"'")=='received')
def invoice(qty,grn):
 return post('supplier-invoice-save',{'vendorId':vendor,'poId':po,'grnId':grn,'supplierInvoiceNumber':prefix+'-'+secrets.token_hex(3),'invoiceDate':today,'lines':[{'itemName':'Fixture towels','quantity':qty,'unitPrice':10000,'taxRate':0,'accountClass':'inventory','poItemId':item}]})['data']['invoice']['id']
inv=invoice(6,first);duplicate=invoice(6,first)
posted=post('supplier-invoice-post',{'id':inv});tx=posted['canonicalAccrualTransactionIds'][0]
check('Accrual uses canonical noncash transaction',sql("SELECT CONCAT(transactionKind,'|',bankAccountId) FROM transactions WHERE id='"+tx+"'")=='supplier_inventory_accrual|accounts_payable')
post('supplier-invoice-post',{'id':duplicate},expected=False)
check('Second invoice does not duplicate AP accrual',sql("SELECT COUNT(*) FROM transactions WHERE sourceEntityId='"+duplicate+"'")=='0')
post('ap-payment-create',{'supplierInvoiceId':inv,'amount':60000.01,'paymentMethod':'transfer','bankAccountId':'sim_bank','date':today},expected=False)
payop=prefix+'_payment';paid=post('ap-payment-create',{'supplierInvoiceId':inv,'amount':60000,'paymentMethod':'transfer','bankAccountId':'sim_bank','date':today},op=payop)
again=post('ap-payment-create',{'supplierInvoiceId':inv,'amount':60000,'paymentMethod':'transfer','bankAccountId':'sim_bank','date':today},op=payop)
check('Payment retry returns same transaction',paid['transactionId']==again['transactionId'])
check('AP settlement clears invoice balance',float(paid['data']['outstanding'])==0)
check('Payment canonical kind avoids expense duplication',sql("SELECT transactionKind FROM transactions WHERE id='"+paid['transactionId']+"'")=='supplier_ap_payment')
s,d=request('growth-suite&command=po-detail&id='+po)
check('PO detail includes AP settlement and exact outstanding',s==200 and d['success'] and float(d['data']['paidAmount'])==60000 and float(d['data']['outstanding'])==40000)
s,d=request('growth-suite&command=bootstrap');rows=[x for x in d['data']['purchaseOrders'] if x['id']==po]
check('PO list includes AP settlement',s==200 and len(rows)==1 and float(rows[0]['paid_amount'])==60000)
post('po-link-payment',{'poId':po,'transactionId':paid['transactionId'],'amountApplied':1},'growth-suite',expected=False)
post('po-link-payment',{'poId':po,'transactionId':tx,'amountApplied':1},'growth-suite',expected=False)
post('po-status',{'id':po,'status':'closed'},'growth-suite',expected=False)
final_invoice=invoice(4,remaining);post('supplier-invoice-post',{'id':final_invoice})
post('ap-payment-create',{'supplierInvoiceId':final_invoice,'amount':40000,'paymentMethod':'transfer','bankAccountId':'sim_bank','date':today})
post('po-status',{'id':po,'status':'closed'},'growth-suite')
check('PO closure recognizes canonical AP settlements',sql("SELECT status FROM growth_purchase_orders WHERE id='"+po+"'")=='closed')
s,d=request('growth-suite&command=po-detail&id='+po)
check('Fully paid PO detail agrees with closure',s==200 and d['success'] and float(d['data']['paidAmount'])==100000 and float(d['data']['outstanding'])==0)
check('All journals balanced',sql("SELECT COUNT(*) FROM (SELECT e.id FROM journal_entries e JOIN journal_lines l ON l.journal_entry_id=e.id GROUP BY e.id HAVING ABS(SUM(l.debit-l.credit))>0.005) x")=='0')
print('Procurement assertions passed:',len(results))
