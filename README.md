# Speeches

Theodore Roosevelt's speeches as an open dataset and website, from the Theodore Roosevelt Presidential Library. A companion to [Day by Day](https://daybyday.labs.trlibrary.com/).

Site: https://speeches.labs.trlibrary.com (once GitHub Pages is turned on for this repo)

## What is in it

- **Full texts** of about 520 addresses, lectures and messages to Congress, from editions printed in his lifetime (public domain):
  - *Presidential Addresses and State Papers* (Review of Reviews Co., 1910), parts 1 to 8. Parts 1 to 4 use the proofread Project Gutenberg texts; parts 5 to 8 are machine-read (OCR) from Internet Archive scans.
  - *The Strenuous Life*, *African and European Addresses*, *The New Nationalism*, *Realizable Ideals*, *History as Literature*, *California Addresses* (California Promotion Committee, 1903; 52 talks of the May 1903 California tour, machine-read from an Internet Archive scan), and single addresses printed as pamphlets (1905 to 1912), including the 1912 "Confession of Faith" and the Milwaukee speech.
- **Archive records** for about 470 more speeches from the Theodore Roosevelt Center's digital library (resource type "Speech"), each linked to its scan. Most are short tour remarks from 1902 and 1903 whose texts are not yet transcribed here.
- **Source links on every speech**, in this order: Theodore Roosevelt Center record, Library of Congress (Theodore Roosevelt Papers, Series 5, reel and frame, derived from the TRC scan path), then the printed edition (page scan and Gutenberg text), then the Day by Day page for that date.
- **Computed layers**: places geocoded with GeoNames; topics from keyword lexicons (`sources/themes.json`); people and places named in each speech; distinctive words (tf-idf); phrase counts; word statistics.
- **Date checks**: each dated speech is compared with Day by Day. When the two put him more than 700 km apart, or a document says "to be delivered," the speech carries a note in `checks`.

Proclamations and public letters printed in the same volumes are left out for now.

## Layout

```
sources/            inputs: TRC catalog JSON, LOC Series 5 segments, Gutenberg and IA texts,
                    collections.json (hand-checked manifest of books and pamphlets),
                    overrides.json (hand corrections, each with a reason), themes/people/places lexicons
scripts/            the pipeline (Python 3, standard library only)
data/               speeches.json (everything), places.json, corpus_stats.json
api/v1/             the static JSON API the site reads (generated)
templates/          page templates; scripts/build_pages.py writes the .html pages at the root
assets/             CSS and shared JS (brand tokens shared with Day by Day)
```

## Rebuild

```
python3 -m venv .venv && source .venv/bin/activate   # no packages needed, but keep it tidy
./build.sh
python3 -m http.server 8000   # then open http://localhost:8000
```

`build.sh` downloads the GeoNames US places file on first run into `build/` (ignored by git). To refresh the TRC catalog, re-run the fetch in `scripts/fetch_trc_pages.py` after updating `sources/trc/page*.json` from the TRC REST API (`/wp-json/wp/v2/digital-library?dl_resource_type=292993`).

## Rights and care

Speech texts are in the public domain. TRC catalog descriptions are not copied; only titles, dates, page counts and links. Library of Congress images are linked from its IIIF image service ("No known restrictions on use or reproduction").

Texts are shown as printed. Check the original document before quoting. Corrections: hello@trlibrary.com.
