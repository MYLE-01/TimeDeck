
import os,sys
import json
import getpass
from models.employee import load_all_employees
from models.employee import can_edit

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
    TEMPLATES_DIR = os.path.join(sys._MEIPASS, "templates")
else:
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))  # one level up
    TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
CONFIGS_DIR = os.path.join(BASE_DIR, "configs")
JOB_TITLES_FILE = os.path.join(CONFIGS_DIR, "jobtitle.json")


def who_is_login():

    emp_list = load_all_employees()

    login = get_windows_login()
    me = find_employee_by_login(emp_list, login)
    # --- figure out current user ---

    if not me:
        print(f"❌ No employee matched login: {login}")
        ok = (False, f"No employee matched login: {login}", "hidden")
    else:
        ok = can_user_add_employee(me["id"], emp_list, load_reporting_managers(),login)
        #print(f"✅ Logged in as {me['name']} ({me['job_title']})")

    # --- handle empty employee list ---
    #if not emp_list:
    #    print("⚠️ No employees configured yet. Please add employees first.")
    #    return templates.TemplateResponse("pages/help.html", {
    #        "request": request,
    #        "ok": ok,
    #        "me": me,
    #       "reporting_managers": load_reporting_managers(),
    #       "now": datetime.now(),
    #       "datetime": datetime
    #   })

    # --- optionally: enforce login match before proceeding ---
    if not me:
        ok = (False, f"No employee matched login: {login}", "",login)

    return ok, me




def get_windows_login() -> str:
    """
    Get the current Windows login username.
    Tries os.getlogin(), falls back to getpass.getuser().
    """
    try:
        return os.getlogin()
    except Exception:
        return getpass.getuser()

def load_reporting_managers(default_value=None) -> list:
    """
    Load 'reporting_managers' from jobtitle.json.
    Accepts either a space-separated string, comma-separated string, or a list.
    Always returns a clean list of titles.
    """


    default_value = default_value or []
    job_titles_path = os.path.join(CONFIGS_DIR, "jobtitle.json")
    default_path = os.path.join(CONFIGS_DIR, "default.json")

    #print(f" job_titles_path  = {job_titles_path}")


    # Try jobtitle.json first
    if os.path.exists(job_titles_path):
        with open(job_titles_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        val = data.get("reporting_managers", default_value)
        if isinstance(val, str):
            # Split by spaces or commas, remove empty strings
            return [v.strip() for v in val.replace(',', ' ').split() if v.strip()]
        elif isinstance(val, list):
            # Clean any extra whitespace or trailing commas
            return [v.strip().rstrip(',') for v in val if v.strip()]
    
    # Fallback to default.json
    if os.path.exists(default_path):
        with open(default_path, "r", encoding="utf-8") as f:
            default = json.load(f)
        val = default.get("reporting_managers", default_value)
        if isinstance(val, str):
            return [v.strip() for v in val.replace(',', ' ').split() if v.strip()]
        elif isinstance(val, list):
            return [v.strip().rstrip(',') for v in val if v.strip()]
    
    return []

def can_user_add_employee(emp_id: int, emp_data: dict, reporting_managers: list , login: str) -> tuple:
    """
    Check if the user with emp_id can add/edit employees.
    Permissions are granted if:
    - The user's job title is in reporting_managers list
    """
    user = emp_data.get(emp_id)
    if not user:
        return False, "User not found" , "hidden"

    job_title = user.get("job_title")
    if job_title in reporting_managers:
        return True, "User has permission","",login

    return False, "User does not have permission" , "hidden", login


def find_employee_by_login(emp_data: dict, login: str):
    """
    Match a Windows login to an employee record.
    Looks for "your_windows_login" field in each employee.
    Returns the employee dict if found, else None.
    """
    # print(emp_data)
    for emp_id, details in emp_data.items():
        if details.get("your_windows_login", "").lower() == login.lower():
            return {
                "id": emp_id,
                "name": details.get("name", "Unknown"),
                "job_title": details.get("job_title", "Unknown"),
                "department": details.get("department", "Unknown"),
                "contact_number": details.get("contact_number", ""),
                "shift": details.get("shift", "Unknown"),
                "working_dept": details.get("working_dept", []),
            }
    return None
