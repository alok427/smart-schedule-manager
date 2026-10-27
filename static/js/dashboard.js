async function loadStats() {
  const grid = document.getElementById("stats");
  try {
    const s = await SSM.request("/api/dashboard/stats/");
    const cells = [
      ["Faculty", s.faculty_count],
      ["Departments", s.department_count],
      ["Sections", s.section_count],
      ["Subjects", s.subject_count],
      ["Classrooms", s.classroom_count],
      ["Labs", s.lab_count],
      ["Failed generations", s.failed_generation_count],
    ];
    grid.innerHTML = "";
    cells.forEach(([label, num]) => {
      const col = SSM.el("div", { class: "col" }, [
        SSM.el("div", { class: "card h-100" }, [
          SSM.el("div", { class: "card-body py-3" }, [
            SSM.el("div", { class: "stat-num", text: num }),
            SSM.el("div", { class: "stat-label", text: label }),
          ]),
        ]),
      ]);
      grid.appendChild(col);
    });

    const conflictsBox = document.getElementById("conflicts");
    conflictsBox.innerHTML = "";
    if (!s.recent_conflicts.length) {
      conflictsBox.appendChild(SSM.el("div", { class: "text-muted text-center py-4", text: "No conflicts recorded. Every recent generation was clean." }));
    } else {
      s.recent_conflicts.forEach((c) => {
        conflictsBox.appendChild(SSM.el("div", { class: "alert alert-danger", text: `${c.section} — ${c.message}` }));
      });
    }
  } catch (err) {
    grid.innerHTML = "";
    grid.appendChild(SSM.el("div", { class: "alert alert-danger", text: err.message }));
  }
}

let searchTimer = null;
document.getElementById("search-input").addEventListener("input", (e) => {
  clearTimeout(searchTimer);
  const q = e.target.value.trim();
  const box = document.getElementById("search-results");
  if (!q) { box.innerHTML = ""; return; }
  searchTimer = setTimeout(async () => {
    try {
      const data = await SSM.request(`/api/dashboard/search/?q=${encodeURIComponent(q)}`);
      box.innerHTML = "";
      const sections = [
        ["Faculty", data.faculty.map((f) => `${f.name} (${f.short_code})`)],
        ["Subjects", data.subjects.map((s) => `${s.code} — ${s.name}`)],
        ["Classrooms", data.classrooms.map((c) => `${c.room_number} (${c.type})`)],
        ["Sections", data.sections.map((s) => s.name)],
      ];
      let any = false;
      sections.forEach(([label, items]) => {
        if (!items.length) return;
        any = true;
        box.appendChild(SSM.el("h6", { class: "font-display mt-3", text: label }));
        items.forEach((t) => box.appendChild(SSM.el("div", { text: "· " + t })));
      });
      if (!any) box.appendChild(SSM.el("div", { class: "text-muted", text: "No matches." }));
    } catch (err) {
      box.innerHTML = "";
      box.appendChild(SSM.el("div", { class: "alert alert-danger", text: err.message }));
    }
  }, 300);
});

loadStats();
