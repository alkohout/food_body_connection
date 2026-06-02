import { getCurrentUser, API_URL } from "./api.js";

console.log("Dashboard module loading...");

// =========================================================
// Helpers
// =========================================================

const debounce = (fn, delay = 300) => {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
};

const localDateTimeForInput = (date = new Date()) => {
  const tzOffsetMs = date.getTimezoneOffset() * 60000;
  return new Date(date.getTime() - tzOffsetMs).toISOString().slice(0, 16);
};

function positionRangeLabels(sliderId, labelsId) {
  const slider = document.getElementById(sliderId);
  const labelsContainer = document.getElementById(labelsId);

  if (!slider || !labelsContainer) return;

  const min = Number(slider.min);
  const max = Number(slider.max);
  const labels = labelsContainer.querySelectorAll("span");

  labels.forEach(label => {
    const value = Number(label.dataset.value);
    const percent = (value - min) / (max - min);
    label.style.left = `${percent * 100}%`;
  });
}

function isTokenExpired(token) {
  try {
    if (!token) return true;
    const payload = JSON.parse(atob(token.split(".")[1]));
    return Date.now() >= payload.exp * 1000;
  } catch (err) {
    console.warn("Failed to parse token:", err);
    return true;
  }
}

// =========================================================
// Elements (re-query inside functions for safety)
// =========================================================

// Don't cache element references at module load time
const getElement = (id) => {
  const el = document.getElementById(id);
  if (!el) {
    console.warn(`Element with id "${id}" not found`);
  }
  return el;
};

// =========================================================
// Initialization
// =========================================================

document.addEventListener("DOMContentLoaded", async () => {
  console.log("DOMContentLoaded fired");
  await init();
});

// =========================================================
// Logout
// =========================================================

function setupLogout() {
  const logoutBtn = getElement("logout-btn");
  if (!logoutBtn) return;

  logoutBtn.addEventListener("click", () => {
    localStorage.removeItem("access_token");
    window.location.href = "index.html";
  });
}

// =========================================================
// Defaults
// =========================================================

function setupDefaults() {
  const dateInput = getElement("allergen-date");
  const symptomDateInput = getElement("symptom-date");

  if (dateInput) dateInput.value = localDateTimeForInput();
  if (symptomDateInput) symptomDateInput.value = localDateTimeForInput();
}

// =========================================================
// Fetch units
// =========================================================

const fetchUnits = async () => {
  const unitSelect = getElement("allergen-unit");
  if (!unitSelect) return;

  try {
    console.log("Fetching units from:", `${API_URL}/units`);
    const res = await fetch(`${API_URL}/units`, {
      headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` }
    });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);

    const units = await res.json();
    console.log(`Loaded ${units.length} units`);
    
    units.forEach(u => {
      const opt = document.createElement("option");
      opt.value = u.unit_id;
      opt.textContent = u.unit_name;
      unitSelect.appendChild(opt);
    });

    return units;
  } catch (err) {
    console.error("Failed to fetch units:", err);
    return [];
  }
}

// =========================================================
// Fetch allergens 
// =========================================================


const fetchAllergens = async () => {
  const url = `${API_URL}/allergens`;
  const token = localStorage.getItem("access_token");

  const res = await fetch(url, {
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/json",
    },
  });

  if (!res.ok) {
    throw new Error(`Failed to fetch allergens (${res.status})`);
  }

  const allergens = await res.json();

  if (!Array.isArray(allergens)) {
    throw new Error("Invalid allergens response");
  }

  console.log("✅ Loaded all allergens:", allergens.length);
  return allergens;
};

const fetchRecentAllergens = async (limit = 5) => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      console.error("No access token found");
      return [];
    }

    const url = `${API_URL}/allergens/recent?limit=${limit}`;
    console.log("Fetching recent allergens from:", url);

    const res = await fetch(url, {
      headers: {
        "Authorization": `Bearer ${token}`,
        "Accept": "application/json",
      },
    });

    console.log("Recent allergens response status:", res.status, res.statusText);

    if (!res.ok) {
      const errorText = await res.text();
      throw new Error(`HTTP ${res.status}: ${res.statusText} - ${errorText}`);
    }

    const recentAllergens = await res.json();
    console.log("Recent allergens data:", recentAllergens);

    if (!Array.isArray(recentAllergens)) {
      console.error("Expected array but got:", typeof recentAllergens, recentAllergens);
      throw new Error("Invalid data format for /allergens/recent: expected array");
    }

    return recentAllergens;
};

// =========================================================
// Populate allergen <select> with recent + all
// =========================================================

const populateAllergenSelect = (allergens, recentAllergens) => {
  const allergenSelect = getElement("allergen-select");
  if (!allergenSelect) return;

  allergenSelect.innerHTML = "";

  // Placeholder
  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = "Select an allergen…";
  allergenSelect.appendChild(placeholder);

  const usedIds = new Set();

  // ---- Recent allergens ----
  if (Array.isArray(recentAllergens) && recentAllergens.length > 0) {
    const recentGroup = document.createElement("optgroup");
    recentGroup.label = "Recent allergens";

    recentAllergens.forEach(a => {
      if (!a.allergen_id || !a.allergen_name) return;
      usedIds.add(a.allergen_id);

      const opt = document.createElement("option");
      opt.value = a.allergen_id;
      opt.textContent = a.allergen_name;
      recentGroup.appendChild(opt);
    });

    if (recentGroup.children.length > 0) {
      allergenSelect.appendChild(recentGroup);
    }
  }

  // Divider
  if (Array.isArray(allergens) && allergens.length > 0) {
    const divider = document.createElement("option");
    divider.disabled = true;
    divider.textContent = "──────────────";
    allergenSelect.appendChild(divider);
  }

  // ---- All allergens ----
  if (Array.isArray(allergens) && allergens.length > 0) {
    const allGroup = document.createElement("optgroup");
    allGroup.label = "All allergens";

    allergens.forEach(a => {
      if (!a.allergen_id || !a.allergen_name) return;
      if (usedIds.has(a.allergen_id)) return;

      const opt = document.createElement("option");
      opt.value = a.allergen_id;
      opt.textContent = a.allergen_name;
      allGroup.appendChild(opt);
    });

    if (allGroup.children.length > 0) {
      allergenSelect.appendChild(allGroup);
    }
  }
};


async function addNewAllergen(name) {
  const token = localStorage.getItem("access_token");
  if (!token) return;

  try {
    const res = await fetch(`${API_URL}/allergens`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${token}`
      },
      body: JSON.stringify({ allergen_name: name })
    });

    if (!res.ok) throw new Error(await res.text());

    const data = await res.json();
    console.log("Created allergen:", data);

    // ✅ FULL refresh, correctly
    const allergens = await fetchAllergens();
    const recentAllergens = await fetchRecentAllergens(5);
    populateAllergenSelect(allergens, recentAllergens);

    const select = getElement("allergen-select");
    if (select) select.value = data.allergen_id;

    return data;
  } catch (err) {
    console.error("Failed to create allergen:", err);
    alert("Error adding allergen: " + err.message);
  }
}

