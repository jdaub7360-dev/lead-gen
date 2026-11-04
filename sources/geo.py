"""Distance from a ZIP code (or county) to the client's nearest office, using Census Gazetteer centroids.
Files (free): https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/
  2024_Gaz_zcta_national.zip, 2024_Gaz_counties_national.zip  -> unzipped into data/raw/"""
import math, os

RAW = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
_zip, _county = {}, {}


def _load():
    if _zip:
        return
    with open(os.path.join(RAW, "2024_Gaz_zcta_national.txt")) as fh:
        next(fh)
        for line in fh:
            p = line.split("\t")
            _zip[p[0].strip()] = (float(p[5]), float(p[6]))
    with open(os.path.join(RAW, "2024_Gaz_counties_national.txt"), encoding="latin-1") as fh:
        next(fh)
        for line in fh:
            p = line.split("\t")
            _county[p[1].strip()] = (float(p[8]), float(p[9]))


def miles(a, b):
    (la1, lo1), (la2, lo2) = [(math.radians(x), math.radians(y)) for x, y in (a, b)]
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 3958.8 * 2 * math.asin(math.sqrt(h))


def point_for_zip(z):
    _load()
    return _zip.get(str(z)[:5])


def point_for_county(state_fips, county_fips):
    _load()
    return _county.get(f"{state_fips}{str(county_fips).zfill(3)}")


def nearest_office(cfg, point):
    """(office name, miles) for a (lat, lon) point, or ("", None)."""
    if not point:
        return "", None
    best = None
    for o in cfg["offices"]:
        p = point_for_zip(o["zip"])
        d = miles(point, p)
        if best is None or d < best[1]:
            best = (o["name"], round(d))
    return best
