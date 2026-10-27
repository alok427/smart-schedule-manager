const DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

function optionEl(value, label) {
  const o = document.createElement("option");
  o.value = value;
  o.textContent = label;
  return o;
}

let allDepartments = [];
let allSubjects = [];
let allFaculty = [];

async function loadDepartments() {
  const sel = document.getElementById("f-department");
  const data = await SSM.request("/api/academics/departments/");
  allDepartments = data.results || data;
  allDepartments.forEach((d) => sel.appendChild(optionEl(d.id, d.name)));

  const rDeptSel = document.getElementById("r-department");
  allDepartments.forEach((d) => rDeptSel.appendChild(optionEl(d.id, d.name)));
}

// ---------------- Faculty list + bulk operations ----------------

async function loadFacultyList() {
  const box = document.getElementById("f-list");
  box.innerHTML = '<span class="text-muted">Loading…</span>';
  try {
    const data = await SSM.request("/api/faculty/");
    allFaculty = data.results || data;
    box.innerHTML = "";
    updateBulkBar();
    if (!allFaculty.length) {
      box.appendChild(SSM.el("div", { class: "text-muted text-center py-4", text: "No faculty configured yet." }));
      return;
    }
    const wrap = document.createElement("div");
    wrap.className = "table-responsive";
    const table = document.createElement("table");
    table.className = "table table-sm table-hover align-middle";
    const thead = document.createElement("thead");
    thead.innerHTML = "<tr><th style='width:2rem;'><input type='checkbox' class='form-check-input' id='f-select-all'></th>" +
      "<th>Code</th><th>Name</th><th>Email</th><th>Type</th><th>Max/day</th><th>Max/week</th><th>Status</th></tr>";
    table.appendChild(thead);
    const tbody = document.createElement("tbody");
    allFaculty.forEach((f) => {
      const tr = document.createElement("tr");
      const selectTd = document.createElement("td");
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.className = "form-check-input f-row-select";
      cb.value = f.id;
      cb.addEventListener("change", updateBulkBar);
      selectTd.appendChild(cb);
      tr.appendChild(selectTd);

      const cells = [f.short_code, f.name, f.email, f.faculty_type, f.max_lectures_per_day, f.max_lectures_per_week];
      cells.forEach((val) => {
        const td = document.createElement("td");
        td.textContent = val;
        tr.appendChild(td);
      });
      const statusTd = document.createElement("td");
      statusTd.appendChild(SSM.el("span", {
        class: `badge text-bg-${f.is_active ? "success" : "secondary"}`,
        text: f.is_active ? "Active" : "Inactive",
      }));
      tr.appendChild(statusTd);
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    wrap.appendChild(table);
    box.appendChild(wrap);

    document.getElementById("f-select-all").addEventListener("change", (e) => {
      document.querySelectorAll(".f-row-select").forEach((cb) => (cb.checked = e.target.checked));
      updateBulkBar();
    });
  } catch (err) {
    box.innerHTML = "";
    box.appendChild(SSM.el("div", { class: "alert alert-danger", text: err.message }));
  }
}

function getSelectedFacultyIds() {
  return Array.from(document.querySelectorAll(".f-row-select:checked")).map((cb) => parseInt(cb.value, 10));
}

function updateBulkBar() {
  const bar = document.getElementById("f-bulk-actions");
  const selected = document.querySelectorAll(".f-row-select:checked").length;
  bar.style.display = selected > 0 ? "" : "none";
}

async function bulkUpdateFaculty(ids, payload) {
  const results = await Promise.allSettled(
    ids.map((id) => SSM.request(`/api/faculty/${id}/`, { method: "PATCH", body: payload }))
  );
  return results;
}

document.getElementById("f-bulk-activate").addEventListener("click", async () => {
  const ids = getSelectedFacultyIds();
  const resultBox = document.getElementById("f-bulk-result");
  resultBox.innerHTML = "";
  const results = await bulkUpdateFaculty(ids, { is_active: true });
  const failed = results.filter((r) => r.status === "rejected").length;
  resultBox.appendChild(SSM.el("div", { class: `alert alert-${failed ? "danger" : "success"}`,
    text: `Activated ${ids.length - failed}/${ids.length} faculty.` }));
  await loadFacultyList();
});

document.getElementById("f-bulk-deactivate").addEventListener("click", async () => {
  const ids = getSelectedFacultyIds();
  const resultBox = document.getElementById("f-bulk-result");
  resultBox.innerHTML = "";
  const results = await bulkUpdateFaculty(ids, { is_active: false });
  const failed = results.filter((r) => r.status === "rejected").length;
  resultBox.appendChild(SSM.el("div", { class: `alert alert-${failed ? "danger" : "success"}`,
    text: `Deactivated ${ids.length - failed}/${ids.length} faculty.` }));
  await loadFacultyList();
});

document.getElementById("f-bulk-delete").addEventListener("click", async () => {
  const ids = getSelectedFacultyIds();
  if (!ids.length) return;
  if (!confirm(`Delete ${ids.length} faculty member(s)? This cannot be undone.`)) return;
  const resultBox = document.getElementById("f-bulk-result");
  resultBox.innerHTML = "";
  const results = await Promise.allSettled(
    ids.map((id) => SSM.request(`/api/faculty/${id}/`, { method: "DELETE" }))
  );
  const failed = results.filter((r) => r.status === "rejected").length;
  resultBox.appendChild(SSM.el("div", { class: `alert alert-${failed ? "danger" : "success"}`,
    text: `Deleted ${ids.length - failed}/${ids.length} faculty.${failed ? " Some may be referenced by existing timetable data and cannot be deleted." : ""}` }));
  await loadFacultyList();
});

document.getElementById("f-submit").addEventListener("click", async () => {
  const errorBox = document.getElementById("form-error");
  errorBox.innerHTML = "";
  const payload = {
    department: parseInt(document.getElementById("f-department").value, 10),
    name: document.getElementById("f-name").value.trim(),
    short_code: document.getElementById("f-short-code").value.trim().toUpperCase(),
    email: document.getElementById("f-email").value.trim(),
    designation: document.getElementById("f-designation").value.trim(),
    faculty_type: document.getElementById("f-type").value,
    max_lectures_per_day: parseInt(document.getElementById("f-max-day").value, 10),
    max_lectures_per_week: parseInt(document.getElementById("f-max-week").value, 10),
  };
  if (!payload.name || !payload.short_code || !payload.email) {
    errorBox.appendChild(SSM.el("div", { class: "alert alert-danger", text: "Name, short code and email are required." }));
    return;
  }
  try {
    await SSM.request("/api/faculty/", { method: "POST", body: payload });
    ["f-name", "f-short-code", "f-email", "f-designation"].forEach((id) => (document.getElementById(id).value = ""));
    await loadFacultyList();
    await loadFacultyOptionsForRules();
  } catch (err) {
    const detail = (err.body && JSON.stringify(err.body)) || err.message;
    errorBox.appendChild(SSM.el("div", { class: "alert alert-danger", text: detail }));
  }
});

// ---------------- Faculty assignment rules ----------------

async function loadFacultyOptionsForRules() {
  const sel = document.getElementById("r-faculty");
  sel.innerHTML = "";
  const data = await SSM.request("/api/faculty/");
  (data.results || data).forEach((f) => sel.appendChild(optionEl(f.id, `${f.name} (${f.short_code}) — ${f.faculty_type}`)));
}

async function loadSubjectOptionsForRules() {
  const sel = document.getElementById("r-subject");
  sel.innerHTML = "";
  const data = await SSM.request("/api/academics/subjects/");
  allSubjects = data.results || data;
  allSubjects.forEach((s) => sel.appendChild(optionEl(s.id, `${s.code} — ${s.name}`)));
}

document.getElementById("r-scope-type").addEventListener("change", (e) => {
  document.getElementById("r-subject-wrap").style.display = e.target.value === "subject" ? "" : "none";
  document.getElementById("r-category-wrap").style.display = e.target.value === "category" ? "" : "none";
  document.getElementById("r-department-wrap").style.display = e.target.value === "department" ? "" : "none";
});

document.getElementById("r-submit").addEventListener("click", async () => {
  const errorBox = document.getElementById("rule-form-error");
  errorBox.innerHTML = "";

  const scopeType = document.getElementById("r-scope-type").value;
  const payload = {
    faculty: parseInt(document.getElementById("r-faculty").value, 10),
    subject: scopeType === "subject" ? parseInt(document.getElementById("r-subject").value, 10) : null,
    subject_category: scopeType === "category" ? document.getElementById("r-category").value : null,
    department: scopeType === "department" ? parseInt(document.getElementById("r-department").value, 10) : null,
    is_generator_eligible: document.getElementById("r-generator-eligible").checked,
    is_active: true,
  };
  const maxLectures = document.getElementById("r-max-lectures").value;
  if (maxLectures) payload.max_lectures = parseInt(maxLectures, 10);

  const fixedDay = document.getElementById("r-fixed-day").value;
  const fixedSlot = document.getElementById("r-fixed-slot").value;
  if (fixedDay !== "" && fixedSlot !== "") {
    payload.fixed_day = parseInt(fixedDay, 10);
    payload.fixed_slot_label = fixedSlot;
  } else if (fixedDay !== "" || fixedSlot !== "") {
    errorBox.appendChild(SSM.el("div", { class: "alert alert-danger", text: "A fixed day needs a fixed period too (and vice versa)." }));
    return;
  }

  try {
    await SSM.request("/api/faculty-assignment-rules/", { method: "POST", body: payload });
    document.getElementById("r-max-lectures").value = "";
    document.getElementById("r-fixed-day").value = "";
    document.getElementById("r-fixed-slot").value = "";
    await loadRulesList();
  } catch (err) {
    const detail = (err.body && JSON.stringify(err.body)) || err.message;
    errorBox.appendChild(SSM.el("div", { class: "alert alert-danger", text: detail }));
  }
});

async function loadRulesList() {
  const box = document.getElementById("r-list");
  box.innerHTML = '<span class="text-muted">Loading…</span>';
  try {
    const data = await SSM.request("/api/faculty-assignment-rules/");
    const items = data.results || data;
    box.innerHTML = "";
    if (!items.length) {
      box.appendChild(SSM.el("div", { class: "text-muted text-center py-4", text: "No assignment rules configured yet." }));
      return;
    }
    const listGroup = document.createElement("div");
    listGroup.className = "list-group list-group-flush";
    items.forEach((r) => {
      const row = document.createElement("div");
      row.className = "list-group-item d-flex justify-content-between align-items-center px-0";
      const scopeText = r.subject_code ? `subject ${r.subject_code}`
        : r.subject_category ? `category ${r.subject_category}`
        : r.department ? "whole department" : "—";
      const left = document.createElement("div");
      left.appendChild(SSM.el("strong", { text: r.faculty_name }));
      const details = [`scope: ${scopeText}`];
      if (r.max_lectures != null) details.push(`max ${r.max_lectures} lectures`);
      if (r.fixed_day != null && r.fixed_slot_label) details.push(`fixed ${DAY_NAMES[r.fixed_day]} ${r.fixed_slot_label}`);
      details.push(r.is_generator_eligible ? "auto-assignable" : "manual-only");
      left.appendChild(SSM.el("div", { class: "cell-meta", text: details.join(" · ") }));
      row.appendChild(left);

      const delBtn = SSM.el("button", { class: "btn btn-outline-danger btn-sm", text: "Delete" });
      delBtn.addEventListener("click", async () => {
        if (!confirm("Delete this rule?")) return;
        await SSM.request(`/api/faculty-assignment-rules/${r.id}/`, { method: "DELETE" });
        await loadRulesList();
      });
      row.appendChild(delBtn);
      listGroup.appendChild(row);
    });
    box.appendChild(listGroup);
  } catch (err) {
    box.innerHTML = "";
    box.appendChild(SSM.el("div", { class: "alert alert-danger", text: err.message }));
  }
}

(async function init() {
  await loadDepartments();
  await loadFacultyList();
  await loadFacultyOptionsForRules();
  await loadSubjectOptionsForRules();
  await loadRulesList();
})();
