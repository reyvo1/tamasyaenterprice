from runtime_tools import mysql_binary, mysqldump_binary, background_process_options, python_command
from client import *
import os,subprocess
runtime=os.environ.copy();runtime.update(json.loads((base/'environment.json').read_text()))
r=subprocess.run(['php',str(base/'site/backup_now.php')],env=runtime,capture_output=True,encoding='utf8')
(base/'logs/backup-result.json').write_text(r.stdout or r.stderr,encoding='utf8')
r.check_returncode();b=json.loads(r.stdout);assert b['success'],b
print('Backup generated:',b['tables'],'tables;',b['triggers'],'triggers;',b['sizeBytes'],'bytes')
mysql=mysql_binary()
args=[mysql,'--defaults-file='+str(base/'client.ini'),'--batch','--skip-column-names']
def sql(s):
 r=subprocess.run(args,input=s,capture_output=True,encoding='utf8');
 if r.returncode:raise RuntimeError(r.stderr)
 return r.stdout
identity=sql('SELECT @@datadir,@@port;').strip().split('\t')
assert Path(identity[0]).resolve()==(base/'mysql-data').resolve() and identity[1]=='33384'
sql('CREATE DATABASE tamasya_restore_sim CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;')
dump=(base/'backups'/b['file']).read_text(encoding='utf8')
assert not __import__('re').search(r'^USE\s|^CREATE DATABASE',dump,__import__('re').M|__import__('re').I)
sql('USE tamasya_restore_sim;\n'+dump)
results=[]
def check(name,ok,detail=None):
 results.append({'test':name,'pass':bool(ok),'details':detail});print('PASS' if ok else 'FAIL',name,detail or '')
tables=sql("SELECT table_name FROM information_schema.tables WHERE table_schema='tamasya_sim' AND table_type='BASE TABLE' ORDER BY table_name").split()
check('Restore contains every source table',sql("SELECT table_name FROM information_schema.tables WHERE table_schema='tamasya_restore_sim' AND table_type='BASE TABLE' ORDER BY table_name").split()==tables,len(tables))
diffs=[]
for t in tables:
 a=sql('SELECT COUNT(*) FROM tamasya_sim.`'+t+'`;').strip();c=sql('SELECT COUNT(*) FROM tamasya_restore_sim.`'+t+'`;').strip()
 if t!='backup_runs' and a!=c:diffs.append([t,a,c])
check('Restored row counts match except post-snapshot backup metadata',not diffs,diffs)
check('Restored triggers match source',sql("SELECT trigger_name FROM information_schema.triggers WHERE trigger_schema='tamasya_sim' ORDER BY trigger_name")==sql("SELECT trigger_name FROM information_schema.triggers WHERE trigger_schema='tamasya_restore_sim' ORDER BY trigger_name"))
check('Restored journals balance',not sql('SELECT journal_entry_id FROM tamasya_restore_sim.journal_lines GROUP BY journal_entry_id HAVING ABS(SUM(debit)-SUM(credit))>0.001').strip())
for t in ['transactions','bookings','pos_products','journal_lines']:
 check('Restored content matches '+t,sql('SELECT * FROM tamasya_sim.`'+t+'` ORDER BY id')==sql('SELECT * FROM tamasya_restore_sim.`'+t+'` ORDER BY id'))
(base/'logs/restore-results.json').write_text(json.dumps(results,indent=2))
