"""Split the published collections and single-address pamphlets listed in sources/collections.json.
Output: build/items_collections.jsonl"""
import json, os, re, sys

sys.path.insert(0, os.path.dirname(__file__))
from textutil import vocab_from, dehyphenate_lines, paragraphs_from_lines

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def norm(s):
    return re.sub(r"[^A-Z]", "", s.upper())


def body_of(raw):
    a = raw.find("*** START OF")
    if a >= 0:
        raw = raw[raw.find("\n", a) + 1:]
    b = raw.find("*** END OF")
    if b >= 0:
        raw = raw[:b]
    return raw.replace("⁠", "").replace("\f", "\n")


def strip_running(lines, titles):
    """Drop OCR running heads ("4 THE NEW NATIONALISM", "CONSERVATION 51") and bare page numbers."""
    tn = [norm(t) for t in titles if t != "*"]
    out = []
    for l in lines:
        s = re.sub(r"^[\divxlcIVXLC]{1,4}\s+|\s+[\divxlcIVXLC]{1,4}$", " 0 ", l.strip()).strip()
        if re.fullmatch(r"[\divxlcIVXLC.,'’\-—•\s]{1,8}", s or "x"):
            out.append("")
            continue
        if s and s == s.upper() and len(s) < 80 and re.search(r"\d", s):
            ns = norm(s)
            if any(t and (t in ns or ns in t) for t in tn) or len(ns) < 30:
                out.append("")
                continue
        out.append(l)
    return out


def find_heading(lines, heading, start):
    target = norm(heading)
    for i in range(start, len(lines)):
        s = lines[i].strip()
        if not s or s != s.upper():
            continue
        if norm(s) == target:
            return i
        # heading split across two lines
        if i + 1 < len(lines) and norm(s + " " + lines[i + 1].strip()) == target:
            return i
    return None


def junk(p, vocab):
    toks = re.findall(r"[A-Za-z']+", p)
    if not toks:
        return True
    known = sum(1 for t in toks if vocab.get(t.lower(), 0) > 0)
    if re.search(r"JOB PRINT|Murray Street|Stoddard-Sutherland|Digitized by|Google$", p):
        return True
    return len(toks) < 80 and known / len(toks) < 0.7


