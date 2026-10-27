"""Compare pass 1 (transcriptions/) with an independent pass 2 (build/pass2/) word by word.

Where the reading texts agree, the pass 1 file is marked checked. Where they differ, the differences are
written to build/review/ID.txt for a person (or a third read of the image) to settle.

usage: python3 scripts/compare_passes.py [--mark] [SPEECH_ID ...]
With ids, only those speeches are compared (use this while other pass 2 files are still being written).
--mark only changes files whose checked line is still pending."""
import difflib, os, re, sys, datetime

sys.path.insert(0, os.path.dirname(__file__))
from transcripts import parse_markup, reading, tidy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def words(path):
    raw = open(path, encoding="utf-8").read()
    m = re.match(r"---\n(.*?)\n---\n(.*)", raw, re.S)
    head = dict(re.findall(r"^(\w+):\s*(.*)$", m.group(1), re.M))
    body = "\n\n".join(tidy(reading(parse_markup(p))) for p in re.split(r"\n\s*\n", m.group(2)) if p.strip() and not p.strip().startswith("[note:"))
    norm = re.sub(r"[“”]", '"', body)
    norm = re.sub(r"[‘’]", "'", norm)
    # an uncertainty flag is not a different reading: two readers who read the same word agree on it
    norm = norm.replace(" [?]", "").replace("[?]", "")
    return head, re.findall(r"[\w'-]+|[^\w\s]", norm)


def same(a, b):
    """Spacing and line-end hyphen differences ("re- fused" / "refused") are not different readings."""
    k = lambda ws: re.sub(r"[\s\-—–]", "", "".join(ws))
    return k(a) == k(b)


def main():
    mark = "--mark" in sys.argv
    only = {a + ".txt" for a in sys.argv[1:] if not a.startswith("--")}
    p2dir = os.path.join(ROOT, "build/pass2")
    os.makedirs(os.path.join(ROOT, "build/review"), exist_ok=True)
    today = datetime.date.today().isoformat()
    agree = differ = 0
    for fn in sorted(os.listdir(p2dir)):
        if not fn.endswith(".txt") or (only and fn not in only):
            continue
        p1 = os.path.join(ROOT, "transcriptions", fn)
        if not os.path.exists(p1):
            print("no pass 1 for", fn)
            continue
        h1, w1 = words(p1)
        h2, w2 = words(os.path.join(p2dir, fn))
        if h1.get("status", "ok") != "ok" or h2.get("status", "ok") != "ok":
            print(f"{fn}: status {h1.get('status')} / {h2.get('status')}")
            continue
        sm = difflib.SequenceMatcher(a=w1, b=w2, autojunk=False)
        ops = [o for o in sm.get_opcodes() if o[0] != "equal" and not same(w1[o[1]:o[2]], w2[o[3]:o[4]])]
        if not ops:
            agree += 1
            if mark and h1.get("checked", "pending").startswith("pending"):
                raw = open(p1, encoding="utf-8").read()
                raw = re.sub(r"^checked:.*$", f"checked: {today} (pass 2, independent read, agreed word for word)", raw, count=1, flags=re.M)
                open(p1, "w", encoding="utf-8").write(raw)
            continue
        differ += 1
        lines = [f"{fn}: {len(ops)} difference(s), similarity {sm.ratio():.3f}"]
        for tag, i1, i2, j1, j2 in ops:
            ctx = " ".join(w1[max(0, i1 - 6):i1])
            lines.append(f"  ...{ctx} | pass 1: {' '.join(w1[i1:i2]) or '(nothing)'} | pass 2: {' '.join(w2[j1:j2]) or '(nothing)'}")
        open(os.path.join(ROOT, "build/review", fn), "w").write("\n".join(lines) + "\n")
        print("\n".join(lines[:8]))
    print(f"agree: {agree}  differ: {differ}")


if __name__ == "__main__":
    main()
