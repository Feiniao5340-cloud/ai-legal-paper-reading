#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pdf_to_text.py — 把有文字层的 PDF 转成带 [[page:N]] 页标记的 .txt。

这是可选辅助工具：主流程（lit_extract.py）只吃 .docx/.md/.txt。
PDF 需要以下任一后端，缺一个也能跑：
  1. pymupdf  (pip install pymupdf)      —— 推荐，版面还原最好
  2. pypdf    (pip install pypdf)
  3. pdftotext 命令行（poppler-utils）

没有文字层的扫描件会被识别并停止，不做 OCR、不猜内容。

用法:
    python scripts/pdf_to_text.py --input a.pdf --out a.txt
    python scripts/pdf_to_text.py --input a.pdf --out a.txt --pages 8-12
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import json

MIN_CHARS_PER_PAGE = 120  # 低于此值视为无文字层/扫描件


def die(msg, code=2):
    sys.stderr.write("ERROR: " + msg + "\n")
    raise SystemExit(code)


def parse_pages(spec, total):
    if not spec:
        return list(range(total))
    out = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            out.extend(range(int(a) - 1, int(b)))
        elif part:
            out.append(int(part) - 1)
    return [p for p in out if 0 <= p < total]


def tidy(text):
    """把一个 PDF 文本块还原成段落。

    pymupdf 的 block 基本就是一个自然段，内部换行是排版折行。
    中文折行直接相连，英文/数字之间补一个空格，避免粘词。
    不再按句号切段——切碎了会让"跨句的主张"无法整句引用。
    """
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return []
    buf = lines[0]
    for ln in lines[1:]:
        if re.search(r"[A-Za-z0-9,.;:)\]]$", buf) and re.match(r"^[A-Za-z0-9(\[]", ln):
            buf += " " + ln
        else:
            buf += ln
    buf = re.sub(r"[ \t]+", " ", buf).strip()
    return [buf] if buf else []


HEAD_RE = re.compile(r"^\s*(?:第[一二三四五六七八九十百]+[章节]|[一二三四五六七八九十]+、|（[一二三四五六七八九十]+）|[（(]\d{1,2}[）)]|\d{1,2}[.．、]\s*)\S")
TOC_LINE_RE = re.compile(r"(?:[.·…]{2,}|…{2,}|\t)\s*\d{1,3}\s*$")


def merge_lines(col):
    """把同一列里的逐行块拼回段落。"""
    paras, buf, prev = [], "", None
    for b in sorted(col, key=lambda x: (x[1], x[0])):
        text = (b[4] or "").strip()
        if not text:
            continue
        # 目录行各自成段：点线引导符 + 行末页码，拼起来会变成一坨
        if TOC_LINE_RE.search(text) and len(text) < 140:
            if buf:
                paras.append(buf)
                buf = ""
            paras.append(text)
            prev = b
            continue
        if HEAD_RE.match(text) and len(text) < 40:
            if buf:
                paras.append(buf)
                buf = ""
            paras.append(text)
            prev = b
            continue
        if prev is not None:
            line_h = max(1.0, prev[3] - prev[1])
            # 中文排版段落必有首行缩进；段间距也可靠。不用"上一行没排满"，
            # 因为整栏里夹了表格行时，这个判据会让所有行都被误判为段首。
            new_para = ((b[1] - prev[3]) > line_h * 1.6 or b[0] > prev[0] + 6)
            if new_para and buf:
                paras.append(buf)
                buf = ""
        if buf and re.search(r"[A-Za-z0-9,.;:)\]]$", buf) and re.match(r"^[A-Za-z0-9(\[]", text):
            buf += " " + text
        else:
            buf += text
        prev = b
    if buf:
        paras.append(buf)
    return paras


def assemble_paragraphs(blocks, width):
    """把 PDF 的"逐行块"还原成段落，并按阅读顺序输出。

    三个坑：
    1. 双栏按 y 排序会交织成碎片 → 先判断是不是双栏，再分栏；
    2. 单栏正文的整行也是"宽块"，若按通栏处理，每一行都会变成一段（本文件曾如此）；
    3. pymupdf 的 blocks 常是"一行一块"，需要按缩进/行距拼回段落。
    """
    cand = [b for b in blocks if (b[4] or "").strip()]
    if not cand:
        return []

    # 先判断版面：窄块够多才可能是双栏
    narrow = [b for b in cand if (b[2] - b[0]) <= width * 0.62]
    two_col = len(narrow) >= max(6, 0.3 * len(cand)) and len(narrow) >= 0.3 * len(cand)

    if not two_col:
        return [re.sub(r"[ \t]+", " ", p).strip() for p in merge_lines(cand) if p.strip()]

    left, right, wide = [], [], []
    for b in cand:
        if (b[2] - b[0]) > width * 0.62:
            wide.append(b)
        elif b[0] < width * 0.45:
            left.append(b)
        else:
            right.append(b)

    # 通栏行（标题、摘要、表头、页眉页脚）各自成段，不与正文拼接
    out = [(b[4] or "").strip() for b in sorted(wide, key=lambda x: (x[1], x[0]))]
    out = [p for p in out if p]
    lp, rp = merge_lines(left), merge_lines(right)
    # 栏间断句：左栏最后一段没有句末标点时，句子是被分栏切断的，接到右栏第一段
    if lp and rp and not re.search(r"[。！？；：…”」』】]$", lp[-1].rstrip()):
        lp[-1] = lp[-1] + rp.pop(0)
    out += lp + rp
    return [re.sub(r"[ \t]+", " ", p).strip() for p in out if p.strip()]


