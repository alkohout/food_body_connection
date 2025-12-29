// docs/js/dashboard.js

import { getCurrentUser, API_URL } from "./api.js";

const allergenInput = document.getElementById("allergen-input");
const allergenIdInput = document.getElementById("allergen-id");
const suggestions = document.getElementById("allergen-suggestions");
const dateInput = document.getElementById("allergen-date");
const unitSelect = document.getElementById("allergen-unit");

// Fetch units from backend
async function fetchUnits() {
  try {
    const res = await fetch(`${API_URL}/unit`, {
      headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` }
    });
    const data = await res.json();
    data.forEach(u => {
      const opt = document.createElement("option");
      opt.value = u.unit_id;
      opt.textContent = u.unit_name;
      unitSelect.appendChild(opt);
    });
  } catch (err) {
    console.error("Failed to fetch units:", err);
  }
}

// Call on page load
fetchUnits();

// Set default to current date/time
const now = new Date();
dateInput.value = now.toISOString().slice(0,16); // "YYYY-MM-DDTHH:mm"

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
  const dateTime = dateInput.value; // "YYYY-MM-DDTHH:mm"

  if (!allergenId) {
    document.getElementById("log-error").textContent =
      "Please select an allergen from the list.";
    return;
  }

  try {
    const res = await fetch(`${API_URL}/entries/allergen?allergen_id=${allergenId}`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${localStorage.getItem("access_token")}`,
      },
      body: JSON.stringify({
        allergen_id: allergenId,
        date_time: dateTime
      }),
    });

    if (res.ok) {
      document.getElementById("log-success").textContent = "Allergen logged!";
      document.getElementById("log-error").textContent = "";
      allergenInput.value = "";
      allergenIdInput.value = "";
      suggestions.innerHTML = "";
      dateInput.value = now.toISOString().slice(0,16)
    } else {
      const err = await res.text();
      document.getElementById("log-error").textContent = `Failed to log allergen: ${err}`;
    }
  } catch (error) {
    document.getElementById("log-error").textContent = `Error: ${error.message}`;
  }

});

const allergenId = allergenIdInput.value;
const dateTime = dateInput.value;
const quantity = document.getElementById("allergen-quantity").value;
const unitId = unitSelect.value;

if (!allergenId) {
  document.getElementById("log-error").textContent =
    "Please select an allergen from the list.";
  return;
}

try {
  const res = await fetch(`${API_URL}/entries/allergen`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${localStorage.getItem("access_token")}`,
    },
    body: JSON.stringify({
      allergen_id: parseInt(allergenId),
      date_time: dateTime,
      quantity: quantity ? parseFloat(quantity) : null,
      unit_id: unitId ? parseInt(unitId) : null
    }),
  });

  if (res.ok) {
    document.getElementById("log-success").textContent = "Allergen logged!";
    document.getElementById("log-error").textContent = "";
    allergenInput.value = "";
    allergenIdInput.value = "";
    suggestions.innerHTML = "";
    dateInput.value = new Date().toISOString().slice(0,16);
    document.getElementById("allergen-quantity").value = "";
    unitSelect.value = "";
  } else {
    const err = await res.text();
    document.getElementById("log-error").textContent = `Failed to log allergen: ${err}`;
  }
} catch (error) {
  document.getElementById("log-error").textContent = `Error: ${error.message}`;
}

init();
