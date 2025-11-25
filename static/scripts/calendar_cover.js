// static/scripts/calendar_cover.js
document.addEventListener("DOMContentLoaded", () => {
  loadCoverCalendar();
});

// Navigate months from the UI arrows
function changeMonth(offset) {
  const monthSelect = document.getElementById("monthSelect");
  const yearSelect = document.getElementById("yearSelect");
  let month = parseInt(monthSelect.value, 10);
  let year = parseInt(yearSelect.value, 10);
  month += offset;
  if (month < 1) { month = 12; year--; }
  if (month > 12) { month = 1; year++; }
  monthSelect.value = month;
  yearSelect.value = year;
  loadCoverCalendar();
}

// Fetch and render for the selected year/month/filters
async function loadCoverCalendar() {
  const year = document.getElementById("yearSelect").value;
  const month = document.getElementById("monthSelect").value;
  const selectedShift = document.getElementById("shiftSelect").value;
  const selectedDept = document.getElementById("deptSelect").value;
  try {
    const res = await fetch(`/cover-report?month=${month}&year=${year}`, { cache: "no-store" });
    if (!res.ok) throw new Error(`Failed to load cover data: ${res.status}`);
    const payload = await res.json();
    const data = payload.report || {};
    const callbacks = payload.callbacks || {};
    renderCalendarGrid(data, year, month, selectedShift, selectedDept);
    renderSummaryTable(data, year, month, selectedShift, selectedDept);
    renderCallbackStats(callbacks, document.getElementById("callbackStats"));
    updateHeader(year, month, selectedShift, selectedDept);
    // console.log("✅ Cover data loaded for", month, year);
  } catch (err) {
    console.error("❌ Cover calendar error:", err);
    alert("Could not load cover data");
  }
}

// Header label (Month Year – optional Shift – optional Dept)
function updateHeader(year, month, shift, dept) {
  const header = document.getElementById("calendarMonthYear");
  const monthName = new Date(year, month - 1).toLocaleString("default", { month: "long" });
  let label = `${monthName} ${year}`;
  if (shift) label += ` – ${shift}`;
  if (dept) label += ` – ${dept}`;
  header.textContent = label;
}

// Aggregate coverage for a given date across shifts/departments as needed
function aggregateCoverage(data, dateStr, selectedShift, selectedDept) {
  const day = data[dateStr];
  if (!day) return { expected: 0, actual: 0, missing: 0, extra: 0, coverage: 0 };
  let expected = 0, actual = 0;
  const add = (e, a) => { expected += e || 0; actual += a || 0; };

  if (selectedShift) {
    const s = day[selectedShift];
    if (!s) return { expected: 0, actual: 0, missing: 0, extra: 0, coverage: 0 };
    if (selectedDept) {
      const rec = s.departments?.[selectedDept];
      if (rec) add(rec.expected, rec.actual);
    } else {
      const t = s.totals;
      if (t) add(t.expected, t.actual);
    }
  } else {
    // All shifts on that day
    for (const sName in day) {
      const s = day[sName];
      if (selectedDept) {
        const rec = s.departments?.[selectedDept];
        if (rec) add(rec.expected, rec.actual);
      } else {
        const t = s.totals;
        if (t) add(t.expected, t.actual);
      }
    }
  }

  const missing = Math.max(0, expected - actual);
  const extra = Math.max(0, actual - expected);
  const coverage = expected > 0 ? Math.round((actual / expected) * 1000) / 10 : 0; // 1dp
  return { expected, actual, missing, extra, coverage };
}

// For shift indicator (use left border color, not background)
function getShiftType(data, dateStr, shift) {
  const raw = shift ? (data[dateStr]?.[shift]?.shift_type || "") : "";
  const norm = String(raw).trim().toLowerCase();
  if (norm.startsWith("night") || norm === "n" || norm === "night shift") return "Night";
  if (norm.startsWith("day") || norm === "d" || norm === "day shift") return "Day";
  return "";
}

function renderCalendarGrid(data, year, month, selectedShift, selectedDept) {
  const grid = document.getElementById("calendarGrid");
  grid.innerHTML = "";

  const firstDay = new Date(year, month - 1, 1).getDay();
  for (let i = 0; i < firstDay; i++) {
    // Invisible placeholder to align grid
    const ph = document.createElement("div");
    ph.style.visibility = "hidden";
    grid.appendChild(ph);
  }

  const daysInMonth = new Date(year, month, 0).getDate();
  const pad = (n) => String(n).padStart(2, "0");

  for (let d = 1; d <= daysInMonth; d++) {
    const dateStr = `${year}-${pad(month)}-${pad(d)}`;
    const rec = aggregateCoverage(data, dateStr, selectedShift, selectedDept);
    const shiftType = getShiftType(data, dateStr, selectedShift);

    // Background by status: missing > extra > ok/none
    let statusClass = "cover-ok";
    if (rec.expected === 0) statusClass = "bg-gray-100"; // no schedule
    else if (rec.missing > 0) statusClass = "cover-missing";
    else if (rec.extra > 0) statusClass = "cover-extra";
    else statusClass = "cover-ok";

    // Heat via ring (so it doesn't override background)
    let heatRing = "";
    if (rec.expected > 0) {
      if (rec.coverage >= 95) heatRing = "ring-2 ring-green-300";
      else if (rec.coverage >= 75) heatRing = "ring-2 ring-yellow-300";
      else heatRing = "ring-2 ring-red-300";
    }

    // Shift indicator via left border
    let leftBorder = "";
    if (shiftType === "Night") leftBorder = "border-l-4 border-blue-400";
    else if (shiftType === "Day") leftBorder = "border-l-4 border-yellow-400";

    const cell = document.createElement("div");
    cell.className = `cover-cell ${statusClass} ${leftBorder} ${heatRing}`;
    cell.dataset.date = dateStr;
    cell.title = buildTooltip(dateStr, rec, selectedShift, selectedDept);

    const dayNum = document.createElement("div");
    dayNum.className = "font-bold";
    dayNum.textContent = d;

    const covLine = document.createElement("div");
    covLine.className = "text-xs";
    covLine.textContent = rec.expected > 0 ? `${rec.coverage.toFixed(1)}%` : "-";

    const meta = document.createElement("div");
    meta.className = "text-xs";
    meta.innerHTML = `
      <div>Exp:${rec.expected} Act:${rec.actual}</div>
      <div>M:${rec.missing} / X:${rec.extra}</div>
    `;

    cell.appendChild(dayNum);
    cell.appendChild(covLine);
    cell.appendChild(meta);
    grid.appendChild(cell);
  }
}

