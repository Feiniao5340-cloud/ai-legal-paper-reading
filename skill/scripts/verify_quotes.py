"""核对短引句的源段、原页与实际挂注；不判断语义或外部法源。"""
import argparse,copy,json,re
from pathlib import Path

def norm(text):
    return re.sub(r'\s+','',text).translate(str.maketrans({'“':'"','”':'"','‘':"'",'’':"'"}))

def check(source,quotes):
    errors=[];resolved=[]
    if not isinstance(quotes,list) or not quotes:return {'ok':False,'errors':['quotes须为非空数组'],'quotes_checked':0,'quotes_located':0,'semantic_support_checked':False}
    paras={p['i']:p for p in source['paragraphs']}
    for i,row in enumerate(quotes,1):
        if not isinstance(row,dict) or type(row.get('para')) is not int:
            errors.append(str(i)+'：缺真实源段号');continue
        p=paras.get(row['para']);q=row.get('quote')
        if not p or not isinstance(q,str) or not norm(q) or norm(q) not in norm(p['text']):
            errors.append(str(i)+'：原句未在指定段命中');continue
        if 'page' in row and row['page']!=p.get('page'):
            errors.append(str(i)+'：显式原页错误');continue
        if 'section' in row and row['section']!=p.get('section'):
            errors.append(str(i)+'：显式章节错误');continue
        actual={str(n):source.get('footnotes',{}).get(str(n)) for n in p.get('footnotes',[])}
        if 'footnote_ids' in row and (not isinstance(row['footnote_ids'],list) or any(str(n) not in actual for n in row['footnote_ids'])):
            errors.append(str(i)+'：脚注未挂在该段');continue
        item=copy.deepcopy(row);item.update({'page':p.get('page'),'section':p.get('section'),'attached_footnotes':actual});resolved.append(item)
    return {'ok':not errors,'errors':errors,'quotes_checked':len(quotes),'quotes_located':len(resolved),'resolved_quotes':resolved,'semantic_support_checked':False,'note':'仅核对本次文字索引位置及实挂脚注。原句命中不等于解释正确、依据充分或外部内容已核。'}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ['source','quotes','out']:ap.add_argument('--'+name,required=True)
    a=ap.parse_args();inputs=[Path(a.source).resolve(),Path(a.quotes).resolve()];out=Path(a.out).resolve()
    if out in inputs:raise SystemExit('不覆盖输入文件')
    try:result=check(json.loads(inputs[0].read_text(encoding='utf-8-sig')),json.loads(inputs[1].read_text(encoding='utf-8-sig')))
    except (ValueError,KeyError,TypeError,OSError) as e:result={'ok':False,'errors':[str(e)],'quotes_checked':0,'quotes_located':0,'semantic_support_checked':False}
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in result.items() if k!='resolved_quotes'},ensure_ascii=False))
    raise SystemExit(0 if result['ok'] else 2)

if __name__=='__main__':main()
