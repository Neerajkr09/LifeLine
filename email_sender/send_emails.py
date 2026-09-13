"""
send_emails.py -- standalone outreach-email sender.

Reads recipient addresses from input.csv and sends each one the "someone
nearby needs blood" notification with a link to register. Completely
isolated from the rest of the project on purpose: no imports from
osmharvest, email_outreach, outreach_orchestrator, or the backend, and its
own venv -- nothing here can affect any other component, and nothing else
imports this.

This is a manual, run-it-yourself tool, not a bulk blaster -- it sends to
whatever's in input.csv, one at a time, and nothing more. It's meant for
testing the exact message/credentials/deliverability with one address
before ever considering pointing it at a larger list. If that's ever the
plan, worth thinking through first: an unsubscribe/opt-out path, your
provider's sending-rate limits, and your local anti-spam regulations --
none of that is needed for a single test send, all of it matters at scale.

Usage:
    python send_emails.py                  # sends to everyone in input.csv
    python send_emails.py --dry-run        # prints instead of sending -- try this first
    python send_emails.py --input other.csv
"""

from __future__ import annotations

import argparse
import csv
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import List

try:
    # Optional convenience, same pattern as the rest of the project: fill in
    # .env once instead of exporting SMTP_* variables every session. Nothing
    # breaks if python-dotenv isn't installed -- real environment variables
    # still work.
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass


FORM_URL = "https://docs.google.com/forms/d/1_w3-zlWD3JgwSlNagd7ENT_P5-dj3UntHFPF65bOEl8/viewform"

SUBJECT = "Someone in your nearby radius needs blood!"

BODY_TEXT = f"""Greetings,

We are from Team Lifeline. We have taken a step forward towards closing the
gap between blood donors and recipients.

A person within your nearby radius (5 km) currently needs blood. We request
that you kindly register on our platform to learn the details, and if
you're interested, please come forward to contribute to this cause.

Register here: {FORM_URL}

Thank you for considering this,
Team Lifeline
"""

BODY_HTML = f"""\
<html>
  <body style="font-family: Arial, sans-serif; font-size: 14px; color: #222; line-height: 1.5;">
    <p>Greetings,</p>
    <p>
      We are from <strong>Team Lifeline</strong>. We have taken a step forward
      towards closing the gap between blood donors and recipients.
    </p>
    <p>
      A person within your nearby radius (<strong>5&nbsp;km</strong>) currently
      needs blood. We request that you kindly register on our platform to
      learn the details, and if you're interested, please come forward to
      contribute to this cause.
    </p>
    <p>
      <a href="{FORM_URL}"
         style="display:inline-block; padding:10px 18px; background:#c0392b;
                color:#ffffff; text-decoration:none; border-radius:4px;">
        Register here
      </a>
    </p>
    <p>Thank you for considering this,<br>Team Lifeline</p>
  </body>
</html>
"""


def load_recipients(input_csv: Path) -> List[str]:
    if not input_csv.exists():
        raise SystemExit(f"Input CSV not found: {input_csv}")

    with input_csv.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise SystemExit(f"{input_csv} has no header row.")

        # Accept either column name, so a row copied straight out of a real
        # contacts_<id>.csv (which uses "extracted_email") works with no edits.
        column = next((c for c in ("email", "extracted_email") if c in reader.fieldnames), None)
        if column is None:
            raise SystemExit(
                f"{input_csv} needs an 'email' (or 'extracted_email') column. "
                f"Found columns: {reader.fieldnames}"
            )

        return [row[column].strip() for row in reader if row.get(column, "").strip()]


def build_message(to_address: str, from_address: str) -> MIMEMultipart:
    message = MIMEMultipart("alternative")
    message["Subject"] = SUBJECT
    message["From"] = from_address
    message["To"] = to_address
    # Plain-text part first, HTML second -- email clients use the last
    # part they understand, so this order makes HTML-capable clients show
    # the styled version while plain-text clients still get something readable.
    message.attach(MIMEText(BODY_TEXT, "plain"))
    message.attach(MIMEText(BODY_HTML, "html"))
    return message


def send(to_addresses: List[str], dry_run: bool) -> None:
    host = os.environ.get("SMTP_HOST")
    port = int(os.environ.get("SMTP_PORT", "587"))
    username = os.environ.get("SMTP_USERNAME")
    password = os.environ.get("SMTP_PASSWORD")
    from_address = os.environ.get("SMTP_FROM_EMAIL") or username or "lifeline09990@gmail.com"
    use_tls = os.environ.get("SMTP_USE_TLS", "true").lower() != "false"

    if dry_run:
        for to_address in to_addresses:
            message = build_message(to_address, from_address)
            print("=" * 60)
            print(f"DRY RUN -- would send to: {to_address}")
            print(f"Subject: {message['Subject']}")
            print(f"From:    {message['From']}")
            print("-" * 60)
            print(BODY_TEXT)
        print(f"{len(to_addresses)} message(s) NOT sent (--dry-run).")
        return

    if not host or not username or not password:
        raise SystemExit(
            "SMTP_HOST, SMTP_USERNAME, and SMTP_PASSWORD must be set -- copy .env.example "
            "to .env and fill them in, or run with --dry-run to preview without sending."
        )

    sent = 0
    with smtplib.SMTP(host, port) as server:
        if use_tls:
            server.starttls()
        server.login(username, password)
        for to_address in to_addresses:
            message = build_message(to_address, from_address)
            server.sendmail(from_address, [to_address], message.as_string())
            print(f"Sent to {to_address}")
            sent += 1

    print(f"\n{sent} message(s) sent.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Send the blood-donor-outreach notification to addresses in a CSV.")
    parser.add_argument("--input", default="input.csv", help="CSV with an 'email' or 'extracted_email' column (default: input.csv)")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be sent instead of actually sending")
    args = parser.parse_args()

    recipients = load_recipients(Path(args.input))
    if not recipients:
        print("No email addresses found in the input file.")
        return 1

    print(f"Loaded {len(recipients)} recipient(s) from {args.input}\n")
    send(recipients, args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())