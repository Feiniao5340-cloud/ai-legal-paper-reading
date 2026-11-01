"""只读检查文本容量、链接和疑似凭据；不联网、不调用模型。"""
from pathlib import Path
import json,re,sys
from urllib.parse import unquote

root=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path(__file__).resolve().parents[1]
files=[p for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts and '.git' not in p.parts]
sizes=[];links=[];sensitive=[]
for p in files:
    if p.suffix.lower() not in {'.md','.txt','.py','.json','.jsonl','.toml','.yml','.yaml','.csv'}:
        raise SystemExit('存在未计量文件类型：'+str(p.relative_to(root)))
    text=p.read_text(encoding='utf-8-sig')
    sizes.append({'path':p.relative_to(root).as_posix(),'utf8_bytes':len(text.encode('utf8'))})
    if p.suffix=='.md':
        for x in re.findall(r'\]\(([^)]+)\)',text):
            if '://' in x or x.startswith('#'):continue
            target=(p.parent/unquote(x.split('#')[0])).resolve()
            if not target.exists():links.append({'file':p.relative_to(root).as_posix(),'target':x})
    # Exact literal strings are avoided here so the checker does not flag itself.
    pats=[r'a'+'sp_[a-f0-9]{24,}',r's'+'k-[A-Za-z0-9_-]{20,}',r'g'+'hp_[A-Za-z0-9]{25,}']
    if any(re.search(x,text) for x in pats):sensitive.append(p.relative_to(root).as_posix())
total=sum(x['utf8_bytes'] for x in sizes)
print(json.dumps({'total_utf8_bytes':total,'text_limit_bytes':245760,'recommended_limit_bytes':204800,'within_hard_limit':total<=245760,'within_recommended_limit':total<=204800,'file_count':len(files),'missing_local_links':links,'credential_pattern_matches':sensitive,'files':sorted(sizes,key=lambda x:-x['utf8_bytes']),'limits':'检查器只识别列出的凭据形态，零命中不保证完全匿名；暂不接受PDF与Notebook，需另加真实文本提取计量'},ensure_ascii=False,indent=2))
