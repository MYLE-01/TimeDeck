const codeMap = {
  D: "Day Shift 🕒",
  N: "Night Shift 🌙",
  "*": "Off Shift 💤"
};

function getCrewForShift(shiftName) {
  return Object.values(allEmployees).filter(emp => emp.shift === shiftName);
}

function empIdByName(name) {
  return Object.entries(allEmployees).find(([id, info]) => info.name === name)?.[0] || "unknown";
}

function showCrewMenu(event, name, empId,code) {
  event.stopPropagation();

  const oldMenu = document.getElementById("crewMenu");
  if (oldMenu) oldMenu.remove();

  const info = allEmployees[empId] || { name };

  const menu = document.createElement("div");
    menu.id = "crewMenu";
    menu.className = `
      fixed text-sm backdrop-blur-md bg-white/90 border border-gray-300 rounded-xl p-4 shadow-xl
      transition-transform transform scale-95 opacity-0
      z-[1000]
    `;
    Object.assign(menu.style, {
      left: `${event.pageX + 10}px`,
      top: `${event.pageY}px`,
      minWidth: "240px",
      maxWidth: "320px"
    });

  menu.addEventListener("click", e => e.stopPropagation());
  const title = document.createElement("h3");
  title.className = "text-lg font-semibold text-gray-800";
  title.textContent = `${info.name}`;
  const idSpan = document.createElement("A");
  idSpan.className = "text-sm text-gray-500 mb-2";
  idSpan.textContent = `ID: ${empId}`;
  idSpan.setAttribute(`href`, `/config_person/${empId}`);
  const btnGroup = document.createElement("div");
  btnGroup.className = "space-y-2";

const createButton = (label, color, empId, action) => {
  const btn = document.createElement("button");
  btn.className = `w-full px-4 py-2 text-sm rounded shadow-sm hover:shadow-md transition text-white ${color}`;
  btn.textContent = label;

  btn.addEventListener("click", () => {
    loadEmpConfig(empId).then(config => {
      //console.log("Loaded config:", config);

      fetch(`/configs/roster_${empId}.json?v=${Date.now()}`)
        .then(res => res.json())
        .then(roster => {
          // console.log("Loaded roster:", roster);

          const totals = getSeasonTotals(roster, config);
          

          // Handle action after data is ready
          if (action === "extra") {
            showAddExtraEntryForm(empId);  // ✅ Here’s your extra entry modal
          } else if (action === "edit") {
            editTodayHours(empId, code);
          } else if (action === "PSL") {
            console.log("📞 Sick leave triggered for", empId);
          } else if (action === "leave") {
            showTimeOffModal(empId,config,roster)
            console.log("🛫 Time off triggered for", empId);
          } else if (action ==="shift") {
            const dateInput = document.getElementById("datePicker")?.value;
            showShifts(empId,totals,config,dateInput);  
          }
        });
    });
  });

  return btn;
};

  btnGroup.appendChild(createButton("⭐️ Edit Today Hours", "bg-red-600 hover:bg-cyan-700",empId,"edit"));
  btnGroup.appendChild(createButton("➕ Add Extra Entry", "bg-green-600 hover:bg-green-700", empId, "extra"));
  btnGroup.appendChild(createButton("📆 Show Shifts", "bg-violet-600 hover:bg-violet-700",empId,"shift"));
  //btnGroup.appendChild(createButton("☎️ Phone in Sick", "bg-pink-600 hover:bg-pink-700",empId,"PSL"));
  btnGroup.appendChild(createButton("🔔 Time Off", "bg-cyan-600 hover:bg-cyan-700",empId,"leave"));
  menu.append(title, idSpan, btnGroup);
  document.body.appendChild(menu);

  // Trigger entrance animation
  requestAnimationFrame(() => {
    menu.style.transform = "scale(1)";
    menu.style.opacity = "1";
  });
}

// Auto-close menu on outside click
document.addEventListener("click", e => {
  const menu = document.getElementById("crewMenu");
  if (menu && !menu.contains(e.target)) menu.remove();
});

function renderSummary() {
  const dateInput = document.getElementById("datePicker")?.value;
  const target = new Date(dateInput);
  const output = document.getElementById("summaryOutput");
  output.innerHTML = "";

  const holidayName = holidayMap[dateInput];
  if (holidayName) {
    const banner = document.createElement("div");
    banner.className = "text-yellow-600 font-semibold mb-2";
    banner.textContent = `🎉 ${holidayName}`;
    output.appendChild(banner);
  }

  shiftData.Shifts.forEach(shift => {
    const start = new Date(Date.parse(shift.first));
    const seq = shift.shift_sequence;
    const len = seq.length;
    const daysDiff = Math.floor((target - start) / (1000 * 60 * 60 * 24));

    let code = "*", cycleDay = "Not started";
    if (daysDiff >= 0) {
      const pos = daysDiff % len;
      code = seq[pos];
      cycleDay = pos + 1;
    }

    const section = document.createElement("section");
    section.className = `mb-4 p-4 border-l-4 rounded bg-white shadow transform transition-all duration-300 ${
      code === "*" ? "scale-y-95 opacity-80 border-gray-300" :
      code === "D" ? "scale-y-105 font-bold border-blue-500" :
      code === "N" ? "scale-y-105 font-bold border-violet-500" : "border-gray-300"
    }`;

    const header = document.createElement("div");
    header.className = "mb-2";
    header.innerHTML = `
      <h2 class="text-lg text-blue-800">${shift.name}</h2>
      <p class="text-sm text-gray-600">${codeMap[code] || "Unknown"}</p>
    `;

    const cycle = document.createElement("p");
    cycle.className = "text-gray-500 text-sm mb-1";
    cycle.innerHTML = `Cycle: <span class="font-medium">Day ${cycleDay}</span> of ${len}`;

    const crewWrap = document.createElement("div");
    crewWrap.className = "text-sm mt-2";
    const label = document.createElement("strong");
    label.textContent = "On duty:";

    crewWrap.appendChild(label);

    const crew = getCrewForShift(shift.name);
if (crew.length) {
  crew.forEach((emp, i) => {
    const empId = empIdByName(emp.name);
    const span = document.createElement("span");
    span.textContent = emp.name;
    span.className = "ml-1 text-blue-700 hover:underline cursor-pointer";

    span.addEventListener("click", () => {
      loadEmpConfig(empId).then(config => {
        fetch(`/configs/roster_${empId}.json?v=${Date.now()}`)
          .then(res => res.json())
          .then(roster => {
            const totals = getSeasonTotals(roster, config);
            const dateInput = document.getElementById("datePicker")?.value || null;
            showShifts(empId, totals, config, dateInput);
          });
      });
    });

    crewWrap.appendChild(span);

    if (i < crew.length - 1) {
      crewWrap.appendChild(document.createTextNode(", "));
    }
  });
} else {
  const empty = document.createElement("em");
  empty.textContent = "No crew assigned";
  crewWrap.appendChild(empty);
}

    section.append(header, cycle, crewWrap);
    output.appendChild(section);
  });
}

document.addEventListener("DOMContentLoaded", () => {
  const picker = document.getElementById("datePicker");
  if (picker) {
    picker.addEventListener("change", renderSummary);
    renderSummary();
  }
});
