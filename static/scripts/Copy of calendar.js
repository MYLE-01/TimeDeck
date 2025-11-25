document.addEventListener("DOMContentLoaded", () => {
  const monthSelect = document.getElementById("monthSelect");
  const yearSelect = document.getElementById("yearSelect");
  const today = new Date();

  if (!monthSelect.value) monthSelect.value = today.getMonth() + 1;
  if (!yearSelect.value) yearSelect.value = today.getFullYear();

  loadCalendar();

  // Calendar cell double-click
  document.addEventListener("dblclick", async (e) => {
  const cell = e.target.closest("[data-id], [data-has_data]");
  if (!cell) return;

  const { emp, id, date, shift, type, has_data } = cell.dataset;
  console.log("Double-clicked cell:", { emp, id, date, shift, type, has_data });

  const empId = document.getElementById("employeeSelect").value;
  if (!empId) {
    alert("Please select an employee first!");
    return;
  }

  try {
    // Fetch employee config always (needed for modal)
    const configRes = await fetch(`/configs/emp_${empId}.json?v=${Date.now()}`);
    const config = await configRes.json();
    console.log("✅ Loaded employee config:", config);

    // Case 1: existing data
    if (has_data === "true") {
      const res = await fetch(`/configs/roster_${empId}.json?v=${Date.now()}`);
      const roster = await res.json();
      console.log("Raw roster fetch response:", roster);

      const entry = roster.find(r => r.date === date && r.shift_type === shift);
      //const entry = roster.find(r => r.date === date);
      console.log("Matched roster entry:", entry);

      showTimeOffModal(empId, config, date, shift, roster, () => {
        loadCalendar();
        updateEmployeeSummary(empId);
        updateCalendarHeader();
      });

    // Case 2: no data yet → create new record
    } else {
      console.log("No existing data, opening modal for NEW record...");
      showTimeOffModal(empId, config, date, shift, [], () => {
        updateEmployeeSummary(empId);
        updateCalendarHeader();
        loadCalendar();
      });
    }

  } catch (err) {
    console.error("❌ Failed to load config/roster:", err);
    alert("Could not load employee data");
  }
});
});


document.getElementById("shiftSelect")?.addEventListener("change", updateEmployeeDropdown);

