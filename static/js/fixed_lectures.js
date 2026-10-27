function optionEl(value, label) {
  const o = document.createElement("option");
  o.value = value;
  o.textContent = label;
  return o;
}

const DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
let currentSectionId = null;
let currentSemesterId = null;
let currentAcademicYearId = null;

async function loadDepartments() {
  const sel = document.getElementById("fl-department");
  const data = await SSM.request("/api/academics/departments/");
  (data.results || data).forEach((d) => sel.appendChild(optionEl(d.id, d.name)));
  if (sel.options.length) sel.dispatchEvent(new Event("change"));
}

document.getElementById("fl-department").addEventListener("change", async (e) => {
  const sectionSel = document.getElementById("fl-section");
  sectionSel.innerHTML = "";
  const data = await SSM.request(`/api/academics/sections/?department=${e.target.value}`);
  (data.results || data).forEach((s) => sectionSel.appendChild(optionEl(s.id, `Year ${s.year_number} - ${s.name}`)));
  if (sectionSel.options.length) sectionSel.dispatchEvent(new Event("change"));

  const facSel = document.getElementById("fl-faculty");
  facSel.innerHTML = '<option value="">— none —</option>';
  const facData = await SSM.request(`/api/faculty/?department=${e.target.value}`);
  (facData.results || facData).forEach((f) => facSel.appendChild(optionEl(f.id, `${f.name} (${f.short_code})`)));

  const roomSel = document.getElementById("fl-classroom");
  roomSel.innerHTML = '<option value="">— none —</option>';
  const roomData = await SSM.request(`/api/classrooms/?department=${e.target.value}`);
  (roomData.results || roomData).forEach((r) => roomSel.appendChild(optionEl(r.id, `${r.room_number} (${r.room_type})`)));
});

document.getElementById("fl-section").addEventListener("change", async (e) => {
  const semSel = document.getElementById("fl-semester");
  semSel.innerHTML = "";
  const sectionId = e.target.value;
  if (!sectionId) return;
  currentSectionId = sectionId;
  const secData = await SSM.request(`/api/academics/sections/${sectionId}/`);
  currentAcademicYearId = secData.academic_year;
  const data = await SSM.request(`/api/academics/semesters/?year=${secData.year}`);
  (data.results || data).forEach((s) => semSel.appendChild(optionEl(s.id, `Semester ${s.semester_number} (${s.semester_type})`)));
  if (semSel.options.length) semSel.dispatchEvent(new Event("change"));
});

document.getElementById("fl-semester").addEventListener("change", async (e) => {
  currentSemesterId = e.target.value;
  await loadOfferings();
  await loadFixedList();
});

async function loadOfferings() {
  const offSel = document.getElementById("fl-offering");
  offSel.innerHTML = "";
  if (!currentSectionId || !currentSemesterId) return;
  const data = await SSM.request(`/api/academics/subject-offerings/?section=${currentSectionId}&semester=${currentSemesterId}`);
  (data.results || data).forEach((o) => offSel.appendChild(optionEl(o.id, `${o.subject_code} — ${o.subject_name}`)));
}

async function loadFixedList() {
  const box = document.getElementById("fl-list");
  if (!currentSectionId || !currentSemesterId) return;
  box.innerHTML = '<span class="text-muted">Loading…</span>';
  try {
    const data = await SSM.request(`/api/scheduling/fixed-lectures/?subject_offering__section=${currentSectionId}&subject_offering__semester=${currentSemesterId}`);
    const items = data.results || data;
    box.innerHTML = "";
    if (!items.length) {
      box.appendChild(SSM.el("div", { class: "text-muted text-center py-4", text: "No fixed lectures for this section/semester yet." }));
      return;
    }
    const listGroup = document.createElement("div");
    listGroup.className = "list-group list-group-flush";
    items.forEach((fl) => {
      const row = document.createElement("div");
      row.className = "list-group-item px-0";
      row.textContent = `${DAY_NAMES[fl.day]} ${fl.period_label} — ${fl.session_type}` +
        (fl.notes ? ` — ${fl.notes}` : "");
      listGroup.appendChild(row);
    });
    box.appendChild(listGroup);
  } catch (err) {
    box.innerHTML = "";
    box.appendChild(SSM.el("div", { class: "alert alert-danger", text: err.message }));
  }
}

document.getElementById("fl-submit").addEventListener("click", async () => {
  const errorBox = document.getElementById("form-error");
  errorBox.innerHTML = "";
  const offeringId = document.getElementById("fl-offering").value;
  if (!offeringId) {
    errorBox.appendChild(SSM.el("div", { class: "alert alert-danger", text: "Select a subject first." }));
    return;
  }
  const payload = {
    academic_year: parseInt(currentAcademicYearId, 10),
    subject_offering: parseInt(offeringId, 10),
    session_type: document.getElementById("fl-session-type").value,
    faculty: document.getElementById("fl-faculty").value || null,
    classroom: document.getElementById("fl-classroom").value || null,
    day: parseInt(document.getElementById("fl-day").value, 10),
    period_label: document.getElementById("fl-period").value,
    notes: document.getElementById("fl-notes").value,
  };
  try {
    await SSM.request("/api/scheduling/fixed-lectures/", { method: "POST", body: payload });
    document.getElementById("fl-notes").value = "";
    await loadFixedList();
  } catch (err) {
    errorBox.appendChild(SSM.el("div", { class: "alert alert-danger", text: err.message }));
  }
});

loadDepartments();
