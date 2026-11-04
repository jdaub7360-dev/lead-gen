"""HIPAA breaches affecting 500+ people that HHS is currently investigating (last ~24 months), for one state.
Source: https://ocrportal.hhs.gov/ocr/breach/ (public list; the site is JSF, so this walks its two form posts).
Usage: python3 sources/hhs_breach.py configs/<client>.json data/<client>/breaches.json"""
import csv, http.cookiejar, io, json, re, sys, urllib.request, uuid

BASE = "https://ocrportal.hhs.gov/ocr/breach/"


def multipart(fields):
    b = uuid.uuid4().hex
    body = "".join(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n' for k, v in fields.items())
    return (body + f"--{b}--\r\n").encode(), f"multipart/form-data; boundary={b}"


def fetch_csv():
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    op.addheaders = [("User-Agent", "Mozilla/5.0")]

    def post(page, html, link_pattern):
        vs = re.search(r'javax\.faces\.ViewState:0" value="([^"]+)', html).group(1)
        link = re.search(link_pattern, html).group(1)
        data, ctype = multipart({"ocrForm": "ocrForm", link: link, "javax.faces.ViewState": vs})
        req = urllib.request.Request(BASE + page, data=data, headers={"Content-Type": ctype})
        with op.open(req, timeout=120) as r:
            return r.read().decode("utf-8", "ignore")

    with op.open(BASE + "breach_frontpage.jsf", timeout=60) as r:
        front = r.read().decode("utf-8", "ignore")
    report = post("breach_frontpage.jsf", front,
                  r"\{'(ocrForm:j_idt\d+)':'ocrForm:j_idt\d+'\},''\);return false\">View HIPAA Breach Reports")
    return post("breach_report_hip.jsf", report,
                r"\{'(ocrForm:j_idt\d+)':'ocrForm:j_idt\d+'\},''\);return false\"><img id=\"ocrForm:j_idt\d+\" src=\"/ocr/images/icons/csv")


def main(cfg_path, out_path):
    state = json.load(open(cfg_path))["state_abbr"]
    rows = list(csv.reader(io.StringIO(fetch_csv())))
    out = [{"name": r[0].strip(), "entity_type": r[2], "individuals": int(r[3] or 0), "reported": r[4],
            "breach_type": r[5], "location": r[6]}
           for r in rows[1:] if len(r) > 6 and r[1] == state]
    out.sort(key=lambda r: r["reported"][-4:] + r["reported"][:5], reverse=True)
    json.dump(out, open(out_path, "w"), indent=1)
    print(f"{len(out)} {state} breaches -> {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main(*sys.argv[1:3])
