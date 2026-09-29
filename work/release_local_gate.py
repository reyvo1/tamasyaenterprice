"""Run recovered integration harness against a fresh isolated Linux fixture.

No existing MySQL data directory or credentials are reused. Artifacts and logs
are retained in a new work/release-local-* directory, including on failure.
"""
from pathlib import Path
import datetime, hashlib, json, os, secrets, shutil, signal, socket, subprocess, sys, tempfile, time, zipfile

work = Path(__file__).resolve().parent
stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
run = work / ('release-local-' + stamp)
run.mkdir(mode=0o700)
sim = run / 'simulation'
sim.mkdir()
(sim / 'logs').mkdir()
(sim / 'backups').mkdir()
source = run / 'enterprise'
candidate = run / 'candidate.zip'
with zipfile.ZipFile(candidate, 'w', zipfile.ZIP_DEFLATED) as archive:
    for path in sorted((work / 'enterprise').rglob('*')):
        if path.is_file(): archive.write(path, path.relative_to(work / 'enterprise'))
with zipfile.ZipFile(candidate) as archive: archive.extractall(source)
for path in (work / 'simulation').iterdir():
    if path.is_file() and path.suffix in ('.py', '.php') and 'credentials' not in path.name:
        shutil.copy2(path, sim / path.name)
env = {**os.environ, 'TAMASYA_TEST_SOURCE': str(source),
       'TAMASYA_MYSQL_DATADIR': str(sim / 'mysql-data')}
children = []
mysql_temp = Path(tempfile.mkdtemp(prefix='tamasya-mysql-'))
(run / 'mysql-runtime-path.txt').write_text(str(mysql_temp))
results = []
password = secrets.token_hex(24)
(sim / 'credentials.json').write_text(json.dumps({'user': 'tamasya_sim', 'password': password}))
(sim / 'client.ini').write_text('[client]\nhost=127.0.0.1\nport=33384\nuser=root\npassword='+password+'\ndefault-character-set=utf8mb4\n')
(sim / 'client.ini').chmod(0o600)

def ready(port):
    for _ in range(200):
        try:
            with socket.create_connection(('127.0.0.1', port), timeout=.2): return
        except OSError: time.sleep(.1)
    raise RuntimeError(f'Port {port} did not become ready')

def script(name, *args):
    print('RUN', name, flush=True)
    result = subprocess.run([sys.executable, '-u', str(sim / name), *args], env=env,
                            capture_output=True, text=True, timeout=1200)
    (sim / 'logs' / ('gate-' + name + '.txt')).write_text(result.stdout + result.stderr)
    print((result.stdout + result.stderr)[-1800:], flush=True)
    results.append({'script': name, 'exitCode': result.returncode})
    (run / 'gate-progress.json').write_text(json.dumps(results, indent=2))
    result.check_returncode()

def stop_php(pidfile, document_root):
    path = Path(pidfile)
    if not path.exists(): return
    pid = int(path.read_text())
    proc = Path('/proc') / str(pid) / 'cmdline'
    if not proc.exists(): return
    command = proc.read_bytes().split(b'\0')
    if b'-S' not in command or str(document_root).encode() not in command:
        raise RuntimeError('Refusing to stop an unrecognized process')
    os.kill(pid, signal.SIGTERM)
    for _ in range(100):
        if not proc.exists(): return
        time.sleep(.05)

def sql(statement, initial=False):
    args = ['mysql', '--no-defaults', '--socket=' + str(mysql_temp / 'mysql.sock'), '-uroot'] if initial else ['mysql', '--defaults-file=' + str(sim / 'client.ini')]
    result = subprocess.run(args, input=statement, text=True, capture_output=True)
    if result.returncode: raise RuntimeError(result.stderr)

try:
    for port in [33384, 38184, 38185, 38186, 38189, 38190, 38191, 38192, 38193, 38194, 38200]:
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', port))
    data = mysql_temp / 'data'
    data.mkdir()
    (sim / 'mysql-data').symlink_to(data, target_is_directory=True)
    env['TAMASYA_MYSQL_DATADIR'] = str(data)
    subprocess.run(['mysqld', '--no-defaults', '--initialize-insecure', '--datadir='+str(data),
                    '--log-error='+str(mysql_temp/'mysql-init.log')], check=True)
    mysql = subprocess.Popen(['mysqld', '--no-defaults', '--datadir='+str(data),
        '--socket='+str(mysql_temp/'mysql.sock'), '--pid-file='+str(mysql_temp/'mysql.pid'),
        '--port=33384', '--bind-address=127.0.0.1', '--mysqlx=OFF', '--skip-log-bin',
        '--secure-file-priv='+str(mysql_temp), '--log-error='+str(mysql_temp/'mysql.log')])
    children.append(mysql)
    ready(33384)
    sql("ALTER USER 'root'@'localhost' IDENTIFIED BY '"+password+"'; CREATE USER 'root'@'127.0.0.1' IDENTIFIED BY '"+password+"'; GRANT ALL ON *.* TO 'root'@'127.0.0.1' WITH GRANT OPTION; CREATE USER 'tamasya_sim'@'127.0.0.1' IDENTIFIED BY '"+password+"'; GRANT ALL ON tamasya_sim.* TO 'tamasya_sim'@'127.0.0.1';", initial=True)
    script('run_final.py')
    script('prepare_growth_fixture.py')
    ready(38189)
    script('growth_client.py')
    script('run_growth_complete.py')
    script('scenario_currency.py')
    script('scenario_interproperty.py')
    script('scenario_ha_pair.py')
    print('CORE, GROWTH, USD, INTERPROPERTY, HA GATES PASSED', run, flush=True)
finally:
    for pidfile, root in [(sim/'php.pid', sim/'site'), (run/'simulation-growth/php.pid', run/'simulation-growth/site')]:
        stop_php(pidfile, root)
    for process in reversed(children):
        subprocess.run(['mysqladmin','--defaults-file='+str(sim/'client.ini'),'shutdown'],check=True)
        process.wait(timeout=30)
    for log in mysql_temp.glob('*.log'): shutil.copy2(log, sim / 'logs' / log.name)
    print('Evidence retained:', run, flush=True)