function setupAddAllergen() {
  const addBtn = getElement("add-allergen-btn");
  const nameInput = getElement("new-allergen-name");
  const select = getElement("allergen-select");
  const idInput = getElement("allergen-id");

  if (!addBtn || !nameInput) return;

  addBtn.addEventListener("click", async () => {
    const name = nameInput.value.trim();
    if (!name) return alert("Enter an allergen name");

    const created = await addNewAllergen(name);
    if (!created) return;

    // Select newly created allergen
    select.value = created.allergen_id;
    idInput.value = created.allergen_id;

    // Clear input
    nameInput.value = "";
  });
};

// =========================================================
// Fetch symtpoms 
// =========================================================

const fetchSymptoms = async () => {
  const url = `${API_URL}/symptoms`;
  const token = localStorage.getItem("access_token");

  const res = await fetch(url, {
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/json",
    },
  });

  if (!res.ok) {
    throw new Error(`Failed to fetch symptoms (${res.status})`);
  }

  const symptoms = await res.json();
  if (!Array.isArray(symptoms)) {
    throw new Error("Invalid symptoms response");
  }

  console.log("✅ Loaded all symptoms:", symptoms.length);
  return symptoms;
};

const fetchRecentSymptoms = async (limit = 5) => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      console.error("No access token found");
      return [];
    }

    const url = `${API_URL}/symptoms/recent?limit=${limit}`;
    console.log("Fetching recent symptoms from:", url);

    const res = await fetch(url, {
      headers: {
        "Authorization": `Bearer ${token}`,
        "Accept": "application/json",
      },
    });

    console.log("Recent symptoms response status:", res.status, res.statusText);
    if (!res.ok) {
      const errorText = await res.text();
      throw new Error(`HTTP ${res.status}: ${res.statusText} - ${errorText}`);
    }

    const recentSymptoms = await res.json();
    console.log("Recent symptoms data:", recentSymptoms);

    if (!Array.isArray(recentSymptoms)) {
      console.error("Expected array but got:", typeof recentSymptoms, recentSymptoms);
      throw new Error("Invalid data format for /symptoms/recent: expected array");
    }

    return recentSymptoms;
};

// =========================================================
// Populate symptom <select> with recent + all
// =========================================================

const populateSymptomSelect = (symptoms, recentSymptoms) => {
  const symptomSelect = getElement("symptom-select");
  if (!symptomSelect) return;

  symptomSelect.innerHTML = "";

  // Placeholder
  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = "Select a symptom…";
  symptomSelect.appendChild(placeholder);

  const usedIds = new Set();

  // ---- Recent symptoms ----
  if (Array.isArray(recentSymptoms) && recentSymptoms.length > 0) {
    const recentGroup = document.createElement("optgroup");
    recentGroup.label = "Recent symptoms";

    recentSymptoms.forEach(a => {
      if (!a.symptom_id || !a.symptom_name) return;
      usedIds.add(a.symptom_id);

      const opt = document.createElement("option");
      opt.value = a.symptom_id;
      opt.textContent = a.symptom_name;
      recentGroup.appendChild(opt);
    });

    if (recentGroup.children.length > 0) {
      symptomSelect.appendChild(recentGroup);
    }
  }

  // Divider
  if (Array.isArray(symptoms) && symptoms.length > 0) {
    const divider = document.createElement("option");
    divider.disabled = true;
    divider.textContent = "──────────────";
    symptomSelect.appendChild(divider);
  }

  // ---- All symptoms ----
  if (Array.isArray(symptoms) && symptoms.length > 0) {
    const allGroup = document.createElement("optgroup");
    allGroup.label = "All symptoms";

    symptoms.forEach(a => {
      if (!a.symptom_id || !a.symptom_name) return;
      if (usedIds.has(a.symptom_id)) return;

      const opt = document.createElement("option");
      opt.value = a.symptom_id;
      opt.textContent = a.symptom_name;
      allGroup.appendChild(opt);
    });

    if (allGroup.children.length > 0) {
      symptomSelect.appendChild(allGroup);
    }
  }
};

