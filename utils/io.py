from fileinput import filename
import os 
import json
import sys
from datetime import datetime
from pathlib import Path
from .paths import BASE_DIR, CONFIGS_DIR
import os
import json
import time



def load_shifts():
    shifts_file = os.path.join(CONFIGS_DIR, "shifts.json")
    if not os.path.exists(shifts_file):
        return {}
    with open(shifts_file, "r", encoding="utf-8") as f:
        return json.load(f)
    
def parse_datef(date_str):
    from datetime import datetime
    try:
        return datetime.strptime(date_str, "%d-%m-%Y")
    except Exception:
        return None  # gracefully handle bad or missing dates


def load_roster_this_season(emp_id):
    """
    Load roster entries for the given emp_id that fall within the employee's current season.
    
    """
    all_entries = load_json(f"roster_{emp_id}.json")
    config_emp = load_json(f"emp_{emp_id}.json")
    season_config = config_emp.get("season", {})
    season_start = parse_datef(season_config.get("start"))
    season_end = parse_datef(season_config.get("ends"))
    filtered = []
    for entry in all_entries:
        try:
            entry_date = datetime.strptime(entry["date"], "%Y-%m-%d")
            if season_start <= entry_date <= season_end:
                filtered.append(entry)
        except Exception:
            continue  # skip bad entries

    return filtered



def load_json(filename: str):
    filepath = os.path.join(CONFIGS_DIR, filename)
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"Config file not found: {filepath}")
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)




def save_json(filename: str, data: dict):
    filepath = os.path.join(CONFIGS_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def create_user_config(emp_id: int,emp_name: str,report_to:int,shift_name: str):
    base_config = load_json("default.json")
    base_config["emp_id"] = emp_id
    base_config["emp_name"] = emp_name
    base_config["report_to"] = report_to
    base_config["shift_name"] = shift_name
    filename = f"emp_{emp_id}.json"
    save_json(filename, base_config)
    return filename

def save_roster(emp_id: int, roster_data: list):
    filename = f"roster_{emp_id}.json"
    filepath = os.path.join(CONFIGS_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(roster_data, f, indent=2)

def save_roster_sorted(emp_id: int, roster_data: list):
    filename = f"roster_{emp_id}.json"
    filepath = os.path.join(CONFIGS_DIR, filename)

    # sort roster by date then shift_type
    sorted_roster = sorted(
        roster_data,
        key=lambda x: (
            datetime.strptime(x["date"], "%Y-%m-%d"),
            0 if x["shift_type"] == "Day" else 1
        )
    )

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(sorted_roster, f, indent=2, ensure_ascii=False)