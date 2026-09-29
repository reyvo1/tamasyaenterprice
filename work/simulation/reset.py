from runtime_tools import mysql_binary, mysqldump_binary, background_process_options, python_command
from pathlib import Path
import subprocess,shutil,json,os
base=Path(__file__).resolve().parent
mysql=mysql_binary()
args=[mysql,'--defaults-file='+str(base/'client.ini'),'--batch','--skip-column-names']
def sql(s):
 r=subprocess.run(args,input=s,capture_output=True,encoding='utf8');r.check_returncode();return r.stdout
identity=sql('SELECT @@datadir,@@port;').strip().split('\t')
assert Path(identity[0]).resolve()==(base/'mysql-data').resolve() and identity[1]=='33384',identity
saved=base/'logs/before-fixes';saved.mkdir(exist_ok=True)
for p in (base/'logs').glob('*results.json'):shutil.copy2(p,saved/p.name)
sql('DROP DATABASE IF EXISTS tamasya_sim; CREATE DATABASE tamasya_sim CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;')
test_source=Path(os.environ.get('TAMASYA_TEST_SOURCE',str(base.parent/'audit'))).resolve()
assert test_source in [(base.parent/name).resolve() for name in ['audit','hybrid','enterprise','enterprise-release-check']]
sql('USE tamasya_sim;\n'+(test_source/'database_setup.sql').read_text(encoding='utf-8-sig'))
print('Verified isolated server; fresh schema imported.')
