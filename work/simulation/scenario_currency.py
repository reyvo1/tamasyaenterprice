from runtime_tools import mysql_binary, mysqldump_binary, background_process_options, python_command
from pathlib import Path
import os,json,secrets,subprocess,socket,time,urllib.request,urllib.error
b=Path(__file__).resolve().parent;root=b.parent/'enterprise';private=b.parent/'simulation-currency';private.mkdir(exist_ok=True)
args=[mysql_binary(),'--defaults-file='+str(b/'client.ini'),'--batch','--skip-column-names']
def sql(q,db=None):
 r=subprocess.run(args+([db] if db else []),input=q,capture_output=True,text=True,encoding='utf-8');r.check_returncode();return r.stdout.strip()
port,datadir=sql('SELECT @@port,@@datadir').split('\t');assert port=='23384' and Path(datadir).resolve()==(b/'mysql-data').resolve()
try:
 with socket.create_connection(('127.0.0.1',28194),timeout=.2):raise RuntimeError('Currency port occupied')
except OSError:pass
suffix=secrets.token_hex(4);db='tamasya_currency_test_'+suffix;results=[];token=None;url='http://127.0.0.1:28194'
def check(name,ok,detail=None):
 results.append({'name':name,'pass':bool(ok),'detail':detail});(b/'growth-currency-results.json').write_text(json.dumps(results,indent=2),encoding='utf-8');print('PASS' if ok else 'FAIL',name,flush=True)
 assert ok,(name,detail)
sql('CREATE DATABASE `'+db+'` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;USE `'+db+'`;\n'+(root/'database_setup.sql').read_text(encoding='utf-8-sig'))
sql("GRANT ALL ON `"+db+"`.* TO 'tamasya_sim'@'127.0.0.1'")
cred=json.loads((b/'credentials.json').read_text(encoding='utf-8'));credential=private/(suffix+'-db.php');credential.write_text("<?php return ['host'=>'127.0.0.1','port'=>23384,'name'=>'"+db+"','user'=>'tamasya_sim','pass'=>'"+cred['password']+"'];",encoding='utf-8')
env=json.loads((b/'environment.json').read_text(encoding='utf-8'));env.update(APP_CREDENTIALS_FILE=str(credential),APP_EXPECTED_DB_NAME=db,APP_URL=url,APP_ALLOWED_ORIGINS=url,TAMASYA_PROPERTY_ID='usd-fixture',TAMASYA_PROPERTY_CODE='USDFIX',TAMASYA_PROPERTY_CURRENCY='USD',TAMASYA_COMPANY_ID='currency-fixture-company',TAMASYA_PROPERTY_NAME='Synthetic USD fixture',TAMASYA_NODE_ID='usd-node',TAMASYA_GROWTH_SUITE_ENABLED='1',TAMASYA_ENTERPRISE_COMPLETION_ENABLED='1',TAMASYA_HQ_BRIDGE_ENABLED='0',TAMASYA_ENTERPRISE_CRM_CAMPAIGN_SEND_ENABLED='0')
for key in ['KPI','RATE_MANAGER','GROUP_CORPORATE','ADVANCED_FOLIO','PROCUREMENT','CHANNEL_FOUNDATION','PAYMENT_FOUNDATION']:env['TAMASYA_GROWTH_'+key+'_ENABLED']='1'
env={**os.environ,**env}
for script in ['first_install.php']:
 r=subprocess.run(['php',str(root/script)],env=env,capture_output=True,text=True,encoding='utf-8');check('Fresh USD '+script,r.returncode==0,r.stderr if r.returncode else None)
backup=private/(suffix+'-before-optional.sql')
with backup.open('wb') as out:r=subprocess.run([mysqldump_binary(),'--defaults-file='+str(b/'client.ini'),'--no-tablespaces','--single-transaction',db],stdout=out,stderr=subprocess.PIPE);r.check_returncode()
r=subprocess.run(['php',str(root/'optional_modules_install.php'),'--apply','--target=all','--backup-confirmed='+str(backup)],env=env,capture_output=True,text=True,encoding='utf-8');check('USD optional schema installed',r.returncode==0,r.stderr if r.returncode else None)
def request(action,data=None,expected=True):
 headers={'Origin':url,'Content-Type':'application/json','X-Device-ID':'currency-fixture','X-Tamasya-Operation-ID':'usd_'+secrets.token_hex(12)}
 if data is not None:data={'operationId':headers['X-Tamasya-Operation-ID'],**data}
 if token:headers['Authorization']='Bearer '+token
 req=urllib.request.Request(url+'/api.php?action='+action,headers=headers,data=json.dumps(data).encode() if data is not None else None)
 try:r=urllib.request.urlopen(req,timeout=90)
 except urllib.error.HTTPError as x:r=x
 d=json.loads(r.read().decode('utf-8-sig'));ok=r.status==200 and d.get('success') is not False
 check(action+('' if expected else ' currency mismatch rejected'),ok==expected and (expected or 'mata uang' in str(d.get('error',d.get('message',''))).lower()),{'status':r.status,'message':d.get('error',d.get('message'))});return d
