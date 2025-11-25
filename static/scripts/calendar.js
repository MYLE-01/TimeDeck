// ==========================
// CALENDAR.JS
// ==========================


document.addEventListener("DOMContentLoaded", () => {
  const monthSelect = document.getElementById("monthSelect");
  const yearSelect = document.getElementById("yearSelect");
  const today = new Date();
  const empId = document.getElementById("employeeSelect")?.value;



  // Set defaults if empty
  if (!monthSelect.value) monthSelect.value = today.getMonth() + 1;
  if (!yearSelect.value) yearSelect.value = today.getFullYear();

  // Load initial calendar
  loadCalendar();
  


  document.getElementById("calendarGrid")?.addEventListener("click", e => {
  const cell = e.target.closest("[data-date]");
  if (!cell) return;

  selectedDate = cell.getAttribute("data-date"); // e.g., "2025-07-20"

  const empId = document.getElementById("employeeSelect")?.value;
  if (!empId) {
    alert("Please select an employee first!");
    return;
  }






  document.querySelectorAll("#calendarGrid [data-date]").forEach(c => c.classList.remove("ring-2", "ring-blue-500"));
  cell.classList.add("ring-2", "ring-blue-500");


  const clickedDate = cell.dataset.date;
  updateEmployeeSummary(empId, clickedDate);
  loadTimelineBlock(empId);
  //console.log("Clicked date:", clickedDate);
  //console.log("shifts from server:", shifts);
  const shiftsContainer = document.getElementById("Shifts");
  shiftsContainer.innerHTML = `${formatDateDDMMMYY(clickedDate)} =>`; // clear previous

  shifts.forEach(shift => {
    const data = getShiftTodayData(shift, clickedDate); // pass clickedDate
    const div = document.createElement("div");
    div.className = "inline-block px-1 py-1 rounded-full " + data.labelback; // compact layout
    div.innerHTML = ` ${shift.name} `;
    shiftsContainer.appendChild(div);
  });

  });

  
  
  
  // -----------------------------
  // Calendar cell double-click
  // -----------------------------

  document.addEventListener("dblclick", async (e) => {
    const cell = e.target.closest("[data-id], [data-has_data]");
    if (!cell) return;

    const { date, shift, has_data } = cell.dataset;
    const empId = document.getElementById("employeeSelect").value;
    if (!empId) {
      alert("Please select an employee first!");
      return;
    }

    try {
      // Fetch employee config
      const configRes = await fetch(`/api/configs/emp_${empId}.json?v=${Date.now()}`);
      if (!configRes.ok) throw new Error(`Config fetch failed: ${configRes.status}`);
      const config = await configRes.json();

      // Case 1: existing data
      if (has_data === "true") {
        const rosterRes = await fetch(`/api/configs/roster_${empId}.json?v=${Date.now()}`);
        if (!rosterRes.ok) throw new Error(`Roster fetch failed: ${rosterRes.status}`);
        const roster = await rosterRes.json();

        let shiftType = cell.dataset.shiftType || cell.dataset.type || shift || "";
        let entry = roster.find(r => r.date === date && r.shift_type === shiftType);

        // Fallback: match by date only, then infer shiftType from entry
        if (!entry) {
          entry = roster.find(r => r.date === date);
          if (entry) shiftType = entry.shift_type;
        }

        if (!entry) {
          console.warn(`⚠️ No roster entry found for ${date} / ${shiftType}`);
        }

        showTimeOffModal(empId, config, date, shiftType, roster, () => {
          loadCalendar();
          updateEmployeeSummary(empId);
          updateCalendarHeader();
        });
      }

      // Case 2: no data → create new record
      else {
        console.log("No existing data, opening modal for NEW record...");
        const shiftType = cell.dataset.shiftType || cell.dataset.type || shift || "";
        showTimeOffModal(empId, config, date, shiftType, [], () => {
          updateEmployeeSummary(empId);
          updateCalendarHeader();
          loadCalendar();
        });
      }

    } catch (err) {
      console.error("❌ Failed to load config/roster:", err);
      alert("Could not load employee data. Please check the config files or try again.");
    }
  });


  // -----------------------------
  // Shift dropdown listener
  // -----------------------------
  document.getElementById("shiftSelect")?.addEventListener("change", updateEmployeeDropdown);

  // -----------------------------
  // Employee dropdown listener
  // -----------------------------
document.getElementById("employeeSelect")?.addEventListener("change", e => {
  const empId = e.target.value;
  // console.log("🔄 Employee changed to:", empId);
  updateEmployeeSummary(empId);


});


  // -----------------------------
  // Initialize summary for selected employee
  // -----------------------------
  const select = document.getElementById("employeeSelect");
  if (select && select.value) {
    updateEmployeeSummary(select.value);
  }
  
});

