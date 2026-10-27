"""Place parsing from printed headings and catalog titles, and offline geocoding (GeoNames)."""
import csv, json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

STATES = {
    "AL": ["alabama", "ala"], "AZ": ["arizona", "ariz", "arizona territory", "ariz. t"], "AR": ["arkansas", "ark"],
    "CA": ["california", "cal", "calif"], "CO": ["colorado", "colo"], "CT": ["connecticut", "conn"],
    "DE": ["delaware", "del"], "DC": ["d. c", "d.c", "dc", "district of columbia"], "FL": ["florida", "fla"],
    "GA": ["georgia", "ga"], "ID": ["idaho", "ida"], "IL": ["illinois", "ill"], "IN": ["indiana", "ind"],
    "IA": ["iowa", "ia"], "KS": ["kansas", "kan", "kans"], "KY": ["kentucky", "ky"], "LA": ["louisiana", "la"],
    "ME": ["maine", "me"], "MD": ["maryland", "md"], "MA": ["massachusetts", "mass", "massachussetts"], "MI": ["michigan", "mich"],
    "MN": ["minnesota", "minn"], "MS": ["mississippi", "miss"], "MO": ["missouri", "mo"], "MT": ["montana", "mont"],
    "NE": ["nebraska", "neb", "nebr"], "NV": ["nevada", "nev"], "NH": ["new hampshire", "n. h", "n.h"],
    "NJ": ["new jersey", "n. j", "n.j"], "NM": ["new mexico", "n. m", "n. mex", "n.m", "new mexico territory"],
    "NY": ["new york", "n. y", "n.y", "new york state", "l. i", "l.i", "long island"], "NC": ["north carolina", "n. c", "n.c"],
    "ND": ["north dakota", "n. d", "n. dak", "n.d", "n.dak"], "OH": ["ohio", "o"], "OK": ["oklahoma", "okla", "oklahoma territory", "o. t"],
    "OR": ["oregon", "ore", "oreg"], "PA": ["pennsylvania", "pa", "penn"], "RI": ["rhode island", "r. i", "r.i"],
    "SC": ["south carolina", "s. c", "s.c"], "SD": ["south dakota", "s. d", "s. dak", "s.d", "s.dak"],
    "TN": ["tennessee", "tenn"], "TX": ["texas", "tex"], "UT": ["utah"], "VT": ["vermont", "vt"],
    "VA": ["virginia", "va"], "WA": ["washington state", "wash", "washington"], "WV": ["west virginia", "w. va", "w.va"],
    "WI": ["wisconsin", "wis"], "WY": ["wyoming", "wyo"], "IT": ["indian territory", "ind. t", "ind. ter", "i. t"],
}
STATE_NAME = {"AL": "Alabama", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado", "CT": "Connecticut",
              "DE": "Delaware", "DC": "D.C.", "FL": "Florida", "GA": "Georgia", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana",
              "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
              "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri",
              "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey",
              "NM": "New Mexico", "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio",
              "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
              "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia",
              "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming", "IT": "Indian Territory"}
VARIANT = {}
for code, vs in STATES.items():
    for v in vs:
        VARIANT[re.sub(r"[^a-z]", "", v)] = code
VARIANT.pop("o", None)  # too ambiguous on its own

