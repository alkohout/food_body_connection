import { login } from "./api.js";

document.getElementById("login-form").addEventListener("submit", async (e) => {
  e.preventDefault();

  const email = document.getElementById("email").value;
  const password = document.getElementById("password").value;

  // Clear previous messages
  document.getElementById("error").textContent = "";
  document.getElementById("success").textContent = "";

  try {
    const data = await login(email, password);

    // STORE TOKEN
    localStorage.setItem("access_token", data.access_token);

    document.getElementById("success").textContent =
      "✅ Successfully logged in! Redirecting…";

    setTimeout(() => {
      window.location.href = "dashboard.html";
    }, 800);

  } catch (err) {
    document.getElementById("error").textContent =
      "❌ Login failed. Please check your details.";
  }
});
