#!/usr/bin/env bash
# Rebuild the dataset and the site from the sources in this repo.
# Needs Python 3.9+, no packages. The GeoNames place file is downloaded on first run.
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -f build/geo/us_places.tsv ]; then
  mkdir -p build/geo
  curl -sL https://download.geonames.org/export/dump/US.zip -o build/geo/US.zip
  (cd build/geo && unzip -o -q US.zip US.txt && awk -F'\t' '$7=="P" {print $2"\t"$3"\t"$5"\t"$6"\t"$11"\t"$15"\t"$8}' US.txt > us_places.tsv && rm US.txt US.zip)
fi
python3 scripts/parse_pasp.py
python3 scripts/parse_collections.py > /dev/null
python3 scripts/build_dataset.py
python3 scripts/enrich.py > /dev/null
python3 scripts/build_site.py
python3 scripts/build_pages.py > /dev/null