async function addNewSymptom(name) {
  const token = localStorage.getItem("access_token");
  if (!token) return;

  try {
    const res = await fetch(`${API_URL}/symptoms`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${token}`
      },
      body: JSON.stringify({ symptom_name: name })
    });

    if (!res.ok) {
      const txt = await res.text();
      throw new Error(txt);
    }

    const data = await res.json();
    console.log("Created symptom:", data);

    // ✅ FULL refresh (same pattern as allergens)
    const symptoms = await fetchSymptoms();
    const recentSymptoms = await fetchRecentSymptoms(5);
    populateSymptomSelect(symptoms, recentSymptoms);

    // AUTO‑SELECT the newly added symptom
    const select = getElement("symptom-select");
    if (select) {
      select.value = data.symptom_id;
    }

    // Fill the text input and ID hidden input
    const input = getElement("symptom-select");
    const idInput = getElement("symptom-id");
    if (input) input.value = data.symptom_name;
    if (idInput) idInput.value = data.symptom_id;

    return data;
  } catch (err) {
    console.error("Failed to create symptom:", err);
    alert("Error adding symptom: " + err.message);
  }
}

function setupAddSymptom() {
  const addBtn = getElement("add-symptom-btn");
  const nameInput = getElement("new-symptom-name");
  const select = getElement("symptom-select");
  const idInput = getElement("symptom-id");

  if (!addBtn || !nameInput) return;

  addBtn.addEventListener("click", async () => {
    const name = nameInput.value.trim();
    if (!name) return alert("Enter a symptom name");
    const created = await addNewSymptom(name);
    if (!created) return;

    // Select newly created symptom
    select.value = created.symptom_id;
    idInput.value = created.symptom_id;

    // Clear input
    nameInput.value = "";
  });
}

// =========================================================
// Autocomplete
// =========================================================

const fetchSuggestions = async (query, type) => {
  if (!query) return [];

  let endpoint = 
    type === "allergen" ? "allergens" :
    type === "symptom_group" ? "symptom_groups" :
    type === "symptom" ? "symptoms" :
    "allergens";

  try {
    const res = await fetch(
      `${API_URL}/${endpoint}?q=${encodeURIComponent(query)}`,
      { headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` } }
    );

    if (!res.ok) return [];
    return await res.json();
  } catch (err) {
    console.error(`Failed to fetch suggestions for ${type}:`, err);
    return [];
  }
};

const setupAutocomplete = (inputEl, idEl, suggestionsEl, type) => {
  if (!inputEl || !suggestionsEl) {
    console.warn("Autocomplete missing required elements", { inputEl, suggestionsEl, type });
    return;
  }

  const handleInput = debounce(async () => {
    const query = inputEl.value.trim();

    if (idEl) idEl.value = "";

    suggestionsEl.innerHTML = "";
    suggestionsEl.classList.remove("visible");

    if (!query) return;

    const data = await fetchSuggestions(query, type);

    // Populate suggestions list
    data.forEach(item => {
      const li = document.createElement("li");
      li.textContent =
        type === "symptom" ? item.symptom_name :
        type === "symptom_group" ? item.symptom_group :
        item.allergen_name;

      li.addEventListener("click", () => {
        inputEl.value = li.textContent;

        if (idEl && type !== "symptom_group") {
          idEl.value =
            type === "symptom" ? item.symptom_id : item.allergen_id;
        }

        suggestionsEl.innerHTML = "";
        suggestionsEl.classList.remove("visible");
      });

      suggestionsEl.appendChild(li);
    });

    if (data.length > 0) {
      suggestionsEl.classList.add("visible");
    }

    if (type === "allergen") {
      const addBtnWrapper = getElement("add-allergen-wrapper");
      const addBtn = getElement("add-allergen-btn");

      if (data.length === 0 && query.length > 1) {
        addBtnWrapper.style.display = "block";
        addBtn.textContent = `Add "${query}" as a new allergen`;

        addBtn.onclick = async () => {
          const created = await addNewAllergen(query);
          if (created) {
            addBtnWrapper.style.display = "none";
          }
        };

        suggestionsEl.innerHTML = "";
        suggestionsEl.classList.remove("visible");
      } else {
        if (addBtnWrapper) {
            addBtnWrapper.style.display = "none";
        }
      }
    }

  }, 300);

  inputEl.addEventListener("input", handleInput);
};


// =========================================================
// Generic form submitter
// =========================================================

const submitForm = (formEl, endpoint, payloadFn, successEl, errorEl, resetFields = [], onSuccess = null) => {
  if (!formEl) {
    console.warn("Form element not found for", endpoint);
    return;
  }

  formEl.addEventListener("submit", async e => {
    e.preventDefault();

    try {
      const res = await fetch(`${API_URL}/${endpoint}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("access_token")}`
        },
        body: JSON.stringify(payloadFn())
      });

      if (!res.ok) {
        const text = await res.text();
        throw new Error(text);
      }

      if (successEl) successEl.textContent = "Logged successfully!";
      if (errorEl) errorEl.textContent = "";
      resetFields.forEach(f => {
        if (f) f.value = "";
      });
      if (onSuccess) await onSuccess();
    } catch (err) {
      if (errorEl) errorEl.textContent = `Error: ${err.message}`;
    }
  });
};

// =========================================================
// Forms
// =========================================================

