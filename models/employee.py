import os , sys
import json
import re
from datetime import datetime, date
from collections import defaultdict
from typing import Optional, Dict, Any
from utils.paths import BASE_DIR, CONFIGS_DIR,CONFIG_DIR ,JOB_TITLES_FILE, TEMPLATES_DIR, STATIC_DIR, IMAGES_DIR
from utils.io import load_shifts

def can_edit(my_title, employee_title) -> bool:

    level_order = {
        "Manager": 9,
        "L8": 8,
        "L7": 7,
        "2IC": 6,   # Assuming 2IC is below L7 but above L6; adjust if needed
        "L6": 6,
        "5A": 5,
        "5B": 4,
        "L4": 3
    }

    manager_level = level_order.get(my_title)
    employee_level = level_order.get(employee_title)

    if manager_level is None or employee_level is None:
        return False  # Unknown titles

    # Manager can edit if employee level is strictly less than manager level
    return employee_level < manager_level



def build_reporting_tree(emp_list, departments):
    tree = {}

    for emp in emp_list:
        emp_id = emp.get("id", "")  # fixed, use "id", not "emp_id"
        report_to = emp.get("report_to", "")
        department_code = emp.get("department", "")
        department_name = departments.get(department_code, "Unknown Department")

        if not report_to or report_to == '0':
            report_to = emp_id  # root manager reports to themselves

        # Prepare employee info
        employee_info = {
            "department": department_code,
            "id": emp_id,
            "name": emp.get("name"),
            "phone": emp.get("contact_number", ""),
            "shift": emp.get("shift", ""),
            "job_title": emp.get("job_title", ""),
            "report_to": report_to,
            "department_name": department_name
        }

        # Include the employee under the manager if manager exists
        manager = next((e for e in emp_list if e.get("id") == report_to), None)

        if manager and manager.get("job_title") in {"L7", "L8", "Manager"}:
            tree.setdefault(report_to, []).append(employee_info)

        # ✅ Also include the manager themselves if they are top-level
        if emp_id == report_to and emp.get("job_title") in {"L7", "L8", "Manager"}:
            # Avoid duplicate if already appended
            if emp_id not in tree or employee_info not in tree[emp_id]:
                tree.setdefault(emp_id, []).insert(0, employee_info)  # insert at top
    # print(f"📊 Reporting tree built successfully: {tree}")
    return tree



def get_active_managers(emp_data, reporting_levels=None):
    """
    Finds all employees who:
    - Exist in emp_data,
    - Have a job_title listed in reporting_levels (list of titles)
    """
    reporting_levels = reporting_levels or []
    allowed_titles = set(reporting_levels)  # already a list, no need to split

    return [
        {
            "id": emp_id,
            "name": details["name"],
            "job_title": details.get("job_title", "")
        }
        for emp_id, details in emp_data.items()
        if details.get("job_title") in allowed_titles
    ]

def get_direct_reports(my_id, all_employees):
    return [emp for emp in all_employees if emp.get("report_to") == my_id]


def load_all_employees():
    """
    Load all employee configs from emp_??????.json files.
    """
    #pattern = re.compile(r"emp_(\d{6})\.json")
    #pattern = re.compile(r"^emp_(\w+)\.json$")
    pattern = re.compile(r"^emp_(\d{6}|temp_.+)\.json$")

    emp_data = {}

    # Default carryover template
    default_carryover = {
        "_notes": "This is our start point rem in MINS but input could be in mins",
        "SHIFT": 0,
        "CB": 0,
        "PNW": 0,
        "LWP": 0,
        "PAL": 0,
        "ADT": 0,
        "LSL": 0,
        "PSL": 0,
        "USL": 0,
        "ACC": 0,
        "BVT": 0,
        "PPL": 0,
        "TRE": 0
    }

    for filename in os.listdir(CONFIGS_DIR):
        match = pattern.match(filename)
        if not match:
            continue
        #print(f"Loading employee config: {filename}")         
        emp_id = match.group(1)
        with open(os.path.join(CONFIGS_DIR, filename), "r", encoding="utf-8") as f:
            data = json.load(f)

        # Merge defaults with employee's stored carryover
        emp_carryover = default_carryover.copy()
        emp_carryover.update(data.get("annual_entitlements_carryover", {}))
        total_mins = data.get("default_entitlement_mins", 0)
        emp_data[emp_id] = {
            "id": emp_id,
            "name": data.get("emp_name", "Unknown"),
            "department": data.get("departments", ""),
            "working_dept": data.get("working_dept", []),
            "report_to": str(data.get("report_to", "0")),
            "job_title": data.get("job_title", "Unknown"),
            "contact_number": data.get("contact_number", ""),
            "shift": data.get("shift_name", "Unknown"),
            "total_mins": total_mins,
            "cover_over": emp_carryover,
            "season": data.get("season", {}),
            "your_windows_login": data.get("your_windows_login", "").lower()
        }
    #print(f"len === {len(emp_data)}")
    return emp_data


