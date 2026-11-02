"""Render reader text and check evidence-card structure/quotes; never certify semantics."""
from pathlib import Path
import argparse,json,re,unicodedata,hashlib
STATES={'直接主张','采用','不采用或另择','并列保留','未明确'}
def norm(text):return re.sub(r'\s+','',unicodedata.normalize('NFKC',text))
def decode(raw):
 text=raw.strip()
 if text.startswith('```') and text.endswith('```'):text=re.sub(r'^```(?:json)?\s*','',text)[:-3].strip()
 return json.loads(text)
def segments(text):
 parts=re.split(r'(?m)^\[([A-Z]\d+)\][^\n]*\n',text)
 return {parts[i]:parts[i+1].strip() for i in range(1,len(parts)-1,2)}
def inspect(data,source):
 errors=[];warnings=[];checks=[];ids=set();parts=segments(source)
 if not isinstance(data,dict):return {'errors':['Root must be an object'],'warnings':[],'quote_checks':[],'semantic_verified':False}
 if not isinstance(data.get('reader_markdown'),str) or len(data['reader_markdown'].strip())<80:errors.append('Missing substantial reader_markdown')
 claims=data.get('claims')
 if not isinstance(claims,list) or not claims:errors.append('No evidence cards');claims=[]
 for index,card in enumerate(claims):
  label='card '+str(index+1)
  if not isinstance(card,dict):errors.append(label+': not an object');continue
  cid=card.get('id');label=str(cid or label)
  if not isinstance(cid,str) or not cid or cid in ids:errors.append(label+': missing/duplicate id')
  if isinstance(cid,str):ids.add(cid)
  for field in ['proposition','support','uncertainty']:
   if not isinstance(card.get(field),str) or not card[field].strip():errors.append(label+': missing '+field)
  if not isinstance(card.get('conditions'),list) or any(not isinstance(x,str) for x in card.get('conditions',[])):errors.append(label+': invalid conditions')
  for axis in ['statement_source','author_attitude']:
   value=card.get(axis)
   if not isinstance(value,dict):errors.append(label+': missing '+axis);continue
   required=['who'] if axis=='statement_source' else ['state','scope']
   if any(not isinstance(value.get(k),str) or not value[k].strip() for k in required):errors.append(label+': missing axis description '+axis)
   if axis=='author_attitude' and value.get('state') not in STATES:errors.append(label+': invalid attitude enum')
   seg=value.get('segment');quote=value.get('quote')
   if not isinstance(seg,str) or not isinstance(quote,str):errors.append(label+': invalid anchor type '+axis);continue
   if not quote.strip() or not seg.strip():
    warnings.append(label+': '+axis+' anchor missing; requires reading review');checks.append({'id':cid,'axis':axis,'matched':False,'reason':'missing anchor'});continue
   matched=seg in parts and norm(quote) in norm(parts[seg])
   checks.append({'id':cid,'axis':axis,'segment':seg,'quote':quote,'matched':matched})
   if not matched:errors.append(label+': '+axis+' quote not found in specified segment')
 return {'structure_and_quotes_passed':not errors and all(x['matched'] for x in checks),'errors':errors,'warnings':warnings,'quote_checks':checks,'semantic_verified':False,'limits':'Only shape, enum and NFKC/whitespace-normalized substring membership checked. A match does not verify attribution, adoption, reasoning, legal validity or effectiveness.'}
def render(data,source):
 check=inspect(data,source);cards=['# 证据卡回查\n','本页为模型提供的关系解释；短引核字不等于语义已核实。\n']
 for c in data.get('claims',[]) if isinstance(data,dict) and isinstance(data.get('claims'),list) else []:
  if not isinstance(c,dict):continue
  cards+=['## '+str(c.get('id','?'))+' '+str(c.get('proposition',''))]
  for axis,title in [('statement_source','表述来源'),('author_attitude','作者态度')]:
   a=c.get(axis,{})
   if isinstance(a,dict):cards += [title+'：'+str(a.get('who',a.get('state','')))+'；'+str(a.get('scope','')),str(a.get('segment',''))+' 原文短引：'+str(a.get('quote',''))]
  conditions=c.get('conditions',[])
  if not isinstance(conditions,list):conditions=[]
  cards+=['支持关系：'+str(c.get('support','')),'条件：'+'；'.join(map(str,conditions)),'未决：'+str(c.get('uncertainty',''))]
 return check,'\n\n'.join(cards)+'\n'
def deliver(source_path,result_path,out):
 if out.exists():raise ValueError('Output exists; no overwrite')
 source=source_path.read_text(encoding='utf8');data=decode(result_path.read_text(encoding='utf8'))
 if not isinstance(data,dict):raise ValueError('Result root must be an object; raw result retained')
 check,cards=render(data,source)
 out.mkdir(parents=True);(out/'reading.md').write_text(data.get('reader_markdown','')+'\n',encoding='utf8');(out/'evidence-cards.md').write_text(cards,encoding='utf8')
 check.update({'source_sha256':hashlib.sha256(source_path.read_bytes()).hexdigest(),'actual_result_sha256':hashlib.sha256(result_path.read_bytes()).hexdigest()});(out/'checks.json').write_text(json.dumps(check,ensure_ascii=False,indent=2),encoding='utf8');return check
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--source',type=Path,required=True);ap.add_argument('--result',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();result=deliver(a.source,a.result,a.out);print(json.dumps(result,ensure_ascii=False,indent=2))
 if result['errors']:raise SystemExit(2)
if __name__=='__main__':main()