// ==========================
// LOAD CALENDAR
// ==========================
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

    // leave Stuff
    const leaveEntries = data.leave_entries || [];


    renderPacingCard(data.pacing, emp,data.winter_mins,data.season_mins,data.PSL);

    function getBgColor(entry) {
      if (!entry) return "bg-white";
      const { shift_type } = entry;
      if (shift_type === "N") return "bg-blue-200";
      if (shift_type === "D") return "bg-yellow-200";
      return "bg-white";
    }

    function getLeaveColor(entry) {
      const status = entry.coverage_status || "";
      if (status === "covered") return "bg-green-200";
      if (status === "approved") return "bg-amber-200";
      if (status === "pending") return "bg-yellow-200";
      return "bg-gray-200";
    }

    function getLeaveGradient(status, shiftType) {
      const base = shiftType === "N" ? "from-blue-300" : "from-yellow-300";

      if (status === "covered") return `bg-gradient-to-b ${base} to-green-300`;
      if (status === "approved") return `bg-gradient-to-b ${base} to-amber-300`;
      if (status === "pending") return `bg-gradient-to-b ${base} to-yellow-300`;
      return `bg-gradient-to-b ${base} to-gray-300`;
    }



    // Build holiday list once
    const seenHolidays = new Set();
    if (holidayList) {
      data.entries.forEach(entry => {
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

    // Build calendar grid
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
      const basePayday = new Date(2022, 1, 8);
      const cleanCheck = new Date(checkDate.getFullYear(), checkDate.getMonth(), checkDate.getDate());
      const msInDay = 24 * 60 * 60 * 1000;
      const daysDiff = Math.floor((cleanCheck - basePayday) / msInDay);
      return daysDiff % 14 === 0 && cleanCheck.getDay() === 2
        ? `<span class="text-orange-600 font-semibold">${dayNumber}</span>`
        : dayNumber;
    }

    function formatDateDM(dateStr) {
      const d = new Date(dateStr);
      if (isNaN(d)) return dateStr;
      const day = String(d.getDate()).padStart(2, "0");
      const month = d.toLocaleString("en-US", { month: "short" });
      return `${day}-${month}`;
    }

    const pad = (n) => String(n).padStart(2, "0");

    for (let d = 1; d <= daysInMonth; d++) {
      const dayEntries = data.entries.filter(e => new Date(e.date).getDate() === d);
      const cellDate = `${year}-${pad(month)}-${pad(d)}`;
      // leave stuff
      const dayLeaves = leaveEntries.filter(e => e.date === cellDate);

      const totalMins = dayEntries.reduce((sum, e) => sum + (e.shift_minutes || 0), 0);
      const labels = dayEntries.filter(e => e.type_shift && e.type_shift !== "SHIFT").map(e => e.type_shift);
      const labeledNotes = dayEntries.filter(e =>
        e.type_shift && e.type_shift !== "SHIFT" && e.notes && e.notes.trim()
      );
      // leave stuff
      //const leaveColor = dayLeaves.length ? getLeaveColor(dayLeaves[0]) : null;
      //const bgColor = leaveColor || getBgColor(dayEntries.find(e => e.type_shift !== "SHIFT") || dayEntries[0]);
      const firstLeave = Array.isArray(dayLeaves) && dayLeaves.length ? dayLeaves[0] : null;
      const firstEntry = Array.isArray(dayEntries) && dayEntries.length ? dayEntries[0] : null;

      const leaveShiftType = firstLeave?.shift_type || firstEntry?.shift_type || "";
      //console.log("=====>", leaveShiftType);
      const leaveGradient = firstLeave ? getLeaveGradient(firstLeave.coverage_status, leaveShiftType) : null;

      const bgColor = leaveGradient || getBgColor(dayEntries?.find(e => e.type_shift !== "SHIFT") || firstEntry);
      // const bgColor = dayEntries.length ? getBgColor(dayEntries[0]) : "bg-white";
      const borderColor = dayEntries.some(e => e.is_holiday) ? "border-orange-500 border-2" : "";

      const isToday = new Date(cellDate).toDateString() === new Date().toDateString()
        ? "border-red-500 border-4"
        : "";

      const has_data = dayEntries.length > 0 ? "true" : "false";
      const empAttr = document.getElementById("employeeSelect")?.value || "";

      const shiftEntry = dayEntries.find(e => e.type_shift === "SHIFT") || dayEntries[0] || {};
      const shiftType = shiftEntry.shift_type || "";
      const type = shiftEntry.type_shift || "";

      // 📝 Tooltip logic: grab first non-empty notes
      const labelNotePairs = labeledNotes.map(e =>
        `${e.type_shift} : ${e.notes.replace(/"/g, '&quot;')}`
      );


      const tooltip = labelNotePairs.length
        ? labelNotePairs.join('\n')
        : "";


      const notesHtml = tooltip
        ? `<div class="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-1 px-3 py-2 bg-black text-white text-xs rounded opacity-0 group-hover:opacity-100 pointer-events-none z-10 whitespace-pre-line break-words max-w-xl min-w-[150px] text-left tooltip-with-arrow">
            ${tooltip}
          </div>`
        : "";



      grid.innerHTML += `
        <div data-has_data="${has_data}" data-emp="${empAttr}" data-date="${cellDate}"
            
            class="relative group h-24 border p-2 text-center rounded flex flex-col justify-center ${bgColor} ${borderColor} ${isToday}">
            ${notesHtml}
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
      const monthNotes = data.entries.filter(e => e.notes && e.date.startsWith(`${year}-${pad(month)}`));
      if (monthNotes.length === 0) {
        noteContainer.innerHTML = "";
      } else {
        let tableHTML = `
          <h3 class="text-lg font-semibold mb-2">Notes / Comments for the Month</h3>
          <div class="overflow-x-auto">
            <table class="min-w-full border border-gray-300 rounded-lg shadow-sm text-sm">
              <thead class="bg-gray-200 text-gray-700">
                <tr>
                  <th class="px-3 py-2 border">Date</th>
                  <th class="px-3 py-2 border">Note / Comments</th>
                </tr>
              </thead>
              <tbody>
        `;

        monthNotes.forEach(entry => {
          let value = '';
          if (entry.type_shift === 'SHIFT' && /\bcover\b/i.test(entry?.notes ?? '')) {
            value = 'SHORTY :';
          }
          tableHTML += `
            <tr>
              <td class="px-3 py-2 border">${formatDateDM(entry.date)}</td>
              <td class="px-3 py-2 border">${value} ${entry.type_shift} : ${entry.notes} <span class="text-xs text-gray-500 ml-2"> ${minToHrs(entry.shift_minutes)}</span></td>
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

// ==========================
// UPDATE EMPLOYEE DROPDOWN
// ==========================
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

    employees.forEach(emp => {
      const option = document.createElement("option");
      option.value = emp.id;
      option.textContent = emp.name;
      empSelect.appendChild(option);
    });
  } catch (err) {
    console.error("Error updating employee dropdown:", err);
  }
}

// ==========================
// UPDATE EMPLOYEE SUMMARY
// ==========================
async function updateEmployeeSummary(empId , overrideDate = null) {
  if (!empId) return;

  try {
    const config = await fetch(`/api/configs/emp_${empId}.json?v=${Date.now()}`).then(res => res.json());
    const roster = await fetch(`/api/configs/roster_${empId}.json?v=${Date.now()}`).then(res => res.json());

    const year = parseInt(document.getElementById("yearSelect").value, 10);
    const month = parseInt(document.getElementById("monthSelect").value, 10);

    //const today = new Date();
    //const isCurrentMonth = year === today.getFullYear() && month === (today.getMonth() + 1);
    //const referenceDate = isCurrentMonth ? today : new Date(year, month, 0);

    const today = new Date();
    const referenceDate = overrideDate
      ? new Date(overrideDate)
      : (year === today.getFullYear() && month === (today.getMonth() + 1))
        ? today
        : new Date(year, month, 0);



    const formattedDate = overrideDate
      ? `as of ${referenceDate.toLocaleDateString("en-NZ", { day: "numeric", month: "short", year: "numeric" })}`
      : `to end of ${referenceDate.toLocaleDateString("en-NZ", { month: "short", year: "numeric" })}`;
    const totals = getSeasonTotals(roster, config, referenceDate, true);

    const rosterStart = parseDateDDMMYYYY(config.season.roster_first_day || config.season.start);
    const rosterStartStr = rosterStart.toLocaleDateString("en-NZ", { day: "numeric", month: "short", year: "numeric" });
    //console.log(config)
    const rawEndDate = config.season.roster_first_day || config.season.ends || "";
    const rosterEnd = rawEndDate ? parseDateDDMMYYYY(rawEndDate) : null;
    const rosterEndStr = rosterEnd
      ? rosterEnd.toLocaleDateString("en-NZ", { day: "numeric", month: "short", year: "numeric" })
      : "N/A";

    
    let statusMsg = "";
    let statusColor = "";
    // chnage the < to > to it look right
    if (totals.behindPct > 0) {
      statusMsg = `✅ Ahead by ${Math.abs(totals.behindPct)}% (${totals.display.behindHours} h)`;
      statusColor = "text-green-700";
    } else if (totals.behindPct < 0) {
      statusMsg = `⚠️ Behind by ${totals.behindPct}% (${totals.display.behindHours} h)`;
      statusColor = "text-red-700";
    } else {
      statusMsg = `⏺ On track (0%)`;
      statusColor = "text-gray";
    }

    const summary = document.getElementById("summaryContainer");

    summary.innerHTML = `
      <link href="https://fonts.googleapis.com/css2?family=Gloria+Hallelujah&display=swap" rel="stylesheet">
      <div class="print:break-before-page relative bg-yellow-200 p-6 rounded-lg shadow-xl max-w-[600px] w-full transform rotate-[-0deg] font-['Gloria_Hallelujah']">
        <div class="absolute -top-3 left-1/2 -translate-x-1/2 bg-yellow-300 w-28 h-5 rounded-sm shadow rotate-[2deg]"></div>
        <h1 class="text-xl font-bold mb-4 text-gray-800">
          <span class="block text-sm text-gray-700">${formattedDate}</span>
          <span class="block text-sm text-gray-700">Night shift hours are counted toward the next calendar day</span>
        </h1>

        <div class="text-xs text-gray-600 italic mb-4 text-center">
          🧠 Roster-aware tracking enabled<br>
          Season From : ${rosterStartStr} to ${rosterEndStr}
        </div>

        <div class="grid grid-cols-2 gap-4 mb-5">
          <div class="bg-yellow-100/60 p-3 rounded-md shadow-inner text-center">
            <p class="text-xs">ToDo</p>
            <p class="text-lg text-blue-700">${totals.display.totalToDo}</p>
          </div>
          <div class="bg-yellow-100/60 p-3 rounded-md shadow-inner text-center">
            <p class="text-xs">Done</p>
            <p class="text-lg text-green-700">${totals.display.totalSoFar}</p>
          </div>
          <div class="bg-yellow-100/60 p-3 rounded-md shadow-inner text-center">
            <p class="text-xs">Left</p>
            <p class="text-lg text-yellow-700">${totals.display.totalRemaining}</p>
          </div>
          <div class="bg-yellow-100/60 p-3 rounded-md shadow-inner text-center">
            <p class="text-xs">Makeup</p>
            <p class="text-lg ${totals.xtraShift < 0 ? 'text-green-700' : 'text-red-700'}">
            ${totals.xtraShift < 0 ? "✅ Covers Complete" : `${totals.xtraShift} Covers`}
            </p>

          </div>
        </div>

        <div class="mt-2 h-3 bg-yellow-100 rounded-full overflow-hidden shadow-inner border border-gray-400">
          <div class="h-full bg-gradient-to-r from-blue-400 to-green-400 transition-all duration-500 ease-out"
              style="width: ${totals.progressPct}%"></div>
        </div>
        <p class="text-sm text-gray-800 mt-2 text-center">${totals.display.progressPctText}</p>

        ${totals.isTemp ? `
          <p class="text-sm text-gray-500 mt-2 text-center">📅 Temp staff pacing not tracked</p>
        ` : `
          <div class="mt-2 h-3 bg-yellow-100 rounded-full overflow-hidden shadow-inner border border-dashed border-gray-500">
            <div class="h-full bg-gradient-to-r from-purple-400 to-pink-400 transition-all duration-500 ease-out"
                style="width: ${totals.expectedPct}%"></div>
          </div>
          <p class="text-sm text-gray-600 mt-2 text-center">${totals.display.expectedPctText}</p>
          <p class="${statusColor}">${statusMsg}</p>
        `}
      </div>
    `;
// put it here a 
// 🔔 Fetch and show incoming cover requests
  fetch(`/incoming-cover-requests?emp_id=${empId}`)
    .then(res => res.json())
    .then(data => {
      data.incoming_requests.forEach(req => {
        const alreadyDeclined = Array.isArray(req.decline_by) && req.decline_by.includes(empId);
        if (alreadyDeclined) return;

        showPopup({
          message: `${req.requested_name} has requested cover\nfor ${req.day_name}, ${formatDateDM(req.date)} (${req.shift_type} Shift).\nIt’s your ${req.off_day_label}.`,
          actions: [
            { label: "Accept", onClick: () => submitCoverRequest(req, "covered") },
            { label: "Decline", onClick: () => submitCoverRequest(req, "decline") },
            { label: "x", onClick: () => '' }
          ]
        });
      });
    })
    .catch(err => {
      console.error("Failed to fetch incoming cover requests:", err);
    });


  } catch (err) {
    console.error("Failed to load employee data or roster:", err);
  }
loadTimelineBlock(empId);
}


function selectNextEmployee() {
  const select = document.getElementById("employeeSelect");
  if (!select) return;
  select.selectedIndex = Math.min(select.options.length - 1, select.selectedIndex + 1);
  select.dispatchEvent(new Event("change"));
  updateEmployeeSummary(select.value);
}

// ==========================
// HELPER FUNCTIONS
// ==========================
function parseISO(d) {
  const nd = new Date(d);
  nd.setHours(0,0,0,0);
  return nd;
}

function formatNZ(d) {
  if (!d) return "-";
  return d.toLocaleDateString("en-NZ", { weekday: "short", day: "2-digit", month: "short", year: "numeric" });
}

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

function computeFinishDate(roster, coverMins, seasonEndDate) {
  if (!Array.isArray(roster) || !coverMins || coverMins <= 0) return null;

  const end = parseISO(seasonEndDate);
  const futureShifts = roster
    .filter(r => r && r.type_shift === "SHIFT" && r.on_shift && r.mins > 0 && parseISO(r.date) <= end)
    .sort((a,b) => parseISO(b.date) - parseISO(a.date)); 

  let remaining = coverMins;
  let lastCoveredShiftDate = null;

  for (const s of futureShifts) {
    remaining -= Number(s.mins) || 0;
    lastCoveredShiftDate = parseISO(s.date);
    if (remaining <= 0) break;
  }

  if (!lastCoveredShiftDate) return null;

  const finish = new Date(lastCoveredShiftDate);
  finish.setDate(finish.getDate() - 1);
  return finish;
}

function renderPacingCard(pacing, empId,winter_mins,season_mins,PSL) {
  const pacingContainer = document.getElementById("pacingContainer");
  pacingContainer.innerHTML = ""; // Clear previous content

  const empPacing = pacing[empId];
  //console.log("empPacing",pacing[empId]);
  if (!empPacing || Object.keys(empPacing).length === 0) {
    const card = document.createElement("div");
    card.className = "bg-gray-100 p-4 rounded shadow";

    const message = document.createElement("p");
    message.className = "text-sm text-gray-500 italic";
    message.textContent = "No entitlements configured for this employee.";

    card.appendChild(message);
    pacingContainer.appendChild(card);
    return;
  }


  const card = document.createElement("div");
  card.className = "bg-gray-100 p-4 rounded shadow";

  // Details container (initially hidden)
  const detailsContainer = document.createElement("div");
  detailsContainer.id = "pacingDetails";
  detailsContainer.style.display = "none";

  // Day length toggle dropdown
  const dayLengthToggleWrapper = document.createElement("div");
  dayLengthToggleWrapper.className = "mb-2";
  const winter = winter_mins / 60;
  const season = season_mins / 60;
  dayLengthToggleWrapper.innerHTML = `
    <fieldset class="mb-2">
      <!-- <legend class="font-medium mb-1">Day length:</legend>-->
      <label class="mr-4">
        <input type="radio" name="dayLength" value="${season_mins}" checked>
        ${season} - hour day
      </label>
      <label>
        <input type="radio" name="dayLength" value="${winter_mins}">
        ${winter} - hour day
      </label>
    </fieldset>
  `;

  detailsContainer.appendChild(dayLengthToggleWrapper);

  // Breakdown lines
  const renderBreakdown = (dayLength) => {
  detailsContainer.querySelectorAll(".pacing-line, hr, button, span").forEach(el => el.remove());

  Object.entries(empPacing).forEach(([code, info]) => {
    const line = document.createElement("div");
    line.className = "mb-1 flex justify-between items-center pacing-line";

    const label = document.createElement("span");
    const usedStr = minToHrs(info.used);
    const entitledStr = minToHrs(info.entitled);
    const remaining = info.entitled - info.used;
    const remainingDays = minToDays(Math.abs(remaining), dayLength);

    // Main breakdown line
    label.textContent = info.used
      ? remaining < 0
        ? `${code} : ${usedStr} / ${entitledStr} = Ahead by ${remainingDays} day(s)`
        : `${code} : ${usedStr} / ${entitledStr} = ${remainingDays} day(s) remaining`
        : `${code} : ${entitledStr} = ${minToDays(info.entitled, dayLength)} day(s)`;

    const badge = document.createElement("span");
    badge.textContent = info.status;
    badge.className = {
      "✅ Ahead": "text-green-600 font-bold",
      "⚠️ Close": "text-yellow-600 font-bold",
      "❌ Overdrawn": "text-red-600 font-bold"
    }[info.status] || "text-gray-600";

    line.appendChild(label);
    line.appendChild(badge);
    detailsContainer.appendChild(line);

    // 🟢 Ahead line (extra insight)
  
    const aheadMins = info.used - info.entitled;
    //console.log(`${code} used: ${info.used}, entitled: ${info.entitled}, aheadMins: ${aheadMins}`);
    if (aheadMins > 0) {
      const aheadLine = document.createElement("div");
      aheadLine.className = "mb-1 flex justify-between items-center text-green-700 text-sm pacing-line";

      aheadLine.innerHTML = `
        <span>${code} is ahead by ${minToHrs(aheadMins)} → ${minToDays(aheadMins, dayLength)} day(s) available to take</span>
        <span class="font-bold">🟢</span>
      `;
      detailsContainer.appendChild(aheadLine);

    }




  });

  // Request leave link
  // Create wrapper span
  if (showLeave) {
    const requestleaveLink = document.createElement("span");
    requestleaveLink.className = "px-4 py-2 bg-amber-500 hover:bg-amber-600 text-white rounded shadow";

    requestleaveLink.button = document.createElement("button");
    requestleaveLink.button.onclick = goToLeaveRequestScreen;
    requestleaveLink.button.innerHTML = `📝 Request Some Leave`;

    
    requestleaveLink.appendChild(requestleaveLink.button);
    detailsContainer.appendChild(requestleaveLink);

    const suggestleaveLink = document.createElement("span");
    suggestleaveLink.className = "px-4 py-2 bg-amber-500 hover:bg-amber-600 text-white rounded shadow ml-4";

    suggestleaveLink.button = document.createElement("button");
    suggestleaveLink.button.onclick = goToLeavesuggestedScreen;
    suggestleaveLink.button.innerHTML = `📝 Suggested Covers`;

    suggestleaveLink.appendChild(suggestleaveLink.button);
    detailsContainer.appendChild(suggestleaveLink);
  }  

  // PSL specific line
  // Add visual separator before PSL

  const divider = document.createElement("hr");
  divider.className = "my-2 border-gray-300";
  detailsContainer.appendChild(divider);

  // 🔒 Fixed 8-hour day for PSL
  if (PSL && typeof PSL.used === "number" && typeof PSL.entitled === "number") {
    const pslDayLength = 480; // 8 hours in minutes
    const usedStr = minToHrs(PSL.used);
    const entitledStr = minToHrs(PSL.entitled);
    const remaining = PSL.entitled - PSL.used;
    const remainingDays = minToDays(Math.abs(remaining), pslDayLength);

    const line = document.createElement("div");
    line.className = "mb-1 flex justify-between items-center pacing-line";

    const label = document.createElement("span");
    label.textContent = PSL.used
      ? remaining < 0
        ? `PSL : ${usedStr} / ${entitledStr} = Ahead by ${remainingDays} day(s)`
        : `PSL : ${usedStr} / ${entitledStr} = ${remainingDays} day(s) remaining`
        : `PSL : ${entitledStr} = ${minToDays(PSL.entitled, pslDayLength)} day(s)`;

    const badge = document.createElement("span");
    badge.textContent = PSL.status || "";
    badge.className = {
      "✅ Ahead": "text-green-600 font-bold",
      "⚠️ Close": "text-yellow-600 font-bold",
      "❌ Overdrawn": "text-red-600 font-bold"
    }[PSL.status] || "text-gray-600";

    line.appendChild(label);
    line.appendChild(badge);
    detailsContainer.appendChild(line);
  }



  };

  // Initial render with default 12hr day
  renderBreakdown(season_mins);

  // Title with toggle button and dynamic totalDays
  const totalMins = Object.values(empPacing).reduce((sum, info) => sum + (info.entitled - info.used), 0);
  const totalDays = minToDays(totalMins, season_mins);


  const title = document.createElement("h3");
  title.className = "text-lg font-semibold mb-2 flex items-center gap-2";
  title.innerHTML = `
    <span>Leave Pacing Summary – ${totalDays} day(s) remaining</span>
    <button id="togglePacing" class="text-sm text-blue-600 underline flex items-center">
      <span id="arrowIcon" class="transition-transform duration-300 rotate-0">▼</span>
      <span class="ml-1">Show details</span>
    </button>
  `;
  card.appendChild(title);
  card.appendChild(detailsContainer);

  // Toggle logic
  const toggleBtn = card.querySelector("#togglePacing");
  const arrowIcon = card.querySelector("#arrowIcon");
  const labelSpan = toggleBtn.querySelector("span:nth-child(2)");

  if (toggleBtn && arrowIcon && labelSpan) {
    toggleBtn.addEventListener("click", () => {
      const isVisible = detailsContainer.style.display === "block";
      detailsContainer.style.display = isVisible ? "none" : "block";
      labelSpan.textContent = isVisible ? "Show details" : "Hide details";
      arrowIcon.classList.toggle("rotate-180");
    });
  }

  // Re-render breakdown on day length change

  const radioButtons = dayLengthToggleWrapper.querySelectorAll('input[name="dayLength"]');
  radioButtons.forEach(radio => {
    radio.addEventListener("change", () => {
      const newDayLength = parseInt(radio.value, 10);
      renderBreakdown(newDayLength);
    });
  });

  pacingContainer.appendChild(card);
}


function formatDateDM(dateStr) {
  const d = new Date(dateStr);
  if (isNaN(d)) return dateStr;
  const day = String(d.getDate()).padStart(2, "0");
  const month = d.toLocaleString("en-US", { month: "short" });
  return `${day}-${month}`;
}

function showPopup({ message, actions }) {
  // Remove any existing banner
  const existing = document.getElementById("coverBanner");
  if (existing) existing.remove();

  const banner = document.createElement("div");
  banner.id = "coverBanner";
  //banner.className = "fixed top-5 left-0 right-0 bg-blue-600 text-white px-4 py-3 shadow-lg z-[1000] flex justify-between items-center";
  banner.className = "fixed top-5 left-5 right-5 bg-blue-600 text-white px-4 py-3 shadow-lg z-[1000] flex justify-between items-center rounded-lg";
  
  const msg = document.createElement("span");
  msg.className = "text-sm font-medium whitespace-pre-line";
  msg.textContent = message;

  const buttons = document.createElement("div");
  buttons.className = "flex gap-2";

  actions.forEach(({ label, onClick }) => {
    const btn = document.createElement("button");
    btn.className = "bg-white text-blue-600 px-3 py-1 rounded font-semibold hover:bg-blue-100";
    btn.textContent = label;
    btn.onclick = () => {
      onClick?.();
      banner.remove(); // remove banner after action
    };
    buttons.appendChild(btn);
  });

  banner.appendChild(msg);
  banner.appendChild(buttons);
  document.body.appendChild(banner);
}

function submitCoverRequest(data, status) {
  const formData = new URLSearchParams();
  formData.append("cover_by", data.cover_by);
  formData.append("shift_cover", data.shift_name);
  formData.append("date", data.date);
  formData.append("emp_id", data.requested_by);
  formData.append("coverage_status", status);
  formData.append("Popup",1)

  fetch("/request-cover", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: formData.toString()
  })
  .then(res => {
    if (!res.ok) throw new Error("Failed to submit");
    return res.json();
  })
  .then(() => {
    showPopup({
      message: `✅ Your  ${status} request submitted for ${formatDateDM(data.date)} (${data.shift_name})`,
      actions: [{ label: "OK", onClick: () => {} }]
    });
  })
  .catch(err => {
    showPopup({
      message: `❌ Error: ${err.message}`,
      actions: [{ label: "Retry", onClick: () => submitCoverRequest(data, status) }]
    });
  });
}

