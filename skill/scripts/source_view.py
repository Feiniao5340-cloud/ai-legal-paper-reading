#!/usr/bin/env python3
"""按源段号显示原句、位置与真实挂接脚注；不生成语义判断。"""
import argparse,json
from pathlib import Path
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source',required=True)
    ap.add_argument('--paras',required=True,help='逗号分隔的源段号')
    a=ap.parse_args()
    source=json.loads(Path(a.source).read_text(encoding='utf-8-sig'))
    paras={p['i']:p for p in source['paragraphs']}
    try:ids=list(dict.fromkeys(int(n.strip()) for n in a.paras.split(',') if n.strip()))
    except ValueError:raise SystemExit('ERROR: 段号必须是逗号分隔整数')
    if not ids or any(n not in paras for n in ids):raise SystemExit('ERROR: 所选源段不存在')
    for n in ids:
        p=paras[n]
        print(json.dumps({'paragraph':p,'attached_footnotes':{str(fid):source.get('footnotes',{}).get(str(fid)) for fid in p.get('footnotes',[])}},ensure_ascii=False))
if __name__=='__main__':main()
