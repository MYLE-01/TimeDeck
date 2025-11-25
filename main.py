from urllib import request
from urllib.parse import quote
from fastapi import FastAPI, Request, HTTPException, Query, APIRouter , Form
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse, FileResponse, JSONResponse 
from fastapi.staticfiles import StaticFiles 
from fastapi.templating import Jinja2Templates 
import logging, json, os, re, calendar 
from datetime import datetime, timedelta, date 
from pathlib import Path 
from uuid import uuid4 
from holidays.countries import NewZealand
import os 
from os import listdir
from fastapi import status
from fastapi.routing import APIRoute
import ast
import sys, getpass
import threading , uvicorn , webview
from collections import defaultdict
from collections import Counter
from typing import Optional, Dict, Any, Tuple

# Custom modules
from models.employee import can_edit , get_code_sets , _to_minutes , _parse_date , load_all_employees, get_active_managers, build_reporting_tree , build_cover_report
from models.roster import load_roster, generate_roster, build_roster, load_all_rosters, load_roster_for_employee
from models.entitlements import build_shift_summary, calculate_entitlements, summarize_entitlements_by_department
from models.reporting import build_html_tree, build_tree_recursive, build_department_tree
from models.getseasontotal import getSeasonTotals
from utils.io import load_shifts , load_json, save_roster, save_json, load_roster_this_season , create_user_config
from utils.math import min_to_hrs, convert_this_to_mins, flip_date, convert_expression_to_mins, is_it_pay_day ,get_shift_summary_for_date
from utils.auth import get_windows_login, who_is_login, can_user_add_employee,find_employee_by_login,load_reporting_managers
from utils.backup import backup_all_json
from utils.timeline import Timeline,QR_code_alarm,trace_surplus_window
from utils.paths import BASE_DIR,CONFIG_DIRS , CONFIGS_DIR, CONFIG_DIR, JOB_TITLES_FILE, QR_DIR, TEMPLATES_DIR, STATIC_DIR, IMAGES_DIR
import shutil


app = FastAPI()


LOCAL_CONFIGS = os.path.join(CONFIGS_DIR)



LOG_FILE = os.path.join(BASE_DIR, "TimeDeck.log")


#logging.basicConfig(
#    filename=LOG_FILE,
#    encoding="utf-8",
#    filemode="w",
#    format="{asctime} - {levelname} - {message}",
#    style="{",
#    datefmt="%Y-%m-%d %H:%M",
#)

#uvicorn_error_logger = logging.getLogger("uvicorn.error")
#uvicorn_error_logger.handlers = logging.getLogger().handlers
#uvicorn_error_logger.propagate = True
#uvicorn_error_logger.setLevel(logging.ERROR)  # only errors+



# Logging for visibility

#logging.warning(f"BASE_DIR folder: {BASE_DIR}")

#logging.warning(f"CONFIGS_DIR folder: {CONFIG_DIRS}")

logging.warning(f"|-----------------------------|")
logging.warning(f"|           PLEASE            |")
logging.warning(f"| DO NOT CLOSE THIS WINDOW !  |")
logging.warning(f"|                             |")
logging.warning(f"|-----------------------------|")

# Mount folders
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
else:
    print(f"⚠️ Warning: static folder not found: {STATIC_DIR}")

if os.path.exists(IMAGES_DIR):
    app.mount("/images", StaticFiles(directory=IMAGES_DIR), name="images")
else:
    print(f"⚠️ Warning: images folder not found: {IMAGES_DIR}")

if os.path.exists(CONFIGS_DIR):
    app.mount("/configs", StaticFiles(directory=CONFIGS_DIR), name="configs")
else:
    print(f"⚠️ Warning: configs folder not found: {CONFIGS_DIR}")
# Optional: if you want to serve configs via HTTP (read-only)
#app.mount("/configs", StaticFiles(directory=CONFIGS_DIR), name="configs")

# Templates

def safe_display_date(date_str, fmt="%d %b %Y"):
    """Try to parse a date string and return it in the desired format.
    If parsing fails, return the original string.
    """
    try:
        dt = parse(date_str)
        return dt.strftime(fmt)
    except Exception:
        return date_str


templates = Jinja2Templates(directory=TEMPLATES_DIR)
templates.env.filters["url_encode"] = lambda value: quote(value)
templates.env.globals["safe_display_date"] = safe_display_date

def todatetime(value, fmt="%Y-%m-%d"):
    try:
        return datetime.strptime(value, fmt)
    except Exception:
        return None

templates.env.filters["todatetime"] = todatetime


# Load main config JSON
#config_file = os.path.join(CONFIGS_DIR, "default.json")
#if os.path.exists(config_file):
#    
#    with open(config_file, "r") as f:
#        config_data = json.load(f)
#else:
#    config_data = {}
#    print("No config file found, using defaults")
config_data = load_json("default.json")
#def get_current_user(request: Request):
#    # Suppose we store the username in a cookie called "user"
#    username = request.cookies.get("user")
#    if not username or username not in fake_users_db:
#        raise HTTPException(status_code=401, detail="Not logged in")
#    return fake_users_db[username]



@app.get("/jobtitles")
async def jobtitles_page(request: Request):
    """
    Load and display the job titles management page.
    Loads jobtitles and reporting managers from jobtitle.json.
     - **q**: Optional query string to search for items
    """
    data = load_json("jobtitle.json")
    titles = {k: v for k, v in data.get("titles", {}).items() if not k.startswith("_")}
    departments = data.get("departments", {})
    reporting_managers = load_reporting_managers()
    login = get_windows_login()
    emp_list = load_all_employees()
    ok, me = who_is_login()
    #print(f"reporting_manager ",reporting_managers)
    return templates.TemplateResponse("pages/jobtitles.html", {
        "request": request,
        "ok":ok,
        "me":me,
        "titles": titles,
        "now": datetime.now(),
        "departments": departments,
        "reporting_managers": reporting_managers
    })


@app.post("/jobtitles/save")

