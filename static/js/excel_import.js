function optionEl(value, label) {
  const o = document.createElement("option");
  o.value = value;
  o.textContent = label;
  return o;
}

async function loadDepartmentsAndYears() {
  const deptSel = document.getElementById("import-department");
  const yearSel = document.getElementById("import-year");
  const data = await SSM.request("/api/academics/departments/");
  const depts = data.results || data;
  deptSel.innerHTML = "";
  depts.forEach((d) => deptSel.appendChild(optionEl(d.id, d.name)));

  async function loadYears() {
    yearSel.innerHTML = "";
    const yearsData = await SSM.request(`/api/academics/years/?department=${deptSel.value}`);
    (yearsData.results || yearsData).forEach((y) => yearSel.appendChild(optionEl(y.id, `Year ${y.year_number}`)));
  }
  deptSel.addEventListener("change", loadYears);
  if (depts.length) await loadYears();
}

document.getElementById("template-link").addEventListener("click", async (e) => {
  e.preventDefault();
  try {
    const url0 = "/api/data-import/template/";
    const doFetch = () => fetch(url0, { headers: { Authorization: `Bearer ${SSM.getAccess()}` } });
    let resp = await doFetch();
    // Access tokens expire (60 min). Refresh once and retry before giving up.
    if (resp.status === 401 && (await SSM.refreshAccessToken())) resp = await doFetch();
    if (resp.status === 401) {
      SSM.clearSession();
      window.location.href = "/login/";
      return;
    }
    if (!resp.ok) throw new Error(`Could not download the template (HTTP ${resp.status}).`);
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "college_timetable_excel_template.xlsx";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  } catch (err) {
    alert(err.message);
  }
});

document.getElementById("import-btn").addEventListener("click", async () => {
  const resultBox = document.getElementById("import-result");
  resultBox.innerHTML = "";
  const fileInput = document.getElementById("import-file");
  if (!fileInput.files.length) {
    resultBox.appendChild(SSM.el("div", { class: "alert alert-danger", text: "Choose a file first." }));
    return;
  }
  const btn = document.getElementById("import-btn");
  btn.disabled = true;
  btn.textContent = "Importing…";

  const formData = new FormData();
  formData.append("file", fileInput.files[0]);
  formData.append("department_id", document.getElementById("import-department").value);
  formData.append("year_id", document.getElementById("import-year").value);

  try {
    const batch = await SSM.request("/api/data-import/import/", { method: "POST", body: formData, isForm: true });
    renderBatchResult(batch, resultBox);
    await loadHistory();
  } catch (err) {
    if (err.body) {
      renderBatchResult(err.body, resultBox);
    } else {
      resultBox.appendChild(SSM.el("div", { class: "alert alert-danger", text: err.message }));
    }
  } finally {
    btn.disabled = false;
    btn.textContent = "Import";
  }
});

function renderBatchResult(batch, container) {
  // The server sent an error message instead of an import summary (for
  // example: expired login, wrong department, no permission). Show that
  // message rather than a row of "undefined" values.
  if (!batch || batch.status === undefined) {
    let msg = "Import failed. Please try again.";
    if (batch && batch.detail) msg = batch.detail;
    else if (batch && typeof batch === "object" && Object.keys(batch).length) msg = JSON.stringify(batch);
    container.appendChild(SSM.el("div", { class: "alert alert-danger", text: msg }));
    return;
  }
  const tagClass = batch.status === "SUCCESS" ? "success" : batch.status === "PARTIAL" ? "warning" : "danger";
  const box = SSM.el("div", { class: `alert alert-${batch.status === "FAILED" ? "danger" : "success"}` });
  box.appendChild(SSM.el("span", { class: `badge text-bg-${tagClass} me-2`, text: batch.status }));
  box.appendChild(SSM.el("div", { style: "margin-top:8px;", text:
    `Faculty imported: ${batch.faculty_imported}   Subjects imported: ${batch.subjects_imported}   Classrooms imported: ${batch.classrooms_imported}   Warnings: ${batch.warning_count}   Errors: ${batch.error_count}` }));
  if (batch.errors && batch.errors.length) {
    const ul = document.createElement("ul");
    batch.errors.forEach((e) => ul.appendChild(SSM.el("li", { text: e })));
    box.appendChild(ul);
  }
  if (batch.warnings && batch.warnings.length) {
    const ul = document.createElement("ul");
    batch.warnings.forEach((w) => ul.appendChild(SSM.el("li", { text: w })));
    box.appendChild(ul);
  }
  container.appendChild(box);
}

async function loadHistory() {
  const box = document.getElementById("import-history");
  try {
    const batches = await SSM.request("/api/data-import/batches/");
    box.innerHTML = "";
    if (!batches.length) {
      box.appendChild(SSM.el("div", { class: "text-muted text-center py-4", text: "No imports yet." }));
      return;
    }
    const listGroup = document.createElement("div");
    listGroup.className = "list-group list-group-flush";
    batches.forEach((b) => {
      const tagClass = b.status === "SUCCESS" ? "success" : b.status === "PARTIAL" ? "warning" : "danger";
      const row = document.createElement("div");
      row.className = "list-group-item px-0";
      row.appendChild(SSM.el("span", { class: `badge text-bg-${tagClass} me-2`, text: b.status }));
      row.appendChild(document.createTextNode(
        ` ${b.original_filename} — ${new Date(b.created_at).toLocaleString()} — ` +
        `F:${b.faculty_imported} S:${b.subjects_imported} C:${b.classrooms_imported} ` +
        `(${b.warning_count} warnings, ${b.error_count} errors)`
      ));
      listGroup.appendChild(row);
    });
    box.appendChild(listGroup);
  } catch (err) {
    box.innerHTML = "";
    box.appendChild(SSM.el("div", { class: "alert alert-danger", text: err.message }));
  }
}

(async function init() {
  await loadDepartmentsAndYears();
  await loadHistory();
})();