def parse_first_date(s: str) -> date:
    # "14 July 2025"
    return datetime.strptime(s.strip(), "%d %B %Y").date()

def parse_query_date(on_date) -> date:
    if on_date is None:
        return date.today()
    if isinstance(on_date, date):
        return on_date
    if isinstance(on_date, datetime):
        return on_date.date()
    # Expect "YYYY-MM-DD"
    return datetime.strptime(str(on_date), "%Y-%m-%d").date()

def parse_roster_minutes(roster_pattern: str) -> int:
    # e.g., "4x4x12" -> 12 hours -> 720 minutes
    try:
        hours = int(str(roster_pattern).split("x")[-1])
        return hours * 60
    except Exception:
        return 0

def shift_code_for_date(shift_entry: dict, on_date: date, allow_before_start: bool = False):
    """
    Returns a tuple (code, index) where code is 'D'/'N'/'*' or None if not started
    and index is the index in the sequence for this date (when code is not None).
    """
    seq = (shift_entry.get("shift_sequence") or "").strip()
    if not seq:
        return None, None
    first_day = parse_first_date(shift_entry["first"])
    offset = (on_date - first_day).days
    if offset < 0 and not allow_before_start:
        return None, None
    idx = offset % len(seq)  # works for negative offsets too
    return seq[idx], idx

def get_shift_status_for_date(shift_name: str, on_date=None, allow_before_start: bool = False) -> dict:
    """
    Lookup a shift by name and report today's (or given date's) code/label and metadata.
    """
    shifts = load_shifts()
    entry = next((s for s in shifts if s.get("name") == shift_name), None)
    if not entry:
        raise ValueError(f"Shift '{shift_name}' not found in {SHIFTS_FILE}")

    qdate = parse_query_date(on_date)
    seq = (entry.get("shift_sequence") or "").strip()
    code, idx = shift_code_for_date(entry, qdate, allow_before_start=allow_before_start)
    minutes = parse_roster_minutes(entry.get("roster_pattern", ""))

    # Next day's code, if sequence started
    next_code = None
    if code is not None and seq:
        next_code = seq[(idx + 1) % len(seq)]

    # Cycle info: Day X of Y (1-based position within the repeating sequence)
    cycle_day = None
    cycle_len = len(seq) if seq else None
    cycle_text = None
    if code is not None and cycle_len:
        cycle_day = idx + 1  # 1-based
        cycle_text = f"Cycle: Day {cycle_day} of {cycle_len}"

    return {
        "shift_name": shift_name,
        "date": qdate.isoformat(),
        "code": code,
        "label": "Not started" if code is None else CODE_LABELS.get(code, "Unknown"),
        "minutes": minutes,
        "hours": minutes // 60 if minutes else 0,
        "sequence": seq,
        "first": entry.get("first", ""),
        "next_code": next_code,
        "next_label": CODE_LABELS.get(next_code, "Unknown") if next_code else None,
        "cycle_day": cycle_day,
        "cycle_length": cycle_len,
        "cycle_text": cycle_text,  # e.g., "Cycle: Day 2 of 8"
    }

# --- Convenience: simple function that just returns the code/label for today ---
def shift_code_today(shift_name: str) -> tuple[str | None, str]:
    info = get_shift_status_for_date(shift_name)
    return info["code"], info["label"]

def build_shift_today(on_date: Optional[str] = None, allow_before_start: bool = False, include_not_started: bool = False) -> Dict[str, Dict[str, Any]]:
    """
    Loop through all shifts and build a dict keyed by shift name with today's status.
    on_date: None (today) or 'YYYY-MM-DD'
    allow_before_start: if True, cycles repeat even before first date
    include_not_started: include entries where code is None
    """
    qdate = parse_query_date(on_date)
    result: Dict[str, Dict[str, Any]] = {}
    for s in load_shifts():
        name = s.get("name")
        if not name:
            continue
        info = get_shift_status_for_date(name, qdate, allow_before_start=allow_before_start)
        if info["code"] is None and not include_not_started:
            continue
        result[name] = {
            "date": info["date"],
            "code": info["code"],
            "label": info["label"],
            "cycle_day": info["cycle_day"],
            "cycle_length": info["cycle_length"],
            "cycle_text": info["cycle_text"],
            "hours": info["hours"],
            "minutes": info["minutes"],
        }
    return result

