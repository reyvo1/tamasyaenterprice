from runtime_tools import mysql_binary, mysqldump_binary, background_process_options, python_command
from pathlib import Path
import os,json,subprocess,shutil
b=Path(__file__).resolve().parent
shutil.copytree(b.parent/'enterprise',b/'site',dirs_exist_ok=True)
env={**os.environ,**json.loads((b/'enterprise-environment.json').read_text())}
commands=[
 [python_command(),str(b/'scenario_hybrid_failures.py')],
 [python_command(),str(b/'scenario_hybrid_pagination.py')],
 [python_command(),str(b/'scenario_control.py')],
 [python_command(),str(b/'scenario_enterprise_worker.py')],
 [python_command(),str(b/'scenario_enterprise_reports.py')],
 [python_command(),str(b/'scenario_delivery.py')],
 [python_command(),str(b/'scenario_object_storage.py')],
 ['php',str(b/'scenario_ha_commit.php')],
 [python_command(),str(b/'scenario_hq_permissions.py')],
]
for command in commands:
 print('RUN',Path(command[1]).name,flush=True)
 r=subprocess.run(command,env=env,capture_output=True,text=True,encoding='utf-8');(b/'logs'/('enterprise-'+Path(command[1]).stem+'.txt')).write_text(r.stdout+r.stderr,encoding='utf-8')
 print((r.stdout+r.stderr)[-1100:],flush=True);r.check_returncode()
print('ENTERPRISE EXTRA SCENARIOS PASSED',flush=True)
