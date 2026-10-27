const DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
const TIME_SLOTS = [
  ["09:45", "10:35", false, "P1"], ["10:35", "11:25", false, "P2"], ["11:25", "11:30", true, "SHORT BREAK"],
  ["11:30", "12:20", false, "P3"], ["12:20", "13:10", false, "P4"], ["13:10", "13:40", true, "LUNCH"],
  ["13:40", "14:30", false, "P5"], ["14:30", "15:20", false, "P6"], ["15:20", "16:05", false, "P7"],
  ["16:05", "16:50", false, "P8"],
];

document.getElementById("print-btn").addEventListener("click", () => window.print());

function renderGrid(entries) {
  const byDayPeriod = {};
  entries.forEach((e) => {
    const key = `${e.day}_${e.period_label}`;
    (byDayPeriod[key] = byDayPeriod[key] || []).push(e);
  });

  const table = document.createElement("table");
  table.className = "tt";
  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  headRow.appendChild(document.createElement("th")).textContent = "Day";
  TIME_SLOTS.forEach(([start, end, isBreak, label]) => {
    const th = document.createElement("th");
    th.textContent = isBreak ? label : `${label}\n${start}-${end}`;
    headRow.appendChild(th);
  });
  thead.appendChild(headRow);
  table.appendChild(thead);

  const tbody = document.createElement("tbody");
  DAY_NAMES.forEach((dayName, dayIdx) => {
    const tr = document.createElement("tr");
    const th = document.createElement("th");
    th.textContent = dayName;
    tr.appendChild(th);
    TIME_SLOTS.forEach(([start, end, isBreak, label]) => {
      const td = document.createElement("td");
      if (isBreak) {
        td.className = "break-col";
        td.textContent = label;
      } else {
        (byDayPeriod[`${dayIdx}_${label}`] || []).forEach((e) => {
          const wrap = document.createElement("div");
          wrap.className = "tt-item type-" + String(e.session_type || "").toLowerCase();
          wrap.appendChild(SSM.el("div", { class: "cell-subject", text: `${e.subject_name} (${e.subject_code})` }));
          wrap.appendChild(SSM.el("div", { class: "cell-meta", text: `${e.section} · ${e.classroom || "-"}${e.batch ? " · Batch " + e.batch : ""}` }));
          td.appendChild(wrap);
        });
      }
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  return table;
}

(async function init() {
  const grid = document.getElementById("timetable-grid");
  const stats = document.getElementById("workload-stats");
  const todayList = document.getElementById("today-list");
  const todayTitle = document.getElementById("today-title");

  try {
    const data = await SSM.request("/api/faculty/me/timetable/");

    stats.innerHTML = "";
    [
      ["Weekly periods", data.weekly_total],
      ["Max per day", data.faculty.max_lectures_per_day],
      ["Max per week", data.faculty.max_lectures_per_week],
    ].forEach(([label, num]) => {
      stats.appendChild(SSM.el("div", { class: "col" }, [
        SSM.el("div", { class: "card h-100" }, [
          SSM.el("div", { class: "card-body py-3" }, [
            SSM.el("div", { class: "stat-num", text: num }),
            SSM.el("div", { class: "stat-label", text: label }),
          ]),
        ]),
      ]));
    });

    const jsDay = new Date().getDay(); // 0=Sun..6=Sat
    const todayIdx = jsDay === 0 ? null : jsDay - 1; // our Day enum: 0=Mon..5=Sat
    todayTitle.textContent = todayIdx === null ? "Today (no classes — Sunday)" : `Today — ${DAY_NAMES[todayIdx]}`;
    const todays = todayIdx === null ? [] : data.entries.filter((e) => e.day === todayIdx);
    todayList.innerHTML = "";
    if (!todays.length) {
      todayList.appendChild(SSM.el("div", { class: "text-muted text-center py-3", text: "No classes scheduled today." }));
    } else {
      todays.sort((a, b) => a.period_label.localeCompare(b.period_label));
      const listGroup = document.createElement("div");
      listGroup.className = "list-group list-group-flush";
      todays.forEach((e) => {
        listGroup.appendChild(SSM.el("div", {
          class: "list-group-item px-0",
          text: `${e.period_label} — ${e.subject_name} (${e.subject_code}) · ${e.section}${e.classroom ? " · " + e.classroom : ""}`,
        }));
      });
      todayList.appendChild(listGroup);
    }

    grid.innerHTML = "";
    if (!data.entries.length) {
      grid.appendChild(SSM.el("div", { class: "text-muted text-center py-4", text: "No published timetable entries yet." }));
    } else {
      grid.appendChild(renderGrid(data.entries));
    }
  } catch (err) {
    grid.innerHTML = "";
    grid.appendChild(SSM.el("div", { class: "alert alert-danger", text: err.message }));
    stats.innerHTML = "";
  }
})();
