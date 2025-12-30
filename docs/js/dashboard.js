// docs/js/dashboard.js

import { getCurrentUser, API_URL } from "./api.js";

const allergenInput = document.getElementById("allergen-input");
const allergenIdInput = document.getElementById("allergen-id");
const suggestions = document.getElementById("allergen-suggestions");
const localInput = document.getElementById("allergen-date").value;
const unitSelect = document.getElementById("allergen-unit");
const allergenId = allergenIdInput.value;
const quantity = document.getElementById("allergen-quantity").value;
const unitId = unitSelect.value;
// Example: "2025-01-01T08:30" (no seconds, no timezone)

// Split into parts
const [date, time] = localInput.split("T");
const [year, month, day] = date.split("-").map(Number);
const [hour, minute] = time.split(":").map(Number);

// JS months are 0-indexed
const localDate = new Date(year, month - 1, day, hour, minute);

// Convert to UTC ISO string
const utcISOString = localDate.toISOString();

// Fetch units from backend
async function fetchUnits() {
  try {
    const res = await fetch(`${API_URL}/units`, {
      headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` }
    });

    if (!res.ok) throw new Error(`Failed to fetch units: ${res.status}`);

    const data = await res.json();

    if (!Array.isArray(data)) {
      console.error("Units data is not an array:", data);
      return;
    }

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
  const dateTime = utcISOString;
  const quantity = document.getElementById("allergen-quantity").value;
  const unitId = unitSelect.value;

  if (!allergenId) {
    document.getElementById("log-error").textContent =
      "Please select an allergen from the list.";
    return;
  }

  try {
    const res = await fetch(`${API_URL}/entries/allergens`, {
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
});

init();
