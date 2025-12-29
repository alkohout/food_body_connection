// docs/js/dashboard.js

import { getCurrentUser, API_URL } from "./api.js";

const allergenInput = document.getElementById("allergen-input");
const allergenIdInput = document.getElementById("allergen-id");
const suggestions = document.getElementById("allergen-suggestions");

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

let debounceTimer;

allergenInput.addEventListener("input", () => {
  const query = allergenInput.value.trim();

  allergenIdInput.value = "";
  suggestions.innerHTML = "";

  if (query.length < 1) return;

  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => fetchAllergens(query), 300);
});

async function fetchAllergens(query) {

  const res = await fetch(`${API_URL}/allergens?q=${encodeURIComponent(query)}`, {
  headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` }
  });

  const data = await res.json();
  suggestions.innerHTML = "";

  data.forEach(a => {
    const li = document.createElement("li");
    li.textContent = a.allergen_name;
    li.addEventListener("click", () => {
      allergenInput.value = a.allergen_name;
      allergenIdInput.value = a.allergen_id;
      suggestions.innerHTML = "";
    });
    suggestions.appendChild(li);
  });
}

document.getElementById("log-form").addEventListener("submit", async (e) => {
  e.preventDefault();

  const allergenId = allergenIdInput.value;
  if (!allergenId) {
    document.getElementById("log-error").textContent =
      "Please select an allergen from the list.";
    return;
  }

  const res = await fetch(`${API_URL}/entries/allergen?allergen_id=${allergenId}`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${localStorage.getItem("access_token")}`,
    },
  });

  if (res.ok) {
    document.getElementById("log-success").textContent = "Allergen logged!";
    document.getElementById("log-error").textContent = "";
    allergenInput.value = "";
    allergenIdInput.value = "";
  } else {
    document.getElementById("log-error").textContent = "Failed to log allergen.";
  }
});



init();
