from email.header import decode_header
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv
import imaplib, email, sys, os

load_dotenv()

IMAP_SERVER = os.getenv("IMAP_SERVER")
USERNAME     = os.getenv("IMAP_USER")
PASSWORD     = os.getenv("IMAP_PASS")
EMAIL_FROM   = os.getenv("EMAIL_FROM")
DOWNLOAD_FOLDER = Path(os.getenv("DOWNLOAD_FOLDER", "/home/junghans/services/mein-skript/bilder"))
DOWNLOAD_FOLDER.mkdir(exist_ok=True)

today = datetime.today()
monday = today - timedelta(days=today.weekday())
next_monday = monday + timedelta(days=7)
date_fmt = "%d-%b-%Y"
since_str = monday.strftime(date_fmt)
before_str = next_monday.strftime(date_fmt)

search_criteria = f'(FROM "{EMAIL_FROM}" SINCE "{since_str}" BEFORE "{before_str}")'
print("Search:", search_criteria)

mail = imaplib.IMAP4_SSL(IMAP_SERVER)
mail.login(USERNAME, PASSWORD)
mail.select("INBOX")

status, message_numbers = mail.search(None, search_criteria)
uids = message_numbers[0].split()
print("Gefundene Mails:", message_numbers[0].decode())

if not uids:
    print("Keine Mail in dieser Woche.")
    mail.logout()
    sys.exit(0)

latest_uid = uids[-1]
print("Bearbeite UID:", latest_uid.decode())

status, msg_data = mail.fetch(latest_uid, "(RFC822)")
msg = email.message_from_bytes(msg_data[0][1])
mail.store(latest_uid, "+FLAGS", "\\Seen")

downloaded = 0
for part in msg.walk():
    ctype = part.get_content_type()
    cid = part.get("Content-ID", "")

    if not ctype.startswith("image/"):
        continue

    filename = part.get_filename()
    if filename:
        name, enc = decode_header(filename)[0]
        if isinstance(name, bytes):
            name = name.decode(enc or "utf-8", errors="ignore")
        filename = name
    else:
        ext = ".jpg" if "jpeg" in ctype else ".png"
        clean_cid = cid.strip("<>")
        filename = f"mailbild_{monday.strftime('%Y%m%d')}_{downloaded+1}_{clean_cid}{ext}"

    path = DOWNLOAD_FOLDER / filename
    if path.exists():
        print("⏭️  Bereits vorhanden:", path.name)
        continue

    payload = part.get_payload(decode=True)
    if not payload:
        continue

    with open(path, "wb") as f:
        f.write(payload)
    print("💾  Gespeichert:", path.name)
    downloaded += 1

print(f"✅ {downloaded} Bilder in {DOWNLOAD_FOLDER}")
mail.logout()
