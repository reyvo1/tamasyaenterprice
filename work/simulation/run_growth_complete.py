from pathlib import Path
import subprocess,json,datetime
from runtime_tools import python_command
b=Path(__file__).resolve().parent;started=datetime.datetime.now(datetime.timezone.utc).isoformat();suites=[]
for name,result in [
 ('scenario_growth_procurement.py','growth-procurement-results.json'),('scenario_growth_folio_rates.py','growth-folio-rate-results.json'),
 ('scenario_growth_crm.py','growth-crm-results.json'),('scenario_crm_delivery.py','growth-crm-delivery-results.json'),
 ('scenario_growth_payments.py','growth-payment-results.json'),('scenario_growth_payroll.py','growth-payroll-results.json'),
 ('scenario_growth_groups.py','growth-group-results.json'),('scenario_hq_v3.py','growth-hq-v3-results.json'),('scenario_provider_bridge.py','provider-bridge-results.json')]:
 print('RUN',name,flush=True);r=subprocess.run([python_command(),'-u',str(b/name)],capture_output=True,text=True,encoding='utf-8');(b/'logs'/('fresh-'+name+'.txt')).write_text(r.stdout+r.stderr,encoding='utf-8');print((r.stdout+r.stderr)[-700:],flush=True);r.check_returncode()
 rows=json.loads((b/result).read_text(encoding='utf-8'));assert rows and all(x['pass'] for x in rows)
 suites.append({'suite':name,'passed':len(rows),'result':result});(b/'growth-complete-results.json').write_text(json.dumps({'startedAt':started,'suites':suites},indent=2),encoding='utf-8')
print('ALL FRESH GROWTH SCENARIOS PASSED',sum(x['passed'] for x in suites),flush=True)
