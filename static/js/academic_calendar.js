function optionEl(value, label) {
  const o = document.createElement("option");
  o.value = value;
  o.textContent = label;
  return o;
}

const DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
let currentCalendar = null;

async function loadSelectors() {
  const ayData = await SSM.request("/api/academics/academic-years/");
  const aySel = document.getElementById("cal-academic-year");
  (ayData.results || ayData).forEach((y) => aySel.appendChild(optionEl(y.id, y.label)));

  const deptData = await SSM.request("/api/academics/departments/");
  const deptSel = document.getElementById("cal-department");
  (deptData.results || deptData).forEach((d) => deptSel.appendChild(optionEl(d.id, d.name)));
}

async function loadCalendar() {
  const statusBox = document.getElementById("cal-status");
  const workingBox = document.getElementById("working-days-box");
  statusBox.innerHTML = "";
  const ayId = document.getElementById("cal-academic-year").value;
  const deptId = document.getElementById("cal-department").value;
  if (!ayId) return;

  const query = deptId ? `academic_year=${ayId}&department=${deptId}` : `academic_year=${ayId}`;
  const data = await SSM.request(`/api/academic-calendar/calendars/?${query}`);
  const matches = (data.results || data).filter((c) => (deptId ? String(c.department) === deptId : c.department === null));

  if (!matches.length) {
    currentCalendar = null;
    const alertBox = SSM.el("div", { class: "alert alert-warning d-flex align-items-center gap-2 flex-wrap" });
    alertBox.appendChild(document.createTextNode("No calendar exists yet for this selection."));
    const btn = SSM.el("button", { class: "btn btn-outline-secondary btn-sm", text: "Create it (Jul 15 – Dec 5, adjust later)" });
    btn.addEventListener("click", async () => {
      await SSM.request("/api/academic-calendar/calendars/", {
        method: "POST",
        body: { academic_year: parseInt(ayId, 10), department: deptId ? parseInt(deptId, 10) : null,
                semester_start: `${new Date().getFullYear()}-07-15`, semester_end: `${new Date().getFullYear()}-12-05` },
      });
      await loadCalendar();
    });
    alertBox.appendChild(btn);
    statusBox.appendChild(alertBox);
    workingBox.innerHTML = '<span class="text-muted">No calendar yet.</span>';
    return;
  }

  currentCalendar = matches[0];
  statusBox.appendChild(SSM.el("div", { class: "alert alert-success",
    text: `Calendar found: ${currentCalendar.semester_start} to ${currentCalendar.semester_end}` }));

  await loadWorkingDays();
  await loadHolidays();
}

async function loadWorkingDays() {
  const box = document.getElementById("working-days-box");
  box.innerHTML = "";
  const data = await SSM.request(`/api/academic-calendar/working-days/?calendar=${currentCalendar.id}`);
  const existing = data.results || data;
  const byDay = {};
  existing.forEach((w) => (byDay[w.day] = w));

  DAY_NAMES.forEach((name, idx) => {
    const wrap = document.createElement("div");
    wrap.className = "form-check";
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.className = "form-check-input";
    cb.id = `wd-${idx}`;
    cb.checked = byDay[idx] ? byDay[idx].is_working : idx !== 5;
    cb.addEventListener("change", async () => {
      if (byDay[idx]) {
        await SSM.request(`/api/academic-calendar/working-days/${byDay[idx].id}/`, {
          method: "PATCH", body: { is_working: cb.checked },
        });
      } else {
        const created = await SSM.request("/api/academic-calendar/working-days/", {
          method: "POST", body: { calendar: currentCalendar.id, day: idx, is_working: cb.checked },
        });
        byDay[idx] = created;
      }
    });
    const label = document.createElement("label");
    label.className = "form-check-label";
    label.htmlFor = cb.id;
    label.textContent = name;
    wrap.appendChild(cb);
    wrap.appendChild(label);
    box.appendChild(wrap);
  });
}

async function loadHolidays() {
  const box = document.getElementById("holiday-list");
  box.innerHTML = '<span class="text-muted">Loading…</span>';
  const data = await SSM.request(`/api/academic-calendar/holidays/?calendar=${currentCalendar.id}`);
  const items = data.results || data;
  box.innerHTML = "";
  if (!items.length) {
    box.appendChild(SSM.el("div", { class: "text-muted text-center py-4", text: "No holidays added yet." }));
    return;
  }
  items.sort((a, b) => a.date.localeCompare(b.date));
  const listGroup = document.createElement("div");
  listGroup.className = "list-group list-group-flush";
  items.forEach((h) => {
    listGroup.appendChild(SSM.el("div", { class: "list-group-item px-0", text: `${h.date} — ${h.name}` }));
  });
  box.appendChild(listGroup);
}

document.getElementById("hol-submit").addEventListener("click", async () => {
  if (!currentCalendar) {
    alert("Create a calendar for this selection first.");
    return;
  }
  const date = document.getElementById("hol-date").value.trim();
  const name = document.getElementById("hol-name").value.trim();
  if (!date || !name) return;
  try {
    await SSM.request("/api/academic-calendar/holidays/", { method: "POST", body: { calendar: currentCalendar.id, date, name } });
    document.getElementById("hol-date").value = "";
    document.getElementById("hol-name").value = "";
    await loadHolidays();
  } catch (err) {
    alert(err.message);
  }
});

document.getElementById("cal-academic-year").addEventListener("change", loadCalendar);
document.getElementById("cal-department").addEventListener("change", loadCalendar);

(async function init() {
  await loadSelectors();
  await loadCalendar();
})();
