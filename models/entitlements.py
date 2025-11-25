from models.employee import load_all_employees, get_active_managers, build_reporting_tree
from utils.io import load_json
import os, sys
from datetime import datetime, date, timedelta
import json
from utils.paths import BASE_DIR,CONFIG_DIR, CONFIGS_DIR, JOB_TITLES_FILE, TEMPLATES_DIR, STATIC_DIR, IMAGES_DIR
from collections import defaultdict
from datetime import datetime

#-------------------------------------------------------------------------------

# Function to summarize entitlements across all employees

def load_default_config(path=CONFIGS_DIR + "\default.json"):
    #print(f"Loading default config from {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def summarize_entitlements_by_department():


    emp_dir = CONFIG_DIR #"configs/"
    department_summary = defaultdict(lambda: defaultdict(lambda: {'total_mins': 0, 'count': 0, 'description': ''}))
    date_format = "%Y-%m-%d"  # Format used in roster dates
    emp_count = 0
    for emp_file in os.listdir(emp_dir):
        if not emp_file.startswith("emp_") or not emp_file.endswith(".json"):
            continue

        emp_id = emp_file[4:-5]  # Extract ID from emp_?????.json
        emp_path = os.path.join(emp_dir, emp_file)
        emp_count += 1  
        # Load employee JSON
        with open(emp_path, "r", encoding="utf-8") as f:
            emp_data = json.load(f)

        department = emp_data.get("departments", "Unknown")
        season = emp_data.get("season", {})
        notes = emp_data.get("notes", {})  # Contains entitlement descriptions
        season_default = load_default_config()

        try:
            season_start_str = season_default["season"].get("start", "01-01-1900")
            season_end_str = season_default["season"].get("ends", "31-12-2999")

            season_start = datetime.strptime(season_start_str, "%d-%m-%Y")
            season_end = datetime.strptime(season_end_str, "%d-%m-%Y")

        except ValueError:
            season_start = datetime.min
            season_end = datetime.max

        # Load matching roster file
        roster_file = f"roster_{emp_id}.json"
        roster_path = os.path.join(emp_dir, roster_file)
        if not os.path.exists(roster_path):
            continue

        with open(roster_path, "r", encoding="utf-8") as f:
            roster_data = json.load(f)

        for shift in roster_data:
            shift_date_str = shift.get("date")
            if not shift_date_str:
                continue

            try:
                shift_date = datetime.strptime(shift_date_str, date_format)
            except ValueError:
                continue

            if not (season_start <= shift_date <= season_end):
                continue  # Skip shifts outside season

            type_shift = shift.get("type_shift")
            mins = shift.get("mins", 0)
            notes_text = shift.get("notes", "").lower()

            try:
                mins_int = int(mins)
            except (ValueError, TypeError):
                mins_int = 0

            if type_shift:
                summary = department_summary[department][type_shift]
                summary['total_mins'] += mins_int
                summary['count'] += 1
                summary['description'] = notes.get(type_shift, '')  # Set description

            if type_shift == "SHIFT" and "cover" in notes_text:
                shorty = department_summary[department]["SHORTY"]
                shorty['total_mins'] += mins_int
                shorty['count'] += 1
                shorty['description'] = "Short notice to cover shift."
    formatted_start = season_start.strftime("%d-%b-%Y")  # e.g., 20-Jul-2025
    formatted_end = season_end.strftime("%d-%b-%Y")

    # After collecting all mins per shift type
    for department, shifts in department_summary.items():
        total_shift_mins = shifts.get("SHIFT", {}).get("total_mins", 0)

        for shift_type, summary in shifts.items():
            if total_shift_mins > 0:
                summary['percent_of_shift'] = round((summary['total_mins'] / total_shift_mins) * 100, 2)
            else:
                summary['percent_of_shift'] = 0.0




    return department_summary, formatted_start, formatted_end, emp_count



def calculate_entitlements(roster_data):
    entitlements = {}

    for entry in roster_data:
        emp_name = entry["employee"]
        mins = entry.get("minutes", 0)
        etype = entry.get("type", "Unknown")

        if emp_name not in entitlements:
            entitlements[emp_name] = {}

        if etype not in entitlements[emp_name]:
            entitlements[emp_name][etype] = 0

        entitlements[emp_name][etype] += mins

    return entitlements

