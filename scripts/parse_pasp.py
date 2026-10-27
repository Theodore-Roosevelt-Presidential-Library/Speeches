"""Split the eight parts of *Presidential Addresses and State Papers* (Review of Reviews Co., 1910)
into individual items.

Parts 1-4 come from the proofread Project Gutenberg editions; parts 5-8 from Internet Archive OCR.
Output: build/items_pasp.jsonl, one item per address, message, statement or letter.
"""
import json, os, re, sys
from collections import Counter

sys.path.insert(0, os.path.dirname(__file__))
from textutil import (MONTHS, parse_date, clean_heading, vocab_from, dehyphenate_lines,
                      paragraphs_from_lines, KIND_START, classify_kind)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PARTS = [
    # part, source file, scan id on the Internet Archive used for page links, gutenberg id
    (1, "sources/gutenberg/pg74572.txt", "presidentialaddr0001roos", 74572),
    (2, "sources/gutenberg/pg74680.txt", "presidentialaddr0002roos", 74680),
    (3, "sources/gutenberg/pg74681.txt", "presidentialaddr0003roos", 74681),
    (4, "sources/gutenberg/pg76020.txt", "bwb_T3-BEE-874_4", 76020),
    (5, "sources/editions/pasp-part5__presidentialaddr0005theo.txt", "presidentialaddr0005theo", None),
    (6, "sources/editions/pasp-part6__presidentialaddr0006theo.txt", "presidentialaddr0006theo", None),
    (7, "sources/editions/pasp-part7__presidentialaddr0007theo.txt", "presidentialaddr0007theo", None),
    (8, "sources/editions/pasp-part8__presidentialadd01roosgoog.txt", "presidentialadd01roosgoog", None),  # European addresses after this come from Gutenberg 13930
]

RUNNING = re.compile(r"^\s*([\w]{0,6}\s*_?\s*)?(Presidential\s+Addresses|And\s+State\s+Papers|Addresses\s+and\s+State\s+Papers|European\s+Addresses)(\s*[\w]{0,6})?\s*$", re.I)
SIGNATURE = re.compile(r"^\s*[\dIlO]{1,3}\s*[—–-]+\s*VOL\.?.*$", re.I)
PAGENUM = re.compile(r"^\s*[\divxlc]{1,5}\s*$", re.I)
PAGEHDR = re.compile(r"^\s*(\d+)\s+Presidential\s+Addresses\s*$|^\s*And\s+State\s+Papers\s+(\d+)\s*$", re.I)


def is_caps_line(s):
    t = s.strip()
    if len(t) < 3:
        return False
    letters = [c for c in t if c.isalpha()]
    if len(letters) < 2:
        return False
    return not any(c.islower() for c in letters if c not in "ß")


def gutenberg_body(text):
    a = text.find("*** START OF")
    b = text.find("*** END OF")
    body = text[text.find("\n", a) + 1: b]
    # the transcriber notes at the end
    tn = body.rfind("TRANSCRIBER’S NOTE")
    if tn > len(body) * 0.8:
        body = body[:tn]
    return body


def gutenberg_toc(text):
    """Return a list of (title, page) from the transcriber's table of contents."""
    seg = text[text.find("convenience of the reader one has been created"):]
    seg = seg[: seg.find("\n\n\n")] if False else seg
    entries, cur = [], []
    for line in seg.split("\n")[1:]:
        if line.startswith("[Illustration") or re.match(r"^[A-Z]{3,}", line):
            break
        if not line.strip():
            if cur:
                joined = " ".join(x.strip() for x in cur)
                m = re.match(r"(.*?)\s+([ivxlc\d]+)$", joined)
                if m:
                    entries.append((m.group(1).strip(), m.group(2)))
                cur = []
            continue
        cur.append(line)
    return entries


def _no_lower(s):
    t = s.strip()
    return bool(t) and not any(c.islower() for c in t) and any(c.isalnum() for c in t)


def heading_blocks(lines, start=0):
    """Find candidate heading blocks: runs of all-caps lines bounded by blank lines.
    A date line without letters ("22, 1902") continues a block, and a block with no date yet
    may jump one blank line to a following all-caps line."""
    i, n = start, len(lines)
    while i < n:
        if is_caps_line(lines[i]) and (i == 0 or not lines[i - 1].strip() or RUNNING.match(lines[i - 1]) or SIGNATURE.match(lines[i-1])):
            j = i
            while j < n:
                if lines[j].strip() and _no_lower(lines[j]) and not RUNNING.match(lines[j]) and not SIGNATURE.match(lines[j]):
                    j += 1
                    continue
                block = " ".join(x.strip() for x in lines[i:j])
                if (not lines[j].strip() and j + 1 < n and is_caps_line(lines[j + 1]) and not parse_date(block)[0]
                        and j - i < 5 and not RUNNING.match(lines[j + 1])):
                    j += 1
                    continue
                break
            if j == i:
                i += 1
                continue
            yield i, j
            i = j
        else:
            i += 1


