export const API_URL = "https://foodbodyconnection.54.253.73.35.nip.io";

export async function apiFetch(endpoint, options = {}) {
  const token = localStorage.getItem("access_token");

  const headers = {
    ...(token && { Authorization: `Bearer ${token}` }),
    ...options.headers,
  };

  const response = await fetch(`${API_URL}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    throw new Error(await response.text());
  }

  return response.json();
}

export async function login(email, password) {
  const formData = new URLSearchParams();
  formData.append("username", email);
  formData.append("password", password);

  const response = await fetch(`${API_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: formData,
  });

  if (!response.ok) {
    throw new Error("Invalid credentials");
  }

  return response.json();
}

export async function register(email, password) {

  const response = await fetch(`${API_URL}/auth/register`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      email: email,
      password: password,
    }),
  });

  if (!response.ok) {
    const err = await response.json();
    throw new Error(err.detail || "Registration failed");
  }

  return await response.json();
}


export async function getCurrentUser() {
  return apiFetch("/auth/me");
}

