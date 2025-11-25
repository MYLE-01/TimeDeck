#******************************************************************************

import os

import json
from utils.io import load_json
from utils.auth import get_windows_login, who_is_login, can_user_add_employee,find_employee_by_login,load_reporting_managers
from utils.paths import BASE_DIR, CONFIGS_DIR, JOB_TITLES_FILE, TEMPLATES_DIR, STATIC_DIR, IMAGES_DIR
from models.employee import load_all_employees
from collections import defaultdict

def job_title_badge_class(title):
    colors = {
        "L8": "bg-red-100 text-red-800",
        "L7": "bg-orange-100 text-orange-800",
        "Manager": "bg-blue-100 text-blue-800",
        "5B": "bg-green-100 text-green-800",
    }
    return colors.get(title, "bg-gray-100 text-gray-800")


def format_nz_mobile(number):
    """Format a 9–10 digit NZ mobile number (e.g., 0220233194 → 022 023 3194)."""
    number = number.strip().replace(" ", "")
    
    if number.startswith("+64"):
        number = "0" + number[3:]
    elif number.startswith("64") and not number.startswith("640"):
        number = "0" + number[2:]

    if len(number) == 10:
        return f"{number[:3]} {number[3:6]} {number[6:]}"
    elif len(number) == 9:
        return f"{number[:2]} {number[2:5]} {number[5:]}"
    return number  # fallback if formatting fails


def build_department_tree(data, emp_ids):
    """
    Build nested tree for a list of employee IDs
    """
    html = "<ul class='space-y-2'>"
    for emp_id in emp_ids:
        # Find the employee object (manager + reports)
        emp_obj = None
        for reports in data.values():
            for e in reports:
                if e['id'] == emp_id:
                    emp_obj = e
                    break
            if emp_obj:
                break
        if not emp_obj:
            continue

        job_title = emp_obj.get("job_title", "N/A")
        manager_class = "bg-yellow-100 font-bold" if job_title in {"L7","L8","Manager"} else "bg-white"
        phone = emp_obj.get("phone", "N/A").strip() or "N/A"
        shift = emp_obj.get("shift", "N/A")

        html += f'''
        <li data-emp-id="{emp_obj['id']}">
            <div class="flex items-center {manager_class} rounded-xl shadow px-4 py-2 hover:scale-105 transition">
                <a href="/config_person/{emp_obj['id']}" class="font-semibold text-gray-800 hover:underline">{emp_obj['name']}</a>
                <span class="text-sm text-gray-600 ml-2">{shift}</span>
                <span class="ml-2 px-2 py-0.5 rounded-full text-xs font-medium">{job_title}</span>
                <span class="text-sm text-gray-500 ml-2">{phone}</span>
                <span class="text-xs text-red-600 ml-2">ID: {emp_obj['id']}</span>
            </div>
            {build_department_tree(data, [e['id'] for e in data.get(emp_obj['id'], [])])}
        </li>
        '''
    html += "</ul>"

    return html



def build_tree_recursive(data, emp_ids, titles_order, visited=None):
    """
    Recursively render employees and their direct reports.
    Stops infinite loops using `visited` set.
    Adds accessible toggle buttons with ARIA attributes.
    """
    if visited is None:
        visited = set()

    html = ''
    emp_ids_sorted = sorted(
        emp_ids,
        key=lambda eid: titles_order.index(next(
            (emp["job_title"] for emp_list in data.values() for emp in emp_list if emp["id"] == eid), None
        )) if next(
            (emp["job_title"] for emp_list in data.values() for emp in emp_list if emp["id"] == eid), None
        ) in titles_order else len(titles_order)
    )
    reporting_managers = load_reporting_managers()
    reporting_managers = set(reporting_managers)  # faster lookup

    for emp_id in emp_ids_sorted:
        if emp_id in visited:
            continue
        visited.add(emp_id)

        emp_obj = next(
            (emp for emp_list in data.values() for emp in emp_list if emp["id"] == emp_id),
            None
        )
        if not emp_obj:
            continue

        job_title = emp_obj.get("job_title", "N/A")
        manager_class = "bg-yellow-100 font-bold" if job_title in reporting_managers else "bg-white"
        phone = emp_obj.get("phone", "N/A").strip() or "N/A"
        shift = emp_obj.get("shift", "N/A")
        has_reports = emp_id in data
        ok, me = who_is_login()

        # Build name HTML: link only when job_title is in reporting_managers
        if ok[0]:
            name_html = (
                f'<a href="/config_person/{emp_obj["id"]}" '
                f'class="font-semibold text-gray-800 hover:underline">{emp_obj["name"]}</a>'
            )
        else:
            name_html = f'<span class="font-semibold text-gray-800">{emp_obj["name"]}</span>'

        # Create unique ID for collapsible reports section
        reports_id = sanitize_id(f"reports-{emp_obj['id']}")

        html += f'''
        <div class="employee-wrapper mb-2">
            <div class="flex items-center justify-between {manager_class} rounded-xl shadow px-4 py-2 employee-card">
                <div>
                    {name_html}
                    <span class="ml-2 px-2 py-0.5 rounded-full text-xs font-medium {job_title_badge_class(job_title)}">{job_title}</span>
                    <span class="text-sm text-gray-500 ml-2">{format_nz_mobile(phone)}</span>
                </div>
                {'<button class="toggle-employee focus:outline-none ml-2" aria-expanded="false" aria-controls="' + reports_id + '" onclick="toggleSection(this)" aria-label="Toggle direct reports for ' + emp_obj["name"] + '">' +
                '<svg class="w-4 h-4 transition-transform duration-300 rotate-90" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">' +
                '<path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7" />' +
                '</svg></button>' if has_reports else ''}
            </div>
        '''

        # Recurse only on direct reports
        if has_reports:
            html += f'''
            <div id="{reports_id}" class="employee-reports ml-4 mt-1 hidden" aria-hidden="true">
                <ul class="list-none">
                    {build_tree_recursive(data, [e['id'] for e in data[emp_id]], titles_order, visited)}
                </ul>
            </div>
            '''

        html += "</div>"  # close employee-wrapper

    return html

