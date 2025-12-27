import { getCurrentUser } from "./api.js";

async function init() {
  if (!localStorage.getItem("access_token")) {
    window.location.href = "index.html";
    return;
  }

  try {
    const user = await getCurrentUser();
    document.getElementById("user-email").textContent = user.email;
  } catch {
    localStorage.removeItem("access_token");
    window.location.href = "index.html";
  }
}

document.getElementById("log-form").addEventListener("submit", async (e) => {
  e.preventDefault(); // stops page reload

  const token = localStorage.getItem("access_token");

  const payload = {
    allergen_id: parseInt(document.getElementById("allergen-item").value),
    date_time: document.getElementById("entry-date").value
  };

  const res = await fetch(`${API_URL}/entries`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`
    },
    body: JSON.stringify(payload)
  });

  if (!res.ok) {
    document.getElementById("log-error").textContent = "Failed to log entry";
    return;
  }

  document.getElementById("log-success").textContent = "Entry logged!";
});


init();
