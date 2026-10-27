"""Shared text helpers for the speech parsers."""
import re
from collections import Counter

MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august",
          "september", "october", "november", "december"]
ABBR = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "sept": 9,
        "oct": 10, "nov": 11, "dec": 12}


def _spaced(word):
    return r"\s?".join(word)


MONTH_RE = re.compile(
    r"\b(" + "|".join(_spaced(m) for m in MONTHS) + r"|(?:" + "|".join(ABBR) + r")\.)" +
    r"[\s,]*[-—]?\s*([0-9IlO]{1,2})(?:st|nd|rd|th|d)?\b[\s,.]*(?:A\.\s?D\.\s*)?([0-9IlOS]{4})?", re.I)
YEAR_ONLY = re.compile(r"\b(1[89][0-9IlO]{2})\b")


def _num(s):
    return int(s.replace("I", "1").replace("l", "1").replace("O", "0").replace("S", "9"))


def _fix_year(y):
    if 1000 <= y <= 1019:  # OCR read 19 as 10
        y += 900
    if 1880 <= y <= 1919:
        return y
    return None


def parse_date(text, require_year=False):
    """Return (iso_date, precision) for the last date in text, or (None, None)."""
    best = None
    for m in MONTH_RE.finditer(text):
        mon = m.group(1).lower().replace(" ", "").rstrip(".")
        month = MONTHS.index(mon) + 1 if mon in MONTHS else ABBR.get(mon)
        if not month:
            continue
        try:
            day = _num(m.group(2))
        except ValueError:
            continue
        year = _fix_year(_num(m.group(3))) if m.group(3) else None
        if year is None and require_year:
            continue
        if not (1 <= day <= 31):
            continue
        best = (year, month, day)
    if best:
        y, mth, d = best
        if y is None:
            return None, None
        return f"{y:04d}-{mth:02d}-{d:02d}", "day"
    if not require_year:
        m = YEAR_ONLY.search(text)
        if m:
            y = _fix_year(_num(m.group(1)))
            if y:
                return f"{y:04d}", "year"
    return None, None


def clean_heading(h):
    h = h.replace("⁠", "")
    h = re.sub(r"(\w)- (\w)", r"\1\2", h)          # CON- GREGATIONAL
    h = re.sub(r"\s+", " ", h).strip()
    h = h.replace("D. C,", "D. C.,").replace("THB ", "THE ")
    h = re.sub(r"^['\"‘’“”.,;:]+", "", h)
    return h


KIND_START = re.compile(
    r"^(?:SPEECH|ADDRESS|REMARKS|SPECIAL MESSAGE|MESSAGE|ANNUAL MESSAGE|STATEMENT|LETTER|CORRESPONDENCE|"
    r"PROCLAMATION|THANKSGIVING PROCLAMATION|VETO MESSAGE|EXECUTIVE ORDER|MEMORANDUM|INAUGURAL|AT|TO|ON|IN|BEFORE|FROM|WELCOMING|TRANSMITTING|RECEPTION|"
    r"REPLY|RESPONSE|OUTSIDE|DELIVERED|LECTURE|TALK|DEDICATION|INTRODUCING)\b")


def classify_kind(h):
    u = h.upper()
    if re.match(r"^(SPECIAL |VETO )?MESSAGE|^ANNUAL MESSAGE|^TRANSMITTING", u):
        return "message"
    if re.match(r"^(LETTER|CORRESPONDENCE)", u):
        return "letter"
    if re.match(r"^STATEMENT", u):
        return "statement"
    if re.search(r"PROCLAMATION", u[:40]):
        return "proclamation"
    if re.match(r"^(MEMORANDUM|EXECUTIVE ORDER)", u):
        return "memorandum"
    return "speech"


WORD = re.compile(r"[a-z]+(?:-[a-z]+)*")


def vocab_from(text):
    return Counter(WORD.findall(text.lower().replace("’", "'")))


def dehyphenate_lines(lines, vocab):
    """Rejoin words broken across lines in OCR text, keeping true hyphenated compounds."""
    out = list(lines)
    for i in range(len(out) - 1):
        l = out[i].rstrip()
        if not l.endswith("-") or l.endswith("--") or l.endswith(" -"):
            continue
        # next non-empty line
        j = i + 1
        while j < len(out) and not out[j].strip():
            j += 1
        if j >= len(out):
            continue
        nxt = out[j].lstrip()
        m = re.match(r"([A-Za-z']+)(.*)", nxt)
        if not m:
            continue
        right, rest = m.group(1), m.group(2)
        lm = re.search(r"([A-Za-z']+)-$", l)
        if not lm:
            continue
        left = lm.group(1)
        joined = (left + right).lower()
        hyph = (left + "-" + right).lower()
        if vocab.get(hyph, 0) > vocab.get(joined, 0):
            word = left + "-" + right
        elif vocab.get(joined, 0) > 0:
            word = left + right
        elif vocab.get(left.lower(), 0) > 2 and vocab.get(right.lower(), 0) > 2 and len(left) > 2 and len(right) > 2:
            word = left + "-" + right
        else:
            word = left + right
        out[i] = l[: lm.start()] + word
        out[j] = rest.lstrip() if rest.strip() else ""
        if not out[j]:
            # keep paragraph structure: if the next line is now empty and was the end of a paragraph, fine
            pass
    return out


def paragraphs_from_lines(lines, gutenberg=False):
    paras, cur = [], []
    for l in lines:
        if not l.strip():
            if cur:
                paras.append(" ".join(x.strip() for x in cur))
                cur = []
        else:
            cur.append(l)
    if cur:
        paras.append(" ".join(x.strip() for x in cur))
    clean = []
    for p in paras:
        p = re.sub(r"\s+", " ", p).strip()
        if gutenberg:
            p = re.sub(r"(?<!\w)_(.+?)_(?!\w)", r"\1", p)
        p = p.replace(" ;", ";").replace(" ,", ",").replace(" :", ":").replace(" .", ".").replace(" ?", "?").replace(" !", "!")
        if not p or re.fullmatch(r"[\d\W]+", p):
            continue
        clean.append(p)
    # merge paragraphs split by page breaks: previous does not end a sentence and next starts lowercase
    merged = []
    for p in clean:
        if merged and not re.search(r"[.!?:;\"”’)\]]$", merged[-1]) and (p[:1].islower() or p[:1] in ",;"):
            merged[-1] = merged[-1] + " " + p
        else:
            merged.append(p)
    return merged