# cities named without a state in the printed headings
BARE_CITY = {
    "washington court house": ("Washington Court House", "OH"),
    "washington": ("Washington", "DC"), "the white house": ("Washington", "DC"), "white house": ("Washington", "DC"),
    "new york": ("New York", "NY"), "new york city": ("New York", "NY"), "boston": ("Boston", "MA"),
    "chicago": ("Chicago", "IL"), "philadelphia": ("Philadelphia", "PA"), "baltimore": ("Baltimore", "MD"),
    "west point": ("West Point", "NY"), "annapolis": ("Annapolis", "MD"), "oyster bay": ("Oyster Bay", "NY"),
    "arlington": ("Arlington", "VA"), "arlington national cemetery": ("Arlington", "VA"), "cincinnati": ("Cincinnati", "OH"),
    "detroit": ("Detroit", "MI"), "st. louis": ("St. Louis", "MO"), "san francisco": ("San Francisco", "CA"),
    "brooklyn": ("Brooklyn", "NY"), "jamestown exposition": ("Norfolk", "VA"), "gettysburg": ("Gettysburg", "PA"),
    "valley forge": ("Valley Forge", "PA"), "cambridge": ("Cambridge", "MA"), "new haven": ("New Haven", "CT"),
    "princeton": ("Princeton", "NJ"), "pittsburg": ("Pittsburgh", "PA"), "pittsburgh": ("Pittsburgh", "PA"),
    "milwaukee": ("Milwaukee", "WI"), "denver": ("Denver", "CO"), "grand canyon": ("Grand Canyon", "AZ"),
    "yellowstone": ("Yellowstone National Park", "WY"), "jamestown": ("Jamestown", "VA"), "norfolk": ("Norfolk", "VA"),
    "chautauqua": ("Chautauqua", "NY"), "groton": ("Groton", "MA"), 
 "chicago university": ("Chicago", "IL"), "new orleans": ("New Orleans", "LA"),
    "louisville": ("Louisville", "KY"), "memphis": ("Memphis", "TN"), "indianapolis": ("Indianapolis", "IN"),
}
# institutions and landmarks named without a town
LANDMARKS = {
    "howard university": ("Washington", "DC"), "georgetown college": ("Washington", "DC"), "gallaudet": ("Washington", "DC"),
    "corcoran": ("Washington", "DC"), "bureau of american republics": ("Washington", "DC"), "conservation conference": ("Washington", "DC"),
    "white house": ("Washington", "DC"), "war college": ("Washington", "DC"), "naval academy": ("Annapolis", "MD"),
    "harvard": ("Cambridge", "MA"), "lookout mountain": ("Lookout Mountain", "TN"), "chickamauga": ("Chickamauga", "GA"),
    "charleston exposition": ("Charleston", "SC"), "carnegie hall": ("New York", "NY"), "waldorf": ("New York", "NY"),
    "hotel astor": ("New York", "NY"), "sherry's": ("New York", "NY"), "liederkranz": ("New York", "NY"), "liederkrans": ("New York", "NY"),
    "culebra": ("Culebra", "Panama Canal Zone"), "matachin": ("Matachin", "Panama Canal Zone"), "aibonito": ("Aibonito", "Puerto Rico"),
    "university and normal school of porto rico": ("Río Piedras", "Puerto Rico"), "matinnecock": ("Locust Valley", "NY"),
    "roosevelt, arizona": ("Roosevelt Dam", "AZ"), "roosevelt dam": ("Roosevelt Dam", "AZ"), "forest hills": ("Forest Hills", "NY"),
    "pomona college": ("Claremont", "CA"), "santa barbara": ("Santa Barbara", "CA"), "toronto": ("Toronto", "Canada"),
    "rio de janiero": ("Rio de Janeiro", "Brazil"), "rio de janeiro": ("Rio de Janeiro", "Brazil"), "lake mohonk": ("Mohonk Lake", "NY"),
    "upper divide creek": ("Upper Divide Creek", "CO"), "invalides": ("Paris", "France"), "guildhall": ("London", "England"),
    "nobel prize committee": ("Christiania (Oslo)", "Norway"),
}
# special coordinates for places that are not towns
SPECIAL = {
    ("Grand Canyon", "AZ"): (36.0573, -112.1430),
    ("Yellowstone National Park", "WY"): (44.9772, -110.6960),  # Gardiner gate area
    ("Minnesota State Fairgrounds", "MN"): (44.9817, -93.1694),
    ("Arlington", "VA"): (38.8783, -77.0687),   # Arlington National Cemetery
    ("Valley Forge", "PA"): (40.0970, -75.4400),
    ("Gettysburg", "PA"): (39.8309, -77.2311),
    ("Antietam", "MD"): (39.4734, -77.7449),
    ("Saratoga", "NY"): (43.0831, -73.7846),
    ("Weirs", "NH"): (43.6087, -71.4614),
    ("North Yakima", "WA"): (46.6021, -120.5059),   # now Yakima
    ("Hampstead", "NY"): (40.7062, -73.6187),       # spelled so in the catalog; Hempstead, Long Island
    ("The Weirs", "NH"): (43.6087, -71.4614),
    ("Fort Myer", "VA"): (38.8806, -77.0789),
    ("Brandy", "VA"): (38.5068, -77.8933),
    ("Sisson", "CA"): (41.3099, -122.3106),   # now Mount Shasta
    ("Woodville", "OR"): (42.4337, -123.0478),  # now Rogue River
    ("Hermitage", "TN"): (36.2147, -86.6136),
    ("Roosevelt Dam", "AZ"): (33.6717, -111.1612),
    ("Upper Divide Creek", "CO"): (39.35, -107.55),
    ("Blue Schoolhouse on Upper Divide Creek", "CO"): (39.35, -107.55),
    ("Lookout Mountain", "TN"): (35.0098, -85.3442),
}
FOREIGN = {
    "khartoum": ("Khartoum", "Sudan", 15.5007, 32.5599), "khartum": ("Khartoum", "Sudan", 15.5007, 32.5599),
    "cairo": ("Cairo", "Egypt", 30.0444, 31.2357), "paris": ("Paris", "France", 48.8566, 2.3522),
    "christiania": ("Christiania (Oslo)", "Norway", 59.9139, 10.7522), "berlin": ("Berlin", "Germany", 52.52, 13.405),
    "cambridge england": ("Cambridge", "England", 52.2053, 0.1218), "london": ("London", "England", 51.5074, -0.1278),
    "oxford": ("Oxford", "England", 51.7520, -1.2577), "rome": ("Rome", "Italy", 41.9028, 12.4964),
    "buenos aires": ("Buenos Aires", "Argentina", -34.6037, -58.3816), "rio de janeiro": ("Rio de Janeiro", "Brazil", -22.9068, -43.1729),
    "panama": ("Panama", "Panama", 8.9824, -79.5199), "colon": ("Colón", "Panama", 9.3592, -79.9014),
    "san juan": ("San Juan", "Puerto Rico", 18.4655, -66.1057), "ponce": ("Ponce", "Puerto Rico", 18.0111, -66.6141),
    "havana": ("Havana", "Cuba", 23.1136, -82.3666), "stockholm": ("Stockholm", "Sweden", 59.3293, 18.0686),
    "copenhagen": ("Copenhagen", "Denmark", 55.6761, 12.5683), "budapest": ("Budapest", "Hungary", 47.4979, 19.0402),
    "vienna": ("Vienna", "Austria", 48.2082, 16.3738), "amsterdam": ("Amsterdam", "Netherlands", 52.3676, 4.9041),
    "the hague": ("The Hague", "Netherlands", 52.0705, 4.3007), "brussels": ("Brussels", "Belgium", 50.8503, 4.3517),
    "edinburgh": ("Edinburgh", "Scotland", 55.9533, -3.1883),
    "toronto": ("Toronto", "Canada", 43.6532, -79.3832), "culebra": ("Culebra", "Panama Canal Zone", 9.0450, -79.6560),
    "matachin": ("Matachin", "Panama Canal Zone", 9.1050, -79.7150), "aibonito": ("Aibonito", "Puerto Rico", 18.1400, -66.2660),
    "rio piedras": ("Río Piedras", "Puerto Rico", 18.3995, -66.0500), "rio de janiero": ("Rio de Janeiro", "Brazil", -22.9068, -43.1729), "dublin": ("Dublin", "Ireland", 53.3498, -6.2603),
}


