"""Email the lead workbook through Resend (HTTPS API; SMTP ports are blocked in the cloud environment).

Environment variables (set as secrets in the cloud environment, never committed):
  RESEND_API_KEY   API key from resend.com (sending access only)
  MAIL_FROM        Optional. Default: "Daubenmire Group Leads <leads@daubenmiregroup.com>"
  MAIL_REPLY_TO    Optional. Where replies go.

Usage:
  python3 mailer.py --to a@x.com --to b@x.com --subject "..." --body-file body.html --attach file.xlsx
"""
import argparse, base64, json, os, sys, urllib.request, urllib.error

DEFAULT_FROM = "Daubenmire Group Leads <leads@daubenmiregroup.com>"


def send(to, subject, html, attachments):
    key = os.environ.get("RESEND_API_KEY") or sys.exit("Missing RESEND_API_KEY environment variable.")
    files = []
    for path in attachments:
        raw = open(path, "rb").read()
        if len(raw) > 30 * 1024 * 1024:
            sys.exit(f"{path} is too large to attach.")
        files.append({"filename": os.path.basename(path), "content": base64.b64encode(raw).decode()})
    msg = {"from": os.environ.get("MAIL_FROM") or DEFAULT_FROM, "to": to, "subject": subject,
           "html": html, "attachments": files}
    if os.environ.get("MAIL_REPLY_TO"):
        msg["reply_to"] = os.environ["MAIL_REPLY_TO"]
    req = urllib.request.Request("https://api.resend.com/emails", data=json.dumps(msg).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                                          "User-Agent": "lead-gen-mailer/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            res = json.load(r)
            print(f"Sent from {msg['from']} to {', '.join(to)}; id {res.get('id')}; attached: "
                  + ", ".join(f["filename"] for f in files))
    except urllib.error.HTTPError as e:
        sys.exit(f"Resend send failed: HTTP {e.code} {e.read().decode()[:500]}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--to", action="append", required=True)
    ap.add_argument("--subject", required=True)
    ap.add_argument("--body-file", required=True)
    ap.add_argument("--attach", action="append", default=[])
    a = ap.parse_args()
    send(a.to, a.subject, open(a.body_file).read(), a.attach)
