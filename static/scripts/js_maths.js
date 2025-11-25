function getShiftTodayData(shift, clickedDate) {
  const shiftSequence = shift.shift_sequence || '';
  const firstStr = shift.first || '';

  // Try to parse the date safely
  let firstDate;
  try {
    firstDate = new Date(firstStr);
    if (isNaN(firstDate)) throw new Error("Invalid date");
  } catch (e) {
    return { cycle_text: "Invalid date", label: "⚠ Error parsing date" };
  }

  ///const today = new Date();
  const today = new Date(clickedDate);
  const todayDate = new Date(today.getFullYear(), today.getMonth(), today.getDate()+1);
  const firstDateOnly = new Date(firstDate.getFullYear(), firstDate.getMonth(), firstDate.getDate());
  const daysSinceFirst = Math.floor((todayDate - firstDateOnly) / (1000 * 60 * 60 * 24));

  if (daysSinceFirst < 0) {
    return {
      cycle_text: `Starts in ${-daysSinceFirst} days`,
      label: "⏳ Not Started"
    };
  }

  const cycleLength = shiftSequence.length;
  if (cycleLength === 0) {
    return { cycle_text: "Empty sequence", label: "⚠ No schedule" };
  }

  const indexToday = daysSinceFirst % cycleLength;
  const symbol = shiftSequence[indexToday];

  const labelMap = {
    'D': '🟢', // On Duty (Day)
    'N': '🌙', // On Duty (Night)
    '*': '🔴'  // Rest Day
  };
  const labelbackMap = {
      'D': 'bg-yellow-200', // On Duty (Day)
      'N': 'bg-blue-200', // On Duty (Night)
      '*': 'bg-white'  // Rest Day
    };
  
  const label = labelMap[symbol] || `⚠ Unknown (${symbol})`;
  const labelback = labelbackMap[symbol] || `bg-white`;
  return {
    cycle_text: `Day ${indexToday + 1} of ${cycleLength}`,
    label: label,
    labelback: labelback
  };
}



function parseMins(value) {
  if (value.includes(":")) {
    const [hrs, mins] = value.split(":").map(Number);
    return (hrs || 0) * 60 + (mins || 0);
  }
  return Math.round(parseFloat(value) * 60);
}

function loadEmpConfig(empId) {
  return fetch(`/api/configs/emp_${empId}.json?v=${Date.now()}`)
    .then(res => {
      if (!res.ok) throw new Error(`Failed to load config for emp ${empId}`);
      return res.json();
    });
}

function formatDateDDMMMYY(dateStr) {
  const date = new Date(dateStr);
  if (isNaN(date)) return ""; // handle invalid dates gracefully

  return date.toLocaleDateString('en-NZ', {
    day: '2-digit',
    month: 'short',
    year: '2-digit'
  }).replace(/ /g, '-');
}



function parseDateDDMMYYYY(str) {
  const [day, month, year] = str.split("-").map(Number);
  return new Date(year, month - 1, day);
}
// ---------------------------
// Helper: normalize date to midnight
// ---------------------------
function normalizeDate(d) {
  const nd = new Date(d);
  nd.setHours(0,0,0,0);
  return nd;
}

// ---------------------------
// Sum minutes between two dates
// ---------------------------
function sumMinutesBetween(data, startDate, endDate, rollOverNights = false) {
  const start = normalizeDate(startDate);
  const end = normalizeDate(endDate);
  end.setDate(end.getDate() + 1); // inclusive

  return data.reduce((total, entry) => {
    let entryDate = normalizeDate(entry.date);
    let addMins = entry.mins || 0;

    // Night shift rollover
    if (rollOverNights && entry.shift_type === "Night") {
      const rolledDate = new Date(entryDate);
      rolledDate.setDate(rolledDate.getDate() + 1);

      // Only roll forward if it falls in the range
      if (rolledDate <= end) {
        entryDate = rolledDate;
      }
    }

    if (entryDate >= start && entryDate < end) {
      total += addMins;
    }
    return total;
  }, 0);
}