def skey(s):
    return re.sub(r"[^a-z]", "", s.lower())


_gaz = None


def gazetteer():
    global _gaz
    if _gaz is None:
        _gaz = {}
        path = os.path.join(ROOT, "build/geo/us_places.tsv")
        if os.path.exists(path):
            for row in csv.reader(open(path, encoding="utf-8"), delimiter="\t", quoting=csv.QUOTE_NONE):
                name, ascii_, lat, lon, admin1, pop, fcode = row
                pop = int(pop or 0)
                for n in {name, ascii_}:
                    k = (skey(n), admin1)
                    if k not in _gaz or pop > _gaz[k][2]:
                        _gaz[k] = (float(lat), float(lon), pop)
    return _gaz


CACHE_PATH = os.path.join(ROOT, "data/places.json")


def load_cache():
    if os.path.exists(CACHE_PATH):
        return json.load(open(CACHE_PATH))
    return {}


def place_id(city, region):
    return re.sub(r"[^a-z0-9]+", "-", f"{city} {region}".lower()).strip("-")


ALIASES = {}


def geocode(city, code, cache):
    """city + two-letter state code (or country name for foreign places)."""
    pid = place_id(city, STATE_NAME.get(code, code))
    pid = ALIASES.get(pid, pid)
    if pid in cache:
        return pid
    lat = lon = None
    method = None
    if (city, code) in SPECIAL:
        lat, lon = SPECIAL[(city, code)]
        method = "manual"
    elif code not in STATE_NAME:
        for key, val in FOREIGN.items():
            if val[0] == city:
                lat, lon = val[2], val[3]
                method = "manual"
                break
    elif code in STATE_NAME:
        g = gazetteer()
        TYPO = {"Loominster": "Leominster", "Gettsyburg": "Gettysburg", "Ooltewah Junction": "Ooltewah", "Midland City": "Midland"}
        city = TYPO.get(city, city)
        c = city.replace("St. ", "Saint ").replace("Ft. ", "Fort ").replace("Mt. ", "Mount ")
        for key, (lc, lcode) in LANDMARKS.items():
            if key in city.lower() and lcode == code:
                city = lc
                break
        m_of = re.search(r"^.*\b(?:of|at|in|reaching|near)\s+(?:the\s+)?([A-Z][\w.']*(?: [A-Z][\w.']*)*)$", city)
        suffixes = [m_of.group(1).strip()] if m_of else []
        for cand in [city, c, city.replace("St. ", "St "), city + " City", re.sub(r"\s*\(.*\)", "", city)] + suffixes:
            hit = g.get((skey(cand), code))
            if hit:
                lat, lon, _ = hit
                method = "geonames"
                if cand in suffixes:
                    city = cand
                break
        if lat is None and (code == "DC" or (code == "NY" and re.search(r"church|hotel|hall|club|residence|office|library|theater|theatre", city, re.I))):
            big = {"DC": "Washington", "NY": "New York City"}[code]
            hit = g.get((skey(big), code))
            big = {"DC": "Washington", "NY": "New York"}[code]
            if hit:
                lat, lon, _ = hit
                method = "geonames"
                city = big
        if lat is None:
            for key, (lc, lcode) in LANDMARKS.items():
                if key in city.lower() and lcode == code:
                    hit = g.get((skey(lc), code))
                    if hit:
                        lat, lon, _ = hit
                        method = "geonames"
                        city = lc
                        break
    DISPLAY = {"North Yakima": "North Yakima (now Yakima)", "Sisson": "Sisson (now Mount Shasta)", "Woodville": "Woodville (now Rogue River)", "Hampstead": "Hempstead"}
    final = place_id(city, STATE_NAME.get(code, code))
    if final != pid:
        ALIASES[pid] = final
        pid = final
        if pid in cache:
            return pid
    cache[pid] = {"id": pid, "name": DISPLAY.get(city, city), "region": STATE_NAME.get(code, code),
                  "country": "United States" if code in STATE_NAME else code,
                  "lat": lat, "lon": lon, "geocode": method}
    return pid


