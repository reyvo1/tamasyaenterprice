"""Conservative source inventory. Discovery is NEVER evidence of a passed test."""
from pathlib import Path
from html.parser import HTMLParser
import hashlib,json,re
root=Path(__file__).resolve().parents[1];src=root/'work/enterprise';items=[]
def add(kind,file,key,line,detail=''):
    identity=f'{kind}:{file}:{key}'
    items.append({'id':hashlib.sha256(identity.encode()).hexdigest()[:20],
      'kind':kind,'file':file,'key':key,'line':line,'detail':detail[:240],
      'status':'NOT_TESTED','evidence':[]})
class Controls(HTMLParser):
    def __init__(self,file):super().__init__();self.file=file;self.ordinal=0
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag not in ('button','input','select','textarea','form','a'):return
        if tag=='a' and not a.get('href'):return
        if tag=='input' and a.get('type')=='hidden':return
        self.ordinal+=1
        key='#'+a['id'] if a.get('id') else f'{tag}[data-tab="{a["data-tab"]}"]' if a.get('data-tab') else f'{tag}:{self.ordinal}'
        add('html-control',self.file,key,self.getpos()[0],json.dumps(a,ensure_ascii=False))
for path in sorted(src.rglob('*')):
    if not path.is_file():continue
    file=path.relative_to(src).as_posix()
    if path.suffix=='.html':
        add('page',file,file,1);Controls(file).feed(path.read_text())
    if path.suffix=='.php' and 'api/routes/' in file:
        for match in re.finditer(r"\bcase\s+['\"]([^'\"]+)['\"]\s*:",path.read_text()):
            add('api-action-or-command',file,match[1],path.read_text()[:match.start()].count('\n')+1)
    if path.suffix=='.js':
        text=path.read_text()
        # Includes template-generated controls and React compiled event handlers.
        for match in re.finditer(r"(?:onClick|onSubmit|onChange|onclick|onsubmit|onchange)\s*[:=]|data-[a-z-]+(?==)|<button\b",text):
            add('dynamic-control-site',file,str(match.start()),text[:match.start()].count('\n')+1,match[0])
mapping=json.loads((src/'api/domains/MIGRATION_MAP.json').read_text())
for file,domain in mapping.items():add('domain-module',f'api/modules/{domain}/{file}',domain+':'+file,1)
for match in re.finditer(r'callback_data[\"\x27]?\s*=>\s*([\"\x27])(.+?)\1',(src/'api/routes/080_telegram_webhook.php').read_text()):
    add('telegram-callback','api/routes/080_telegram_webhook.php',match[2],1)
add('external-live','telegram','bot-and-designated-uat-chat',1,'User explicitly requested simulator first; no live bot/chat supplied.')
items=list({x['id']:x for x in items}.values())
for item in items:
    if item['kind']=='external-live':item['status']='BLOCKED_LIVE'
report={'scope':'Conservative static inventory; dynamic states, roles, negative/retry/offline flows also need human-reviewed scenario mapping. Not a completeness proof.',
 'fullOperationalUatPassed':False,'total':len(items),'items':items}
out=root/'artifacts';out.mkdir(exist_ok=True)
(out/'coverage-inventory.json').write_text(json.dumps(report,indent=2,ensure_ascii=False))
(out/'coverage-summary.md').write_text('# UAT coverage — NOT COMPLETE\n\n'+report['scope']+'\n\n'+''.join(f'- {kind}: {sum(x["kind"]==kind for x in items)} unverified inventory entries\n' for kind in sorted({x['kind'] for x in items}))+'\nTelegram live: BLOCKED_LIVE. Simulator results do not close this gate.\n')
print('Inventory entries:',len(items),'; full operational UAT: NOT COMPLETE')