def build_shift_summary(config_dir="configs"):
    """
    Builds a per-employee summary of shift and leave usage for the current season.
    Includes entitlement, usage, balance, washup, and extra effort metrics.
    """
    employees = load_all_employees()
    summary = {}

    for emp_id, emp_info in employees.items():
        # --- Season safety checks ---
        season_info = emp_info.get("season")
        if not season_info:
            print(f"⚠️ {emp_id} missing season info, skipping.")
            continue

        season_start = season_info.get("start")
        season_end = season_info.get("ends")
        if not season_start or not season_end:
            print(f"⚠️ {emp_id} missing season dates, skipping.")
            continue

        try:
            season_start_dt = datetime.strptime(season_start, "%d-%m-%Y").date()
            season_end_dt = datetime.strptime(season_end, "%d-%m-%Y").date()
        except ValueError as e:
            print(f"⚠️ {emp_id} has invalid season dates: {e}, skipping.")
            continue

        # --- Load roster and calculate total workload ---
        roster_data = load_json(f"roster_{emp_id}.json")
        raw_total_mins = emp_info.get("total_mins", 0)
        is_temp = raw_total_mins == 0
        total_minutes_todo = raw_total_mins or sum(entry.get("mins", 0) for entry in roster_data)

        type_counts = {}
        type_minutes = {}
        today = datetime.today().date()

        for entry in roster_data:
            entry_date_str = entry.get("date")
            if not entry_date_str:
                continue

            try:
                entry_date = datetime.strptime(entry_date_str, "%Y-%m-%d").date()
            except ValueError:
                continue

            if entry_date < season_start_dt or entry_date > min(today, season_end_dt):
                continue

            type_shift = entry.get("type_shift") or entry.get("shift_type") or "UNKNOWN"
            notes = entry.get("notes", "").lower()
            mins = entry.get("mins", 0)

            # Reclassify covered SHIFTs as SHORTY
            code = "SHORTY" if type_shift == "SHIFT" and "cover" in notes else type_shift

            type_counts[code] = type_counts.get(code, 0) + 1
            type_minutes[code] = type_minutes.get(code, 0) + mins

        # --- Inject SHIFT entitlement and usage ---
        emp_carryover = {k: v for k, v in emp_info.get("cover_over", {}).items() if k != "_notes"}
        desired_order = list(emp_carryover.keys())

        emp_carryover["SHIFT"] = total_minutes_todo
        type_minutes["SHIFT"] = type_minutes.get("SHIFT", 0) + type_minutes.get("SHORTY", 0)

        # --- Calculate balance and washup ---
        all_codes = set(emp_carryover.keys()) | set(type_minutes.keys())
        balance = {}
        washup = {}

        for code in all_codes:
            start_mins = emp_carryover.get(code, 0)
            used = type_minutes.get(code, 0)
            balance[code] = start_mins - used
            washup[code] = used  # washup mirrors usage

        total_used_mins = sum(type_minutes.values())

        # --- Extra effort metric ---
        shift_count = type_counts.get("SHIFT", 0)
        cb_count = type_counts.get("CB", 0)
        shorty_count = type_counts.get("SHORTY", 0)

        extra_effort_percent = 0
        if shift_count > 0:
            extra_effort_percent = ((cb_count + shorty_count) / shift_count) * 100

        # --- Final sort and summary ---
        sorted_codes = [code for code in desired_order if code in all_codes]
        sorted_codes += [c for c in all_codes if c not in desired_order]

        summary[emp_id] = {
            "employee": emp_info,
            "type_counts": type_counts,
            "type_minutes": type_minutes,
            "carryover_start": {code: emp_carryover.get(code, 0) for code in sorted_codes},
            "carryover_used": {code: type_minutes.get(code, 0) for code in sorted_codes},
            "carryover_balance": {code: balance.get(code, 0) for code in sorted_codes},
            "washup": {code: washup.get(code, 0) for code in sorted_codes},
            "total_used_mins": total_used_mins,
            "sorted_codes": sorted_codes,
            "is_temp": is_temp,
            "total_minutes_todo": total_minutes_todo,
            "extra_effort_percent": round(extra_effort_percent, 1),
        }

    return dict(sorted(summary.items(), key=lambda item: item[1].get("total_used_mins", 0)))