async function loadCalendar() {
  const emp = document.getElementById("employeeSelect")?.value || "";
  const shift = document.getElementById("shiftSelect")?.value || "";
  const year = document.getElementById("yearSelect")?.value || "";
  const month = document.getElementById("monthSelect")?.value || "";
  const holidayList = document.getElementById("ShowHolidays");
  updateEmployeeSummary(emp);
  updateCalendarHeader();
  if (holidayList) holidayList.innerHTML = "";

  try {
    const res = await fetch(
      `/calendar-data?emp_id=${emp}&shift=${encodeURIComponent(shift)}&month=${month}&year=${year}`
    );
    if (!res.ok) throw new Error(`Failed to load calendar data: ${res.status}`);

    const data = await res.json();

    function getBgColor(entry) {
      if (!entry) return "bg-white";
      const { shift_type } = entry;
      if (shift_type === "N") return "bg-blue-200";
      if (shift_type === "D") return "bg-yellow-200";
      return "bg-white";
    }

    // Build holiday list once
    const seenHolidays = new Set();
    if (holidayList) {
      data.forEach((entry) => {
        if (entry.is_holiday && entry.holiday_name && !seenHolidays.has(entry.date)) {
          const colorClass = getBgColor(entry);
          holidayList.innerHTML += `
            <div class="text-sm text-orange-600 flex items-center gap-2">
              <span class="px-2 py-0.5 rounded ${colorClass}">${entry.shift_type || "-"}</span>
              <span>${entry.date}: ${entry.holiday_name}</span>
            </div>
          `;
          seenHolidays.add(entry.date);
        }
      });
    }

    const grid = document.getElementById("calendarGrid");
    if (!grid) return;
    grid.innerHTML = "";

    const firstDay = new Date(year, month - 1, 1).getDay();
    for (let i = 0; i < firstDay; i++) {
      grid.innerHTML += `<div class="h-24 border p-2 text-center rounded bg-gray-100"></div>`;
    }

    const daysInMonth = new Date(year, month, 0).getDate();

    function minToHrs(mins) {
      if (typeof mins !== "number" || isNaN(mins) || mins === 0) return "";
      const hours = Math.floor(mins / 60);
      const minutes = mins % 60;
      return `(${hours}:${minutes.toString().padStart(2, "0")})`;
    }

    function isItPayDay(dateCheck, dayNumber) {
      const checkDate = new Date(dateCheck);
      const basePayday = new Date(2022, 1, 8); // Feb is 1
      const cleanCheck = new Date(
        checkDate.getFullYear(),
        checkDate.getMonth(),
        checkDate.getDate()
      );
      const msInDay = 24 * 60 * 60 * 1000;
      const daysDiff = Math.floor((cleanCheck - basePayday) / msInDay);
      return daysDiff % 14 === 0 && cleanCheck.getDay() === 2
        ? `<span class="text-orange-600 font-semibold">${dayNumber}</span>`
        : dayNumber;
    }

    function Wordit(shift) {
      if (shift === "N") return "Night";
      if (shift === "D") return "Day";
      return shift || "";
    }

    function formatDateDM(dateStr) {
      const d = new Date(dateStr);
      if (isNaN(d)) return dateStr; // fallback if invalid
      const day = String(d.getDate()).padStart(2, "0");
      const month = d.toLocaleString("en-US", { month: "short" });
      return `${day}-${month}`;
    }

    // Helper to make YYYY-MM-DD
    const pad = (n) => String(n).padStart(2, "0");
    // start 
    for (let d = 1; d <= daysInMonth; d++) {
      const dayEntries = data.filter((e) => new Date(e.date).getDate() === d);
      const cellDate = `${year}-${pad(month)}-${pad(d)}`;

      // Sum minutes from ALL entries (SHIFT included in sum)
      const totalMins = dayEntries.reduce((sum, e) => sum + (e.shift_minutes || 0), 0);

      // Collect non-SHIFT labels
      const labels = dayEntries
        .filter(e => e.type_shift && e.type_shift !== "SHIFT")
        .map(e => e.type_shift);

      const bgColor = dayEntries.length ? getBgColor(dayEntries[0]) : "bg-white";
      const borderColor = dayEntries.some(e => e.is_holiday) ? "border-orange-500 border-2" : "";
      const isToday =
        new Date(cellDate).toDateString() === new Date().toDateString()
          ? "border-red-500 border-4"
          : "";

      const has_data = dayEntries.length > 0 ? "true" : "false";
      const empAttr = document.getElementById("employeeSelect")?.value || "";

      grid.innerHTML += `
        <div data-has_data="${has_data}" data-emp="${empAttr}" data-date="${cellDate}"
            class="relative group h-24 border p-2 text-center rounded flex flex-col justify-center ${bgColor} ${borderColor} ${isToday}">
          <div class="font-bold">${isItPayDay(cellDate, d)}</div>
          ${labels.length ? `<div class="text-xs break-words">${labels.join("+")}</div>` : ""}
          <div class="text-xs text-gray-500 mt-1">
            ${minToHrs(totalMins)}
          </div>
        </div>
      `;
    }

    // -------------------------------
    // Month Notes Table
    // -------------------------------
    const noteContainer = document.getElementById("monthnoteContainer");
    if (noteContainer) {
      const monthNotes = data.filter(
        (e) => e.notes && e.date.startsWith(`${year}-${pad(month)}`)
      );

      if (monthNotes.length === 0) {
        noteContainer.innerHTML = "";
      } else {
        let tableHTML = `
          <h3 class="text-lg font-semibold mb-2">
            Notes / Comments for the Month <!-- ${year}-${pad(month)}-->
          </h3>
          <div class="overflow-x-auto">
            <table class="min-w-full border border-gray-300 rounded-lg shadow-sm text-sm">
              <thead class="bg-gray-200 text-gray-700">
                <tr>
                  <th class="px-3 py-2 border">Date</th>
                  <!--<th class="px-3 py-2 border">Shift</th>-->
                  <th class="px-3 py-2 border">Note / Comments </th>
                </tr>
              </thead>
              <tbody>
        `;

        monthNotes.forEach((entry) => {
          let value = '';
          if (entry.type_shift === 'SHIFT' && /\bcover\b/i.test(entry?.notes ?? '')) {
            value = 'SHORTY :';
          }
          tableHTML += `
            <tr>
              <td class="px-3 py-2 border">${formatDateDM(entry.date)}</td>
              <!--<td class="px-3 py-2 border">${entry.shift_type || ""}</td>-->
              <td class="px-3 py-2 border">${value} ${entry.notes}</td>
            </tr>
          `;
        });

        tableHTML += `
              </tbody>
            </table>
          </div>
        `;

        noteContainer.innerHTML = tableHTML;
      }
    }
  } catch (err) {
    console.error(err);
    alert(err.message);
  }
}