// ---------------------------
// Calculate season totals
// ---------------------------
function getSeasonTotals(data, config, referenceDate = null, rollOverNights = false) {
  const refDate = referenceDate ? new Date(referenceDate) : new Date();
  refDate.setHours(0,0,0,0);

  const seasonStart = parseDateDDMMYYYY(config.season.start);
  const seasonEnd = parseDateDDMMYYYY(config.season.ends);
  let totaltodo = config.default_entitlement_mins;
  const isTemp = !totaltodo || totaltodo === 0;

  // 1️⃣ Actual minutes so far
  const minsSoFar = sumMinutesBetween(data, seasonStart, refDate, rollOverNights);

  // 2️⃣ Expected so far
  const seasonDays = Math.floor((seasonEnd - seasonStart) / 86400000) + 1;
  const daysPassed = Math.floor((refDate - seasonStart) / 86400000) + 1;
  
  
  // 3️⃣ Remaining + makeup
  const tomorrow = new Date(refDate);
  tomorrow.setDate(refDate.getDate() + 1);
  const minsRemaining = sumMinutesBetween(data, tomorrow, seasonEnd, rollOverNights);

  if (isTemp) {
      totaltodo = minsRemaining + minsSoFar;
    }

  const today = new Date();
  today.setHours(0,0,0,0);

  const outsideSeason = today < seasonStart || today > seasonEnd;

  if (isTemp && outsideSeason) {
    return {
      totaltodo: 0,
      minsSoFar: 0,
      isTemp: true,
      expectedSoFar: 0,
      minsRemaining: 0,
      makeup: 0,
      xtraShift: "0.0",
      totalSeason: 0,
      progressPct: "0.0",
      expectedPct: "0.0",
      behindPct: "0.0",
      display: {
        totalToDo: "0:00",
        totalSoFar: "0:00",
        totalRemaining: "0:00",
        behindHours: "0.0",
        progressPctText: "0% complete",
        expectedPctText: "Out of season",
        behindPctText: "—",
        makeupText: "0.0 Covers"
      },
      statusMsg: "📅 No active season"
    };
  }

  const expectedSoFar = Math.round((daysPassed / seasonDays) * totaltodo);

  const makeup = totaltodo - (minsSoFar + minsRemaining);
  const xtraShift = (makeup / 720).toFixed(1);

  const progressPct = ((minsSoFar / totaltodo) * 100).toFixed(1);
  const expectedPct = ((expectedSoFar / totaltodo) * 100).toFixed(1);
  

  const behindMins = minsSoFar - expectedSoFar;
  const behindPct = ((behindMins / totaltodo) * 100).toFixed(1);
  // const behindPct = isTemp ? 0 : ((behindMins / totaltodo) * 100).toFixed(1);
  // 4️⃣ Callback minutes (CB shifts)
  // These are credited separately and do not count towards totals
  // e.g. 60 mins for a 12h CB shift
  // Only count those up to the reference date  
  const callbackMins = data
    .filter(e => e.type_shift === "CB" && parseISO(e.date) <= referenceDate)
    .reduce((sum, e) => sum + (e.mins || 0), 0);

  //console.log("🟢 Callback minutes credited:", callbackMins);
  // HH:MM formatting helper
  const minToHrs = mins => {
    const h = Math.floor(mins / 60);
    const m = mins % 60;
    return `${h}:${m.toString().padStart(2,'0')}`;
  };
    
  return {
    totaltodo,
    minsSoFar,
    isTemp,
    expectedSoFar,
    minsRemaining,
    makeup,
    xtraShift,
    totalSeason: minsSoFar + minsRemaining,
    progressPct,
    expectedPct,
    behindPct,
    display: {
      totalToDo: minToHrs(totaltodo),
      totalSoFar: minToHrs(minsSoFar),
      totalRemaining: minToHrs(minsRemaining),
      behindHours: (Math.abs(behindMins)/60).toFixed(1), // decimal hours
      progressPctText: `${progressPct}% complete`,
      expectedPctText: `Should be at ${expectedPct}%`,
      behindPctText: `Behind by ${behindPct}%`,
      makeupText: `${xtraShift} Covers`

    }
  };
}


function decimal100ToHHMM(timeStr) {
  const [hoursStr, decimalStr] = timeStr.split(".");
  const hours = parseInt(hoursStr, 10);
  const decimal = decimalStr ? parseInt(decimalStr, 10) : 0;
  const minutes = Math.round(decimal * 60 / 100);
  if (isNaN(hours) || isNaN(minutes)) return "";
  return `${hours}:${minutes.toString().padStart(2, "0")}`;
}

// Converts decimal time (e.g., 12.3) to HH:MM format
function decimalTime(time) {
    const hours = Math.floor(time); 
    const minutes = Math.round((time - hours) * 60);
    return `${hours}:${minutes.toString().padStart(2, '0')}`;
}