#------------------------------------------------------------------
# Rules make a bit smarter 
def auto_select_single_employee(emp_list: dict):
    """
    Rule 1: If only 1 employee exists, auto-select them.
    """
    if len(emp_list) == 1:
        return next(iter(emp_list.values()))  # return the only employee dict
    return None


def user_can_add_employee(user_id: str, emp_list: dict, reporting_managers: str) -> bool:
    """
    Rule 2: Only reporting managers can add employees.
    """
    # Get the user object
    user = emp_list.get(user_id)
    if not user:
        return False  # User not found

    # Allowed titles from jobtitle.json or default.json
    allowed_titles = reporting_managers.split()

    # Check if their job_title matches one of the allowed ones
    return user.get("job_title", "") in allowed_titles

def can_add_first_employee(emp_list: dict) -> bool:

    """
    Rule 3: If there are no employees, anyone can add the first one.
    """
    return len(emp_list) == 0

def can_user_add_employee(user_id: str, emp_list: dict, reporting_managers: list) -> tuple[bool, str]:
    """
    Decide if a user can add employees.
    
    Rules:
      1. If no employees exist → anyone can add the first one.
      2. If exactly 1 employee exists → anyone can add that one (bootstrap rule).
      3. If employees exist → only reporting managers can add.
    
    Returns:
      (can_add, reason)
    """

    # --- Rule 1: no employees
    if len(emp_list) == 0:
        return True, "No employees exist. Anyone can add the first employee."

    # --- Rule 2: exactly one employee
    if len(emp_list) == 1:
        return True, "Only one employee exists. Allow adding one more.","",user_id

    # --- Rule 3: normal mode (need reporting manager)
    user = emp_list.get(user_id)
    if not user:
        return False, "User not found in employee list.","hidden",user_id

    if user.get("job_title") in reporting_managers:
        return True, "User is a reporting manager and can add employees.","",user_id

    return False, "User is not a reporting manager. Cannot add employees.","hidden",user_id



# ---------------------------------------------------------------

# Rules for employee management

#---------------------------------------------------------------

def get_code_sets(emp: dict) -> tuple[set[str], set[str], set[str]]:
    default_off = {"PNW", "LWP", "PAL", "ADT", "LSL", "PSL", "USL", "ACC", "BVT", "PPL"}
    default_working = {"SHIFT", "CB"}  # keep TRE out; min_blind will add expected anyway
    default_min_blind = {"TRE"}        # add any others you want minute-blind

    raw_off = emp.get("off_codes")
    raw_work = emp.get("working_codes")
    raw_min_blind = emp.get("min_blind_codes")

    def to_set(values, fallback):
        if not values or not isinstance(values, (list, tuple, set)):
            src = fallback
        else:
            src = values
        return {str(v).strip().upper() for v in src}

    off_codes = to_set(raw_off, default_off)
    base_working = to_set(raw_work, default_working)
    min_blind = to_set(raw_min_blind, default_min_blind)

    # Ensure min-blind codes contribute to "expected"
    working_codes = base_working | min_blind

    return off_codes, working_codes, min_blind

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

def _parse_date(s):
    if not s:
        return None
    if isinstance(s, date):
        return s
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(str(s), fmt).date()
        except Exception:
            continue
    return None


def _to_minutes(v):
    try:
        return int(round(float(v)))
    except Exception:
        return 0


def load_all_rosters(roster_dir="configs"):
    """
    Load all roster_*.json files into a dict keyed by emp_id.
    """
    rosters = {}
    pattern = re.compile(r"roster_(\d{6})\.json")
    for filename in os.listdir(roster_dir):
        match = pattern.match(filename)
        if not match:
            continue
        emp_id = match.group(1)
        filepath = os.path.join(roster_dir, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            roster_data = json.load(f)
            rosters[emp_id] = roster_data
    return rosters


def build_cover_report(config_dir: str = "configs", employees: dict | None = None) -> dict:
    if employees is None:
        employees = load_all_employees()  # must return {emp_id: emp_config}

    # Load all rosters
    rosters: dict[str, list[dict]] = {}
    for emp_id in employees:
        roster_file = os.path.join(CONFIG_DIR , f"roster_{emp_id}.json")
        try:
            if os.path.exists(roster_file):
                with open(roster_file, "r", encoding="utf-8") as f:
                    rosters[emp_id] = json.load(f)
            else:
                rosters[emp_id] = []
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
                    #print(
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