async def save_jobtitles(
    request: Request,
    key: list[str] = Form(...),        # existing keys
    titles: list[str] = Form(...),     # existing & new titles
    managers: list[str] = Form([]),    # checked reporting manager keys
    departments: list[str] = Form([])  # existing & new departments
):
    """
Save job titles, reporting managers, and departments from the form submission.
- **key**: Optional query string to search for items
- **titles**: List of job titles from the form
- **managers**: List of reporting manager keys from the form
- **departments**: List of departments from the form

"""
    # Load current JSON
    if os.path.exists(JOB_TITLES_FILE):
        with open(JOB_TITLES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {"titles": {}, "departments": {}, "reporting_managers": ""}

    # Clean up titles: merge keys & titles, skip blanks
    new_titles = {}
    for k, t in zip(key, titles[:len(key)]):
        if t.strip():
            new_titles[k.strip()] = t.strip()

    # Add any new title from extra row(s)
    extra_titles = titles[len(key):]
    for t in extra_titles:
        if t.strip():
            new_key = t.strip().replace(" ", "_")
            new_titles[new_key] = t.strip()

    data["titles"] = new_titles

    # Clean up departments: skip blanks
    clean_departments = [d.strip() for d in departments if d.strip()]
    data["departments"] = {d: d for d in clean_departments}

    # Update reporting managers
    data["reporting_managers"] = ", ".join(managers)

    # Save back
    with open(JOB_TITLES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    return RedirectResponse(url="/jobtitles", status_code=303)


@app.post("/jobtitles/update", response_class=RedirectResponse)
async def jobtitles_update(
    titles: list[str] = Form(...),
    report_flags: list[str] = Form(None),
    departments: str = Form("")
):
    """
    Update job titles, reporting managers, and departments from the form submission.
    - **titles**: List of job titles from the form
    - **report_flags**: List of reporting manager keys from the form
    - **departments**: String of departments from the form (newline-separated)
    """
    # Build titles dict
    titles_dict = {v.strip(): v.strip() for v in titles if v.strip()}

    # Reporting managers = all titles with checkbox ticked
    reporting_mgrs = " ".join(report_flags or [])

    # Build departments dict
    departments_dict = {v.strip(): v.strip() for v in departments.splitlines() if v.strip()}

    data = {
        "reporting_managers": reporting_mgrs,
        "titles": titles_dict,
        "departments": departments_dict
    }
    save_jobtitles(data)
    return RedirectResponse(url="/jobtitles", status_code=303)




@app.get("/list-configs")
async def list_configs():
    """
    List all JSON config files in the configs directory.
    """ 
    return os.listdir(CONFIGS_DIR)


@app.get("/paths")
async def get_paths():
    """
    Get all JSON config file paths in the configs directory.
    """
    return {"paths": [str(p) for p in Path(CONFIGS_DIR).glob("**/*.json")]}


def load_job_titles(strip_notes: bool = False):
    """
    Load job titles from configs/jobtitle.json.
    Supports both:
      - New structure: {"titles": {...}, "reporting_managers": "..." }
      - Legacy flat structure: {"L8": {}, "L7": {}, ... }
    Falls back to default.json['titles'] if jobtitle.json is missing.
    """
    titles = {}
    departments = {}
    
    # Check if the job titles file exists
    if os.path.exists(JOB_TITLES_FILE):
        try:
            with open(JOB_TITLES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            titles = data.get("titles", data)  # handle both new and legacy formats
            departments = data.get("departments", {})  # Add departments from the file (if available)
        except json.JSONDecodeError:
            print(f"Error decoding JSON from {JOB_TITLES_FILE}")
            return {}, {}
    else:
        # Fallback to default.json
        default_path = os.path.join(CONFIGS_DIR, "default.json")
        if os.path.exists(default_path):
            try:
                with open(default_path, "r", encoding="utf-8") as f:
                    default = json.load(f)
                titles = default.get("titles", {})
                departments = default.get("departments", {})
            except json.JSONDecodeError:
                print(f"Error decoding JSON from {default_path}")
                return {}, {}

    # If strip_notes is True, filter out '_notes' from titles and departments
    if strip_notes:
        if isinstance(titles, dict):
            titles = {k: v for k, v in titles.items() if k != "_notes"}
        if isinstance(departments, dict):
            departments = {k: v for k, v in departments.items() if k != "_notes"}

    return titles, departments


def ensure_job_titles_file():
    """
    Create configs/jobtitle.json if it doesn't exist yet, using titles and reporting_managers
    from default.json when available. Writes in the new structured format.
    """
    if not os.path.exists(JOB_TITLES_FILE):
        # Gather from defaults if possible
        titles, departments = load_job_titles(strip_notes=False)
        reporting = load_reporting_managers(default_value="L7 L8 Manager")
        # Ensure we write with the new structure
        if "titles" in titles:
            # If caller already returned a structured dict by mistake, unwrap
            titles = titles["titles"]
        obj = {
            "_notes": "Global job title settings moved from default.json",
            "reporting_managers": reporting or "L7 L8 Manager",
            "titles": titles or {"_notes": "Ordered job titles; key order defines sort priority (seniority)."}
        }
        os.makedirs(CONFIGS_DIR, exist_ok=True)
        with open(JOB_TITLES_FILE, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2)
        logging.info("Created jobtitle.json from defaults.")


# 📅 Generate full-season roster



def load_default_config(path=CONFIGS_DIR + "\default.json"):
    """
    Load the default configuration from the specified JSON file.
    """
    print(f"Loading default config from {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def prepare_entitlement_summary(startdate, roster, carryover, days=14):
    # 🗓️ Parse the startdate (string or datetime)
    if isinstance(startdate, str):
        start = datetime.strptime(startdate, "%Y-%m-%d")
    else:
        start = startdate

    date_keys = [(start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]

    # 🧼 Clean carryover
    entitlements = {k: v for k, v in carryover.items() if not k.startswith("_")}

    # 🧱 Build grid
    grid = {code: {d: "" for d in date_keys} for code in entitlements}

    # 🔁 Fill rows
    for entry in roster:
        date = entry.get("date")
        code = entry.get("type_shift")
        is_night = entry.get("shift_type") == "Night"

        if date in date_keys and code in grid:
            hours = min_to_hrs(entry["mins"])
            if is_night:
                grid[code][date] = f"{hours} (N)"
            else:
                grid[code][date] = hours


    # 🔢 Totals + Washup
    for code in grid:
        for d in date_keys:
            grid[code].setdefault(d, "—")  # mark as not rostered

        used_mins = sum(
            int(entry["mins"]) for entry in roster
            if entry.get("type_shift") == code and entry.get("date") in date_keys
        )

        ent_mins = entitlements.get(code, 0)
        washup_mins = ent_mins - used_mins

        grid[code]["entitlement"] = min_to_hrs(ent_mins)
        grid[code]["used"] = min_to_hrs(used_mins)
        grid[code]["washup"] = min_to_hrs(washup_mins)
        grid[code]["total"] = min_to_hrs(used_mins)
        grid[code]["blanks"] = sum(1 for d in date_keys if grid[code][d] == "—")

    # 🧭 Add meta info once, outside the loop
    grid["_meta"] = {
        "start": start.strftime("%Y-%m-%d"),
        "end": date_keys[-1],
        "generated": datetime.now().isoformat()
    }
    return grid

@app.get("/summary")
def get_summary():  
    """
    Retrieve a summary of roster data grouped by employee.
    """
    # Load your roster or summary data
    with open("roster.json") as f:
        roster_data = json.load(f)

    grouped = {}
    for entry in roster_data:
        emp = entry["name"]
        mins = entry.get("mins", 0)
        grouped.setdefault(emp, {"total_mins": 0, "entries": []})
        grouped[emp]["entries"].append(entry)
        grouped[emp]["total_mins"] += mins

    return JSONResponse(content=grouped)




@app.get("/carryover")
def carryover_summary(request: Request):
    """
    Generate a summary of carryover entitlements filtered by the logged-in user's role and department.
    """
    from datetime import datetime

    #login = get_windows_login()
    #emp_list = load_all_employees()
    ok, me = who_is_login()
    summary = build_shift_summary()
    #print(f"summary == ",summary)
    reporting_managers = load_reporting_managers()
    emp_list = load_all_employees()
    #print(f"emp_list == ",emp_list)
    report_map = {}
    for emp_id, emp_data in emp_list.items():
        manager_id = emp_data.get("report_to")
        if manager_id and manager_id != "0":
            report_map.setdefault(manager_id, set()).add(emp_id)

    #dont know how has login
    #If not logged in, goto help page
    if not me:
        return templates.TemplateResponse("pages/help.html", {
            "request": request,
            "error": "User not logged in",
            "ok":ok,
            "me":me,
            "now": datetime.now()

        })

    if me["job_title"] in reporting_managers:
        me_department = me["department"]
        summary = {
            k: v for k, v in summary.items()
            if v.get("employee", {}).get("department") == me_department
        }
        Filter_by = f"{me_department}"
    else:
        me_department = me.get("department")
        me_shift = me.get("shift")
        summary = {
            k: v for k, v in summary.items()
            if v.get("employee", {}).get("shift") == me_shift
            and v.get("employee", {}).get("department") == me_department
        }
        Filter_by = f"{me_shift}, In: {me_department}"

    config_all = load_json("default.json")
    code_descriptions = config_all["notes"]
    # print(f"summary == ",summary)
    return templates.TemplateResponse(
        "pages/carryover.html",{
        "request": request, 
        "code_descriptions": code_descriptions,
        "ok":ok,
        "me":me,
        "summary": summary, 
        "Filter_by": Filter_by,
        "report_map": report_map,
        "reporting_managers":reporting_managers,
        "now": datetime.now()}
    )

@app.get("/config_person")
@app.get("/config_person/{emp_id}")
def config_person(request: Request, emp_id: str = "0"):
    """
    Render the configuration page for a specific person or the default configuration.
    - **emp_id**: Employee ID to load configuration for; "0" or missing loads default.
    """
    # Resolve filename for loading
    if emp_id == "0" or not emp_id.strip():
        filename = "default.json"
    else:
        filename = f"emp_{emp_id}.json"
        full_path = os.path.join("configs", filename)
        if not os.path.exists(full_path):
            filename = "default.json"

    is_new = emp_id == "0" or filename == "default.json"

    config = load_json(filename)  # filename only — load_json handles the path

    if 'schedule' not in config or not config['schedule']:
        config['schedule'] = {
            "Day": "05:00",
            "Night": "17:00"
        }



    job_titles, departments = load_job_titles(strip_notes=True)

    shift_config = load_json("shifts.json")
    shift_names = [s["name"] for s in shift_config.get("Shifts", [])]
    emp_list = load_all_employees()
    login = get_windows_login()

    ok, me = who_is_login()

    reportingManager = load_reporting_managers()
    manager_list = get_active_managers(emp_list, reportingManager)

    return templates.TemplateResponse("pages/config_person.html", {
        "request": request,
        "ok":ok,
        "me":me,
        "shift_names": shift_names,
        "titles": job_titles,
        "manager_list": manager_list,
        "departments": departments,
        "config": config,
        "emp_id": emp_id,
        "now": datetime.now(),
        "login": login,
        "is_new": is_new
    })

import shutil
@app.post("/config_person/delete")
async def delete_config(request: Request):
    """
    Delete configuration files for a specific employee and back them up.
    """
    form = await request.form()
    emp_id = form.get("emp_id", "").strip()
    folder = CONFIGS_DIR
    backup_dir = os.path.join(folder, "backups")
    os.makedirs(backup_dir, exist_ok=True)

    # Validate emp_id
    if not emp_id:
        print("Delete failed: no emp_id provided")
        return RedirectResponse(url="/?error=missing_id", status_code=303)

    deleted_files = []
    for prefix in ["emp_", "roster_"]:
        path = os.path.join(CONFIGS_DIR, f"{prefix}{emp_id}.json")
        src = path
        dst = os.path.join(backup_dir, f"{prefix}{emp_id}.json.{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak")
        
        if os.path.exists(path):
            shutil.copy2(src, dst)
            os.remove(path)
            deleted_files.append(path)
            print(f"Deleted: {path}")
        else:
            print(f"File not found: {path}")

    # Optional: log to a file
    if deleted_files:
        with open(os.path.join(CONFIGS_DIR, "deleted.log"), "a") as log:
            log.write(f"{datetime.now().isoformat()} Deleted {emp_id}: {deleted_files}\n")

    return RedirectResponse(url="/?deleted=1", status_code=303)



@app.post("/config_person/save")
async def save_config(request: Request):
    """
    Save configuration for a specific person.
    - **is_new**: Flag indicating if this is a new employee
    - **emp_id**: Employee ID to save configuration for

    """
    form = await request.form()
    is_new = form.get("is_new") == "1"
    emp_id = form.get("emp_id", "").strip()

    if not emp_id or emp_id == "0" or emp_id.lower().startswith("temp"):
        raw_name = form.get("emp_name", "").strip()
        safe_name = re.sub(r'\W+', '', raw_name).title()
        if not safe_name:
            safe_name = f"Temp{datetime.now().strftime('%H%M%S')}"
        emp_id = f"temp_{safe_name}"

    filename = f"emp_{emp_id}.json"
    path = os.path.join(CONFIGS_DIR, filename)

    print(f"Saving config for EMP {emp_id} to {path}, is_new={is_new}")

    # 🔹 Load default.json as base
    default_path = os.path.join(CONFIGS_DIR, "default.json")
    with open(default_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    # 🔹 Load existing config if not new employee
    existing_config = None
    if not is_new and os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            existing_config = json.load(f)

    # 🔹 Update fields from form
    config.update({
        "emp_name": form.get("emp_name", ""),
        "your_windows_login": form.get("your_windows_login", ""),
        "departments": form.get("departments", ""),
        "working_dept": form.getlist("working_dept"),
        "contact_number": form.get("contact_number", ""),
        "job_title": form.get("job_title", ""),
        "report_to": form.get("report_to") or "0",
        "emp_id": emp_id,
        "shift_name": form.get("shift_name", ""),
        "view_range_days": int(form.get("view_range_days", 14)),
        "callback_trigger_hours": int(form.get("callback_trigger_hours", 48)),
        "schedule": {
            "Day": form.get("Day", ""),
            "Night": form.get("Night", "")
        },
        "season": {
            "start": flip_date(form.get("season_start", "")),
            "ends": flip_date(form.get("season_ends", "")),
            "mins": convert_this_to_mins(form.get("season_mins", "")),
            "winter_maths": form.get("winter_maths", ""),
            "winter_pattern": form.get("winter_pattern", ""),
            "winter_sequence": form.get("winter_sequence", ""),
            "winter_mins": convert_this_to_mins(form.get("winter_mins", "")),
            "winter_start": flip_date(form.get("winter_start", "")),
            "winter_ends": flip_date(form.get("winter_ends", ""))
        },
        "public_holidays": form.get("public_holidays", ""),
        "default_entitlement_mins": convert_this_to_mins(form.get("default_entitlement_mins", "0")),
        "force_season_roll": form.get("force_season_roll") == "on"  # ✅ Store checkbox state
    })

    # 🔹 Clean out the working_dept
    if config["job_title"] not in ["L8", "Manager"]:
        config["working_dept"] = []

    # 🔹 Logic flags
    for key in config.get("logic_flags", {}):
        config["logic_flags"][key] = f"logic_flags_{key}" in form

    # 🔹 Entitlements carryover
    for k in config.get("annual_entitlements_carryover", {}):
        if not k.startswith("_"):
            val = form.get(f"ent_carry_{k}", "0")
            # config["annual_entitlements_carryover"][k] = convert_this_to_mins(val) if val.strip() else 0
            config["annual_entitlements_carryover"][k] = convert_expression_to_mins(val) if val.strip() else 0

    # 🔹 Entitlements used
    for k in config.get("annual_entitlements_used", {}):
        if not k.startswith("_"):
            config["annual_entitlements_used"][k] = int(form.get(f"ent_used_{k}", 0))

    # 🔹 Misc adjustments
    for k in config.get("misc_adjustments", {}):
        if not k.startswith("_"):
            config["misc_adjustments"][k] = int(form.get(f"misc_{k}", 0))

    # 🔹 Handle roster regeneration
    change_date_str = form.get("change_date", config["season"]["start"])

    shift_changed = (
        existing_config
        and existing_config.get("shift_name") != config.get("shift_name")
    )

    season_start_changed = (
        existing_config
        and existing_config.get("season", {}).get("start") != config.get("season", {}).get("start")
    )

    force_roll = config.get("force_season_roll", False)

    should_roll = is_new or shift_changed or season_start_changed or force_roll
    
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    
    if should_roll:
        rebuild_roster_with_change(emp_id, change_date=change_date_str)
        print(f"Roster regenerated for EMP: {emp_id} (reason: {'new' if is_new else 'shift/season/force'})")
        config["force_season_roll"] = False  # ✅ Reset after roll
        config["season"]["rolled_on"] = datetime.now().strftime("%Y-%m-%d")
        config["season"]["rolled_by"] = get_windows_login()
    else:
        print(f"No roster rebuild needed for EMP: {emp_id}")

    config["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    config["updated_by"] = get_windows_login()

    # 🔹 Save updated config
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    return RedirectResponse(url="/?updated=1", status_code=303)
# ----------------------------


# Helper function to regenerate roster from a specific date
def rebuild_roster_with_change(emp_id, change_date=None):
    """
    rebuild_roster_with_change(emp_id, change_date=None)
    Regenerate the roster for a specific employee from a given change date. 
    - **emp_id**: Employee ID to regenerate roster for
    - **change_date**: Date string (format "DD-MM-YYYY" or "YYYY-MM-DD") to start regeneration from; if None, regenerates full season.
    Regenerate the roster for a specific employee from a given change date.
    """
    emp_config = load_json(f"emp_{emp_id}.json")
    shift_config = load_json("shifts.json")

    # Load old roster if exists
    try:
        #roster_data = load_roster(emp_id)  # returns list of dicts
        roster_data = load_json(f"roster_{emp_id}.json") # returns list of dicts
        # roster_data = load_roster_this_season(emp_id)
    except FileNotFoundError:
        roster_data = []

    s = change_date
    last_segment = s.split("-")[-1]   # Take the last piece after splitting
    length = len(last_segment)     
    if length == 4:
        format = "%d-%m-%Y"
    else:
        format = "%Y-%m-%d"

    if change_date:
        change_date_dt = datetime.strptime(change_date, format)  # <-- updated format
        # Keep old entries before change date
        old_entries = [e for e in roster_data if datetime.strptime(e['date'], "%Y-%m-%d") < change_date_dt]
        # Update season start for generation
        emp_config["season"]["start"] = change_date
        new_entries = generate_roster(emp_config, shift_config)
        roster_data = old_entries + new_entries
    else:
        roster_data = generate_roster(emp_config, shift_config)

    save_roster(emp_id, roster_data)

    return roster_data

# ----------------------------







@app.get("/config/roster_{emp}.json")
def get_roster(emp: str):
    """
    Retrieve the roster configuration file for a specific employee.
    - **emp**: Employee ID to retrieve the roster for
    - Returns the roster JSON file as a FileResponse.
    """
    path = f"{CONFIGS_DIR}/roster_{emp}.json"
    return FileResponse(path, media_type="application/json")

from copy import deepcopy
from datetime import datetime


def serialize_summary(obj):
    if isinstance(obj, list):
        return [serialize_summary(x) for x in obj]
    elif isinstance(obj, dict):
        return {k: serialize_summary(v) for k, v in obj.items()}
    elif isinstance(obj, datetime):
        return obj.strftime('%Y-%m-%d')  # or '%d %b %Y' etc
    else:
        return obj



@app.get("/progress-summary")
def progress_summary(request: Request):
    """
    Render the progress summary page with filtering and sorting options.
    - **sort**: Sorting criteria (default: "makeup")
    - **dept**: Department filter
    - **shift**: Shift filter

    """
    sort = request.query_params.get("sort", "makeup")
    dept = request.query_params.get("dept")
    shift = request.query_params.get("shift")

    summary_report = generate_summary_report()

    # Filter by department
    if dept:
        summary_report = [emp for emp in summary_report if emp.get("department") == dept]

    # Filter by shift
    if shift:
        summary_report = [emp for emp in summary_report if emp.get("shift_name") == shift]

    # Apply sorting
    if sort == "progress":
        summary_report.sort(key=lambda emp: emp["progressPct"], reverse=True)
    elif sort == "ontrack":
        summary_report = [emp for emp in summary_report if emp["trend"] == "on_track"]
    else:
        summary_report.sort(key=lambda emp: emp["makeup"], reverse=True)

    # Get dropdown options
    all_departments = sorted(set(emp.get("department") for emp in generate_summary_report() if "department" in emp))
    all_shifts = sorted(set(emp.get("shift_name") for emp in generate_summary_report() if "shift_name" in emp))

    avg_expected_pct = round(
        sum(emp["expectedPct"] for emp in summary_report if "expectedPct" in emp) / len(summary_report), 1
    ) if summary_report else 0

    ok, me = who_is_login()

    return templates.TemplateResponse("pages/Progress_Summary.html", {
        "request": request,
        "summary_report": summary_report,
        "report_summary": serialize_summary(summary_report),
        "avg_expected_pct": avg_expected_pct,
        "sort": sort,
        "dept": dept,
        "shift": shift,
        "departments": all_departments,
        "shifts": all_shifts,
        "ok": ok,
        "me": me,
        "now": datetime.now()
    })




@app.route("/progress-summary")
def progress_summary(request: Request):
    """
    Render the progress summary page with filtering and sorting options.
    - **sort**: Sorting criteria (default: "makeup")
    """
    summary_report = generate_summary_report()
    expected_pcts = [emp["expectedPct"] for emp in summary_report if "expectedPct" in emp]
    avg_expected_pct = round(sum(expected_pcts) / len(expected_pcts), 1) if expected_pcts else 0

    print(f"Generated summary report for {len(summary_report)} employees.")
    # print(f"Sample entry: {summary_report[0] if summary_report else 'No data'}")
    ok, me = who_is_login()

    departments = sorted(set(emp["department"] for emp in summary_report if "department" in emp))


    return templates.TemplateResponse(
        "pages/Progress_Summary.html",
        {
            "request": request,  # 👈 Required for Starlette templates
            "summary_report": summary_report,   
            "departments": departments,
            "avg_expected_pct": avg_expected_pct, 
            "ok": ok,
            "me": me,
            "now": datetime.now()
        }   
    )



def parse_date(date_str):
    for fmt in ("%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unrecognized date format: {date_str}")


def calculate_expected_minutes(config, roster_data):
    season = config.get("season", {})
    default_mins = season.get("mins", 0)
    winter_mins = season.get("winter_mins", default_mins)
    winter_on = season.get("winter_maths", "off") == "on"

    season_start = parse_date(season.get("start"))
    season_end = parse_date(season.get("ends"))
    winter_start = parse_date(season.get("winter_start")) if winter_on else None
    winter_end = parse_date(season.get("winter_ends")) if winter_on else None

    expected = 0
    for entry in roster_data:
        shift_date = parse_date(entry["date"])
        if season_start <= shift_date <= season_end:
            if winter_on and winter_start <= shift_date <= winter_end:
                expected += winter_mins
            else:
                expected += default_mins
    return expected

def sum_minutes_between(data, start_date, end_date):
    return sum(
        entry.get("mins", 0)
        for entry in data
        if "date" in entry and start_date <= parse_date(entry["date"]) <= end_date
    )



def get_season_totals(data, config, reference_date=None):
    """
    Calculate season totals and progress metrics for an employee.
    Args:
        data (list): List of roster entries with 'date' and 'mins'.
        config (dict): Configuration dictionary containing season details and entitlements.
        reference_date (datetime, optional): Date to consider as "today" for calculations. Defaults to None.
        The rules are:
        1. Actual minutes worked so far in the season.
        2. Expected minutes worked so far based on straight-line pacing.
        3. Remaining minutes and makeup required to meet entitlement.
        4. Trend indicator (ahead, behind, on track).
        
    Returns:
        dict: Summary of season totals and progress metrics.

    """
    # Normalize reference date (default = today)
    today = reference_date or datetime.today()
    today = today.replace(hour=0, minute=0, second=0, microsecond=0)

    season_start = parse_date(config["season"]["start"])
    season_end = parse_date(config["season"]["ends"])
    totaltodo = config.get("default_entitlement_mins", 0)

    # 1. Actual so far
    mins_so_far = sum_minutes_between(data, season_start, today)
    #print("==============================")
    #print(f" mins_so_far = {mins_so_far}")
    # 2. Expected so far (straight-line pacing)
    season_days = (season_end - season_start).days
    days_passed = (today - season_start).days
    expected_so_far = round((days_passed / season_days) * totaltodo) if season_days else 0

    # 3. Remaining + makeup
    tomorrow = today + timedelta(days=1)

    mins_remaining = sum_minutes_between(data, tomorrow, season_end)
    makeup = totaltodo - (mins_so_far + mins_remaining)
    xtra_shift = round(makeup / 720, 1)

    # 4. Trend indicator
    if totaltodo:
        if (mins_so_far / totaltodo) * 100 >= (expected_so_far / totaltodo) * 100 + 2:
            trend = "ahead"
        elif (mins_so_far / totaltodo) * 100 <= (expected_so_far / totaltodo) * 100 - 2:
            trend = "behind"
        else:
            trend = "on_track"
    else:
        trend = "unknown"

    # 5. Cycle snapshots (last 3 x 7-day blocks)
    cycle_length = 7
    today = reference_date or datetime.today()
    today = today.replace(hour=0, minute=0, second=0, microsecond=0)

    cycles = []
    for i in range(4):
        end = today - timedelta(days=i * cycle_length)
        start = end - timedelta(days=cycle_length - 1)
        actual = sum_minutes_between(data, start, end)

        # Expected pacing for this cycle
        season_days = (season_end - season_start).days
        start_offset = (start - season_start).days
        end_offset = (end - season_start).days
        expected = round(((end_offset / season_days) * totaltodo) - ((start_offset / season_days) * totaltodo)) if season_days else 0

        pct = round((actual / expected) * 100, 1) if expected else 0
        cycles.append({
            "start": start,
            "end": end,
            "actual": actual,
            "expected": expected,
            "pct": pct
        })


    return {
        "season_start": season_start,
        "season_end": season_end,
        "cycle_snapshots": cycles,
        "employee": config.get("emp_name", "Unknown"),
        "department": config.get("departments", "Unknown"),
        "shift_name": config.get("shift_name", "Unknown"),
        "totaltodo": totaltodo,
        "minsSoFar": mins_so_far,
        "expectedSoFar": expected_so_far,
        "minsRemaining": mins_remaining,
        "makeup": makeup,
        "xtraShift": xtra_shift,
        "trend": trend,
        "totalSeason": mins_so_far + mins_remaining,
        "progressPct": round((mins_so_far / totaltodo) * 100, 1) if totaltodo else 0,
        "expectedPct": round((expected_so_far / totaltodo) * 100, 1) if totaltodo else 0
    }


def generate_summary_report():
    """
    Generate a summary report for all employees, including their season totals and progress metrics.

    Returns:
        list: A list of summary dictionaries for each employee, sorted by makeup descending.
    """
    employees = load_all_employees()
    report = []

    for emp_id in employees:
        config = load_employee_config(emp_id)
        #roster_data = load_json(f"roster_{emp_id}.json")
        roster_data = load_roster_this_season(emp_id)
        summary = get_season_totals(roster_data, config)
        #print(f"Processed {emp_id}: {config}")
        report.append(summary)

    # Sort by makeup descending (most behind first)
    report.sort(key=lambda emp: emp["makeup"], reverse=True)

    return report



def load_employee_config(emp_id):
    """
    Loads the config for a given employee ID from a JSON file.

    Args:
        emp_id (str): The employee ID (e.g., "123456").
        base_path (str): Directory where config files are stored.

    Returns:
        dict: Parsed config dictionary.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        json.JSONDecodeError: If the file isn't valid JSON.
    """
    filename = f"emp_{emp_id}.json"
    filepath = os.path.join(CONFIGS_DIR, filename)

    with open(filepath, "r", encoding="utf-8") as f:
        config = json.load(f)

    return config


@app.post("/append_roster_entry")
def append_roster_entry(payload: dict):
    emp_id = payload["emp_id"]
    entry = payload["entry"]

    # ✅ Ensure ID exists
    entry.setdefault("ID", str(uuid4()))

    # ✅ Validate required fields
    required_fields = ["date", "shift_type", "type_shift", "mins"]
    missing = [k for k in required_fields if k not in entry]
    if missing:
        return {"status": "error", "detail": f"Missing fields: {', '.join(missing)}"}

    file_path = Path(f"{CONFIGS_DIR}/roster_{emp_id}.json")

    with file_path.open("r+", encoding="utf-8") as f:
        data = json.load(f)

        # ✅ Optional: prevent duplicates
        if any(
            e["date"] == entry["date"] and
            e.get("shift_type") == entry["shift_type"] and
            e.get("type_shift") == entry["type_shift"]
            for e in data
        ):
            return {"status": "error", "detail": "Duplicate entry"}

        # ✅ Append and sort
        data.append(entry)
        data.sort(key=lambda x: (
            datetime.strptime(x["date"], "%Y-%m-%d"),
            0 if x.get("shift_type", "").lower() == "day" else 1
        ))

        # ✅ Write back
        f.seek(0)
        json.dump(data, f, indent=2)
        f.truncate()

    print(f"✅ Added roster entry for {emp_id} on {entry['date']} ({entry['shift_type']} - {entry['type_shift']})")
    return {"status": "ok"}






@app.post("/append_roster_entry_OLD")
def append_roster_entry(payload: dict):
    emp_id = payload["emp_id"]
    entry = payload["entry"]
    entry.setdefault("ID", str(uuid4()))
    file_path = Path(f"{CONFIGS_DIR}/roster_{emp_id}.json")  # Use Path object

    with file_path.open("r+", encoding="utf-8") as f:
        data = json.load(f)

        # Add the new entry
        data.append(entry)

        # Sort by date and shift_type (Day before Night)
        data.sort(key=lambda x: (
            datetime.strptime(x["date"], "%Y-%m-%d"),
            0 if x["shift_type"].lower() == "day" else 1
        ))
        

        # Write back sorted data
        f.seek(0)
        json.dump(data, f, indent=2)
        f.truncate()

    return {"status": "ok"}


def calculate_entitlements(rosters, entitlement_types=None):
    """
    Calculate total mins per entitlement type per employee.
    entitlement_types is a set or list of types to sum, or None to sum all.
    """
    entitlements = {}
    
    for emp_id, shifts in rosters.items():
        entitlements[emp_id] = {}
        for entry in shifts:
            etype = entry.get("type_shift") or entry.get("shift_type") or "Unknown"
            mins = entry.get("mins", 0)
            
            if entitlement_types and etype not in entitlement_types:
                continue
            
            entitlements[emp_id][etype] = entitlements[emp_id].get(etype, 0) + mins

    return entitlements


def update_employee_config(emp_file, defaults):
    #.... 1
    from datetime import datetime
    import json

    with open(emp_file, "r", encoding="utf-8") as f:
        emp = json.load(f)

    # 1) Replace notes exactly
    defaults_notes = defaults.get("notes", {})
    emp["notes"] = dict(defaults_notes)

    # 2) Replace code lists exactly
    emp["off_codes"] = list(defaults.get("off_codes", []))
    emp["working_codes"] = list(defaults.get("working_codes", []))
    emp["min_blind_codes"] = list(defaults.get("min_blind_codes", []))
    emp["draw_down_codes"] = list(defaults.get("draw_down_codes", []))

    # 3) Determine valid entitlement codes (exclude meta keys)
    meta = {"entitlement_unit", "purpose", "last_updated"}
    valid_codes = {k for k in defaults_notes.keys() if k not in meta}

    # 4) Sync carryover and used: prune deleted codes, add missing with 0, keep existing values
    for section in ("annual_entitlements_carryover", "annual_entitlements_used"):
        sec = emp.get(section, {})
        notes_val = sec.get("_notes")
        sec = {k: v for k, v in sec.items() if k in valid_codes}
        for code in valid_codes:
            sec.setdefault(code, 0)
        if notes_val is not None:
            sec["_notes"] = notes_val
        emp[section] = sec

    emp["last_updated"] = datetime.utcnow().isoformat()

    with open(emp_file, "w", encoding="utf-8") as f:
        json.dump(emp, f, indent=2, ensure_ascii=False)



# New route to view the entitlement summary by department
@app.route('/entitlement-summary')
async def entitlement_summary(request: Request):
    department_summary , season_start, season_end , emp_count = summarize_entitlements_by_department()
    ok, me = who_is_login()
    return templates.TemplateResponse(
        "pages/entitlement-summary.html", 
        {"request": request,  # Pass 'request' to the template (needed for Jinja2)
         "department_summary": department_summary,
         "season_start": season_start,
         "season_end": season_end,
         "emp_count": emp_count,
         "ok": ok, 
         "me": me, 
         "now": datetime.now()}
    )

#----------------------------



@app.get("/help", response_class=HTMLResponse)
async def help_page(request: Request):
    login = get_windows_login()
    emp_list = load_all_employees()
    ok, me = who_is_login()
    # print(f" reporting manager = {load_reporting_managers()}")
    return templates.TemplateResponse("pages/help.html", {

        "request": request,
        "ok":ok,
        "me":me,
        "reporting_managers": load_reporting_managers(),
        "now": datetime.now(),
        "datetime": datetime
    })


@app.get("/start", response_class=HTMLResponse)
async def start(request: Request):

    updated = request.query_params.get("updated")
    # Use updated to trigger frontend message logic
    ensure_job_titles_file()
    config_default = load_json("default.json")
    #config_default_annual_entitlements_used = config_default["annual_entitlements_used"]
    config_carryover = config_default["annual_entitlements_carryover"]
    del config_carryover['_notes']
    config_entitlements = config_default["notes"]
    del config_entitlements['entitlement_unit']
    del config_entitlements['purpose']
    del config_entitlements['last_updated']
    emp_list = load_all_employees()
    reportmanager = load_reporting_managers()
    reportingto = get_active_managers(emp_list, reportmanager)
    shiftdata = load_json("shifts.json")
    import holidays
    current_year = datetime.now().year
    next_year = current_year + 1
    
    nz_holidays = holidays.country_holidays('NZ',years=[current_year, next_year],subdiv="Taranaki")

    holiday_map = {date.strftime("%Y-%m-%d"): name for date, name in nz_holidays.items()}
 
    rosters = load_all_rosters()
    config_carryover = config_default["annual_entitlements_carryover"]

    # print(f"🔍 Loaded carryover config: {config_carryover}")
    entitlements_data = calculate_entitlements(rosters, entitlement_types={"SHIFT", "SICK", "TOFF"})

    shifts_data = load_shifts()
    shifts = shifts_data.get("Shifts", [])
    today_str = datetime.now().strftime("%d %B %Y")
    # whaton = get_shift_summary_for_date(today_str,shiftdata)
    today_str = datetime.now().strftime("%Y-%m-%d")
    employees = load_all_employees()
    current_year = datetime.now().year
    current_month = datetime.now().month
    login = get_windows_login()
    emp_list = load_all_employees()
    ok, me = who_is_login()
    
    return templates.TemplateResponse("pages/summary.html", {
        "request": request,
        "ok":ok,
        "me":me,
        "shifts": shifts,
        "employees": employees,
        "current_year": current_year,
        "current_month": current_month,
        "shiftdata":shiftdata,
        "today_str":today_str,
        "now": datetime.now(),
        "datetime": datetime,
        "config_entitlements": config_entitlements, 
        "holiday_map": holiday_map
    })



def sort_ids(eids, emp_map, titles_order):
    def prio(eid):
        emp = emp_map[eid]
        title = emp.get('job_title', '')
        t = titles_order.index(title) if title in titles_order else len(titles_order)
        name = (emp.get('name') or '').lower()
        return (t, name)
    return sorted(eids, key=prio)


def render_node_tree(eid, dept, emp_map, children_map, titles_order, visited, prefix):
    """Render one employee and their in-department children (no duplicates)."""
    if eid in visited:
        return ''
    emp = emp_map.get(eid)
    if not emp:
        return ''

    # only show if this employee is in this department
    if emp.get('department_name') != dept:
        return ''

    visited.add(eid)

    job_title = emp.get('job_title', 'N/A')
    is_manager = job_title in {'Manager', 'L8', 'L7'}
    manager_class = "bg-yellow-100 font-bold" if is_manager else "bg-white"
    phone = (emp.get('phone') or 'N/A').strip() or 'N/A'
    shift = emp.get('shift', 'N/A')

    # children restricted to same department & not yet visited
    raw_children = children_map.get(eid, [])
    dept_children = [cid for cid in raw_children
                     if cid in emp_map and emp_map[cid].get('department_name') == dept and cid not in visited]

    ordered_children = sort_ids(dept_children, emp_map, titles_order)

    # we’ll render children with proper ASCII connectors
    items_html = []
    for idx, cid in enumerate(ordered_children):
        is_last = (idx == len(ordered_children) - 1)
        new_prefix = prefix + ("   " if is_last else "│  ")
        items_html.append(render_node_tree(cid, dept, emp_map, children_map, titles_order, visited, new_prefix))

    # figure out this node’s branch glyph relative to its parent (prefix shows ancestor lines)
    # when prefix == '' we’re at a root → no branch glyph
    branch = ''
    if prefix != '':
        # if parent handed us a prefix that already includes spaces/pipes,
        # add our own connector at the end based on whether parent considered us last.
        # We can infer from the last 3 chars of prefix: '   ' means parent marked previous as last
        parent_mark_last = prefix.endswith('   ')
        # but we can’t know our own birth order from here; so we draw our own in the parent loop.
        # Instead, we render the branch for children below, and show nothing here.
        # To keep it simple, show the prefix pipes; the child rows will show ├─/└─.
        pass

    # Build this LI row (we’ll show prefix pipes + a bullet connector for clarity)
    # For roots (prefix == ''), show no leading pipes
    prefix_text = prefix[:-3] if prefix.endswith(('   ', '│  ')) else prefix  # clean trailing marker for current row

    # Row HTML
    row_html = f'''
    <li>
      <div class="flex items-center {manager_class} rounded-xl shadow px-4 py-2 hover:scale-105 transition">
        {'<span class="mr-2 text-gray-500 whitespace-pre">' + prefix_text + ('└─' if not ordered_children else '├─') + '</span>' if prefix else ''}
        <a href="/config_person/{emp['id']}" class="font-semibold text-gray-800 hover:underline">{emp['name']}</a>
        <span class="text-sm text-gray-600 ml-2">{shift}</span>
        <span class="ml-2 px-2 py-0.5 rounded-full text-xs font-medium">{job_title}</span>
        <span class="text-sm text-gray-500 ml-2">{phone}</span>
        <span class="text-xs text-red-600 ml-2">ID: {emp['id']}</span>
      </div>
    '''

    # Children <ul>
    children_html = ''
    if ordered_children:
        # For each child we must draw its own connector (├─/└─). We’ll embed it inside the child’s row
        # via its received prefix.
        children_html = '<ul class="pl-4 border-l-2 border-gray-300 space-y-2">' + ''.join(items_html) + '</ul>'

    return row_html + children_html + '</li>'






@app.get("/org", response_class=HTMLResponse)
async def org_chart(request: Request):
    
    # print(f"🔍 Loaded employee list: {emp_data}")
    emp_list = load_all_employees()
    report_map = {}
    for emp_id, emp_data in emp_list.items():
        manager_id = emp_data.get("report_to")
        if manager_id and manager_id != "0":
            report_map.setdefault(manager_id, set()).add(emp_id)
    # Get job titles and departments
    job_titles, departments = load_job_titles(strip_notes=True)
    emp_data = load_all_employees()
    emp_list = list(emp_data.values())
    # print(f"🔍 Loaded job emp_list: {emp_list}")

    # Build reporting tree
    data = build_reporting_tree(emp_list, departments)

    # Custom titles order
    titles_order = ["Manager", "L8", "L7", "2IC", "L6", "5A", "5B", "L4"]

    # Sort top-level managers
    def sort_priority(emp):
        title = emp.get("job_title", "")
        return titles_order.index(title) if title in titles_order else len(titles_order)

    no_manager = sorted(
        [{**{'id': emp_id}, **info} for emp_id, info in emp_data.items() if info.get('report_to') in ('0', None)],
        key=sort_priority
    )

    # Sort each manager's reports
    sorted_data = {
        manager_id: sorted(reports, key=sort_priority)
        for manager_id, reports in data.items()
    }

    emp_list = load_all_employees()
    login = get_windows_login()
 
    ok, me = who_is_login()

    #print(f"ok={ok}, me={me}")

    if not me:
        return RedirectResponse(url="/help", status_code=303)

    # Build HTML tree with sorting
    html_body = build_html_tree(sorted_data, departments, titles_order, me, no_manager)
    return templates.TemplateResponse("pages/org_tree.html", {
        "request": request,
        "ok":ok,
        "me":me,
        "now": datetime.now(),
        "no_manager": no_manager,
        "html_body": html_body
    })


@app.post("/delete_time_offf")
async def delete_time_offf(request: Request):
    try:
        data = await request.json()
        id = data.get("id")
        emp_id = data.get("emp_id")
        date = data.get("date")
        shift_type = data.get("shift_type")
        type_shift = data.get("type_shift")
        #print(f"🗑️ Deleting entry with ID: {id} for emp_id: {emp_id}, date: {date}, shift_type: {shift_type}, type_shift: {type_shift}")
        if not emp_id or not date or not shift_type or not type_shift or not id:
            raise HTTPException(status_code=400, detail="Missing required fields")

        file_path = Path(f"configs/roster_{emp_id}.json")

        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Roster not found")

        with file_path.open("r", encoding="utf-8") as f:
            try:
                roster = json.load(f)
            except json.JSONDecodeError:
                raise HTTPException(status_code=500, detail="Invalid JSON in roster file")

        original_len = len(roster)
        roster = [
            r for r in roster
            if not (
                r.get("ID") == id
                # r.get("date") == date and
                # r.get("shift_type", "").lower() == shift_type.lower() and
                # r.get("type_shift", "").lower() == type_shift.lower()
            )
        ]

        if len(roster) == original_len:
            return {"status": "ok", "message": "Nothing deleted"}

        # Sort again
        roster.sort(key=lambda x: (
            datetime.strptime(x["date"], "%Y-%m-%d"),
            0 if x.get("shift_type", "").lower() == "day" else 1
        ))

        with file_path.open("w", encoding="utf-8") as f:
            json.dump(roster, f, indent=2)

        return {"status": "ok"}

    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "detail": str(e)})

@app.post("/delete_time_off")
async def delete_time_off(request: Request):
    try:
        data = await request.json()
        id = data.get("id")
        emp_id = data.get("emp_id")

        if not emp_id or not id:
            raise HTTPException(status_code=400, detail="Missing required fields")

        file_path = Path(f"{CONFIGS_DIR}/roster_{emp_id}.json")
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Roster not found")

        with file_path.open("r", encoding="utf-8") as f:
            roster = json.load(f)

        original_len = len(roster)
        roster = [r for r in roster if r.get("ID") != id]

        if len(roster) == original_len:
            return {"status": "ok", "message": "Nothing deleted"}

        # Sort by date + shift_type again
        roster.sort(key=lambda x: (
            datetime.strptime(x["date"], "%Y-%m-%d"),
            0 if x.get("shift_type", "").lower() == "day" else 1
        ))

        with file_path.open("w", encoding="utf-8") as f:
            json.dump(roster, f, indent=2)

        return {"status": "ok"}

    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "detail": str(e)})



@app.post("/save_time_off")
async def save_time_off(request: Request):
    try:
        payload = await request.json()
        emp_id = payload.get("emp_id")
        entries = payload.get("entries", [])

        # print(f"📝 Received entries for emp_id {emp_id}: {entries}")

        if not emp_id or not entries:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "detail": "Missing emp_id or entries"}
            )

        file_path = Path(f"{CONFIGS_DIR}/roster_{emp_id}.json")

        if not file_path.exists():
            return JSONResponse(
                status_code=404,
                content={"status": "error", "detail": "Roster file not found"}
            )

        with file_path.open("r+", encoding="utf-8") as f:
            try:
                roster_data = json.load(f)
            except json.JSONDecodeError:
                return JSONResponse(
                    status_code=500,
                    content={"status": "error", "detail": "Invalid JSON file"}
                )

            updated_count = 0
            added_count = 0

            for new_entry in entries:
                entry_id = new_entry.get("ID")  # Get ID from entry
                shift = new_entry.get("shift", "")
                date = new_entry.get("date")
                shift_type = new_entry.get("shift_type")
                type_shift = new_entry.get("type_shift")
                mins = new_entry.get("mins")
                notes = new_entry.get("notes", "")

                matched = False

                if entry_id:  # Try to update existing record
                    for record in roster_data:
                        if record.get("ID") == entry_id:
                            record.update({
                                "date": date,
                                "shift": shift,
                                "shift_type": shift_type,
                                "type_shift": type_shift,
                                "mins": mins,
                                "notes": notes
                            })
                            updated_count += 1
                            matched = True
                            break

                if not matched:  # Add new record
                    roster_data.append({
                        "ID": str(uuid4()),
                        "date": date,
                        "shift": shift,
                        "shift_type": shift_type,
                        "type_shift": type_shift,
                        "mins": mins,
                        "callback_eligible": False,
                        "cover_allowed": False,
                        "on_shift": True,
                        "notes": notes,
                        
                    })
                    added_count += 1

            # Sort the records by date and shift_type
            roster_data.sort(key=lambda x: (
                datetime.strptime(x["date"], "%Y-%m-%d"),
                0 if x.get("shift_type", "").lower() == "day" else 1
            ))

            # Save the updated file
            f.seek(0)
            json.dump(roster_data, f, indent=2)
            f.truncate()

        return {
            "status": "ok",
            "updated": updated_count,
            "added": added_count
        }

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "detail": f"Unexpected error: {str(e)}"}
        )


