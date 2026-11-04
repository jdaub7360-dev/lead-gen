"""Email the lead workbook through Microsoft Graph (app-only auth, HTTPS).

Environment variables (set as secrets in the cloud environment, never committed):
  M365_TENANT_ID      Azure AD tenant ID
  M365_CLIENT_ID      App registration (client) ID
  M365_CLIENT_SECRET  App registration client secret
  M365_SENDER         Mailbox the email is sent from, e.g. leads@infinit.us

Usage:
  python3 mailer.py --to a@x.com --to b@x.com --subject "..." --body-file body.html --attach file.xlsx
"""
import argparse, base64, json, os, sys, urllib.parse, urllib.request

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def token():
    t, c, s = (os.environ.get(k) for k in ("M365_TENANT_ID", "M365_CLIENT_ID", "M365_CLIENT_SECRET"))
    if not all((t, c, s)):
        sys.exit("Missing M365_TENANT_ID / M365_CLIENT_ID / M365_CLIENT_SECRET environment variables.")
    data = urllib.parse.urlencode({"client_id": c, "client_secret": s, "grant_type": "client_credentials",
                                   "scope": "https://graph.microsoft.com/.default"}).encode()
    with urllib.request.urlopen(f"https://login.microsoftonline.com/{t}/oauth2/v2.0/token", data, timeout=30) as r:
        return json.load(r)["access_token"]


def send(to, subject, html, attachments):
    sender = os.environ.get("M365_SENDER") or sys.exit("Missing M365_SENDER environment variable.")
    files = []
    for path in attachments:
        raw = open(path, "rb").read()
        if len(raw) > 3 * 1024 * 1024:
            sys.exit(f"{path} is over 3 MB; Graph needs an upload session for that size.")
        files.append({"@odata.type": "#microsoft.graph.fileAttachment", "name": os.path.basename(path),
                      "contentType": XLSX if path.endswith(".xlsx") else "application/octet-stream",
                      "contentBytes": base64.b64encode(raw).decode()})
    msg = {"message": {"subject": subject, "body": {"contentType": "HTML", "content": html},
                       "toRecipients": [{"emailAddress": {"address": a}} for a in to],
                       "attachments": files},
           "saveToSentItems": True}
    req = urllib.request.Request(f"https://graph.microsoft.com/v1.0/users/{urllib.parse.quote(sender)}/sendMail",
                                 data=json.dumps(msg).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {token()}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            print(f"Sent from {sender} to {', '.join(to)} (HTTP {r.status}); attached: "
                  + ", ".join(f["name"] for f in files))
    except urllib.error.HTTPError as e:
        sys.exit(f"Graph sendMail failed: HTTP {e.code} {e.read().decode()[:500]}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--to", action="append", required=True)
    ap.add_argument("--subject", required=True)
    ap.add_argument("--body-file", required=True)
    ap.add_argument("--attach", action="append", default=[])
    a = ap.parse_args()
    send(a.to, a.subject, open(a.body_file).read(), a.attach)
