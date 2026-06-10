import { API_URL } from "./api.js";

const token = new URLSearchParams(window.location.search).get("token");

if (!token) {
  document.getElementById("reset-error").textContent =
    "Invalid reset link. Please request a new one.";
  document.getElementById("reset-form").style.display = "none";
}

document.getElementById("reset-form").addEventListener("submit", async (e) => {
  e.preventDefault();

  const newPassword = document.getElementById("new_password").value;
  const confirmPassword = document.getElementById("confirm_password").value;

  document.getElementById("reset-error").textContent = "";
  document.getElementById("reset-success").textContent = "";

  if (newPassword !== confirmPassword) {
    document.getElementById("reset-error").textContent = "Passwords do not match.";
    return;
  }

  try {
    const res = await fetch(`${API_URL}/auth/reset-password`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token, new_password: newPassword }),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Reset failed.");
    }

    document.getElementById("reset-success").textContent =
      "✅ Password updated! Redirecting to login…";
    document.getElementById("reset-form").style.display = "none";

    setTimeout(() => {
      window.location.href = "index.html";
    }, 2000);

  } catch (err) {
    document.getElementById("reset-error").textContent = `❌ ${err.message}`;
  }
});
