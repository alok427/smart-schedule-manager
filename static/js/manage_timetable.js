const DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
// Mirrors common/constants.py TIME_SLOTS exactly.
const TIME_SLOTS = [
  ["09:45", "10:35", false, "P1"],
  ["10:35", "11:25", false, "P2"],
  ["11:25", "11:30", true, "SHORT BREAK"],
  ["11:30", "12:20", false, "P3"],
  ["12:20", "13:10", false, "P4"],
  ["13:10", "13:40", true, "LUNCH"],
  ["13:40", "14:30", false, "P5"],
  ["14:30", "15:20", false, "P6"],
  ["15:20", "16:05", false, "P7"],
  ["16:05", "16:50", false, "P8"],
];

const state = { departments: [], currentSection: null, currentSemester: null, selectedSessionId: null };

function optionEl(value, label) {
  const o = document.createElement("option");
  o.value = value;
  o.textContent = label;
  return o;
}

async function loadAcademicYears() {
  const sel = document.getElementById("gen-academic-year");
  const data = await SSM.request("/api/academics/academic-years/");
  const years = data.results || data;
  sel.innerHTML = "";
  years.forEach((y) => sel.appendChild(optionEl(y.id, `${y.label}${y.is_active ? " (active)" : ""}`)));
  const active = years.find((y) => y.is_active);
  if (active) sel.value = active.id;
}

async function loadDepartmentsForGeneration() {
  const box = document.getElementById("gen-departments");
  const viewSel = document.getElementById("view-department");
  const data = await SSM.request("/api/academics/departments/");
  const depts = data.results || data;
  state.departments = depts;
  box.innerHTML = "";
  viewSel.innerHTML = "";
  depts.forEach((d) => {
    const wrap = document.createElement("div");
    wrap.className = "form-check";
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.value = d.id;
    cb.className = "form-check-input gen-dept-cb";
    cb.id = `gen-dept-${d.id}`;
    const label = document.createElement("label");
    label.className = "form-check-label";
    label.htmlFor = cb.id;
    label.textContent = d.name;
    wrap.appendChild(cb);
    wrap.appendChild(label);
    box.appendChild(wrap);
    viewSel.appendChild(optionEl(d.id, d.name));
  });
}

document.getElementById("gen-scope-type").addEventListener("change", async (e) => {
  const wrap = document.getElementById("gen-sections-wrap");
  const btn = document.getElementById("generate-btn");
  if (e.target.value === "SECTION") {
    wrap.style.display = "";
    btn.textContent = "Generate Selected Section(s)";
    await loadSectionsForGeneration();
  } else {
    wrap.style.display = "none";
    btn.textContent = e.target.value === "DRAFT" ? "Generate Draft" : "Generate Complete Timetable";
  }
});

async function loadSectionsForGeneration() {
  const box = document.getElementById("gen-sections");
  const ayId = document.getElementById("gen-academic-year").value;
  const data = await SSM.request(`/api/academics/sections/?academic_year=${ayId}`);
  const sections = data.results || data;
  box.innerHTML = "";
  sections.forEach((s) => {
    const wrap = document.createElement("div");
    wrap.className = "form-check";
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.value = s.id;
    cb.className = "form-check-input";
    cb.id = `gen-section-${s.id}`;
    const label = document.createElement("label");
    label.className = "form-check-label";
    label.htmlFor = cb.id;
    label.textContent = `${s.department_code} Y${s.year_number} - ${s.name}`;
    wrap.appendChild(cb);
    wrap.appendChild(label);
    box.appendChild(wrap);
  });
}