def accept_heading(h):
    """A heading starts a new item if it begins like an address/message title or carries a date."""
    if RUNNING.match(h) or re.match(r"^(PRESIDENTIAL ADDRESSES|AND STATE PAPERS|ADDRESSES AND STATE PAPERS|THEODORE ROOSEVELT\.?|APPENDIX|INDEX|INTRODUCTION|CONTENTS|EUROPEAN ADDRESSES)\b", h):
        return False
    if KIND_START.match(h):
        return True
    return False


def parse_part(part, path, scan, gid, vocab):
    raw = open(os.path.join(ROOT, path), encoding="utf-8", errors="replace").read()
    is_gut = gid is not None
    text = gutenberg_body(raw) if is_gut else raw
    text = text.replace("⁠", "").replace("\f", "\n")
    if part == 8:
        cut = re.search(r"\n\s*INTERNATIONAL PEACE\s*\n", text)
        text = text[: cut.start()] if cut else text
    lines = text.split("\n")
    toc = gutenberg_toc(raw) if is_gut else []

    # track printed page numbers by line for OCR volumes
    page_at = [None] * len(lines)
    cur = None
    for k, l in enumerate(lines):
        m = PAGEHDR.match(l)
        if m:
            cur = int(m.group(1) or m.group(2))
        page_at[k] = cur

    # body starts after the first "ADDRESSES AND STATE PAPERS" line (Introduction and "The Presidency" essay come before)
    begin = 0
    for k, l in enumerate(lines):
        if re.match(r"^\s*(ADDRESSES\s+AND\s+STATE\s+PAPERS|PRESIDENTIAL\s+ADDRESSES)\s*$", l) and k > 60:
            # first one after the title pages
            nxt = "\n".join(lines[k:k + 12])
            if KIND_START.search(re.sub(r"\s+", " ", nxt.upper())):
                begin = k
                break
    heads = []
    for a, b in heading_blocks(lines, begin):
        h = clean_heading(" ".join(x.strip() for x in lines[a:b]))
        if accept_heading(h):
            heads.append((a, b, h))
    # merge headings that are adjacent continuation (e.g. kind line then date line separated by blank)
    items = []
    toc_i = 0
    for idx, (a, b, h) in enumerate(heads):
        end = heads[idx + 1][0] if idx + 1 < len(heads) else len(lines)
        body = []
        for l in lines[b:end]:
            if RUNNING.match(l) or SIGNATURE.match(l) or PAGENUM.match(l) or l.startswith("[Illustration"):
                body.append("")
                continue
            body.append(l.rstrip())
        if not is_gut:
            body = dehyphenate_lines(body, vocab)
        paras = paragraphs_from_lines(body, gutenberg=is_gut)
        # drop trailing library junk
        paras = [p for p in paras if not re.search(r"RETURN\s+CIRCULATION|ALL BOOKS MAY BE RECALLED|Renewals and Recharges|Digitized by", p)]
        date, prec = parse_date(h)
        if not date:
            # messages: look for "White House, <date>" near the end
            tail = " ".join(paras[-3:]) if paras else ""
            date, prec = parse_date(tail, require_year=True)
            if date:
                prec = "from-signature"
        page = page_at[a] if not is_gut else None
        if is_gut and toc:
            # align with the table of contents by order and fuzzy text match
            best, bscore = None, 0
            hw = set(re.findall(r"[a-z]{3,}", h.lower()))
            for j in range(toc_i, len(toc)):
                tw = set(re.findall(r"[a-z]{3,}", toc[j][0].lower()))
                sc = len(hw & tw) / (len(hw | tw) or 1)
                sc -= 0.01 * (j - toc_i)
                if sc > bscore:
                    best, bscore = j, sc
            if best is not None and bscore >= 0.35:
                toc_i = best + 1
                page = toc[best][1]
        words = sum(len(p.split()) for p in paras)
        if words < 15:
            continue
        for sub in split_embedded(h, date, prec, paras):
            sub["source"] = {"edition": "pasp", "part": part, "page": page, "scan": scan, "gutenberg": gid, "ocr": not is_gut}
            items.append(sub)
        continue
        items.append({
            "heading": h,
            "date": date, "date_precision": prec,
            "kind": classify_kind(h),
            "paragraphs": paras,
            "source": {
                "edition": "pasp",
                "part": part,
                "page": page,
                "scan": scan,
                "gutenberg": gid,
                "ocr": not is_gut,
            },
        })
    return items


