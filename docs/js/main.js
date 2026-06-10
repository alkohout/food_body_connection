// docs/js/main.js

// Import API helper functions for authentication
import { login, register } from "./api.js";
import { API_URL } from "./api.js";

// =========================================================
// Login Form Handler
// =========================================================

// Listen for login form submission
document.getElementById("login-form").addEventListener("submit", async (e) => {
  e.preventDefault(); // Prevent default form submission (page reload)

  // Get user input values
  const email = document.getElementById("login_email").value;
  const password = document.getElementById("login_password").value;

  // Clear previous success/error messages
  document.getElementById("login-error").textContent = "";
  document.getElementById("login-success").textContent = "";

  try {
    // Call login API
    const data = await login(email, password);

    // Store returned JWT access token in localStorage
    localStorage.setItem("access_token", data.access_token);

    // Show success message to user
    document.getElementById("login-success").textContent =
      "✅ Successfully logged in! Redirecting…";

    // Redirect to dashboard after short delay
    setTimeout(() => {
      window.location.href = "dashboard.html";
    }, 800);

  } catch (err) {
    // Display generic error message if login fails
    document.getElementById("login-error").textContent =
      "❌ Login failed. Please check your details.";
  }
});

// =========================================================
// Forgot Password Toggle
// =========================================================

document.getElementById("forgot-password-link").addEventListener("click", (e) => {
  e.preventDefault();
  document.getElementById("login-form").style.display = "none";
  document.getElementById("forgot-form").style.display = "block";
});

document.getElementById("back-to-login-link").addEventListener("click", (e) => {
  e.preventDefault();
  document.getElementById("forgot-form").style.display = "none";
  document.getElementById("login-form").style.display = "block";
});

document.getElementById("forgot-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const email = document.getElementById("forgot_email").value;

  document.getElementById("login-error").textContent = "";
  document.getElementById("login-success").textContent = "";

  try {
    const res = await fetch(`${API_URL}/auth/forgot-password`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    });

    const data = await res.json();
    document.getElementById("login-success").textContent = `✅ ${data.message}`;
    document.getElementById("forgot-form").style.display = "none";
    document.getElementById("login-form").style.display = "block";
  } catch {
    document.getElementById("login-error").textContent =
      "❌ Something went wrong. Please try again.";
  }
});

// =========================================================
// Registration Form Handler
// =========================================================

// Listen for registration form submission
document.getElementById("register-form").addEventListener("submit", async (e) => {
  e.preventDefault(); // Prevent default form submission

  // Get user input values
  const email = document.getElementById("registration_email").value;
  const password = document.getElementById("registration_password").value;

  // Clear previous success/error messages
  document.getElementById("registration-error").textContent = "";
  document.getElementById("registration-success").textContent = "";

  try {
    // Call register API to create new user
    const data = await register(email, password);

    // Show success message
    document.getElementById("registration-success").textContent =
      "✅ Registered! Please log in.";

    // Redirect back to login page after short delay
    setTimeout(() => {
      window.location.href = "index.html";
    }, 1000);

  } catch (err) {
    // Display generic error message if registration fails
    document.getElementById("registration-error").textContent =
      "❌ Registration failed. Please check your details.";
  }
});