function setupForms() {
  // Allergen form
  const allergenForm = getElement("allergen-form");
  const allergenIdInput = getElement("allergen-id");
  const allergenQuantityInput = getElement("allergen-quantity");
  const dateInput = getElement("allergen-date");
  const unitSelect = getElement("allergen-unit");

  submitForm(
    allergenForm,
    "entries/allergens",
    () => {
      const allergenId = Number(allergenIdInput?.value);
      if (!allergenId) {
        throw new Error("Please select an allergen");
      }

      return {
        allergen_id: allergenId,
        date_time: new Date(dateInput.value).toISOString(),
        quantity: Number(allergenQuantityInput.value) || null,
        unit_id: Number(unitSelect.value) || null
      };
    },
    getElement("log-success"),
    getElement("log-error"),
    [dateInput, allergenQuantityInput],
    loadAllergenLogs
  );

  // Symptom form
  const symptomForm = getElement("symptom-form");
  const symptomIdInput = getElement("symptom-id");
  const symptomDateInput = getElement("symptom-date");
  const symptomIntensityInput = getElement("symptom-intensity");

  submitForm(
    symptomForm,
    "entries/symptoms",
    () => ({
      symptom_id: Number(symptomIdInput?.value || 0),
      date_time: new Date(symptomDateInput?.value || Date.now()).toISOString(),
      intensity: Number(symptomIntensityInput?.value) || null
    }),
    getElement("symptom-success"),
    getElement("symptom-error"),
    [symptomIdInput, symptomDateInput],
    loadSymptomLogs
  );
}

// =========================================================
// Cached data (populated in init, used by log renderers)
// =========================================================

let cachedAllergens = [];
let cachedSymptoms = [];
let cachedUnits = [];

const INTENSITY_LABELS = ["None", "Mild", "Moderate", "Severe"];

// =========================================================
// Analysis state
// =========================================================

let analysisStatsLoaded = false;
let summaryLoaded = false;
let histogramLoaded = false;
let allergenRankLoaded = false;

let analysisStatsLoading = false;
let summaryLoading = false;
let histogramLoading = false;
let allergenRankLoading = false;

// =========================================================
// Analysis helpers
// =========================================================

function hideAllAnalysisPanels() {
  const panels = [
    getElement("analysis-placeholder"),
    getElement("panel-allergen-importance"),
    getElement("panel-symptom-grouping"),
    getElement("panel-deeper-analysis")
  ];

  panels.forEach(panel => {
    if (panel) panel.classList.remove("visible");
  });
}

async function showAnalysisPanel(selected) {
  hideAllAnalysisPanels();

  const placeholder = getElement("analysis-placeholder");
  const allergenPanel = getElement("panel-allergen-importance");
  const symptomPanel = getElement("panel-symptom-grouping");
  const deeperPanel = getElement("panel-deeper-analysis");

  if (!selected) {
    if (placeholder) placeholder.classList.add("visible");
    return;
  }

  if (selected === "allergen-importance") {
    if (allergenPanel) allergenPanel.classList.add("visible");
    await fetchAllergenRankPlot();
    return;
  }

  if (selected === "symptom-grouping") {
    if (symptomPanel) symptomPanel.classList.add("visible");
    await fetchHistogramPlot();
    return;
  }

  if (selected === "deeper-analysis") {
    if (deeperPanel) deeperPanel.classList.add("visible");
    return;
  }
}

function setupAnalysisDropdown() {
  const analysisSelect = getElement("analysis-select");
  if (!analysisSelect) return;

  analysisSelect.addEventListener("change", async (e) => {
    const selected = e.target.value;
    await showAnalysisPanel(selected);
  });
}

function setSummaryState(message) {
  const summaryDiv = getElement("summaryDiv");
  if (summaryDiv) summaryDiv.innerText = message;
}

function setButtonLoading(button, loadingText = "Loading...") {
  if (!button) return;
  button.disabled = true;
  button.dataset.originalText = button.textContent;
  button.textContent = loadingText;
}

function restoreButton(button, fallbackText = "Load") {
  if (!button) return;
  button.disabled = false;
  button.textContent = button.dataset.originalText || fallbackText;
}

function renderAnalysisStats(stats) {
  const totalAllergens = Number(stats["Total allergens logged"] || 0);
  const totalSymptoms = Number(stats["Total symptoms logged"] || 0);

  const totalAllergensEl = getElement("stat-total-allergens");
  if (totalAllergensEl) totalAllergensEl.textContent = totalAllergens;

  const totalSymptomsEl = getElement("stat-total-symptoms");
  if (totalSymptomsEl) totalSymptomsEl.textContent = totalSymptoms;

  const totalEntriesEl = getElement("stat-total-entries");
  if (totalEntriesEl) totalEntriesEl.textContent = totalAllergens + totalSymptoms;

  const daysEl = getElement("stat-days");
  if (daysEl) daysEl.textContent = stats["Total days tracked"] || 0;

  const avgAllergensPerDayEl = getElement("stat-avg-allergens-per-day");
  if (avgAllergensPerDayEl) {
    avgAllergensPerDayEl.textContent = stats["Average allergens logged per day"] || 0;
  }

  const avgSymptomsPerDayEl = getElement("stat-avg-symptoms-per-day");
  if (avgSymptomsPerDayEl) {
    avgSymptomsPerDayEl.textContent = stats["Average symptoms logged per day"] || 0;
  }

  const emptyState = getElement("analysis-empty-state");
  const pickerContainer = document.querySelector(".analysis-picker-container");
  const hasData = totalAllergens > 0 && totalSymptoms > 0;

  if (!hasData) {
    if (emptyState) emptyState.style.display = "block";
    if (pickerContainer) pickerContainer.style.display = "none";
    setSummaryState("No summary yet.");
  } else {
    if (emptyState) emptyState.style.display = "none";
    if (pickerContainer) pickerContainer.style.display = "block";
  }

  const extraStatsContainer = getElement("extra-stats");
  if (extraStatsContainer) {
    extraStatsContainer.innerHTML = "";

    const standardKeys = [
      "Total allergens logged",
      "Total symptoms logged",
      "Total days tracked",
      "Average allergens logged per day",
      "Average symptoms logged per day"
    ];

    Object.entries(stats).forEach(([key, value]) => {
      if (standardKeys.includes(key)) return;

      let displayValue = value;
      if (key === "Predicted next cycle date" && value) {
        displayValue = value;
      }

      const statDiv = document.createElement("div");
      statDiv.className = "stat-card stat-card--secondary stat-inline";
      statDiv.innerHTML = `
        <span class="stat-label">${key}</span>
        <span class="stat-value">${displayValue ?? "—"}</span>
      `;
      extraStatsContainer.appendChild(statDiv);
    });
  }
}

