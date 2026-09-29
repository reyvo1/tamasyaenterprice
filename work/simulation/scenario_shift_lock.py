from client import *
from scenario_core import db,state
import subprocess,time
old=db("SELECT require_open_shift_for_sale FROM hotel_operational_settings WHERE id='system_default'")[0]['require_open_shift_for_sale']
try:
 db("UPDATE hotel_operational_settings SET require_open_shift_for_sale=0 WHERE id='system_default'")
 p=subprocess.Popen(['php',str(base/'hold_shift.php')],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
 assert p.stdout.readline().strip()=='LOCKED'
 start=time.monotonic()
 status,b=request('pos-sale-create','POST',{'paymentMethod':'cash','items':[{'productId':state['product_1'],'quantity':1}]},'sim_locked_shift')
 elapsed=time.monotonic()-start;p.wait(timeout=10)
 result={'test':'POS waits for locked shift with optional sale-shift policy disabled','pass':status==200 and elapsed>=3,'details':{'status':status,'elapsedSeconds':round(elapsed,3)}}
 print(result);(base/'logs/shift-lock-results.json').write_text(json.dumps([result],indent=2))
finally:db("UPDATE hotel_operational_settings SET require_open_shift_for_sale=? WHERE id='system_default'",[old])
