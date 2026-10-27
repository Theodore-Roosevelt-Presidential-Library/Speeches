"""Write the static JSON API under api/v1/ from data/*.json."""
import json, os, re, shutil
from collections import defaultdict, Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = os.path.join(ROOT, "api/v1")

SIGNATURE = [
    "square deal", "equality of opportunity", "worth his salt", "show the stuff", "fair play", "righteousness",
    "decency", "efficiency", "americanism", "the average man", "plain people", "commonplace virtues", "common sense",
    "tillers of the soil", "children's children", "shoulder to shoulder", "wore the blue", "wore the gray",
    "social and industrial justice", "national efficiency", "natural resources", "big stick", "in the arena",
    "strenuous life", "muck-rake", "malefactors of great wealth", "new nationalism", "mollycoddle", "bully",
]


def dump(path, obj):
    full = os.path.join(API, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))


def main():
    S = json.load(open(os.path.join(ROOT, "data/speeches.json")))
    P = json.load(open(os.path.join(ROOT, "data/places.json")))
    T = json.load(open(os.path.join(ROOT, "sources/themes.json")))
    stats = json.load(open(os.path.join(ROOT, "data/corpus_stats.json")))
    if os.path.exists(API):
        shutil.rmtree(API)

    order = sorted(S, key=lambda s: (s["date"] or "9999", s["id"]))
    idx = {s["id"]: i for i, s in enumerate(order)}

    # index: one compact row per speech
    rows = []
    for s in order:
        rows.append({
            "id": s["id"], "date": s["date"], "prec": s["date_precision"], "title": s["title"],
            "place": s["place"], "kind": s["kind"], "period": s["period"], "themes": s.get("themes", []),
            "words": s["word_count"], "text": s["has_text"], "trc": len(s["trc"]), "loc": bool(s["loc"]),
            "occasion": s.get("occasion"),
        })
    dump("speeches.json", {"count": len(rows), "speeches": rows})

    # full records
    for s in order:
        i = idx[s["id"]]
        rec = dict(s)
        rec["place"] = P.get(s["place"]) if s["place"] else None
        rec["prev"] = order[i - 1]["id"] if i > 0 else None
        rec["next"] = order[i + 1]["id"] if i + 1 < len(order) else None
        rec["daybyday"] = f"https://daybyday.labs.trlibrary.com/day.html?date={s['date']}" if s["date"] and len(s["date"]) == 10 else None
        rec["loc_search"] = (f"https://www.loc.gov/collections/theodore-roosevelt-papers/?dates={s['date']}/{s['date']}&fa=partof:theodore+roosevelt+papers:+series+5:+speeches+and+executive+orders,+1899-1918"
                             if s["date"] and len(s["date"]) == 10 and "1899" <= s["date"][:4] <= "1918" else None)
        dump(f"speeches/{s['id']}.json", rec)

    # places
    by_place = defaultdict(list)
    for s in order:
        if s["place"]:
            by_place[s["place"]].append(s["id"])
    places = []
    for pid, ids in by_place.items():
        p = P[pid]
        places.append({**p, "speeches": ids, "count": len(ids)})
    places.sort(key=lambda p: -p["count"])
    dump("places.json", {"count": len(places), "places": places})

    # themes
    tcount = Counter(t for s in S for t in s.get("themes", []))
    dump("themes.json", {"themes": [{**{k: v for k, v in t.items() if k != "terms"}, "count": tcount[t["id"]],
                                      "by_year": stats["theme_year"].get(t["id"], {})} for t in T]})

    # on this day
    otd = defaultdict(list)
    for s in order:
        if s["date"] and len(s["date"]) == 10:
            otd[s["date"][5:]].append({"id": s["id"], "date": s["date"], "title": s["title"],
                                        "place": P[s["place"]]["name"] + ", " + P[s["place"]]["region"] if s["place"] else None,
                                        "text": s["has_text"], "words": s["word_count"]})
    for md, lst in otd.items():
        dump(f"on-this-day/{md}.json", {"date": md, "speeches": lst})

    # words and phrases
    sig = []
    for ph in SIGNATURE:
        sig.append(ph)
    dump("words.json", {
        "total_words": stats["words"], "speeches_with_text": stats["with_text"],
        "top_words": stats["top_words"], "by_year_total": stats["by_year_total"], "by_year_top": stats["by_year_top"],
    })
    dump("phrases.json", {"signature": sig, "common": stats["phrases"][:600]})

    # corpus for phrase search: id, date, paragraphs
    corpus = [[s["id"], s["date"], s["title"], s["paragraphs"]] for s in order if s["has_text"]]
    dump("corpus.json", corpus)

    # per-speech stats table for the words page
    table = [[s["id"], s["date"], s["title"], s["stats"]["words"], s["stats"]["avg_sentence"], s["stats"]["i_count"], s["stats"]["we_count"], s["stats"]["unique_words"], s["kind"]]
             for s in order if s.get("stats")]
    dump("stats.json", table)

    # people mentioned
    people = defaultdict(lambda: {"count": 0, "speeches": []})
    for s in order:
        for m in s.get("mentions", {}).get("people", []):
            p = people[m["id"]]
            p["name"] = m["name"]
            p["count"] += m["count"]
            p["speeches"].append([s["id"], m["count"]])
    dump("people.json", sorted([{"id": k, **v} for k, v in people.items()], key=lambda x: -x["count"]))
    lands = defaultdict(lambda: {"count": 0, "speeches": []})
    for s in order:
        for m in s.get("mentions", {}).get("places", []):
            p = lands[m["id"]]
            p["name"] = m["name"]
            p["count"] += m["count"]
            p["speeches"].append([s["id"], m["count"]])
    dump("mentioned-places.json", sorted([{"id": k, **v} for k, v in lands.items()], key=lambda x: -x["count"]))
    dump("meta.json", {"speeches": len(S), "with_text": stats["with_text"], "words": stats["words"],
                       "trc_records": sum(len(s["trc"]) for s in S), "places": len(places),
                       "first": order[0]["date"], "last": max(s["date"] or "" for s in S)})
    print("api written:", len(order), "speeches,", len(places), "places")


if __name__ == "__main__":
    main()
