from runtime_tools import mysql_binary, mysqldump_binary, background_process_options, python_command
from client import *
from scenario_core import db,state
import subprocess,os,concurrent.futures,datetime,time
runtime=os.environ.copy();runtime.update(json.loads((base/'environment.json').read_text()))
log=open(base/'logs/php-second.log','ab')
p=subprocess.Popen(['php','-S','127.0.0.1:28185','-t',str(base/'site')],env=runtime,stdout=log,stderr=log,**background_process_options())
results=[]
def check(name,ok,detail=None):
 results.append({'test':name,'pass':bool(ok),'details':detail});print('PASS' if ok else 'FAIL',name,detail or '')
try:
 time.sleep(1)
 future=datetime.date.today()+datetime.timedelta(days=20)
 payload={'guestName':'SIM Concurrent Guest','roomNumber':'103','checkIn':str(future),'checkOut':str(future+datetime.timedelta(days=1)),'totalAmount':220000,'paymentStatus':'unpaid','broadcast':False}
 with concurrent.futures.ThreadPoolExecutor(2) as pool:
  jobs=[pool.submit(request,'bookings','POST',payload,'sim_concurrent_'+str(i),port=28184+i) for i in range(2)]
  replies=[j.result() for j in jobs]
 check('Concurrent overlapping reservation has one winner',sorted(r[0] for r in replies)==[200,409],[r[0] for r in replies])
 check('Concurrent booking writes one row',db('SELECT COUNT(*) n FROM bookings WHERE guestName=?',['SIM Concurrent Guest'])[0]['n']==1)
 cart={'paymentMethod':'cash','items':[{'productId':state['product_1'],'quantity':1}]}
 before=db('SELECT COUNT(*) n FROM pos_sales')[0]['n']
 with concurrent.futures.ThreadPoolExecutor(2) as pool:
  jobs=[pool.submit(request,'pos-sale-create','POST',cart,'sim_concurrent_same_sale',port=28184+i) for i in range(2)]
  replies=[j.result() for j in jobs]
 check('Concurrent operation creates one sale',db('SELECT COUNT(*) n FROM pos_sales')[0]['n']==before+1,[r[0] for r in replies])
 status,body=request('pos-sale-create','POST',cart,'sim_concurrent_same_sale')
 check('Concurrent operation retry resolves successfully',status==200 and body.get('success') is True,status)
 check('Concurrent sale retry remains one sale',db('SELECT COUNT(*) n FROM pos_sales')[0]['n']==before+1)
finally:
 p.terminate();p.wait(timeout=10)
 (base/'logs/concurrency-results.json').write_text(json.dumps(results,indent=2))