document.getElementById("generate-btn").addEventListener("click", async () => {
  const errorBox = document.getElementById("gen-error");
  const resultBox = document.getElementById("gen-result");
  errorBox.innerHTML = "";
  resultBox.innerHTML = "";
  const btn = document.getElementById("generate-btn");
  btn.disabled = true;
  const originalText = btn.textContent;
  btn.textContent = "Generating…";

  const payload = {
    academic_year: parseInt(document.getElementById("gen-academic-year").value, 10),
    semester_type: document.getElementById("gen-semester-type").value,
    scope_type: document.getElementById("gen-scope-type").value,
    department_ids: Array.from(document.querySelectorAll(".gen-dept-cb:checked")).map((c) => parseInt(c.value, 10)),
    year_numbers: Array.from(document.querySelectorAll("#gen-years input:checked")).map((c) => parseInt(c.value, 10)),
    section_ids: Array.from(document.querySelectorAll("#gen-sections input:checked")).map((c) => parseInt(c.value, 10)),
  };

  try {
    const gen = await SSM.request("/api/scheduling/generate/", { method: "POST", body: payload });
    const tagClass = gen.status === "CURRENT" ? "success" : gen.status === "DRAFT" ? "warning" : "danger";
    const box = SSM.el("div", { class: `alert alert-${tagClass === "danger" ? "danger" : "success"}` });
    box.appendChild(SSM.el("span", { class: `badge text-bg-${tagClass} me-2`, text: gen.status }));
    box.appendChild(document.createTextNode(`Generation #${gen.id} covering: ${gen.section_names.join(", ") || "—"}`));
    if (gen.failure_summary) {
      box.appendChild(SSM.el("div", { class: "mt-2", text: gen.failure_summary }));
    }
    if (gen.issues && gen.issues.length) {
      const ul = document.createElement("ul");
      ul.className = "mb-0 mt-2";
      gen.issues.forEach((i) => ul.appendChild(SSM.el("li", { text: `[${i.severity}] ${i.message}` })));
      box.appendChild(ul);
    }
    resultBox.appendChild(box);
    if (gen.status === "CURRENT" && state.currentSection && state.currentSemester) {
      await loadTimetable(state.currentSection, state.currentSemester);
      await loadHistory(state.currentSection, state.currentSemester);
    }
  } catch (err) {
    errorBox.appendChild(SSM.el("div", { class: "alert alert-danger", text: err.message }));
  } finally {
    btn.disabled = false;
    btn.textContent = originalText;
  }
});

// ---------------- View controls ----------------


document.getElementById("view-department").addEventListener("change", async (e) => {
  const sectionSel = document.getElementById("view-section");
  const semSel = document.getElementById("view-semester");

  sectionSel.innerHTML = '<option value="">Loading sections...</option>';
  semSel.innerHTML = '<option value="">Select a section first</option>';

  const deptId = e.target.value;
  if (!deptId) {
    sectionSel.innerHTML = '<option value="">Select department first</option>';
    return;
  }

  try {
    const data = await SSM.request(
      `/api/academics/sections/?department=${encodeURIComponent(deptId)}`
    );

    const sections = data.results || data;
    sectionSel.innerHTML = "";

    if (!Array.isArray(sections) || sections.length === 0) {
      sectionSel.innerHTML = '<option value="">No sections found</option>';
      return;
    }

    sectionSel.appendChild(optionEl("", "Select section"));
    sections.forEach((s) => {
      sectionSel.appendChild(
        optionEl(s.id, `Year ${s.year_number} - ${s.name}`)
      );
    });

  } catch (err) {
    console.error("Failed to load sections:", err);
    sectionSel.innerHTML = '<option value="">Failed to load sections</option>';
  }
});


document.getElementById("view-section").addEventListener("change", async (e) => {
  const semSel = document.getElementById("view-semester");
  semSel.innerHTML = "";
  const sectionId = e.target.value;
  if (!sectionId) return;
  const secData = await SSM.request(`/api/academics/sections/${sectionId}/`);
  const data = await SSM.request(`/api/academics/semesters/?year=${secData.year}`);
  const semesters = data.results || data;
  semesters.forEach((s) => semSel.appendChild(optionEl(s.id, `Semester ${s.semester_number} (${s.semester_type})`)));
});



document.getElementById("view-btn").addEventListener("click", async () => {
  const sectionId = document.getElementById("view-section").value;
  const semesterId = document.getElementById("view-semester").value;
  if (!sectionId || !semesterId) return;
  state.currentSection = sectionId;
  state.currentSemester = semesterId;
  document.getElementById("edit-panel").style.display = "none";
  state.selectedSessionId = null;
  await loadTimetable(sectionId, semesterId);
  await loadHistory(sectionId, semesterId);
  await loadFacultyTool(sectionId, semesterId);
  await loadRoomsForEditPanel();
});

function periodColumns() {
  return TIME_SLOTS;
}