def parse_place(text, strict=False):
    """Find (city, state_code) in a heading or title. Returns (city, code, start_index) or None."""
    t = re.sub(r"\([^)]*\)", "", text)
    t = re.sub(r"\s+", " ", t).strip().rstrip(".,")
    segs = [s.strip() for s in re.split(r",", t) if s.strip()]
    low = [s.lower() for s in segs]
    flat = re.sub(r"[^a-z ]", " ", t.lower())
    flat = re.sub(r"\s+", " ", flat)
    us_state_named = any(VARIANT.get(re.sub(r"[^a-z]", "", x)) for x in low[1:])
    if not us_state_named or re.search(r"\b(england|france|germany|norway|egypt|sudan|italy|brazil|canada|ontario)\b", flat):
        if "cambridge" in flat and "england" in flat:
            v = FOREIGN["cambridge england"]
            return v[0], v[1], 0
        for k in range(len(segs) - 1, -1, -1):
            for key, val in FOREIGN.items():
                if re.search(r"\b" + key + r"\b", low[k]):
                    return val[0], val[1], k
    for k in range(len(segs) - 1, 0, -1):
        code = VARIANT.get(re.sub(r"[^a-z]", "", low[k]))
        if code and strict:
            intro = any(re.search(r"\b(at|in|near|from)\b", x) for x in low[:k])
            if not intro and not re.match(r"^(remarks|address|speech|colonel)", low[0]):
                code = None
        if code == "WA" and re.sub(r"[^a-z]", "", low[k]) == "washington":
            prev = re.sub(r"^.*\b(at|in|near)\s+", "", low[k - 1]).strip()
            prev = re.sub(r"^(the|of)\s+", "", prev)
            known_wa = (skey(prev), "WA") in gazetteer() or any(c.lower() == prev for c, st in SPECIAL if st == "WA")
            if not known_wa:
                return "Washington", "DC", k
        if code:
            city = re.sub(r"^(at|in|near|on|to|before)\s+(the\s+)?", "", segs[k - 1], flags=re.I).strip()
            if re.search(r"\b(at|in|near)\s+\w", city, flags=re.I):
                city = re.sub(r"^.*\b(at|in|near)\s+", "", city, flags=re.I)
            city = re.sub(r"^(the|of)\s+", "", city, flags=re.I)
            city = re.sub(r"^(Remarks|Address|Speech)( of)?( President| Governor| Colonel)?( Theodore)? Roosevelt\s+", "", city, flags=re.I)
            # Washington alone with no D.C. after it means the city when the next is a state abbreviation for DC
            return smart_title(city), code, k - 1
    for k in range(len(segs) - 1, -1, -1):
        if strict and not re.search(r"\b(at|in|near)\b", low[k]):
            continue
        s = re.sub(r"^(at|in|near|on|to|before)\s+(the\s+)?", "", low[k]).strip()
        s2 = re.sub(r"^.*\b(at|in)\s+", "", s)
        for cand in (s, s2, "the " + s):
            if cand in BARE_CITY:
                c, code = BARE_CITY[cand]
                return c, code, k
        for key, (c, code) in BARE_CITY.items():
            if re.search(r"\b" + re.escape(key) + r"\b", low[k]) and len(key) > 6:
                return c, code, k
    full = t.lower()
    for key, (c, code) in LANDMARKS.items():
        if key in full:
            return c, code, 0
    # "Speech at Racine": a town named after at/in, matched to the most populous US place of that name
    m = re.search(r"\b(?:at|in)\s+((?:[A-Z][a-z]+\.?\s?){1,3})", t)
    if m:
        name = m.group(1).strip()
        if VARIANT.get(re.sub(r"[^a-z]", "", name.lower())) or name.lower() in ("the", "new"):
            return None
        g = gazetteer()
        best = None
        for (k2, code), (lat, lon, pop) in ((kk, vv) for kk, vv in g.items() if kk[0] == skey(name)):
            if pop > 5000 and (best is None or pop > best[2]):
                best = (name, code, pop)
        if best:
            return best[0], best[1], 0
    return None


