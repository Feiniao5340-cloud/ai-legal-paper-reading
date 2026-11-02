"""Offline boundary checks. Synthetic fixtures are not model experiments."""
from pathlib import Path
import json,copy
from review_cards import inspect,decode
root=Path(__file__).resolve().parents[1];source=(root/'sources/case-E.txt').read_text(encoding='utf8')
fixture={'reader_markdown':'仅用于离线工具边界测试的合成文字。'*12,'claims':[{'id':'T1','proposition':'合成命题，不是模型结果','statement_source':{'who':'合成标签','segment':'A1','quote':'有鉴于此'},'author_attitude':{'state':'采用','scope':'合成','segment':'A1','quote':'有鉴于此'},'support':'合成','conditions':[],'uncertainty':'合成'}]}
rows=[]
def check(name,data,error=False,warning=False):
 r=inspect(data,source);assert bool(r['errors'])==error and bool(r['warnings'])==warning and r['semantic_verified'] is False
 rows.append({'test':name,'expected_behavior_confirmed':True,'quote_passed':r.get('structure_and_quotes_passed'),'semantic_verified':False})
check('matching synthetic fixture',fixture)
x=copy.deepcopy(fixture);x['claims'][0]['statement_source']['who']='故意错误的语义标签';check('wrong semantic label cannot be caught by quote membership',x)
x=copy.deepcopy(fixture);x['claims'][0]['statement_source']['quote']='伪造的原文短引XYZ';check('invented quote rejected',x,True)
x=copy.deepcopy(fixture);x['claims'][0]['statement_source']['segment']='A1、A2';check('multi-segment string rejected',x,True)
x=copy.deepcopy(fixture);x['claims'][0]['author_attitude']['state']='已外部证实';check('invalid enum rejected',x,True)
x=copy.deepcopy(fixture);x['claims'][0]['author_attitude']['quote']='';check('missing quote left unresolved',x,False,True);assert rows[-1]['quote_passed'] is False
x=copy.deepcopy(fixture);x['claims'][0]['conditions']=17;check('malformed conditions rejected',x,True)
for label in ['A-map','D-map','E-map']:
 data=decode((root/'results'/label/'model-output.txt').read_text(encoding='utf8'));src=(root/'sources'/('case-'+label[0]+'.txt')).read_text(encoding='utf8');r=inspect(data,src)
 assert len(r['errors'])==(2 if label=='E-map' else 0);rows.append({'actual_output':label,'errors_reproduced':r['errors'],'semantic_verified':False})
platform=decode((root/'results/bohrium-new/model-output.txt').read_text(encoding='utf8'));r=inspect(platform,source)
assert len(r['errors'])==1 and len(r['quote_checks'])==14 and sum(x['matched'] for x in r['quote_checks'])==13
rows.append({'actual_output':'Bohrium new Q&A, user-confirmed standard mode','errors_reproduced':r['errors'],'semantic_verified':False})
print(json.dumps({'model_calls':0,'synthetic_and_actual_checks_distinguished':True,'checks':rows},ensure_ascii=False,indent=2))
