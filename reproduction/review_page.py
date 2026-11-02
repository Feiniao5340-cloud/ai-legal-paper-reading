"""Build a self-contained, escaped review page; never certify semantic accuracy."""
from pathlib import Path
import argparse,html,json,hashlib
from review_cards import decode,inspect,segments

def build(source_path,result_path,out):
    if out.exists():raise ValueError("Output exists; raw evidence is never overwritten")
    if out.suffix.lower()!='.html':raise ValueError("Use a new .html output")
    source=source_path.read_text(encoding='utf8');data=decode(result_path.read_text(encoding='utf8'))
    if not isinstance(data,dict):raise ValueError('Expected object')
    check=inspect(data,source);parts=segments(source)
    esc=lambda x:html.escape(str(x),quote=True)
    pre=lambda x:'<pre>'+esc(x)+'</pre>'
    blocks=['<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>导读与原文回查</title>',
    '<style>body{max-width:1100px;margin:24px auto;padding:0 20px;font:17px/1.7 system-ui;color:#202b33;background:#fafafa}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:inherit;background:white;padding:16px;border:1px solid #ddd}article{border-top:3px solid #789;padding:12px 0}aside{background:#fff0cf;padding:14px}a{color:#145a95}.pair{display:grid;grid-template-columns:1fr 1fr;gap:16px}@media(max-width:750px){.pair{display:block}}</style>',
    '<h1>导读与原文回查</h1><aside>以下导读和关系解释来自原模型回答，未经本页面语义认证。字串匹配只确认文字出现，不能确认谁主张、作者采用或法律效力。本工具不联网、不执行模型回答中的脚本。</aside>',
    '<p><a href="#reader">先读导读</a> · <a href="#cards">核对证据卡</a> · <a href="#source">完整输入片段</a></p>',
    '<h2 id="reader">原模型导读（保留Markdown文本）</h2>',pre(data.get('reader_markdown','')),
    '<h2>检查结果</h2>',pre(json.dumps(check,ensure_ascii=False,indent=2)),
    '<h2 id="cards">逐卡核对：模型解释与源文并排</h2>']
    for i,c in enumerate(data.get('claims',[]) if isinstance(data.get('claims'),list) else []):
        if not isinstance(c,dict):continue
        blocks+=['<article><h3>'+esc(c.get('id',i))+' '+esc(c.get('proposition',''))+'</h3>']
        for axis,title in [('statement_source','表述来源'),('author_attitude','作者态度')]:
            a=c.get(axis,{})
            if not isinstance(a,dict):continue
            seg=a.get('segment','');quote=a.get('quote','')
            matched=next((x.get('matched') for x in check['quote_checks'] if x.get('id')==c.get('id') and x.get('axis')==axis),False)
            blocks+=['<h4>'+title+'：'+('文字命中，关系待核' if matched else '未命中或缺锚点，需回查')+'</h4><div class="pair"><section><b>模型解释及所引文字</b>',pre(json.dumps(a,ensure_ascii=False,indent=2)),'</section><section><b>指定段原文：'+esc(seg)+'</b>',pre(parts.get(seg,'没有这个单一段号；请在完整片段中核对，不能自动拼接。')),'</section></div>']
        blocks += [pre({k:c.get(k) for k in ['support','conditions','uncertainty']}),'<p>人工复核问题：态度究竟针对哪部分？这是作者建议还是现实描述？短引能否支持这一解释？</p></article>']
    blocks+=['<h2 id="source">完整输入片段</h2>',pre(source),'<h2>文件指纹</h2>',pre(json.dumps({'source_sha256':hashlib.sha256(source_path.read_bytes()).hexdigest(),'result_sha256':hashlib.sha256(result_path.read_bytes()).hexdigest(),'semantic_verified':False},indent=2)),'</html>']
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(''.join(blocks),encoding='utf8')
    return check

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--result',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    c=build(a.source,a.result,a.out);print(json.dumps({'page_written':str(a.out),'errors':c['errors'],'semantic_verified':False},ensure_ascii=False))
    if c['errors']:raise SystemExit(2)
if __name__=='__main__':main()
