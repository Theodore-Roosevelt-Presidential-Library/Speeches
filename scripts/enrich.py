"""Add themes, word statistics, distinctive words, people and places mentioned, and corpus-wide
phrase and word tables. Reads and rewrites data/speeches.json; writes data/corpus_stats.json.

Themes are assigned by keyword lexicons (sources/themes.json), so they are a computed guide,
not a cataloger's judgment."""
import json, math, os, re
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

STOP = set("""a about above after again against all almost also am among an and any are aren't as at be because been before
being below between both but by can can't cannot could couldn't did didn't do does doesn't doing don't down during each
either else ever every few for from further had hadn't has hasn't have haven't having he he'd he'll he's her here here's hers
herself him himself his how how's however i i'd i'll i'm i've if in into is isn't it it's its itself just let let's like made make
many may me might more most much must mustn't my myself neither never no nor not now of off often on once one only or other
others ought our ours ourselves out over own per perhaps quite rather really said same say says shall shan't she she'd she'll
she's should shouldn't since so some such than that that's the their theirs them themselves then there there's these they
they'd they'll they're they've this those though through thus to too toward towards under until up upon us very was wasn't we
we'd we'll we're we've well were weren't what what's when when's where where's whether which while who who's whom whose why
why's will with within without won't would wouldn't yet you you'd you'll you're you've your yours yourself yourselves
mr mrs gentlemen ladies sir shall unto ye thee thou hath doth wherein whereof thereby therein hereby
one two three four five six seven eight nine ten first second third great good men man people way things thing time times
year years day days part kind sort matter fact case place point make made making get got go going come came know knew think
thought see seen want wish feel felt say said tell told give gave given take took taken put stand stood keep kept ask
something nothing anything everything someone anyone every each another way ways done whole just even still less
least far better best certain able order course need needs become became found find use used set high large small
little long within upon among whom whose already always ever never""".split())

WORD = re.compile(r"[a-z]+(?:['’][a-z]+)?(?:-[a-z]+)*")


def tokens(text):
    return WORD.findall(text.lower().replace("’", "'"))


def main():
    S = json.load(open(os.path.join(ROOT, "data/speeches.json")))
    themes = json.load(open(os.path.join(ROOT, "sources/themes.json")))
    people = json.load(open(os.path.join(ROOT, "sources/people.json")))
    places_m = json.load(open(os.path.join(ROOT, "sources/mentioned_places.json")))

    theme_res = {t["id"]: [re.compile(r"\b(?:" + "|".join(t["terms"]) + r")\b", re.I) for _ in [0]][0] for t in themes}
    people_res = [(p["id"], p["name"], re.compile(r"\b(?:" + "|".join(p["patterns"]) + r")\b")) for p in people]
    place_res = [(p["id"], p["name"], re.compile(r"\b(?:" + "|".join(p["patterns"]) + r")\b")) for p in places_m]

    df = Counter()
    docs = {}
    for s in S:
        if not s["has_text"]:
            continue
        text = "\n".join(s["paragraphs"])
        toks = tokens(text)
        docs[s["id"]] = toks
        df.update(set(toks))
    N = len(docs)

    by_year_words = defaultdict(Counter)
    by_year_total = Counter()
    corpus = Counter()
    theme_year = defaultdict(Counter)
    for s in S:
        s["themes"] = []
        s["mentions"] = {"people": [], "places": []}
        s["distinctive"] = []
        s["stats"] = None
        if not s["has_text"]:
            continue
        text = "\n".join(s["paragraphs"])
        toks = docs[s["id"]]
        n = len(toks)
        sents = [x for x in re.split(r"(?<=[.!?])\s+(?=[A-Z“\"])", text) if len(x.split()) > 2]
        content = [t for t in toks if t not in STOP and len(t) > 2]
        s["stats"] = {
            "words": n,
            "unique_words": len(set(toks)),
            "sentences": len(sents),
            "avg_sentence": round(n / max(1, len(sents)), 1),
            "minutes": max(1, round(n / 130)),   # a deliberate speaking pace
            "i_count": toks.count("i"), "we_count": toks.count("we"),
        }
        # themes: lexicon hits per thousand words
        scores = []
        for t in themes:
            hits = len(theme_res[t["id"]].findall(text))
            rate = hits * 1000 / max(n, 1)
            if hits >= 3 and rate >= t.get("min_rate", 3.0):
                scores.append((rate, t["id"]))
        scores.sort(reverse=True)
        s["themes"] = [tid for _, tid in scores[:4]]
        y = (s["date"] or "")[:4]
        if y:
            for tid in s["themes"]:
                theme_year[tid][y] += 1
            by_year_words[y].update(content)
            by_year_total[y] += n
        corpus.update(content)
        # mentions
        pm = []
        for pid, name, rx in people_res:
            c = len(rx.findall(text))
            if c:
                pm.append({"id": pid, "name": name, "count": c})
        s["mentions"]["people"] = sorted(pm, key=lambda x: -x["count"])
        lm = []
        for pid, name, rx in place_res:
            c = len(rx.findall(text))
            if c:
                lm.append({"id": pid, "name": name, "count": c})
        s["mentions"]["places"] = sorted(lm, key=lambda x: -x["count"])
        # distinctive words: tf-idf over content words
        tf = Counter(content)
        scored = []
        for w, c in tf.items():
            if c < 3 or df[w] < 2:
                continue
            scored.append((c * math.log(N / df[w]), w))
        scored.sort(reverse=True)
        s["distinctive"] = [w for _, w in scored[:10]]

    # corpus phrase table: 2- to 5-word sequences that appear in many speeches
    gram_df = Counter()
    gram_tf = Counter()
    for sid, toks in docs.items():
        seen = set()
        for n in (2, 3, 4, 5):
            for i in range(len(toks) - n + 1):
                g = toks[i:i + n]
                if g[0] in STOP or g[-1] in STOP:
                    continue
                if sum(1 for x in g if x not in STOP) < (2 if n <= 3 else 2):
                    continue
                k = " ".join(g)
                gram_tf[k] += 1
                seen.add(k)
        gram_df.update(seen)
    phrases = [{"phrase": k, "speeches": gram_df[k], "uses": gram_tf[k]} for k in gram_df if gram_df[k] >= 6]
    phrases.sort(key=lambda x: (-x["speeches"], -x["uses"]))

    stats = {
        "speeches": len(S), "with_text": N,
        "words": sum(len(t) for t in docs.values()),
        "top_words": [[w, c] for w, c in corpus.most_common(300)],
        "by_year_total": dict(sorted(by_year_total.items())),
        "by_year_top": {y: [[w, c] for w, c in cnt.most_common(40)] for y, cnt in sorted(by_year_words.items())},
        "theme_year": {k: dict(sorted(v.items())) for k, v in theme_year.items()},
        "phrases": phrases[:1500],
    }
    json.dump(S, open(os.path.join(ROOT, "data/speeches.json"), "w"), ensure_ascii=False, indent=0)
    json.dump(stats, open(os.path.join(ROOT, "data/corpus_stats.json"), "w"), ensure_ascii=False)
    print("speeches with text:", N, "words:", stats["words"])
    print("theme counts:", {k: sum(v.values()) for k, v in theme_year.items()})
    print("top phrases:", [p["phrase"] for p in phrases[:80]])


if __name__ == "__main__":
    main()
