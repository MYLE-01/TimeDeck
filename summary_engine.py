from datetime import datetime
from utils import load_all_employees, load_config, load_json

def parse_date(date_str):
    return datetime.strptime(date_str, "%d-%m-%Y")

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

def summarize_employee(emp_id, config, roster_data):
    try:
        expected = calculate_expected_minutes(config, roster_data)
        done = sum(entry["mins"] for entry in roster_data if entry.get("on_shift"))
        makeup = sum(entry["mins"] for entry in roster_data if entry.get("type_shift") == "COVER")
        left = max(expected - done, 0)
        percent = round((done / expected) * 100, 1) if expected else 0

        return {
            "Employee": emp_id,
            "Done (min)": done,
            "Left (min)": left,
            "Makeup (min)": makeup,
            "Expected (min)": expected,
            "Completion (%)": percent
        }

    except Exception as e:
        return {
            "Employee": emp_id,
            "Error": str(e)
        }

def generate_summary_report():
    employees = load_all_employees()
    report = []

    for emp_id in employees:
        config = load_config(emp_id)
        roster_data = load_json(f"roster_{emp_id}.json")
        summary = summarize_employee(emp_id, config, roster_data)
        report.append(summary)

    return report