"""Tax-exempt organizations from the IRS Exempt Organizations Business Master File (free).
Download: https://www.irs.gov/pub/irs-soi/eo_<state>.csv"""
import csv, json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import geo

# Broad NTEE major groups, for a readable "type" column.
NTEE_MAJOR = {
    "A": "Arts & culture", "B": "Education", "C": "Environment", "D": "Animal-related", "E": "Health care",
    "F": "Mental health", "G": "Disease/disorder", "H": "Medical research", "I": "Crime & legal",
    "J": "Employment", "K": "Food & nutrition", "L": "Housing", "M": "Public safety", "N": "Recreation & sports",
    "O": "Youth development", "P": "Human services", "Q": "International", "R": "Civil rights",
    "S": "Community improvement", "T": "Philanthropy", "U": "Science & tech", "V": "Social science",
    "W": "Public benefit", "X": "Religion", "Y": "Mutual benefit", "Z": "Unknown",
}


def fetch(cfg, path):
    n = cfg["nonprofit"]
    rows = []
    for r in csv.DictReader(open(path, encoding="latin-1")):
        if r["ZIP"][:3] not in cfg["zip3"]:
            continue
        try:
            rev = int(r["REVENUE_AMT"] or 0)
        except ValueError:
            continue
        if not (n["min_revenue"] <= rev <= n["max_revenue"]):
            continue
        if n["exclude_private_foundations"] and r["FOUNDATION"] in ("02", "03", "04"):
            continue
        office, dist = geo.nearest_office(cfg, geo.point_for_zip(r["ZIP"][:5]))
        if dist is None or dist > cfg.get("max_miles_from_office", 999):
            continue
        ntee = (r["NTEE_CD"] or "Z").strip() or "Z"
        vertical = n["vertical_by_ntee_prefix"].get(ntee[0], n["default_vertical"])
        if ntee.startswith("E2"):  # hospitals: large, usually have in-house IT
            vertical = "Healthcare"
        rows.append({
            "name": r["NAME"].title(), "ein": r["EIN"], "address": r["STREET"].title(),
            "city": r["CITY"].title(), "zip": r["ZIP"][:5], "ntee": ntee,
            "type": NTEE_MAJOR.get(ntee[0], "Other"), "revenue": rev,
            "assets": int(r["ASSET_AMT"] or 0), "tax_period": r["TAX_PERIOD"], "vertical": vertical,
            "office": office, "miles": dist,
            "propublica": f"https://projects.propublica.org/nonprofits/organizations/{r['EIN']}",
        })
    return rows


if __name__ == "__main__":
    cfg = json.load(open(sys.argv[1]))
    rows = fetch(cfg, sys.argv[2])
    json.dump(rows, open(sys.argv[3], "w"), indent=1)
    print(len(rows), "nonprofits written", file=sys.stderr)
