// docs/js/dashboard.js

import { getCurrentUser, API_URL } from "./api.js";

// -----------------------------------------------------------------------
// -----------------------------------------------------------------------
// INITIALIZATION
// -----------------------------------------------------------------------
// -----------------------------------------------------------------------

const logoutBtn = document.getElementById("logout-btn");
if (logoutBtn) {
  logoutBtn.addEventListener("click", () => {
    localStorage.removeItem("access_token");
    window.location.href = "index.html";
  });
}

// Set date input to local datetime format
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

fetchUnits();

// Initialize dashboard
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

// Select tabs
const tabs = document.querySelectorAll(".tab");
const forms = document.querySelectorAll(".form");

tabs.forEach(tab => {
  tab.addEventListener("click", () => {
    const target = tab.dataset.tab;

    // Switch active tab
    tabs.forEach(t => t.classList.remove("active"));
    tab.classList.add("active");

    // Switch active form
    forms.forEach(f => f.classList.remove("active"));
    const activeForm = document.getElementById(`${target}-form`);
    activeForm.classList.add("active");

    // If Analysis tab, fetch plot immediately
    if (target === "analysis") {
      fetchAnalysisPlot(); // function to get the plot
    }
  });
});

// -----------------------------------------------------------------------
// -----------------------------------------------------------------------
// ALLERGEN LOGGIN
// -----------------------------------------------------------------------
// -----------------------------------------------------------------------

// Allergen logging elements
const allergenInput = document.getElementById("allergen-input");
const allergenIdInput = document.getElementById("allergen-id");
const suggestions = document.getElementById("allergen-suggestions");
const unitSelect = document.getElementById("allergen-unit");

// Allergen autocomplete
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

// Fetch allergen suggestions
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

// Handle allergen log form submission
const logForm = document.getElementById("allergen-form");

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

// -----------------------------------------------------------------------
// -----------------------------------------------------------------------
// SYMPTOM LOGGIN
// -----------------------------------------------------------------------
// -----------------------------------------------------------------------

// Symptom logging elements
const symptomInput = document.getElementById("symptom-input");
const symptomIdInput = document.getElementById("symptom-id");
const symptomSuggestions = document.getElementById("symptom-suggestions");
const symptomDateInput = document.getElementById("symptom-date");
symptomDateInput.value = localDateTimeForInput();

// Symptom autocomplete
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

// Fetch symptom suggestions
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

// Handle symptom log form submission
const logForm2 = document.getElementById("symptom-form");

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
      document.getElementById("symptom-error").textContent =
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
          symptom_id: parseInt(symptomId),
          date_time: symptomDateTime,
          intensity: intensity !== "" ? parseInt(intensity) : null
        })

      });

      if (res.ok) {
        document.getElementById("symptom-success").textContent = "Symptom logged!";
        document.getElementById("symptom-error").textContent = "";
        symptomInput.value = "";
        symptomIdInput.value = "";
        symptomSuggestions.innerHTML = "";
        symptomDateInput.value = localDateTimeForInput();
        document.getElementById("symptom-intensity").value = "";
      } else {
        const err = await res.text();
        document.getElementById("symptom-error").textContent = `Failed to log symptom: ${err}`;
      }
    } catch (error) {
      document.getElementById("symptom-error").textContent = `Error: ${error.message}`;
    }
  });

}

// -----------------------------------------------------------------------
// -----------------------------------------------------------------------
// ANALYSIS DASHBOARD
// -----------------------------------------------------------------------
// -----------------------------------------------------------------------

const symptomPlotInput = document.getElementById("symptom-plot-input");
const allergenPlotInput = document.getElementById("allergen-plot-input");
const allergenPlotIdInput = document.getElementById("allergen-plot-id");
const symptomPlotIdInput = document.getElementById("symptom-plot-id");
const allergenPlotSuggestions = document.getElementById("allergen-plot-suggestions");
const symptomPlotSuggestions = document.getElementById("symptom-plot-suggestions");

let debouncePlotTimer;