function renderSummaryText(text) {
  setSummaryState(text?.trim() || "No summary available.");
}

function setAnalysisStatus(message) {
  const el = getElement("analysis-status");
  if (el) el.textContent = message;
}

// =========================================================
// Fetch summary text
// =========================================================

async function fetchAnalysisStats({ force = false } = {}) {
  console.log("fetchAnalysisStats entered", {
    force,
    analysisStatsLoading,
    analysisStatsLoaded
  });

  if (analysisStatsLoading) {
    console.log("Analysis stats already loading, skipping duplicate call");
    return null;
  }

  if (analysisStatsLoaded && !force) {
    console.log("Analysis stats already loaded, skipping duplicate call");
    return null;
  }

  analysisStatsLoading = true;

  try {
    const url = `${API_URL}/analysis/stats`;
    const token = localStorage.getItem("access_token");

    console.log("Fetching analysis stats from:", url);
    console.trace("fetchAnalysisStats called from");

    const AnalStatsRes = await fetch(url, {
      method: "GET",
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/json",
      },
    });

    console.log("Analysis stats response status:", AnalStatsRes.status);

    if (!AnalStatsRes.ok) {
      const text = await AnalStatsRes.text();
      console.log("Analysis stats error body:", text);
      throw new Error(`Failed to fetch analysis (${AnalStatsRes.status})`);
    }

    const stats = await AnalStatsRes.json();
    console.log("Analysis stats data:", stats);

    renderAnalysisStats(stats);
    analysisStatsLoaded = true;
    return stats;

  } catch (err) {
    console.error("Failed to fetch analysis stats:", err);
    return null;

  } finally {
    analysisStatsLoading = false;
    console.log("fetchAnalysisStats finished; analysisStatsLoading reset to false");
  }
}

// =========================================================
// Plots
// =========================================================

