const CATEGORY_TAGS = {
  TIMETABLE_PUBLISHED: "success",
  TIMETABLE_GENERATED: "success",
  TIMETABLE_UPDATED: "secondary",
  FACULTY_CHANGED: "secondary",
  CLASSROOM_CHANGED: "secondary",
  TIMETABLE_RESTORED: "secondary",
  CONFLICT_WARNING: "warning",
  GENERATION_FAILED: "danger",
  IMPORT_SUMMARY: "secondary",
};

async function loadNotifications() {
  const list = document.getElementById("notif-list");
  try {
    const data = await SSM.request("/api/notifications/mine/");
    list.innerHTML = "";
    if (!data.notifications.length) {
      list.appendChild(SSM.el("div", { class: "text-muted text-center py-4", text: "No notifications yet." }));
      return;
    }
    const listGroup = document.createElement("div");
    listGroup.className = "list-group list-group-flush";
    data.notifications.forEach((n) => {
      const row = document.createElement("div");
      row.className = "list-group-item d-flex justify-content-between align-items-start gap-3" + (n.is_read ? "" : " bg-light");
      const left = document.createElement("div");
      const tagClass = CATEGORY_TAGS[n.category] || "secondary";
      const headRow = document.createElement("div");
      headRow.appendChild(SSM.el("span", { class: `badge text-bg-${tagClass}`, text: n.category.replace(/_/g, " ") }));
      headRow.appendChild(SSM.el("strong", { text: " " + n.title, class: "ms-2" }));
      left.appendChild(headRow);
      if (n.body) left.appendChild(SSM.el("div", { class: "cell-meta mt-1", text: n.body }));
      left.appendChild(SSM.el("div", { class: "helptext mt-1", text: new Date(n.created_at).toLocaleString() }));
      row.appendChild(left);
      if (!n.is_read) {
        const btn = SSM.el("button", { class: "btn btn-outline-secondary btn-sm flex-shrink-0", text: "Mark read" });
        btn.addEventListener("click", async () => {
          await SSM.request(`/api/notifications/${n.id}/read/`, { method: "POST" });
          loadNotifications();
        });
        row.appendChild(btn);
      }
      listGroup.appendChild(row);
    });
    list.appendChild(listGroup);
  } catch (err) {
    list.innerHTML = "";
    list.appendChild(SSM.el("div", { class: "alert alert-danger", text: err.message }));
  }
}

document.getElementById("mark-all-btn").addEventListener("click", async () => {
  await SSM.request("/api/notifications/mark-all-read/", { method: "POST" });
  loadNotifications();
});

loadNotifications();