async function loadTimetable(sectionId, semesterId) {
  const panel = document.getElementById("timetable-panel");
  const grid = document.getElementById("timetable-grid");
  const title = document.getElementById("timetable-title");
  panel.style.display = "";
  grid.innerHTML = '<span class="text-muted">Loading…</span>';

  const data = await SSM.request(`/api/scheduling/timetable/?section=${sectionId}&semester=${semesterId}`);
  if (!data.entries || !data.entries.length) {
    title.textContent = data.section || "Timetable";
    grid.innerHTML = "";
    grid.appendChild(SSM.el("div", { class: "text-muted text-center py-4", text: data.detail || "No published timetable yet." }));
    return;
  }
  title.textContent = `${data.section} — v${data.version_number}`;

  const byDayPeriod = {};
  data.entries.forEach((e) => {
    const key = `${e.day}_${e.period_label}`;
    (byDayPeriod[key] = byDayPeriod[key] || []).push(e);
  });

  const table = document.createElement("table");
  table.className = "tt";
  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  headRow.appendChild(document.createElement("th")).textContent = "Day";
  periodColumns().forEach(([start, end, isBreak, label]) => {
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
    periodColumns().forEach(([start, end, isBreak, label]) => {
      const td = document.createElement("td");
      if (isBreak) {
        td.className = "break-col";
        td.textContent = label;
      } else {
        td.dataset.day = dayIdx;
        td.dataset.period = label;
        addDropHandlers(td, sectionId, semesterId);

        const cellEntries = byDayPeriod[`${dayIdx}_${label}`] || [];
        if (cellEntries.length) {
          if (cellEntries.some((e) => e.is_fixed)) td.classList.add("cell-fixed");
          cellEntries.forEach((e) => {
            const wrap = document.createElement("div");
            wrap.className = "tt-item type-" + String(e.session_type || "").toLowerCase();
            wrap.appendChild(SSM.el("div", { class: "cell-subject", text: `${e.subject_name} (${e.subject_code})` }));
            const metaParts = [e.session_type];
            if (e.faculty_short_code) metaParts.push(e.faculty_short_code);
            if (e.classroom_number) metaParts.push(e.classroom_number);
            if (e.batch_name) metaParts.push(`Batch ${e.batch_name}`);
            wrap.appendChild(SSM.el("div", { class: "cell-meta", text: metaParts.join(" · ") }));
            if (!e.is_fixed) {
              wrap.classList.add("cell-editable");
              wrap.title = "Drag to a new slot, or click to move precisely / change the room";
              wrap.addEventListener("click", () => selectEntryForEdit(e, dayIdx, label));
              wrap.draggable = true;
              wrap.addEventListener("dragstart", (ev) => {
                dragState = { sessionId: e.session_id, periodCount: e.session_type === "PRACTICAL" ? 2 : 1,
                              subjectLabel: `${e.subject_name} (${e.subject_code})` };
                wrap.classList.add("cell-dragging");
                ev.dataTransfer.effectAllowed = "move";
                ev.dataTransfer.setData("text/plain", String(e.session_id));
              });
              wrap.addEventListener("dragend", () => wrap.classList.remove("cell-dragging"));
            } else {
              wrap.title = "Fixed/locked — edit it from the Fixed Scheduling page";
            }
            td.appendChild(wrap);
          });
        }
      }
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  grid.innerHTML = "";
  grid.appendChild(table);
}

// ---------------- Drag-and-drop ----------------

let dragState = null;
const LAB_PAIR_LABELS = [["P1", "P2"], ["P3", "P4"], ["P5", "P6"], ["P7", "P8"]];

function addDropHandlers(td, sectionId, semesterId) {
  td.addEventListener("dragover", (ev) => {
    if (!dragState) return;
    ev.preventDefault();
    ev.dataTransfer.dropEffect = "move";
    td.classList.add("drop-target-ok");
  });
  td.addEventListener("dragleave", () => {
    td.classList.remove("drop-target-ok", "drop-target-bad");
  });
  td.addEventListener("drop", async (ev) => {
    ev.preventDefault();
    td.classList.remove("drop-target-ok", "drop-target-bad");
    if (!dragState) return;

    const targetDay = parseInt(td.dataset.day, 10);
    const targetPeriod = td.dataset.period;
    const feedback = document.getElementById("dnd-feedback");
    feedback.innerHTML = "";

    let neededLabels;
    if (dragState.periodCount === 1) {
      neededLabels = [targetPeriod];
    } else {
      // Labs must land on the FIRST period of a real consecutive pair
      // (never spanning a break/lunch) — never a raw slice of adjacent
      // column labels, which could straddle SHORT BREAK/LUNCH.
      const pair = LAB_PAIR_LABELS.find((p) => p[0] === targetPeriod);
      if (!pair) {
        feedback.appendChild(SSM.el("div", { class: "alert alert-danger",
          text: `"${dragState.subjectLabel}" is a 2-period lab block — drop it on the first period of a pair (P1, P3, P5, or P7).` }));
        dragState = null;
        return;
      }
      neededLabels = pair;
    }

    try {
      await SSM.request("/api/scheduling/edit/move-session/", {
        method: "POST",
        body: { session_id: dragState.sessionId, new_day: targetDay, new_period_labels: neededLabels },
      });
      feedback.appendChild(SSM.el("div", { class: "alert alert-success",
        text: `Moved "${dragState.subjectLabel}" to ${DAY_NAMES[targetDay]} ${neededLabels.join("/")}.` }));
      await loadTimetable(sectionId, semesterId);
    } catch (err) {
      renderViolations(err, feedback);
    }
    dragState = null;
  });
}

document.getElementById("print-btn").addEventListener("click", () => window.print());

function selectEntryForEdit(entry, dayIdx, periodLabel) {
  state.selectedSessionId = entry.session_id;
  document.getElementById("edit-panel").style.display = "";
  document.getElementById("edit-summary").textContent =
    `Selected: ${entry.subject_name} (${entry.subject_code}) — currently ${DAY_NAMES[dayIdx]} ${periodLabel}` +
    (entry.classroom_number ? `, room ${entry.classroom_number}` : "");
  document.getElementById("edit-day").value = dayIdx;
  document.getElementById("edit-period").value = periodLabel;
  document.getElementById("edit-result").innerHTML = "";
  document.getElementById("edit-panel").scrollIntoView({ behavior: "smooth", block: "center" });
}

async function loadRoomsForEditPanel() {
  const sel = document.getElementById("edit-classroom");
  sel.innerHTML = "";
  const secData = await SSM.request(`/api/academics/sections/${state.currentSection}/`);
  const data = await SSM.request(`/api/classrooms/?department=${secData.department}`);
  (data.results || data).forEach((r) => sel.appendChild(optionEl(r.id, `${r.room_number} (${r.room_type})`)));
}

document.getElementById("edit-move-btn").addEventListener("click", async () => {
  const resultBox = document.getElementById("edit-result");
  resultBox.innerHTML = "";
  if (!state.selectedSessionId) return;
  const payload = {
    session_id: state.selectedSessionId,
    new_day: parseInt(document.getElementById("edit-day").value, 10),
    new_period_labels: [document.getElementById("edit-period").value],
  };
  try {
    await SSM.request("/api/scheduling/edit/move-session/", { method: "POST", body: payload });
    resultBox.appendChild(SSM.el("div", { class: "alert alert-success", text: "Moved successfully." }));
    await loadTimetable(state.currentSection, state.currentSemester);
  } catch (err) {
    renderViolations(err, resultBox);
  }
});

document.getElementById("edit-room-btn").addEventListener("click", async () => {
  const resultBox = document.getElementById("edit-result");
  resultBox.innerHTML = "";
  if (!state.selectedSessionId) return;
  const payload = {
    session_id: state.selectedSessionId,
    new_classroom_id: parseInt(document.getElementById("edit-classroom").value, 10),
  };
  try {
    await SSM.request("/api/scheduling/edit/change-classroom/", { method: "POST", body: payload });
    resultBox.appendChild(SSM.el("div", { class: "alert alert-success", text: "Room changed successfully." }));
    await loadTimetable(state.currentSection, state.currentSemester);
  } catch (err) {
    renderViolations(err, resultBox);
  }
});

function renderViolations(err, container) {
  const violations = (err.body && err.body.violations) || [];
  const box = SSM.el("div", { class: "alert alert-danger", text: err.message });
  if (violations.length) {
    const ul = document.createElement("ul");
    ul.className = "mb-0 mt-2";
    violations.forEach((v) => ul.appendChild(SSM.el("li", { text: v })));
    box.appendChild(ul);
  }
  container.appendChild(box);
}

async function loadHistory(sectionId, semesterId) {
  const panel = document.getElementById("history-panel");
  const list = document.getElementById("history-list");
  panel.style.display = "";
  list.innerHTML = '<span class="text-muted">Loading…</span>';

  const data = await SSM.request(`/api/scheduling/history/?section=${sectionId}&semester=${semesterId}`);
  list.innerHTML = "";
  if (!data.recent.length) {
    list.appendChild(SSM.el("div", { class: "text-muted text-center py-4", text: "No versions generated yet." }));
    return;
  }
  const listGroup = document.createElement("div");
  listGroup.className = "list-group list-group-flush";
  data.recent.forEach((v) => {
    const row = document.createElement("div");
    row.className = "list-group-item d-flex align-items-center justify-content-between px-0";
    const left = document.createElement("div");
    const tagClass = v.status === "CURRENT" ? "success" : "secondary";
    left.appendChild(SSM.el("span", { class: `badge text-bg-${tagClass} me-2`, text: v.status }));
    left.appendChild(document.createTextNode(`v${v.version_number} — activated ${v.activated_at ? new Date(v.activated_at).toLocaleString() : "—"}`));
    row.appendChild(left);
    if (v.status !== "CURRENT") {
      const btn = SSM.el("button", { class: "btn btn-outline-secondary btn-sm", text: "Restore" });
      btn.addEventListener("click", async () => {
        btn.disabled = true;
        try {
          await SSM.request(`/api/scheduling/versions/${v.id}/restore/`, { method: "POST" });
          await loadTimetable(sectionId, semesterId);
          await loadHistory(sectionId, semesterId);
        } catch (err) {
          alert("Restore blocked: " + err.message + (err.body && err.body.violations ? "\n- " + err.body.violations.join("\n- ") : ""));
          btn.disabled = false;
        }
      });
      row.appendChild(btn);
    }
    listGroup.appendChild(row);
  });
  list.appendChild(listGroup);
  list.appendChild(SSM.el("div", { class: "helptext mt-2", text: `${data.total_versions} version(s) total (all preserved).` }));
}

async function loadFacultyTool(sectionId, semesterId) {
  const panel = document.getElementById("faculty-tool-panel");
  panel.style.display = "";
  const offSel = document.getElementById("fac-tool-offering");
  const facSel = document.getElementById("fac-tool-faculty");
  offSel.innerHTML = "";
  facSel.innerHTML = "";

  const [offerings, section] = await Promise.all([
    SSM.request(`/api/academics/subject-offerings/?section=${sectionId}&semester=${semesterId}`),
    SSM.request(`/api/academics/sections/${sectionId}/`),
  ]);
  (offerings.results || offerings).forEach((o) => {
    offSel.appendChild(optionEl(o.id, `${o.subject_code} — ${o.subject_name} (currently: ${o.faculty_name || "unassigned"})`));
  });

  const faculty = await SSM.request(`/api/faculty/?department=${section.department}`);
  (faculty.results || faculty).forEach((f) => facSel.appendChild(optionEl(f.id, `${f.name} (${f.short_code})`)));
}

document.getElementById("fac-tool-btn").addEventListener("click", async () => {
  const resultBox = document.getElementById("fac-tool-result");
  resultBox.innerHTML = "";
  const offering_id = parseInt(document.getElementById("fac-tool-offering").value, 10);
  const new_faculty_id = parseInt(document.getElementById("fac-tool-faculty").value, 10);
  try {
    await SSM.request("/api/scheduling/edit/change-faculty/", { method: "POST", body: { offering_id, new_faculty_id } });
    resultBox.appendChild(SSM.el("div", { class: "alert alert-success", text: "Faculty changed successfully." }));
    await loadTimetable(state.currentSection, state.currentSemester);
    await loadFacultyTool(state.currentSection, state.currentSemester);
  } catch (err) {
    renderViolations(err, resultBox);
  }
});


(async function init() {
  try {
    await loadAcademicYears();
    await loadDepartmentsForGeneration();

    const departmentSelect = document.getElementById("view-department");

    if (departmentSelect.value) {
      departmentSelect.dispatchEvent(new Event("change"));
    }
  } catch (err) {
    console.error("Failed to initialize timetable page:", err);
  }
})();

