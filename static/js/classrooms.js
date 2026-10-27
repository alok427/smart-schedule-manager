function optionEl(value, label) {
  const o = document.createElement("option");
  o.value = value;
  o.textContent = label;
  return o;
}

let allClassrooms = [];

async function loadDepartments() {
  const sel = document.getElementById("c-department");
  const data = await SSM.request("/api/academics/departments/");
  (data.results || data).forEach((d) => sel.appendChild(optionEl(d.id, d.name)));
}

async function loadClassroomList() {
  const box = document.getElementById("c-list");
  box.innerHTML = '<span class="text-muted">Loading…</span>';
  try {
    const data = await SSM.request("/api/classrooms/");
    allClassrooms = data.results || data;
    box.innerHTML = "";
    updateBulkBar();
    if (!allClassrooms.length) {
      box.appendChild(SSM.el("div", { class: "text-muted text-center py-4", text: "No classrooms configured yet." }));
      return;
    }
    const wrap = document.createElement("div");
    wrap.className = "table-responsive";
    const table = document.createElement("table");
    table.className = "table table-sm table-hover align-middle";
    const thead = document.createElement("thead");
    thead.innerHTML = "<tr><th style='width:2rem;'><input type='checkbox' class='form-check-input' id='c-select-all'></th>" +
      "<th>Room</th><th>Building</th><th>Type</th><th>Capacity</th><th>Status</th></tr>";
    table.appendChild(thead);
    const tbody = document.createElement("tbody");
    allClassrooms.forEach((c) => {
      const tr = document.createElement("tr");

      const selectTd = document.createElement("td");
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.className = "form-check-input c-row-select";
      cb.value = c.id;
      cb.addEventListener("change", updateBulkBar);
      selectTd.appendChild(cb);
      tr.appendChild(selectTd);

      const roomTd = document.createElement("td");
      roomTd.textContent = c.room_number;
      tr.appendChild(roomTd);

      const buildingTd = document.createElement("td");
      buildingTd.textContent = c.building || "-";
      tr.appendChild(buildingTd);

      const typeTd = document.createElement("td");
      typeTd.appendChild(SSM.el("span", {
        class: `badge text-bg-${c.room_type === "LAB" ? "warning" : "secondary"}`, text: c.room_type,
      }));
      tr.appendChild(typeTd);

      const capTd = document.createElement("td");
      capTd.textContent = c.capacity;
      tr.appendChild(capTd);

      const statusTd = document.createElement("td");
      statusTd.appendChild(SSM.el("span", {
        class: `badge text-bg-${c.is_active ? "success" : "secondary"}`,
        text: c.is_active ? "Active" : "Inactive",
      }));
      tr.appendChild(statusTd);

      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    wrap.appendChild(table);
    box.appendChild(wrap);

    document.getElementById("c-select-all").addEventListener("change", (e) => {
      document.querySelectorAll(".c-row-select").forEach((cb) => (cb.checked = e.target.checked));
      updateBulkBar();
    });
  } catch (err) {
    box.innerHTML = "";
    box.appendChild(SSM.el("div", { class: "alert alert-danger", text: err.message }));
  }
}

function getSelectedClassroomIds() {
  return Array.from(document.querySelectorAll(".c-row-select:checked")).map((cb) => parseInt(cb.value, 10));
}

function updateBulkBar() {
  const bar = document.getElementById("c-bulk-actions");
  const selected = document.querySelectorAll(".c-row-select:checked").length;
  bar.style.display = selected > 0 ? "" : "none";
}

document.getElementById("c-bulk-activate").addEventListener("click", async () => {
  const ids = getSelectedClassroomIds();
  const resultBox = document.getElementById("c-bulk-result");
  resultBox.innerHTML = "";
  const results = await Promise.allSettled(ids.map((id) => SSM.request(`/api/classrooms/${id}/`, { method: "PATCH", body: { is_active: true } })));
  const failed = results.filter((r) => r.status === "rejected").length;
  resultBox.appendChild(SSM.el("div", { class: `alert alert-${failed ? "danger" : "success"}`, text: `Activated ${ids.length - failed}/${ids.length} rooms.` }));
  await loadClassroomList();
});

document.getElementById("c-bulk-deactivate").addEventListener("click", async () => {
  const ids = getSelectedClassroomIds();
  const resultBox = document.getElementById("c-bulk-result");
  resultBox.innerHTML = "";
  const results = await Promise.allSettled(ids.map((id) => SSM.request(`/api/classrooms/${id}/`, { method: "PATCH", body: { is_active: false } })));
  const failed = results.filter((r) => r.status === "rejected").length;
  resultBox.appendChild(SSM.el("div", { class: `alert alert-${failed ? "danger" : "success"}`, text: `Deactivated ${ids.length - failed}/${ids.length} rooms.` }));
  await loadClassroomList();
});

document.getElementById("c-bulk-delete").addEventListener("click", async () => {
  const ids = getSelectedClassroomIds();
  if (!ids.length) return;
  if (!confirm(`Delete ${ids.length} room(s)? This cannot be undone.`)) return;
  const resultBox = document.getElementById("c-bulk-result");
  resultBox.innerHTML = "";
  const results = await Promise.allSettled(ids.map((id) => SSM.request(`/api/classrooms/${id}/`, { method: "DELETE" })));
  const failed = results.filter((r) => r.status === "rejected").length;
  resultBox.appendChild(SSM.el("div", { class: `alert alert-${failed ? "danger" : "success"}`,
    text: `Deleted ${ids.length - failed}/${ids.length} rooms.${failed ? " Some may be referenced by existing timetable data and cannot be deleted." : ""}` }));
  await loadClassroomList();
});

document.getElementById("c-submit").addEventListener("click", async () => {
  const errorBox = document.getElementById("form-error");
  errorBox.innerHTML = "";
  const deptVal = document.getElementById("c-department").value;
  const payload = {
    department: deptVal ? parseInt(deptVal, 10) : null,
    room_number: document.getElementById("c-room-number").value.trim().toUpperCase(),
    building: document.getElementById("c-building").value.trim(),
    room_type: document.getElementById("c-type").value,
    capacity: parseInt(document.getElementById("c-capacity").value, 10),
  };
  if (!payload.room_number) {
    errorBox.appendChild(SSM.el("div", { class: "alert alert-danger", text: "Room number is required." }));
    return;
  }
  try {
    await SSM.request("/api/classrooms/", { method: "POST", body: payload });
    document.getElementById("c-room-number").value = "";
    document.getElementById("c-building").value = "";
    await loadClassroomList();
  } catch (err) {
    const detail = (err.body && JSON.stringify(err.body)) || err.message;
    errorBox.appendChild(SSM.el("div", { class: "alert alert-danger", text: detail }));
  }
});

(async function init() {
  await loadDepartments();
  await loadClassroomList();
})();
