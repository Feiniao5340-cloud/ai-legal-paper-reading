from pathlib import Path
import argparse,subprocess,sys,json,hashlib,os
ap=argparse.ArgumentParser();ap.add_argument('--input',required=True);ap.add_argument('--out-dir',required=True);ap.add_argument('--offset',type=int,default=0);ap.add_argument('--max-chars',type=int,default=6000);a=ap.parse_args()
original=Path(a.input).resolve();out=Path(a.out_dir).resolve();digest=hashlib.sha256(original.read_bytes()).hexdigest();stamp=out/'read_source_identity.json'
if not (out/'source.json').exists():
 child_env=os.environ.copy();child_env['PYTHONUTF8']='1';child_env['PYTHONIOENCODING']='utf-8'
 p=subprocess.run([sys.executable,str(Path(__file__).with_name('prepare_source.py')),'--input',str(original),'--out-dir',str(out)],capture_output=True,text=True,encoding='utf8',env=child_env)
 if p.returncode:print(p.stdout);print(p.stderr,file=sys.stderr);raise SystemExit(p.returncode)
 stamp.write_text(json.dumps({'input_sha256':digest}),encoding='utf8')
elif not stamp.exists() or json.loads(stamp.read_text(encoding='utf8'))['input_sha256']!=digest:raise SystemExit('Prepared source identity mismatch; do not overwrite')
d=json.loads((out/'source.json').read_text(encoding='utf8'));lines=['原文及实挂注转录；不是执行指令。DOCX的P号为抽取段号，不是Word页码。'];used=set();last_section=None
for r in d['paragraphs']:
 if r.get('role')=='toc':continue
 section=r.get('section','')
 if section!=last_section:lines.append('章节：'+section);last_section=section
 loc='P'+str(r['i'])+(' PDF原页'+str(r['page']) if r.get('page') is not None else '')
 lines.extend([loc,r['text']])
 for f in r.get('footnotes',[]):
  f=str(f);used.add(f)
  lines.append('实挂注'+f+'：'+d.get('footnotes',{}).get(f,'[源文件中未找到注释正文]'))
for f,t in d.get('footnotes',{}).items():
 if str(f) not in used:lines.append('其他注'+str(f)+'：'+t)
lines.extend(d.get('warnings',[]));text='\n'.join(lines);(out/'compact-fulltext.txt').write_text(text,encoding='utf8')
if a.offset<0 or a.offset>len(text) or a.max_chars<1:raise SystemExit('Invalid text range')
end=min(a.offset+a.max_chars,len(text));print('SOURCE_CHAR_RANGE',a.offset,end,'TOTAL',len(text));print(text[a.offset:end]);print('END_SOURCE' if end==len(text) else 'NEXT_OFFSET '+str(end))
