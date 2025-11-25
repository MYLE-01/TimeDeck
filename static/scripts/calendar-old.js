// ===== Helpers =====
function minToHrs(mins) {
  if (typeof mins !== "number" || isNaN(mins) || mins === 0) return "0:00";
  const hours = Math.floor(mins / 60);
  const minutes = mins % 60;
  return `${hours}:${minutes.toString().padStart(2, "0")}`;
}

// Normalize shift codes
function Wordit(shift) {
  if (!shift) return "";
  if (shift.toUpperCase() === "N") return "Night";
  if (shift.toUpperCase() === "D") return "Day";
  if (shift.toLowerCase() === "night") return "Night";
  if (shift.toLowerCase() === "day") return "Day";
  return shift;
}

// Get cell background based on shift type
function normalizedShiftColor(shift_type) {
  if (shift_type === "Night") return "bg-blue-200";
  if (shift_type === "Day") return "bg-yellow-200";
  return "bg-white";
}

// Highlight paydays (every 14 days from 8 Feb 2022, Tuesday)
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

// ===== Load Calendar =====
async function loadCalendar() {
  const emp = document.getElementById("employeeSelect")?.value;
  const shiftFilter = document.getElementById("shiftSelect")?.value || "";
  const year = parseInt(document.getElementById("yearSelect")?.value, 10);
  const month = parseInt(document.getElementById("monthSelect")?.value, 10);

  if (!emp || !month || !year) return;

  const grid = document.getElementById("calendarGrid");
  const holidayList = document.getElementById("ShowHolidays");
  if (!grid) return;

  grid.innerHTML = "";
  if (holidayList) holidayList.innerHTML = "";

  try {
    const res = await fetch(`/calendar-data?emp_id=${emp}&shift=${encodeURIComponent(shiftFilter)}&month=${month}&year=${year}`);
    if (!res.ok) throw new Error(`Failed to load calendar data: ${res.status}`);
    const data = await res.json();

    // Show holidays
    const seenHolidays = new Set();
    data.forEach(entry => {
      if (entry.is_holiday && entry.holiday_name && !seenHolidays.has(entry.date) && holidayList) {
        const colorClass = normalizedShiftColor(Wordit(entry.shift_type));
        holidayList.innerHTML += `
          <div class="text-sm text-orange-600 flex items-center gap-2">
            <span class="px-2 py-0.5 rounded ${colorClass}">${Wordit(entry.shift_type) || "-"}</span>
            <span>${entry.date}: ${entry.holiday_name}</span>
          </div>
        `;
        seenHolidays.add(entry.date);
      }
    });

    // Fill empty cells for first day offset
    const firstDay = new Date(year, month - 1, 1).getDay();
    for (let i = 0; i < firstDay; i++) {
      grid.innerHTML += `<div class="h-24 border p-2 text-center rounded bg-gray-100"></div>`;
    }

    const daysInMonth = new Date(year, month, 0).getDate();
    const pad = n => String(n).padStart(2, "0");

    for (let d = 1; d <= daysInMonth; d++) {
      const entryRaw = data.find(e => new Date(e.date).getDate() === d) || {};
      const entry = {
        ID: entryRaw.ID || "",
        date: entryRaw.date || `${year}-${pad(month)}-${pad(d)}`,
        shift: entryRaw.shift || "",
        shift_type: Wordit(entryRaw.shift_type),
        type_shift: entryRaw.type_shift || "",
        mins: entryRaw.mins || 0,
        notes: entryRaw.notes || "",
        is_holiday: entryRaw.is_holiday || false,
        holiday_name: entryRaw.holiday_name || ""
      };

      const bgColor = normalizedShiftColor(entry.shift_type);
      const borderColor = entry.is_holiday ? "border-orange-500 border-2" : "";
      const isToday = new Date(entry.date).toDateString() === new Date().toDateString() ? "border-red-500 border-4" : "";
      const notesHtml = entry.notes ? `<div class="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-1 px-2 py-1 bg-black text-white text-xs rounded opacity-0 group-hover:opacity-100 pointer-events-none z-10 whitespace-nowrap">${entry.notes}</div>` : "";

      grid.innerHTML += `
        <div 
          data-id="${entry.ID}" 
          data-entry='${JSON.stringify(entry)}' 
          data-date="${entry.date}" 
          data-emp="${emp}" 
          data-shift_type="${entry.shift_type}" 
          data-type_shift="${entry.type_shift}" 
          class="relative group h-24 border p-2 text-center rounded flex flex-col justify-center ${bgColor} ${borderColor} ${isToday}"
        >
          <div class="font-bold">${isItPayDay(entry.date, d)}</div>
          ${entry.type_shift ? `<div>${entry.type_shift}</div>` : ""}
          ${notesHtml}
          ${entry.is_holiday && entry.holiday_name ? `<div class="text-xs text-orange-600 font-semibold">${entry.holiday_name}</div>` : ""}
          ${minToHrs(entry.mins) !== "0:00" ? `<div class="text-xs text-gray-500">(${minToHrs(entry.mins)})</div>` : ""}
        </div>
      `;
    }

    // Attach double-click listener for popup
    document.querySelectorAll("#calendarGrid > div[data-id]").forEach(cell => {
      cell.addEventListener("dblclick", () => {
        const empId = cell.getAttribute("data-emp");
        const entry = JSON.parse(cell.getAttribute("data-entry") || "{}");
        const normalizedEntry = {
          ID: entry.ID || "",
          date: entry.date || "",
          shift: entry.shift || "",
          shift_type: Wordit(entry.shift_type),
          type_shift: entry.type_shift || "",
          mins: entry.mins || 0,
          notes: entry.notes || ""
        };
        const config = { emp_name: empId };

        showTimeOffModal(
          empId,
          config,
          normalizedEntry.date,
          normalizedEntry.shift_type,
          [normalizedEntry],
          () => loadCalendar()
        );
      });
    });

  } catch (err) {
    console.error(err);
    alert(err.message);
  }
}

// ===== DOM Ready =====
document.addEventListener("DOMContentLoaded", () => {
  const monthSelect = document.getElementById("monthSelect");
  const yearSelect = document.getElementById("yearSelect");
  const today = new Date();

  if (!monthSelect.value) monthSelect.value = today.getMonth() + 1;
  if (!yearSelect.value) yearSelect.value = today.getFullYear();

  loadCalendar();

  document.getElementById("shiftSelect")?.addEventListener("change", loadCalendar);
  document.getElementById("employeeSelect")?.addEventListener("change", loadCalendar);
});