function buildTooltip(dateStr, stats, selectedShift, selectedDept) {
  if (!stats || stats.expected === 0) {
    return `${dateStr}\nNo scheduled coverage.`;
  }
  let title = `${dateStr}`;
  if (selectedShift) title += ` | Shift: ${selectedShift}`;
  if (selectedDept) title += ` | Dept: ${selectedDept}`;
  return [
    title,
    `Expected: ${stats.expected}, Actual: ${stats.actual}`,
    `Coverage: ${stats.coverage.toFixed(1)}%`,
    `Missing: ${stats.missing}, Extra: ${stats.extra}`
  ].join("\n");
}

function renderSummaryTable(data, year, month, selectedShift, selectedDept) {
  const container = document.getElementById("coverSummary");
  const pad = (n) => String(n).padStart(2, "0");
  const daysInMonth = new Date(year, month, 0).getDate();

  let eSum = 0, aSum = 0;

  let html = `
    <div class="print-block">
      <h3 class="text-lg font-semibold mb-2">
        Daily Coverage Summary${selectedShift ? " – " + selectedShift : ""}${selectedDept ? " – " + selectedDept : ""}
      </h3>
      <div class="overflow-x-auto">
        <table class="min-w-full border text-sm">
          <thead class="bg-gray-200">
            <tr>
              <th class="px-2 py-1 border">Date</th>
              <th class="px-2 py-1 border">Expected</th>
              <th class="px-2 py-1 border">Actual</th>
              <th class="px-2 py-1 border">Missing</th>
              <th class="px-2 py-1 border">Extra</th>
              <th class="px-2 py-1 border">Coverage %</th>
            </tr>
          </thead>
          <tbody>
  `;

  for (let d = 1; d <= daysInMonth; d++) {
    const dateStr = `${year}-${pad(month)}-${pad(d)}`;
    const rec = aggregateCoverage(data, dateStr, selectedShift, selectedDept);
    eSum += rec.expected;
    aSum += rec.actual;

    const monthShort = new Date(year, month - 1, d).toLocaleString("en-US", { month: "short" });
    const cov = rec.expected > 0 ? rec.coverage.toFixed(1) : "-";

    html += `
      <tr>
        <td class="px-2 py-1 border">${pad(d)}-${monthShort}</td>
        <td class="px-2 py-1 border">${rec.expected || "-"}</td>
        <td class="px-2 py-1 border">${rec.actual || "-"}</td>
        <td class="px-2 py-1 border text-red-600">${rec.missing || "-"}</td>
        <td class="px-2 py-1 border text-green-600">${rec.extra || "-"}</td>
        <td class="px-2 py-1 border">${cov}</td>
      </tr>
    `;
  }

  const mMissing = Math.max(0, eSum - aSum);
  const mExtra = Math.max(0, aSum - eSum);
  const mCov = eSum > 0 ? (aSum / eSum) * 100 : 0;

  html += `
      <tr class="bg-gray-100 font-semibold">
        <td class="px-2 py-1 border">Monthly Totals</td>
        <td class="px-2 py-1 border">${eSum}</td>
        <td class="px-2 py-1 border">${aSum}</td>
        <td class="px-2 py-1 border">${mMissing}</td>
        <td class="px-2 py-1 border">${mExtra}</td>
        <td class="px-2 py-1 border">${eSum ? mCov.toFixed(1) : "-"}</td>
      </tr>
    </tbody></table></div></div>
  `;

  container.innerHTML = html;
}

function renderCallbackStats(callbacks, container) {
  if (!container) return;
  const threshold = 3;
  const sorted = Object.entries(callbacks).sort((a, b) => b[1] - a[1]);
  if (!sorted.length) {
    container.innerHTML = "";
    return;
  }
  let html = `
    <h3 class="text-lg font-semibold mt-6">Callback Fairness</h3>
    <table class="min-w-full border text-sm mb-4">
      <thead class="bg-gray-100">
        <tr>
          <th class="px-2 py-1 border">Name</th>
          <th class="px-2 py-1 border">Callbacks</th>
        </tr>
      </thead>
      <tbody>
  `;
  for (const [name, count] of sorted) {
    const alert = count > threshold ? "bg-red-100 font-bold" : "";
    html += `
      <tr class="${alert}">
        <td class="px-2 py-1 border">${name}</td>
        <td class="px-2 py-1 border">${count}</td>
      </tr>
    `;
  }
  html += `</tbody></table>`;
  container.innerHTML = html;
}

// Expose functions for inline handlers
window.changeMonth = changeMonth;
window.loadCoverCalendar = loadCoverCalendar;