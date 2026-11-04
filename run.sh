#!/usr/bin/env bash
# Rebuild the lead workbook for one client.  Usage: ./run.sh infinit
set -euo pipefail
cd "$(dirname "$0")"
CLIENT="${1:?client config name, e.g. infinit}"
CFG="configs/$CLIENT.json"
DATA="data/$CLIENT"
mkdir -p "$DATA" data/raw output
ST=$(python3 -c "import json;print(json.load(open('$CFG'))['state_abbr'].lower())")
FIPS=$(python3 -c "import json;print(json.load(open('$CFG'))['state_fips'])")

# Public source files (refreshed monthly by the IRS / yearly by Census)
[ -s "data/raw/eo_$ST.csv" ] || curl -sS -o "data/raw/eo_$ST.csv" "https://www.irs.gov/pub/irs-soi/eo_$ST.csv"
[ -s "data/raw/sub_est_$FIPS.csv" ] || curl -sS -o "data/raw/sub_est_$FIPS.csv" \
  "https://www2.census.gov/programs-surveys/popest/datasets/2020-2024/cities/totals/sub-est2024_$FIPS.csv"

python3 sources/irs_bmf.py   "$CFG" "data/raw/eo_$ST.csv"        "$DATA/nonprofits.json"
python3 sources/census_gov.py "$CFG" "data/raw/sub_est_$FIPS.csv" "$DATA/gov.json"
python3 sources/usaspending.py "$CFG" "$DATA/dod.json"

# top_leads.json (researched accounts + drafts) and apollo_searches.json are written per client by Claude
python3 build.py "$CFG" "$DATA" "output/${CLIENT}_leads_$(date +%Y-%m-%d).xlsx"
