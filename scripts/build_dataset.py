"""Merge parsed texts with the Theodore Roosevelt Center catalog, attach Library of Congress links,
geocode places, and write data/speeches.json.

Run after parse_pasp.py, parse_collections.py and fetch_trc_pages.py."""
import json, os, re, sys, unicodedata
from collections import defaultdict, Counter

sys.path.insert(0, os.path.dirname(__file__))
from places import parse_place, geocode, load_cache, smart_title, STATE_NAME, CACHE_PATH, place_id
from textutil import parse_date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def slug(s, n=60):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s[:n].rstrip("-")


def period_of(date):
    d = date or ""
    if d < "1899-01-01": return "Before 1899"
    if d < "1901-01-01": return "Governor of New York"
    if d < "1901-09-14": return "Vice President"
    if d < "1905-03-04": return "President, first term"
    if d < "1909-03-04": return "President, second term"
    if d < "1912-01-01": return "After the White House"
    if d < "1912-11-06": return "The 1912 campaign"
    return "Final years"


DATE_STRIP = re.compile(
    r",?\s*(?:(?:ON\s+)?(?:THE\s+)?(?:EVENING|AFTERNOON|MORNING)\s+OF\s+)?(?:(?:MONDAY|TUESDAY|WEDNESDAY|THURSDAY|FRIDAY|SATURDAY|SUNDAY)\s*,?\s*)?"
    r"(?:JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER|JAN\.|FEB\.|MAR\.|APR\.|AUG\.|SEPT?\.|OCT\.|NOV\.|DEC\.)"
    r"\s*[-—]?\s*[\dIlO]{1,2}(?:st|nd|rd|th|d)?,?\s*(?:A\.\s?D\.\s*)?([\dIlOS]{4})?\.?", re.I)


def heading_parts(h):
    """Title, place and occasion from a printed heading like
    'AT THE BANQUET OF THE CHAMBER OF COMMERCE OF THE STATE OF NEW YORK, AT NEW YORK, NOVEMBER 11, 1902'."""
    base = DATE_STRIP.sub("", h).strip().rstrip(",.;: ")
    base = re.sub(r"^SPEECH OF PRESIDENT ROOSEVELT\s+", "", base)
    p = parse_place(base)
    occasion = None
    if p:
        city, code, k = p
        segs = [s.strip() for s in base.split(",") if s.strip()]
        occ = ", ".join(segs[:k])
        occ = re.sub(r"\s+(AT|IN)\s*$", "", occ.strip())
        occasion = smart_title(occ) if occ else None
    title = smart_title(base)
    return title, p, occasion


def clean_trc_title(t):
    t = t.replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", t).strip()


def words_of(paras):
    return re.findall(r"[A-Za-z][A-Za-z'’-]*", " ".join(paras))


def jacc(a, b):
    a, b = set(a), set(b)
    return len(a & b) / (len(a | b) or 1)


DISCREPANCIES = []