allergenPlotInput.addEventListener("input", () => {
  const query = allergenPlotInput.value.trim();
  allergenPlotIdInput.value = "";
  allergenPlotSuggestions.innerHTML = "";

  if (query.length < 1) return;

  clearTimeout(debouncePlotTimer);
  debouncePlotTimer = setTimeout(
    () => fetchAllergensForPlot(query),
    300
  );
});

symptomPlotInput.addEventListener("input", () => {
  const query = symptomPlotInput.value.trim();
  symptomPlotIdInput.value = "";
  symptomPlotSuggestions.innerHTML = "";

  if (query.length < 1) return;

  clearTimeout(debouncePlotTimer);
  debouncePlotTimer = setTimeout(
    () => fetchSymptomsForPlot(query),
    300
  );
});

async function fetchAllergensForPlot(query) {
  const res = await fetch(`${API_URL}/allergens?q=${encodeURIComponent(query)}`, {
    headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` }
  });

  const data = await res.json();
  allergenPlotSuggestions.innerHTML = "";

  data.forEach(a => {
    const li = document.createElement("li");
    li.textContent = a.allergen_name;
    li.addEventListener("click", () => {
      allergenPlotInput.value = a.allergen_name;
      allergenPlotIdInput.value = a.allergen_id;
      allergenPlotSuggestions.innerHTML = "";
    });
    allergenPlotSuggestions.appendChild(li);
  });
}

async function fetchSymptomsForPlot(query) {
  const res = await fetch(`${API_URL}/symptoms?q=${encodeURIComponent(query)}`, {
    headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` }
  });

  const data = await res.json();
  symptomPlotSuggestions.innerHTML = "";

  data.forEach(s => {
    const li = document.createElement("li");
    li.textContent = s.symptom_name;
    li.addEventListener("click", () => {
      symptomPlotInput.value = s.symptom_name;
      symptomPlotIdInput.value = s.symptom_id;
      symptomPlotSuggestions.innerHTML = "";
    });
    symptomPlotSuggestions.appendChild(li);
  });
}

async function fetchAnalysisPlot() {
    const img = document.getElementById("analysis-plot");
    
    try {

        // --------------------
        // Fetch stats
        // --------------------
        const response_stat = await fetch(`${API_URL}/analysis/stats`, {
          headers: {
            Authorization: `Bearer ${localStorage.getItem("access_token")}`
          }
        });

        if (!response_stat.ok) {
          console.error("Failed to fetch stats:", response_stat.statusText);
          return;
        }

        const stats = await response_stat.json();

        // Populate stats cards
        const totalEntries =
          stats["Total allergens logged"] + stats["Total symptoms logged"];

        document.getElementById("stat-total-entries").textContent =
          totalEntries;

        document.getElementById("stat-days").textContent =
          stats["Total days tracked"];

        const response_plot = await fetch(`${API_URL}/analysis/plot-eda`, {
            headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` }
        });

        if (!response_plot.ok) {
            console.error("Failed to fetch plot:", response_plot.statusText);
            return;
        }

        const blob = await response_plot.blob();
        img.src = URL.createObjectURL(blob);

    } catch (err) {
        console.error("Error fetching default analysis:", err);
    }
}

document.getElementById("update-plot-btn").addEventListener("click", async () => {
    const img = document.getElementById("analysis-plot");
    
    try {
        const symptom = symptomPlotInput.value || "Nausea";
        const allergen = allergenPlotInput.value || "Dairy";
        const start_date = dateInput.value ? dateInput.value.split("T")[0] : "2025-01-01";

        const response = await fetch(`${API_URL}/analysis/plot-eda?allergen=${allergen}&symptom=${symptom}&start_date=${start_date}`, {
            headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` }
        });

        if (!response.ok) {
            console.error("Failed to fetch plot:", response.statusText);
            return;
        }

        const blob = await response.blob();
        img.src = URL.createObjectURL(blob);

    } catch (err) {
        console.error("Error fetching plot:", err);
    }
});

document.addEventListener("DOMContentLoaded", async () => {
  await init();
  // set up updatePlot, event listeners here
});
