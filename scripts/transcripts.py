"""Read the diplomatic transcriptions in transcriptions/*.txt and produce two views per speech:
reading paragraphs (plain text, corrections applied) and diplomatic paragraphs (HTML with the marks shown).
See transcriptions/README.md for the markup."""
import html, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def parse_markup(s):
    """Return a list of nodes: ('text', str) | (kind, children|str, extra)."""
    nodes, i, n = [], 0, len(s)
    buf = []

    def flush():
        if buf:
            nodes.append(("text", "".join(buf)))
            buf.clear()

    def matching(start, open_, close):
        depth, j = 0, start
        while j < n:
            if s.startswith(open_, j):
                depth += 1
                j += len(open_)
                continue
            if s.startswith(close, j):
                depth -= 1
                if depth == 0:
                    return j
                j += len(close)
                continue
            j += 1
        raise ValueError(f"unclosed {open_} at {start}: {s[start:start + 40]!r}")

    while i < n:
        if s.startswith("[-", i):
            j = matching(i, "[-", "-]")
            flush(); nodes.append(("del", parse_markup(s[i + 2:j]))); i = j + 2
        elif s.startswith("[+", i):
            j = matching(i, "[+", "+]")
            flush(); nodes.append(("ins", parse_markup(s[i + 2:j]))); i = j + 2
        elif s.startswith("[?", i):
            j = matching(i, "[?", "?]")
            flush(); nodes.append(("unc", parse_markup(s[i + 2:j]))); i = j + 2
        elif s.startswith("[illegible]", i):
            flush(); nodes.append(("illeg", None)); i += len("[illegible]")
        elif s.startswith("[pb ", i):
            j = s.index("]", i)
            flush(); nodes.append(("pb", s[i + 4:j].strip())); i = j + 1
        elif s.startswith("[margin:", i) or s.startswith("[note:", i):
            kind = "margin" if s.startswith("[margin:", i) else "note"
            j = matching(i, "[", "]")
            flush(); nodes.append((kind, parse_markup(s[i + len(kind) + 2:j].strip()))); i = j + 1
        elif s[i] == "{":
            j = s.index("}", i)
            typed, _, reading = s[i + 1:j].partition("|")
            flush(); nodes.append(("reg", typed, reading)); i = j + 1
        else:
            buf.append(s[i]); i += 1
    flush()
    return nodes


def reading(nodes):
    out = []
    for nd in nodes:
        k = nd[0]
        if k == "text": out.append(nd[1])
        elif k == "ins": out.append(reading(nd[1]))
        elif k == "unc": out.append(reading(nd[1]) + " [?]")
        elif k == "illeg": out.append("[illegible]")
        elif k == "reg": out.append(reading(parse_markup(nd[2])))
    return "".join(out)


def diplomatic(nodes):
    out = []
    for nd in nodes:
        k = nd[0]
        if k == "text": out.append(html.escape(nd[1]))
        elif k == "del": out.append(f'<del title="struck through">{diplomatic(nd[1])}</del>')
        elif k == "ins": out.append(f'<ins title="added by hand">{diplomatic(nd[1])}</ins>')
        elif k == "unc": out.append(f'<span class="unc" title="uncertain reading">{diplomatic(nd[1])}</span>')
        elif k == "illeg": out.append('<span class="illeg">[illegible]</span>')
        elif k == "reg": out.append(f'<span class="sic" title="reads: {html.escape(tidy(reading(parse_markup(nd[2]))))}">{diplomatic(parse_markup(nd[1]))}</span>')
        elif k == "pb":
            folio, _, frame = nd[1].partition(" ")
            out.append(f'<span class="pb">Page {html.escape(folio)}{" (frame " + html.escape(frame) + ")" if frame else ""}</span>')
        elif k == "margin": out.append(f'<span class="margin">In the margin: {diplomatic(nd[1])}</span>')
        elif k == "note": out.append(f'<span class="tnote">{diplomatic(nd[1])}</span>')
    return "".join(out)


def tidy(t):
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"\s+([.,;:!?)])", r"\1", t)
    t = re.sub(r"\(\s+", "(", t)
    t = re.sub(r",(?=[A-Za-z])", ", ", t)
    t = re.sub(r",,+", ",", t)
    return t


_VOCAB = None
KEEP_SPACED = {"foot ball"}   # period spellings written as two words


def close_gaps(t):
    """Typewriter gaps inside a word ("accordi ng", "experime nt") are closed in the reading text when the joined
    form is a common word and one of the pieces is not. The "As typed" view keeps the gap."""
    global _VOCAB
    if _VOCAB is None:
        from textutil import vocab_from
        g = os.path.join(ROOT, "sources/gutenberg")
        _VOCAB = vocab_from(" ".join(open(os.path.join(g, f), encoding="utf-8").read() for f in os.listdir(g) if f.endswith(".txt")))
    common = lambda w: _VOCAB.get(w.lower(), 0) >= 3

    def fix(m):
        a, b = m.group(1), m.group(2)
        if (a + " " + b).lower() in KEEP_SPACED:
            return m.group(0)
        if common(a + b) and not (common(a) and common(b)):
            return a + b
        return m.group(0)
    return re.sub(r"\b([A-Za-z]+) ([a-z]+)\b", fix, t)


def load():
    out = {}
    d = os.path.join(ROOT, "transcriptions")
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".txt"):
            continue
        raw = open(os.path.join(d, fn), encoding="utf-8").read()
        m = re.match(r"---\n(.*?)\n---\n(.*)", raw, re.S)
        head = dict(re.findall(r"^(\w+):\s*(.*)$", m.group(1), re.M))
        # only transcriptions that passed the second, independent reading are published
        if head.get("checked", "pending").startswith("pending") or head.get("status", "ok") != "ok":
            continue
        body = m.group(2).strip()
        paras = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
        read_p, dip_p, notes = [], [], []
        for p in paras:
            nodes = parse_markup(p)
            dip_p.append(diplomatic(nodes))
            r = close_gaps(tidy(reading(nodes)))
            if r:
                read_p.append(r)
            for nd in nodes:
                if nd[0] == "note":
                    notes.append(tidy(reading(nd[1])))
        out[head["speech"]] = {
            "title": head.get("title"), "source": head.get("source"), "image": head.get("image"),
            "transcribed": head.get("transcribed"), "checked": head.get("checked"),
            "reading": read_p, "diplomatic": dip_p, "notes": notes, "file": f"transcriptions/{fn}",
        }
    return out


if __name__ == "__main__":
    for k, v in load().items():
        print("==", k)
        print("\n\n".join(v["reading"]))
        print("--- diplomatic:", v["diplomatic"][1][:300])
