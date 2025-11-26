


python -m PyInstaller main.py --onefile --clean `
  --hidden-import pywebview --hidden-import clr_loader --hidden-import clr --hidden-import cffi `
  --add-data "images;images" --add-data "static;static" --add-data "templates;templates" `
  --icon "images/logo.ico" --name TimeDeck


# Function to summarize entitlements across all employees
def summarize_entitlements_by_department():

    emp_dir = CONFIGS_DIR #"configs/"
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
            #work
            #season_start = datetime.strptime(season.get("start", "1900-01-01"), "%d-%m-%Y")
            #season_end = datetime.strptime(season.get("ends", "2999-12-31"), "%d-%m-%Y")
            #not work
            season_start = datetime.strptime(season_default.get("start",""), "%d-%m-%Y")
            season_end = datetime.strptime(season_default.get("ends",""), "%d-%m-%Y")

        except ValueError:
            season_start = datetime.min
            season_end = datetime.max
        print(f"season_start = {season_start}, season_end = {season_end}")
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
    return department_summary, formatted_start, formatted_end, emp_count



Remove-Item -Recurse -Force .venv

pyinstaller main.py --onedir --clean --hidden-import pywebview --add-data "images;images" --add-data "static;static" --add-data "templates;templates" --name TimeDeck



<svg id="icon-{{ emp_id }}" xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor">

python -m venv venv 

.\venv\Scripts\activate
uvicorn main:app --reload --reload

https://bootswatch.com/sandstone/

--noconsole


{{ min_to_hrs(data.total_used_mins) }}


need to change this to match the TIMEDECK logic


pyinstaller main.py --onefile --clean --hidden-import pywebview --hidden-import holidays.countries.NewZealand --add-data "images;images" --add-data "static;static" --add-data "templates;templates" --icon "images/logo.ico" --name TimeDeck


pyinstaller main.py --onefile --clean --hidden-import pywebview --add-data "images;images" --add-data "static;static" --add-data "templates;templates" --icon "images/logo.ico" --name TimeDeck


<!-- <tr class="{{ "table-info" if entry.date >= config.start_date and entry.date <= config.end_date else "" }}">-->



some jason stuff  more home work

<div x-data="{
    emp: '541895',
    date: '2025-07-24',
    shift_type: 'Day',
    fieldname: 'type_shift',
    value: 'PSL',
    updateShift() {
      fetch('/update_roster_field', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          emp: this.emp,
          date: this.date,
          shift_type: this.shift_type,
          fieldname: this.fieldname,
          value: this.value
        })
      })
      .then(() => this.showToast = true);
    },
    showToast: false
}" class="p-6">

  <label for="typeShift" class="block text-sm font-medium text-gray-700 mb-2">Change Shift Type:</label>
  <select id="typeShift" x-model="value" class="border px-3 py-2 rounded w-40 mb-4">
    <option value="SHIFT">SHIFT</option>
    <option value="PSL">PSL</option>
    <option value="LEAVE">LEAVE</option>
  </select>

  <button @click="updateShift"
          class="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700">
    Save Change
  </button>

  <div x-show="showToast"
       x-transition
       x-init="setTimeout(() => showToast = false, 3000)"
       class="mt-4 bg-green-100 border border-green-300 text-green-800 px-4 py-2 rounded">
    ✅ Roster updated!
  </div>

</div>

Get windows login name.

import getpass

@app.get("/config_person")
async def config_person(request: Request):
    current_user = getpass.getuser()  # This gets OS login of the user running FastAPI

    config = load_config_for_user(current_user)
    editable = config.get("your_windows_login") == current_user

    return templates.TemplateResponse("config_person.html", {
        "request": request,
        "config": config,
        "hideit": not editable
    })


🛠️ Config & Access Logic

[ ] Auto-detect Windows login using getpass.getuser() and pre-fill "your_windows_login" in the config file

[ ] Filter EMPs by manager login → show only those where report_to == your_windows_login

[ ] Enable edit mode for manager view → auto-unhide fields when logged-in user matches "report_to"

📋 Roster Editing Flow

[ ] Build JS-powered roster editor that:

Reads roster_{emp}.json

Finds entry by date + shift_type

Updates a specific fieldname (like "type_shift")

Sends the change to /update_roster_field

[ ] Implement FastAPI route: @app.post("/update_roster_field") using your new save_roster(emp, date, shift_type, fieldname, value) function

[ ] Add Alpine toast for success confirmation — "✅ Roster updated!"

🧠 Quality-of-Life Upgrades

[ ] Create dropdown or inline editor for type_shift that saves changes live

[ ] Add audit trail: "last_updated_by": "Steve", "timestamp": "2025-07-24T13:45"

[ ] Style config pages based on user role — color-coded headers or manager badges

🎯 Debug & Cleanup

[ ] Revisit Alpine toast behavior — make it bulletproof with timed fade-out

[ ] Patch create_user_config() to correctly inherit "shift_name" on initial save

[ ] Run a config sweep to ensure "your_windows_login" is populated in all EMP profiles





<div class="relative">
    <label for="timeInput1" class="font-semibold text-lg">Enter Time 1:</label>
    <input type="text" id="timeInput1" placeholder="Enter time (e.g., 12.3, 12:18, 12h)" class="border-2 border-gray-300 p-2 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 w-full mt-2" />
    <div id="tooltip1" class="tooltip absolute text-sm bg-gray-700 text-white px-4 py-2 rounded-xl shadow-lg transform opacity-0 pointer-events-none transition-all -translate-y-2 mt-2"></div> <!-- Tooltip will be shown here -->
</div>






fetch("/rosters/roster_541895.json")  // Adjust path to match your server
  .then(response => response.json())
  .then(data => {
    // Find and update the target record
    let entry = data.find(e => e.date === "2025-07-24" && e.shift_type === "Day");
    if (entry) {
      entry.type_shift = "PSL";
    }

    // Send updated data back to server
    return fetch("/save_roster", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data)
    });
  })
  .then(() => {
    console.log("Roster updated and saved.");
  });

