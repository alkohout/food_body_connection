import { login } from "./api.js";
import { register } from "./api.js";

document.getElementById("login-form").addEventListener("submit", async (e) => {
  e.preventDefault();

  const email = document.getElementById("login_email").value;
  const password = document.getElementById("login_password").value;

  // Clear previous messages
  document.getElementById("loginerror").textContent = "";
  document.getElementById("loginsuccess").textContent = "";

  try {
    const data = await login(login_email, login_password);

    // STORE TOKEN
    localStorage.setItem("access_token", data.access_token);

    document.getElementById("login-success").textContent =
      "✅ Successfully logged in! Redirecting…";

    setTimeout(() => {
      window.location.href = "dashboard.html";
    }, 800);

  } catch (err) {
    document.getElementById("login-error").textContent =
      "❌ Login failed. Please check your details.";
  }
});

document.getElementById("registration-form").addEventListener("submit", async (e) => {
  e.preventDefault();

  const email = document.getElementById("registration_email").value;
  const password = document.getElementById("registration_password").value;

  // Clear previous messages
  document.getElementById("registration-error").textContent = "";
  document.getElementById("registration-success").textContent = "";

  try {
    const data = await register(registration_email, registration_password);

    // STORE TOKEN
    localStorage.setItem("access_token", data.access_token);

    document.getElementById("registration-success").textContent =
  "✅ Registered! Please log in.";

    setTimeout(() => {
      window.location.href = "index.html";
    }, 1000);

  } catch (err) {
    document.getElementById("registration-error").textContent =
      "❌ Registration failed. Please check your details.";
  }
});
