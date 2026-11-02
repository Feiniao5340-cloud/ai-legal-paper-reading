"""Read-only conservative byte, local-link and common credential-pattern checks."""
from pathlib import Path
import json,re,sys,hashlib
from urllib.parse import unquote
root=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path(__file__).resolve().parents[1]
text_suffixes={'.md','.txt','.py','.json','.jsonl','.toml','.yaml','.yml','.csv'};images={'.png','.jpg','.jpeg'}
files=[p for p in root.rglob('*') if p.is_file() and '.git' not in p.parts and '__pycache__' not in p.parts]
rows=[];links=[];suspects=[]
for p in files:
 if p.is_symlink():raise SystemExit('Symbolic link not accepted: '+str(p))
 data=p.read_bytes();name=p.relative_to(root).as_posix()
 if p.suffix.lower() in text_suffixes:
  text=data.decode('utf8');count=len(data) # Include BOM and CRLF bytes; do not undercount by normalizing newlines.
  if len(data)>2*1024**2:raise SystemExit('Text file too large')
  if p.suffix.lower()=='.md':
   for ref in re.findall(r'\]\(([^)]+)\)',text):
    if '://' in ref or ref.startswith('#'):continue
    target=(p.parent/unquote(ref.split('#')[0])).resolve()
    if not target.is_relative_to(root) or not target.is_file():links.append({'file':name,'target':ref})
  patterns=[r'a'+'sp_[A-Za-z0-9]{24,}',r'g'+'hp_[A-Za-z0-9]{25,}',r's'+'k-[A-Za-z0-9_-]{30,}']
  if any(re.search(x,text) for x in patterns):suspects.append(name)
 elif p.suffix.lower() in images:
  count=0
  if len(data)>2*1024**2:raise SystemExit('Image exceeds conservative single-file limit')
  if not (data.startswith(b'\xff\xd8\xff') or data.startswith(b'\x89PNG')):raise SystemExit('Invalid image header')
 else:raise SystemExit('Unsupported material type: '+name)
 rows.append({'path':name,'bytes':len(data),'text_bytes_counted':count,'sha256':hashlib.sha256(data).hexdigest()})
total=sum(x['text_bytes_counted'] for x in rows)
result={'text_bytes_conservative':total,'hard_limit':245760,'recommended_limit':204800,'within_hard_limit':total<=245760,'within_recommended_limit':total<=204800,'file_count':len(rows),'unpacked_bytes':sum(x['bytes'] for x in rows),'missing_links':links,'credential_pattern_matches':suspects,'image_text_policy':'Screenshots duplicate complete visible TXT outputs; all key evidence available as counted text. Image presence alone not used for legal/content claims.','scope':'No PDF/Notebook accepted without explicit extraction. Zero credential matches is not full anonymization proof.','files':rows}
print(json.dumps(result,ensure_ascii=False,indent=2))
if total>245760 or links or suspects:raise SystemExit(2)
