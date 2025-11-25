import json
from datetime import datetime, date, timedelta
import os,sys
from utils.io import load_json, save_roster, create_user_config
import logging
from uuid import uuid4 
from utils.paths import BASE_DIR, CONFIG_DIR, CONFIGS_DIR, JOB_TITLES_FILE, TEMPLATES_DIR, STATIC_DIR, IMAGES_DIR




def load_roster_for_employee(emp_id, month=None, year=None):
    path = os.path.join(CONFIG_DIR, f"roster_{emp_id}.json")
    if not os.path.exists(path):
        return []

    try:
        with open(path, "r", encoding="utf-8") as f:
            all_entries = json.load(f)
    except Exception as e:
        print(f"⚠️ Error loading roster for {emp_id}: {e}")
        return []

    filtered = []
    for entry in all_entries:
        try:
            entry_date = datetime.fromisoformat(entry["date"])
        except Exception:
            continue

        if month and year:
            if entry_date.year != year or entry_date.month != month:
                continue

        filtered.append({
            "date": entry["date"],
            "holiday_name": "" if entry.get("holidays", "") == "-" else entry.get("holidays", ""),
            "shift_type": entry.get("shift_type", "")[:1].upper(),
            "type_shift": entry.get("type_shift", ""),
            "notes": entry.get("notes", ""),
            "shift_minutes": entry.get("mins", 0)
        })

    return filtered


def load_roster(emp_id):
    path = os.path.join(CONFIG_DIR, f"roster_{emp_id}.json")
    if not os.path.exists(path):
        return []

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️ Error loading roster for {emp_id}: {e}")
        return []



def load_all_rosters(roster_dir="configs"):
    rosters = {}
    for fname in os.listdir(roster_dir):
        if fname.startswith("roster_") and fname.endswith(".json"):
            emp_id = fname[len("roster_"):-len(".json")]
            with open(os.path.join(roster_dir, fname), "r", encoding="utf-8") as f:
                rosters[emp_id] = json.load(f)
    return rosters


def build_roster(emp_id: int):
    try:
        emp_config = load_json(f"emp_{emp_id}.json")
    except FileNotFoundError:
        logging.warning(f"Config for emp_id {emp_id} not found. Creating from default.")
        create_user_config(emp_id, f"EMP-{emp_id}", 0, "XXXXX")
        emp_config = load_json(f"emp_{emp_id}.json")

    shift_config = load_json("shifts.json")

    season_start = datetime.strptime(emp_config["season"]["start"], "%d-%m-%Y")
    season_end = datetime.strptime(emp_config["season"]["ends"], "%d-%m-%Y")

    roster_data = generate_roster(emp_config, shift_config)


    save_roster(emp_id, roster_data)

    return "Roster created"





def generate_roster(emp_config, shift_config):
    current_year = date.today().year
    import holidays
    nz_holidays = holidays.NewZealand(
        years=[current_year, current_year + 1],
        subdiv=emp_config["public_holidays"]
    )

    shift_name = emp_config["shift_name"]
    shift_info = next((s for s in shift_config["Shifts"] if s["name"] == shift_name), None)
    if not shift_info:
        raise ValueError(f"Shift '{shift_name}' not found in shifts.json")

    season_start = datetime.strptime(emp_config["season"]["start"], "%d-%m-%Y")
    season_end = datetime.strptime(emp_config["season"]["ends"], "%d-%m-%Y")
    shift_start = datetime.strptime(shift_info["first"], "%d %B %Y")
    #print(f"🔍 Building roster for {shift_name} from {season_start.date()} to {season_end.date()}")

    # Handle regular pattern
    regular_pattern = shift_info.get("roster_pattern")
    regular_sequence = shift_info.get("shift_sequence", "")
    if not regular_sequence and regular_pattern:
        regular_sequence = expand_pattern(regular_pattern)
    if not regular_sequence:
        raise ValueError("No valid regular shift pattern found")
    
    regular_mins = emp_config["season"].get("mins", 0)

    # Handle winter pattern safely
    winter_enabled = emp_config["season"].get("winter_maths", False)
    if winter_enabled:
        winter_start = datetime.strptime(emp_config["season"]["winter_start"], "%d-%m-%Y")
        winter_end = datetime.strptime(emp_config["season"]["winter_ends"], "%d-%m-%Y")
        winter_pattern = emp_config["season"].get("winter_pattern")
        if not winter_pattern:
            print("⚠️ Warning: winter_maths enabled but no winter_pattern defined in config. Skipping winter roster.")
            winter_sequence = None
            winter_mins = 0
            winter_enabled = False
        else:
            winter_sequence = expand_pattern(winter_pattern) if "x" in winter_pattern else winter_pattern
            winter_mins = emp_config["season"].get("winter_mins", 0)
    else:
        winter_start = winter_end = None
        winter_sequence = None
        winter_mins = 0

    roster = []
    prev_code = None

    for n in range((season_end - season_start).days + 1):
        current_date = season_start + timedelta(days=n)
        entry_date = current_date.strftime("%Y-%m-%d")
        day_name = current_date.strftime("%A")

        # Choose which pattern and mins to apply
        if winter_enabled and winter_start <= current_date <= winter_end:
            sequence = winter_sequence
            cycle_length = winter_mins
            ref_start = winter_start
            winter_active = True
        else:
            sequence = regular_sequence
            cycle_length = regular_mins
            ref_start = shift_start
            winter_active = False

        if not sequence:
            raise ValueError(f"No shift sequence available for {entry_date}")

        pattern_length = len(sequence)
        if pattern_length == 0:
            raise ValueError("Shift pattern is empty (ZeroDivisionError prevention)")

        offset = (current_date - ref_start).days
        if offset >= 0:
            index = offset % pattern_length
            shift_code = sequence[index]
            next_code = sequence[(index + 1) % pattern_length]
        else:
            shift_code = "-"
            next_code = "-"

        def get_cover_flags(shift_type):
            if shift_code == "*":
                if prev_code == "N" and shift_type == "Day":
                    return False, False
                if next_code == "D" and shift_type == "Night":
                    return False, False
                return True, True
            return True, True

        if shift_code == "D":
            callback, cover = get_cover_flags("Day")
            roster.append({
                "ID": str(uuid4()),
                "date": entry_date,
                "shift": shift_name,
                "day": day_name,
                "holidays": nz_holidays.get(current_date) or "-",
                "shift_type": "Day",
                "type_shift": "SHIFT",
                "on_shift": True,
                "mins": cycle_length,
                "callback_eligible": callback,
                "cover_allowed": cover,
                "notes": ""
            })
        elif shift_code == "N":
            callback, cover = get_cover_flags("Night")
            roster.append({
                "ID": str(uuid4()),
                "date": entry_date,
                "shift": shift_name,
                "day": day_name,
                "holidays": nz_holidays.get(current_date) or "-",
                "shift_type": "Night",
                "type_shift": "SHIFT",
                "on_shift": True,
                "mins": cycle_length,
                "callback_eligible": callback,
                "cover_allowed": cover,
                "notes": ""
            })

        prev_code = shift_code

    return roster


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
