"""Download readable crops of a speech's typescript pages from the Library of Congress image service.

usage: python3 scripts/fetch_page_crops.py SPEECH_ID [SPEECH_ID ...]
Writes build/crops/SPEECH_ID/pN-S.jpg: page N (1-based), strip S (1-3, top to bottom), each 1600 px wide,
plus pN-full.jpg (the whole page, smaller) for layout. Reads the page list from build/transcribe_jobs.json."""
import json, os, sys, time, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JOBS = {j["id"]: j for j in json.load(open(os.path.join(ROOT, "build/transcribe_jobs.json")))}


def get(url, path):
    if os.path.exists(path) and os.path.getsize(path) > 1000:
        return
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "TRPL-Speeches/0.1 (hello@trlibrary.com)"})
            open(path, "wb").write(urllib.request.urlopen(req, timeout=90).read())
            return
        except Exception as e:
            time.sleep(3 + attempt * 5)
    raise SystemExit(f"could not fetch {url}")


def main():
    for sid in sys.argv[1:]:
        job = JOBS[sid]
        out = os.path.join(ROOT, "build/crops", sid)
        os.makedirs(out, exist_ok=True)
        for n, pg in enumerate(job["pages"], 1):
            info_p = os.path.join(out, f"p{n}-info.json")
            get(pg["iiif"] + "/info.json", info_p)
            info = json.load(open(info_p))
            W, H = info["width"], info["height"]
            if pg["half"] == "a":
                x0, x1 = 0, W // 2 + 60
            elif pg["half"] == "b":
                x0, x1 = W // 2 - 60, W
            else:
                x0, x1 = 0, W
            w = x1 - x0
            get(f"{pg['iiif']}/{x0},0,{w},{H}/1000,/0/default.jpg", os.path.join(out, f"p{n}-full.jpg"))
            strip = H // 3
            for k in range(3):
                y = max(0, k * strip - 80)
                h = min(H - y, strip + 160)
                get(f"{pg['iiif']}/{x0},{y},{w},{h}/1600,/0/default.jpg", os.path.join(out, f"p{n}-{k + 1}.jpg"))
        print(sid, len(job["pages"]), "pages ->", out)


if __name__ == "__main__":
    main()
