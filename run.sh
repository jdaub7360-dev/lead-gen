#!/usr/bin/env bash
# Lead pipeline for one client.
#   ./run.sh <client> data    refresh public data + enrichment (run first)
#   ./run.sh <client> build   merge Top Leads enrichment and build the workbook (after top_leads.json is written)
#   ./run.sh <client> all     both
set -uo pipefail
cd "$(dirname "$0")"
CLIENT="${1:?client config name, e.g. infinit}"
STEP="${2:-all}"
CFG="configs/$CLIENT.json"
DATA="data/$CLIENT"
RAW="data/raw"
mkdir -p "$DATA" "$RAW" output
ST=$(python3 -c "import json;print(json.load(open('$CFG'))['state_abbr'].lower())")
FIPS=$(python3 -c "import json;print(json.load(open('$CFG'))['state_fips'])")
TODAY=$(date +%Y-%m-%d)
pip install -q zipfile-deflate64 >/dev/null 2>&1 || true

fetch() { [ -s "$2" ] || curl -sS -m 300 -o "$2" "$1"; }
unzip_py() { python3 -c "import zipfile,sys; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" "$1" "$2"; }
step() { echo "== $*"; "$@" || echo "!! step failed: $*"; }   # keep going; report failures

if [ "$STEP" = data ] || [ "$STEP" = all ]; then
  # Public source files (IRS monthly, Census yearly)
  fetch "https://www.irs.gov/pub/irs-soi/eo_$ST.csv" "$RAW/eo_$ST.csv"
  fetch "https://www2.census.gov/programs-surveys/popest/datasets/2020-2024/cities/totals/sub-est2024_$FIPS.csv" "$RAW/sub_est_$FIPS.csv"
  fetch "https://www2.census.gov/programs-surveys/gus/datasets/2022/govt_units_2022.ZIP" "$RAW/govt_units_2022.zip"
  [ -s "$RAW/gus/Govt_Units_2022_Final.xlsx" ] || unzip_py "$RAW/govt_units_2022.zip" "$RAW/gus"
  for g in zcta counties; do
    fetch "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/2024_Gaz_${g}_national.zip" "$RAW/gaz_$g.zip"
    [ -s "$RAW/2024_Gaz_${g}_national.txt" ] || unzip_py "$RAW/gaz_$g.zip" "$RAW"
  done

  step python3 sources/irs_bmf.py     "$CFG" "$RAW/eo_$ST.csv" "$DATA/nonprofits.json"
  step python3 sources/census_gov.py  "$CFG" "$RAW/sub_est_$FIPS.csv" "$DATA/gov.json"
  step python3 sources/census_gus.py  "$CFG" "$RAW/gus/Govt_Units_2022_Final.xlsx" "$DATA"
  step python3 sources/usaspending.py "$CFG" "$DATA/dod.json"
  step python3 sources/hhs_breach.py  "$CFG" "$DATA/breaches.json"
  step python3 sources/erate.py       "$CFG" "$DATA"   # competitor clients, open school bids, cyber pilot
  step python3 sources/irs_990.py     "$CFG" "$DATA/nonprofits.json" "$RAW"
  step python3 enrich.py domains "$DATA"
  step python3 sources/domain_check.py "$DATA/domains.json"
  # Rep's status updates from the live Google Sheet (needs GOOGLE_SERVICE_ACCOUNT_JSON; skipped otherwise)
  [ -n "${GOOGLE_SERVICE_ACCOUNT_JSON:-}" ] && step python3 sources/sheets_sync.py pull "$CFG" "$DATA"
fi

if [ "$STEP" = build ] || [ "$STEP" = all ]; then
  step python3 enrich.py domains "$DATA"
  step python3 sources/domain_check.py "$DATA/domains.json"   # checks any new Top Lead websites
  step python3 enrich.py top "$DATA"
  step python3 build.py "$CFG" "$DATA" "output/${CLIENT}_leads_$TODAY.xlsx"
  [ -n "${GOOGLE_SERVICE_ACCOUNT_JSON:-}" ] && step python3 sources/sheets_sync.py push "$CFG" "$DATA"
fi
