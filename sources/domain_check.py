"""Passive email-security and IT signals for a domain, from public DNS (Google DNS-over-HTTPS)
and one HTTPS request to the homepage. Nothing is scanned or probed beyond what any mail server
or browser does.

Signals: email provider, security gateway, SPF, DMARC policy, website reachable over HTTPS.
Usage: python3 sources/domain_check.py data/<client>/domains.json   (list of domains)
       -> data/<client>/domain_checks.json (cached; rerun refreshes entries older than 30 days)"""
import datetime, json, os, sys, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor

PROVIDERS = [  # (substring in MX host, provider label, has security gateway)
    ("mail.protection.outlook.com", "Microsoft 365", False),
    ("google.com", "Google Workspace", False), ("googlemail.com", "Google Workspace", False),
    ("pphosted.com", "Proofpoint gateway", True), ("ppe-hosted.com", "Proofpoint Essentials gateway", True),
    ("mimecast", "Mimecast gateway", True), ("barracudanetworks", "Barracuda gateway", True),
    ("iphmx.com", "Cisco Secure Email gateway", True), ("sophos", "Sophos gateway", True),
    ("messagelabs", "Broadcom/Symantec gateway", True), ("trendmicro", "Trend Micro gateway", True),
    ("secureserver.net", "GoDaddy email", False), ("emailsrvr.com", "Rackspace email", False),
    ("zoho", "Zoho Mail", False), ("yahoodns", "Yahoo Small Business", False),
]


def dns(name, rtype):
    url = "https://dns.google/resolve?" + urllib.parse.urlencode({"name": name, "type": rtype})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=20) as r:
                return [a["data"] for a in json.load(r).get("Answer", []) if a.get("type") in (15, 16, 5)]
        except Exception:
            time.sleep(2)
    return None


def fetch_ok(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            return r.status < 400, r.geturl()
    except Exception:
        return False, ""


def web_status(domain):
    """'https', 'http-only' (plain HTTP loads, HTTPS fails), or 'unreachable' (don't report: could be our network)."""
    for host in (domain, "www." + domain):
        ok, _ = fetch_ok(f"https://{host}")
        if ok:
            return "https"
    for host in (domain, "www." + domain):
        ok, final = fetch_ok(f"http://{host}")
        if ok:
            return "https" if final.startswith("https://") else "http-only"
    return "unreachable"


def check(domain):
    mx = dns(domain, "MX") or []
    txt = dns(domain, "TXT") or []
    dmarc_txt = [t.strip('"') for t in (dns("_dmarc." + domain, "TXT") or []) if "v=DMARC1" in t]
    hosts = " ".join(mx).lower()
    provider, gateway = ("Self-hosted / other" if mx else "No MX record"), False
    for sub, label, gw in PROVIDERS:
        if sub in hosts:
            provider, gateway = label, gw
            break
    spf = next((t.strip('"') for t in txt if "v=spf1" in t), "")
    policy = ""
    if dmarc_txt:
        for part in dmarc_txt[0].split(";"):
            if part.strip().startswith("p="):
                policy = part.strip()[2:]
    web = web_status(domain)

    return {"domain": domain, "checked": datetime.date.today().isoformat(), "mx_provider": provider,
            "security_gateway": gateway, "spf": bool(spf), "spf_all": spf.rstrip()[-4:] if spf else "",
            "dmarc": policy or ("missing" if not dmarc_txt else "set"), "website": web,
            **findings_for(provider, bool(spf), spf.rstrip()[-4:] if spf else "", policy or ("missing" if not dmarc_txt else "set"), web)}


def findings_for(provider, spf, spf_all, dmarc, web):
    """Only report email findings when the domain actually receives email (has MX records);
    a website host is often not the organization's email domain."""
    findings = []
    if provider != "No MX record":
        if dmarc == "missing":
            findings.append("No DMARC record: anyone can send email that appears to come from this domain")
        elif dmarc.strip() == "none":
            findings.append("DMARC set to monitor only (p=none): spoofed email still gets delivered")
        if not spf:
            findings.append("No SPF record")
        elif spf_all == "+all":
            findings.append("SPF allows any server to send (+all)")
        if provider in ("GoDaddy email", "Yahoo Small Business"):
            findings.append(f"Email on {provider}: likely no one managing email security")
    if web == "http-only":
        findings.append("Website appears to load only over plain HTTP, not HTTPS (verify in a browser before mentioning)")
    return {"findings": findings, "hook": findings[0] if findings else ""}


def main(domains_path):
    out_path = os.path.join(os.path.dirname(domains_path), "domain_checks.json")
    done = json.load(open(out_path)) if os.path.exists(out_path) else {}
    cutoff = (datetime.date.today() - datetime.timedelta(days=30)).isoformat()
    todo = [d for d in json.load(open(domains_path)) if d and (d not in done or done[d]["checked"] < cutoff)]
    print(f"{len(todo)} domains to check", file=sys.stderr, flush=True)
    with ThreadPoolExecutor(24) as ex:
        for i, res in enumerate(ex.map(check, todo), 1):
            done[res["domain"]] = res
            if i % 50 == 0:
                json.dump(done, open(out_path, "w"), indent=1)
                print(f"  {i}/{len(todo)}", file=sys.stderr, flush=True)
    json.dump(done, open(out_path, "w"), indent=1)
    print(f"{len(done)} domains in {out_path}", file=sys.stderr)


def refresh_findings(path):
    data = json.load(open(path))
    for v in data.values():
        v.update(findings_for(v["mx_provider"], v["spf"], v.get("spf_all", ""), v["dmarc"], v["website"]))
    json.dump(data, open(path, "w"), indent=1)


if __name__ == "__main__":
    if sys.argv[1] == "--refresh-findings":
        refresh_findings(sys.argv[2])
    else:
        main(sys.argv[1])
