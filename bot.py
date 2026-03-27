import logging
import subprocess
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

load_dotenv()

BOT_TOKEN       = os.getenv("TELEGRAM_TOKEN")
ALLOWED_USER_ID = int(os.getenv("CHAT_ID"))
WORK_DIR        = "/home/junghans/services/mein-skript"
BILDER_DIR      = Path(os.getenv("DOWNLOAD_FOLDER", "/home/junghans/services/mein-skript/bilder"))
ALLOWED_EXTS    = {".jpg", ".jpeg", ".png", ".webp"}

logging.basicConfig(level=logging.INFO)


def is_authorized(update: Update) -> bool:
    return update.effective_user.id == ALLOWED_USER_ID


def get_bilder() -> list[Path]:
    return sorted(reverse=True,
        [p for p in BILDER_DIR.glob("*") if p.is_file() and p.suffix.lower() in ALLOWED_EXTS]
    )


def format_bilderliste(bilder: list[Path]) -> str:
    lines = ["📸 *Heruntergeladene Bilder:*"]
    for i, p in enumerate(bilder, start=1):
        lines.append(f"{i}. {p.name}")
    lines.append("")
    lines.append("✅ /confirm – Upload in dieser Reihenfolge starten")
    lines.append("🔀 /reorder 3 1 2 – Reihenfolge ändern")
    lines.append("❌ /cancel – Abbrechen und Bilder löschen")
    return "\n".join(lines)


# /upload – Download starten, dann Bilderliste anzeigen
async def cmd_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        await update.message.reply_text("❌ Nicht autorisiert.")
        return

    await update.message.reply_text("⏳ Starte Download aus Gmail...")

    result = subprocess.run(
        [sys.executable, "AutoDownloadEKHA.py"],
        capture_output=True, text=True, timeout=120, cwd=WORK_DIR
    )

    if result.returncode != 0:
        await update.message.reply_text(f"❌ Download fehlgeschlagen:\n{result.stderr[-1000:]}")
        return

    await update.message.reply_text(f"✅ Download fertig:\n{result.stdout[-1000:]}")

    bilder = get_bilder()
    if not bilder:
        await update.message.reply_text("⚠️ Keine Bilder im bilder/-Ordner gefunden.")
        return

    context.user_data["bilder"] = bilder
    await update.message.reply_text(format_bilderliste(bilder), parse_mode="Markdown")


# /reorder 3 1 2 – Reihenfolge ändern
async def cmd_reorder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        await update.message.reply_text("❌ Nicht autorisiert.")
        return

    bilder: list[Path] = context.user_data.get("bilder")
    if not bilder:
        await update.message.reply_text("⚠️ Kein aktiver Upload. Starte zuerst mit /upload.")
        return

    args = context.args
    if not args:
        await update.message.reply_text("❌ Nutzung: /reorder 3 1 2")
        return

    try:
        indices = [int(x) for x in args]
    except ValueError:
        await update.message.reply_text("❌ Nur Zahlen angeben, z.B. /reorder 3 1 2")
        return

    if sorted(indices) != list(range(1, len(bilder) + 1)):
        await update.message.reply_text(
            f"❌ Ungültige Reihenfolge. Gib alle {len(bilder)} Nummern an, z.B. /reorder "
            + " ".join(str(i) for i in range(1, len(bilder) + 1))
        )
        return

    neue_reihenfolge = [bilder[i - 1] for i in indices]
    context.user_data["bilder"] = neue_reihenfolge
    await update.message.reply_text(
        "🔀 Neue Reihenfolge gespeichert:\n\n" + format_bilderliste(neue_reihenfolge),
        parse_mode="Markdown"
    )


# /confirm – Upload starten
async def cmd_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        await update.message.reply_text("❌ Nicht autorisiert.")
        return

    bilder: list[Path] = context.user_data.get("bilder")
    if not bilder:
        await update.message.reply_text("⚠️ Kein aktiver Upload. Starte zuerst mit /upload.")
        return

    await update.message.reply_text("⏳ Starte FTP-Upload...")

    # Reihenfolge als Umgebungsvariable übergeben
    reihenfolge = ",".join(p.name for p in bilder)
    env = os.environ.copy()
    env["UPLOAD_ORDER"] = reihenfolge

    result = subprocess.run(
        [sys.executable, "AutoUpload.py"],
        capture_output=True, text=True, timeout=300,
        cwd=WORK_DIR, env=env
    )

    if result.returncode != 0:
        await update.message.reply_text(f"❌ Upload fehlgeschlagen:\n{result.stderr[-1000:]}")
        return

    await update.message.reply_text(f"✅ Upload fertig:\n{result.stdout[-1000:]}")
    context.user_data.pop("bilder", None)


# /cancel – Abbrechen und Bilder löschen
async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        await update.message.reply_text("❌ Nicht autorisiert.")
        return

    bilder: list[Path] = context.user_data.get("bilder")
    if not bilder:
        await update.message.reply_text("⚠️ Kein aktiver Upload vorhanden.")
        return

    deleted = 0
    for p in bilder:
        if p.exists():
            p.unlink()
            deleted += 1

    context.user_data.pop("bilder", None)
    await update.message.reply_text(f"❌ Abgebrochen. {deleted} Bild(er) gelöscht.")


app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("upload",  cmd_upload))
app.add_handler(CommandHandler("reorder", cmd_reorder))
app.add_handler(CommandHandler("confirm", cmd_confirm))
app.add_handler(CommandHandler("cancel",  cmd_cancel))

print("Bot läuft... Sende /upload im Telegram-Chat.")
app.run_polling()
