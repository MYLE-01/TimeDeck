# 🧰 Roster & Config Manager — Task Readme

https://127.0.0.1:8000/pacing-trend?emp_id=541895

This project streamlines employee roster editing and configuration logic, tailored for manager-specific views and FastAPI integration.
using tailwindcss as the CSS formating

---

## How to start

.\venv\Scripts\activate
uvicorn main:app --reload --reload

---

## Building the Executable (PyInstaller)

pyinstaller main.py --onefile --clean --hidden-import pywebview ^
--add-data "images;images" --add-data "static;static" ^
--add-data "templates;templates" --icon "images/logo.ico" --name TimeDeck

---

## 🛠️ Config & Access Logic

- [ ] Auto-detect Windows login using `getpass.getuser()` and pre-fill `your_windows_login` in config
- [ ] Filter EMPs by manager login → show only those where `report_to == your_windows_login`
- [ ] Enable edit mode for manager view → auto-unhide fields when logged-in user matches `report_to`
- [ ] if I add a feild to the default want a python script to update all emp\_??????.json file

---

## 📋 Roster Editing Flow

- [ ] JS-powered roster editor that:

  - Reads `roster_{emp}.json`
  - Finds entry by `date` + `shift_type`
  - Updates fieldname (e.g., `type_shift`)
  - Sends change to `/update_roster_field`
  - [ ] FastAPI route: `@app.post("/update_roster_field")` → uses `save_roster(emp, date, shift_type,fieldname, value)`
  - [ ] Need to think about when some does a shift change part way tho a season
  - [ ] Alpine toast: — "✅ Roster updated!" need to get this working
  - [ ] As all number input is a time format
        12.3 <= 100 min clock `decimal_time_hrs_to_mins() `
        12:00 <= real time `hrs_to_mins()`
        2325h <= this would be hours.
        2325 <= would be mins
        have one def `convert_this_to_mins()` which look for a . or : passes to the right def
        need to get smart look at the type imput if number apply the maths to convert as it right back to file

---

## 🧠 Quality-of-Life Upgrades

- [ ] Dropdown or inline editor for `type_shift` → live-save on change
- [ ] Add audit trail to JSON:
  - `"last_updated_by": "Steve"`
  - `"timestamp": "2025-07-24T13:45"`
- [ ] Style config pages based on user role
      Add color-coded headers or manager badges

---

## 🎯 Debug & Cleanup

- [ ] Refactor Alpine toast → timed fade-out logic
- [ ] Patch `create_user_config()` → ensure `"shift_name"` is inherited correctly
- [ ] Sweep config → make sure `"your_windows_login"` is populated across all EMP profiles

---

## 🧩 Component Breakdown

### Backend Logic

- FastAPI: `/update_roster_field`
- Filtering by `report_to`
- Audit trail fields

### Frontend Dynamics

- Roster editor UI
- Inline editor for `type_shift`
- Alpine toast behavior
- Role-based visual cues
- Display a roster down the page or cross the page

### Config Hygiene

- `getpass.getuser()` for auto login
- Initial `shift_name` inheritance
- EMP config sweep

---

### Build more EDIT screen

✅ To-Do When You Return

Shift Dropdown in Modal

Replace the free-text type_shift input with a <select> dropdown.

Populate it with available shift codes (e.g., LSL, Sick, Annual, Training, Cover, etc.).

Ideally load from your shifts.json config so you don’t hardcode them.

Roster Loading Fix

Your modal is trying to fetch /configs/roster\_${empId}.json.

Make sure that file exists and is accessible for every employee, otherwise you’ll see Failed to load config/roster.

If you don’t want per-employee files, adjust it to fetch from a single roster.json and filter by empId.

Calendar Hook-up

Confirm your double-click event is passing empId, date, and shiftType into showTimeOffModal.

Ensure those values match what’s stored in your roster (especially date format YYYY-MM-DD vs localized strings).

Save Button

Hook up #saveTimeOffBtn to write changes back to JSON (or send them to your FastAPI backend).

Right now, the modal updates UI but doesn’t persist.

# ---------------------------------------------------------

Perfect — here’s a PyInstaller-ready startup block for your main.py, fully integrated with paths, backup, live backup, and webview, ready to build into an exe:

import os
import sys
import threading
import logging
from datetime import datetime
import webview
import uvicorn

# --------------------------------------

# 1️⃣ Paths & Configs

# --------------------------------------

if getattr(sys, "frozen", False): # Running from EXE
BASE_DIR = os.path.dirname(sys.executable)
CONFIGS_DIR = os.path.join(BASE_DIR, "configs") # keep configs inside dist/
TEMPLATES_DIR = os.path.join(sys.\_MEIPASS, "templates")
STATIC_DIR = os.path.join(sys.\_MEIPASS, "static")
IMAGES_DIR = os.path.join(sys.\_MEIPASS, "images")
else: # Running as script
BASE_DIR = os.path.dirname(os.path.abspath(**file**))
CONFIGS_DIR = os.path.join(BASE_DIR, "configs")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")
IMAGES_DIR = os.path.join(BASE_DIR, "images")

JOB_TITLES_FILE = os.path.join(CONFIGS_DIR, "jobtitle.json")

# Warn only if folder truly missing

if not os.path.exists(BASE_DIR):
logging.warning(f"BASE_DIR folder not found: {BASE_DIR}")
if not os.path.exists(CONFIGS_DIR):
logging.warning(f"CONFIGS_DIR folder not found: {CONFIGS_DIR}")

# --------------------------------------

# 2️⃣ Backup system

# --------------------------------------

from backup import start_live_backup, backup_on_exit

# Start live backup every 5 minutes

start_live_backup() # optional, keeps JSON files backed up while app runs

# --------------------------------------

# 3️⃣ FastAPI server

# --------------------------------------

def run_server():
logging.debug("Starting TimeDeck server...")
uvicorn.run(app, host="127.0.0.1", port=8000)

# Run server in background thread so UI can start

threading.Thread(target=run_server, daemon=True).start()

# --------------------------------------

# 4️⃣ Webview UI

# --------------------------------------

try:
logging.info("Launching TimeDeck™ window...")
window = webview.create_window(
"TimeDeck™",
"http://127.0.0.1:8000",
width=750,
height=1000 # Removed on_closed for PyInstaller compatibility
)

    webview.start()  # blocking call

    # Backup when user closes the window
    backup_on_exit()

except Exception as e:
logging.error(f"Window launch failed: {e}")
import webbrowser
webbrowser.open("http://127.0.0.1:8000") # fallback

✅ Features

BASE_DIR & CONFIGS_DIR work in both script and exe mode.

Warnings only if folder truly missing, no false alarms.

Live backup thread runs every 5 minutes.

Backup on exit works reliably after webview.start().

PyInstaller compatible — no on_closed keyword (avoids the crash).

If you like, I can also make a fully commented version with arrows and ASCII diagram showing:

Main thread → server thread → UI thread → backup

So it’s crystal clear how everything runs in parallel.

Do you want me to do that?