def sanitize_id(text):
    """Helper to create safe HTML IDs from strings."""
    import re
    return re.sub(r'\W+', '-', text.lower()).strip('-')


def build_html_tree(data, departments, titles_order, me, no_manager=None):
    """
    Build full org chart HTML:
    - Department grouping with counts
    - Shift sub-grouping (collapsible) with ARIA
    - Nested reports
    - Manager highlighting
    - Toggle expand/collapse with accessible buttons
    """
    me_depts = list(set(me.get("working_dept", []) + [me.get("department")]))
    html = ''
    print("Building HTML tree...")
    print(f"Data keys: {list(data.keys())}")

    emp_list = load_all_employees()
    report_map = {}
    for emp_id, emp_data in emp_list.items():
        manager_id = emp_data.get("report_to")
        if manager_id and manager_id != "0":
            report_map.setdefault(manager_id, set()).add(emp_id)

            
    
  

    filtered_data = {
        emp_id: [
            emp for emp in emp_data
            if emp.get("department_name") in me_depts
        ]
        for emp_id, emp_data in data.items()
    }

    # Group employees by department
    dept_map = {}
    for emp_list in filtered_data.values():
        for emp in emp_list:
            dept = emp.get("department_name", "N/A")
            dept_map.setdefault(dept, []).append(emp)

    # Build HTML per department
    for department, emp_list in dept_map.items():
        dept_count = len(emp_list)
        dept_id = sanitize_id(department)

        html += f'''
        <div class="department-section mb-4" id="dept-{dept_id}">
            <button 
                class="toggle-department-btn w-full text-left bg-blue-500 text-white px-4 py-2 rounded-t-lg font-semibold shadow flex justify-between items-center focus:outline-none"
                aria-expanded="false"
                aria-controls="dept-content-{dept_id}"
                onclick="toggleSection(this)"
            >
                <span>{department} ({dept_count})</span>
                <svg class="w-4 h-4 transition-transform duration-300 rotate-90" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7" />
                </svg>
            </button>

            <div 
                id="dept-content-{dept_id}" 
                class="bg-white border border-blue-300 rounded-b-lg shadow p-3 hidden"
                aria-hidden="true"
            >
        '''

        shift_config = load_json("shifts.json")
        shift_order = [s["name"] for s in shift_config.get("Shifts", [])]

        # Group by shift
        shift_map = {}
        for emp in emp_list:
            shift = emp.get("shift", "N/A")
            shift_map.setdefault(shift, []).append(emp)

        # Build HTML per shift with ARIA toggles
        for shift_name in sorted(
            shift_map.keys(),
            key=lambda s: shift_order.index(s) if s in shift_order else len(shift_order)
        ):
            shift_emps = shift_map[shift_name]
            shift_id = sanitize_id(f"{department}-{shift_name}")

            html += f'''
            <div class="shift-section mb-2" id="shift-{shift_id}">
                <button
                    class="toggle-shift-btn w-full text-left bg-blue-100 px-3 py-1 rounded-md font-medium flex justify-between items-center focus:outline-none"
                    aria-expanded="false"
                    aria-controls="shift-content-{shift_id}"
                    onclick="toggleSection(this)"
                >
                    <span>{shift_name} ({len(shift_emps)})</span>
                    <svg class="w-4 h-4 transition-transform duration-300 rotate-90" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7" />
                    </svg>
                </button>
                <div 
                    id="shift-content-{shift_id}" 
                    class="shift-employees ml-4 mt-2 hidden"
                    aria-hidden="true"
                >
                    {build_tree_recursive(data, [e['id'] for e in shift_emps], titles_order)}
                </div>
            </div>
            '''

        html += "</div></div>"

    ok, me = who_is_login()

    # Add special "No Manager" block with ARIA toggle
    if no_manager:
        html += f'''
        <div class="no-manager-section mt-6" id="no-manager-section">
            <button
                class="toggle-no-manager w-full text-left bg-red-500 text-white px-4 py-2 rounded-t-lg font-semibold shadow flex justify-between items-center focus:outline-none"
                aria-expanded="false"
                aria-controls="no-manager-content"
                onclick="toggleSection(this)"
            >
                🚫 Employees with No reportto ({len(no_manager)}) top of food chain
                <svg class="w-4 h-4 transition-transform duration-300 rotate-90" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7" />
                </svg>
            </button>

            <div 
                id="no-manager-content" 
                class="no-manager-employees bg-white border border-red-300 rounded-b-lg shadow p-3 grid gap-2 hidden"
                aria-hidden="true"
            >
        '''
        for emp in sorted(no_manager, key=lambda e: e['name']):

            # Build name HTML: link only when job_title is in reporting_managers
            if ok[0] :
                name_html = (
                    f'<a href="/config_person/{emp["id"]}" class="font-semibold text-gray-800 hover:underline">{emp["name"]}</a>'
                )
            else:
                name_html = f'<span class="font-semibold text-gray-800">{emp["name"]}</span>'

            html += f'''
                <div class="p-2 rounded-lg bg-red-50 hover:bg-red-100 transition flex items-center justify-between">
                    {name_html}
                    <span class="text-sm text-gray-600">{emp.get("job_title", "N/A")}</span>
                </div>
            '''
        html += "</div></div>"

    return html