def _caps(p):
    letters = [c for c in p if c.isalpha()]
    return len(letters) > 6 and sum(c.isupper() for c in letters) / len(letters) > 0.8


STOP_AT = re.compile(r"^(END OF VOLUME|EXTRACTS FROM THE MESSAGES|FIRST ADMINISTRATION|SECOND ADMINISTRATION|INDEX\b|APPENDIX)")
LETTER_HEAD = re.compile(r"^(?:T\w{2} )?W\w{3,4} Hou\w{1,2},?\s+W|^OYSTER BAY,? N\.? ?Y|^SAGAMORE HILL", re.I)
SALUTE = re.compile(r"^[“\"]?(?:my )?d\w{1,3}r\b", re.I)


def split_embedded(h, date, prec, paras):
    """A printed item can carry things that are not part of it: a following address whose heading the
    parser missed, letters printed after a speech, or an essay included in the volume. Split or drop them."""
    out = []
    # a heading the OCR split across a blank line continues into the first paragraph
    while paras and (_caps(paras[0]) or (parse_date(paras[0], require_year=True)[0] and not re.search(r"[a-z]{3}", paras[0]))) and len(paras[0]) < 200 and not SALUTE.match(paras[0]) and (not date or parse_date(paras[0], require_year=True)[0]):
        h = clean_heading(h + " " + paras[0])
        paras = paras[1:]
        nd, np_ = parse_date(h)
        if nd:
            date, prec = nd, np_
    cur = {"heading": h, "date": date, "date_precision": prec, "kind": classify_kind(h), "paragraphs": []}
    for i, p in enumerate(paras):
        nxt = paras[i + 1] if i + 1 < len(paras) else ""
        if _caps(p) and (STOP_AT.match(p) or nxt.startswith("[Included") or nxt.startswith("[Written")):
            break
        new_head = None
        soon = paras[i + 1:i + 4]
        if i > 0 and _caps(p) and re.search(r"PROCLAMATION|VETO MESSAGE", p[:60]):
            new_head = (p, "proclamation" if "PROCLAMATION" in p[:60] else "message")
        elif i > 0 and _caps(p) and KIND_START.match(p) and parse_date(p)[0] and cur["kind"] != "message":
            new_head = (p, "speech")
        elif i > 2 and cur["kind"] == "speech" and _caps(p) and len(p) < 80 and any(SALUTE.match(x) for x in soon):
            new_head = (p, "letter")
        elif i > 0 and LETTER_HEAD.match(p) and cur["kind"] != "message" and len(p) < 120 and (_caps(p) or parse_date(p)[0]):
            new_head = (p, "letter")
        if new_head:
            if cur["paragraphs"]:
                out.append(cur)
            hp, kind = new_head
            d, pr = parse_date(hp + " " + " ".join(soon[:2]), require_year=True)
            if not d and kind in ("proclamation", "message"):
                # proclamations and messages are dated at the end
                tail = " ".join(paras[i + 1:i + 30])
                d, pr = parse_date(tail, require_year=True)
            heading = hp
            if kind == "letter":
                sal = next((x for x in soon if SALUTE.match(x)), nxt)
                m = re.match(r"^[“\"]?(?:my )?d\w{1,3}r (.+?)[:,]", sal, re.I)
                heading = "LETTER TO " + m.group(1).upper() if m else "LETTER"
            cur = {"heading": clean_heading(heading), "date": d, "date_precision": pr or "day", "kind": kind, "paragraphs": []}
            if kind in ("speech", "message", "proclamation"):
                continue
        cur["paragraphs"].append(p)
    if cur["paragraphs"]:
        out.append(cur)
    return [o for o in out if sum(len(x.split()) for x in o["paragraphs"]) >= 15]


def main():
    corpus = " ".join(open(os.path.join(ROOT, p), encoding="utf-8", errors="replace").read() for _, p, _, g in PARTS if g)
    vocab = vocab_from(corpus)
    out = []
    for part, path, scan, gid in PARTS:
        items = parse_part(part, path, scan, gid, vocab)
        kinds = Counter(i["kind"] for i in items)
        nodate = sum(1 for i in items if not i["date"])
        print(f"part {part}: {len(items)} items {dict(kinds)} no date: {nodate}")
        out += items
    os.makedirs(os.path.join(ROOT, "build"), exist_ok=True)
    with open(os.path.join(ROOT, "build/items_pasp.jsonl"), "w") as f:
        for it in out:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