async function updateEmployeeDropdown() {
  const shift = document.getElementById("shiftSelect")?.value || "";
  const empSelect = document.getElementById("employeeSelect");
  const grid = document.getElementById("calendarGrid");
   updateEmployeeSummary(empSelect);
  if (grid) grid.innerHTML = "";
  if (!shift || !empSelect) return;

  try {
    const res = await fetch(`/employees-by-shift?shift=${encodeURIComponent(shift)}`);
    if (!res.ok) throw new Error(`Failed to load employees: ${res.status}`);

    const employees = await res.json();
    empSelect.innerHTML = "";

    const defaultOption = document.createElement("option");
    defaultOption.value = "";
    defaultOption.textContent = "Select Employee";
    empSelect.appendChild(defaultOption);

    employees.forEach((emp) => {
      const option = document.createElement("option");
      option.value = emp.id;
      option.textContent = emp.name;
      empSelect.appendChild(option);
    });
  } catch (err) {
    console.error("Error updating employee dropdown:", err);
  }
}

// -------------------------------
// Employee Summary Section
// -------------------------------

// Ensure you have a container in your HTML somewhere
// <div id="summaryContainer" class="mt-4"></div>

async function updateEmployeeSummary(empId) {
  if (!empId) return;

  try {
    // Load employee config
    const configResp = await fetch(`configs/emp_${empId}.json?v=${Date.now()}`);
    const config = await configResp.json();

    // Load employee roster
    const rosterResp = await fetch(`configs/roster_${empId}.json?v=${Date.now()}`);
    const roster = await rosterResp.json();
    const year = parseInt(document.getElementById("yearSelect").value, 10);
    const month = parseInt(document.getElementById("monthSelect").value, 10);

    // get last day of selected month
    const lastDayOfMonth = new Date(year, month, 0); // month is 1-based
    const formatted = lastDayOfMonth.toLocaleDateString("en-NZ", {
      month: "short",
      year: "numeric"
    });

    const totals = getSeasonTotals(roster, config, lastDayOfMonth);

    // Calculate actual percent complete
    const percent = ((totals.minsSoFar / totals.totaltodo) * 100).toFixed(1);

    // 🔥 NEW: calculate expected percent by time elapsed in season
    const seasonStart = parseDateDDMMYYYY(config.season.start);
    const seasonEnd = parseDateDDMMYYYY(config.season.ends);

    const totalSeasonDays = (seasonEnd - seasonStart) / (1000 * 60 * 60 * 24);
    const daysIntoSeason = (lastDayOfMonth - seasonStart) / (1000 * 60 * 60 * 24);

    const expectedPercent = Math.min(
      100,
      ((daysIntoSeason / totalSeasonDays) * 100).toFixed(1)
    );


    // 🔥 Calculate difference between actual vs expected
    const diffPercent = (percent - expectedPercent).toFixed(1);

    // Convert percent gap into minutes, then hours
    const diffMins = Math.round((diffPercent / 100) * totals.totaltodo);
    const diffHours = (diffMins / 60).toFixed(1);

    let statusMsg = "";
    let statusColor = "";

    if (diffPercent > 0) {
      statusMsg = `✅ Ahead by ${diffPercent}% (${diffHours} h)`;
      statusColor = "text-green-700";
    } else if (diffPercent < 0) {
      statusMsg = `⚠️ Behind by ${Math.abs(diffPercent)}% (${Math.abs(diffHours)} h)`;
      statusColor = "text-red-700";
    } else {
      statusMsg = `⏺ On track (0%)`;
      statusColor = "text-gray";
    }

    // Render the summary
    const summary = document.getElementById("summaryContainer");
    summary.innerHTML = `
      <!-- import a handwriting font -->
      <link href="https://fonts.googleapis.com/css2?family=Gloria+Hallelujah&display=swap" rel="stylesheet">

      <div class="print:break-before-page relative bg-yellow-200 p-6 rounded-lg shadow-xl max-w-[600px] w-full transform rotate-[-0deg] font-['Gloria_Hallelujah']">
        <!-- tape strip -->
        <div class="absolute -top-3 left-1/2 -translate-x-1/2 bg-yellow-300 w-28 h-5 rounded-sm shadow rotate-[2deg]"></div>

        <!-- Title   📌 Summary -->
        <h1 class="text-xl font-bold mb-4 text-gray-800">
          <span class="block text-sm text-gray-700">to end of ${formatted}</span>
        </h1>

        <!-- Stats -->
        <div class="grid grid-cols-2 gap-4 mb-5">
          <div class="bg-yellow-100/60 p-3 rounded-md shadow-inner text-center">
            <p class="text-xs">ToDo</p>
            <p class="text-lg text-blue-700">${minToHrs(totals.totaltodo)}</p>
          </div>
          <div class="bg-yellow-100/60 p-3 rounded-md shadow-inner text-center">
            <p class="text-xs">Done</p>
            <p class="text-lg text-green-700">${minToHrs(totals.minsSoFar)}</p>
          </div>
          <div class="bg-yellow-100/60 p-3 rounded-md shadow-inner text-center">
            <p class="text-xs">Left</p>
            <p class="text-lg text-yellow-700">${minToHrs(totals.minsRemaining)}</p>
          </div>
          <div class="bg-yellow-100/60 p-3 rounded-md shadow-inner text-center">
            <p class="text-xs">Makeup</p>
            <p class="text-lg text-red-700">${totals.xtraShift} Covers</p>
          </div>
        </div>

        <!-- Progress bar (actual) -->
        <div class="mt-2 h-3 bg-yellow-100 rounded-full overflow-hidden shadow-inner border border-gray-400">
          <div class="h-full bg-gradient-to-r from-blue-400 to-green-400 transition-all duration-500 ease-out"
              style="width: ${percent}%"></div>
        </div>
        <p class="text-sm text-gray-800 mt-2 text-center">${percent}% complete</p>

        <!-- Expected progress bar -->
        <div class="mt-2 h-3 bg-yellow-100 rounded-full overflow-hidden shadow-inner border border-dashed border-gray-500">
          <div class="h-full bg-gradient-to-r from-purple-400 to-pink-400 transition-all duration-500 ease-out"
              style="width: ${expectedPercent}%"></div>
        </div>
        <p class="text-sm text-gray-600 mt-2 text-center">Should be at ${expectedPercent}%</p>
        <p class = "${statusColor}">${statusMsg}</p>
        </div>
    `;
  } catch (err) {
    console.error("Failed to load employee data or roster:", err);
  }
}