def main():
    man = json.load(open(os.path.join(ROOT, "sources/collections.json")))
    gut = " ".join(open(os.path.join(ROOT, f"sources/gutenberg/{f}"), encoding="utf-8").read()
                   for f in os.listdir(os.path.join(ROOT, "sources/gutenberg")) if f.endswith(".txt"))
    vocab = vocab_from(gut)
    items = []
    for book in man["books"]:
        raw = body_of(open(os.path.join(ROOT, book["file"]), encoding="utf-8", errors="replace").read())
        lines = raw.split("\n")
        ocr = book.get("ocr", False)
        titles = [e["heading"] for e in book["entries"]] + book.get("stop", [])
        # find the last table-of-contents line so we search the body only
        toc_end = 0
        for k, l in enumerate(lines[:400]):
            if re.match(r"^\s*(CONTENTS|PAGE)\s*$", l.strip()):
                toc_end = k
        # locate each heading in order; contents pages list them first, so take the occurrence
        # that is followed by real prose
        positions = {}
        for t in titles:
            if t == "*":
                continue
            cands = []
            for i in range(toc_end, len(lines)):
                a = re.sub(r"\[\d+\]", "", lines[i]).strip()
                if not a or a != a.upper() or re.search(r"\d", a):
                    continue
                b = re.sub(r"\[\d+\]", "", lines[i + 1]).strip() if i + 1 < len(lines) else ""
                if norm(a) == norm(t) or (b and b == b.upper() and not re.search(r"\d", b) and norm(a + b) == norm(t)):
                    cands.append(i + (1 if norm(a) != norm(t) else 0))
            good = []
            for c in cands:
                after = " ".join(x for x in lines[c + 1:c + 25] if x.strip())
                nearby = [norm(re.sub(r"\[\d+\]", "", x)) for x in lines[c + 1:c + 16] if x.strip()]
                if len(re.findall(r"[a-z]", after)) > 300 and not any(nb in {norm(z) for z in titles} for nb in nearby):
                    good.append(c)
            if good:
                positions[t] = good[0]
        for e in book["entries"]:
            if e["heading"] == "*":
                # whole book is one lecture: from the first prose after the title page to the end
                start = next(i for i in range(len(lines)) if len(re.findall(r"[a-z]", lines[i])) > 30)
                end = len(lines)
            else:
                if e["heading"] not in positions:
                    print("  !! heading not found:", book["id"], e["heading"])
                    continue
                start = positions[e["heading"]] + 1
                later = sorted(p for p in positions.values() if p > positions[e["heading"]])
                end = later[0] if later else len(lines)
            seg = lines[start:end]
            if ocr:
                seg = strip_running(seg, titles)
                seg = dehyphenate_lines(seg, vocab)
            paras = paragraphs_from_lines(seg, gutenberg=not ocr)
            # drop the delivery line(s) printed under the title, and footnote markers
            while paras and len(paras[0]) < 220 and (paras[0] == paras[0].upper() or re.match(r"^(SPEECH|ADDRESS|AN ADDRESS|DELIVERED|AT THE|AT |\[|An Address|Address [Dd]elivered|Delivered|Speech)", paras[0]) or re.fullmatch(r"[\dIlO ]{1,3} [A-Z][a-z]+,? [\dIlO ]{4,7}\.?", paras[0])):
                paras.pop(0)
            for _ in range(e.get("skip_first", 0)):
                if paras and len(paras[0]) < 120:
                    paras.pop(0)
            paras = [p for p in paras if not junk(p, vocab) and not re.match(r"^\[\d+\]", p)]
            paras = cut_tail(paras)
            items.append(make_item(e, book, paras))
    for pam in man["pamphlets"]:
        raw = body_of(open(os.path.join(ROOT, pam["file"]), encoding="utf-8", errors="replace").read())
        if pam.get("slice"):
            a = raw.find(pam["slice"][0])
            # back up to the start of that paragraph
            a = raw.rfind("\n\n", 0, a) + 2
            raw = raw[a:]
            if pam["slice"][1]:
                raw = raw[: raw.find(pam["slice"][1])]
        lines = raw.split("\n")
        ocr = pam.get("ocr", False)
        if ocr:
            lines = strip_running(lines, [])
            lines = dehyphenate_lines(lines, vocab)
        paras = paragraphs_from_lines(lines, gutenberg=not ocr)
        # keep from the first real paragraph (salutation or prose) onward; drop front matter
        k = 0
        while k < len(paras) and (len(re.findall(r"[a-z]", paras[k])) < 40 or re.search(r"Digitized|Gutenberg|Copyright|PRINTING OFFICE|Library of|University of California|Press\b|Company\b|Illustration", paras[k])):
            k += 1
        paras = paras[k:]
        # Gutenberg pamphlets end with transcriber notes
        paras = [p for p in paras if not re.match(r"^(Transcriber|TRANSCRIBER|\[Illustration|Footnote)", p)]
        if pam.get("cut_at_caps"):
            # stop at the end of the speech in the Milwaukee book (the next chapter heading)
            cut = next((i for i, p in enumerate(paras) if p == p.upper() and len(p) > 8 and i > 5), None)
            if cut:
                paras = paras[:cut]
        paras = [p for p in paras if not junk(p, vocab)]
        paras = cut_tail(paras)
        items.append(make_item(pam, {"id": "pamphlet", "title": pam["title"], "gutenberg": pam.get("gutenberg"),
                                      "ia": pam.get("ia"), "ocr": ocr}, paras))
    with open(os.path.join(ROOT, "build/items_collections.jsonl"), "w") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    for it in items:
        w = sum(len(p.split()) for p in it["paragraphs"])
        print(f"{it['date']} {w:6d}  {it['title'][:60]} | {it['paragraphs'][0][:70] if it['paragraphs'] else '—'}")


def _caps(p):
    letters = [c for c in p if c.isalpha()]
    return len(letters) > 4 and sum(c.isupper() for c in letters) / len(letters) > 0.8


CUT = re.compile(r"^(FOLLOWED BY|APPENDIX|TRANSCRIBER|END OF VOLUME|PART [IVX]+\b|THE WORD AND THE DEED|THE NEW NATIONALISM AND\b|MR\. ROOSEVELT'S LETTER|BIOLOGICAL ANALOGIES IN HISTORY|INDEX\b)")


def cut_tail(paras):
    """Stop at book matter printed after an address: appendices, part titles, the next chapter."""
    for i, p in enumerate(paras):
        if i > 2 and _caps(p) and CUT.match(p.strip("“”\"' ")):
            return paras[:i]
    return paras


def make_item(e, book, paras):
    return {
        "heading": e.get("heading") if e.get("heading") not in (None, "*") else e["title"],
        "title": e["title"],
        "date": e["date"], "date_precision": "day", "date_source": e.get("date_source", "text"),
        "place_text": e.get("place"), "occasion": e.get("occasion"),
        "kind": e.get("kind", "speech"),
        "note": e.get("note"),
        "paragraphs": paras,
        "source": {
            "edition": book["id"], "book_title": book["title"],
            "gutenberg": book.get("gutenberg") or e.get("gutenberg"),
            "scan": book.get("ia") or e.get("ia"),
            "ocr": bool(book.get("ocr")),
        },
    }


if __name__ == "__main__":
    main()
