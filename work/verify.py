from pathlib import Path
import subprocess,json,re,hashlib,sys
from html.parser import HTMLParser
from urllib.parse import unquote,urlsplit
root=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).parent/'audit'
scratch=Path(__file__).parent/'inline-checks';scratch.mkdir(exist_ok=True)
results=[];missing=[];inline=[]
class Page(HTMLParser):
 def __init__(self,file):super().__init__();self.file=file;self.active=False;self.buf=[];self.n=0;self.module=False
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  for k in (['src'] if tag in ['script','img','iframe'] else ['href'] if tag=='link' else []):
   ref=a.get(k,'');u=urlsplit(ref)
   if ref and not u.scheme and not u.netloc and not ref.startswith(('#','data:','/')):
    target=self.file.parent/unquote(u.path)
    if not target.exists():missing.append({'file':str(self.file.relative_to(root)),'reference':ref})
  if tag=='script' and not a.get('src') and a.get('type','') in ('','module','text/javascript','application/javascript'):
   self.active=True;self.buf=[];self.module=a.get('type')=='module'
 def handle_data(self,data):
  if self.active:self.buf.append(data)
 def handle_endtag(self,tag):
  if tag=='script' and self.active:
   self.active=False;self.n+=1
   f=scratch/(str(self.file.relative_to(root)).replace('\\','_').replace('/','_')+f'-{self.n}.mjs')
   f.write_text(''.join(self.buf),encoding='utf-8');r=subprocess.run(['node','--check',str(f)],capture_output=True,text=True)
   inline.append({'page':self.file.relative_to(root).as_posix(),'script':self.n,'ok':r.returncode==0,'error':r.stderr})
for f in sorted(root.rglob('*')):
 if not f.is_file():continue
 rel=f.relative_to(root).as_posix();ext=f.suffix
 row={'file':rel,'bytes':f.stat().st_size,'sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'verification':'inventory only'}
 if ext in ('.php','.js','.mjs'):
  cmd=['php','-l',str(f)] if ext=='.php' else ['node','--check',str(f)]
  r=subprocess.run(cmd,capture_output=True,text=True)
  row.update(verification='syntax',ok=r.returncode==0)
  if r.returncode:row['error']=r.stdout+r.stderr
  if ext in ('.js','.mjs'):
   text=f.read_text(encoding='utf-8-sig')
   for ref in re.findall(r'''(?:\bfrom\s*|\bimport\s*\(\s*)['"](\.[^'"]+)['"]''',text):
    if not (f.parent/urlsplit(ref).path).exists():missing.append({'file':rel,'reference':ref})
 elif ext in ('.json','.webmanifest'):
  try:json.loads(f.read_text(encoding='utf-8-sig'));row.update(verification='JSON parse',ok=True)
  except Exception as e:row.update(verification='JSON parse',ok=False,error=str(e))
 elif ext=='.html':Page(f).feed(f.read_text(encoding='utf-8-sig'));row['verification']='local asset references and inline JavaScript syntax'
 results.append(row)
sw=(root/'sw.js').read_text(encoding='utf-8')
precache=re.search(r'const ASSETS_TO_CACHE = \[(.*?)\];',sw,re.S).group(1)
for ref in re.findall(r'"(\./[^"\n]*)"',precache):
 if not (root/urlsplit(ref).path).exists():missing.append({'file':'sw.js','reference':ref})
mapping=json.loads((root/'api/domains/MIGRATION_MAP.json').read_text())
for basename,domain in mapping.items():
 if not (root/'api/modules'/domain/basename).exists() and not (root/'api/support'/basename).exists():missing.append({'file':'MIGRATION_MAP.json','reference':basename})
summary={'files':len(results),'php':sum(r['file'].endswith('.php') for r in results),'javascript':sum(r['file'].endswith(('.js','.mjs')) for r in results),'inlineScripts':len(inline),'syntaxOrParseFailures':sum(r.get('ok') is False for r in results+inline),'missingReferences':missing}
report={'summary':summary,'files':results,'inlineScripts':inline}
(Path(__file__).parent/'verification.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps(summary,indent=2))