async function fetchHistogramPlot({ force = false } = {}) {
  if (histogramLoaded && !force) return;
  if (histogramLoading) return;

  histogramLoading = true;

  try {
    const histogramPlotImg = getElement("group_histogram");
    if (!histogramPlotImg) return;

    const res = await fetch(`${API_URL}/analysis/symptom_group_histogram`, {
      headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` },
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    const blob = await res.blob();

    if (histogramPlotImg.dataset.objectUrl) {
      URL.revokeObjectURL(histogramPlotImg.dataset.objectUrl);
    }

    const objectUrl = URL.createObjectURL(blob);
    histogramPlotImg.src = objectUrl;
    histogramPlotImg.dataset.objectUrl = objectUrl;

    histogramLoaded = true;
  } catch (err) {
    console.error("Failed to fetch histogram plot:", err);
  } finally {
    histogramLoading = false;
  }
}

async function fetchAllergenRankPlot({ force = false } = {}) {
  if (allergenRankLoaded && !force) return;
  if (allergenRankLoading) return;

  allergenRankLoading = true;

  try {
    const allergenrankPlotImg = getElement("allergenrank-plot");
    if (!allergenrankPlotImg) return;

    const res = await fetch(`${API_URL}/analysis/plot_allergen_rank`, {
      headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` },
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    const blob = await res.blob();

    if (allergenrankPlotImg.dataset.objectUrl) {
      URL.revokeObjectURL(allergenrankPlotImg.dataset.objectUrl);
    }

    const objectUrl = URL.createObjectURL(blob);
    allergenrankPlotImg.src = objectUrl;
    allergenrankPlotImg.dataset.objectUrl = objectUrl;

    allergenRankLoaded = true;
  } catch (err) {
    console.error("Failed to fetch allergen rank plot:", err);
  } finally {
    allergenRankLoading = false;
  }
}

// =========================================================
// Analysis tab load
// =========================================================
function loadAnalysisTab() {
  fetchAnalysisStats({ force: true }).catch(err => {
    console.error("Analysis refresh failed:", err);
  });
}

// =========================================================
// Tabs
// =========================================================

const setupTabs = () => {
  document.querySelectorAll(".tab").forEach(tab => {
    tab.addEventListener("click", () => {
      const target = tab.dataset.tab;

      document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
      document.querySelectorAll(".form").forEach(f => f.classList.remove("active"));

      tab.classList.add("active");

      const targetForm = getElement(`${target}-form`);
      if (targetForm) targetForm.classList.add("active");

      if (target === "analysis") {
        loadAnalysisTab();
      }
    });
  });
};

// =========================================================
// Captions
// =========================================================

function updateCaptions(allergenName, symptomGroup, lagText) {
  const elements = {
    "caption-allergen": allergenName,
    "caption-symptom-group": symptomGroup,
    "caption-lag": lagText,
    "caption-allergen-dose": allergenName,
    "caption-lag-dose": lagText
  };

  for (const [id, text] of Object.entries(elements)) {
    const el = getElement(id);
    if (el) el.textContent = text;
  }
}

// =========================================================
// Global click handler for hiding suggestions
// =========================================================

document.addEventListener("click", (e) => {
  if (!e.target.closest(".autocomplete-wrapper")) {
    document.querySelectorAll(".suggestions").forEach(s => s.classList.remove("visible"));
  }
});

// =========================================================
// Recent logs – API helpers
// =========================================================

async function fetchAllergenLogs(limit = 10) {
  const token = localStorage.getItem("access_token");
  const res = await fetch(`${API_URL}/entries/allergens?limit=${limit}`, {
    headers: { Authorization: `Bearer ${token}`, Accept: "application/json" },
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function fetchSymptomLogs(limit = 10) {
  const token = localStorage.getItem("access_token");
  const res = await fetch(`${API_URL}/entries/symptoms?limit=${limit}`, {
    headers: { Authorization: `Bearer ${token}`, Accept: "application/json" },
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function updateAllergenLog(logId, payload) {
  const token = localStorage.getItem("access_token");
  const res = await fetch(`${API_URL}/entries/allergens/${logId}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

async function updateSymptomLog(logId, payload) {
  const token = localStorage.getItem("access_token");
  const res = await fetch(`${API_URL}/entries/symptoms/${logId}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// =========================================================
// Recent logs – display helpers
// =========================================================

function formatLogDate(isoString) {
  const d = new Date(isoString);
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  });
}

function isoToDateTimeLocal(isoString) {
  const d = new Date(isoString);
  const tzOffsetMs = d.getTimezoneOffset() * 60000;
  return new Date(d.getTime() - tzOffsetMs).toISOString().slice(0, 16);
}

// =========================================================
// Recent logs – render allergen logs
// =========================================================

function renderAllergenLogs(logs, allergens, units) {
  const container = getElement("allergen-logs-list");
  if (!container) return;

  if (!logs.length) {
    container.innerHTML = '<p class="logs-empty">No allergen logs yet.</p>';
    return;
  }

  container.innerHTML = "";

  logs.forEach(log => {
    const item = document.createElement("div");
    item.className = "log-item";

    const qtyText = log.quantity != null
      ? `${log.quantity}${log.unit_name ? " " + log.unit_name : ""}`
      : "—";

    const display = document.createElement("div");
    display.className = "log-item-display";
    display.innerHTML = `
      <span class="log-field log-field--name">${log.allergen_name}</span>
      <span class="log-field log-field--meta">${formatLogDate(log.date_time)}</span>
      <span class="log-field log-field--meta">${qtyText}</span>
      <button class="log-edit-btn" type="button">Edit</button>
    `;

    const allergenOptions = allergens
      .map(a => `<option value="${a.allergen_id}" ${a.allergen_id === log.allergen_id ? "selected" : ""}>${a.allergen_name}</option>`)
      .join("");

    const unitOptions = `<option value="">—</option>` +
      units.map(u => `<option value="${u.unit_id}" ${u.unit_id === log.unit_id ? "selected" : ""}>${u.unit_name}</option>`).join("");

    const edit = document.createElement("div");
    edit.className = "log-item-edit";
    edit.hidden = true;
    edit.innerHTML = `
      <div class="edit-row">
        <label>Allergen</label>
        <select class="edit-allergen">${allergenOptions}</select>
      </div>
      <div class="edit-row">
        <label>Date &amp; time</label>
        <input type="datetime-local" class="edit-date" value="${isoToDateTimeLocal(log.date_time)}" />
      </div>
      <div class="edit-row">
        <label>Quantity</label>
        <div class="inline-fields">
          <input type="number" step="any" class="edit-qty" value="${log.quantity ?? ""}" style="width:70px" />
          <select class="edit-unit" style="width:80px">${unitOptions}</select>
        </div>
      </div>
      <div class="edit-actions">
        <button type="button" class="primary save-log-btn">Save</button>
        <button type="button" class="secondary cancel-log-btn">Cancel</button>
        <span class="edit-error error"></span>
      </div>
    `;

    item.appendChild(display);
    item.appendChild(edit);
    container.appendChild(item);

    display.querySelector(".log-edit-btn").addEventListener("click", () => {
      display.hidden = true;
      edit.hidden = false;
    });

    edit.querySelector(".cancel-log-btn").addEventListener("click", () => {
      edit.hidden = true;
      display.hidden = false;
    });

    edit.querySelector(".save-log-btn").addEventListener("click", async () => {
      const errorEl = edit.querySelector(".edit-error");
      errorEl.textContent = "";

      const allergenId = Number(edit.querySelector(".edit-allergen").value);
      const dateTime = new Date(edit.querySelector(".edit-date").value).toISOString();
      const qtyRaw = edit.querySelector(".edit-qty").value;
      const unitId = Number(edit.querySelector(".edit-unit").value) || null;

      try {
        await updateAllergenLog(log.allergen_log_id, {
          allergen_id: allergenId,
          date_time: dateTime,
          quantity: qtyRaw !== "" ? Number(qtyRaw) : null,
          unit_id: unitId,
        });

        const newAllergenName = allergens.find(a => a.allergen_id === allergenId)?.allergen_name ?? "";
        const newUnitName = units.find(u => u.unit_id === unitId)?.unit_name ?? "";
        const newQtyText = qtyRaw !== "" ? `${Number(qtyRaw)}${newUnitName ? " " + newUnitName : ""}` : "—";

        display.querySelector(".log-field--name").textContent = newAllergenName;
        display.querySelectorAll(".log-field--meta")[0].textContent = formatLogDate(dateTime);
        display.querySelectorAll(".log-field--meta")[1].textContent = newQtyText;

        log.allergen_id = allergenId;
        log.date_time = dateTime;
        log.quantity = qtyRaw !== "" ? Number(qtyRaw) : null;
        log.unit_id = unitId;

        edit.hidden = true;
        display.hidden = false;
      } catch (err) {
        errorEl.textContent = "Save failed: " + err.message;
      }
    });
  });
}

// =========================================================
// Recent logs – render symptom logs
// =========================================================

function renderSymptomLogs(logs, symptoms) {
  const container = getElement("symptom-logs-list");
  if (!container) return;

  if (!logs.length) {
    container.innerHTML = '<p class="logs-empty">No symptom logs yet.</p>';
    return;
  }

  container.innerHTML = "";

  logs.forEach(log => {
    const item = document.createElement("div");
    item.className = "log-item";

    const display = document.createElement("div");
    display.className = "log-item-display";
    display.innerHTML = `
      <span class="log-field log-field--name">${log.symptom_name}</span>
      <span class="log-field log-field--meta">${formatLogDate(log.date_time)}</span>
      <span class="log-field log-field--meta">${INTENSITY_LABELS[log.intensity] ?? "—"}</span>
      <button class="log-edit-btn" type="button">Edit</button>
    `;

    const symptomOptions = symptoms
      .map(s => `<option value="${s.symptom_id}" ${s.symptom_id === log.symptom_id ? "selected" : ""}>${s.symptom_name}</option>`)
      .join("");

    const edit = document.createElement("div");
    edit.className = "log-item-edit";
    edit.hidden = true;
    edit.innerHTML = `
      <div class="edit-row">
        <label>Symptom</label>
        <select class="edit-symptom">${symptomOptions}</select>
      </div>
      <div class="edit-row">
        <label>Date &amp; time</label>
        <input type="datetime-local" class="edit-date" value="${isoToDateTimeLocal(log.date_time)}" />
      </div>
      <div class="edit-row">
        <label>Intensity</label>
        <select class="edit-intensity">
          <option value="0" ${log.intensity === 0 ? "selected" : ""}>None</option>
          <option value="1" ${log.intensity === 1 ? "selected" : ""}>Mild</option>
          <option value="2" ${log.intensity === 2 ? "selected" : ""}>Moderate</option>
          <option value="3" ${log.intensity === 3 ? "selected" : ""}>Severe</option>
        </select>
      </div>
      <div class="edit-actions">
        <button type="button" class="primary save-log-btn">Save</button>
        <button type="button" class="secondary cancel-log-btn">Cancel</button>
        <span class="edit-error error"></span>
      </div>
    `;

    item.appendChild(display);
    item.appendChild(edit);
    container.appendChild(item);

    display.querySelector(".log-edit-btn").addEventListener("click", () => {
      display.hidden = true;
      edit.hidden = false;
    });

    edit.querySelector(".cancel-log-btn").addEventListener("click", () => {
      edit.hidden = true;
      display.hidden = false;
    });

    edit.querySelector(".save-log-btn").addEventListener("click", async () => {
      const errorEl = edit.querySelector(".edit-error");
      errorEl.textContent = "";

      const symptomId = Number(edit.querySelector(".edit-symptom").value);
      const dateTime = new Date(edit.querySelector(".edit-date").value).toISOString();
      const intensity = Number(edit.querySelector(".edit-intensity").value);

      try {
        await updateSymptomLog(log.symptom_log_id, {
          symptom_id: symptomId,
          date_time: dateTime,
          intensity: intensity,
        });

        const newSymptomName = symptoms.find(s => s.symptom_id === symptomId)?.symptom_name ?? "";

        display.querySelector(".log-field--name").textContent = newSymptomName;
        display.querySelectorAll(".log-field--meta")[0].textContent = formatLogDate(dateTime);
        display.querySelectorAll(".log-field--meta")[1].textContent = INTENSITY_LABELS[intensity];

        log.symptom_id = symptomId;
        log.date_time = dateTime;
        log.intensity = intensity;

        edit.hidden = true;
        display.hidden = false;
      } catch (err) {
        errorEl.textContent = "Save failed: " + err.message;
      }
    });
  });
}

// =========================================================
// Recent logs – load functions (called from init + form submit)
// =========================================================

async function loadAllergenLogs() {
  const container = getElement("allergen-logs-list");
  if (!container) return;
  container.innerHTML = '<p class="logs-loading">Loading…</p>';
  try {
    const logs = await fetchAllergenLogs(10);
    renderAllergenLogs(logs, cachedAllergens, cachedUnits);
  } catch (err) {
    container.innerHTML = '<p class="logs-empty">Could not load logs.</p>';
    console.error("Failed to load allergen logs:", err);
  }
}

async function loadSymptomLogs() {
  const container = getElement("symptom-logs-list");
  if (!container) return;
  container.innerHTML = '<p class="logs-loading">Loading…</p>';
  try {
    const logs = await fetchSymptomLogs(10);
    renderSymptomLogs(logs, cachedSymptoms);
  } catch (err) {
    container.innerHTML = '<p class="logs-empty">Could not load logs.</p>';
    console.error("Failed to load symptom logs:", err);
  }
}

// =========================================================
// Init
// =========================================================

async function init() {
  console.log("init() started");
  const token = localStorage.getItem("access_token");

  if (!token || isTokenExpired(token)) {
    console.log("Missing or expired token, redirecting to login");
    localStorage.removeItem("access_token");
    window.location.href = "index.html";
    return;
  }

  try {

    console.log("Calling getCurrentUser()");
    const user = await getCurrentUser();
    console.log("Received user:", user);

    if (!user || !user.email) {
      console.error("Invalid user object!", user);
      throw new Error("Invalid user");
    }

    const userEmailEl = getElement("user-email");
    if (userEmailEl) userEmailEl.textContent = user.email;

    // Set up UI components
    setupLogout();
    setupDefaults();
    setupTabs();

    try {
      const [units, allergens, recentAllergens, symptoms, recentSymptoms] = await Promise.all([
        fetchUnits(),
        fetchAllergens(),
        fetchRecentAllergens(10),
        fetchSymptoms(),
        fetchRecentSymptoms(10)
      ]);

      cachedAllergens = allergens || [];
      cachedSymptoms = symptoms || [];
      cachedUnits = units || [];

      populateAllergenSelect(allergens, recentAllergens);
      populateSymptomSelect(symptoms, recentSymptoms);

      setupAddAllergen();
      setupAddSymptom();

      await Promise.all([loadAllergenLogs(), loadSymptomLogs()]);
    } catch (err) {
      console.error("Error during page init:", err);

      const allergenSelect = getElement("allergen-select");
      if (allergenSelect) {
        allergenSelect.innerHTML = '<option value="">Error loading allergens</option>';
      }
    }

    console.log("Data loading complete");

    // -----------------------------------------
    // Sync allergen select → inputs
    // -----------------------------------------
    const allergenSelect = getElement("allergen-select");
    const allergenIdInput = getElement("allergen-id");

    console.log({ allergenSelect, allergenIdInput });
    if (allergenSelect) {
      allergenSelect.addEventListener("change", () => {
        const selectedOption = allergenSelect.selectedOptions[0];

        if (!selectedOption || !allergenSelect.value) {
          allergenIdInput.value = "";
          return;
        }

        allergenIdInput.value = allergenSelect.value;
      });
    }
    // -----------------------------------------
    // Sync allergen select → inputs
    // -----------------------------------------
    const symptomSelect = getElement("symptom-select");
    const symptomIdInput = getElement("symptom-id");

    if (symptomSelect) {
      symptomSelect.addEventListener("change", () => {
        const selectedOption = symptomSelect.selectedOptions[0];

        if (!selectedOption || !symptomSelect.value) {
          symptomIdInput.value = "";
          return;
        }

        symptomIdInput.value = symptomSelect.value;
      });
    }

    // Set up autocomplete (after data is loaded)
    console.log("Setting up autocomplete...");
    setupAutocomplete(
      getElement("symptom-select"),
      getElement("symptom-id"),
      getElement("symptom-suggestions"),
      "symptom"
    );
    setupAutocomplete(
      getElement("allergen-intensity-input"),
      getElement("allergen-intensity-id"),
      getElement("allergen-intensity-suggestions"),
      "allergen"
    );
    setupAutocomplete(
      getElement("symptom-group-input"),
      null,
      getElement("symptom-group-suggestions"),
      "symptom_group"
    );

    // Set up forms
    setupForms();

    // ✅ Position slider labels
    positionRangeLabels("symptom-intensity", "intensity-labels");

    // Re-position on resize
    window.addEventListener("resize", () =>
      positionRangeLabels("symptom-intensity", "intensity-labels")
    );

    // Set up analysis
    //setupAnalysis();
    setupAnalysisDropdown();

    // Initialize captions
    initializeCaptions();

    console.log("✅ init() completed successfully");

  } catch (err) {
    console.error("❌ init() failed:", err);
    localStorage.removeItem("access_token");
    window.location.href = "index.html";
  }
}

function initializeCaptions() {
  const allergenIntInput = getElement("allergen-intensity-input");
  const symptomGroupInput = getElement("symptom-group-input");
  const lagWindowInput = getElement("lag-window");

  const captionAllergen = getElement("caption-allergen");
  const captionSymptomGroup = getElement("caption-symptom-group");
  const captionLag = getElement("caption-lag");
  const captionLagDose = getElement("caption-lag-dose");
  const captionAllergenDose = getElement("caption-allergen-dose");

  if (captionAllergen && allergenIntInput) {
    captionAllergen.textContent = allergenIntInput.value || "";
  }
  
  if (captionSymptomGroup && symptomGroupInput) {
    captionSymptomGroup.textContent = symptomGroupInput.value || "";
  }
  
  if (captionLag && lagWindowInput && lagWindowInput.selectedOptions[0]) {
    captionLag.textContent = lagWindowInput.selectedOptions[0].text || "";
  }
  
  if (captionLagDose && lagWindowInput && lagWindowInput.selectedOptions[0]) {
    captionLagDose.textContent = lagWindowInput.selectedOptions[0].text || "";
  }
  
  if (captionAllergenDose && allergenIntInput) {
    captionAllergenDose.textContent = allergenIntInput.value || "";
  }
}