// Converts decimal time in hours to minutes (e.g., 12.30 -> 738 minutes)
function decimalTimeHrsToMins(hours) {
    return hrsToMins(decimalTime(hours));
}

// Converts minutes into HH:MM format
function minToHrs(minutes) {
    if (minutes < 0) {
        minutes = Math.abs(minutes);
        var sign = "-";
    } else {
        sign = "";
    }
    const hrs = Math.floor(minutes / 60);
    minutes = minutes - (hrs * 60);
    const timeStr = `${sign}${hrs.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`;
    return timeStr === "00:00" ? "" : timeStr;
}

// Converts time in HH:MM format to minutes (e.g., 12:18 -> 738 minutes)
function hrsToMins(hours) {
    const [hrs, mins] = hours.split(":").map(Number);
    return (hrs * 60) + mins;
}
// Convert time if it has a h at the end to mins
function convertThisToMins(time) {
    const thisTime = String(time).toLowerCase().trim();
    //console.log("Loaded time:", time);
    let answer;

    if (thisTime.endsWith("h") && !isNaN(thisTime.slice(0, -1))) {
        // Example: "2325h" → 2325 hours → 2325 × 60 mins
        const hours = parseInt(thisTime.slice(0, -1), 10);
        answer = hours * 60;
    } else if (thisTime.includes(".")) {
        answer = decimalTimeHrsToMins(time); // Assuming decimalTimeHrsToMins is defined elsewhere
    } else if (thisTime.includes(":")) {
        answer = hrsToMins(time); // Assuming hrsToMins is defined elsewhere
    } else if (!isNaN(thisTime)) {
        answer = parseInt(thisTime, 10);
    } else {
        throw new Error(`Unknown time format: '${time}'`);
    }

    return Math.floor(answer); // Ensures result is an integer (in case of floating point arithmetic)
}

function convertToHHMM(time) {
    const thisTime = String(time).toLowerCase().trim();
    let totalMinutes;

    // Case 1: Time ends with 'h' (e.g., "2325h" → 2325 hours → 2325 * 60 minutes)
    if (thisTime.endsWith("h") && !isNaN(thisTime.slice(0, -1))) {
        const hours = parseInt(thisTime.slice(0, -1), 10);
        totalMinutes = hours * 60;
    } 
    // Case 2: Decimal time (e.g., "12.30" → 12 hours 18 minutes)
    else if (thisTime.includes(".")) {
        totalMinutes = decimalTimeHrsToMins(time); // Assuming this is defined elsewhere
    } 
    // Case 3: Time in HH:MM format (e.g., "12:18" → 738 minutes)
    else if (thisTime.includes(":")) {
        totalMinutes = hrsToMins(time); // Assuming this is defined elsewhere
    } 
    // Case 4: Pure number of minutes (e.g., "500" → 500 minutes)
    else if (!isNaN(thisTime)) {
        totalMinutes = parseInt(thisTime, 10);
    } 
    else {
        throw new Error(`Unknown time format: '${time}'`);
    }

    // Convert total minutes into HH:MM format
    const hours = Math.floor(totalMinutes / 60);
    const minutes = totalMinutes % 60;

    // Return the formatted string
    return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`;
}

// Generalized function for handling input and tooltip display

// Attach tooltips to multiple input fields
// attachTimeTooltip("timeInput1", "tooltip1");
// attachTimeTooltip("timeInput2", "tooltip2");


function minToDays(mins, dayLengthMins = 720) {
  // Default is 12h days = 720 mins
  if (typeof mins !== "number" || mins <= 0) return "";
  return (mins / dayLengthMins).toFixed(2); // e.g. 960 mins → 1.33 days
}



function attachTimeTooltip(timeInputId, tooltipId) {
    const timeInput = document.getElementById(timeInputId);
    const tooltip = document.getElementById(tooltipId);
    //console.log("attachTimeTooltip");
    timeInput.addEventListener("input", function () {
        const inputValue = this.value;

        try {
            const convertedTime = convertToHHMM(inputValue);
            tooltip.textContent = convertedTime; // Update tooltip text
            tooltip.style.visibility = 'visible'; // Make tooltip visible
            tooltip.style.opacity = '1'; // Fade in the tooltip
            tooltip.style.transform = 'translateY(0)'; // Reset position to its natural state
        } catch (e) {
            tooltip.style.visibility = 'hidden'; // Hide tooltip if there's an error
            tooltip.style.opacity = '0'; // Fade out the tooltip
            tooltip.style.transform = 'translateY(-10px)'; // Slide the tooltip out
        }
    });
}