SMALL = {"a", "an", "the", "of", "at", "in", "on", "to", "and", "for", "by", "with", "from", "upon", "before", "or", "as", "into"}


def smart_title(s):
    s = re.sub(r"\s+", " ", s.strip())
    letters = [c for c in s if c.isalpha()]
    if not letters or sum(c.isupper() for c in letters) / len(letters) < 0.8:
        return s
    # OCR debris in headings
    s = re.sub(r"(?<=\w)[’'](?=\s)", "", s)
    s = re.sub(r"\s-(?=[A-Z])", " ", s)
    s = re.sub(r"\s[.,](?=[A-Z])", " ", s)
    words = s.split(" ")
    out = []
    for i, w in enumerate(words):
        lw = w.lower()
        if re.fullmatch(r"([A-Z]\.)+,?", w) or re.fullmatch(r"[IVX]+,?", w) and len(w) <= 4 and w not in ("I", "VI,"):
            out.append(w)
            continue
        core = re.sub(r"[^a-z']", "", lw)
        if i > 0 and core in SMALL:
            out.append(lw)
            continue
        t = lw[:1].upper() + lw[1:]
        t = re.sub(r"^(Mc|Mac)([a-z])", lambda m: m.group(1) + m.group(2).upper(), t) if lw.startswith("mc") else t
        t = re.sub(r"-([a-z])", lambda m: "-" + m.group(1).upper(), t)
        t = re.sub(r"^([\"“'‘(])([a-z])", lambda m: m.group(1) + m.group(2).upper(), t)
        out.append(t)
    r = " ".join(out)
    r = r.replace("Y. M. C. A.", "Y.M.C.A.").replace("G. A. R.", "G.A.R.").replace("D. C.", "D.C.")
    r = re.sub(r"\bSt\b", "St.", r).replace("St..", "St.")
    return r