// Hook to select dropdown
document.getElementById("employeeSelect").addEventListener("change", e => {
  updateEmployeeSummary(e.target.value);
});

// Update summary on arrow key employee changes
function selectPreviousEmployee() {
  const select = document.getElementById("employeeSelect");
  if (!select) return;
  select.selectedIndex = Math.max(0, select.selectedIndex - 1);
  select.dispatchEvent(new Event("change"));
  updateEmployeeSummary(select.value);
}

function selectNextEmployee() {
  const select = document.getElementById("employeeSelect");
  if (!select) return;
  select.selectedIndex = Math.min(select.options.length - 1, select.selectedIndex + 1);
  select.dispatchEvent(new Event("change"));
  updateEmployeeSummary(select.value);
}


// --- helpers ---

function parseISO(d) {
  const nd = new Date(d);
  nd.setHours(0,0,0,0);
  return nd;
}

function formatNZ(d) {
  if (!d) return "-";
  return d.toLocaleDateString("en-NZ", { weekday: "short", day: "2-digit", month: "short", year: "numeric" });
}

// Sum all usable carryover mins (skip notes/invalids). Adjust the allowedKeys if you want to restrict.
function sumCarryoverMins(carryover) {
  if (!carryover || typeof carryover !== "object") return 0;
  let total = 0;
  for (const [k,v] of Object.entries(carryover)) {
    if (k === "_notes") continue;
    const n = Number(v);
    if (!Number.isFinite(n)) continue;
    total += n;
  }
  return total;
}

/**
 * Work backwards from season end and consume cover minutes on future rostered shifts.
 * Returns the first date you DO NOT need to work (i.e., the day after the last “covered” shift).
 */
function computeFinishDate(roster, coverMins, seasonEndDate) {
  if (!Array.isArray(roster) || !coverMins || coverMins <= 0) return null;

  const end = parseISO(seasonEndDate);
  // Consider only future shifts up to (and including) season end, that are real shifts
  const futureShifts = roster
    .filter(r => r && r.type_shift === "SHIFT" && r.on_shift && r.mins > 0 && parseISO(r.date) <= end)
    .sort((a,b) => parseISO(b.date) - parseISO(a.date)); // descending

  let remaining = coverMins;
  let lastCoveredShiftDate = null;

  for (const s of futureShifts) {
    remaining -= Number(s.mins) || 0;
    lastCoveredShiftDate = parseISO(s.date);
    if (remaining <= 0) break;
  }

  if (!lastCoveredShiftDate) return null; // nothing to cover

  // If we never exhausted the cover, you could stop even earlier than the earliest considered shift.
  // In that case we’ll still return the day after the last shift we looked at (earliest in list).
  const finish = new Date(lastCoveredShiftDate);
  finish.setDate(finish.getDate() - 1); // day BEFORE the last covered shift is your last working day
  return finish;
}




// Optional: initialize summary for currently selected employee
document.addEventListener("DOMContentLoaded", () => {
  const select = document.getElementById("employeeSelect");
  if (select && select.value) {
    updateEmployeeSummary(select.value);
  }
});