def backend_pymupdf(path, page_spec):
    try:
        import pymupdf
    except ImportError:  # 旧版包名为 fitz
        import fitz as pymupdf

    doc = pymupdf.open(path)
    pages = parse_pages(page_spec, doc.page_count)
    out = []
    for i in pages:
        pg = doc[i]
        blocks = [b for b in pg.get_text("blocks") if b[6] == 0]
        out.append("\n\n".join(assemble_paragraphs(blocks, pg.rect.width)))
    return pages, out


def backend_pypdf(path, page_spec):
    from pypdf import PdfReader

    r = PdfReader(path)
    pages = parse_pages(page_spec, len(r.pages))
    # 无几何信息的备用后端保留行，不把整页压成一个假段落。
    return pages, ["\n\n".join((r.pages[i].extract_text() or "").splitlines()) for i in pages]


def backend_pdfplumber(path, page_spec):
    """按实际版面合并同页折行；跨页片段不合并。"""
    import pdfplumber

    texts = []
    with pdfplumber.open(path) as doc:
        pages = parse_pages(page_spec, len(doc.pages))
        for i in pages:
            pg = doc.pages[i]
            words = pg.extract_words()
            mid = pg.width / 2
            left_long = sum(w["x1"] < mid and w["x1"] - w["x0"] > pg.width * .22 for w in words)
            right_long = sum(w["x0"] > mid and w["x1"] - w["x0"] > pg.width * .22 for w in words)
            crossing = sum(w["x0"] < pg.width * .47 and w["x1"] > pg.width * .53 for w in words)
            two_col = min(left_long, right_long) >= 6 and crossing < (left_long + right_long) * .25
            # 有左右栏证据才拆栏；单栏整行不能误判为两栏。
            regions = [(0, 0, mid, pg.height), (mid, 0, pg.width, pg.height)] if two_col else [(0, 0, pg.width, pg.height)]
            paragraphs = []
            for box in regions:
                col = pg.crop(box)
                blocks = []
                for line in col.extract_text_lines():
                    t = line["text"].strip()
                    # 仅过滤页边的纯页码，不删除正文里的数字或法条。
                    if re.fullmatch(r"[-—–]?\s*\d+\s*[-—–]?", t) and (line["top"] < pg.height * .08 or line["bottom"] > pg.height * .92):
                        continue
                    blocks.append((line["x0"], line["top"], line["x1"], line["bottom"], t))
                paragraphs.extend(merge_lines(blocks))
            texts.append("\n\n".join(paragraphs))
    return pages, texts


def backend_pdftotext(path, page_spec):
    exe = shutil.which("pdftotext")
    if not exe:
        raise ImportError("pdftotext 不在 PATH")
    tmp = path + ".tmp.txt"
    subprocess.run([exe, "-layout", "-enc", "UTF-8", path, tmp], check=True)
    try:
        with open(tmp, "r", encoding="utf-8", errors="replace") as f:
            raw = f.read()
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
    chunks = raw.split("\f")
    pages = parse_pages(page_spec, len(chunks))
    return pages, [chunks[i] if i < len(chunks) else "" for i in pages]


def convert(path, page_spec, selected="auto"):
    backends = [("pdfplumber", backend_pdfplumber), ("pymupdf", backend_pymupdf), ("pypdf", backend_pypdf), ("pdftotext", backend_pdftotext)]
    if selected != "auto":
        backends = [(name, fn) for name, fn in backends if name == selected]
    errors = []
    for name, fn in backends:
        try:
            pages, texts = fn(path, page_spec)
            if not texts:
                raise ValueError("没有解析出任何页")
            return name, pages, texts
        except ImportError as e:
            errors.append("%s: %s" % (name, e))
        except Exception as e:  # 后端解析失败，换下一个
            errors.append("%s: %s" % (name, e))
    die("没有可用的 PDF 解析后端。\n可选其一：pip install pymupdf ／ pip install pypdf ／ 安装 poppler 的 pdftotext。\n"
        "已尝试：" + " | ".join(errors))


def main():
    ap = argparse.ArgumentParser(description="PDF（有文字层）→ 带 [[page:N]] 的 .txt")
    ap.add_argument("--input", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--pages", default=None, help="如 1-5 或 3,7,9；默认全部")
    ap.add_argument("--backend", default="auto", choices=["auto", "pdfplumber", "pymupdf", "pypdf", "pdftotext"], help="可锁定后端，失败时不静默切换；正式验证应固定同一后端")
    ap.add_argument("--force", action="store_true", help="即使判定为扫描件也照样输出（不推荐）")
    a = ap.parse_args()
    if not os.path.isfile(a.input):
        die("找不到输入文件: " + a.input)

    backend, pages, texts = convert(a.input, a.pages, a.backend)
    chars = [len(re.sub(r"\s", "", t)) for t in texts]
    avg = sum(chars) / max(1, len(chars))
    if avg < MIN_CHARS_PER_PAGE and not a.force:
        die("判定为无文字层或扫描件（平均每页 %d 字）。本工具不做 OCR。\n"
            "替代方案：① 用原出版社的 HTML/EPUB 版本；② 先用 OCR（如 tesseract/PaddleOCR）生成文字层再重跑；"
            "③ 若确认是文字层异常，可加 --force 强行输出后人工抽查。" % avg)

    lines = ["[[from:%s]]" % os.path.basename(a.input)]
    for p, t in zip(pages, texts):
        lines.append("[[page:%d]]\n" % (p + 1))
        paras = [x.strip() for x in t.split("\n\n") if x.strip()] if "\n\n" in t else tidy(t)
        for para in paras:
            lines.append(para + "\n")
        lines.append("\n")
    with open(a.out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(json.dumps({"ok": True, "backend": backend, "pages": len(pages), "chars": sum(chars), "chars_per_page": int(avg), "out": a.out}, ensure_ascii=False))


if __name__ == "__main__":
    main()
