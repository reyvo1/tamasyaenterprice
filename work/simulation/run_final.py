from runtime_tools import mysql_binary, mysqldump_binary, background_process_options, python_command
from pathlib import Path
import json,subprocess,shutil,datetime,sys
sys.stdout.reconfigure(encoding="utf-8")
b=Path(__file__).resolve().parent
if len(sys.argv)==1:
 archive=b/'logs'/('before-r45-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'));archive.mkdir()
 for p in (b/'logs').glob('*results.json'):shutil.copy2(p,archive/p.name)
 # reset.py first checks the exact datadir and port of the disposable MySQL instance.
 r=subprocess.run([python_command(),'-u',str(b/'reset.py')]);r.check_returncode()
 mysql=mysql_binary()
 r=subprocess.run([mysql,'--defaults-file='+str(b/'client.ini')],input='DROP DATABASE IF EXISTS tamasya_restore_sim;',text=True,capture_output=True);r.check_returncode()
for script,log in [
 ('setup.py',None),('client.py login',None),('scenario_setup.py','setup-results.json'),
 ('scenario_core.py','core-results.json'),('scenario_finance.py','finance-results.json'),
 ('scenario_operations.py','operations-results.json'),('scenario_concurrency.py','concurrency-results.json'),
 ('scenario_shift_lock.py','shift-lock-results.json'),('scenario_extended.py','extended-finance-results.json'),
 ('scenario_allocations.py','allocation-results.json'),('scenario_settlement_sync.py','settlement-sync-results.json'),
 ('scenario_controls.py','finance-controls-results.json'),('scenario_accounting_reports.py','accounting-report-results.json'),
 ('scenario_tax_edges.py','tax-edge-results.json'),('scenario_integrity.py','shift-integrity-results.json'),
 ('scenario_exports.py','report-export-results.json'),('scenario_backup.py','restore-results.json')]:
 if len(sys.argv)>1:
  if script!=sys.argv[1]:continue
  sys.argv=[sys.argv[0]]
 parts=script.split();print('\nRUN',script,flush=True)
 r=subprocess.run([python_command(),'-u',str(b/parts[0])]+parts[1:],capture_output=True,encoding='utf8')
 (b/'logs'/('final-'+parts[0]+'.txt')).write_text(r.stdout+r.stderr,encoding='utf8')
 print((r.stdout+r.stderr)[-1300:],flush=True);r.check_returncode()
 if log:
  rows=json.loads((b/'logs'/log).read_text(encoding='utf8'));bad=[x for x in rows if not x['pass']]
  print('VERIFIED',len(rows),'checks, failures',len(bad),flush=True)
  if bad:raise RuntimeError(str(bad))
print('ALL FRESH DATABASE SCENARIOS PASSED',flush=True)
