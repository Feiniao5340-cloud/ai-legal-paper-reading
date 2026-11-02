"""Find an exact source phrase after Unicode/whitespace normalization; not semantic verification."""
from pathlib import Path
import argparse,json,re,unicodedata,hashlib
def norm(s):return re.sub(r'\s+','',unicodedata.normalize('NFKC',s))
def find(source,quote):
 text=source.read_text(encoding='utf8');needle=norm(quote)
 if not needle:raise ValueError('Empty quote')
 parts=re.split(r'(?m)^(?=\[[ABCS]\d+\])',text);matches=[]
 for part in parts:
  clean=norm(part);offset=clean.find(needle)
  if offset>=0:matches.append({'segment':part.splitlines()[0],'normalized_offset':offset,'context':clean[max(0,offset-70):offset+len(needle)+70]})
 return {'quote':quote,'found':bool(matches),'matches':matches,'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'normalization':'Unicode NFKC and whitespace only; no word substitution or synonym matching','scope':'Exact text presence in supplied excerpt only. A match does not verify attribution, legal meaning, validity or efficacy. No match does not prove full-paper absence.'}
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--source',type=Path,required=True);ap.add_argument('--quote',required=True);a=ap.parse_args()
 print(json.dumps(find(a.source.resolve(),a.quote),ensure_ascii=False,indent=2))
if __name__=='__main__':main()
