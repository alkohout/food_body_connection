// docs/js/dashboard.js

import { getCurrentUser, API_URL } from "./api.js";

// Allergen logging elements
const allergenInput = document.getElementById("allergen-input");
const allergenIdInput = document.getElementById("allergen-id");
const suggestions = document.getElementById("allergen-suggestions");
const unitSelect = document.getElementById("allergen-unit");

function localDateTimeForInput(date = new Date()) {
  const tzOffsetMs = date.getTimezoneOffset() * 60000;
  return new Date(date.getTime() - tzOffsetMs)
    .toISOString()
    .slice(0, 16);
}
const dateInput = document.getElementById("allergen-date");
dateInput.value = localDateTimeForInput();


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

  if (allergenIdInput) {
    allergenIdInput.value = "";
  }
  if (suggestions) {
    suggestions.innerHTML = "";
  }

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

const logForm = document.getElementById("log-form");

if (logForm) {
  logForm.addEventListener("submit", async (e) => {
    e.preventDefault();

    const allergenId = allergenIdInput.value;
    const localInput = dateInput.value; // we already have dateInput above

    if (!allergenId) {
      document.getElementById("log-error").textContent =
        "Please select an allergen from the list.";
      return;
    }

    if (!localInput) {
      document.getElementById("log-error").textContent =
        "Please select a date and time.";
      return;
    }

    const dateTime = new Date(localInput).toISOString();
    const quantity = document.getElementById("allergen-quantity").value;
    const unitId = unitSelect.value;

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
          unit_id: unitId ? parseInt(unitId) : null,
        }),
      });

      if (res.ok) {
        document.getElementById("log-success").textContent = "Allergen logged!";
        document.getElementById("log-error").textContent = "";
        allergenInput.value = "";
        allergenIdInput.value = "";
        suggestions.innerHTML = "";
        dateInput.value = localDateTimeForInput();
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
}
// Symptom logging elements
const symptomInput = document.getElementById("symptom-input");
const symptomIdInput = document.getElementById("symptom-id");
const symptomSuggestions = document.getElementById("symptom-suggestions");
const symptomDateInput = document.getElementById("symptom-date");
symptomDateInput.value = localDateTimeForInput();

let debounceTimer2;

symptomInput.addEventListener("input", () => {
  const query = symptomInput.value.trim();

  if (symptomIdInput) {
    symptomIdInput.value = "";
  }
  if (symptomSuggestions) {
    symptomSuggestions.innerHTML = "";
  }

  if (query.length < 1) return;

  clearTimeout(debounceTimer2);
  debounceTimer2 = setTimeout(() => fetchSymptoms(query), 300);
});

async function fetchSymptoms(query) {

  const res = await fetch(`${API_URL}/symptoms?q=${encodeURIComponent(query)}`, {
  headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` }
  });

  const data = await res.json();
  symptomSuggestions.innerHTML = "";

  data.forEach(a => {
    const li = document.createElement("li");
    li.textContent = a.symptom_name;
    li.addEventListener("click", () => {
      symptomInput.value = a.symptom_name;
      symptomIdInput.value = a.symptom_id;
      symptomSuggestions.innerHTML = "";
    });
    symptomSuggestions.appendChild(li);
  });
}

const logForm2 = document.getElementById("log-form");

if (logForm2) {
  logForm2.addEventListener("submit", async (e) => {
    e.preventDefault();

    const symptomId = symptomIdInput.value;
    const localInput = symptomDateInput.value; 

    if (!symptomId) {
      document.getElementById("log-error").textContent =
        "Please select a symptom from the list.";
      return;
    }

    if (!localInput) {
      document.getElementById("log-error").textContent =
        "Please select a date and time.";
      return;
    }

    const symptomDateTime = new Date(localInput).toISOString();
    const intensity = document.getElementById("symptom-intensity").value;

    try {
      const res = await fetch(`${API_URL}/entries/symptoms`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("access_token")}`,
        },

        body: JSON.stringify({
          allergen_id: parseInt(allergenId),
          date_time: symptomDateTime,
          intensity: intensity !== "" ? parseInt(intensity) : null
        })

      });

      if (res.ok) {
        document.getElementById("log-success").textContent = "Symptom logged!";
        document.getElementById("log-error").textContent = "";
        symptomInput.value = "";
        symptomIdInput.value = "";
        symptomSuggestions.innerHTML = "";
        symptomDateInput.value = localDateTimeForInput();
        document.getElementById("symptom-intensity").value = "";
      } else {
        const err = await res.text();
        document.getElementById("log-error").textContent = `Failed to log symptom: ${err}`;
      }
    } catch (error) {
      document.getElementById("log-error").textContent = `Error: ${error.message}`;
    }
  });
}

init();
