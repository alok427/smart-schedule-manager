function optionEl(value, label) {
  const o = document.createElement("option");
  o.value = value;
  o.textContent = label;
  return o;
}

let allSubjects = [];

async function loadDepartments() {
  const sel = document.getElementById("s-department");
  const data = await SSM.request("/api/academics/departments/");
  (data.results || data).forEach((d) => sel.appendChild(optionEl(d.id, d.name)));
  if (sel.options.length) sel.dispatchEvent(new Event("change"));
}

document.getElementById("s-department").addEventListener("change", async (e) => {
  const yearSel = document.getElementById("s-year");
  yearSel.innerHTML = "";
  const data = await SSM.request(`/api/academics/years/?department=${e.target.value}`);
  (data.results || data).forEach((y) => yearSel.appendChild(optionEl(y.id, `Year ${y.year_number}${y.is_active ? "" : " (OFF)"}`)));
});

async function loadSubjectList() {
  const box = document.getElementById("s-list");
  box.innerHTML = '<span class="text-muted">Loading…</span>';
  try {
    const data = await SSM.request("/api/academics/subjects/");
    allSubjects = data.results || data;
    box.innerHTML = "";
    updateBulkBar();
    if (!allSubjects.length) {
      box.appendChild(SSM.el("div", { class: "text-muted text-center py-4", text: "No subjects configured yet." }));
      return;
    }
    const wrap = document.createElement("div");
    wrap.className = "table-responsive";
    const table = document.createElement("table");
    table.className = "table table-sm table-hover align-middle";
    const thead = document.createElement("thead");
    thead.innerHTML = "<tr><th style='width:2rem;'><input type='checkbox' class='form-check-input' id='s-select-all'></th>" +
      "<th>Code</th><th>Name</th><th>Category</th><th>Lecture</th><th>Tutorial</th><th>Practical</th><th>Credits</th><th>Batches</th></tr>";
    table.appendChild(thead);
    const tbody = document.createElement("tbody");
    allSubjects.forEach((s) => {
      const tr = document.createElement("tr");

      const selectTd = document.createElement("td");
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.className = "form-check-input s-row-select";
      cb.value = s.id;
      cb.addEventListener("change", updateBulkBar);
      selectTd.appendChild(cb);
      tr.appendChild(selectTd);

      const codeTd = document.createElement("td");
      codeTd.textContent = s.code;
      tr.appendChild(codeTd);

      const nameTd = document.createElement("td");
      nameTd.textContent = s.name;
      tr.appendChild(nameTd);

      const catTd = document.createElement("td");
      catTd.appendChild(SSM.el("span", {
        class: `badge text-bg-${s.category === "CORE" ? "success" : "secondary"}`, text: s.category,
      }));
      tr.appendChild(catTd);

      [s.lecture_hours, s.tutorial_hours, s.practical_hours, s.credits].forEach((val) => {
        const td = document.createElement("td");
        td.textContent = val;
        tr.appendChild(td);
      });

      const batchTd = document.createElement("td");
      batchTd.textContent = s.has_batches ? `Yes (${s.num_batches})` : "No";
      tr.appendChild(batchTd);

      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    wrap.appendChild(table);
    box.appendChild(wrap);

    document.getElementById("s-select-all").addEventListener("change", (e) => {
      document.querySelectorAll(".s-row-select").forEach((cb) => (cb.checked = e.target.checked));
      updateBulkBar();
    });
  } catch (err) {
    box.innerHTML = "";
    box.appendChild(SSM.el("div", { class: "alert alert-danger", text: err.message }));
  }
}

function getSelectedSubjectIds() {
  return Array.from(document.querySelectorAll(".s-row-select:checked")).map((cb) => parseInt(cb.value, 10));
}

function updateBulkBar() {
  const bar = document.getElementById("s-bulk-actions");
  const selected = document.querySelectorAll(".s-row-select:checked").length;
  bar.style.display = selected > 0 ? "" : "none";
}

document.getElementById("s-bulk-activate").addEventListener("click", async () => {
  const ids = getSelectedSubjectIds();
  const resultBox = document.getElementById("s-bulk-result");
  resultBox.innerHTML = "";
  const results = await Promise.allSettled(ids.map((id) => SSM.request(`/api/academics/subjects/${id}/`, { method: "PATCH", body: { is_active: true } })));
  const failed = results.filter((r) => r.status === "rejected").length;
  resultBox.appendChild(SSM.el("div", { class: `alert alert-${failed ? "danger" : "success"}`, text: `Activated ${ids.length - failed}/${ids.length} subjects.` }));
  await loadSubjectList();
});

document.getElementById("s-bulk-deactivate").addEventListener("click", async () => {
  const ids = getSelectedSubjectIds();
  const resultBox = document.getElementById("s-bulk-result");
  resultBox.innerHTML = "";
  const results = await Promise.allSettled(ids.map((id) => SSM.request(`/api/academics/subjects/${id}/`, { method: "PATCH", body: { is_active: false } })));
  const failed = results.filter((r) => r.status === "rejected").length;
  resultBox.appendChild(SSM.el("div", { class: `alert alert-${failed ? "danger" : "success"}`, text: `Deactivated ${ids.length - failed}/${ids.length} subjects.` }));
  await loadSubjectList();
});

document.getElementById("s-bulk-delete").addEventListener("click", async () => {
  const ids = getSelectedSubjectIds();
  if (!ids.length) return;
  if (!confirm(`Delete ${ids.length} subject(s)? This cannot be undone.`)) return;
  const resultBox = document.getElementById("s-bulk-result");
  resultBox.innerHTML = "";
  const results = await Promise.allSettled(ids.map((id) => SSM.request(`/api/academics/subjects/${id}/`, { method: "DELETE" })));
  const failed = results.filter((r) => r.status === "rejected").length;
  resultBox.appendChild(SSM.el("div", { class: `alert alert-${failed ? "danger" : "success"}`,
    text: `Deleted ${ids.length - failed}/${ids.length} subjects.${failed ? " Some may be referenced by existing offerings and cannot be deleted." : ""}` }));
  await loadSubjectList();
});

document.getElementById("s-submit").addEventListener("click", async () => {
  const errorBox = document.getElementById("form-error");
  errorBox.innerHTML = "";
  const practical = parseInt(document.getElementById("s-practical").value, 10);
  if (practical % 2 !== 0) {
    errorBox.appendChild(SSM.el("div", { class: "alert alert-danger", text: "Practical hours must be even (2-period lab blocks)." }));
    return;
  }
  const hasBatches = document.getElementById("s-has-batches").checked;
  const payload = {
    department: parseInt(document.getElementById("s-department").value, 10),
    year: parseInt(document.getElementById("s-year").value, 10),
    code: document.getElementById("s-code").value.trim().toUpperCase(),
    name: document.getElementById("s-name").value.trim(),
    category: document.getElementById("s-category").value,
    lecture_hours: parseInt(document.getElementById("s-lecture").value, 10),
    tutorial_hours: parseInt(document.getElementById("s-tutorial").value, 10),
    practical_hours: practical,
    credits: parseFloat(document.getElementById("s-credits").value),
    has_batches: hasBatches,
    num_batches: hasBatches ? 2 : 1,
  };
  if (!payload.code || !payload.name) {
    errorBox.appendChild(SSM.el("div", { class: "alert alert-danger", text: "Subject code and name are required." }));
    return;
  }
  try {
    await SSM.request("/api/academics/subjects/", { method: "POST", body: payload });
    ["s-code", "s-name"].forEach((id) => (document.getElementById(id).value = ""));
    await loadSubjectList();
  } catch (err) {
    const detail = (err.body && JSON.stringify(err.body)) || err.message;
    errorBox.appendChild(SSM.el("div", { class: "alert alert-danger", text: detail }));
  }
});

(async function init() {
  await loadDepartments();
  await loadSubjectList();
})();