with (private/(suffix+'-php.log')).open('ab') as log:
 p=subprocess.Popen(['php','-S','127.0.0.1:28194','-t',str(root)],env=env,stdout=log,stderr=log,**background_process_options())
 try:
  for _ in range(50):
   try:
    with socket.create_connection(('127.0.0.1',28194),timeout=.2):break
   except OSError:time.sleep(.1)
  token=request('login',{'username':env['APP_BOOTSTRAP_ADMIN_USERNAME'],'password':env['APP_BOOTSTRAP_ADMIN_PASSWORD']})['token']
  request('property-setup',{'command':'save','propertyName':'Synthetic USD fixture','address':'Fixture only','phone':'0000000000','email':'fixture@example.invalid','taxSetupMode':'not_applicable','paymentSetupMode':'cash_only'})
  for key,typ in [('room_rental','income'),('extra_service','income'),('pos_revenue','income'),('pos_refund','expense'),('pos_cogs','expense'),('pos_cogs_reversal','income')]:
   cat=request('categories',{'name':'USD '+key,'type':typ})['categoryId'];request('categories-semantic-bind',{'categoryId':cat,'systemKey':key})
   if key=='room_rental':request('subcategories',{'categoryId':cat,'subcategoryName':'USD Deluxe'})
  request('rooms',{'number':'USD101','type':'USD Deluxe','price':123.45,'floor':1})
  ready=request('property-setup',{'command':'finalize'});check('USD property ready',ready['data']['ready'])
  request('operations-center',{'command':'shift-open','openingCash':1000,'shiftTime':'malam'})
  request('operations-center',{'command':'tax-rule-save','id':'usd_synthetic_zero','name':'Synthetic arithmetic zero only','sourcePattern':'*','transactionKind':'*','rate':0,'priority':100,'taxable':0,'isActive':1})
  booking=request('bookings',{'guestName':'USD fixture','roomNumber':'USD101','checkIn':'2026-11-01','checkOut':'2026-11-02','totalAmount':123.45,'paymentStatus':'unpaid','bookingSource':'Direct','broadcast':False})['bookingId']
  rate=request('growth-suite',{'command':'rate-plan-save','code':'USD','name':'USD rate','baseRate':123.45,'active':True})['id']
  folio=request('enterprise-suite',{'command':'folio-create','bookingId':booking,'name':'USD folio'})['data']['id']
  vendor=request('growth-suite',{'command':'vendor-save','code':'USD','name':'USD supplier'})['id']
  po=request('growth-suite',{'command':'po-save','vendorId':vendor,'orderDate':'2026-09-23','items':[{'itemName':'USD item','quantity':1,'unitPrice':12.34}]})['id']
  inv=request('enterprise-suite',{'command':'supplier-invoice-save','vendorId':vendor,'supplierInvoiceNumber':'USD-1','invoiceDate':'2026-09-23','lines':[{'itemName':'USD service','quantity':1,'unitPrice':12.34,'accountClass':'expense'}]})['data']['invoice']['id']
  for table,id in [('growth_rate_plans',rate),('growth_folios',folio),('growth_purchase_orders',po),('growth_supplier_invoices',inv)]:check(table+' stores USD',sql("SELECT currency FROM "+table+" WHERE id='"+id+"'",db)=='USD')
  request('booking-payments',{'bookingId':booking,'amount':12.34,'paymentMethod':'cash'})
  check('USD booking retains exact fractional payment',sql("SELECT amountPaid FROM bookings WHERE id='"+booking+"'",db)=='12.34')
  check('USD canonical journals balanced',sql('SELECT COUNT(*) FROM (SELECT journal_entry_id FROM journal_lines GROUP BY journal_entry_id HAVING ABS(SUM(debit)-SUM(credit))>0.001) x',db)=='0')
  request('growth-suite',{'command':'po-status','id':po,'status':'submitted'})
  request('growth-suite',{'command':'po-status','id':po,'status':'approved'})
  item=sql("SELECT id FROM growth_purchase_order_items WHERE po_id='"+po+"' LIMIT 1",db)
  receipt=request('enterprise-suite',{'command':'grn-save','poId':po,'items':[{'poItemId':item,'quantityReceived':1}]})['data']['receipt']['id']
  sql("UPDATE growth_purchase_orders SET currency='IDR' WHERE id='"+po+"'",db)
  try:request('enterprise-suite',{'command':'grn-post','id':receipt},expected=False)
  finally:sql("UPDATE growth_purchase_orders SET currency='USD' WHERE id='"+po+"'",db)
  check('Rejected currency mismatch leaves goods receipt unposted',sql("SELECT status FROM growth_goods_receipts WHERE id='"+receipt+"'",db)=='draft')
  sql("UPDATE growth_supplier_invoices SET currency='IDR' WHERE id='"+inv+"'",db)
  try:request('enterprise-suite',{'command':'supplier-invoice-post','id':inv},expected=False)
  finally:sql("UPDATE growth_supplier_invoices SET currency='USD' WHERE id='"+inv+"'",db)
  check('Rejected currency mismatch leaves invoice unposted',sql("SELECT status FROM growth_supplier_invoices WHERE id='"+inv+"'",db)=='draft' and sql("SELECT COUNT(*) FROM transactions WHERE sourceEntityId='"+inv+"'",db)=='0')
  probe="require $argv[1]; $c=require getenv('APP_CREDENTIALS_FILE'); $p=new PDO('mysql:host='.$c['host'].';port='.$c['port'].';dbname='.$c['name'],$c['user'],$c['pass']); try { tamasyaDatabasePropertyIdentity($p,true); exit(2); } catch (RuntimeException $e) { if(str_contains($e->getMessage(),'currency')) {echo 'currency blocked'; exit(0);} exit(3); }"
  r=subprocess.run(['php','-r',probe,str(root/'database_bootstrap.php')],env={**env,'TAMASYA_PROPERTY_CURRENCY':'EUR'},capture_output=True,text=True)
  check('Changing deployment currency is rejected against posted USD property',r.returncode==0 and r.stdout=='currency blocked')
  check('Property and posted amount remain USD',sql("SELECT currency FROM property_settings WHERE id='system_default'",db)=='USD' and sql("SELECT amountPaid FROM bookings WHERE id='"+booking+"'",db)=='12.34')
 finally:p.terminate();p.wait(timeout=10)
print('Currency assertions:',len(results))
