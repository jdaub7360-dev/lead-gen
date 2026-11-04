"""Enrich nonprofits from their latest IRS Form 990 e-file: website, phone, employee count, officers.

The IRS publishes e-filed returns as large zip archives. This reads only the needed files out of
each archive with HTTP range requests, so nothing large is downloaded.
Index files: https://apps.irs.gov/pub/epostcard/990/xml/<year>/index_<year>.csv
Usage: python3 sources/irs_990.py configs/<client>.json data/<client>/nonprofits.json data/raw
Writes data/<client>/enrich_990.json (keyed by EIN). Already-enriched EINs are skipped."""
import csv, html, io, json, os, re, sys, urllib.request, zipfile
try:
    import zipfile_deflate64  # noqa: F401  (adds Deflate64, used by some IRS archives; pip install zipfile-deflate64)
except ImportError:
    pass
from collections import defaultdict

BASE = "https://apps.irs.gov/pub/epostcard/990/xml"
YEARS = [2026, 2025, 2024]


class RangeFile(io.RawIOBase):
    """Seekable read-only file over HTTP range requests, with a small block cache."""
    BLOCK = 256 * 1024

    def __init__(self, url):
        self.url, self.pos, self.cache = url, 0, {}
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=60) as r:
            self.size = int(r.headers["Content-Length"])

    def readable(self): return True
    def seekable(self): return True
    def tell(self): return self.pos

    def seek(self, off, whence=0):
        self.pos = off if whence == 0 else self.pos + off if whence == 1 else self.size + off
        return self.pos

    def _block(self, n):
        if n not in self.cache:
            start = n * self.BLOCK
            end = min(start + self.BLOCK, self.size) - 1
            req = urllib.request.Request(self.url, headers={"Range": f"bytes={start}-{end}"})
            for attempt in range(4):
                try:
                    with urllib.request.urlopen(req, timeout=90) as r:
                        self.cache[n] = r.read()
                    break
                except Exception:
                    if attempt == 3:
                        raise
            if len(self.cache) > 64:
                self.cache.pop(next(iter(self.cache)))
        return self.cache[n]

    def read(self, n=-1):
        if n < 0:
            n = self.size - self.pos
        out = bytearray()
        while n > 0 and self.pos < self.size:
            b = self._block(self.pos // self.BLOCK)
            off = self.pos % self.BLOCK
            chunk = b[off:off + n]
            out += chunk
            self.pos += len(chunk)
            n -= len(chunk)
        return bytes(out)

    def readinto(self, b):
        data = self.read(len(b))
        b[:len(data)] = data
        return len(data)


def tag(x, name):
    m = re.search(rf"<{name}>(.*?)</{name}>", x, re.S)
    return html.unescape(m.group(1)).strip() if m else ""


def parse(xml):
    officers = []
    for grp in re.findall(r"<Form990PartVIISectionAGrp>(.*?)</Form990PartVIISectionAGrp>", xml, re.S):
        name = tag(grp, "PersonNm") or tag(grp, "BusinessNameLine1Txt")
        title = tag(grp, "TitleTxt")
        comp = tag(grp, "ReportableCompFromOrgAmt")
        is_officer = "<OfficerInd>" in grp or "<KeyEmployeeInd>" in grp
        departed = re.search(r"\b(thru|through|until|former|resigned|eff\.?|ended)\b", f"{name} {title}", re.I)
        if name and not departed:
            officers.append({"name": name.title(), "title": title.title(), "comp": int(comp or 0), "officer": is_officer})
    # Staff leaders first (officers/key employees who are paid), then the board chair
    officers.sort(key=lambda o: (not o["officer"], -o["comp"]))
    web = tag(xml, "WebsiteAddressTxt")
    if web and web.upper() not in ("N/A", "NONE", "NA"):
        web = re.sub(r"^https?://", "", web.lower()).strip("/")
    else:
        web = ""
    phone = tag(tag(xml, "Filer"), "PhoneNum")
    return {
        "website": web,
        "phone": f"({phone[:3]}) {phone[3:6]}-{phone[6:]}" if len(phone) == 10 else phone,
        "employees": int(tag(xml, "TotalEmployeeCnt") or 0),
        "principal_officer": tag(xml, "PrincipalOfficerNm").title(),
        "officers": officers[:5],
        "tax_period_end": tag(xml, "TaxPeriodEndDt"),
    }


def ranked_filings(eins, raw_dir):
    """All e-filed 990/990-EZ returns per EIN, newest first."""
    found = defaultdict(list)
    for y in YEARS:
        path = f"{raw_dir}/index_{y}.csv"
        if not os.path.exists(path):
            urllib.request.urlretrieve(f"{BASE}/{y}/index_{y}.csv", path)
        for r in csv.DictReader(open(path, encoding="latin-1")):
            e = r["EIN"].zfill(9)
            if e in eins and r["RETURN_TYPE"] in ("990", "990EZ"):
                found[e].append({**r, "year": y})
    for e in found:
        found[e].sort(key=lambda r: (r["TAX_PERIOD"], r["year"]), reverse=True)
    return found


def main(cfg_path, np_path, raw_dir):
    cfg = json.load(open(cfg_path))
    out_path = os.path.join(os.path.dirname(np_path), "enrich_990.json")
    done = json.load(open(out_path)) if os.path.exists(out_path) else {}
    lo, hi = cfg["nonprofit"]["sweet_spot"]
    targets = {r["ein"].zfill(9) for r in json.load(open(np_path)) if lo <= r["revenue"] <= hi}
    targets = {e for e in targets if e not in done or "error" in done[e]}
    print(f"{len(targets)} nonprofits to enrich", file=sys.stderr, flush=True)
    ranked = ranked_filings(targets, raw_dir)
    archives = {}

    def archive(year, batch):
        key = (year, batch)
        if key not in archives:
            archives[key] = None
            for name in dict.fromkeys([batch, batch.upper()]):  # index uses lowercase for some 2024 batches
                try:
                    zf = zipfile.ZipFile(RangeFile(f"{BASE}/{year}/{name}.zip"))
                    archives[key] = (zf, {os.path.basename(n).split("_")[0]: n for n in zf.namelist()})
                    break
                except Exception as ex:
                    err = ex
            if archives[key] is None:
                print(f"  {batch}: unavailable ({err})", file=sys.stderr, flush=True)
        return archives[key]

    # Group by the newest filing's archive to keep reads local; fall back to older filings on failure
    order = sorted(ranked.items(), key=lambda kv: (kv[1][0]["year"], kv[1][0]["XML_BATCH_ID"]))
    for i, (e, filings) in enumerate(order, 1):
        result = {"error": "no readable filing"}
        for f in filings[:3]:
            a = archive(f["year"], f["XML_BATCH_ID"])
            if not a or f["OBJECT_ID"] not in a[1]:
                continue
            try:
                result = parse(a[0].read(a[1][f["OBJECT_ID"]]).decode("utf-8", "ignore"))
                break
            except Exception as ex:
                result = {"error": str(ex)[:100]}
        done[e] = result
        if i % 25 == 0:
            json.dump(done, open(out_path, "w"), indent=1)
            print(f"  {i}/{len(order)}", file=sys.stderr, flush=True)
    json.dump(done, open(out_path, "w"), indent=1)
    print(f"{len(done)} nonprofits enriched -> {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main(*sys.argv[1:4])
