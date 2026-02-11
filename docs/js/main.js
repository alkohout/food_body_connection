// docs/js/main.js

// Import API helper functions for authentication
import { login } from "./api.js";
import { register } from "./api.js";

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