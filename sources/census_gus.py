"""Official websites, addresses and lead-official titles for local governments and school districts
(Census Bureau Government Units listing, 2022 Census of Governments, free).
Download: https://www2.census.gov/programs-surveys/gus/datasets/2022/govt_units_2022.ZIP
Usage: python3 sources/census_gus.py configs/<client>.json data/raw/gus/Govt_Units_2022_Final.xlsx data/<client>
Writes gov_directory.json (municipalities, keyed by "<name>|<kind>") and schools.json."""
import json, re, sys
import openpyxl

KIND = {"2 - MUNICIPAL": None, "3 - TOWNSHIP": "Township"}


def clean_web(w):
    if not w:
        return ""
    return re.sub(r"^https?://", "", str(w).strip().lower()).strip("/").removeprefix("www.")


def base_name(unit):
    n = unit.upper()
    for pre in ("CITY OF ", "VILLAGE OF ", "TOWNSHIP OF ", "TOWN OF "):
        if n.startswith(pre):
            return n[len(pre):].title(), pre.strip().split()[0].title()
    return n.title(), ""


def main(cfg_path, xlsx, out_dir):
    cfg = json.load(open(cfg_path))
    counties = {k.lstrip("0"): v for k, v in cfg["counties"].items()}
    wb = openpyxl.load_workbook(xlsx, read_only=True)
    directory, schools = {}, []
    for sheet in ("General Purpose", "School District"):
        rows = wb[sheet].iter_rows(values_only=True)
        h = next(rows)
        for r in rows:
            d = dict(zip(h, r))
            if d["FIPS_STATE"] != cfg["state_fips"] or str(d["FIPS_COUNTY"]).lstrip("0") not in counties:
                continue
            if d.get("IS_ACTIVE") != "Y":
                continue
            rec = {"website": clean_web(d["WEB_ADDRESS"]), "contact_title": (d["TITLE"] or "").title(),
                   "address": " ".join(filter(None, [d["ADDRESS1"], d["ADDRESS2"]])).title(),
                   "mail_city": (d["CITY"] or "").title(), "zip": d["ZIP"] or "",
                   "county": counties[str(d["FIPS_COUNTY"]).lstrip("0")]}
            if sheet == "General Purpose":
                if d["UNIT_TYPE"] not in KIND:
                    continue
                name, kind = base_name(d["UNIT_NAME"])
                kind = kind if kind in ("City", "Village") else "Township" if d["UNIT_TYPE"].startswith("3") else kind
                key = f"{name} Township|Township" if kind == "Township" else f"{name}|{kind}"
                directory[key] = rec
            else:
                schools.append({**rec, "name": d["UNIT_NAME"].title().replace("Sch Dist", "School District")
                                .replace("Cty", "City").replace("Vlg", "Village"),
                                "enrollment": d["ENROLLMENT"] or 0})
    json.dump(directory, open(f"{out_dir}/gov_directory.json", "w"), indent=1)
    json.dump(schools, open(f"{out_dir}/schools.json", "w"), indent=1)
    print(f"{len(directory)} municipalities, {len(schools)} school districts", file=sys.stderr)


if __name__ == "__main__":
    main(*sys.argv[1:4])
