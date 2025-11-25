from datetime import datetime, timedelta ,date
import json
import os,sys
import getpass

from utils.paths import BASE_DIR, CONFIGS_DIR, JOB_TITLES_FILE, TEMPLATES_DIR, STATIC_DIR, IMAGES_DIR

def load_jobtitles():
    """
    Load job titles JSON but strip out _notes so they don't show in UI.
    """
    if not os.path.exists(JOB_TITLES_FILE):
        return {"reporting_managers": "", "titles": {}, "departments": {}}

    with open(JOB_TITLES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Strip _notes if present
    data.pop("_notes", None)
    if "titles" in data and "_notes" in data["titles"]:
        data["titles"].pop("_notes")
    if "departments" in data and "_notes" in data["departments"]:
        data["departments"].pop("_notes")

    return data

def save_jobtitles(data: dict):
    """
    Save job titles JSON (keeping structure consistent).
    """
    with open(JOB_TITLES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)




def save_roster_json_file(emp, date, shift_type, fieldname, value):
    """
    DONT USE THIS FUNCTION ANYMORE. Use utils/io.py -> save_json() instead.
    Update a specific field in an employee's roster JSON file for a given date and shift type.

    Example usage:
    save_roster_json_file("541895", "2025-07-24", "Day", "type_shift", "PSL")


    """

    filename = f"configs/roster_{emp}.json"

    # Fail gracefully if file doesn't exist
    if not os.path.exists(filename):
        raise FileNotFoundError(f"No roster file found for EMP {emp}")

    # Load roster data
    with open(filename, "r", encoding="utf-8") as f:
        roster = json.load(f)

    # Search and update
    match_found = False
    for entry in roster:
        if entry["date"] == date and entry["shift_type"] == shift_type:
            entry[fieldname] = value
            match_found = True
            break

    if not match_found:
        raise ValueError(f"No entry found for {date} ({shift_type}) in EMP {emp}'s roster")

    # Save back
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(roster, f, indent=2)

    print(f"✅ Updated {fieldname} to '{value}' for EMP {emp} on {date} ({shift_type})")


def flip_date(date_str):
    """
    Flip date between YYYY-MM-DD and DD-MM-YYYY formats.
    """
    parts = date_str.split('-')
    
    if len(parts[0]) == 4:  # Format is YYYY-MM-DD
        return f"{parts[2]}-{parts[1]}-{parts[0]}"  # Flip to DD-MM-YYYY
    elif len(parts[2]) == 4:  # Format is DD-MM-YYYY
        return f"{parts[2]}-{parts[1]}-{parts[0]}"  # Flip to YYYY-MM-DD
    else:
        raise ValueError("Invalid date format. Expected YYYY-MM-DD or DD-MM-YYYY.")



def is_it_pay_day(date_check: date) -> bool:
    """
    Given a date, return True if it's a pay day, otherwise False.
    Pay days are every second Tuesday starting from 8 Feb 2022.
    """
    base_payday = date(2022, 1, 8)  # known reference payday
    days_diff = (date_check - base_payday).days

    # Tuesday is weekday() == 1, and must be a 14-day multiple
    return days_diff % 14 == 0 and date_check.weekday() == 1

def is_date_between(begin_time, end_time) -> bool:
    check_time = date.today()
    if begin_time < end_time:
        return check_time >= begin_time and check_time <= end_time
    else:  # crosses midnight
        return check_time >= begin_time or check_time <= end_time
    
    
def SumJason(jsonFile, attribute):
    """ 
    Input Jasondata array
    Finds the attribute you want sum
    """
    sum = 0
    for item in jsonFile:
        if attribute in item and isinstance(item[attribute], int):
            sum += item[attribute]

    return sum

def convert_expression_to_mins(expr):
    """
    Convert a time expression (e.g., "8h + 30", "7.5 + 1h", "6:30 + 2:15") into total minutes.
    Supports multiple parts separated by '+'.
    """
    import re
    if not expr or str(expr).lower().strip() in ["none", "null"]:
        return 0

    parts = re.split(r"\s*\+\s*", expr.strip())
    total = 0

    for part in parts:
        total += convert_this_to_mins(part)

    return total



def convert_this_to_mins(time):
    """
    Convert a single time expression into minutes.
    Supports formats like:
    - "12h"  → 720 mins
    """
    if not time or str(time).lower().strip() in ["none", "null"]:
        return 0

    this = str(time).lower().strip()

    if this.endswith("h") and this[:-1].isdigit():
        # Example: "12h" → 12 hours → 720 mins
        hours = int(this[:-1])
        answer = hours * 60

    elif "." in this:
        # Decimal hours (e.g., "40.", "7.5")
        hours = float(this)
        answer = decimal_time_hrs_to_mins(hours)

    elif ":" in this:
        # HH:MM format
        answer = hrs_to_mins(this)

    elif this.isdigit():
        # Plain integer already in minutes
        answer = int(this)

    else:
        raise ValueError(f"Unknown time format: '{time}'")

    return int(answer)

def decimal_time_hrs_to_mins(hours):
    """Convert decimal hours (float or string) into minutes."""
    if isinstance(hours, str):
        hours = float(hours.strip())
    return hrs_to_mins(decimal_time(hours))


def decimal_time(hours):
    """Convert decimal hours to HH:MM string."""
    if isinstance(hours, str):
        hours = float(hours.strip())

    h = int(hours)
    minutes = int(round((hours * 60) % 60))  # remainder minutes
    return f"{h:02d}:{minutes:02d}"



def min_to_hrs(minutes):
    """
    Import : minutes

    return in time format 00:00
    """
    if minutes < 0:
        minu = - minutes
        my = "-"
    else:
        minu = minutes
        my = ""
    hours = minu // 60
    minu = minu - (hours * 60)
    check1 = my + (("%02d:%02d" % (hours, minu)))
    return check1 if check1 != "00:00" else ""


def hrs_to_mins(time_str):
    """Convert HH:MM string to minutes."""
    if isinstance(time_str, (int, float)):
        # already numeric
        return int(time_str)

    parts = str(time_str).split(":")
    h, m = int(parts[0]), int(parts[1])
    return h * 60 + m

def sum_cover_minutes(roster, emp_id):
    return sum(
        entry["mins"]
        for entry in roster
        if "notes" in entry and emp_id in entry["notes"]
    )
def callback_summary(roster, emp_id):
    count = 0
    total_min = 0
    for entry in roster:
        if entry.get("notes") and emp_id in entry["notes"]:
            count += 1
            total_min += entry["mins"]
    return {
        "entries": count,
        "minutes": total_min,
        "time": min_to_hrs(total_min)
    }

def sort_and_clean_records(records, key="date", label_fmt="%#d-%b", pop_fields=("sort_key",)):
    """
    Sorts a list of records by a real datetime key, formats label, and removes helper fields.
    
    Args:
        records (list): List of dicts with at least 'date' or specified key.
        key (str): Field name containing the raw date string.
        label_fmt (str): Format string for display labels.
        pop_fields (tuple): Helper keys to remove after processing.
    
    Returns:
        List of cleaned records ready for charting
    """
    processed = []
    for entry in records:
        raw = entry.get(key, "")
        try:
            d = datetime.fromisoformat(raw)
            label = d.strftime(label_fmt)
        except ValueError:
            d = datetime.today()
            label = raw

        item = {
            "label": label,
            "value": entry.get("value", 0),
            "sort_key": d
        }
        processed.append(item)

    processed.sort(key=lambda x: x["sort_key"])

    for item in processed:
        for field in pop_fields:
            item.pop(field, None)

    return processed

def get_shift_summary_for_date(date_str, shift_configs):
    """
    Returns a summary list of each shift’s status for a given date.
    
    Format:
    [ { "name": ..., "code": ..., "status": ..., "cycle_day": ..., "cycle_length": ... }, ... ]
    """
    target = datetime.strptime(date_str, "%d %B %Y").date()
    summary = []

    code_map = {
        "D": "Day Shift 🕒",
        "N": "Night Shift 🌙",
        "*": "Off Shift 💤"
    }

    for shift in shift_configs["Shifts"]:
        start = datetime.strptime(shift["first"], "%d %B %Y").date()
        sequence = shift["shift_sequence"]
        cycle_len = len(sequence)

        days_since_start = (target - start).days

        if days_since_start >= 0:
            cycle_pos = days_since_start % cycle_len
            code = sequence[cycle_pos]
        else:
            cycle_pos = None
            code = "*"

        summary.append({
            "name": shift["name"],
            "code": code,
            "status": code_map.get(code, "Unknown"),
            "cycle_day": cycle_pos + 1 if cycle_pos is not None else "Not started",
            "cycle_length": cycle_len
        })

    return summary