@app.post("/save_shift_edits")
def save_shift_edits(payload: dict):
    emp_id = payload.get("emp_id")
    edits = payload.get("edits", [])
    # print("📝 Incoming edits:", edits)

    file_path = Path(f"{CONFIGS_DIR}/roster_{emp_id}.json")

    if not file_path.exists():
        return {"status": "error", "detail": "Roster file not found"}

    try:
        with file_path.open("r+", encoding="utf-8") as f:
            try:
                data = json.load(f)
                print("📂 Loaded roster data:", data)
            except Exception as e:
                print("💥 Failed to parse JSON:", e)
                return {"status": "error", "detail": "Invalid JSON format"}

            updated = 0

            for edit in edits:
                for entry in data:
                   
                    if entry.get("date") == edit.get("date"):
                        #print(f"✅ Updating {edit['date']}")
                        entry["shift_type"] = edit.get("shift_type", "")
                        entry["type_shift"] = edit.get("type_shift", "")
                        entry["mins"] = edit.get("mins", 0)
                        entry["notes"] = edit.get("notes", "")
                        updated += 1
                        break

            data.sort(key=lambda x: (
                datetime.strptime(x["date"], "%Y-%m-%d"),
                0 if x.get("shift_type", "").lower() == "day" else 1
            ))

            # Overwrite the file from the beginning
            f.seek(0)
            json.dump(data, f, indent=2)
            f.truncate()

        return {"status": "ok", "updated": updated}

    except Exception as e:
        print("💥 Unexpected error opening/writing the file:", e)
        return {"status": "error", "detail": "File access error"}


def expand_pattern(pattern_str):
    """
    Expands a shorthand pattern like '4x4x12' into a sequence like 'DDNN****'.
    Currently assumes:
      - 'D' for day
      - 'N' for night
      - '*' for off
    """
    parts = pattern_str.split("x")
    if len(parts) != 3:
        raise ValueError("Invalid pattern format, expected '4x4x12'")
    
    days_on = int(parts[0])
    days_off = int(parts[1])
    hours = int(parts[2])  # unused here but could be logged or validated
    
    # Default to D for on-days, * for off-days (you can adjust this logic)
    sequence = "D" * days_on + "*" * days_off
    return sequence




@app.get("/config/roster_{emp}.json")
def get_roster(emp: str):
    path = f"{CONFIGS_DIR}/roster_{emp}.json"
    return FileResponse(path, media_type="application/json")


@app.get("/progress-summary")
def progress_summary(request: Request):
    sort = request.query_params.get("sort", "makeup")
    dept = request.query_params.get("dept")
    shift = request.query_params.get("shift")

    summary_report = generate_summary_report()

    # Filter by department
    if dept:
        summary_report = [emp for emp in summary_report if emp.get("department") == dept]

    # Filter by shift
    if shift:
        summary_report = [emp for emp in summary_report if emp.get("shift_name") == shift]

    # Apply sorting
    if sort == "progress":
        summary_report.sort(key=lambda emp: emp["progressPct"], reverse=True)
    elif sort == "ontrack":
        summary_report = [emp for emp in summary_report if emp["trend"] == "on_track"]
    else:
        summary_report.sort(key=lambda emp: emp["makeup"], reverse=True)

    # Get dropdown options
    all_departments = sorted(set(emp.get("department") for emp in generate_summary_report() if "department" in emp))
    all_shifts = sorted(set(emp.get("shift_name") for emp in generate_summary_report() if "shift_name" in emp))

    avg_expected_pct = round(
        sum(emp["expectedPct"] for emp in summary_report if "expectedPct" in emp) / len(summary_report), 1
    ) if summary_report else 0

    ok, me = who_is_login()

    return templates.TemplateResponse("pages/Progress_Summary.html", {
        "request": request,
        "summary_report": summary_report,
        "avg_expected_pct": avg_expected_pct,
        "sort": sort,
        "dept": dept,
        "shift": shift,
        "departments": all_departments,
        "shifts": all_shifts,
        "ok": ok,
        "me": me,
        "now": datetime.now()
    })




@app.route("/progress-summary")
def progress_summary(request: Request):
    summary_report = generate_summary_report()
    expected_pcts = [emp["expectedPct"] for emp in summary_report if "expectedPct" in emp]
    avg_expected_pct = round(sum(expected_pcts) / len(expected_pcts), 1) if expected_pcts else 0

    print(f"Generated summary report for {len(summary_report)} employees.")
    # print(f"Sample entry: {summary_report[0] if summary_report else 'No data'}")
    ok, me = who_is_login()

    departments = sorted(set(emp["department"] for emp in summary_report if "department" in emp))


    return templates.TemplateResponse(
        "pages/Progress_Summary.html",
        {
            "request": request,  # 👈 Required for Starlette templates
            "summary_report": summary_report,   
            "departments": departments,
            "avg_expected_pct": avg_expected_pct, 
            "ok": ok,
            "me": me,
            "now": datetime.now()
        }   
    )



def parse_date(date_str):
    for fmt in ("%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unrecognized date format: {date_str}")


