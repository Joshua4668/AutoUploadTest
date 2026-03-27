from ftplib import FTP_TLS
from pathlib import Path
from dotenv import load_dotenv
import time, os

load_dotenv()

FTP_HOST     = os.getenv("FTP_HOST")
FTP_USER     = os.getenv("FTP_USER")
FTP_PASS     = os.getenv("FTP_PASS")
LOCAL_FOLDER = Path(os.getenv("DOWNLOAD_FOLDER", "/home/junghans/services/mein-skript/bilder"))
ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def upload_files():
    # Reihenfolge aus Umgebungsvariable (gesetzt von bot.py)
    upload_order = os.getenv("UPLOAD_ORDER")

    if upload_order:
        files = []
        for name in upload_order.split(","):
            p = LOCAL_FOLDER / name.strip()
            if p.exists():
                files.append(p)
            else:
                print(f"⚠️  Datei nicht gefunden: {name}")
    else:
        files = sorted(
            [p for p in LOCAL_FOLDER.glob("*") if p.is_file() and p.suffix.lower() in ALLOWED_EXTS]
        )

    if not files:
        print("Keine Bilder zum Hochladen gefunden.")
        return

    print("Upload-Reihenfolge:")
    for i, p in enumerate(files, start=1):
        print(f"{i:2d}: {p.name}")

    ftps = FTP_TLS(FTP_HOST)
    ftps.login(FTP_USER, FTP_PASS)
    ftps.prot_p()

    for path in files:
        with open(path, "rb") as f:
            ftps.storbinary(f"STOR {path.name}", f)
        print(f"✅ Hochgeladen: {path.name}")
        path.unlink()
        time.sleep(1)

    ftps.quit()
    print("Fertig.")


if __name__ == "__main__":
    upload_files()