def main():
    cache = load_cache()
    texts = [json.loads(l) for l in open(os.path.join(ROOT, "build/items_pasp.jsonl"))]
    texts += [json.loads(l) for l in open(os.path.join(ROOT, "build/items_collections.jsonl"))]
    overrides = json.load(open(os.path.join(ROOT, "sources/overrides.json")))["items"]
    kept = []
    for t in texts:
        if t["kind"] in ("proclamation", "letter", "statement", "memorandum"):
            continue   # papers that were never spoken: proclamations belong to the executive actions record,
                       # and public letters are left for a later letters collection
        o = next((o for o in overrides if o["match"] in (t.get("heading") or "").upper()), None)
        if o and o.get("drop"):
            continue
        t["_override"] = o
        kept.append(t)
    texts = kept
    for t in texts:
        t["words"] = words_of(t["paragraphs"])
        if t["source"]["edition"] == "pasp":
            title, p, occasion = heading_parts(t["heading"])
            t["title"] = title
            t["occasion"] = occasion
            t["place"] = p
            o = t.get("_override")
            if o:
                for k in ("date", "date_source", "title", "occasion"):
                    if k in o:
                        t[k] = o[k]
                if "place" in o:
                    t["place"] = (o["place"][0], o["place"][1], 0)
                if "date" in o:
                    t["date_precision"] = "day"
        else:
            p = parse_place(t["place_text"]) if t.get("place_text") else None
            if t.get("place_text") and not p:
                # "Minnesota State Fairgrounds, Minnesota" style
                segs = [s.strip() for s in t["place_text"].split(",")]
                from places import VARIANT
                code = VARIANT.get(re.sub(r"[^a-z]", "", segs[-1].lower()))
                p = (segs[0], code or segs[-1], 0)
            t["place"] = p

    # --- merge duplicates: the same address printed in two editions -------------------------
    groups = []
    by_date = defaultdict(list)
    for t in texts:
        by_date[t["date"]].append(t)
    used = set()
    for d, lst in by_date.items():
        for i, a in enumerate(lst):
            if id(a) in used:
                continue
            grp = [a]
            used.add(id(a))
            for b in lst[i + 1:]:
                if id(b) in used:
                    continue
                if a["kind"] == b["kind"] and jacc([w.lower() for w in a["words"][:400]], [w.lower() for w in b["words"][:400]]) > 0.35:
                    grp.append(b)
                    used.add(id(b))
            groups.append(grp)

    for t in texts:
        if not t["date"] and t["kind"] in ("letter", "statement", "memorandum"):
            for para in t["paragraphs"][:3] + t["paragraphs"][-4:]:
                d, pr = parse_date(para, require_year=True)
                if d:
                    t["date"], t["date_precision"], t["date_source"] = d, pr, "text"
                    break

    def quality(t):
        return (0 if t["source"].get("ocr") else 1, 1 if t["source"]["edition"] != "pasp" else 0, len(t["words"]))

    speeches = []
    for grp in groups:
        grp.sort(key=quality, reverse=True)
        main_t = grp[0]
        # prefer the PASP heading as the descriptive title when it exists, but a book title when the main text is from a book
        pasp = next((g for g in grp if g["source"]["edition"] == "pasp"), None)
        title = main_t["title"]
        occasion = main_t.get("occasion") or (pasp or {}).get("occasion")
        place = main_t.get("place") or (pasp or {}).get("place")
        editions = []
        for g in grp:
            s = g["source"]
            ed = {"edition": s["edition"], "ocr": bool(s.get("ocr"))}
            if s["edition"] == "pasp":
                ed["title"] = f"Presidential Addresses and State Papers, Part {s['part']} (Review of Reviews Co., 1910)"
                ed["page"] = s.get("page")
            else:
                ed["title"] = s.get("book_title")
            if s.get("gutenberg"):
                ed["gutenberg"] = f"https://www.gutenberg.org/ebooks/{s['gutenberg']}"
            if s.get("scan"):
                pg = s.get("page")
                ed["scan"] = f"https://archive.org/details/{s['scan']}" + (f"/page/{pg}/mode/1up" if pg and str(pg).isdigit() else "")
            ed["heading"] = g.get("heading")
            editions.append(ed)
        speeches.append({
            "date": main_t["date"], "date_precision": main_t.get("date_precision", "day"),
            "date_source": main_t.get("date_source", "text"),
            "title": title, "occasion": occasion, "place": place,
            "kind": main_t["kind"], "note": main_t.get("note"),
            "paragraphs": main_t["paragraphs"], "text_source": 0, "ocr": bool(main_t["source"].get("ocr")),
            "editions": editions, "trc": [], "loc": [],
        })

    # --- Theodore Roosevelt Center catalog ------------------------------------------------------
    trc_raw = json.load(open(os.path.join(ROOT, "sources/trc/trc_speeches_raw.json")))
    pages = json.load(open(os.path.join(ROOT, "sources/trc/trc_pages_summary.json"))) if os.path.exists(os.path.join(ROOT, "sources/trc/trc_pages_summary.json")) else {}
    segs = json.load(open(os.path.join(ROOT, "sources/loc/series5_segments.json")))
    trc = []
    for r in trc_raw:
        if "Roosevelt, Theodore" not in r.get("Creator(s)", ""):
            continue
        d = r.get("Creation Date", "")
        if not re.match(r"^1[89]\d\d", d) or d[:4] > "1919":
            continue
        title = clean_trc_title(r["title"])
        info = pages.get(r["id"], {})
        reel = frame = None
        for img in info.get("images", []):
            m = re.search(r"/LC/\d+/(\d{3})/\d+/[^/]+/(\d{4})[ab]?\.jpe?g", img)
            if m:
                reel, frame = int(m.group(1)), int(m.group(2))
                break
        trc.append({"id": r["id"], "url": r["link"], "title": title, "date": d, "pages": r.get("Page Count"),
                    "collection": r.get("Collection"), "repository": r.get("Repository"),
                    "reel": reel, "frame": frame,
                    # first page from the Library of Congress image service (the TRC's own image host refuses outside pages)
                    "thumb": f"https://tile.loc.gov/image-services/iiif/service:mss:mss38299:mss38299_{reel}:{frame:04d}/full/pct:6.25/0/default.jpg" if reel and frame else None,
                    "production": r.get("Production Method")})

    def loc_for(reel, frame):
        for s in segs:
            if s["reel"] == reel and s["start"] <= frame <= s["end"]:
                return {"title": "Theodore Roosevelt Papers, " + s["title"], "reel": reel, "frame": frame,
                        "url": s["resource"] + f"?sp={frame - s['start'] + 1}", "series": s["title"].split(";")[0]}
        return None

    by_day = defaultdict(list)
    for i, s in enumerate(speeches):
        if s["date"]:
            by_day[s["date"][:10]].append(i)
    unmatched = []
    for r in trc:
        cands = by_day.get(r["date"][:10], [])
        best, score = None, 0
        t2 = re.sub(r"^(Remarks|Address|Speech)( of| by)?( the)?( President| Governor| Colonel| Vice-President| Vice President| Hon\.)?( Theodore)? Roosevelt[’']?s?\s+(?!at\b|in\b|to\b|on\b|before\b)", r"\1 at ", r["title"])
        rp = parse_place(DATE_STRIP.sub("", t2), strict=True)
        STOP = {"president", "roosevelt", "speech", "remarks", "address", "theodore", "colonel", "governor", "delivered",
                "january", "february", "march", "april", "june", "july", "august", "september", "october", "november", "december",
                "north", "south", "west", "east", "new", "city", "draft", "drafts", "extract", "extracts", "additions", "edited", "copy",
                "press", "release", "fragment", "excerpt", "notes", "address", "remarks", "speech", "delivered", "given"} | {v.lower() for v in STATE_NAME.values()} | {w for v in STATE_NAME.values() for w in v.lower().split()}
        rt = set(re.findall(r"[a-z]{4,}", r["title"].lower())) - STOP
        PLACEWORDS = set()
        if rp:
            PLACEWORDS = set(re.findall(r"[a-z]{4,}", rp[0].lower()))
        extra = rt - PLACEWORDS
        for i in cands:
            s = speeches[i]
            st = set(re.findall(r"[a-z]{4,}", (s["title"] + " " + (s["occasion"] or "")).lower())) - STOP
            shared = extra & st
            same_place = bool(rp and s["place"] and (rp[0].lower() == s["place"][0].lower()
                              or geocode(rp[0], rp[1], cache) == geocode(s["place"][0], s["place"][1], cache)))
            if rp and s["place"] and not same_place:
                continue   # a different town that day is a different speech
            if same_place and (not extra or shared):
                sc = 1 + len(shared)
            elif not rp and (len(shared) >= 2 or (extra and len(shared) / len(extra) >= 0.5)):
                sc = 0.5 + len(shared)
            else:
                continue
            if sc > score:
                best, score = i, sc
        if best is not None:
            speeches[best]["trc"].append(r)
        else:
            unmatched.append((r, rp))
    # several catalog records for one speech (a draft and a reading copy, two typed copies): group them
    grouped = {}
    for r, rp in unmatched:
        tnorm = re.sub(r"\b(draft|copy|copies|first|second|edited|colonel'?s|press release|with edits by .*)\b", "", r["title"].lower())
        tnorm = re.sub(r"[^a-z]", "", DATE_STRIP.sub("", tnorm))
        key = (r["date"][:10], rp[0].lower() if rp else tnorm)
        if key in grouped:
            grouped[key][0]["_more"].append(r)
        else:
            r["_more"] = []
            grouped[key] = (r, rp)
    unmatched = list(grouped.values())
    for r, rp in unmatched:
        d, prec = r["date"], "day"
        if len(d) == 4:
            prec = "year"
        elif len(d) == 7:
            prec = "month"
        elif not re.match(r"^\d{4}-\d\d-\d\d$", d):
            m = re.match(r"^(\d{4})", d)
            d, prec = (m.group(1), "year") if m else (None, None)
        t = re.sub(r"^(Remarks|Address|Speech) of (President|Governor|Vice-President|Vice President|Colonel|Mr\.|Hon\.)? ?(Theodore )?Roosevelt,? ", r"\1 ", r["title"])
        t = DATE_STRIP.sub("", t).strip().rstrip(",.;:- ")
        t = re.sub(r"\s+-\s*$|\s+-\s+-", "", t).strip()
        t = re.sub(r"\s+-\s*,", ",", t)
        speeches.append({
            "date": d, "date_precision": prec, "date_source": "trc",
            "title": t, "occasion": None, "place": rp, "kind": "speech", "note": None,
            "paragraphs": [], "ocr": False, "editions": [], "trc": [r] + r.pop("_more"), "loc": [],
        })

    # LOC links from TRC images
    for s in speeches:
        for r in s["trc"]:
            if r.get("reel") and r.get("frame"):
                l = loc_for(r["reel"], r["frame"])
                if l and l not in s["loc"]:
                    s["loc"].append(l)

    # --- check dates against Day by Day: where does the Chronological Record put him that day? ---
    import math
    dbd_grid = {r[0]: r for r in json.load(open(os.path.join(ROOT, "sources/daybyday/grid.json")))["rows"]}
    dbd_places = {p["id"]: p for p in json.load(open(os.path.join(ROOT, "sources/daybyday/places_index.json")))}

    def km(a, b):
        la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
        h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
        return 6371 * 2 * math.asin(math.sqrt(h))

    import urllib.request
    day_cache = os.path.join(ROOT, "sources/daybyday/days")
    os.makedirs(day_cache, exist_ok=True)

    def dbd_day(date):
        p = os.path.join(day_cache, f"{date}.json")
        if not os.path.exists(p):
            try:
                req = urllib.request.Request(f"https://daybyday.labs.trlibrary.com/api/v1/days/{date}.json", headers={"User-Agent": "TRPL-Speeches"})
                open(p, "wb").write(urllib.request.urlopen(req, timeout=30).read())
            except Exception:
                return None
        return json.load(open(p))

    def date_check(s, pid):
        notes = []
        t = (s["title"] + " " + " ".join(r["title"] for r in s["trc"])).lower()
        if re.search(r"to be deli[e]?vered|prepared for|not delivered|undelivered", t):
            notes.append("The document calls this a speech to be delivered. It may have been prepared and never given.")
        if not pid or not s["date"] or len(s["date"]) != 10:
            return notes
        here = cache.get(pid)
        g = dbd_grid.get(s["date"])
        if not here or here.get("lat") is None or not g or not g[2]:
            return notes
        there = dbd_places.get(g[2])
        if not there or there.get("lat") is None:
            return notes
        d = km((here["lat"], here["lon"]), (there["lat"], there["lon"]))
        if d > 700:
            # confirm against the full day record: skip places carried forward from an earlier day,
            # state-level places, and same-named towns (a geocoding slip on one side, logged for review)
            day = dbd_day(s["date"])
            loc = (day or {}).get("location") or {}
            if "carried" in (loc.get("source") or "") or there.get("kind") in ("state", "region", "country"):
                return notes
            for aid in loc.get("also") or []:
                a = dbd_places.get(aid)
                if a and a.get("lat") is not None and km((here["lat"], here["lon"]), (a["lat"], a["lon"])) < 700:
                    if aid.split("-")[0] == there["id"].split("-")[0]:
                        DISCREPANCIES.append({"date": s["date"], "speech": s["title"], "speeches_place": here, "daybyday_place": there, "also": aid})
                    return notes
            if there["name"].split(",")[0].lower() == here["name"].split(" (")[0].lower():
                DISCREPANCIES.append({"date": s["date"], "speech": s["title"], "speeches_place": here, "daybyday_place": there})
                return notes
            notes.append(f"Day by Day, which follows the Theodore Roosevelt Association's Chronological Record, places him at {there['name']} on this date, about {round(d, -1):,.0f} km from {here['name']}. One of the two dates may be wrong.")
        return notes

    # --- places, ids, final shape ---------------------------------------------------------------
    seen = Counter()
    out = []
    for s in sorted(speeches, key=lambda x: (x["date"] or "9999", x["title"])):
        pid = None
        if s["place"] and s["kind"] in ("message", "letter", "memorandum", "statement", "proclamation"):
            s["place"] = None
        if s["place"]:
            city, code = s["place"][0], s["place"][1]
            pid = geocode(city, code, cache)
        base = f"{(s['date'] or 'undated')[:10]}-{slug((s['place'][0] if s['place'] else '') or s['title'], 40)}"
        seen[base] += 1
        sid = base if seen[base] == 1 else f"{base}-{seen[base]}"
        text = s["paragraphs"]
        out.append({
            "id": sid, "date": s["date"], "date_precision": s["date_precision"], "date_source": s["date_source"],
            "title": s["title"], "occasion": s["occasion"], "place": pid,
            "kind": s["kind"], "period": period_of(s["date"]), "note": s["note"],
            "checks": date_check(s, pid),
            "has_text": bool(text), "ocr": s["ocr"],
            "word_count": len(words_of(text)) if text else 0,
            "paragraphs": text,
            "editions": s["editions"],
            "trc": [{k: r[k] for k in ("id", "url", "title", "date", "pages", "repository", "thumb")} for r in s["trc"]],
            "loc": s["loc"],
        })
    os.makedirs(os.path.join(ROOT, "data"), exist_ok=True)
    json.dump(out, open(os.path.join(ROOT, "data/speeches.json"), "w"), ensure_ascii=False, indent=0)
    json.dump(dict(sorted(cache.items())), open(CACHE_PATH, "w"), ensure_ascii=False, indent=1)
    c = Counter((x["has_text"], bool(x["trc"])) for x in out)
    print("speeches:", len(out), "| text+trc:", c[(True, True)], "text only:", c[(True, False)], "trc only:", c[(False, True)])
    print("kinds:", Counter(x["kind"] for x in out))
    print("with place:", sum(1 for x in out if x["place"]), "geocoded:", sum(1 for x in out if x["place"] and cache[x["place"]]["lat"]))
    print("with loc link:", sum(1 for x in out if x["loc"]))
    json.dump(DISCREPANCIES, open(os.path.join(ROOT, "data/daybyday_place_review.json"), "w"), indent=1, ensure_ascii=False)
    print("Day by Day place mismatches to review:", len(DISCREPANCIES))
    print("flagged:", sum(1 for x in out if x["checks"]))
    for x in out:
        if x["checks"]:
            print("   ", x["date"], x["title"][:70], "|", x["checks"][-1][:150])
    missing = Counter(x["place"] for x in out if x["place"] and not cache[x["place"]]["lat"])
    print("not geocoded:", missing.most_common(40))


if __name__ == "__main__":
    main()