def calculate_expected_minutes(config, roster_data):
    season = config.get("season", {})
    default_mins = season.get("mins", 0)
    winter_mins = season.get("winter_mins", default_mins)
    winter_on = season.get("winter_maths", "off") == "on"

    season_start = parse_date(season.get("start"))
    season_end = parse_date(season.get("ends"))
    winter_start = parse_date(season.get("winter_start")) if winter_on else None
    winter_end = parse_date(season.get("winter_ends")) if winter_on else None

    expected = 0
    for entry in roster_data:
        shift_date = parse_date(entry["date"])
        if season_start <= shift_date <= season_end:
            if winter_on and winter_start <= shift_date <= winter_end:
                expected += winter_mins
            else:
                expected += default_mins
    return expected

def sum_minutes_between(data, start_date, end_date):
    return sum(
        entry.get("mins", 0)
        for entry in data
        if "date" in entry and start_date <= parse_date(entry["date"]) <= end_date
    )



def get_season_totals(data, config, reference_date=None):
    # Normalize reference date (default = today)
    today = reference_date or datetime.today()
    today = today.replace(hour=0, minute=0, second=0, microsecond=0)

    season_start = parse_date(config["season"]["start"])
    season_end = parse_date(config["season"]["ends"])
    totaltodo = config.get("default_entitlement_mins", 0)

    # 1. Actual so far
    mins_so_far = sum_minutes_between(data, season_start, today)

    # 2. Expected so far (straight-line pacing)
    season_days = (season_end - season_start).days
    days_passed = (today - season_start).days
    expected_so_far = round((days_passed / season_days) * totaltodo) if season_days else 0

    # 3. Remaining + makeup
    tomorrow = today + timedelta(days=1)
    mins_remaining = sum_minutes_between(data, tomorrow, season_end)
    makeup = totaltodo - (mins_so_far + mins_remaining)
    xtra_shift = round(makeup / 720, 1)

    # 4. Trend indicator
    if totaltodo:
        if (mins_so_far / totaltodo) * 100 >= (expected_so_far / totaltodo) * 100 + 2:
            trend = "ahead"
        elif (mins_so_far / totaltodo) * 100 <= (expected_so_far / totaltodo) * 100 - 2:
            trend = "behind"
        else:
            trend = "on_track"
    else:
        trend = "unknown"

    # 5. Cycle snapshots (last 3 x 7-day blocks)
    cycle_length = 7
    today = reference_date or datetime.today()
    today = today.replace(hour=0, minute=0, second=0, microsecond=0)

    cycles = []
    for i in range(4):
        end = today - timedelta(days=i * cycle_length)
        start = end - timedelta(days=cycle_length - 1)
        actual = sum_minutes_between(data, start, end)

        # Expected pacing for this cycle
        season_days = (season_end - season_start).days
        start_offset = (start - season_start).days
        end_offset = (end - season_start).days
        expected = round(((end_offset / season_days) * totaltodo) - ((start_offset / season_days) * totaltodo)) if season_days else 0

        pct = round((actual / expected) * 100, 1) if expected else 0
        cycles.append({
            "start": start,
            "end": end,
            "actual": actual,
            "expected": expected,
            "pct": pct
        })


    return {
        "season_start": season_start,
        "season_end": season_end,
        "cycle_snapshots": cycles,
        "employee": config.get("emp_name", "Unknown"),
        "department": config.get("departments", "Unknown"),
        "shift_name": config.get("shift_name", "Unknown"),
        "totaltodo": totaltodo,
        "minsSoFar": mins_so_far,
        "expectedSoFar": expected_so_far,
        "minsRemaining": mins_remaining,
        "makeup": makeup,
        "xtraShift": xtra_shift,
        "trend": trend,
        "totalSeason": mins_so_far + mins_remaining,
        "progressPct": round((mins_so_far / totaltodo) * 100, 1) if totaltodo else 0,
        "expectedPct": round((expected_so_far / totaltodo) * 100, 1) if totaltodo else 0
    }


def generate_summary_report():
    employees = load_all_employees()
    report = []

    for emp_id in employees:
        config = load_employee_config(emp_id)
        #roster_data = load_json(f"roster_{emp_id}.json")
        roster_data = load_roster_this_season(emp_id)
        summary = get_season_totals(roster_data, config)
        #print(f"Processed {emp_id}: {config}")
        report.append(summary)

    # Sort by makeup descending (most behind first)
    report.sort(key=lambda emp: emp["makeup"], reverse=True)

    return report

@app.post("/append_roster_entry")
def append_roster_entry(payload: dict):
    emp_id = payload["emp_id"]
    entry = payload["entry"]

    file_path = Path(f"{CONFIGS_DIR}/roster_{emp_id}.json")  # Use Path object

    with file_path.open("r+", encoding="utf-8") as f:
        data = json.load(f)

        # Add the new entry
        data.append(entry)

        # Sort by date and shift_type (Day before Night)
        data.sort(key=lambda x: (
            datetime.strptime(x["date"], "%Y-%m-%d"),
            0 if x["shift_type"].lower() == "day" else 1
        ))
        

        # Write back sorted data
        f.seek(0)
        json.dump(data, f, indent=2)
        f.truncate()

    return {"status": "ok"}


def calculate_entitlements(rosters, entitlement_types=None):
    """
    Calculate total mins per entitlement type per employee.
    entitlement_types is a set or list of types to sum, or None to sum all.
    """
    entitlements = {}
    
    for emp_id, shifts in rosters.items():
        entitlements[emp_id] = {}
        for entry in shifts:
            etype = entry.get("type_shift") or entry.get("shift_type") or "Unknown"
            mins = entry.get("mins", 0)
            
            if entitlement_types and etype not in entitlement_types:
                continue
            
            entitlements[emp_id][etype] = entitlements[emp_id].get(etype, 0) + mins

    return entitlements

def load_entitlements_settings() -> dict:
    config_default = load_json("default.json")
    off_codes = config_default.get("off_codes", [])
    working_codes = config_default.get("working_codes", [])
    min_blind_codes = config_default.get("min_blind_codes", [])
    draw_down_codes = config_default.get("draw_down_codes", [])  # ✅ corrected to list
        
    entitlements = config_default.get("notes", {})
    
    return {
        "off_codes": off_codes,
        "working_codes": working_codes,
        "min_blind_codes": min_blind_codes,
        "draw_down_codes": draw_down_codes,
        "entitlements": entitlements
    }

#=============================================================================

@app.get("/edit-entitlements")
async def edit_entitlements(request: Request):
    data = load_default_config()
    off_codes = data.get("off_codes", [])
    working_codes = data.get("working_codes", [])   
    min_blind_codes = data.get("min_blind_codes", [])   
    draw_down_codes = data.get("draw_down_codes", [])  # ✅ corrected to list
    # print(f"draw_down_codes  = {draw_down_codes}")
    entitlements = data.get("notes", {})
    empcount = len(load_all_employees())
    ok, me = who_is_login()

    return templates.TemplateResponse("pages/entitlements_edits.html", {
        "request": request,
        "ok": ok,
        "me": me,
        "now": datetime.now(),
        "empcount": empcount,
        "off_codes": off_codes,
        "working_codes": working_codes,     
        "min_blind_codes": min_blind_codes,     
        "must_drawdown_codes": draw_down_codes,
        "entitlements": entitlements
    })




