"""Fetch TRC record pages for speech records to read the scan image paths (reel/frame for LOC items)
and the subject headings. Cached in sources/trc/pages/ (gitignored raw), summarized to sources/trc/trc_images.json."""
import json, os, re, time, urllib.request, html
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
raw = json.load(open(f"{ROOT}/sources/trc/trc_speeches_raw.json"))
cache = f"{ROOT}/sources/trc/pages"
os.makedirs(cache, exist_ok=True)
out = {}
for i, r in enumerate(raw):
    p = f"{cache}/{r['id']}.html"
    if not os.path.exists(p):
        for attempt in range(3):
            try:
                req = urllib.request.Request(r['link'], headers={"User-Agent": "TRPL-Speeches/0.1 (hello@trlibrary.com)"})
                s = urllib.request.urlopen(req, timeout=40).read().decode('utf-8', 'replace')
                open(p, 'w').write(s); break
            except Exception as e:
                print('retry', r['id'], e); time.sleep(5)
        time.sleep(0.7)
    if not os.path.exists(p):
        continue
    s = open(p).read()
    imgs = list(dict.fromkeys(re.findall(r'https://s3-us-west-2\.amazonaws\.com/theodorerooseveltcenter/[^"\'\s)]+\.(?:jpg|jpeg|png)', s)))
    subj = []
    m = re.search(r'Subject\(s\):(.*?)Click on image', re.sub(r'<[^>]+>', '\n', s), re.S)
    if m:
        subj = [html.unescape(x.strip()) for x in m.group(1).split('\n') if x.strip() and x.strip() != ',']
    out[r['id']] = {"images": imgs, "subjects": subj}
    if i % 50 == 0: print(i, r['id'], len(imgs), subj[:3], flush=True)
json.dump(out, open(f"{ROOT}/sources/trc/trc_pages_summary.json", 'w'), indent=1)
print('done', len(out))
