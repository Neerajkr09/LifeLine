
cd email_sender
python -m venv .venv
.venv\Scripts\activate.bat
pip install -r requirements.txt
python -m pip install -r requirements.txt



Test codes---
python send_emails.py --dry-run
python send_emails.py


for email sometimes dotenv issue-
pip show python-dotenv

pip install python-dotenv
