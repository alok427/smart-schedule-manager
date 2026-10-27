/* Smart Schedule Manager — shared API/auth helper.
 * Every page includes this before its own page script. Tokens live in
 * localStorage (standard practice for a JWT + server-rendered-template
 * app like this one — this is a real deployable Django project, not a
 * sandboxed artifact).
 */
const SSM = (() => {
  const ACCESS_KEY = "ssm_access";
  const REFRESH_KEY = "ssm_refresh";
  const USER_KEY = "ssm_user";

  function getAccess() { return localStorage.getItem(ACCESS_KEY); }
  function getRefresh() { return localStorage.getItem(REFRESH_KEY); }
  function getUser() {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  }
  function setSession(access, refresh, user) {
    localStorage.setItem(ACCESS_KEY, access);
    if (refresh) localStorage.setItem(REFRESH_KEY, refresh);
    if (user) localStorage.setItem(USER_KEY, JSON.stringify(user));
  }
  function clearSession() {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
    localStorage.removeItem(USER_KEY);
  }

  async function refreshAccessToken() {
    const refresh = getRefresh();
    if (!refresh) return false;
    const resp = await fetch("/api/accounts/auth/refresh/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh }),
    });
    if (!resp.ok) return false;
    const data = await resp.json();
    localStorage.setItem(ACCESS_KEY, data.access);
    return true;
  }

  /** Core request helper. Auto-attaches JWT, auto-retries once on 401
   * after a token refresh, and throws ApiError with parsed JSON body on
   * failure so callers can show real backend validation messages. */
  async function request(path, { method = "GET", body, isForm = false } = {}) {
    const doFetch = () => {
      const headers = {};
      const access = getAccess();
      if (access) headers["Authorization"] = `Bearer ${access}`;
      let payload = body;
      if (body && !isForm) {
        headers["Content-Type"] = "application/json";
        payload = JSON.stringify(body);
      }
      return fetch(path, { method, headers, body: payload });
    };

    let resp = await doFetch();
    if (resp.status === 401 && getRefresh()) {
      const ok = await refreshAccessToken();
      if (ok) resp = await doFetch();
    }

    // Still unauthorised after a refresh attempt: the session is dead.
    // Send the user to sign in instead of showing a raw token error.
    if (resp.status === 401 && !path.includes("/auth/login/")) {
      clearSession();
      window.location.href = "/login/";
      throw new Error("Your session has expired. Redirecting to sign in…");
    }

    const contentType = resp.headers.get("content-type") || "";
    const isJson = contentType.includes("application/json");
    const data = isJson ? await resp.json().catch(() => null) : null;

    if (!resp.ok) {
      const err = new Error((data && (data.detail || JSON.stringify(data))) || `Request failed (${resp.status})`);
      err.status = resp.status;
      err.body = data;
      throw err;
    }
    return isJson ? data : resp;
  }

  function requireAuth() {
    if (!getAccess()) {
      window.location.href = "/login/";
      return false;
    }
    return true;
  }

  function logout() {
    clearSession();
    window.location.href = "/login/";
  }

  const DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

  function el(tag, attrs = {}, children = []) {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (k === "text") node.textContent = v;
      else if (k === "html") node.innerHTML = v;
      else if (k.startsWith("on") && typeof v === "function") node.addEventListener(k.slice(2), v);
      else node.setAttribute(k, v);
    }
    (Array.isArray(children) ? children : [children]).forEach((c) => c && node.appendChild(c));
    return node;
  }

  return { getAccess, getRefresh, getUser, setSession, clearSession, request, requireAuth, logout, DAY_NAMES, el };
})();
