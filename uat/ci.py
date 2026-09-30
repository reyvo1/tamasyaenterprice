"""Run disposable integration gates; publish only allowlisted sanitized results."""
from pathlib import Path
import json,os,re,subprocess,sys
root=Path(__file__).resolve().parents[1];work=root/'work';out=root/'artifacts';out.mkdir(exist_ok=True)
def command(args):
    # Raw fixture output may contain private generated tokens. Never stream it to public CI logs.
    p=subprocess.run(args,cwd=root,capture_output=True,text=True)
    private=work/'ci-private';private.mkdir(mode=0o700,exist_ok=True)
    (private/(Path(args[1]).name+'.log')).write_text(p.stdout+p.stderr)
    print(Path(args[1]).name, 'PASS' if p.returncode==0 else 'FAIL',flush=True)
    if p.returncode:
        # Publish code locations/type only, never exception payloads or raw responses.
        frames=re.findall(r'File "[^"]*/([^/"\n]+)", line (\d+)',p.stdout+p.stderr)
        types=re.findall(r'^([A-Za-z]+(?:Error|Exception)):',p.stdout+p.stderr,re.M)
        diagnostic={'stage':Path(args[1]).name,'exitCode':p.returncode,'frames':frames[-25:],'exceptionTypes':types[-10:]}
        (out/'failure-location.json').write_text(json.dumps(diagnostic,indent=2));print(json.dumps(diagnostic))
    if p.returncode:raise RuntimeError('Fixture step failed; see sanitized stage report, not private raw logs.')
before=set(work.glob('release-local-*'));run=None
try:
    command([sys.executable,str(work/'check_enterprise_current.py'),str(work/'enterprise'),str(out/'unit-results.json')])
    command([sys.executable,str(work/'release_local_gate.py')])
    created=set(work.glob('release-local-*'))-before;assert len(created)==1;run=created.pop()
    command([sys.executable,str(work/'release_enterprise_gate.py'),str(run)])
    command([sys.executable,str(root/'uat/browser_fixture.py'),str(run)])
finally:
    candidates=set(work.glob('release-local-*'))-before
    if len(candidates)==1:
        run=candidates.pop();sim=run/'simulation';summary=[]
        for p in list(sim.glob('*-results.json'))+list((sim/'logs').glob('*-results.json')):
            data=json.loads(p.read_text())
            if not isinstance(data,list) or not all(isinstance(x,dict) and isinstance(x.get('pass'),bool) for x in data):continue
            safe=[{'test':x.get('test',x.get('name','unnamed')),'pass':x['pass']} for x in data]
            (out/p.name).write_text(json.dumps(safe,indent=2))
            summary.append({'suite':p.stem,'passed':sum(x['pass'] for x in safe),'failed':sum(not x['pass'] for x in safe)})
        for name in ['gate-progress.json','enterprise-gate-progress.json']:
            if (run/name).exists():(out/name).write_text((run/name).read_text())
        diagnostics=[]
        for log in list((sim/'logs').glob('*.txt'))+list((run/'simulation-growth/logs').glob('*.log')):
            text=log.read_text(errors='replace')
            signals={key:len(re.findall(pattern,text,re.I)) for key,pattern in {
                'connection_refused':'Connection refused','connection_reset':'Connection reset',
                'timed_out':'timed out','php_fatal':'Fatal error','php_memory':'Allowed memory size',
                'segmentation_fault':'Segmentation fault','address_in_use':'Address already in use',
                'sql_error':'SQLSTATE','http_500':r'\[500\]',
            }.items()}
            frames=re.findall(r'File "[^"\n]*/([^/"\n]+)", line (\d+)',text)
            if any(signals.values()) or frames:diagnostics.append({'log':log.name,'signals':signals,'frames':frames[-25:]})
        (out/'diagnostic-signals.json').write_text(json.dumps(diagnostics,indent=2))
        (out/'integration-summary.json').write_text(json.dumps(summary,indent=2))
        print('Assertions recorded:',sum(x['passed'] for x in summary),'passed;',sum(x['failed'] for x in summary),'failed')
    # Unit output is unnecessary for public artifacts; retain names/counts only.
    p=out/'unit-results.json'
    if p.exists():
        d=json.loads(p.read_text())
        for x in d.get('units',[]):x.pop('output',None)
        p.write_text(json.dumps(d,indent=2))