@app.post("/save-entitlements")
async def save_entitlements(request: Request):
    form = await request.form()
    data = load_default_config()

    data.setdefault("annual_entitlements_carryover", {})
    data.setdefault("annual_entitlements_used", {})

    notes = data.get("notes", {})
    meta_keys = {"entitlement_unit", "purpose", "last_updated"}

    deleted_codes = set(form.getlist("deleted_codes") or [])
    for code in deleted_codes:
        notes.pop(code, None)
        data["annual_entitlements_carryover"].pop(code, None)
        data["annual_entitlements_used"].pop(code, None)

    new_notes = {k: notes[k] for k in meta_keys if k in notes}
    remaining_codes = [c for c in notes.keys() if c not in meta_keys]

    for code in remaining_codes:
        incoming = form.get(f"description_{code}")
        desc = incoming.strip() if incoming and incoming.strip() else notes.get(code, "")
        new_notes[code] = desc

    prev_off = set(data.get("off_codes", []))
    prev_work = set(data.get("working_codes", []))
    prev_min = set(data.get("min_blind_codes", []))
    prev_drawdown = set(data.get("draw_down_codes", []))

    off_codes, working_codes, min_blind_codes, drawdown_codes = set(), set(), set(), set()

    for code in new_notes.keys():
        if code in meta_keys:
            continue
        ent_type = form.get(f"entitlement_{code}")
        if ent_type == "off_code":
            off_codes.add(code)
        elif ent_type == "working_code":
            working_codes.add(code)
        elif ent_type == "min_blind_code":
            min_blind_codes.add(code)
        else:
            if code in prev_off: off_codes.add(code)
            elif code in prev_work: working_codes.add(code)
            elif code in prev_min: min_blind_codes.add(code)

        drawdown_flag = form.get(f"drawdown_{code}")
        if drawdown_flag == "true":
            drawdown_codes.add(code)
        # else: do nothing—unticked codes are excluded


    new_code = (form.get("new_code") or "").strip().upper()
    new_description = (form.get("new_description") or "").strip()
    if new_code and new_description:
        new_notes[new_code] = new_description
        t = form.get("new_entitlement")
        if t == "off_code": off_codes.add(new_code)
        elif t == "working_code": working_codes.add(new_code)
        elif t == "min_blind_code": min_blind_codes.add(new_code)
        if form.get("new_drawdown") == "true":
            drawdown_codes.add(new_code)
        data["annual_entitlements_carryover"].setdefault(new_code, 0)
        data["annual_entitlements_used"].setdefault(new_code, 0)

    new_notes["last_updated"] = datetime.utcnow().date().isoformat()
    data["notes"] = new_notes
    data["off_codes"] = sorted(off_codes)
    data["working_codes"] = sorted(working_codes)
    data["min_blind_codes"] = sorted(min_blind_codes)
    data["draw_down_codes"] = sorted(drawdown_codes)  # ✅ always updated
    data["last_updated"] = datetime.utcnow().isoformat()

    for emp_file in os.listdir(CONFIGS_DIR):
        if emp_file.startswith("emp_") and emp_file.endswith(".json"):
            emp_file_path = os.path.join(CONFIGS_DIR, emp_file)
            update_employee_config(emp_file_path, data)

    with open(os.path.join(CONFIGS_DIR, "default.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return RedirectResponse(url="/edit-entitlements", status_code=303)

#-------------------------------------------------------------------------------

@app.get("/debug/routes")
def list_routes():
    return [
        {"path": route.path, "methods": list(route.methods)}
        for route in app.routes
        if isinstance(route, APIRoute)
    ]





# New route to view the entitlement summary by department
@app.route('/entitlement-summary')
async def entitlement_summary(request: Request):
    department_summary , season_start, season_end , emp_count = summarize_entitlements_by_department()
    ok, me = who_is_login()
    return templates.TemplateResponse(
        "pages/entitlement-summary.html", 
        {"request": request,  # Pass 'request' to the template (needed for Jinja2)
         "department_summary": department_summary,
         "season_start": season_start,
         "season_end": season_end,
         "emp_count": emp_count,
         "ok": ok, 
         "me": me, 
         "now": datetime.now()}
    )


#----------------------------
@app.get("/calendar", response_class=HTMLResponse)
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    updated = request.query_params.get("updated")

    ensure_job_titles_file()
    config_default = load_json("default.json")

    config_carryover = config_default["annual_entitlements_carryover"]
    del config_carryover["_notes"]

    config_entitlements = config_default["notes"]
    del config_entitlements["entitlement_unit"]
    del config_entitlements["purpose"]
    del config_entitlements["last_updated"]

    emp_list = load_all_employees()
    reportmanager = load_reporting_managers()
    reportingto = get_active_managers(emp_list, reportmanager)

    #print(f"emp_list = {emp_list}")
    #print(f"reportingto = {reportingto}")
    #print(f"reportingto count = {len(reportingto)}")
    report_map = {}
    for emp_id, emp_data in emp_list.items():
        manager_id = emp_data.get("report_to")
        if manager_id and manager_id != "0":
            report_map.setdefault(manager_id, set()).add(emp_id)

    # print(f"report_map = {report_map}")
    showLeave = False
    if len(reportingto) >= 3:
        showLeave = True

    shift_counts = Counter(e["shift"] for e in emp_list.values())

    shiftdata = load_json("shifts.json")
    
    shifts = shiftdata.get("Shifts", [])

    for s in shifts:
        s["count"] = shift_counts.get(s["name"], 0)
    
    shifts_counts = [s for s in shifts if s.get("count", 0) > 0]

    
    
    import holidays
    current_year = datetime.now().year
    next_year = current_year + 1
    nz_holidays = holidays.country_holidays(
        "NZ", years=[current_year, next_year], subdiv=config_default.get("public_holidays", "Taranaki")
    )
    holiday_map = {date.strftime("%Y-%m-%d"): name for date, name in nz_holidays.items()}

    rosters = load_all_rosters()
    config_carryover = config_default["annual_entitlements_carryover"]

    entitlements_data = calculate_entitlements(rosters, entitlement_types={"SHIFT", "SICK", "TOFF"})
    shifts_data = load_shifts()
    shifts = shifts_data.get("Shifts", [])

    today_str = datetime.now().strftime("%Y-%m-%d")
    employees = load_all_employees()
    current_year = datetime.now().year
    current_month = datetime.now().month

    # --- figure out current user ---
    login = get_windows_login()
    me = find_employee_by_login(emp_list, login)

    if not me:
        me_depts = []
        me_name = "Unknown"
        me_shift = "?"
    else:
        me_depts = list(set(me.get("working_dept", []) + [me.get("department")]))
        me_name = me.get("name", "Unnamed")
        me_shift = me.get("shift", "?")

    employees = {
        emp_id: emp
        for emp_id, emp in employees.items()
        if emp.get("department") in me_depts
    }


    if not me:
        logging.info(f"❌ No employee matched login: {login}")
        ok = (False, f"No employee matched login: {login}", "")
    else:
        ok = can_user_add_employee(me["id"], emp_list, load_reporting_managers(),login)
        #logging.info(f"✅ Logged in as {me['name']} ({me['job_title']})")

    # --- handle empty employee list ---
    if not emp_list:
        logging.info("⚠️ No employees configured yet. Please add employees first.")
        ok = (False, f"No employee matched login: {login}", "")
        return templates.TemplateResponse("pages/help.html", {
            "request": request,
            "ok": ok,
            "me": me,
            "shifts": shifts,
            "shift_counts": shifts_counts,
            "reporting_managers": load_reporting_managers(),
            "report_map": report_map,
            "now": datetime.now(),
            "datetime": datetime
        })

    # --- optionally: enforce login match before proceeding ---
    if not me:
        return templates.TemplateResponse("pages/help.html", {
            "request": request,
            "ok": ok,
            "me": None,
            "shifts": shifts,
            "shift_counts": shifts_counts,
            "reporting_managers": load_reporting_managers(),
            "report_map": report_map,
            "now": datetime.now(),
            "datetime": datetime
        })

    # --- optionally: override with who_is_login() if needed ---
    # ok, me = who_is_login()
    # Work out Forecast Logic
    leave_codes = config_default["draw_down_codes"]
    season_start = parse_datef(config_default["season"]["start"])
    season_end = parse_datef(config_default["season"]["ends"])

    #print(f"draw_down_codes {leave_codes}")

    forecast = forecast_drawdown_minutes(rosters,leave_codes,season_start, season_end)

    #print(f"forecast == {forecast}")

    #print(f"shifts_counts = {shifts_counts} ")

    return templates.TemplateResponse("pages/calendar.html", {
        "request": request,
        "ok": ok,
        "me": me,
        "shifts": shifts,
        "shift_counts": shifts_counts,
        "employees": employees,
        "current_year": current_year,
        "current_month": current_month,
        "shiftdata": shiftdata,
        "today_str": today_str,
        "now": datetime.now(),
        "datetime": datetime,
        "config_entitlements": config_entitlements,
        "showLeave": showLeave,
        "report_map": report_map,
        "holiday_map": holiday_map
    })

def parse_datef(date_str):
    return datetime.strptime(date_str, "%d-%m-%Y")

def normalize_datef(date_str):
    parts = date_str.split("-")
    if len(parts) == 3 and len(parts[0]) == 4:  # looks like YYYY-MM-DD
        return f"{parts[2]}-{parts[1]}-{parts[0]}"  # convert to DD-MM-YYYY
    return date_str


def forecast_drawdown_minutes(rosters, leave_codes, season_start, season_end):
    forecast = defaultdict(lambda: {
        "total_minutes": 0,
        "type_shift": defaultdict(int)
    })

    # 👇 Add this block right after the function starts
    if isinstance(rosters, list):
        rosters = {"single": rosters}  # Wrap list in a dummy key

    for emp_id in rosters:
        forecast[emp_id]  # triggers defaultdict init even if no leave taken
    forecast[emp_id]["no_leave"] = True

    for emp_id, days in rosters.items():
        for day in days:
            try:
                 day_date = parse_datef(normalize_datef(day.get("date")))
            except Exception as e:
                print(f"⚠️ Bad date format: {day.get('date')} → {e}")
                continue

            if not (season_start <= day_date <= season_end):
                print(f"⏳ Skipped out-of-season: {day_date}")
                continue

            code = day.get("type_shift")
            mins = day.get("mins", 0)

            if code in leave_codes:
                #print(f"✅ Counted: {emp_id} → {code} → {mins} mins")
                forecast[emp_id]["total_minutes"] += mins
                forecast[emp_id]["type_shift"][code] += mins
                forecast[emp_id]["no_leave"] = False

    return forecast

def forecast_drawdown_minutes_d(rosters, leave_codes, season_start, season_end):
    forecast = defaultdict(lambda: {
        "total_minutes": 0,
        "type_shift": defaultdict(int)
    })

    if isinstance(rosters, list):
        rosters = {"single": rosters}

    for emp_id, days in rosters.items():
        for day in days:
            try:
                day_date = parse_datef(normalize_datef(day.get("date")))
                date_str = day_date.strftime("%d-%m-%Y")
            except Exception as e:
                print(f"⚠️ Bad date format: {day.get('date')} → {e}")
                continue

            if not (season_start <= day_date <= season_end):
                print(f"⏳ Skipped out-of-season: {day_date}")
                continue

            code = day.get("type_shift")
            mins = day.get("mins", 0)

            if code in leave_codes:
                # ✅ Add per-day entry
                if date_str not in forecast[emp_id]:
                    forecast[emp_id][date_str] = defaultdict(int)
                forecast[emp_id][date_str][code] += mins

                # ✅ Update summary
                forecast[emp_id]["total_minutes"] += mins
                forecast[emp_id]["type_shift"][code] += mins

    return forecast


@app.get("/start", response_class=HTMLResponse)
async def start(request: Request):

    updated = request.query_params.get("updated")
    # Use updated to trigger frontend message logic
    ensure_job_titles_file()
    config_default = load_json("default.json")
    #config_default_annual_entitlements_used = config_default["annual_entitlements_used"]
    config_carryover = config_default["annual_entitlements_carryover"]
    del config_carryover['_notes']
    config_entitlements = config_default["notes"]
    del config_entitlements['entitlement_unit']
    del config_entitlements['purpose']
    del config_entitlements['last_updated']
    emp_list = load_all_employees()
    reportmanager = load_reporting_managers()
    reportingto = get_active_managers(emp_list, reportmanager)
    shiftdata = load_json("shifts.json")
    import holidays
    current_year = datetime.now().year
    next_year = current_year + 1
    
    nz_holidays = holidays.country_holidays('NZ',years=[current_year, next_year],subdiv="Taranaki")

    holiday_map = {date.strftime("%Y-%m-%d"): name for date, name in nz_holidays.items()}
 
    rosters = load_all_rosters()
    config_carryover = config_default["annual_entitlements_carryover"]

    # print(f"🔍 Loaded carryover config: {config_carryover}")
    entitlements_data = calculate_entitlements(rosters, entitlement_types={"SHIFT", "SICK", "TOFF"})

    shifts_data = load_shifts()
    shifts = shifts_data.get("Shifts", [])
    today_str = datetime.now().strftime("%d %B %Y")
    # whaton = get_shift_summary_for_date(today_str,shiftdata)
    today_str = datetime.now().strftime("%Y-%m-%d")
    employees = load_all_employees()
    current_year = datetime.now().year
    current_month = datetime.now().month
    login = get_windows_login()
    emp_list = load_all_employees()
    ok, me = who_is_login()
    
    for emp_id in emp_list:
        roster_file = f"roster_{emp_id}.json"
        try:
            with open(roster_file, "r", encoding="utf-8") as f:
                rosters[emp_id] = json.load(f)
        except Exception as e:
            print(f"⚠️ Error loading {roster_file}: {e}")
            rosters[emp_id] = []


    report: dict = {}
    # Count callbacks per-employee per-day (avoid duplicates)
    callback_days: dict[str, set[date]] = defaultdict(set)
    # Track which unknown codes we've warned about to reduce spam
    warned_unknown: set[tuple[str, str]] = set()

    for emp_id, entries in rosters.items():
        emp = employees.get(emp_id, {})
        off_codes, working_codes, min_blind = get_code_sets(emp)
        # Normalize to uppercase for robust comparisons
        off_codes = {str(c).upper() for c in off_codes}
        working_codes = {str(c).upper() for c in working_codes}
        min_blind = {str(c).upper() for c in min_blind}

        season = emp.get("season", {}) or {}
        default_mins = _to_minutes(season.get("mins", 720))

        # Parse winter window with multiple formats and key spellings
        winter_start = _parse_date(season.get("winter_start"))
        winter_end = _parse_date(season.get("winter_end") or season.get("winter_ends"))
        if not winter_start or not winter_end:
            winter_start = date.min
            winter_end = date.max

        for entry in entries or []:
            date_str = entry.get("date")
            if not date_str:
                continue

            # Normalize per-entry fields
            shift_name = entry.get("shift") or "UNKNOWN"
            dept = (entry.get("department") or emp.get("department") or "Unknown")
            name = emp.get("name", emp_id)
            ts = (entry.get("type_shift") or "UNKNOWN")
            ts = str(ts).strip().upper()
            mins = _to_minutes(entry.get("mins", 0))
            try:
                entry_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except Exception:
                continue

            full_shift_mins = (
                _to_minutes(season.get("winter_mins", default_mins))
                if winter_start <= entry_date <= winter_end
                else default_mins
            )

            # Ensure report slots exist
            day_bucket = report.setdefault(date_str, {})
            shift_bucket = day_bucket.setdefault(
                shift_name,
                {
                    "departments": {},
                    "totals": {
                        "expected": 0,
                        "actual": 0,
                        "missing": 0,
                        "extra": 0,
                        "coverage": 0.0,
                    },
                    "shift_type": day_bucket.get(shift_name, {}).get("shift_type")
                    or entry.get("shift_type", "UNKNOWN"),
                },
            )

            rec = shift_bucket["departments"].setdefault(
                dept,
                {
                    "off_ids": set(),
                    "on_ids": set(),
                    "partial_ids": set(),
                    "unknown_ids": set(),
                    "expected_ids": set(),
                },
            )

            # Callback count: count once per emp per day regardless of code sets
            if ts == "CB":
                callback_days[emp_id].add(entry_date)

            # Classify (off codes count toward expected since they were scheduled but absent)
            if ts in min_blind:
                # Minute-blind working codes always count as fulfilled
                rec["expected_ids"].add(emp_id)
                rec["on_ids"].add(emp_id)
            elif ts in working_codes:
                rec["expected_ids"].add(emp_id)
                if mins >= full_shift_mins:
                    rec["on_ids"].add(emp_id)
                elif mins > 0:
                    rec["partial_ids"].add(emp_id)
                else:
                    rec["unknown_ids"].add(emp_id)
            elif ts in off_codes:
                rec["expected_ids"].add(emp_id)
                rec["off_ids"].add(emp_id)
            else:
                rec["unknown_ids"].add(emp_id)
                key = (emp_id, ts)
                if key not in warned_unknown:
                    warned_unknown.add(key)
                    #logging.info(
                    #    f"[WARN] {emp_id} {name} {date_str} type_shift={ts} not in working/off sets "
                    #    f"working={sorted(working_codes)} off={sorted(off_codes)} min_blind={sorted(min_blind)}"
                    #)

    # Aggregate per-shift totals
    for date_str, shifts in report.items():
        for shift_name, shift_data in shifts.items():
            totals = {"expected": 0, "actual": 0, "missing": 0, "extra": 0, "coverage": 0.0}

            for dept, rec in shift_data["departments"].items():
                # If someone worked (on/partial/unknown-working), don't also show them as 'off'
                worked_like = rec["on_ids"] | rec["partial_ids"] | rec["unknown_ids"]
                rec["off_ids"] -= worked_like

                expected = len(rec["expected_ids"])
                actual = len(rec["on_ids"])
                missing = max(0, expected - actual)
                extra = max(0, actual - expected)
                coverage = round((actual / expected) * 100, 1) if expected else 0.0

                def _to_names(id_set: set[str]) -> list[str]:
                    return sorted((employees.get(i, {}).get("name", i) for i in id_set), key=str.casefold)

                # Replace sets with output lists and metrics
                shift_data["departments"][dept] = {
                    "off": _to_names(rec["off_ids"]),
                    "on": _to_names(rec["on_ids"]),
                    "partial": _to_names(rec["partial_ids"]),
                    "unknown": _to_names(rec["unknown_ids"]),
                    "expected": expected,
                    "actual": actual,
                    "missing": missing,
                    "extra": extra,
                    "coverage": coverage,
                }

                # Roll up
                totals["expected"] += expected
                totals["actual"] += actual

            totals["missing"] = max(0, totals["expected"] - totals["actual"])
            totals["extra"] = max(0, totals["actual"] - totals["expected"])
            totals["coverage"] = round((totals["actual"] / totals["expected"]) * 100, 1) if totals["expected"] else 0.0
            shift_data["totals"] = totals

    # Build callbacks outputs
    callbacks_by_id = {emp_id: len(days) for emp_id, days in callback_days.items()}
    # Optional: a name-keyed view (note: duplicate names will be merged)
    callbacks_by_name: dict[str, int] = defaultdict(int)
    for emp_id, count in callbacks_by_id.items():
        nm = employees.get(emp_id, {}).get("name", emp_id)
        callbacks_by_name[nm] += count

    # Sort outputs
    report_sorted = dict(sorted(report.items()))  # dates ascending
    callbacks_name_sorted = dict(sorted(callbacks_by_name.items(), key=lambda kv: kv[0].casefold()))
    callbacks_id_sorted = dict(sorted(callbacks_by_id.items(), key=lambda kv: (-kv[1], str(kv[0]).casefold())))

    return {
        "report": report_sorted,
        "callbacks": callbacks_name_sorted,
        "callbacks_by_id": callbacks_id_sorted,
    }
    
        
@app.get("/cover_report", response_class=HTMLResponse)
async def cover_report_page(request: Request):
    ok, me = who_is_login()
    emplist = load_all_employees()
    payload = build_cover_report(emplist)

    # print(f"payload ======  {payload}")
    report = payload["report"]
    callbacks = payload["callbacks"]

    job_titles, departments = load_job_titles(strip_notes=True)

    with open(CONFIGS_DIR + "/shifts.json", "r", encoding="utf-8") as f:
        shifts = json.load(f)["Shifts"]
    # shifts = load_shifts()

    # print(f"Shifts {shifts}")

    return templates.TemplateResponse("pages/calendar_cover.html", {
        "request": request,
        "ok": ok,
        "me": me,
        "now": datetime.now(),
        "departments": departments,
        "datetime": datetime,
        "report": report,
        "callbacks": callbacks,
        "shifts": shifts
    })


from fastapi.responses import JSONResponse
from datetime import datetime
import json
from collections import defaultdict

@app.get("/cover-report")
async def cover_report_api(month: int, year: int):
    ok, me = who_is_login()
    emplist = load_all_employees()
    payload = build_cover_report(emplist)
    report = payload["report"]
    # print(f"report =  {report}")
    callbacks = payload["callbacks"]

    # Filter report by month/year
    filtered = {
        date: shifts
        for date, shifts in payload["report"].items()
        if datetime.strptime(date, "%Y-%m-%d").month == month and datetime.strptime(date, "%Y-%m-%d").year == year
    }


    # Restructure into nested dict: date → shift → report
    nested = defaultdict(dict)
    for date, shifts in report.items():
        for shift, r in shifts.items():
            nested[date][shift] = r


    # Convert defaultdict to regular dict for JSON serialization
    report_by_day = {date: dict(shifts) for date, shifts in nested.items()}

    # Load shift config
    #with open(CONFIGS_DIR + "/shifts.json", "r", encoding="utf-8") as f:
    #    shifts = json.load(f)["Shifts"]
    
    shifts = load_shifts()
    
    
    # Extract departments from employee entries
    departments = sorted({
        emp.get("department", "Unknown")
        for shifts in filtered.values()
        for r in shifts.values()
        for emp in r.get("employees", [])
    })


    return JSONResponse({
        "ok": ok,
        "me": me,
        "now": datetime.now().isoformat(),
        "report": report_by_day,  # ✅ fully serializable nested dict
        "shifts": shifts,
        "callbacks": callbacks,
        "departments": departments
    })


from fastapi.responses import JSONResponse
from datetime import datetime
import traceback

@app.get("/calendar-data")
def calendar_data(emp_id: str, shift: str = "", month: int = None, year: int = None):
    #print(f"Fetching calendar data for emp_id={emp_id}, shift={shift}, month={month}, year={year}")
    try:
        # Rebuild holiday_map
        current_year = datetime.now().year
        next_year = current_year + 1
        config_default = load_json("default.json")
        import holidays
        nz_holidays = holidays.country_holidays(
            "NZ",
            years=[current_year, next_year],
            subdiv=config_default.get("public_holidays", "Taranaki")
        )
        holiday_map = {date.strftime("%Y-%m-%d"): name for date, name in nz_holidays.items()}

        # Build calendar entries
        roster = load_roster_for_employee(emp_id, month, year)
        entries = build_calendar_entries(roster, shift=shift, month=month, year=year, holiday_map=holiday_map)

        leave_data = load_json("leave.json").get("LeaveRequests", [])
        month_str = str(month).zfill(2)

        leave_entries = [
            entry for entry in leave_data
            if entry.get("emp_id") == emp_id and entry.get("date", "").startswith(f"{year}-{month_str}")
        ]




        # Load config and forecast logic
        #emp_roster = load_json(f"roster_{emp_id}.json")
        emp_roster = load_roster_this_season(emp_id)
        config_emp = load_json(f"emp_{emp_id}.json")
        leave_codes = config_emp.get("draw_down_codes", [])
        if "PSL" not in leave_codes:
            leave_codes.append("PSL")

        season_config = config_emp.get("season", {})
        winter_mins = int(season_config.get("winter_mins") or 600)
        season_mins = int(season_config.get("mins") or 720)

        season_start = parse_datef(season_config.get("start"))
        season_end = parse_datef(season_config.get("ends"))

        forecast = forecast_drawdown_minutes({emp_id: emp_roster}, leave_codes, season_start, season_end)
        #print(f"Forecast for {emp_id}: {forecast}")
        entitlements = config_emp.get("annual_entitlements_carryover", {})
        if not entitlements:
            print(f"⚠️ No entitlements found for {emp_id}")

        pacing = compare_to_entitlement(forecast, entitlements)
        PSL = pacing.get(emp_id, {}).get("PSL", {})
        #print(f"PSL pacing for {emp_id}: {PSL}")
        pacing.get(emp_id, {}).pop("PSL", None)

        # Filter pacing to only include approved leave codes
        pacing[emp_id] = {
            code: info
            for code, info in pacing.get(emp_id, {}).items()
            if code in leave_codes
        }

        return {
            "entries": entries,
            "leave_entries": leave_entries,
            "winter_mins": winter_mins,
            "season_mins": season_mins,
            "pacing": pacing,
            "PSL": PSL
        }

    except Exception as e:
        print("🔥 Error in /calendar-data:\n", traceback.format_exc())
        return JSONResponse(content={"error": "Internal error"}, status_code=500)
    
#=============================================================================

def compare_to_entitlement(forecast, entitlements):
    pacing = {}
    
    for emp_id in forecast:
        pacing[emp_id] = {}
        
        for code, entitled_mins in entitlements.items():
            # Skip non-numeric or zero entitlements
            if not isinstance(entitled_mins, (int, float)) or entitled_mins <= 0:
                continue

            used_mins = forecast[emp_id]["type_shift"].get(code, 0)

            percent_used = round((used_mins / entitled_mins) * 100, 2)

            status = (
                "✅ Ahead" if percent_used < 80 else
                "⚠️ Close" if percent_used < 100 else
                "❌ Overdrawn"
            )

            pacing[emp_id][code] = {
                "used": used_mins,
                "entitled": entitled_mins,
                "percent_used": percent_used,
                "status": status
            }

    return pacing


def build_calendar_entries(roster, shift="", month=None, year=None, holiday_map=None):
    from calendar import monthrange
    #print(f"roster {roster}")
    entries = []
    for entry in roster:
        date_str = entry.get("date")
        if not date_str:
            continue
        try:
            entry_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except Exception:
            continue
        if entry_date.month != month or entry_date.year != year:
            continue
        if shift and entry.get("shift") != shift:
            continue

        entry_data = {
            "date": date_str,
            "type_shift": entry.get("type_shift", "UNKNOWN"),
            "shift_type": entry.get("shift_type", "UNKNOWN"),
            "shift_minutes": entry.get("shift_minutes", 0),
            "notes": entry.get("notes", ""),
            "has_data": True,
        }

        if holiday_map and date_str in holiday_map:
            entry_data["is_holiday"] = True
            entry_data["holiday_name"] = holiday_map[date_str]
        else:
            entry_data["is_holiday"] = False
            entry_data["holiday_name"] = ""

        entries.append(entry_data)

    return entries

# =========================================
@app.get("/shifts", response_class=HTMLResponse)
async def show_shifts(request: Request):
    ok, me = who_is_login()
    shifts_data = load_shifts()
    emp = load_all_employees()
    shifts = shifts_data.get("Shifts", [])
    #print(f"emp {emp}")
    #print(f"shifts {shifts}")
    shift_counts = Counter(e["shift"] for e in emp.values())
    for s in shifts:
        s["count"] = shift_counts.get(s["name"], 0)

    #print(f"shift = {shifts}")

    # FIXED: Build shift_today dict from each shift
    shift_today = {shift['name']: get_shift_today_data(shift) for shift in shifts}
    #print(f"shift_today {shift_today}")
    #print(f"shifts {shifts}")
    return templates.TemplateResponse("pages/shifts.html", {
        "request": request,
        "ok": ok,
        "me": me,
        "shifts": shifts,
        "now": datetime.now(),
        "datetime": datetime,
        "shift_today": shift_today
    })



def convert_to_iso_date(date_str):
    try:
        dt = datetime.strptime(date_str, "%d %B %Y")
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return ""  # fallback or empty string if parsing fails

from fastapi import HTTPException


def convert_to_iso_date(first_str: str) -> str:
    """Convert 'DD MMM YYYY' to 'YYYY-MM-DD' for <input type=date>."""
    try:
        dt = datetime.strptime(first_str, "%d %b %Y")
        return dt.strftime("%Y-%m-%d")
    except:
        return ""

from fastapi import Request, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from urllib.parse import quote
from dateutil.parser import parse
from datetime import datetime

@app.api_route("/shifts/edit/{shift_name}", methods=["GET", "POST"], response_class=HTMLResponse)
async def edit_shift(request: Request, shift_name: str):
    shift_name = shift_name.strip()
    shifts_data = load_shifts()
    shifts = shifts_data.get("Shifts", [])
    shift = next((s for s in shifts if s["name"] == shift_name), None)

    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")

    if request.method == "POST":
        form = await request.form()
        shift["name"] = form.get("name")

        # Parse the date safely
        try:
            dt = parse(form.get("first"))
            shift["first"] = dt.strftime("%d %b %Y")  # store as 'DD MMM YYYY'
        except Exception:
            shift["first"] = form.get("first")  # fallback to raw string

        shift["roster_pattern"] = form.get("roster_pattern")
        shift["shift_sequence"] = form.get("shift_sequence")

        save_json("shifts.json", shifts_data)
        return RedirectResponse("/shifts", status_code=303)

    # GET request: convert first date to ISO format for the form
    try:
        dt = parse(shift["first"])
        shift["first_iso"] = dt.strftime("%Y-%m-%d")
    except Exception:
        shift["first_iso"] = ""  # leave blank if parsing fails

    ok, me = who_is_login()
    action_url = f"/shifts/edit/{quote(shift_name)}"

    return templates.TemplateResponse("pages/shift_form.html", {
        "request": request,
        "ok": ok,
        "me": me,
        "action_url": action_url,
        "shift": shift,
        "now": datetime.now(),
        "datetime": datetime
    })


@app.get("/shifts/new", response_class=HTMLResponse)
async def edit_shift(request: Request, index: Optional[int] = None):
    shifts = load_shifts().get("Shifts", [])

    if index is not None and 0 <= index < len(shifts):
        shift = shifts[index]
        shift["first_iso"] = convert_to_iso_date(shift["first"])
    else:
        shift = None

    ok, me = who_is_login()

    return templates.TemplateResponse("pages/shift_form.html", {
        "request": request,
        "ok": ok,
        "me": me,
        "now": datetime.now(),
        "datetime": datetime,
        "shift": shift,
        "index": index
    })

@app.post("/shifts/new", response_class=HTMLResponse)
async def save_new_shift(
    request: Request,
    name: str = Form(...),
    first: str = Form(...),  # expects 'YYYY-MM-DD' from HTML date input
    roster_pattern: str = Form(...),
    shift_sequence: str = Form(...),
):
    # Convert first date to dd MMM YYYY
    try:
        dt = datetime.strptime(first, "%Y-%m-%d")
        first_formatted = dt.strftime("%d %b %Y")
    except ValueError:
        first_formatted = first  # fallback if parsing fails

    # Load current shifts
    shifts_data = load_shifts()
    shifts = shifts_data.get("Shifts", [])

    # Create new shift with formatted date
    new_shift = {
        "name": name,
        "first": first_formatted,
        "roster_pattern": roster_pattern,
        "shift_sequence": shift_sequence
    }

    shifts.append(new_shift)
    shifts_data["Shifts"] = shifts
    save_json("shifts.json", shifts_data)

    # Redirect back to /shifts page
    return RedirectResponse("/shifts", status_code=303)





@app.post("/shifts/reorder")
async def reorder_shifts(request: Request):
    new_order = await request.json()
    
    shifts_data = load_shifts()  # your existing function
    shifts = shifts_data.get("Shifts", [])
    shifts_lookup = {s["name"]: s for s in shifts}
    reordered = [shifts_lookup[name] for name in new_order if name in shifts_lookup]
    for s in shifts:
        if s["name"] not in new_order:
            reordered.append(s)
    shifts_data["Shifts"] = reordered
    save_json("shifts.json", shifts_data)

    return JSONResponse({"status": "ok", "new_order": new_order})


def get_shift_today_data(shift):
    shift_sequence = shift.get('shift_sequence', '')
    first_str = shift.get('first', '')

    # Try to parse the date safely
    try:
        first_date = parse(first_str).date()
    except Exception:
        return {"cycle_text": "Invalid date", "label": "⚠ Error parsing date"}

    today = datetime.today().date()
    days_since_first = (today - first_date).days

    if days_since_first < 0:
        return {
            "cycle_text": f"Starts in {-days_since_first} days",
            "label": "⏳ Not Started"
        }

    cycle_length = len(shift_sequence)
    if cycle_length == 0:
        return {"cycle_text": "Empty sequence", "label": "⚠ No schedule"}

    index_today = days_since_first % cycle_length
    symbol = shift_sequence[index_today]

    label_map = {
        'D': '🟢 On Duty (Day)',
        'N': '🌙 On Duty (Night)',
        '*': '🔴 Rest Day'
    }
    label = label_map.get(symbol, f"⚠ Unknown ({symbol})")

    return {
        "cycle_text": f"Day {index_today + 1} of {cycle_length}",
        "label": label
    }
#======================================================================
from fastapi.responses import JSONResponse
from datetime import datetime
from calendar import month_name
import traceback

@app.get("/pacing-trend")
def pacing_trend(emp_id: str):
    try:
        #emp_roster = load_json(f"roster_{emp_id}.json")
        emp_roster = load_roster_this_season(emp_id)
        config_emp = load_json(f"emp_{emp_id}.json")
        leave_codes = config_emp.get("draw_down_codes", [])
        entitlements = config_emp.get("annual_entitlements_carryover", {})

        season_config = config_emp.get("season", {})
        season_start = parse_datef(season_config.get("start"))
        season_end = parse_datef(season_config.get("ends"))
        season_mins = int(season_config.get("mins") or 720)

        forecast = forecast_drawdown_minutes_d({emp_id: emp_roster}, leave_codes, season_start, season_end)
        print(f" forecast={forecast}")
        monthly_pacing = {}
        skipped_keys = []

        for date_str, usage in forecast.get(emp_id, {}).items():
            if date_str == "total_minutes":
                continue

            try:
                date = parse_datef(date_str)
            except ValueError:
                skipped_keys.append(date_str)
                continue

            month_label = date.strftime("%B")
            monthly_pacing.setdefault(month_label, {"used": 0, "entitled": 0})

            for code, mins in usage.items():
                monthly_pacing[month_label]["used"] += mins
                monthly_pacing[month_label]["entitled"] += entitlements.get(code, 0)

        # Add pacing status
        for month, data in monthly_pacing.items():
            used = data["used"]
            entitled = data["entitled"]
            remaining = entitled - used
            if remaining >= 120:
                status = "✅ Ahead"
            elif remaining >= 0:
                status = "⚠️ Close"
            else:
                status = "❌ Overdrawn"
            data["status"] = status

        # Sort months chronologically
        sorted_months = sorted(
            monthly_pacing.items(),
            key=lambda item: list(month_name).index(item[0])
        )

        # Build summary
        summary = {
            "total_used": sum(data["used"] for data in monthly_pacing.values()),
            "total_entitled": sum(data["entitled"] for data in monthly_pacing.values())
        }

        return {
            "monthly_pacing": dict(sorted_months),
            "season_mins": season_mins,
            "summary": summary,
            "type_shift": dict(forecast[emp_id]["type_shift"]),
            "skipped_keys": skipped_keys
        }

    except Exception as e:
        print("🔥 Error in /pacing-trend:\n", traceback.format_exc())
        return JSONResponse(content={"error": "Internal error"}, status_code=500)
    



@app.get("/load-pacing-trend")
def show_trend_page(request: Request):
    ok, me = who_is_login()
    season_mins = 1000
    emp_id = 541895
    return templates.TemplateResponse("pages/loadPacingTrend.html", {
        "request": request,
        "emp_id": emp_id,
        "season_mins": season_mins, 
        "ok": ok,
        "me": me,
        "now": datetime.now(),
        "datetime": datetime,
        })


from calendar import monthrange
from datetime import date, timedelta



def get_calendar_days(year, month):
    first_day = date(year, month, 1)
    weekday_offset = (first_day.weekday() + 1) % 7  # Sunday = 0

    days = []
    for i in range(31):
        try:
            current = first_day + timedelta(days=i)
            if current.month != month:
                break
            days.append({
                "date": current.strftime("%Y-%m-%d"),
                "day": current.day,
                "weekday": current.strftime("%A")
            })
        except:
            break
    return days, weekday_offset



@app.get("/request-leave", response_class=HTMLResponse)
async def request_leave(request: Request, month: int = None, year: int = None, emp_id: str = None):

    now = datetime.now()
    selected_month = month if month else now.month
    selected_year = year if year else now.year
    #print(f"empid = {emp_id} month = {selected_month} year = {selected_year}")

    ok, me = who_is_login()
    roster = load_roster_for_employee(emp_id, month=selected_month, year=selected_year)
    roster_map = {entry["date"]: entry for entry in roster}
    calendar_days, weekday_offset = get_calendar_days(selected_year, selected_month)


    my_Leave = load_json("leave.json")

    valid_statuses = {"pending", "covered"} #, "covered"
    leave_requests = [
        entry for entry in my_Leave.get("LeaveRequests", [])
        if entry.get("emp_id") == emp_id and entry.get("coverage_status") in valid_statuses
    ]

    
    config_emp = load_json(f"emp_{emp_id}.json")
    emp_name = config_emp.get("emp_name", "Unknown")

    leave_types = config_emp.get("draw_down_codes", [])  # e.g. ['ADT', 'LSL', 'PAL']
    entitlements = config_emp.get("annual_entitlements_carryover", {})  # e.g. {'ADT': 2880, 'LSL': 4320, 'PAL': 1440}

    roster_season = config_emp.get("season", {})
    season_start = parse_datef(roster_season.get("start")).date()
    season_end = parse_datef(roster_season.get("ends")).date()


    #roster_data_everything = load_json(f"roster_{emp_id}.json")
    roster_data_everything = load_roster_this_season(emp_id)
    def normalize_datef(date_str):
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except Exception as e:
            print(f"⚠️ Failed to normalize date: {date_str} → {e}")
            return None

    roster_in_season = []
    for entry in roster_data_everything:
        entry_date = normalize_datef(entry.get("date"))
        if entry_date and season_start <= entry_date <= season_end:
            roster_in_season.append(entry)

    used_minutes = defaultdict(int)
    for day in roster_in_season:
        code = (day.get("type_shift") or "").strip().upper()
        mins = day.get("shift_minutes") or day.get("mins") or 0
        if code in leave_types:
            used_minutes[code] += mins

    drawdown_summary = {}
    for code in leave_types:
        entitled = entitlements.get(code, 0)
        used = used_minutes.get(code, 0)
        drawdown_summary[code] = {
            "entitled": entitled,
            "used": used,
            "remaining": entitled - used
        }
        
    return templates.TemplateResponse("pages/request-leave.html", {
        "request": request,
        "emp_id": emp_id,
        "shift": config_emp.get("shift_name", ""),        
        "leave_requests": leave_requests,
        "emp_name": emp_name,
        "drawdown_summary": drawdown_summary,
        "weekday_offset": weekday_offset,
        "roster": roster,
        "roster_map": roster_map,
        "calendar_days": calendar_days,
        "leave_types": leave_types,
        "datetime": datetime,
        "now": now,
        "month": selected_month,
        "year": selected_year,
        "ok": ok,
        "me": me
    })


@app.post("/submit-leave")
async def submit_leave(requests: str = Form(...)):
    try:
        entries = json.loads(requests)
    except Exception as e:
        return HTMLResponse(f"❌ Failed to parse leave requests: {e}", status_code=400)

    try:
        data = load_json("leave.json")
    except FileNotFoundError:
        data = {"LeaveRequests": []}
    print(f"Submitting leave entries: {entries}")
    for entry in entries:
        leave_entry = {
            "ID": str(uuid4()),
            "emp_id": entry.get("emp_id"),
            "date": entry.get("date"),
            "shift_name": entry.get("shift_name"),
            "shift_type": entry.get("shift_type"),  # e.g. Day/Night
            "type_shift": entry.get("type_shift"),  # e.g. ADT/LSL/PAL
            "status": "requested",
            "notes": entry.get("notes", ""),
            "shift_minutes": entry.get("shift_minutes", 0),
            "cover_by": [],
            "decline_by":[],
            "manager_id": None,
            "decision_timestamp": None,
            "coverage_status": "pending"
        }
        data["LeaveRequests"].append(leave_entry)

    save_json("leave.json", data)
    return RedirectResponse(url=f"/suggest-covers?emp_id={entry.get('emp_id')}&backto=calendar&sourse=leave", status_code=303)

@app.get("/suggest-covers", response_class=HTMLResponse)
def suggest_covers_screen(emp_id: str, sourse: str, request: Request):
    ok, me = who_is_login()

    all_emp_ids = load_all_employees()
    emp_data = all_emp_ids.get(emp_id, {})
    department = emp_data.get("department", "Unknown")
    emp_name = emp_data.get("name", "Unknown")
    shift_cover = emp_data.get("shift_name", "Unknown")
    backto = request.query_params.get("backto")

    leave_data = load_json("leave.json").get("LeaveRequests", [])
    sick_data = load_json("sick.json")
    shift_configs = load_json("shifts.json")

    suggestions_by_date = {}
    all_leave_for_emp = []
    all_sick_for_emp = []

    def enrich_suggestions(date, shift_type):
        raw_suggestions = get_suggested_covers(
            all_emp_ids,
            date,
            exclude_emp=emp_id,
            department=department,
            shift_type=shift_type
        )
        enriched = []
        for cover_id, name, preferred_shift in raw_suggestions:
            off_day_count = count_consecutive_off_days(cover_id, date, shift_configs, all_emp_ids)
            enriched.append((cover_id, name, preferred_shift, off_day_count))
        return sorted(enriched, key=lambda x: (x[2] == shift_type, x[3], x[1]), reverse=True)

    for entry in leave_data:
        if entry.get("emp_id") == emp_id and entry.get("coverage_status") == "pending":
            decliners = entry.get("decline_by", [])
            if not isinstance(decliners, list):
                decliners = [str(decliners)] if decliners else []
            entry["decline_by"] = decliners
            all_leave_for_emp.append(entry)

            date = entry["date"]
            shift_type = entry.get("shift_type", "")
            shift_name = entry.get("shift_name")

            suggestions = enrich_suggestions(date, shift_type)

            suggestions_by_date[date] = {
                "source": "leave",
                "shift_type": shift_type,
                "shift_cover": shift_name,
                "suggestions": suggestions,
                "decline_by": decliners
            }

    for entry in sick_data:
        if entry.get("emp_id") == emp_id and entry.get("status") == "pending":
            all_sick_for_emp.append(entry)

            date = entry["date"]
            shift_type = entry.get("shift_type", "")
            shift_name = entry.get("shift_name")

            suggestions = enrich_suggestions(date, shift_type)

            suggestions_by_date[date] = {
                "source": "sick",
                "shift_type": shift_type,
                "shift_cover": shift_name,
                "suggestions": suggestions,
                "decline_by": []
            }

    return templates.TemplateResponse("pages/suggest_covers.html", {
        "request": request,
        "emp_id": emp_id,
        "emp_name": emp_name,
        "shift_cover": shift_cover,
        "ok": ok,
        "me": me,
        "now": datetime.now(),
        "all_leave_for_emp": all_leave_for_emp,
        "all_sick_for_emp": all_sick_for_emp,
        "suggestions_by_date": suggestions_by_date,
        "backto": backto,
        "datetime": datetime
    })


def count_consecutive_off_days(emp_id, date_str, shift_configs, all_emp_ids):
    target_date = datetime.strptime(date_str, "%Y-%m-%d").date()

    shift_name = all_emp_ids.get(emp_id, {}).get("shift")
    #print(f"shift_name ={shift_name}")
    # Find the shift config for this employee
    shift_config = next((s for s in shift_configs["Shifts"] if s["name"] == shift_name), None)
    if not shift_config:
        return 0
    #print(f"shift_config =  {shift_config}")
    sequence = shift_config["shift_sequence"]
    cycle_len = len(sequence)
    #start_date = datetime.strptime(shift_config["first"], "%d %B %Y").date()
    try:
        start_date = datetime.strptime(shift_config["first"], "%d %B %Y").date()
    except ValueError:
        start_date = datetime.strptime(shift_config["first"], "%d %b %Y").date()


    days_since_start = (target_date - start_date).days
    if days_since_start < 0:
        return 0  # hasn't started yet

    # Work backwards through the sequence
    count = 0
    for i in range(0, cycle_len):
        pos = (days_since_start - i) % cycle_len
        if sequence[pos] == "*":
            count += 1
        else:
            break

    return count

def ordinal(n):
    return f"{n}{'st' if n == 1 else 'nd' if n == 2 else 'rd' if n == 3 else 'th'}"



@app.get("/incoming-cover-requests")
def incoming_cover_requests(emp_id: str):
    all_emp_ids = load_all_employees()
    my_Leave = load_json("leave.json")
    shift_configs = load_json("shifts.json")
    #print(f"/incoming-cover-requests {emp_id}")
    incoming = []
    
    for entry in my_Leave.get("LeaveRequests", []):
        if entry.get("coverage_status") != "pending":
            continue

        decliners = entry.get("decline_by", [])
        if not isinstance(decliners, list):
            decliners = [decliners] if decliners else []
        decliners = [str(d) for d in decliners]  # 👈 normalize to strings

        if emp_id in decliners:
            continue

        requester_id = entry.get("emp_id")
        if requester_id == emp_id:
            continue  # skip self

        shift_type = entry.get("shift_type", "")
        date = entry.get("date")
        shift_name = entry.get("shift_name")

        suggestions = get_suggested_covers(
            all_emp_ids,
            date,
            exclude_emp=requester_id,
            department=all_emp_ids.get(requester_id, {}).get("department", ""),
            shift_type=shift_type
        )
        # print(f"decliners = {decliners}")

        off_day_count = count_consecutive_off_days(emp_id, date, shift_configs, all_emp_ids)
        off_day_label = f"{ordinal(off_day_count)} day off" if off_day_count else "Working day"
        dt = datetime.strptime(date, "%Y-%m-%d")
        day_name = dt.strftime("%A")
        for name, score, preferred_shift in suggestions:
            if name == emp_id:
                incoming.append({
                    "date": date,
                    "shift_type": shift_type,
                    "requested_by": requester_id,
                    "requested_name": all_emp_ids.get(requester_id, {}).get("name", requester_id),
                    "score": score,
                    "cover_by": emp_id,
                    "shift_name": shift_name,
                    "decline_by": decliners,
                    "day_name": day_name,
                    "preferred_shift": preferred_shift,
                    "off_day_count": off_day_count,
                    "off_day_label": off_day_label

                })
                # break

    return {"incoming_requests": incoming}







@app.post("/request-cover")
async def request_cover(
    request: Request,
    source: str = Form("leave"),
    type_shift: str = Form(None),
    shift_name: str = Form(None),
    shift_type: str = Form(None),
    manager_id: str = Form(None),
    backto: str = Form(None),
    date: str = Form(...),
    cover_by: str = Form(None),
    emp_id: str = Form(...),
    shift_cover: str = Form(None),
    coverage_status: str = Form(...)
):
    import ast
    import holidays

    form_data = await request.form()
    popup_mode = form_data.get("Popup") == "1"
    print("Form payload:", dict(form_data))

    # Parse cover_by safely
    if isinstance(cover_by, str):
        try:
            if cover_by.startswith('"') and cover_by.endswith('"'):
                cover_by = cover_by[1:-1]
            cover_by = ast.literal_eval(cover_by)
        except Exception as e:
            print("Failed to parse cover_by:", e)
            cover_by = [cover_by]

    if not isinstance(cover_by, list):
        cover_by = [cover_by]

    # Cover note
    if cover_by and cover_by[0]:
        cover_emp = load_employee_config(cover_by[0])
        cover_by_name = "Cover by " + cover_emp.get("emp_name", "Unknown")
    else:
        cover_by_name = "Approved by Manager No Cover REQ"

    # Load correct dataset
    data_file = "sick.json" if source == "sick" else "leave.json"
    data = load_json(data_file)

    # Find matching entries
    if source == "leave":
        matching_entries = [
            entry for entry in data.get("LeaveRequests", [])
            if entry.get("emp_id") == emp_id and entry.get("date") == date
        ]
    else:
        matching_entries = [
            entry for entry in data
            if entry.get("emp_id") == emp_id and entry.get("date") == date
        ]

    if not matching_entries:
        print(f"No matching entries found for {emp_id} on {date}")
        return RedirectResponse(url=f"/suggest-covers?emp_id={emp_id}&sourse={source}", status_code=303)

    # Update entries
    updated = False
    for entry in matching_entries:
        entry["cover_by"] = cover_by

        if coverage_status.lower() == "decline":
            entry["coverage_status"] = "pending"
            existing_declines = entry.get("decline_by", [])
            if not isinstance(existing_declines, list):
                existing_declines = [existing_declines] if existing_declines else []
            for cid in cover_by:
                if cid not in existing_declines:
                    existing_declines.append(cid)
            entry["decline_by"] = existing_declines
            entry["cover_by"] = []
        else:
            entry["coverage_status"] = coverage_status

        if manager_id:
            entry["manager_id"] = manager_id
            entry["decision_timestamp"] = datetime.now().isoformat()
            entry["status"] = "Approved"

        updated = True

    # Manager logic
    if manager_id:
        print(">>>>>>>>> doing Manager Stuff")

        emp_config = load_employee_config(emp_id)
        public_holidays = emp_config.get("public_holidays")
        current_year = datetime.now().year

        nz_holidays = holidays.NewZealand(
            years=[current_year, current_year + 1],
            subdiv=public_holidays if public_holidays else None
        )

        shift_type = matching_entries[0].get("shift_type")
        shift_name = matching_entries[0].get("shift_name")
        coverage_note = "Covering " + emp_config.get("emp_name", "Unknown")
        leave_dt = datetime.strptime(date, "%Y-%m-%d")

        # Coverer gets one roster entry
        if cover_by and cover_by[0]:
            for cid in cover_by:
                cover_emp_config = load_employee_config(cid)
                season = cover_emp_config.get("season", {})
                default_mins = season.get("mins", 0)
                winter_mins = season.get("winter_mins", 0)

                winter_start = season.get("winter_start")
                winter_ends = season.get("winter_ends")

                is_winter = False
                if winter_start and winter_ends:
                    try:
                        start_dt = datetime.strptime(winter_start, "%d-%m-%Y")
                        end_dt = datetime.strptime(winter_ends, "%d-%m-%Y")
                        is_winter = start_dt <= leave_dt <= end_dt
                    except Exception as e:
                        print("Winter date parse failed:", e)

                cover_minutes = winter_mins if is_winter else default_mins
                if not cover_minutes:
                    cover_minutes = 480  # fallback default

                cover_roster = load_json(f"roster_{cid}.json")
                cover_roster.append({
                    "ID": str(uuid4()),
                    "date": date,
                    "shift": shift_name,
                    "day": leave_dt.strftime("%A"),
                    "holidays": nz_holidays.get(date) or "-",
                    "shift_type": shift_type,
                    "type_shift": "CB",
                    "on_shift": True,
                    "mins": cover_minutes,
                    "callback_eligible": True,
                    "cover_allowed": True,
                    "notes": coverage_note
                })
                save_json(f"roster_{cid}.json", cover_roster)
                print(f"Assigned {cover_minutes} mins to coverer {cid} on {date} (winter: {is_winter})")

        # Leave-taker gets one or more entries
        roster = load_json(f"roster_{emp_id}.json")
        roster = [r for r in roster if r.get("date") != date]

        default_config = load_json("default.json")
        maths_map = default_config.get("Maths", {})

        if not maths_map:
            print("⚠️ Maths map is empty in default.json")
            maths_map = {
                "PSL": "PSL=480 PNW=240",
                "BVT": "BVT=480 PNW=240",
                "PPL": "PPL=480 PNW=240"
            }
            default_config["Maths"] = maths_map  # ← append it back into the config
            save_json("default.json", default_config)


        for entry in matching_entries:
            leave_dt = datetime.strptime(entry["date"], "%Y-%m-%d")
            type_shift = entry.get("type_shift")
            raw_formula = maths_map.get(type_shift)
            is_winter = False

            season = emp_config.get("season", {})
            winter_start = season.get("winter_start")
            winter_ends = season.get("winter_ends")

            if winter_start and winter_ends:
                start_dt = datetime.strptime(winter_start, "%d-%m-%Y")
                end_dt = datetime.strptime(winter_ends, "%d-%m-%Y")
                is_winter = start_dt <= leave_dt <= end_dt

            notes_raw = entry.get("notes", "").strip()
            combined_notes = f"{cover_by_name} — {notes_raw}" if notes_raw else cover_by_name

            if source == "sick" and raw_formula:
                parts = raw_formula.split()
                for part in parts:
                    label, mins = part.split("=")
                    mins = int(mins)
                    if is_winter and label == "PNW":
                        mins = 120
                    roster.append({
                        "ID": str(uuid4()),
                        "date": entry["date"],
                        "shift": entry["shift_name"],
                        "day": leave_dt.strftime("%A"),
                        "holidays": "-",
                        "shift_type": entry["shift_type"],
                        "type_shift": label,
                        "mins": mins,
                        "callback_eligible": True,
                        "cover_allowed": False,
                        "on_shift": False,
                        "notes": combined_notes
                    })
            else:
                roster.append({
                    "ID": str(uuid4()),
                    "date": entry["date"],
                    "shift": entry["shift_name"],
                    "day": leave_dt.strftime("%A"),
                    "holidays": "-",
                    "shift_type": entry["shift_type"],
                    "type_shift": entry["type_shift"],
                    "mins": entry["shift_minutes"],
                    "callback_eligible": True,
                    "cover_allowed": False,
                    "on_shift": False,
                    "notes": combined_notes
                })

        save_json(f"roster_{emp_id}.json", roster)

        for entry in matching_entries:
            entry["cover_by"] = cover_by
            entry["coverage_status"] = "covered"
            entry["manager_id"] = manager_id
            entry["decision_timestamp"] = datetime.now().isoformat()

        save_json(data_file, data)

        with open("deleted.log", "a", encoding="utf-8") as log:
            cover_log = f"by {', '.join(map(str, cover_by))}" if cover_by and cover_by[0] else "by Manager Only"
            log.write(f"{datetime.now().isoformat()} COVERED: {emp_id} on {date} {cover_log}\n")

    if updated:
        print(f"Updated entries for {emp_id} on {date}")
        save_json(data_file, data)

    if popup_mode:
        return JSONResponse({"status": "ok"})
    else:
        redirect_url = "/manager-covers" if manager_id else f"/suggest-covers?emp_id={emp_id}&sourse={source}"
        return RedirectResponse(url=backto, status_code=303)



        
from collections import defaultdict

@app.get("/manager-covers")
def manager_covers_screen(request: Request):
    ok, me = who_is_login()
    if me.get("job_title") not in ["Manager", "L8"]:
        return HTMLResponse("❌ Access denied", status_code=403)

    all_emp_ids = load_all_employees()
    leave_data = load_json("leave.json")
    sick_data = load_json("sick.json")
    default_config = load_json("default.json")
    maths_map = default_config.get("Maths", {})

    if not maths_map:
        print("⚠️ Maths map is empty in default.json")
        maths_map = {
            "PSL": "PSL=480 PNW=240",
            "BVT": "BVT=480 PNW=240",
            "PPL": "PPL=480 PNW=240"
        }
        default_config["Maths"] = maths_map  # ← append it back into the config
        save_json("default.json", default_config)
        
    grouped_raw = defaultdict(list)

    def apply_winter_maths(entry):
        emp_id = entry.get("emp_id")
        emp_info = all_emp_ids.get(str(emp_id), {})
        season = emp_info.get("season", {})
        winter_start = season.get("winter_start")
        winter_ends = season.get("winter_ends")
        winter_mins = season.get("winter_mins", 600)

        leave_date = entry.get("date")
        leave_dt = datetime.strptime(leave_date, "%Y-%m-%d") if leave_date else None

        is_winter = False
        if winter_start and winter_ends and leave_dt:
            start_dt = datetime.strptime(winter_start, "%d-%m-%Y")
            end_dt = datetime.strptime(winter_ends, "%d-%m-%Y")
            is_winter = start_dt <= leave_dt <= end_dt

        raw_formula = maths_map.get(entry.get("type_shift"))
        if raw_formula and is_winter:
            parts = raw_formula.split()
            adjusted = []
            for part in parts:
                label, mins = part.split("=")
                if label == "PNW":
                    adjusted.append(f"{label}=120")  # override for winter
                else:
                    adjusted.append(part)
            formula = " ".join(adjusted)
        elif raw_formula:
            formula = raw_formula
        else:
            formula = entry.get("type_shift")

        entry["type_expanded"] = formula
        entry["winter_applied"] = is_winter

        # Recalculate shift_minutes from formula
        if "=" in formula:
            total = 0
            for part in formula.split():
                label, mins = part.split("=")
                total += int(mins)
            entry["shift_minutes"] = total

    # Tag and group leave entries
    for entry in leave_data.get("LeaveRequests", []):
        if entry.get("coverage_status") in ["pending", "covered"] and entry.get("status") != "Approved":
            entry["source_file"] = "leave"
            apply_winter_maths(entry)
            key = (entry.get("emp_id"), entry.get("date"))
            grouped_raw[key].append(entry)

    # Tag and group sick entries
    for entry in sick_data:
        if entry.get("status") in ["pending", "covered"]:
            entry["source_file"] = "sick"
            apply_winter_maths(entry)
            key = (entry.get("emp_id"), entry.get("date"))
            grouped_raw[key].append(entry)

    grouped_pending = defaultdict(list)

    for (emp_id, date), entries in grouped_raw.items():
        total_minutes = sum(e.get("shift_minutes", 0) for e in entries if "shift_minutes" in e)
        shift_name = entries[0].get("shift_name")
        shift_type = entries[0].get("shift_type")
        cover_ids = entries[0].get("cover_by", entries[0].get("cover_id", []))

        if not isinstance(cover_ids, list):
            cover_ids = [cover_ids] if cover_ids else []

        cover_names = [
            all_emp_ids.get(str(cid), {}).get("name", f"Unknown ({cid})")
            for cid in cover_ids
        ]

        types_used = [e.get("type_shift", "Unknown") for e in entries]
        types_expanded = [e.get("type_expanded", "Unknown") for e in entries]

        grouped_pending[emp_id].append({
            "date": date,
            "shift_name": shift_name,
            "shift_type": shift_type,
            "total_minutes": total_minutes,
            "types_used": types_used,
            "types_expanded": types_expanded,
            "cover_by": cover_ids,
            "cover_names": cover_names,
            "entries": entries
        })

    return templates.TemplateResponse("pages/manager_suggest_covers.html", {
        "request": request,
        "me": me,
        "ok": ok,
        "grouped_pending": grouped_pending,
        "all_emp_ids": all_emp_ids,
        "datetime": datetime,
        "now": datetime.now()
    })


from datetime import datetime, timedelta
import os, json

def get_suggested_covers(all_emp_ids, target_date, exclude_emp, department, shift_type):
    target = datetime.strptime(target_date, "%Y-%m-%d")
    day_before = (target - timedelta(days=1)).strftime("%Y-%m-%d")
    day_after = (target + timedelta(days=1)).strftime("%Y-%m-%d")

    def has_entry(roster, date, shift_type_filter=None):
        return any(
            r.get("date") == date and
            (shift_type_filter is None or r.get("shift_type") == shift_type_filter)
            for r in roster
        )
    # enddef has_entry

    suggested = []

    for emp_id, emp_data in all_emp_ids.items():
        if emp_id == exclude_emp or emp_data.get("department") != department:
            continue
        # endif department check

        path = os.path.join(CONFIGS_DIR, f"roster_{emp_id}.json")
        if not os.path.exists(path):
            continue
        # endif file exists

        with open(path) as f:
            roster = json.load(f)
        # endwith

        if has_entry(roster, target_date):
            continue
        # endif scheduled on target date

        if shift_type == "Day" and has_entry(roster, day_before):
            continue
        # endif worked day before

        if has_entry(roster, day_after, "Day"):
            continue
        # endif scheduled day after

        suggested.append((emp_id, emp_data.get("name"), emp_data.get("shift")))
    # endfor

    return suggested
# enddef get_suggested_covers

#*****************************************************************************

# Define your grouped shifts


core_shift_names = ["A Shift", "B Shift", "C Shift", "D Shift", "E Shift", "F Shift", "G Shift"]

from datetime import datetime

def get_cycle_position(date_str, shift_name, shift_defs):
    # Find the matching shift definition
    shift_def = next((s for s in shift_defs["Shifts"] if s["name"] == shift_name), None)
    if not shift_def:
        return None, None

    # Parse the target date
    try:
        date = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return None, None

    # Parse the cycle start date, supporting both full and abbreviated month names
    try:
        start = datetime.strptime(shift_def["first"], "%d %B %Y")  # e.g. "14 July 2025"
    except ValueError:
        try:
            start = datetime.strptime(shift_def["first"], "%d %b %Y")  # e.g. "14 Jul 2025"
        except ValueError:
            return None, None

    sequence = shift_def.get("shift_sequence", [])
    if not sequence:
        return None, None

    delta = (date - start).days
    if delta < 0:
        return None, None

    index = delta % len(sequence)
    symbol = sequence[index]

    # Remap night shifts: alternate N1/N2 based on prior count
    if symbol == "N":
        prior_ns = sequence[:index].count("N")
        label = "N1" if prior_ns % 2 == 0 else "N2"
    else:
        label = f"{symbol}{index + 1}"

    return label, symbol


def get_all_cycle_labels(shift_defs):
    labels = set()
    for s in shift_defs["Shifts"]:
        if s["name"] in core_shift_names:
            sequence = s["shift_sequence"]
            for i, symbol in enumerate(sequence):
                if symbol == "N":
                    label = "N1" if i % 2 == 0 else "N2"
                else:
                    label = f"{symbol}{i+1}"
                labels.add(label)
    return sorted(labels)

@app.get("/heatmap")
def show_heatmap(request: Request, dept: str = None, emp: str = None, shift: str = None, json: bool = False):
    employees = load_all_employees()
    shift_defs = load_shifts()
    target_types = ["PSL"]
    core_shift_names = ["A Shift", "B Shift", "C Shift", "D Shift", "E Shift", "F Shift", "G Shift"]

    all_departments = set()
    all_shifts = set()
    all_emps = []
    filtered = []

    for emp_id in employees:
        config = load_employee_config(emp_id)
        dept_name = config.get("departments")
        shift_name = config.get("shift_name")
        emp_name = config.get("emp_name")

        if dept_name:
            all_departments.add(dept_name)
        if shift_name:
            all_shifts.add(shift_name)
        if emp_name:
            all_emps.append({"name": emp_name, "emp_id": str(emp_id)})

        if emp:
            if str(emp_id) != str(emp):
                continue
        else:
            if dept and dept_name != dept:
                continue
            if shift and shift_name != shift:
                continue
            if not dept and not shift and shift_name not in core_shift_names:
                continue

        filtered.append(emp_id)

    #print("Filtered employees:", filtered)

    weekday_labels = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    raw_labels = get_all_cycle_labels(shift_defs)

    d_shifts = sorted([l for l in raw_labels if l.startswith("D")])
    n_shifts = sorted([l for l in raw_labels if l.startswith("N")])
    star_shifts = sorted([l for l in raw_labels if l.startswith("*")], key=lambda x: int(x[1:]))
    star_shifts = [s for s in star_shifts if s in ["*1", "*2", "*3", "*4"]]
    cycle_labels = d_shifts + n_shifts + star_shifts

    weekday_counts = {t: Counter() for t in target_types}
    cycle_counts = {t: Counter() for t in target_types}
    found_psl = False

    for emp_id in filtered:
        #roster_data = load_json(f"roster_{emp_id}.json")
        roster_data = load_roster_this_season(emp_id)
        for entry in roster_data:
            t = entry.get("type_shift")
            shift_roster = entry.get("shift")
            if t in target_types:
                found_psl = True
                day = datetime.strptime(entry["date"], "%Y-%m-%d").strftime("%A")
                weekday_counts[t][day] += 1

                if shift_roster in core_shift_names:
                    pos, symbol = get_cycle_position(entry["date"], shift_roster, shift_defs)
                    if pos:
                        cycle_counts[t][pos] += 1

    weekday_data = {
        t: [weekday_counts[t].get(day, 0) for day in weekday_labels]
        for t in target_types
    }
    cycle_data = {
        t: [cycle_counts[t].get(pos, 0) for pos in cycle_labels]
        for t in target_types
    }

    if not filtered:
        anomalies_weekday = ["No matching employees found."]
        anomalies_cycle = ["No matching employees found."]
        weekday_data = {t: [0] * len(weekday_labels) for t in target_types}
        cycle_data = {t: [0] * len(cycle_labels) for t in target_types}
    elif not found_psl:
        anomalies_weekday = ["No PSL entries found in roster data."]
        anomalies_cycle = ["No PSL entries found in roster data."]
        weekday_data = {t: [0] * len(weekday_labels) for t in target_types}
        cycle_data = {t: [0] * len(cycle_labels) for t in target_types}
    else:
        anomalies_weekday = detect_anomalies(weekday_data, weekday_labels)
        anomalies_cycle = detect_anomalies(cycle_data, cycle_labels)

    #print("Weekday data:", weekday_data)
    #print("Cycle data:", cycle_data)

    if json:
        return {
            "heatmap_weekday": weekday_data,
            "heatmap_cycle": cycle_data,
            "labels_weekday": weekday_labels,
            "labels_cycle": cycle_labels,
            "selected_dept": dept,
            "selected_emp": emp,
            "selected_shift": shift,
            "anomalies_weekday": anomalies_weekday,
            "anomalies_cycle": anomalies_cycle
        }

    ok, me = who_is_login()
    return templates.TemplateResponse("pages/heatmap.html", {
        "request": request,
        "ok": ok,
        "me": me,
        "heatmap_weekday": weekday_data,
        "heatmap_cycle": cycle_data,
        "labels_weekday": weekday_labels,
        "labels_cycle": cycle_labels,
        "selected_dept": dept,
        "selected_emp": emp,
        "selected_shift": shift,
        "all_departments": sorted(all_departments),
        "all_shifts": sorted(all_shifts),
        "all_emps": all_emps,
        "anomalies_weekday": anomalies_weekday,
        "anomalies_cycle": anomalies_cycle,
        "datetime": datetime,
        "now": datetime.now()
    })


import statistics

def detect_anomalies(data, labels):
    anomalies = []
    for i, label in enumerate(labels):
        values = [data[t][i] for t in data]
       # if all(v == 0 for v in values):
       #     anomalies.append(f"{label}: ⚠️ No PSL data recorded")
       #     continue

        total = sum(values)
        filtered = [v for v in values if v > 0]
        median = statistics.median(filtered) if filtered else 0

        for t in data:
            count = data[t][i]
            if count > 2 * median:
                anomalies.append(f"{label}: ⚠️ {t} unusually high ({count})")

        if total > 0:
            for t in data:
                count = data[t][i]
                ratio = count / total
                if ratio > 0.9:
                    anomalies.append(f"{label}: ⚠️ {t} dominates ({int(ratio*100)}%)")
    return anomalies


#++++++++++++++++++++++++++++++++++++++++++++++++++++++++

@app.get("/shorties")
def show_shorties(request: Request, dept: str = None, emp: str = None, shift: str = None, json: bool = False):
    employees = load_all_employees()
    shift_defs = load_shifts()
    target_types = ["CB", "SHORTIE"]
    core_shift_names = ["A Shift", "B Shift", "C Shift", "D Shift"]

    all_departments = set()
    all_shifts = set()
    all_emps = []
    filtered = []

    for emp_id in employees:
        config = load_employee_config(emp_id)
        dept_name = config.get("departments")
        shift_name = config.get("shift_name")
        emp_name = config.get("emp_name")

        if dept_name:
            all_departments.add(dept_name)
        if shift_name:
            all_shifts.add(shift_name)
        if emp_name:
            all_emps.append({"name": emp_name, "emp_id": str(emp_id)})

        if emp:
            if str(emp_id) != str(emp):
                continue
        else:
            if dept and dept_name != dept:
                continue
            if shift and shift_name != shift:
                continue
            if not dept and not shift and shift_name not in core_shift_names:
                continue

        filtered.append(emp_id)

    weekday_labels = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    cycle_labels = ['D1', 'D2', 'N1', 'N2', '*1', '*2', '*3', '*4']

    weekday_counts = {t: Counter() for t in target_types}
    cycle_counts = {t: Counter() for t in target_types}

    for emp_id in filtered:
        #roster_data = load_json(f"roster_{emp_id}.json")
        roster_data = load_roster_this_season(emp_id)
        for entry in roster_data:
            t = entry.get("type_shift")
            shift_name = entry.get("shift")  # e.g. "B Shift"
            notes = entry.get("notes", "")
            has_cover = "cover" in notes.lower() or "covered by" in notes.lower() or "by:" in notes.lower()
            date_str = entry["date"]
            day = datetime.strptime(date_str, "%Y-%m-%d").strftime("%A")

            # ✅ Final fix: pass shift_name into get_cycle_position
            pos, symbol = get_cycle_position(date_str, shift_name, shift_defs)

            if t == "CB":
                weekday_counts["CB"][day] += 1
                if pos and pos in cycle_labels:
                    cycle_counts["CB"][pos] += 1


            elif t == "SHIFT" and has_cover:
                weekday_counts["SHORTIE"][day] += 1
                if pos and pos in cycle_labels:
                    cycle_counts["SHORTIE"][pos] += 1


    # print("Final cycle counts:", {t: dict(cycle_counts[t]) for t in target_types})

    weekday_data = {
        t: [weekday_counts[t].get(day, 0) for day in weekday_labels]
        for t in target_types
    }
    cycle_data = {
        t: [cycle_counts[t].get(pos, 0) for pos in cycle_labels]
        for t in target_types
    }
    #print(f"weekday_data =  {weekday_data}")
    #print(f"cycle_data =  {cycle_data}")
    if json:
        return {
            "shorties_weekday": weekday_data,
            "shorties_cycle": cycle_data,
            "labels_weekday": weekday_labels,
            "labels_cycle": cycle_labels,
            "selected_dept": dept,
            "selected_emp": emp,
            "selected_shift": shift
        }

    ok, me = who_is_login()
    return templates.TemplateResponse("pages/shorties.html", {
        "request": request,
        "ok": ok,
        "me": me,
        "shorties_weekday": weekday_data,
        "shorties_cycle": cycle_data,
        "labels_weekday": weekday_labels,
        "labels_cycle": cycle_labels,
        "selected_dept": dept,
        "selected_emp": emp,
        "selected_shift": shift,
        "all_departments": sorted(all_departments),
        "all_shifts": sorted(all_shifts),
        "all_emps": all_emps,
        "datetime": datetime,
        "now": datetime.now()
    })

#-----------------------------------------------------------------------
@app.get("/psl_coverage")
def show_psl_coverage(request: Request, dept: str = None, emp: str = None, shift: str = None, json: bool = False):
    employees = load_all_employees()
    shift_defs = load_shifts()
    core_shift_names = ["A Shift", "B Shift", "C Shift", "D Shift","E Shift","F Shift"]

    all_departments = set()
    all_shifts = set()
    all_emps = []
    filtered = []

    for emp_id in employees:
        config = load_employee_config(emp_id)
        dept_name = config.get("departments")
        shift_name = config.get("shift_name")
        emp_name = config.get("emp_name")

        if dept_name:
            all_departments.add(dept_name)
        if shift_name:
            all_shifts.add(shift_name)
        if emp_name:
            all_emps.append({"name": emp_name, "emp_id": str(emp_id)})

        if emp:
            if str(emp_id) != str(emp):
                continue
        else:
            if dept and dept_name != dept:
                continue
            if shift and shift_name != shift:
                continue
            if not dept and not shift and shift_name not in core_shift_names:
                continue

        filtered.append(emp_id)

    weekday_labels = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    raw_labels = get_all_cycle_labels(shift_defs)

    d_shifts = sorted([l for l in raw_labels if l.startswith("D")])
    n_shifts = sorted([l for l in raw_labels if l.startswith("N")])
    star_shifts = sorted([l for l in raw_labels if l.startswith("*")], key=lambda x: int(x[1:]))
    star_shifts = [s for s in star_shifts if s in ["*1", "*2", "*3", "*4"]]
    cycle_labels = d_shifts + n_shifts + star_shifts

    from collections import defaultdict, Counter

    psl_flags = defaultdict(list)
    shortie_flags = defaultdict(list)

    for emp_id in filtered:
        #roster_data = load_json(f"roster_{emp_id}.json")
        roster_data = load_roster_this_season(emp_id)
        for entry in roster_data:
            date = entry.get("date")
            shift = entry.get("shift")
            key = f"{date}|{shift}"
            t = entry.get("type_shift")
            notes = entry.get("notes", "").lower()

            if t == "PSL":
                psl_flags[key].append(entry)
            elif t == "SHORTIE":
                entry_with_id = dict(entry)
                entry_with_id["emp_id"] = emp_id
                shortie_flags[key].append(entry_with_id)
                #shortie_flags[key].append(entry)
            elif t == "SHIFT" and "cover" in notes:
                entry_with_id = dict(entry)
                entry_with_id["emp_id"] = emp_id
                shortie_flags[key].append(entry_with_id)


    weekday_counts = {"PSL": Counter(), "SHORTIE": Counter()}
    cycle_counts = {"PSL": Counter(), "SHORTIE": Counter()}

    for key in psl_flags:
        date, shift = key.split("|")
        day = datetime.strptime(date, "%Y-%m-%d").strftime("%A")
        weekday_counts["PSL"][day] += len(psl_flags[key])

        if shift in core_shift_names:
            pos, symbol = get_cycle_position(date, shift, shift_defs)
            if pos:
                cycle_counts["PSL"][pos] += len(psl_flags[key])

    for key in shortie_flags:
        date, shift = key.split("|")
        day = datetime.strptime(date, "%Y-%m-%d").strftime("%A")
        weekday_counts["SHORTIE"][day] += len(shortie_flags[key])

        if shift in core_shift_names:
            pos, symbol = get_cycle_position(date, shift, shift_defs)
            if pos:
                cycle_counts["SHORTIE"][pos] += len(shortie_flags[key])

    coverage_audit = []

    for key in psl_flags:
        date, shift = key.split("|")
        covers = shortie_flags.get(key, [])
        for psl_entry in psl_flags[key]:
            day = datetime.strptime(date, "%Y-%m-%d").strftime("%A")
            if covers:
                for cover in covers:
                    name = load_employee_config(cover["emp_id"]).get("emp_name", "Unknown")
                    mins = cover.get("mins", 0)
                    t = cover.get("type_shift")
                    notes = cover.get("notes", "")
                    coverage_audit.append(f"🕵️ PSL on {day} → Covered by {name} ({t}, ‘{notes}’)")
            else:
                coverage_audit.append(f"🕵️ PSL on {day} → No cover assigned ⚠️")





    coverage_weekday = {
        t: [weekday_counts[t].get(day, 0) for day in weekday_labels]
        for t in ["PSL", "SHORTIE"]
    }
    coverage_cycle = {
        t: [cycle_counts[t].get(pos, 0) for pos in cycle_labels]
        for t in ["PSL", "SHORTIE"]
    }

    anomalies_weekday = detect_coverage_anomalies(coverage_weekday, weekday_labels)
    anomalies_cycle = detect_coverage_anomalies(coverage_cycle, cycle_labels)

    if json:
        return {
            "coverage_weekday": coverage_weekday,
            "coverage_cycle": coverage_cycle,
            "labels_weekday": weekday_labels,
            "labels_cycle": cycle_labels,
            "selected_dept": dept,
            "selected_emp": emp,
            "selected_shift": shift,
            "coverage_audit": coverage_audit,
            "anomalies_weekday": anomalies_weekday,
            "anomalies_cycle": anomalies_cycle
        }

    ok, me = who_is_login()
    return templates.TemplateResponse("pages/psl_coverage.html", {
        "request": request,
        "ok": ok,
        "me": me,
        "coverage_weekday": coverage_weekday,
        "coverage_cycle": coverage_cycle,
        "labels_weekday": weekday_labels,
        "labels_cycle": cycle_labels,
        "selected_dept": dept,
        "selected_emp": emp,
        "selected_shift": shift,
        "all_departments": sorted(all_departments),
        "all_shifts": sorted(all_shifts),
        "all_emps": all_emps,
        "anomalies_weekday": anomalies_weekday,
        "anomalies_cycle": anomalies_cycle,
        "coverage_audit": coverage_audit,
        "datetime": datetime,
        "now": datetime.now()
    })

def detect_coverage_anomalies(data, labels):
    anomalies = []
    for i, label in enumerate(labels):
        psl = data.get("PSL", [0]*len(labels))[i]
        shortie = data.get("SHORTIE", [0]*len(labels))[i]

        if psl > 0 and shortie == 0:
            anomalies.append(f"{label}: ⚠️ PSL with no cover assigned")
        elif psl > shortie:
            anomalies.append(f"{label}: ⚠️ PSL not fully covered (PSL={psl}, SHORTIE={shortie})")
        elif shortie > psl:
            anomalies.append(f"{label}: ⚠️ Extra SHORTIE assigned (PSL={psl}, SHORTIE={shortie})")
    return anomalies


@app.get("/surplus", response_class=HTMLResponse)
async def surplus_view(request: Request, emp_id: str = "650381"):
    # Load roster and config
    roster = load_roster_this_season(emp_id)
    config = load_json(f"emp_{emp_id}.json")

    result = getSeasonTotals(roster, config, rollOverNights=True)

    print(result["display"])
    
    print(f'behindMins = {result["behindMins"]}')

    # Get last shift date
    last_shift = max(roster, key=lambda r: r["date"])
    last_day = last_shift["date"]

    # Surplus hours (can be dynamic later)
    surplus_mins = result["behindMins"]
    surplus_hours = config.get("surplus_hours",abs(result["behindMins"]) / 60)

    # Trace surplus window
    start_date = trace_surplus_window(roster, last_day, surplus_hours)

    # Build drawdown data
    drawdown_data = []
    total = 0
    for entry in sorted(roster, key=lambda r: r["date"], reverse=True):
        if datetime.strptime(entry["date"], "%Y-%m-%d") <= datetime.strptime(last_day, "%Y-%m-%d"):
            total += entry.get("mins", 0)
            drawdown_data.append({
                "date": entry["date"],
                "mins": entry.get("mins", 0),
                "cumulative": total
            })
            if total >= surplus_hours * 60:
                break
    ok, me = who_is_login()
    return templates.TemplateResponse("pages/surplus.html", {
        "ok": ok,
        "me": me,
        "request": request,
        "emp_id": emp_id,
        "start_date": start_date,
        "last_day": last_day,
        "surplus_hours": surplus_hours,
        "drawdown_data": drawdown_data,
        "datetime": datetime,
        "now": datetime.now()
    })


@app.get("/timeline-block/{emp_id}", response_class=HTMLResponse)
async def timeline_block(emp_id: str):
    block = Timeline(emp_id)  # returns Markup-safe HTML
    return HTMLResponse(content=str(block))



#====================================================
@app.get("/api/configs/{filename}")
async def get_config_data(filename: str):
    """
    JSON API endpoint to retrieve configuration data.
    Ensures the requested file is within the CONFIGS_DIR for security.
    This Loads and returns the JSON content of the specified configuration file.
    """
    safe_path = Path(CONFIGS_DIR) / filename
    try:
        resolved = safe_path.resolve()
        if CONFIGS_DIR not in str(resolved):
            raise HTTPException(status_code=403, detail="Unsafe path")

        data = load_json(filename)
        #print(f"✅ Loaded config: {filename}")
        return data
    except FileNotFoundError as e:
        print(f"⚠️ {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except json.JSONDecodeError as e:
        print(f"❌ JSON decode error in {filename}: {e}")
        raise HTTPException(status_code=500, detail="Invalid JSON format")

#=====================================================
#=====================================================

@app.get("/api/generate_qr_code")
async def generate_qr_code(
    d: str = Query(...),  # date
    s: str = Query(...),  # shiftType
    e: int = Query(...)   # empId
):
    

    print("qr code request:", d, s, e)
    try:
        message = f"{s} shift alarm"
        output_path = f"images/qrcodes/QR-alarm.png"

        QR_code_alarm(
            emp_id=e,
            mode="calendar",  # or "calendar" if you want to support both
            message=message,
            date=d,
            output_path=output_path
        )

        # Return relative path for frontend use
        return JSONResponse(content={"status": "ok", "path": f"/{output_path}"})

    except Exception as ex:
        return JSONResponse(content={"status": "error", "message": str(ex)}, status_code=400)

from utils.paths import QR_DIR

@app.get("/qr/latest")
def serve_qr_image():
    path = os.path.join(QR_DIR, "QR-alarm.png")
    print(f"🖼️ Serving QR code image from {path}")
    return FileResponse(path, headers={
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0"
    })

def get_employees_on_shift_any(date_str):
    working = []
    rosters = load_all_rosters()  # { "123456": [...], "789012": [...] }

    for emp_id, entries in rosters.items():
        for entry in entries:
            if (
                entry.get("date") == date_str and
                entry.get("type_shift") in ["SHIFT", "CB"] and
                entry.get("shift_type", "").lower() in ["day", "night"]
            ):
                config = load_json(f"emp_{emp_id}.json")
                working.append({
                    "id": emp_id,
                    "name": config.get("emp_name", ""),
                    "shift_type": entry.get("shift_type"),
                    "shift": entry.get("shift"),
                    "department": config.get("departments", ""),
                    "notes": entry.get("notes")
                })
                break  # Found a match for this employee

    return working

@app.post("/api/report-sick")
async def report_sick(
    request: Request,
    date: str = Form(...),
    emp_id: str = Form(...),
    leave_type: str = Form(...),
    shift_type: str = Form(...),
    reason: str = Form("")
):
    """
    Records a sick call for an employee.
    Parameters:
    - date: Date of the sick call (YYYY-MM-DD).
    - emp_id: Employee ID.
    - leave_type: Type of leave.
    - shift_type: Type of shift.
    - reason: Reason for the sick call.
    """
    # Load employee config
    emp_config = load_json(f"emp_{emp_id}.json")
    shift_name = emp_config.get("shift_name", "Unknown")

    # Record the sick call
    record_sick_call(
        date=date,
        emp_id=emp_id,
        shift_name=shift_name,
        shift_type=shift_type,
        type_shift=leave_type,
        notes=reason or "phone in sick"
    )

    # Redirect back to calendar or confirmation page
    return RedirectResponse(url="/calendar", status_code=303)


@app.get("/report-sick", response_class=HTMLResponse)
async def show_sick_form(request: Request, date: Optional[str] = None):
    """
    Displays the sick report form.
    Parameters:
    - date: Optional date to pre-fill the form (YYYY-MM-DD).

    """
    if date:
        today = datetime.strptime(date, "%Y-%m-%d").date()
    else:
        today = datetime.today().date()
        date = today.isoformat()
    defaults = load_json("default.json")
    default_off_codes = defaults.get("off_codes", [])
    default_notes = defaults.get("notes", {})
    employees = get_employees_on_shift_any(date)

    date_list = [
        {
            "value": d.isoformat(),
            "label": d.strftime("%a %d-%m-%Y")
        }
        for d in [today + timedelta(days=i) for i in range(-2, 3)]
    ]

    ok, me = who_is_login()

    #print(f"employees {employees}")

    me_depts = list(set(me.get("working_dept", []) + [me.get("department")]))


    employees = [
        emp for emp in employees
        if emp.get("department") in me_depts
    ]

    return templates.TemplateResponse("pages/report_sick.html", {
        "request": request,
        "employees": employees,
        "date_options": date_list,
        "default_date": date,
        "ok": ok,
        "me": me,
        "datetime": datetime,
        "off_codes": default_off_codes,
        "leave_meanings": {
            k: v for k, v in default_notes.items()
            if k in default_off_codes },
        "now": datetime.now()
    })

#========================================================================


def record_sick_call(date, emp_id, shift_name, shift_type, type_shift, notes="phone in sick"):
    sick_entry = {
        "ID": str(uuid4()),
        "date": date,
        "emp_id": emp_id,
        "shift_name": shift_name,
        "shift_type": shift_type,
        "type_shift": type_shift,
        "notes": notes,
        "cover_id": None,
        "manager_id": None,
        "decision_timestamp": None,
        "status": "pending"
    }

    try:
        sick_data = load_json("sick.json")
    except FileNotFoundError:
        sick_data = []

    sick_data.append(sick_entry)
    save_json("sick.json", sick_data)

    return sick_entry
#=====================================================
import glog

def rollover_by_season_change():  # START def
    """
    Traverses all employee configuration files to detect changes in season start dates.
    If a change is detected, it triggers a roster rebuild for that employee and updates
    the configuration file accordingly.

    """
    base_config = load_json("default.json")
    base_start = base_config.get("season", {}).get("start")

    for path in glob.glob(os.path.join(CONFIGS_DIR, "emp_*.json")):  # START for

        with open(path, "r", encoding="utf-8") as f:  # START with
            config = json.load(f)
        # END with

        emp_id = config.get("emp_id")
        season_start = config.get("season", {}).get("start")

        if season_start != base_start:  # START if
            rebuild_roster_with_change(emp_id, change_date=season_start)
            config["season"]["rolled_on"] = datetime.now().strftime("%Y-%m-%d")
            config["force_season_roll"] = False

            with open(path, "w", encoding="utf-8") as f:  # START with
                json.dump(config, f, indent=2)
            # END with

            print(f"✅ Rolled EMP {emp_id} — season start changed")
        # END if

    # END for

# END def

#=====================================================
# Main application launch logic
#=====================================================
import sys

def is_rollover_mode():
    return "/rollover" in sys.argv or "--rollover" in sys.argv

def run_server():
    logging.debug("Starting TimeDeck server...")
    uvicorn.run(app, host="127.0.0.1", port=8000)

if __name__ == "__main__":
    if is_rollover_mode():
        logging.info("🔄 Rollover mode triggered via command-line switch.")
        rollover_by_season_change()  # ← Your function to scan and rebuild
        logging.info("✅ Rollover completed.")
        sys.exit(0)  # Exit cleanly after rollover

    # Normal launch flow
    threading.Thread(target=run_server, daemon=True).start()
    import time
    time.sleep(0)

    try:
        logging.info("Attempting to launch TimeDeck™ window...")
        window = webview.create_window("TimeDeck™", "http://127.0.0.1:8000",
                                       width=750, height=1000)
        logging.info("Window creation passed without error.")
        webview.start()

        logging.info("TimeDeck window closed. Running backup...")
        backup_all_json()
        logging.info("Backup completed successfully.")

    except Exception as e:
        logging.error(f"Window launch failed: {e}")
        import webbrowser
        webbrowser.open("http://127.0.0.1:8000")
