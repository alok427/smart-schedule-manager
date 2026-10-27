document.getElementById("login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = document.getElementById("submit-btn");
  const errorBox = document.getElementById("error-box");
  errorBox.innerHTML = "";
  btn.disabled = true;
  btn.textContent = "Signing in…";

  const username = document.getElementById("username").value.trim();
  const password = document.getElementById("password").value;

  try {
    const resp = await fetch("/api/accounts/auth/login/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    const data = await resp.json();
    if (!resp.ok) {
      throw new Error(data.detail || "Invalid username or password.");
    }
    SSM.setSession(data.access, data.refresh, { role: data.role, department_id: data.department_id, username });

    // Fetch the full profile so the sidebar has a display name.
    const me = await SSM.request("/api/accounts/auth/me/");
    SSM.setSession(data.access, data.refresh, me);

    const dest = { SUPER_ADMIN: "/dashboard/", DEPT_ADMIN: "/dashboard/", FACULTY: "/faculty/", STUDENT: "/student/" };
    window.location.href = dest[data.role] || "/dashboard/";
  } catch (err) {
    const box = document.createElement("div");
    box.className = "alert alert-danger mt-2";
    box.textContent = err.message;
    errorBox.appendChild(box);
    btn.disabled = false;
    btn.textContent = "Sign in";
  }
});
