#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lit_extract.py — 把 .docx / .md / .txt 转成带段落编号与脚注表的 source.json。

只用标准库（zipfile + xml.etree），不依赖 Word、python-docx 或任何商业软件。
不调用任何模型 API。

用法:
    python scripts/lit_extract.py --input ../materials/x.docx --out ../runs/extract/source.json
    python scripts/lit_extract.py --input a.md --out s.json --plain s.txt

输出 source.json 结构:
{
  "source": {"path","kind","chars","paragraphs","footnotes"},
  "sections": [...],
  "paragraphs": [{"i":1,"role":"body|heading|toc|table","level":0,"section":"...","text":"...","footnotes":["7"],"page":null}],
  "footnotes": {"7": "参见……"},
  "warnings": [...]
}

设计取舍:
1. 页码不猜。.docx 没有固定分页，page 一律为 null；只有输入本身带 [[page:N]] 标记时才填。
2. 脚注从 word/footnotes.xml 读。python-docx 的 paragraphs 读不到脚注，
   而法学论文的引注几乎全在脚注里——漏掉它等于丢掉整条证据链。
3. 旧版 .doc（OLE2 复合文档）不做转换，直接报错并给出可执行替代方案。
"""
import argparse
import json
import os
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
OLE2_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
ZIP_MAGIC = b"PK\x03\x04"

H1_RE = re.compile(r"^(第[一二三四五六七八九十百]+[章节]|[一二三四五六七八九十]+、)\s*\S")
H2_RE = re.compile(r"^[（(][一二三四五六七八九十]+[）)]\s*\S")
H3_RE = re.compile(r"^\d{1,2}[.．、]\s*\S")
SPECIAL_HEADINGS = {"摘要", "关键词", "引言", "绪论", "结论", "参考文献", "Abstract", "Keywords"}
TOC_RE = re.compile(r"(?:[.·…\s]{2,}|\t)\d{1,3}\s*$")
TOC_BLOCK_RE = re.compile(r"(?:[.·…]{2,})\s*\d{1,3}")
PAGE_RE = re.compile(r"^\s*(?:\[\[page:\s*(\d+)\s*\]\]|<!--\s*page\s*(\d+)\s*-->|)\s*$", re.I)


def die(msg, code=2):
    sys.stderr.write("ERROR: " + msg + "\n")
    raise SystemExit(code)


def sniff(path):
    """按文件头判断真实格式，避免把 .doc 当 .docx 打开。"""
    with open(path, "rb") as f:
        head = f.read(8)
    if head.startswith(OLE2_MAGIC):
        return "doc"
    if head.startswith(ZIP_MAGIC):
        return "docx"
    return "text"


def walk_para(el):
    """按文档顺序取一段的文字与脚注引用（跳过修订删除的 w:del 内容）。"""
    text, notes = [], []

    def rec(node, in_del):
        tag = node.tag
        if tag == W + "del":
            in_del = True
        if tag == W + "t":
            if not in_del:
                text.append(node.text or "")
        elif tag == W + "tab":
            text.append("\t")
        elif tag in (W + "br", W + "cr"):
            text.append("\n")
        elif tag == W + "footnoteReference":
            fid = node.get(W + "id")
            if fid is not None:
                notes.append(fid)
        elif tag == W + "footnoteRef":  # 脚注区内的编号占位
            pass
        for child in node:
            rec(child, in_del)

    rec(el, False)
    return "".join(text).strip(), notes


def para_style(el):
    ppr = el.find(W + "pPr")
    if ppr is None:
        return ""
    st = ppr.find(W + "pStyle")
    return st.get(W + "val") if st is not None else ""


def read_docx(path):
    try:
        z = zipfile.ZipFile(path)
    except zipfile.BadZipFile:
        die("文件不是有效的 .docx（可能是改了扩展名的 .doc）。请用 Word 或 LibreOffice 另存为 .docx。")
    if "word/document.xml" not in z.namelist():
        die("缺少 word/document.xml，不是标准 .docx。")

    footnotes = {}
    if "word/footnotes.xml" in z.namelist():
        froot = ET.fromstring(z.read("word/footnotes.xml"))
        for fn in froot.iter(W + "footnote"):
            fid = fn.get(W + "id")
            if fid is None or fn.get(W + "type") in {"separator", "continuationSeparator", "continuationNotice"}:
                continue
            parts = []
            for t in fn.iter(W + "t"):
                parts.append(t.text or "")
            txt = re.sub(r"\s+", " ", "".join(parts)).strip()
            if txt:
                footnotes[str(fid)] = txt

    root = ET.fromstring(z.read("word/document.xml"))
    body = root.find(W + "body")
    if body is None:
        die("document.xml 中没有 w:body。")

    blocks = []  # (kind, text, notes, style)

    def rec_block(el):
        if el.tag == W + "p":
            txt, notes = walk_para(el)
            blocks.append(("p", txt, notes, para_style(el)))
        elif el.tag == W + "tbl":
            for tr in el.findall(W + "tr"):
                cells, cnotes = [], []
                for tc in tr.findall(W + "tc"):
                    cell_txt = []
                    for p in tc.iter(W + "p"):
                        t, n = walk_para(p)
                        if t:
                            cell_txt.append(t)
                        cnotes.extend(n)
                    cells.append(" ".join(cell_txt).strip())
                line = " | ".join([c for c in cells if c])
                if line:
                    blocks.append(("table", line, cnotes, "Table"))
        else:
            for child in el:
                rec_block(child)

    for child in body:
        rec_block(child)
    return blocks, footnotes


FN_DEF_RE = re.compile(r"^\[\^([^\]\s]+)\]:\s*(.+)$")
FN_REF_RE = re.compile(r"\[\^([^\]\s]+)\]")


def read_text(path):
    """读 .md/.txt。

    支持的约定（都可选，不写也照常工作）:
    - 脚注定义行: [^7]: 参见某某……
    - 正文脚注引用: ……某句[^7]
    - 页码标记: [[page:12]] 单独一行（pdf_to_text.py 会自动插入）
    """
    with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
        raw = f.read()

    footnotes, body_lines = {}, []
    derived_from = None
    for line in raw.splitlines():
        m = FN_DEF_RE.match(line.strip())
        if m:
            footnotes[m.group(1)] = m.group(2).strip()
            continue
        m = re.match(r"^\[\[from:(.+)\]\]$", line.strip())
        if m:
            derived_from = m.group(1).strip()
            continue
        body_lines.append(line)
    raw = "\n".join(body_lines)

    blocks = []
    page = None
    for chunk in re.split(r"\n\s*\n", raw):
        lines = [ln.rstrip() for ln in chunk.splitlines() if ln.strip()]
        if not lines:
            continue
        if len(lines) == 1:
            m = PAGE_RE.match(lines[0])
            if m:
                page = int(m.group(1) or m.group(2))
                continue
        text = " ".join(ln.strip() for ln in lines)
        notes = FN_REF_RE.findall(text)
        if notes:
            text = FN_REF_RE.sub("", text)
        m = re.match(r"^(#{1,3})\s+(.*)$", text)
        if m:
            blocks.append(("p", m.group(2).strip(), [], "Heading%d" % len(m.group(1)), page))
            continue
        blocks.append(("p", text, notes, "", page))
    return blocks, footnotes, page, derived_from


def classify(text, style, state):
    """返回 (role, level)；role ∈ body|heading|toc。"""
    st = (style or "").lower()
    if "toc" in st or (TOC_RE.search(text) and len(text) < 80) or re.search(r"[.·…]{3,}\s*\d{1,3}$", text):
        return "toc", 0
    if text.strip() in SPECIAL_HEADINGS:
        return "heading", 1
    if st.startswith("heading") or st in {"1", "2", "3"}:
        lvl = 1
        m = re.search(r"(\d)$", st)
        if m:
            lvl = int(m.group(1))
        return "heading", min(lvl, 3)
    if H1_RE.match(text) and len(text) < 60:
        return "heading", 1
    if H2_RE.match(text) and len(text) < 60:
        return "heading", 2
    if H3_RE.match(text) and len(text) < 40 and "。" not in text:
        return "heading", 3
    return "body", 0


def compute_basis(body, footnotes):
    """判断这篇文献有没有可核验的依据基础。

    规则（任一成立即为 verifiable）：
      脚注 > 0 ／ 正文引注 [n] > 0 ／ 条号 >= 3 ／ 案号 >= 1
    都不成立 → insufficient：没有可回查的定位符，
    此时任何"可否引用"的判断都是空中楼阁，必须降级。
    """
    text = "".join(p["text"] for p in body)
    basis = {
        "footnotes": len(footnotes),
        "in_text_citations": len(re.findall(r"\[\d{1,3}\]", text)),
        "articles": len(re.findall(r"第[一二三四五六七八九十百零〇\d]+条", text)),
        "case_numbers": len(re.findall(r"[（(]\d{4}[）)][^\s，。；]{1,14}?号", text)),
        "law_names": len(re.findall(r"《[^》]{2,40}》", text)),
        "references_section": bool(re.search(r"(参考文献|引用文献|References)", text)),
    }
    ok = (basis["footnotes"] > 0 or basis["in_text_citations"] > 0
          or basis["articles"] >= 3 or basis["case_numbers"] >= 1)
    basis["verdict"] = "verifiable" if ok else "insufficient"
    return basis


def build(path, plain_out=None):
    kind = sniff(path)
    if kind == "doc":
        die("这是旧版 .doc（OLE2 复合文档），本脚本不做格式转换，也不依赖本地 Word。\n"
            "请先另存为 .docx（Word: 文件→另存为→Word 文档 .docx；或 LibreOffice --headless --convert-to docx），再运行。")
    if kind == "docx":
        blocks, footnotes = read_docx(path)
        kind = "docx"
        page = None
        derived_from = None
    else:
        if not re.search(r"\.(md|markdown|txt|text)$", path, re.I):
            die("只支持 .docx / .md / .txt。当前文件: " + os.path.basename(path))
        blocks, footnotes, page, derived_from = read_text(path)
        kind = "text"

    paragraphs, sections, warnings = [], [], []
    path_stack = ["", "", ""]
    page_now = None
    i = 0
    for item in blocks:
        if len(item) == 5:  # 文本输入额外带该段的页码
            bkind, text, notes, style, blk_page = item
        else:
            bkind, text, notes, style = item
            blk_page = None
        if not text:
            continue
        if blk_page is not None:
            page_now = blk_page
        role, level = ("table", 0) if bkind == "table" else classify(text, style, None)
        if role == "body" and (len(TOC_BLOCK_RE.findall(text)) >= 2 or (text.lstrip().startswith("目录") and TOC_BLOCK_RE.search(text))):
            role = "toc"  # 整块目录（点线 + 页码 反复出现）
        if role == "heading":
            path_stack[level - 1] = text.strip()
            for k in range(level, 3):
                path_stack[k] = ""
            sections.append(text.strip())
        i += 1
        sec = " > ".join([s for s in path_stack if s])
        paragraphs.append({
            "i": i,
            "role": role,
            "level": level,
            "section": sec,
            "text": text,
            "footnotes": notes,
            "page": page_now if kind == "text" else None,
        })

    body = [p for p in paragraphs if p["role"] == "body"]
    if not body:
        die("没有解析出正文段落，请检查文件是否为空或结构异常。")

    # 页码是证据锚点：保留跨页片段，阅读时结合相邻段，不把后页文字移到前页。
    if kind == "docx":
        warnings.append("page=null：.docx 无固定分页，禁止在输出中写入页码；改用章节+段号+原句锚点。")
    if len(footnotes) == 0:
        warnings.append("未发现脚注：若文献是立法说明/调研报告，依据多以正文夹注出现（法名、条号、百分比），"
                        "直接按 evidence.locator 抽取即可；若学术论文也查不到注，请确认是否用了尾注或缺文字层。")

    basis = compute_basis(body, footnotes)
    if basis["verdict"] == "insufficient":
        warnings.append(
            "依据基础不足（verdict=insufficient）：脚注 %d、正文引注 %d、条号 %d、案号 %d、参考文献 %s。"
            "该文献无法支撑“可否引用”的判断，只能出命题台账并显式声明不可核验。"
            % (basis["footnotes"], basis["in_text_citations"], basis["articles"],
               basis["case_numbers"], "有" if basis["references_section"] else "无"))

    data = {
        "source": {
            "path": os.path.basename(path),
            "kind": kind,
            "derived_from": derived_from,
            "chars": sum(len(p["text"]) for p in paragraphs),
            "paragraphs": len(paragraphs),
            "body_paragraphs": len(body),
            "footnotes": len(footnotes),
            "sections": len(sections),
        },
        "basis": basis,
        "sections": sections,
        "paragraphs": paragraphs,
        "footnotes": footnotes,
        "warnings": warnings,
    }

    if plain_out:
        with open(plain_out, "w", encoding="utf-8") as f:
            for p in paragraphs:
                nf = ("　注:" + ",".join(p["footnotes"])) if p["footnotes"] else ""
                f.write("[P%d|%s]%s\n%s\n\n" % (p["i"], p["section"] or "-", nf, p["text"]))
    return data


def main():
    ap = argparse.ArgumentParser(description="把 .docx/.md/.txt 转成带段落编号与脚注表的 source.json（仅标准库）")
    ap.add_argument("--input", required=True, help="输入文件（相对路径即可）")
    ap.add_argument("--out", required=True, help="输出 source.json")
    ap.add_argument("--plain", default=None, help="可选：输出带 [Pxx] 段号的可读文本")
    a = ap.parse_args()
    if not os.path.isfile(a.input):
        die("找不到输入文件: " + a.input)
    data = build(a.input, a.plain)
    outdir = os.path.dirname(os.path.abspath(a.out))
    if outdir and not os.path.isdir(outdir):
        os.makedirs(outdir, exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    s = data["source"]
    print(json.dumps({
        "ok": True, "kind": s["kind"], "chars": s["chars"],
        "paragraphs": s["paragraphs"], "body": s["body_paragraphs"],
        "footnotes": s["footnotes"], "sections": s["sections"],
        "out": a.out, "warnings": data["warnings"],
    }, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
