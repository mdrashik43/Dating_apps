const BASE = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000/api";

export const tokenStore = {
  get: () => localStorage.getItem("vm_token"),
  set: (t) => localStorage.setItem("vm_token", t),
  clear: () => localStorage.removeItem("vm_token"),
};

function message(d) {
  if (!d) return "Something went wrong. Is the Django server running?";
  if (d.detail) return d.detail;
  return Object.values(d).flat().join(" ") || "Something went wrong.";
}

export async function api(path, { method = "GET", body } = {}) {
  const token = tokenStore.get();
  let res;
  try {
    res = await fetch(BASE + path, {
      method,
      headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Token ${token}` } : {}) },
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw Object.assign(new Error("Cannot reach the server. Is Django running?"), { status: 0 });
  }
  const data = res.status === 204 ? null : await res.json().catch(() => null);
  if (!res.ok) throw Object.assign(new Error(message(data)), { status: res.status });
  return data;
}
