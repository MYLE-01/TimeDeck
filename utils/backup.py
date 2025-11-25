import os, json, shutil, datetime
import sys
import os
import shutil
from datetime import datetime
import threading
import logging
from .paths import BASE_DIR, CONFIGS_DIR

"""

from backup import start_live_backup, backup_on_exit

# Start live backup every 5 minutes
start_live_backup()

window = webview.create_window(
    "TimeDeck™",
    "http://127.0.0.1:8000",
    width=750,
    height=1000,
    on_closed=backup_on_exit  # backup automatically on exit
)
webview.start()


"""

MAX_BACKUPS_PER_FILE = 7  # keep only the last 5 backups
LIVE_BACKUP_INTERVAL = 300       # seconds (5 minutes)
def backup_all_json():
    """
    Backup all .json files in CONFIGS_DIR into a timestamped 'backups' dir.
    Keeps only the last MAX_BACKUPS_PER_FILE backups per file.
    """
    folder = CONFIGS_DIR
    backup_dir = os.path.join(folder, "backups")
    os.makedirs(backup_dir, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    for filename in os.listdir(folder):
        if filename.endswith(".json"):
            src = os.path.join(folder, filename)
            dst = os.path.join(backup_dir, f"{filename}.{ts}.bak")
            shutil.copy2(src, dst)

            # cleanup old backups
            all_backups = sorted(
                [f for f in os.listdir(backup_dir) if f.startswith(filename) and f.endswith(".bak")]
            )
            if len(all_backups) > MAX_BACKUPS_PER_FILE:
                for old_file in all_backups[:-MAX_BACKUPS_PER_FILE]:
                    os.remove(os.path.join(backup_dir, old_file))

    logging.info(f"✅ Backup complete. Files saved in {backup_dir}")

def start_live_backup(interval: int = LIVE_BACKUP_INTERVAL):
    """Run backup periodically in a background thread."""
    def run():
        while True:
            try:
                backup_all_json()
            except Exception as e:
                logging.error(f"Live backup failed: {e}")
            threading.Event().wait(interval)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    logging.info(f"Live backup started, interval: {interval} seconds.")

def backup_on_exit():
    """Simple helper to call backup when app closes (for webview on_closed)."""
    try:
        backup_all_json()
    except Exception as e:
        logging.error(f"Backup on exit failed: {e}")