function closeCoverPanel(button) {
  const panel = button.closest('.cover-panel-enter');
  if (!panel) return;

  panel.classList.remove('cover-panel-enter');
  panel.classList.add('cover-panel-exit');

  setTimeout(() => {
    panel.closest('.fixed')?.remove();
  }, 300); // match fadeSlideOut duration
}


function openCoverRequestPanel(requests) {
  const container = document.createElement("div");
  container.className = "fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50";

  const panel = document.createElement("div");
  panel.className = "bg-white rounded-lg shadow-lg p-6 max-w-xl w-full cover-panel-enter";

  panel.innerHTML = `
    <h2 class="text-lg font-semibold mb-4">Incoming Cover Requests</h2>
    <div class="space-y-4">
      ${requests.map(req => `
        <div class="border rounded p-3 bg-gray-50">
          <p><strong>${req.requested_name}</strong> → ${req.day_name}, ${formatDateDM(req.date)} (${req.shift_type})</p>
          <p class="text-sm text-gray-600">It’s your ${req.off_day_label}</p>
          <div class="mt-2 flex gap-2">
            <button class="px-3 py-1 bg-green-500 text-white rounded" onclick="submitCoverRequest(${JSON.stringify(req)}, 'covered')">Accept</button>
            <button class="px-3 py-1 bg-red-500 text-white rounded" onclick="submitCoverRequest(${JSON.stringify(req)}, 'decline')">Decline</button>
          </div>
        </div>
      `).join("")}
    </div>
    <div class="mt-4 text-right">
      <button class="px-4 py-2 bg-gray-300 rounded" onclick="closeCoverPanel(this)">Close</button>
    </div>
  `;

  container.appendChild(panel);
  document.body.appendChild(container);
}
async function loadTimelineBlock(empId) {
  try {
    const res = await fetch(`/timeline-block/${empId}`);
    const html = await res.text();
    document.getElementById("timelineBlock").innerHTML = html;
  } catch (err) {
    console.error("Failed to load timeline block:", err);
  }
}
