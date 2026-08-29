import { getCurrentUser, getUserCount, API_URL } from "./api.js";

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

async function loadUserCountBadge() {
  try {
    const data = await getUserCount();
    const badge = getElement("user-count-badge");
    if (!badge) return;

    badge.textContent = `Users: ${data.user_count}`;
    badge.style.display = "inline-flex";
  } catch (err) {
    console.warn("Failed to load user count badge:", err);
  }
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

    const allergens = await fetchAllergens();
    const recentAllergens = await fetchRecentAllergens(5);
    cachedAllergens = allergens || [];
    populateAllergenSelect(allergens, recentAllergens);

    const select  = getElement("allergen-select");
    const idInput = getElement("allergen-id");
    if (select)  select.value  = data.allergen_id;
    if (idInput) idInput.value = data.allergen_id;

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

    const symptoms = await fetchSymptoms();
    const recentSymptoms = await fetchRecentSymptoms(5);
    cachedSymptoms = symptoms || [];
    populateSymptomSelect(symptoms, recentSymptoms);

    const select  = getElement("symptom-select");
    const idInput = getElement("symptom-id");
    if (select)  select.value  = data.symptom_id;
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
let cachedMedications = [];
let currentUser = null;

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
    getElement("panel-time-series"),
    getElement("panel-deeper-analysis"),
    getElement("panel-checkin-trends"),
    getElement("panel-symptom-calendar"),
    getElement("panel-headache-forecast"),
    getElement("panel-medication-change"),
    getElement("panel-triptan-monthly"),
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

  if (selected === "time-series") {
    const tsPanel = getElement("panel-time-series");
    if (tsPanel) tsPanel.classList.add("visible");
    return;
  }

  if (selected === "deeper-analysis") {
    if (deeperPanel) deeperPanel.classList.add("visible");
    return;
  }

  if (selected === "checkin-trends") {
    const panel = getElement("panel-checkin-trends");
    if (panel) panel.classList.add("visible");
    await fetchCheckinTrendsPlot();
    return;
  }

  if (selected === "symptom-calendar") {
    const panel = getElement("panel-symptom-calendar");
    if (panel) panel.classList.add("visible");
    await fetchSymptomCalendarPlot();
    return;
  }

  if (selected === "headache-forecast") {
    const panel = getElement("panel-headache-forecast");
    if (panel) panel.classList.add("visible");
    await fetchHeadacheForecastPlot();
    return;
  }

  if (selected === "medication-change") {
    const panel = getElement("panel-medication-change");
    if (panel) panel.classList.add("visible");
    await initMedicationChangePanel();
    return;
  }

  if (selected === "triptan-monthly") {
    const panel = getElement("panel-triptan-monthly");
    if (panel) panel.classList.add("visible");
    await fetchTriptanMonthlyPlot();
    return;
  }
}

// =========================================================
// Time series panel
// =========================================================

function setupTimeSeries() {
  const typeSelect  = getElement("ts-type-select");
  const nameSelect  = getElement("ts-name-select");
  const type2Select = getElement("ts-type2-select");
  const name2Select = getElement("ts-name2-select");
  const figure      = getElement("ts-figure");
  const img         = getElement("ts-plot");
  const status      = getElement("ts-status");
  const customRange = getElement("ts-custom-range");
  const dateFrom    = getElement("ts-date-from");
  const dateTo      = getElement("ts-date-to");

  if (!typeSelect || !nameSelect) return;

  function populateNameSelect(typeEl, nameEl) {
    const val = typeEl.value;
    if (!val) { nameEl.innerHTML = '<option value="">Select…</option>'; nameEl.disabled = true; return; }
    nameEl.innerHTML = '<option value="">Select…</option>';

    if (val === "checkin") {
      const vars = currentUser?.user_id === 4
        ? [...CHECKIN_VARS_GENERAL, ...CHECKIN_VARS_EXTRA]
        : CHECKIN_VARS_GENERAL;
      vars.forEach(v => nameEl.appendChild(new Option(v.label, v.key)));
      nameEl.disabled = false;
      return;
    }

    let items, labelKey;
    if (val === "allergen")        { items = cachedAllergens;   labelKey = "allergen_name"; }
    else if (val === "symptom")    { items = cachedSymptoms;    labelKey = "symptom_name"; }
    else                           { items = cachedMedications; labelKey = "medication_name"; }
    items.forEach(item => {
      const label = item[labelKey];
      nameEl.appendChild(new Option(label, label));
    });
    nameEl.disabled = false;
  }

  function getDateRange() {
    const active = document.querySelector(".ts-range-btn.active");
    const range = active?.dataset.range ?? "all";
    const tzOffset = new Date().getTimezoneOffset(); // minutes; negative east of UTC (e.g. NZ = -720)
    if (range === "all") return {};
    if (range === "custom") {
      const params = { tz_offset: tzOffset };
      if (dateFrom?.value) params.date_from = dateFrom.value;
      if (dateTo?.value)   params.date_to   = dateTo.value;
      return params;
    }
    const months = range === "3m" ? 3 : 1;
    const from = new Date();
    from.setMonth(from.getMonth() - months);
    return {
      date_from: localDateTimeForInput(from).slice(0, 10),
      date_to:   localDateTimeForInput().slice(0, 10),
      tz_offset: tzOffset,
    };
  }

  async function fetchTsPlot() {
    const type = typeSelect.value;
    const name = nameSelect.value;
    if (!name) return;

    const type2 = type2Select?.value || "";
    const name2 = name2Select?.value || "";

    const params = new URLSearchParams({ type, name });
    if (type2 && name2) { params.set("type2", type2); params.set("name2", name2); }
    Object.entries(getDateRange()).forEach(([k, v]) => params.set(k, v));

    if (status) status.textContent = "Loading…";
    if (figure) figure.style.display = "none";

    const token = localStorage.getItem("access_token");
    try {
      const res = await fetch(`${API_URL}/analysis/plot_event_series?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const blob = await res.blob();
      if (img.dataset.objectUrl) URL.revokeObjectURL(img.dataset.objectUrl);
      const objectUrl = URL.createObjectURL(blob);
      img.src = objectUrl;
      img.dataset.objectUrl = objectUrl;

      if (status) status.textContent = "";
      if (figure) figure.style.display = "block";
    } catch (err) {
      if (status) status.textContent = `Could not load plot: ${err.message}`;
      console.error("Time series plot error:", err);
    }
  }

  // Variable 1
  typeSelect.addEventListener("change", () => {
    populateNameSelect(typeSelect, nameSelect);
    if (figure) figure.style.display = "none";
  });
  nameSelect.addEventListener("change", fetchTsPlot);

  // ── CCF section helpers ─────────────────────────────────────

  const ccfSection = getElement("ts-ccf-section");
  const ccfFigure  = getElement("ts-ccf-figure");
  const ccfStatus  = getElement("ts-ccf-status");
  const ccfImg     = getElement("ts-ccf-plot");
  const ccfBtn     = getElement("ts-ccf-btn");

  function showCcfSection(visible) {
    if (ccfSection) ccfSection.style.display = visible ? "" : "none";
    if (!visible && ccfFigure) ccfFigure.style.display = "none";
    if (!visible && ccfStatus) ccfStatus.textContent = "";
  }

  function resetCcfResult() {
    if (ccfFigure)  ccfFigure.style.display  = "none";
    if (ccfStatus)  ccfStatus.textContent     = "";
    if (periFigure) periFigure.style.display  = "none";
    if (periStatus) periStatus.textContent    = "";
  }

  async function fetchCcfPlot() {
    const type  = typeSelect.value;
    const name  = nameSelect.value;
    const type2 = type2Select?.value;
    const name2 = name2Select?.value;
    if (!name || !type2 || !name2) return;

    const params = new URLSearchParams({ type, name, type2, name2 });
    Object.entries(getDateRange()).forEach(([k, v]) => params.set(k, v));
    // getDateRange() omits tz_offset on the "all" range, but the 12-hour bins
    // are anchored to local midnight regardless of which range is selected.
    if (!params.has("tz_offset")) {
      params.set("tz_offset", new Date().getTimezoneOffset());
    }

    if (ccfStatus)  ccfStatus.textContent = "Running analysis…";
    if (ccfFigure)  ccfFigure.style.display = "none";

    const token = localStorage.getItem("access_token");
    try {
      const res = await fetch(`${API_URL}/analysis/plot_cross_correlation?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const blob = await res.blob();
      if (ccfImg.dataset.objectUrl) URL.revokeObjectURL(ccfImg.dataset.objectUrl);
      const objectUrl = URL.createObjectURL(blob);
      ccfImg.src = objectUrl;
      ccfImg.dataset.objectUrl = objectUrl;

      if (ccfStatus)  ccfStatus.textContent = "";
      if (ccfFigure)  ccfFigure.style.display = "block";
    } catch (err) {
      if (ccfStatus) ccfStatus.textContent = `Analysis failed: ${err.message}`;
      console.error("CCF plot error:", err);
    }
  }

  if (ccfBtn) ccfBtn.addEventListener("click", fetchCcfPlot);

  // ── Peri-event ──────────────────────────────────────────────

  const periBtn     = getElement("ts-peri-btn");
  const periFigure  = getElement("ts-peri-figure");
  const periStatus  = getElement("ts-peri-status");
  const periImg     = getElement("ts-peri-plot");
  const periWindow  = getElement("ts-peri-window");

  function resetPeriResult() {
    if (periFigure) periFigure.style.display = "none";
    if (periStatus) periStatus.textContent = "";
  }

  async function fetchPeriPlot() {
    const type  = typeSelect.value;
    const name  = nameSelect.value;
    const type2 = type2Select?.value;
    const name2 = name2Select?.value;
    const win   = periWindow?.value ?? "15";
    if (!name || !type2 || !name2) return;

    const params = new URLSearchParams({ type, name, type2, name2, window_days: win });
    Object.entries(getDateRange()).forEach(([k, v]) => params.set(k, v));
    // getDateRange() omits tz_offset on the "all" range, but the TODAY marker
    // needs the local timezone regardless of which range is selected.
    if (!params.has("tz_offset")) {
      params.set("tz_offset", new Date().getTimezoneOffset());
    }

    if (periStatus) periStatus.textContent = "Running analysis…";
    if (periFigure) periFigure.style.display = "none";

    const token = localStorage.getItem("access_token");
    try {
      const res = await fetch(`${API_URL}/analysis/plot_peri_event?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const blob = await res.blob();
      if (periImg.dataset.objectUrl) URL.revokeObjectURL(periImg.dataset.objectUrl);
      const objectUrl = URL.createObjectURL(blob);
      periImg.src = objectUrl;
      periImg.dataset.objectUrl = objectUrl;

      if (periStatus) periStatus.textContent = "";
      if (periFigure) periFigure.style.display = "block";
    } catch (err) {
      if (periStatus) periStatus.textContent = `Analysis failed: ${err.message}`;
      console.error("Peri-event plot error:", err);
    }
  }

  if (periBtn) periBtn.addEventListener("click", fetchPeriPlot);

  // ── Variable 2 ──────────────────────────────────────────────

  type2Select?.addEventListener("change", () => {
    populateNameSelect(type2Select, name2Select);
    resetCcfResult();
    if (!type2Select.value) {
      showCcfSection(false);
      if (nameSelect.value) fetchTsPlot();
    }
  });

  name2Select?.addEventListener("change", () => {
    resetCcfResult();
    const hasBoth = !!(nameSelect.value && name2Select.value && type2Select.value);
    showCcfSection(hasBoth);
    if (nameSelect.value) fetchTsPlot();
  });

  // ── Date range buttons ───────────────────────────────────────

  document.querySelectorAll(".ts-range-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".ts-range-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      const isCustom = btn.dataset.range === "custom";
      if (customRange) customRange.style.display = isCustom ? "" : "none";
      resetCcfResult();
      if (!isCustom && nameSelect.value) fetchTsPlot();
    });
  });

  // Custom date inputs
  dateFrom?.addEventListener("change", () => { resetCcfResult(); if (nameSelect.value) fetchTsPlot(); });
  dateTo?.addEventListener("change",   () => { resetCcfResult(); if (nameSelect.value) fetchTsPlot(); });

  // Init
  populateNameSelect(typeSelect, nameSelect);
  if (name2Select) name2Select.disabled = true;
  showCcfSection(false);

  // Default plot for user 4
  if (currentUser?.user_id === 4) {
    function selectByName(selectEl, name) {
      const lower = name.toLowerCase();
      const opt = Array.from(selectEl.options).find(o => o.text.toLowerCase() === lower);
      if (opt) selectEl.value = opt.value;
      return !!opt;
    }

    typeSelect.value = "allergen";
    populateNameSelect(typeSelect, nameSelect);
    selectByName(nameSelect, "triptan");

    if (type2Select && name2Select) {
      type2Select.value = "allergen";
      populateNameSelect(type2Select, name2Select);
      selectByName(name2Select, "period");
      name2Select.disabled = false;
      showCcfSection(!!(nameSelect.value && name2Select.value));
      if (nameSelect.value) fetchTsPlot();
    }
  }
}

// =========================================================
// Deeper analysis panel
// =========================================================

function setupDeeperAnalysis() {
  const btn = getElement("update-plot-btn");
  if (!btn) return;

  btn.addEventListener("click", async () => {
    const allergenName  = getElement("allergen-intensity-input")?.value?.trim();
    const lagRaw        = getElement("lag-window")?.value || "0_24";
    const symptomGroup  = getElement("symptom-group-input")?.value?.trim();

    const statusEl   = getElement("deeper-status");
    const plotsDiv   = getElement("deeper-plots");

    if (!allergenName) {
      if (statusEl) statusEl.textContent = "Please select an allergen first.";
      return;
    }

    // Parse "0_6" → lag_start=0, lag_end=6
    const [lagStart, lagEnd] = lagRaw.split("_").map(Number);

    const token = localStorage.getItem("access_token");
    const headers = { Authorization: `Bearer ${token}` };

    if (statusEl) statusEl.textContent = "Generating plots…";
    if (plotsDiv) plotsDiv.style.display = "none";

    const base = new URLSearchParams({
      allergen_name: allergenName,
      lag_start: lagStart,
      lag_end: lagEnd,
      ...(symptomGroup ? { symptom_group: symptomGroup } : {}),
    });

    async function loadImg(url, imgId) {
      const res = await fetch(url, { headers });
      if (!res.ok) throw new Error(`${imgId}: server returned ${res.status}`);
      const blob = await res.blob();
      const img  = getElement(imgId);
      if (!img) return;
      if (img.dataset.objectUrl) URL.revokeObjectURL(img.dataset.objectUrl);
      img.src = URL.createObjectURL(blob);
      img.dataset.objectUrl = img.src;
    }

    try {
      await Promise.all([
        loadImg(
          `${API_URL}/analysis/plot_time_series?allergen_name=${encodeURIComponent(allergenName)}`,
          "deeper-time-series-plot"
        ),
        loadImg(
          `${API_URL}/analysis/plot_bar_plots?${base}`,
          "deeper-bar-plot"
        ),
        loadImg(
          `${API_URL}/analysis/plot_risk?${base}`,
          "deeper-risk-plot"
        ),
      ]);

      if (statusEl) statusEl.textContent = "";
      if (plotsDiv) plotsDiv.style.display = "block";
    } catch (err) {
      if (statusEl) statusEl.textContent = `Error: ${err.message}`;
      console.error("Deeper analysis error:", err);
    }
  });
}

// =========================================================
// Medications tab – API helpers
// =========================================================

async function fetchMedList() {
  const token = localStorage.getItem("access_token");
  const res = await fetch(`${API_URL}/medications`, {
    headers: { Authorization: `Bearer ${token}`, Accept: "application/json" },
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function fetchCurrentRegimens() {
  const token = localStorage.getItem("access_token");
  const res = await fetch(`${API_URL}/medications/regimens/current`, {
    headers: { Authorization: `Bearer ${token}`, Accept: "application/json" },
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function fetchAllRegimens() {
  const token = localStorage.getItem("access_token");
  const res = await fetch(`${API_URL}/medications/regimens`, {
    headers: { Authorization: `Bearer ${token}`, Accept: "application/json" },
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function apiCreateMedication(name) {
  const token = localStorage.getItem("access_token");
  const res = await fetch(`${API_URL}/medications`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ medication_name: name }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

async function apiCreateRegimen(payload) {
  const token = localStorage.getItem("access_token");
  const res = await fetch(`${API_URL}/medications/regimens`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

async function apiChangeDose(regimenId, payload) {
  const token = localStorage.getItem("access_token");
  const res = await fetch(`${API_URL}/medications/regimens/${regimenId}/change-dose`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// =========================================================
// Medications tab – render helpers
// =========================================================

function formatMedDate(dateStr) {
  if (!dateStr) return "present";
  const d = new Date(dateStr + "T00:00:00");
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function buildMedCard(r) {
  const card = document.createElement("div");
  card.className = "med-card";

  const noteText = r.note ? ` · ${r.note}` : "";
  card.innerHTML = `
    <div class="med-card-header">
      <span class="med-card-name">${r.medication_name}</span>
      <span class="med-card-dose">${r.dose} ${r.unit}${noteText}</span>
    </div>
    <div class="med-card-since">Since ${formatMedDate(r.start_date)}</div>
    <div class="med-card-actions">
      <button type="button" class="secondary med-change-btn">Change dose</button>
    </div>
    <div class="med-change-panel" style="display:none">
      <div class="form-row">
        <label>New dose</label>
        <div class="inline-fields">
          <input type="number" class="med-change-dose" step="any" value="${r.dose}" style="width:80px" />
          <input type="text" class="med-change-unit" value="${r.unit}" style="width:60px" />
        </div>
      </div>
      <div class="form-row">
        <label>Note</label>
        <input type="text" class="med-change-note" value="${r.note || ""}" placeholder="e.g. morning dose" />
      </div>
      <div class="form-row">
        <label>Effective from</label>
        <input type="date" class="med-change-date" value="${localDateTimeForInput().slice(0, 10)}" />
      </div>
      <div class="form-row">
        <label></label>
        <div class="inline-fields">
          <button type="button" class="primary med-change-submit" style="width:auto;margin:0">Update</button>
          <button type="button" class="secondary med-change-cancel" style="width:auto;margin:0">Cancel</button>
        </div>
      </div>
      <p class="med-change-error error"></p>
    </div>
  `;

  const changeBtn  = card.querySelector(".med-change-btn");
  const changePanel = card.querySelector(".med-change-panel");
  const cancelBtn  = card.querySelector(".med-change-cancel");
  const submitBtn  = card.querySelector(".med-change-submit");
  const errorEl    = card.querySelector(".med-change-error");

  changeBtn.addEventListener("click", () => {
    changePanel.style.display = changePanel.style.display === "none" ? "" : "none";
    errorEl.textContent = "";
  });

  cancelBtn.addEventListener("click", () => {
    changePanel.style.display = "none";
    errorEl.textContent = "";
  });

  submitBtn.addEventListener("click", async () => {
    const newDose  = parseFloat(card.querySelector(".med-change-dose").value);
    const newUnit  = card.querySelector(".med-change-unit").value.trim();
    const newNote  = card.querySelector(".med-change-note").value.trim() || null;
    const newStart = card.querySelector(".med-change-date").value;

    if (!newDose || !newUnit || !newStart) {
      errorEl.textContent = "Please fill in dose, unit, and date.";
      return;
    }

    submitBtn.disabled = true;
    try {
      await apiChangeDose(r.regimen_id, {
        medication_id: r.medication_id,
        dose: newDose,
        unit: newUnit,
        note: newNote,
        start_date: newStart,
      });
      await loadMedicationsTab();
    } catch (err) {
      errorEl.textContent = `Error: ${err.message}`;
      submitBtn.disabled = false;
    }
  });

  return card;
}

function renderMedCards(regimens) {
  const container = getElement("med-current-list");
  if (!container) return;

  if (!regimens.length) {
    container.innerHTML = '<p class="logs-empty">No active medications. Add one below.</p>';
    return;
  }

  container.innerHTML = "";
  regimens.forEach(r => container.appendChild(buildMedCard(r)));
}

function renderMedHistory(regimens) {
  const container = getElement("med-history-list");
  if (!container) return;

  if (!regimens.length) {
    container.innerHTML = '<p class="logs-empty">No history yet.</p>';
    return;
  }

  const table = document.createElement("table");
  table.className = "med-history-table";
  table.innerHTML = `
    <thead><tr>
      <th>Medication</th><th>Dose</th><th>Note</th><th>From</th><th>To</th>
    </tr></thead>
  `;
  const tbody = document.createElement("tbody");
  regimens.forEach(r => {
    const tr = document.createElement("tr");
    tr.className = r.end_date ? "med-row--ended" : "med-row--active";
    tr.innerHTML = `
      <td>${r.medication_name}</td>
      <td>${r.dose} ${r.unit}</td>
      <td>${r.note || "—"}</td>
      <td>${formatMedDate(r.start_date)}</td>
      <td>${r.end_date ? formatMedDate(r.end_date) : "current"}</td>
    `;
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  container.innerHTML = "";
  container.appendChild(table);
}

// =========================================================
// Medications tab – load + setup
// =========================================================

async function loadMedicationsTab() {
  const currentContainer = getElement("med-current-list");
  const historyContainer = getElement("med-history-list");
  if (currentContainer) currentContainer.innerHTML = '<p class="logs-loading">Loading…</p>';
  if (historyContainer) historyContainer.innerHTML = '<p class="logs-loading">Loading…</p>';

  try {
    const [current, all] = await Promise.all([fetchCurrentRegimens(), fetchAllRegimens()]);
    renderMedCards(current);
    renderMedHistory(all);
  } catch (err) {
    console.error("Failed to load medications:", err);
    if (currentContainer) currentContainer.innerHTML = '<p class="logs-empty">Could not load medications.</p>';
    if (historyContainer) historyContainer.innerHTML = "";
  }
}

function setupMedicationsTab() {
  const addToggle  = getElement("med-add-toggle");
  const addPanel   = getElement("med-add-panel");
  const submitBtn  = getElement("med-add-submit");
  const errorEl    = getElement("med-add-error");
  const nameInput  = getElement("med-name-input");
  const doseInput  = getElement("med-dose-input");
  const unitInput  = getElement("med-unit-input");
  const noteInput  = getElement("med-note-input");
  const startInput = getElement("med-start-input");
  const datalist   = document.getElementById("med-name-list");

  if (!addToggle) return;

  if (startInput) startInput.value = localDateTimeForInput().slice(0, 10);
  if (unitInput)  unitInput.value  = "mg";

  addToggle.addEventListener("click", () => {
    const open = addPanel.style.display !== "none";
    addPanel.style.display = open ? "none" : "";
    addToggle.textContent  = open ? "+ Add medication" : "− Cancel";
  });

  async function refreshMedDatalist() {
    try {
      const meds = await fetchMedList();
      if (datalist) {
        datalist.innerHTML = "";
        meds.forEach(m => {
          const opt = document.createElement("option");
          opt.value = m.medication_name;
          datalist.appendChild(opt);
        });
      }
    } catch (err) {
      console.warn("Could not refresh med datalist:", err);
    }
  }
  refreshMedDatalist();

  if (!submitBtn) return;

  submitBtn.addEventListener("click", async () => {
    const name      = nameInput?.value.trim();
    const dose      = parseFloat(doseInput?.value);
    const unit      = unitInput?.value.trim() || "mg";
    const note      = noteInput?.value.trim() || null;
    const startDate = startInput?.value;

    if (!name)      { errorEl.textContent = "Enter a medication name."; return; }
    if (!dose)      { errorEl.textContent = "Enter a dose."; return; }
    if (!startDate) { errorEl.textContent = "Enter a start date."; return; }
    errorEl.textContent = "";
    submitBtn.disabled = true;

    try {
      const med = await apiCreateMedication(name);
      await apiCreateRegimen({ medication_id: med.medication_id, dose, unit, note, start_date: startDate });

      nameInput.value  = "";
      doseInput.value  = "";
      unitInput.value  = "mg";
      noteInput.value  = "";
      startInput.value = localDateTimeForInput().slice(0, 10);
      addPanel.style.display = "none";
      addToggle.textContent  = "+ Add medication";

      await Promise.all([loadMedicationsTab(), refreshMedDatalist()]);
    } catch (err) {
      errorEl.textContent = `Error: ${err.message}`;
    } finally {
      submitBtn.disabled = false;
    }
  });
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

async function fetchAISummary() {
  const btn = getElement("ai-summary-btn");
  const status = getElement("ai-summary-status");

  if (btn) btn.disabled = true;
  if (status) status.textContent = "Generating… this may take a few seconds.";
  setSummaryState("");

  try {
    const res = await fetch(
      `${API_URL}/analysis/generate_summary_text?tz_offset=${new Date().getTimezoneOffset()}`, {
      headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` },
    });

    if (!res.ok) throw new Error(`Server returned ${res.status}`);

    const data = await res.json();
    renderSummaryText(data.text);

    const costLabel = formatAICost(data.input_tokens, data.output_tokens);
    if (status) status.textContent = costLabel ? `Cost: ${costLabel}` : "";
  } catch (err) {
    console.error("AI summary failed:", err);
    setSummaryState("Could not generate summary. Please try again.");
    if (status) status.textContent = "";
  } finally {
    if (btn) btn.disabled = false;
  }
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
    // tz_offset so day counts and the cycle prediction bucket on the user's
    // calendar day rather than the UTC one.
    const url = `${API_URL}/analysis/stats?tz_offset=${new Date().getTimezoneOffset()}`;
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

  const statusEl = getElement("histogram-status");
  const img      = getElement("group_histogram");

  if (statusEl) statusEl.textContent = "Loading…";
  if (img) img.style.display = "none";

  try {
    if (!img) return;

    const res = await fetch(`${API_URL}/analysis/symptom_group_histogram`, {
      headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` },
    });

    if (!res.ok) throw new Error(`Server returned ${res.status}`);

    const blob = await res.blob();
    if (img.dataset.objectUrl) URL.revokeObjectURL(img.dataset.objectUrl);
    img.src = URL.createObjectURL(blob);
    img.dataset.objectUrl = img.src;
    img.style.display = "";

    if (statusEl) statusEl.textContent = "";
    histogramLoaded = true;
  } catch (err) {
    console.error("Failed to fetch histogram plot:", err);
    if (statusEl) statusEl.textContent = `Could not load plot: ${err.message}`;
  } finally {
    histogramLoading = false;
  }
}

async function fetchAllergenRankPlot({ force = false } = {}) {
  if (allergenRankLoaded && !force) return;
  if (allergenRankLoading) return;

  allergenRankLoading = true;

  const statusEl = getElement("allergenrank-status");
  const img      = getElement("allergenrank-plot");

  if (statusEl) statusEl.textContent = "Loading…";
  if (img) img.style.display = "none";

  try {
    if (!img) return;

    const res = await fetch(`${API_URL}/analysis/plot_allergen_rank`, {
      headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` },
    });

    if (!res.ok) throw new Error(`Server returned ${res.status}. You may need more data for the model to run.`);

    const blob = await res.blob();
    if (img.dataset.objectUrl) URL.revokeObjectURL(img.dataset.objectUrl);
    img.src = URL.createObjectURL(blob);
    img.dataset.objectUrl = img.src;
    img.style.display = "";

    if (statusEl) statusEl.textContent = "";
    allergenRankLoaded = true;
  } catch (err) {
    console.error("Failed to fetch allergen rank plot:", err);
    if (statusEl) statusEl.textContent = `Could not load plot: ${err.message}`;
  } finally {
    allergenRankLoading = false;
  }
}

async function fetchTriptanMonthlyPlot() {
  const statusEl = getElement("triptan-monthly-status");
  const img = getElement("triptan-monthly-plot");

  if (statusEl) statusEl.textContent = "Loading…";
  if (img) img.style.display = "none";

  try {
    const res = await fetch(`${API_URL}/analysis/plot_triptan_monthly`, {
      headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` },
    });
    if (!res.ok) throw new Error(`Server returned ${res.status}`);

    const blob = await res.blob();
    if (img.dataset.objectUrl) URL.revokeObjectURL(img.dataset.objectUrl);
    img.src = URL.createObjectURL(blob);
    img.dataset.objectUrl = img.src;
    img.style.display = "";
    if (statusEl) statusEl.textContent = "";
  } catch (err) {
    console.error("fetchTriptanMonthlyPlot failed:", err);
    if (statusEl) statusEl.textContent = `Could not load plot: ${err.message}`;
  }
}

async function fetchCheckinTrendsPlot() {
  const statusEl = getElement("checkin-trends-status");
  const img = getElement("checkin-trends-plot");

  if (statusEl) statusEl.textContent = "Loading…";
  if (img) img.style.display = "none";

  try {
    const res = await fetch(`${API_URL}/analysis/plot_checkin_trends`, {
      headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` },
    });
    if (!res.ok) throw new Error(`Server returned ${res.status}`);

    const blob = await res.blob();
    if (img.dataset.objectUrl) URL.revokeObjectURL(img.dataset.objectUrl);
    img.src = URL.createObjectURL(blob);
    img.dataset.objectUrl = img.src;
    img.style.display = "";
    if (statusEl) statusEl.textContent = "";
  } catch (err) {
    console.error("fetchCheckinTrendsPlot failed:", err);
    if (statusEl) statusEl.textContent = `Could not load plot: ${err.message}`;
  }
}

async function fetchSymptomCalendarPlot() {
  const statusEl = getElement("symptom-calendar-status");
  const img = getElement("symptom-calendar-plot");

  if (statusEl) statusEl.textContent = "Loading…";
  if (img) img.style.display = "none";

  try {
    const res = await fetch(
      `${API_URL}/analysis/plot_symptom_calendar?tz_offset=${new Date().getTimezoneOffset()}`, {
      headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` },
    });
    if (!res.ok) throw new Error(`Server returned ${res.status}`);

    const blob = await res.blob();
    if (img.dataset.objectUrl) URL.revokeObjectURL(img.dataset.objectUrl);
    img.src = URL.createObjectURL(blob);
    img.dataset.objectUrl = img.src;
    img.style.display = "";
    if (statusEl) statusEl.textContent = "";
  } catch (err) {
    console.error("fetchSymptomCalendarPlot failed:", err);
    if (statusEl) statusEl.textContent = `Could not load plot: ${err.message}`;
  }
}

async function fetchHeadacheForecastPlot() {
  const statusEl = getElement("headache-forecast-status");
  const img      = getElement("headache-forecast-plot");
  const daysSel  = getElement("headache-forecast-days");

  if (statusEl) statusEl.textContent = "Loading…";
  if (img) img.style.display = "none";

  const params = new URLSearchParams({
    days_ahead: daysSel?.value ?? "14",
    tz_offset: new Date().getTimezoneOffset(),
  });

  try {
    const res = await fetch(`${API_URL}/analysis/plot_headache_forecast?${params}`, {
      headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` },
    });
    if (!res.ok) throw new Error(`Server returned ${res.status}`);

    const blob = await res.blob();
    if (img.dataset.objectUrl) URL.revokeObjectURL(img.dataset.objectUrl);
    img.src = URL.createObjectURL(blob);
    img.dataset.objectUrl = img.src;
    img.style.display = "";
    if (statusEl) statusEl.textContent = "";
  } catch (err) {
    console.error("fetchHeadacheForecastPlot failed:", err);
    if (statusEl) statusEl.textContent = `Could not load plot: ${err.message}`;
  }
}

document.getElementById("headache-forecast-days")
  ?.addEventListener("change", fetchHeadacheForecastPlot);

// ── Medication change ────────────────────────────────────
let medChangeReady = false;

async function initMedicationChangePanel() {
  const changeSel = getElement("medchange-change");
  const typeSel   = getElement("medchange-type");
  const targetSel = getElement("medchange-target");
  const windowSel = getElement("medchange-window");
  const statusEl  = getElement("medication-change-status");
  if (!changeSel || !targetSel) return;

  if (!medChangeReady) {
    const token = localStorage.getItem("access_token");
    const tz = new Date().getTimezoneOffset();

    // Only offer dose changes that actually exist — a medication with a single
    // unchanged regimen has nothing to compare.
    try {
      const res = await fetch(`${API_URL}/analysis/medication_changes?tz_offset=${tz}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`Server returned ${res.status}`);
      const meds = await res.json();

      changeSel.innerHTML = "";
      meds.forEach(m => m.changes.forEach(c => {
        const opt = document.createElement("option");
        opt.value = JSON.stringify({ medication: m.medication, date: c.date });
        opt.textContent = `${m.medication}: ${c.label}`;
        changeSel.appendChild(opt);
      }));

      if (!changeSel.options.length) {
        if (statusEl) {
          statusEl.textContent =
            "No dose changes recorded yet. Add a second regimen with a different " +
            "dose to compare before and after.";
        }
        return;
      }
    } catch (err) {
      if (statusEl) statusEl.textContent = `Could not load dose changes: ${err.message}`;
      return;
    }

    // populateNameSelect is scoped to the time-series setup function, so fill
    // this one from the module-level caches instead.
    const fillTargets = () => {
      const items = typeSel.value === "symptom" ? cachedSymptoms : cachedAllergens;
      const key = typeSel.value === "symptom" ? "symptom_name" : "allergen_name";
      targetSel.innerHTML = "";
      (items || []).forEach(item =>
        targetSel.appendChild(new Option(item[key], item[key])));
    };

    fillTargets();
    typeSel?.addEventListener("change", () => {
      fillTargets();
      fetchMedicationChangePlot();
    });
    [changeSel, targetSel, windowSel].forEach(el =>
      el?.addEventListener("change", fetchMedicationChangePlot));

    medChangeReady = true;
  }

  await fetchMedicationChangePlot();
}

async function fetchMedicationChangePlot() {
  const changeSel = getElement("medchange-change");
  const typeSel   = getElement("medchange-type");
  const targetSel = getElement("medchange-target");
  const windowSel = getElement("medchange-window");
  const statusEl  = getElement("medication-change-status");
  const img       = getElement("medication-change-plot");

  const choice = changeSel?.value;
  const target = targetSel?.value;
  if (!choice || !target) return;

  const { medication, date } = JSON.parse(choice);
  const params = new URLSearchParams({
    medication,
    change_date: date,
    target_type: typeSel?.value || "allergen",
    target,
    tz_offset: new Date().getTimezoneOffset(),
  });
  if (windowSel?.value) params.set("window_days", windowSel.value);

  if (statusEl) statusEl.textContent = "Running comparison…";
  if (img) img.style.display = "none";

  try {
    const res = await fetch(`${API_URL}/analysis/plot_medication_change?${params}`, {
      headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` },
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Server returned ${res.status}`);
    }

    const blob = await res.blob();
    if (img.dataset.objectUrl) URL.revokeObjectURL(img.dataset.objectUrl);
    img.src = URL.createObjectURL(blob);
    img.dataset.objectUrl = img.src;
    img.style.display = "";
    if (statusEl) statusEl.textContent = "";
  } catch (err) {
    console.error("fetchMedicationChangePlot failed:", err);
    if (statusEl) statusEl.textContent = err.message;
  }
}

// =========================================================
// Analysis tab load
// =========================================================
function loadAnalysisTab() {
  fetchAnalysisStats({ force: true }).catch(err => {
    console.error("Analysis refresh failed:", err);
  });

  if (currentUser?.user_id === 4) {
    document.querySelectorAll(".user4-only").forEach(el => el.style.display = "");
  }

  const analysisSelect = getElement("analysis-select");
  if (analysisSelect && !analysisSelect.value) {
    const defaultPanel = currentUser?.user_id === 4 ? "time-series" : "allergen-importance";
    analysisSelect.value = defaultPanel;
    showAnalysisPanel(defaultPanel);
  }
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

      if (target === "analysis") loadAnalysisTab();
      if (target === "medication") loadMedicationsTab();
      if (target === "checkin") setupCheckinTab();
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
// Recent logs – cell builder helper
// =========================================================

function buildLogCell(displayText, inputEl) {
  const td = document.createElement("td");
  td.className = "log-cell";

  const span = document.createElement("span");
  span.className = "cell-display";
  span.textContent = displayText;

  inputEl.className = "cell-input";
  inputEl.hidden = true;

  td.appendChild(span);
  td.appendChild(inputEl);

  td.addEventListener("click", () => {
    span.hidden = true;
    inputEl.hidden = false;
    inputEl.focus();
  });

  return td;
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

  const table = document.createElement("table");
  table.className = "logs-table";
  table.innerHTML = `<thead><tr><th>Allergen</th><th>Date &amp; time</th><th>Amount</th></tr></thead>`;
  const tbody = document.createElement("tbody");
  table.appendChild(tbody);

  logs.forEach(log => {
    const orig = {
      allergen_id: log.allergen_id,
      date_time: log.date_time,
      quantity: log.quantity,
      unit_id: log.unit_id,
    };

    // Allergen select
    const allergenSel = document.createElement("select");
    allergens.forEach(a => allergenSel.appendChild(new Option(a.allergen_name, a.allergen_id, false, a.allergen_id === log.allergen_id)));

    // Date input
    const dateInp = document.createElement("input");
    dateInp.type = "datetime-local";
    dateInp.value = isoToDateTimeLocal(log.date_time);

    // Amount cell: qty + unit side-by-side when editing
    const amountTd = document.createElement("td");
    amountTd.className = "log-cell";

    const amountSpan = document.createElement("span");
    amountSpan.className = "cell-display";
    const qtyStr = log.quantity != null ? String(log.quantity) : "";
    const unitName = units.find(u => u.unit_id === log.unit_id)?.unit_name ?? "";
    amountSpan.textContent = qtyStr ? `${qtyStr}${unitName ? " " + unitName : ""}` : "—";

    const amountWrap = document.createElement("div");
    amountWrap.className = "cell-amount-inputs";
    amountWrap.hidden = true;

    const qtyInp = document.createElement("input");
    qtyInp.type = "number";
    qtyInp.step = "any";
    qtyInp.className = "cell-input cell-qty";
    qtyInp.value = log.quantity ?? "";

    const unitSel = document.createElement("select");
    unitSel.className = "cell-input cell-unit";
    unitSel.appendChild(new Option("—", ""));
    units.forEach(u => unitSel.appendChild(new Option(u.unit_name, u.unit_id, false, u.unit_id === log.unit_id)));

    amountWrap.appendChild(qtyInp);
    amountWrap.appendChild(unitSel);
    amountTd.appendChild(amountSpan);
    amountTd.appendChild(amountWrap);
    amountTd.addEventListener("click", () => {
      amountSpan.hidden = true;
      amountWrap.hidden = false;
      qtyInp.focus();
    });

    const allergenName = allergens.find(a => a.allergen_id === log.allergen_id)?.allergen_name ?? "";
    const allergenTd = buildLogCell(allergenName, allergenSel);
    const dateTd = buildLogCell(formatLogDate(log.date_time), dateInp);

    const tr = document.createElement("tr");
    tr.className = "log-row";
    tr.dataset.dirty = "false";
    tr.appendChild(allergenTd);
    tr.appendChild(dateTd);
    tr.appendChild(amountTd);
    tbody.appendChild(tr);

    const allInputs = [allergenSel, dateInp, qtyInp, unitSel];
    allInputs.forEach(inp => {
      inp.addEventListener("input", () => { tr.dataset.dirty = "true"; });
      inp.addEventListener("change", () => { tr.dataset.dirty = "true"; });
      inp.addEventListener("keydown", e => {
        if (e.key === "Enter") { e.preventDefault(); inp.blur(); }
        if (e.key === "Escape") {
          allergenSel.value = orig.allergen_id;
          dateInp.value = isoToDateTimeLocal(orig.date_time);
          qtyInp.value = orig.quantity ?? "";
          unitSel.value = orig.unit_id ?? "";
          tr.dataset.dirty = "false";
          closeAllergenCells();
        }
      });
    });

    function closeAllergenCells() {
      allergenTd.querySelector(".cell-display").hidden = false;
      allergenSel.hidden = true;
      dateTd.querySelector(".cell-display").hidden = false;
      dateInp.hidden = true;
      amountSpan.hidden = false;
      amountWrap.hidden = true;
    }

    tr.addEventListener("focusout", () => {
      setTimeout(async () => {
        if (tr.contains(document.activeElement)) return;
        if (tr.dataset.dirty !== "true") return;
        tr.dataset.dirty = "false";

        const allergenId = Number(allergenSel.value);
        const dateTime = new Date(dateInp.value).toISOString();
        const qty = qtyInp.value !== "" ? Number(qtyInp.value) : null;
        const unitId = Number(unitSel.value) || null;

        tr.classList.add("log-row--saving");
        try {
          await updateAllergenLog(log.allergen_log_id, { allergen_id: allergenId, date_time: dateTime, quantity: qty, unit_id: unitId });

          allergenTd.querySelector(".cell-display").textContent = allergens.find(a => a.allergen_id === allergenId)?.allergen_name ?? "";
          dateTd.querySelector(".cell-display").textContent = formatLogDate(dateTime);
          const newQtyStr = qty != null ? String(qty) : "";
          const newUnitName = units.find(u => u.unit_id === unitId)?.unit_name ?? "";
          amountSpan.textContent = newQtyStr ? `${newQtyStr}${newUnitName ? " " + newUnitName : ""}` : "—";

          Object.assign(orig, { allergen_id: allergenId, date_time: dateTime, quantity: qty, unit_id: unitId });
          closeAllergenCells();
          tr.classList.remove("log-row--saving");
          tr.classList.add("log-row--saved");
          setTimeout(() => tr.classList.remove("log-row--saved"), 1000);
        } catch (err) {
          allergenSel.value = orig.allergen_id;
          dateInp.value = isoToDateTimeLocal(orig.date_time);
          qtyInp.value = orig.quantity ?? "";
          unitSel.value = orig.unit_id ?? "";
          closeAllergenCells();
          tr.classList.remove("log-row--saving");
          tr.classList.add("log-row--error");
          setTimeout(() => tr.classList.remove("log-row--error"), 2000);
          console.error("Failed to save allergen log:", err);
        }
      }, 0);
    });
  });

  container.innerHTML = "";
  container.appendChild(table);
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

  const table = document.createElement("table");
  table.className = "logs-table";
  table.innerHTML = `<thead><tr><th>Symptom</th><th>Date &amp; time</th><th>Intensity</th></tr></thead>`;
  const tbody = document.createElement("tbody");
  table.appendChild(tbody);

  logs.forEach(log => {
    const orig = { symptom_id: log.symptom_id, date_time: log.date_time, intensity: log.intensity };

    const symptomSel = document.createElement("select");
    symptoms.forEach(s => symptomSel.appendChild(new Option(s.symptom_name, s.symptom_id, false, s.symptom_id === log.symptom_id)));

    const dateInp = document.createElement("input");
    dateInp.type = "datetime-local";
    dateInp.value = isoToDateTimeLocal(log.date_time);

    const intensitySel = document.createElement("select");
    INTENSITY_LABELS.forEach((label, val) => intensitySel.appendChild(new Option(label, val, false, val === log.intensity)));

    const symptomName = symptoms.find(s => s.symptom_id === log.symptom_id)?.symptom_name ?? "";
    const symptomTd = buildLogCell(symptomName, symptomSel);
    const dateTd = buildLogCell(formatLogDate(log.date_time), dateInp);
    const intensityTd = buildLogCell(INTENSITY_LABELS[log.intensity] ?? "—", intensitySel);

    const tr = document.createElement("tr");
    tr.className = "log-row";
    tr.dataset.dirty = "false";
    tr.appendChild(symptomTd);
    tr.appendChild(dateTd);
    tr.appendChild(intensityTd);
    tbody.appendChild(tr);

    function closeSymptomCells() {
      [symptomTd, dateTd, intensityTd].forEach(td => {
        td.querySelector(".cell-display").hidden = false;
        td.querySelector(".cell-input").hidden = true;
      });
    }

    [symptomSel, dateInp, intensitySel].forEach(inp => {
      inp.addEventListener("input", () => { tr.dataset.dirty = "true"; });
      inp.addEventListener("change", () => { tr.dataset.dirty = "true"; });
      inp.addEventListener("keydown", e => {
        if (e.key === "Enter") { e.preventDefault(); inp.blur(); }
        if (e.key === "Escape") {
          symptomSel.value = orig.symptom_id;
          dateInp.value = isoToDateTimeLocal(orig.date_time);
          intensitySel.value = orig.intensity;
          tr.dataset.dirty = "false";
          closeSymptomCells();
        }
      });
    });

    tr.addEventListener("focusout", () => {
      setTimeout(async () => {
        if (tr.contains(document.activeElement)) return;
        if (tr.dataset.dirty !== "true") return;
        tr.dataset.dirty = "false";

        const symptomId = Number(symptomSel.value);
        const dateTime = new Date(dateInp.value).toISOString();
        const intensity = Number(intensitySel.value);

        tr.classList.add("log-row--saving");
        try {
          await updateSymptomLog(log.symptom_log_id, { symptom_id: symptomId, date_time: dateTime, intensity });

          symptomTd.querySelector(".cell-display").textContent = symptoms.find(s => s.symptom_id === symptomId)?.symptom_name ?? "";
          dateTd.querySelector(".cell-display").textContent = formatLogDate(dateTime);
          intensityTd.querySelector(".cell-display").textContent = INTENSITY_LABELS[intensity];

          Object.assign(orig, { symptom_id: symptomId, date_time: dateTime, intensity });
          closeSymptomCells();
          tr.classList.remove("log-row--saving");
          tr.classList.add("log-row--saved");
          setTimeout(() => tr.classList.remove("log-row--saved"), 1000);
        } catch (err) {
          symptomSel.value = orig.symptom_id;
          dateInp.value = isoToDateTimeLocal(orig.date_time);
          intensitySel.value = orig.intensity;
          closeSymptomCells();
          tr.classList.remove("log-row--saving");
          tr.classList.add("log-row--error");
          setTimeout(() => tr.classList.remove("log-row--error"), 2000);
          console.error("Failed to save symptom log:", err);
        }
      }, 0);
    });
  });

  container.innerHTML = "";
  container.appendChild(table);
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

    currentUser = user;

    const userEmailEl = getElement("user-email");
    if (userEmailEl) userEmailEl.textContent = user.email;

    if (currentUser.user_id === 4) {
      await loadUserCountBadge();
    }

    // Set up UI components
    setupLogout();
    setupTraining();
    setupDefaults();
    setupTabs();

    try {
      const [units, allergens, recentAllergens, symptoms, recentSymptoms, medications] = await Promise.all([
        fetchUnits(),
        fetchAllergens(),
        fetchRecentAllergens(10),
        fetchSymptoms(),
        fetchRecentSymptoms(10),
        fetchMedList().catch(() => []),
      ]);

      cachedAllergens = allergens || [];
      cachedSymptoms = symptoms || [];
      cachedUnits = units || [];
      cachedMedications = medications || [];

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
    setupDeeperAnalysis();
    setupTimeSeries();
    setupMedicationsTab();

    // Initialize captions
    initializeCaptions();

    const aiBtn = getElement("ai-summary-btn");
    if (aiBtn) aiBtn.addEventListener("click", fetchAISummary);

    setupChat();
    setupDocumentsTab();
    setupCheckinTab();

    console.log("✅ init() completed successfully");

  } catch (err) {
    console.error("❌ init() failed:", err);
    localStorage.removeItem("access_token");
    window.location.href = "index.html";
  }
}

// =========================================================
// AI Chat
// =========================================================

function formatAICost(inputTokens, outputTokens) {
  if (inputTokens == null || outputTokens == null) return null;
  const cost = (inputTokens / 1e6 * 1.00) + (outputTokens / 1e6 * 5.00);
  return `~$${cost.toFixed(6)}  (${inputTokens.toLocaleString()} in / ${outputTokens.toLocaleString()} out tokens)`;
}

let chatHistory = [];

function appendChatMessage(role, text) {
  const container = getElement("chat-messages");
  if (!container) return;

  const placeholder = getElement("chat-placeholder");
  if (placeholder) placeholder.style.display = "none";

  const bubble = document.createElement("div");
  bubble.style.cssText = `
    max-width: 85%;
    padding: 0.55rem 0.85rem;
    border-radius: 10px;
    font-size: 0.92em;
    line-height: 1.5;
    white-space: pre-wrap;
    word-break: break-word;
    ${role === "user"
      ? "align-self: flex-end; background: #3b82f6; color: #fff;"
      : "align-self: flex-start; background: #f3f4f6; color: #111827;"}
  `;
  bubble.textContent = text;
  container.appendChild(bubble);
  container.scrollTop = container.scrollHeight;
}

function appendChatTable(table) {
  const container = getElement("chat-messages");
  if (!container || !table?.columns?.length) return;

  const wrap = document.createElement("div");
  wrap.style.cssText = `
    align-self: flex-start; max-width: 100%; width: 100%;
    border: 1px solid #e5e7eb; border-radius: 10px; overflow: hidden;
    background: #fff; font-size: 0.82em;
  `;

  if (table.title) {
    const cap = document.createElement("div");
    cap.style.cssText =
      "padding:0.45rem 0.7rem;background:#f9fafb;border-bottom:1px solid #e5e7eb;" +
      "color:#374151;font-weight:600;";
    cap.textContent = table.title;
    wrap.appendChild(cap);
  }

  // Wide tables scroll inside their own box rather than stretching the chat.
  const scroller = document.createElement("div");
  scroller.style.cssText = "overflow-x:auto;max-height:320px;overflow-y:auto;";

  const t = document.createElement("table");
  t.style.cssText = "border-collapse:collapse;width:100%;";

  const thead = document.createElement("thead");
  const hrow = document.createElement("tr");
  table.columns.forEach(col => {
    const th = document.createElement("th");
    th.textContent = String(col).replace(/_/g, " ");
    th.style.cssText =
      "text-align:left;padding:0.4rem 0.7rem;background:#f3f4f6;color:#374151;" +
      "position:sticky;top:0;white-space:nowrap;";
    hrow.appendChild(th);
  });
  thead.appendChild(hrow);
  t.appendChild(thead);

  const tbody = document.createElement("tbody");
  (table.rows || []).forEach((row, i) => {
    const tr = document.createElement("tr");
    if (i % 2) tr.style.background = "#fafafa";
    row.forEach(cell => {
      const td = document.createElement("td");
      // textContent, never innerHTML — these values come from logged data.
      td.textContent = cell === null || cell === undefined ? "—" : String(cell);
      td.style.cssText =
        "padding:0.35rem 0.7rem;border-top:1px solid #f3f4f6;white-space:nowrap;";
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
  t.appendChild(tbody);
  scroller.appendChild(t);
  wrap.appendChild(scroller);

  const foot = document.createElement("div");
  foot.style.cssText =
    "padding:0.35rem 0.7rem;background:#f9fafb;border-top:1px solid #e5e7eb;" +
    "color:#6b7280;font-size:0.92em;display:flex;justify-content:space-between;gap:0.5rem;";
  const count = document.createElement("span");
  count.textContent = table.truncated
    ? `${table.row_count} rows shown — more matched`
    : `${table.row_count} row${table.row_count === 1 ? "" : "s"}`;
  const copy = document.createElement("button");
  copy.type = "button";
  copy.textContent = "Copy CSV";
  copy.style.cssText =
    "background:none;border:none;color:#2563eb;cursor:pointer;font-size:1em;padding:0;";
  copy.addEventListener("click", () => {
    const esc = v => {
      const s = v === null || v === undefined ? "" : String(v);
      return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
    };
    const csv = [table.columns.map(esc).join(",")]
      .concat((table.rows || []).map(r => r.map(esc).join(",")))
      .join("\n");
    navigator.clipboard.writeText(csv).then(
      () => { copy.textContent = "Copied"; setTimeout(() => (copy.textContent = "Copy CSV"), 1500); },
      () => { copy.textContent = "Copy failed"; }
    );
  });
  foot.append(count, copy);
  wrap.appendChild(foot);

  container.appendChild(wrap);
  container.scrollTop = container.scrollHeight;
}

async function sendChatMessage() {
  const input = getElement("chat-input");
  const sendBtn = getElement("chat-send-btn");
  const text = input?.value.trim();
  if (!text) return;

  input.value = "";
  appendChatMessage("user", text);
  chatHistory.push({ role: "user", content: text });

  if (sendBtn) sendBtn.disabled = true;

  // Typing indicator
  const container = getElement("chat-messages");
  const typingEl = document.createElement("div");
  typingEl.id = "chat-typing";
  typingEl.style.cssText = "align-self: flex-start; color: #9ca3af; font-size: 0.85em;";
  typingEl.textContent = "Thinking…";
  if (container) container.appendChild(typingEl);
  if (container) container.scrollTop = container.scrollHeight;

  try {
    const res = await fetch(`${API_URL}/analysis/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${localStorage.getItem("access_token")}`,
      },
      body: JSON.stringify({
        messages: chatHistory,
        tz_offset: new Date().getTimezoneOffset(),
      }),
    });

    typingEl.remove();

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || res.status);
    }

    const data = await res.json();
    chatHistory.push({ role: "assistant", content: data.reply });
    appendChatMessage("assistant", data.reply);

    // Show the rows the AI actually read, so its summary can be checked
    // against the underlying records rather than taken on trust.
    if (data.table) appendChatTable(data.table);

    // The chat runs two models at different prices, so the server computes the
    // cost — token counts alone can't be priced client-side any more.
    const costLabel = data.cost_usd != null
      ? `~$${data.cost_usd.toFixed(6)}  (${data.input_tokens.toLocaleString()} in / ` +
        `${data.output_tokens.toLocaleString()} out tokens)`
      : formatAICost(data.input_tokens, data.output_tokens);
    if (costLabel && container) {
      const costEl = document.createElement("div");
      costEl.style.cssText = "align-self: flex-start; color: #9ca3af; font-size: 0.75em; margin-top: -0.3rem; padding-left: 0.2rem;";
      costEl.textContent = costLabel;
      container.appendChild(costEl);
      container.scrollTop = container.scrollHeight;
    }
  } catch (err) {
    typingEl.remove();
    console.error("chat failed:", err);
    appendChatMessage("assistant", `Sorry, something went wrong: ${err.message}`);
    // Remove the user message from history so they can retry
    chatHistory.pop();
  } finally {
    if (sendBtn) sendBtn.disabled = false;
    input?.focus();
  }
}

function setupChat() {
  const sendBtn = getElement("chat-send-btn");
  const clearBtn = getElement("chat-clear-btn");
  const input = getElement("chat-input");

  if (sendBtn) sendBtn.addEventListener("click", sendChatMessage);

  if (input) {
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendChatMessage();
      }
    });
  }

  if (clearBtn) {
    clearBtn.addEventListener("click", () => {
      chatHistory = [];
      const container = getElement("chat-messages");
      if (container) {
        container.innerHTML = '<p id="chat-placeholder" style="color: #9ca3af; font-size: 0.9em; margin: 0;">Your conversation will appear here.</p>';
      }
    });
  }
}

// =========================================================
// Daily Check-in
// =========================================================

const CHECKIN_VARS_GENERAL = [
  { key: "mood",    label: "Mood",             options: ["Poor", "Okay", "Good"], morningOnly: false },
  { key: "sleep",   label: "Sleep last night", options: ["Poor", "Okay", "Good"], morningOnly: true  },
  { key: "fatigue", label: "Fatigue",           options: ["None", "Mild", "Bad"],  morningOnly: false },
  { key: "gut",     label: "Gut / Digestion",   options: ["None", "Mild", "Bad"],  morningOnly: false },
  { key: "stress",  label: "Stress",            options: ["None", "Mild", "Bad"],  morningOnly: false },
];

const CHECKIN_VARS_EXTRA = [
  { key: "headache",           label: "Headache",           options: ["None", "Mild", "Bad"],             morningOnly: false },
  { key: "headache_overnight", label: "Headache overnight", options: ["None", "Mild", "Bad"],             morningOnly: true  },
  { key: "brain_fog",          label: "Brain fog",          options: ["None", "Mild", "Bad"],             morningOnly: false },
  { key: "tinnitus",           label: "Tinnitus",           options: ["None", "Mild", "Bad"],             morningOnly: false },
  { key: "visual_disturbance", label: "Visual disturbance", options: ["None", "Mild", "Bad"],             morningOnly: false },
  { key: "training",           label: "Training",           options: ["None", "Partial", "Full"],         morningOnly: true  },
  { key: "virus",              label: "Virus / Illness",    options: ["None", "Mild", "Bad"],             morningOnly: false },
];

let checkinPeriod = new Date().getHours() < 13 ? "morning" : "evening";
let checkinValues = {};
let checkinFormBuilt = false;
let checkinExistsOnServer = false;

function getCheckinVars() {
  return currentUser?.user_id === 4
    ? [...CHECKIN_VARS_GENERAL, ...CHECKIN_VARS_EXTRA]
    : CHECKIN_VARS_GENERAL;
}

function renderCheckinVarRows() {
  const varsContainer = getElement("checkin-vars");
  if (!varsContainer) return;

  varsContainer.innerHTML = "";
  getCheckinVars().forEach(v => {
    if (v.morningOnly && checkinPeriod === "evening") return;

    const row = document.createElement("div");
    row.className = "checkin-row";

    const label = document.createElement("span");
    label.className = "checkin-label";
    label.textContent = v.label;

    const group = document.createElement("div");
    group.className = "checkin-btn-group";

    v.options.forEach((optLabel, i) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.dataset.val = i;
      btn.textContent = optLabel;
      if (checkinValues[v.key] === i) btn.classList.add("selected");
      btn.addEventListener("click", () => {
        group.querySelectorAll("button").forEach(b => b.classList.remove("selected"));
        btn.classList.add("selected");
        checkinValues[v.key] = i;
      });
      group.appendChild(btn);
    });

    row.appendChild(label);
    row.appendChild(group);
    varsContainer.appendChild(row);
  });
}

function buildCheckinForm() {
  const container = getElement("checkin-content");
  if (!container) return;

  const today = localDateTimeForInput().slice(0, 10);

  container.innerHTML = `
    <div class="checkin-period-toggle">
      <button type="button" class="checkin-period-btn ${checkinPeriod === "morning" ? "active" : ""}" data-period="morning">Morning</button>
      <button type="button" class="checkin-period-btn ${checkinPeriod === "evening" ? "active" : ""}" data-period="evening">Evening</button>
    </div>

    <div class="form-row" style="margin-bottom:1rem;">
      <label for="checkin-date">Date</label>
      <input type="date" id="checkin-date" value="${today}" style="width:auto;" />
    </div>

    <p class="checkin-section-label">How are you feeling?</p>
    <div id="checkin-vars"></div>

    <div style="margin-top:1.25rem; display:flex; align-items:center; gap:1rem;">
      <button type="button" id="checkin-submit-btn" class="primary" style="width:auto; padding:0.5rem 1.5rem;">Save Check-in</button>
      <span id="checkin-status" style="font-size:0.9em; color:#6b7280;"></span>
    </div>
  `;

  renderCheckinVarRows();

  container.querySelectorAll(".checkin-period-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      checkinPeriod = btn.dataset.period;
      container.querySelectorAll(".checkin-period-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      checkinValues = {};
      renderCheckinVarRows();
      loadCheckinForDate();
    });
  });

  getElement("checkin-date")?.addEventListener("change", () => {
    checkinValues = {};
    renderCheckinVarRows();
    loadCheckinForDate();
  });

  getElement("checkin-submit-btn")?.addEventListener("click", submitCheckin);

  checkinFormBuilt = true;
}

async function loadCheckinForDate() {
  const date = getElement("checkin-date")?.value;
  if (!date) return;

  checkinExistsOnServer = false;
  try {
    const res = await fetch(
      `${API_URL}/checkin?date=${date}&period=${checkinPeriod}`,
      { headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` } }
    );
    if (!res.ok) return;
    const data = await res.json();
    if (!data.exists) return;

    checkinExistsOnServer = true;
    checkinValues = {};
    getCheckinVars().forEach(v => {
      if (data[v.key] != null) checkinValues[v.key] = data[v.key];
    });
    renderCheckinVarRows();
  } catch (err) {
    console.error("loadCheckinForDate failed:", err);
  }
}

async function submitCheckin() {
  const date = getElement("checkin-date")?.value;
  const status = getElement("checkin-status");
  const submitBtn = getElement("checkin-submit-btn");
  if (!date) return;

  // Disable immediately to prevent double-submit
  if (submitBtn) submitBtn.disabled = true;

  // Warn if a check-in already exists (use cached flag — no extra request needed)
  if (checkinExistsOnServer) {
    const ok = confirm(`You already have a ${checkinPeriod} check-in for ${date}. Update it?`);
    if (!ok) {
      if (submitBtn) submitBtn.disabled = false;
      return;
    }
  }

  // Build a local datetime for the check-in (8am morning, 8pm evening) so the
  // plot aligns with allergen/symptom events on the same local day.
  const hour = checkinPeriod === "morning" ? 8 : 20;
  const localDt = new Date(`${date}T${String(hour).padStart(2, "0")}:00:00`);

  const payload = {
    checkin_date: date,
    period: checkinPeriod,
    checkin_datetime: localDt.toISOString(),
  };
  getCheckinVars().forEach(v => {
    if (v.morningOnly && checkinPeriod === "evening") return;
    if (checkinValues[v.key] !== undefined) payload[v.key] = checkinValues[v.key];
  });

  if (status) status.textContent = "Saving…";

  try {
    const res = await fetch(`${API_URL}/checkin`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${localStorage.getItem("access_token")}`,
      },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(await res.text());
    checkinExistsOnServer = true;
    if (status) status.textContent = "Saved!";
    setTimeout(() => { if (status) status.textContent = ""; }, 2500);
  } catch (err) {
    console.error("submitCheckin failed:", err);
    if (status) status.textContent = `Error: ${err.message}`;
  } finally {
    if (submitBtn) submitBtn.disabled = false;
  }
}

function setupCheckinTab() {
  if (!checkinFormBuilt) buildCheckinForm();
  loadCheckinForDate();
}

// =========================================================
// Documents tab
// =========================================================

async function fetchDocumentList() {
  const container = getElement("doc-list");
  if (!container) return;

  try {
    const res = await fetch(`${API_URL}/documents`, {
      headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` },
    });
    if (!res.ok) throw new Error(`${res.status}`);
    const docs = await res.json();

    if (!docs.length) {
      container.innerHTML = '<p class="subtle">No documents uploaded yet.</p>';
      return;
    }

    container.innerHTML = docs.map(doc => `
      <div class="log-item" data-doc-id="${doc.document_id}" style="display:flex; justify-content:space-between; align-items:center; padding:0.6rem 0; border-bottom:1px solid #e5e7eb;">
        <div>
          <strong>${doc.filename}</strong>
          ${doc.description ? `<span class="subtle" style="margin-left:0.5rem;">— ${doc.description}</span>` : ""}
          <br>
          <span class="subtle" style="font-size:0.8em;">
            Uploaded ${new Date(doc.uploaded_at).toLocaleDateString()}
            ${!doc.has_text ? " · no text extracted" : doc.text_truncated ? " · <span style=\"color:#b45309\">partially read (too long)</span>" : " · text extracted"}
          </span>
        </div>
        <button class="delete-doc-btn secondary" data-doc-id="${doc.document_id}" style="padding:0.3rem 0.7rem; font-size:0.85em;">Delete</button>
      </div>
    `).join("");

    container.querySelectorAll(".delete-doc-btn").forEach(btn => {
      btn.addEventListener("click", () => deleteDocument(Number(btn.dataset.docId)));
    });
  } catch (err) {
    console.error("fetchDocumentList failed:", err);
    if (container) container.innerHTML = '<p class="subtle">Could not load documents.</p>';
  }
}

async function deleteDocument(docId) {
  if (!confirm("Delete this document? The AI will no longer reference it.")) return;
  try {
    const res = await fetch(`${API_URL}/documents/${docId}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` },
    });
    if (!res.ok) throw new Error(`${res.status}`);
    await fetchDocumentList();
  } catch (err) {
    console.error("deleteDocument failed:", err);
    alert("Could not delete document. Please try again.");
  }
}

function setupDocumentsTab() {
  const uploadBtn = getElement("doc-upload-btn");
  if (!uploadBtn) return;

  fetchDocumentList();

  uploadBtn.addEventListener("click", async () => {
    const fileInput = getElement("doc-file");
    const descInput = getElement("doc-description");
    const status = getElement("doc-upload-status");

    if (!fileInput.files.length) {
      if (status) status.textContent = "Please select a file first.";
      return;
    }

    const formData = new FormData();
    formData.append("file", fileInput.files[0]);
    if (descInput.value.trim()) formData.append("description", descInput.value.trim());

    uploadBtn.disabled = true;
    if (status) status.textContent = "Uploading…";

    try {
      const res = await fetch(`${API_URL}/documents/upload`, {
        method: "POST",
        headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` },
        body: formData,
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || res.status);
      }

      const data = await res.json();
      fileInput.value = "";
      descInput.value = "";
      if (status) {
        if (data.text_extracted === false) {
          status.textContent = "Uploaded, but text could not be extracted — the AI will not be able to read this document.";
          status.style.color = "#b45309";
        } else if (data.text_truncated) {
          status.textContent = "Uploaded, but the document is too long to read in full — only the first portion will be shown to the AI. Consider splitting it into shorter documents.";
          status.style.color = "#b45309";
        } else {
          status.textContent = "Uploaded successfully.";
          status.style.color = "";
          setTimeout(() => { if (status) status.textContent = ""; }, 3000);
        }
      }
      await fetchDocumentList();
    } catch (err) {
      console.error("upload failed:", err);
      if (status) status.textContent = `Upload failed: ${err.message}`;
    } finally {
      uploadBtn.disabled = false;
    }
  });
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

// =========================================================
// Training
//
// Deliberately thin: this is the logging surface for the data model, not the
// session runner. Everything renders with textContent rather than innerHTML,
// so a stray character in an exercise name or note cannot become markup.
// =========================================================

let trExercises = [];
let trSession = null;

function trAuth() {
  return { Authorization: `Bearer ${localStorage.getItem("access_token")}` };
}

function trEl(tag, text, cls) {
  const el = document.createElement(tag);
  if (text !== undefined && text !== null) el.textContent = String(text);
  if (cls) el.className = cls;
  return el;
}

function trSetStatus(id, msg) {
  const el = getElement(id);
  if (el) el.textContent = msg || "";
}

// A set is described by whichever fields were filled in: reps and weight for
// loaded work, seconds for a hold, a band rating on its own for band work.
function trDescribeSet(s) {
  const bits = [];
  if (s.reps) bits.push(`${s.reps} reps`);
  if (s.weight_kg) bits.push(`${s.weight_kg} kg`);
  if (s.band_kg) bits.push(`${s.band_kg} kg band`);
  if (s.hold_seconds) bits.push(`${s.hold_seconds}s hold`);
  if (s.side) bits.push(s.side);
  if (s.rpe) bits.push(`RPE ${s.rpe}`);
  if (s.pain !== null && s.pain !== undefined) bits.push(`pain ${s.pain}`);
  return bits.join(" · ");
}

async function trLoadExercises() {
  const res = await fetch(`${API_URL}/training/exercises`, { headers: trAuth() });
  if (!res.ok) throw new Error(`exercises: ${res.status}`);
  trExercises = await res.json();

  const sel = getElement("tr-exercise");
  if (!sel) return;
  sel.replaceChildren();
  // Grouped by body area, because picking the right exercise matters more
  // than picking it quickly.
  const byTarget = {};
  trExercises.forEach((e) => (byTarget[e.target || "other"] ||= []).push(e));
  Object.keys(byTarget).sort().forEach((target) => {
    const group = document.createElement("optgroup");
    group.label = target;
    byTarget[target].forEach((e) => {
      const opt = trEl("option", e.exercise_name);
      opt.value = e.exercise_id;
      group.appendChild(opt);
    });
    sel.appendChild(group);
  });
  trRenderCues();
}

function trRenderCues() {
  const box = getElement("tr-cues");
  const sel = getElement("tr-exercise");
  if (!box || !sel) return;
  box.replaceChildren();
  const ex = trExercises.find((e) => String(e.exercise_id) === sel.value);
  if (!ex) return;
  if (ex.form_cues) box.appendChild(trEl("p", ex.form_cues));
  if (ex.video_url) {
    const a = trEl("a", "Form guide →");
    a.href = ex.video_url;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    box.appendChild(a);
  }
}

function trRenderSession() {
  const bar = getElement("tr-session-bar");
  const logSection = getElement("tr-log-section");
  if (!bar) return;
  bar.replaceChildren();

  if (!trSession) {
    const btn = trEl("button", "Start session", "primary tr-big tr-block");
    btn.type = "button";
    btn.addEventListener("click", () => trStartSession());
    bar.appendChild(btn);
    // A one-line reminder of what today is, without opening the plan.
    if (trPlan) {
      const label = trPlan.kind === "strength"
        ? `Day ${trPlan.day} — ${trPlan.theme}`
        : trPlan.theme;
      bar.appendChild(trEl("p", label, "tr-today"));
    }
    if (logSection) logSection.style.display = "none";
    trRunnerVisible(false);
    return;
  }

  const when = new Date(trSession.date_time);
  bar.appendChild(trEl("p",
    `Started ${when.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })} · ${trSession.sets.length} sets logged`,
    "tr-hint"));
  const done = trEl("button", "Finish session", "secondary");
  done.type = "button";
  done.addEventListener("click", trFinishSession);
  bar.appendChild(done);
  // The runner is the way through a session; the manual form stays available
  // behind a toggle for corrections and anything off-plan.
  if (logSection) logSection.style.display = "none";
  trRunnerVisible(true);
  trRenderCurrentSets();
}

function trRenderCurrentSets() {
  const box = getElement("tr-current-sets");
  if (!box) return;
  box.replaceChildren();
  if (!trSession || !trSession.sets.length) return;
  const ul = document.createElement("ul");
  trSession.sets.forEach((s) => {
    ul.appendChild(trEl("li", `${s.exercise_name} — ${trDescribeSet(s)}`));
  });
  box.appendChild(ul);
}

async function trStartSession() {
  const res = await fetch(`${API_URL}/training/sessions`, {
    method: "POST",
    headers: { ...trAuth(), "Content-Type": "application/json" },
    body: JSON.stringify({ session_type: "strength" }),
  });
  if (!res.ok) {
    trSetStatus("tr-status", `Could not start a session (${res.status}).`);
    return;
  }
  trSession = await res.json();
  trRenderSession();
  trStartRunner();
}

function trNum(id) {
  const el = getElement(id);
  if (!el || el.value === "") return null;
  const n = Number(el.value);
  return Number.isFinite(n) ? n : null;
}

async function trAddSet() {
  if (!trSession) return;
  const sel = getElement("tr-exercise");
  const sideEl = getElement("tr-side");
  const payload = {
    exercise_id: Number(sel.value),
    // Sets are numbered per exercise within the session, so the count is of
    // this exercise only rather than of everything logged so far.
    set_number: trSession.sets.filter((s) => s.exercise_id === Number(sel.value)).length + 1,
    reps: trNum("tr-reps"),
    weight_kg: trNum("tr-weight"),
    band_kg: trNum("tr-band"),
    hold_seconds: trNum("tr-hold"),
    side: sideEl && sideEl.value ? sideEl.value : null,
    rpe: trNum("tr-rpe"),
    pain: trNum("tr-pain"),
  };

  trSetStatus("tr-status", "Saving…");
  const res = await fetch(`${API_URL}/training/sessions/${trSession.session_id}/sets`, {
    method: "POST",
    headers: { ...trAuth(), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    trSetStatus("tr-status", `Could not save that set (${res.status}).`);
    return;
  }
  trSession = await res.json();
  trSetStatus("tr-status", "Saved.");
  // Reps and load usually repeat across sets, so they are left in place;
  // pain is cleared because carrying it over would fabricate a reading.
  ["tr-pain"].forEach((id) => { const el = getElement(id); if (el) el.value = ""; });
  trRenderSession();
}

const trExpanded = new Set();

// Fields worth correcting, and the step each one moves in. Only the ones that
// were actually recorded are shown, so a hold does not sprout a weight box.
const TR_EDITABLE = [
  ["reps", "Reps", 1],
  ["weight_kg", "Weight kg", 0.25],
  ["band_kg", "Band kg", 0.5],
  ["hold_seconds", "Hold s", 1],
  ["rpe", "RPE", 1],
  ["pain", "Pain", 1],
];

async function trDeleteSession(id) {
  if (!window.confirm("Delete this whole session and every set in it?")) return;
  const res = await fetch(`${API_URL}/training/sessions/${id}`, {
    method: "DELETE", headers: trAuth(),
  });
  if (!res.ok) return;
  trExpanded.delete(id);
  await trLoadHistory();
  await trLoadPlan();       // history drives the prescription, so refresh it
}

async function trDeleteSet(setId) {
  const res = await fetch(`${API_URL}/training/sets/${setId}`, {
    method: "DELETE", headers: trAuth(),
  });
  if (!res.ok) return;
  await trLoadHistory();
  await trLoadPlan();
}

async function trSaveSet(setId, patch, statusEl) {
  statusEl.textContent = "Saving…";
  const res = await fetch(`${API_URL}/training/sets/${setId}`, {
    method: "PATCH",
    headers: { ...trAuth(), "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  statusEl.textContent = res.ok ? "Saved." : `Could not save (${res.status}).`;
  if (res.ok) {
    await trLoadHistory();
    await trLoadPlan();
  }
}

function trRenderSetRow(st, host) {
  const row = trEl("div", null, "tr-set-row");
  row.appendChild(trEl("span", st.exercise_name, "tr-set-name"));

  const inputs = {};
  const fields = trEl("div", null, "tr-set-fields");
  TR_EDITABLE.forEach(([key, label, step]) => {
    if (st[key] === null || st[key] === undefined) return;
    const wrap = trEl("label", null, "tr-set-field");
    wrap.appendChild(trEl("span", label));
    const inp = document.createElement("input");
    inp.type = "number";
    inp.step = String(step);
    inp.value = st[key];
    wrap.appendChild(inp);
    inputs[key] = inp;
    fields.appendChild(wrap);
  });
  if (st.side) {
    const wrap = trEl("label", null, "tr-set-field");
    wrap.appendChild(trEl("span", "Side"));
    const sel = document.createElement("select");
    [["left", "Left"], ["right", "Right"]].forEach(([v, l]) => {
      const o = trEl("option", l); o.value = v; sel.appendChild(o);
    });
    sel.value = st.side;
    wrap.appendChild(sel);
    inputs.side = sel;
    fields.appendChild(wrap);
  }
  row.appendChild(fields);

  const status = trEl("span", "", "tr-hint");
  const actions = trEl("div", null, "tr-set-actions");
  const save = trEl("button", "Save", "secondary");
  save.type = "button";
  save.addEventListener("click", () => {
    const patch = {};
    Object.entries(inputs).forEach(([k, el]) => {
      patch[k] = k === "side" ? el.value : (el.value === "" ? null : Number(el.value));
    });
    trSaveSet(st.set_id, patch, status);
  });
  const del = trEl("button", "Delete", "secondary");
  del.type = "button";
  del.addEventListener("click", () => trDeleteSet(st.set_id));
  actions.append(save, del, status);
  row.appendChild(actions);
  host.appendChild(row);
}

async function trLoadHistory() {
  const box = getElement("tr-history");
  if (!box) return;
  const res = await fetch(`${API_URL}/training/sessions?limit=10`, { headers: trAuth() });
  box.replaceChildren();
  if (!res.ok) {
    box.appendChild(trEl("p", `Could not load history (${res.status}).`, "tr-hint"));
    return;
  }
  const sessions = await res.json();
  if (!sessions.length) {
    box.appendChild(trEl("p", "No sessions logged yet.", "tr-hint"));
    return;
  }

  sessions.forEach((s) => {
    const d = new Date(s.date_time);
    const card = trEl("div", null, "tr-card");
    card.appendChild(trEl("p", d.toLocaleDateString(undefined,
      { weekday: "short", day: "numeric", month: "short" }), "tr-card-title"));

    const bits = [s.session_type.replace("_", " "), `${s.sets.length} sets`];
    if (s.next_day_knee !== null && s.next_day_knee !== undefined) {
      bits.push(`next-day knee ${s.next_day_knee}/10`);
    }
    card.appendChild(trEl("p", bits.join(" · "), "tr-hint"));
    if (s.notes) card.appendChild(trEl("p", s.notes, "tr-hint"));

    const open = trExpanded.has(s.session_id);
    if (!open) {
      // Collapsed: one line per exercise. Three identical sets are noise when
      // scanning back through a fortnight.
      const byExercise = new Map();
      s.sets.forEach((st) => {
        const list = byExercise.get(st.exercise_name) || [];
        list.push(st);
        byExercise.set(st.exercise_name, list);
      });
      const ul = document.createElement("ul");
      ul.className = "tr-set-list";
      byExercise.forEach((sets, name) => {
        const detail = trDescribeSet(sets[0]);
        ul.appendChild(trEl("li",
          sets.length > 1 ? `${name} — ${sets.length} x ${detail}` : `${name} — ${detail}`));
      });
      card.appendChild(ul);
    } else {
      // Expanded: every set individually, because that is the level a
      // correction happens at.
      const list = trEl("div", null, "tr-set-rows");
      s.sets.forEach((st) => trRenderSetRow(st, list));
      if (!s.sets.length) list.appendChild(trEl("p", "No sets in this session.", "tr-hint"));
      card.appendChild(list);
    }

    const actions = trEl("div", null, "tr-card-actions");
    const edit = trEl("button", open ? "Done editing" : "Edit sets", "secondary");
    edit.type = "button";
    edit.addEventListener("click", () => {
      if (open) trExpanded.delete(s.session_id);
      else trExpanded.add(s.session_id);
      trLoadHistory();
    });
    const del = trEl("button", "Delete session", "secondary");
    del.type = "button";
    del.addEventListener("click", () => trDeleteSession(s.session_id));
    actions.append(edit, del);
    card.appendChild(actions);

    box.appendChild(card);
  });
}

// The exercise catalogue is a fixed list this app ships, not something to
// choose. Asking the user to press a button called "load the starter exercise
// library" made a detail of the implementation their problem, and left a new
// account with an empty plan until they found it. It is now done on the way in,
// and is only mentioned when it actually adds something.
async function trSyncLibrary() {
  try {
    const res = await fetch(`${API_URL}/training/exercises/seed`, {
      method: "POST", headers: trAuth(),
    });
    if (!res.ok) return 0;
    const data = await res.json();
    return data.added || 0;
  } catch (err) {
    console.error("library sync failed:", err);
    return 0;   // a stale library is better than a broken tab
  }
}

function setupTraining() {
  const tab = document.querySelector('.tab[data-tab="training"]');
  if (!tab) return;

  const addBtn = getElement("tr-add-set");
  if (addBtn) addBtn.addEventListener("click", trAddSet);
  const sel = getElement("tr-exercise");
  if (sel) sel.addEventListener("change", trRenderCues);
  const ndBtn = getElement("tr-nextday-save");
  if (ndBtn) ndBtn.addEventListener("click", trSaveNextDay);
  const asBtn = getElement("tr-assess-toggle");
  if (asBtn) asBtn.addEventListener("click", trToggleAssessment);
  const planBtn = getElement("tr-plan-toggle");
  if (planBtn) planBtn.addEventListener("click", () => {
    const sec = getElement("tr-plan");
    if (sec) sec.style.display = sec.style.display === "none" ? "" : "none";
  });
  const manBtn = getElement("tr-manual-toggle");
  if (manBtn) manBtn.addEventListener("click", () => {
    const sec = getElement("tr-log-section");
    if (sec) sec.style.display = sec.style.display === "none" ? "" : "none";
  });

  // Loaded on first visit rather than at startup: most page loads never open
  // this tab, and it is two more requests against a small server.
  let loaded = false;
  tab.addEventListener("click", async () => {
    if (loaded) return;
    loaded = true;
    try {
      const added = await trSyncLibrary();
      await trLoadExercises();
      if (added) {
        trSetStatus("tr-seed-status",
          `${added} new exercise${added === 1 ? "" : "s"} added to your library.`);
      }
      trRenderSession();
      await trLoadPlan();
      await trLoadHistory();
    } catch (err) {
      console.error("training load failed:", err);
      trSetStatus("tr-status", "Could not load training data.");
      loaded = false;   // let a later click retry
    }
  });
}

// =========================================================
// Training: today's prescription
//
// The plan comes from the server's rules, not from this file. The knee
// back-off in particular has to be decided in one place, so the UI only
// renders what it is told and never computes a load of its own.
// =========================================================

let trPlan = null;

function trRenderPlan() {
  const box = getElement("tr-plan");
  if (!box) return;
  box.replaceChildren();
  if (!trPlan) {
    box.appendChild(trEl("p", "Could not load today's plan."));
    return;
  }

  const ph = trPlan.phase;
  const card = trEl("div", null, "tr-card");
  const heading = trPlan.kind === "strength"
    ? `Day ${trPlan.day} — ${trPlan.theme}`
    : trPlan.theme;
  card.appendChild(trEl("p", heading, "tr-card-title"));
  card.appendChild(trEl("p", trPlan.kind_why, "tr-hint"));
  card.appendChild(trEl("p", `Phase ${ph.phase} — ${ph.label}. ${ph.aim}`, "tr-body"));
  card.appendChild(trEl("p", `${ph.sessions_done} strength sessions logged · next phase: ${ph.to_advance}`, "tr-hint"));
  box.appendChild(card);

  // The rest rule is a default, not a cage — some days you feel like more.
  const swap = trEl("button",
    trPlan.kind === "strength" ? "Make today practice only" : "Do a strength session anyway",
    "secondary");
  swap.type = "button";
  swap.style.width = "auto";
  swap.addEventListener("click", async () => {
    trKindOverride = trPlan.kind === "strength" ? "practice" : "strength";
    await trLoadPlan();
  });
  box.appendChild(swap);

  // The knee verdict is the most important line here, so it is called out
  // rather than left to be inferred from the numbers.
  const knee = trEl("p", trPlan.knee.reason,
    trPlan.knee.action === "progress" ? "tr-hint" : "tr-warn");
  box.appendChild(knee);

  trPlan.notes.forEach((n) => box.appendChild(trEl("p", n, "tr-warn")));

  const ol = document.createElement("ol");
  ol.className = "tr-plan-list";
  trPlan.blocks.forEach((b) => {
    const li = document.createElement("li");
    li.appendChild(trEl("span", `${b.exercise} — ${b.prescription}`, "tr-plan-name"));
    if (b.notice) li.appendChild(trEl("div", b.notice, "tr-warn"));
    if (b.why) li.appendChild(trEl("div", b.why, "tr-hint"));
    if (b.form_cues) li.appendChild(trEl("div", b.form_cues, "tr-hint"));
    if (b.video_url) {
      const a = trEl("a", "Form guide →");
      a.href = b.video_url;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      li.appendChild(a);
    }
    ol.appendChild(li);
  });
  box.appendChild(ol);

  // Only ask for the score when the server says one is outstanding.
  const nd = getElement("tr-nextday-section");
  if (nd) nd.style.display = trPlan.knee.awaiting_next_day ? "" : "none";
}

let trKindOverride = null;

async function trLoadPlan() {
  const tz = new Date().getTimezoneOffset();
  const q = `tz_offset=${tz}` + (trKindOverride ? `&kind=${trKindOverride}` : "");
  const res = await fetch(`${API_URL}/training/today?${q}`, { headers: trAuth() });
  trPlan = res.ok ? await res.json() : null;
  trRenderPlan();
}

async function trSaveNextDay() {
  if (!trPlan || !trPlan.knee.awaiting_next_day) return;
  const val = trNum("tr-nextday");
  if (val === null) {
    trSetStatus("tr-nextday-status", "Enter a number from 0 to 10.");
    return;
  }
  trSetStatus("tr-nextday-status", "Saving…");
  const res = await fetch(`${API_URL}/training/sessions/${trPlan.knee.awaiting_next_day}`, {
    method: "PATCH",
    headers: { ...trAuth(), "Content-Type": "application/json" },
    body: JSON.stringify({ next_day_knee: val }),
  });
  if (!res.ok) {
    trSetStatus("tr-nextday-status", `Could not save (${res.status}).`);
    return;
  }
  trSetStatus("tr-nextday-status", "Saved — today's plan updated.");
  await trLoadPlan();
  await trLoadHistory();
}

async function trToggleAssessment() {
  const box = getElement("tr-assess");
  if (!box) return;
  if (box.style.display !== "none") {
    box.style.display = "none";
    return;
  }
  box.style.display = "";
  box.replaceChildren(trEl("p", "Loading…", "logs-loading"));

  const res = await fetch(`${API_URL}/training/assessment`, { headers: trAuth() });
  if (!res.ok) {
    box.replaceChildren(trEl("p", `Could not load (${res.status}).`));
    return;
  }
  const data = await res.json();
  box.replaceChildren();
  const intro = trEl("div", null, "tr-card");
  intro.appendChild(trEl("p", "Baseline assessment", "tr-card-title"));
  intro.appendChild(trEl("p", data.guidance, "tr-body"));
  if (data.completed_before) {
    intro.appendChild(trEl("p", `${data.completed_before} logged before.`, "tr-hint"));
  }
  const go = trEl("button", "Start assessment", "primary tr-big tr-block");
  go.type = "button";
  go.addEventListener("click", trStartAssessment);
  intro.appendChild(go);
  box.appendChild(intro);
  const ol = document.createElement("ol");
  ol.className = "tr-plan-list";
  data.items.forEach((it) => {
    const li = document.createElement("li");
    li.appendChild(trEl("span", it.exercise, "tr-plan-name"));
    li.appendChild(trEl("div", it.how, "tr-body"));
    li.appendChild(trEl("div", it.why, "tr-hint"));
    if (it.video_url) {
      const a = trEl("a", "Form guide →");
      a.href = it.video_url;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      li.appendChild(a);
    }
    ol.appendChild(li);
  });
  box.appendChild(ol);
}

// =========================================================
// Training: guided session runner
//
// Walks the plan one exercise at a time, counting reps and timing holds, so
// nothing has to be remembered or typed mid-set. Skipping is first-class: a
// migraine or a sore knee should cut the session short without the log
// pretending the work was done. A skipped exercise is simply not logged, so
// the progression engine keeps using the last time it was actually performed.
// =========================================================

let trRun = null;
let trTimer = { handle: null, startedAt: 0, elapsed: 0 };
// "plan" or "assessment" — the assessment is a measurement, not training, so
// it must not be reclassified as a strength session when it finishes.
let trRunKind = "plan";

function trTimerStop() {
  if (trTimer.handle) clearInterval(trTimer.handle);
  trTimer = { handle: null, startedAt: 0, elapsed: 0 };
}

function trCurrentBlock() {
  return trRun && trRun.plan.blocks[trRun.idx];
}

function trStartRunner(blocks) {
  if (!trSession) return;
  const plan = blocks ? { blocks } : trPlan;
  if (!plan) return;
  trRun = { plan, idx: 0, done: {}, skipped: [], sides: {} };
  trRenderRunner();
}

async function trStartAssessment() {
  const res = await fetch(`${API_URL}/training/assessment`, { headers: trAuth() });
  if (!res.ok) {
    trSetStatus("tr-status", `Could not load the assessment (${res.status}).`);
    return;
  }
  const data = await res.json();
  if (!data.items.length) {
    trSetStatus("tr-status", "Load the starter exercise library first.");
    return;
  }
  const made = await fetch(`${API_URL}/training/sessions`, {
    method: "POST",
    headers: { ...trAuth(), "Content-Type": "application/json" },
    body: JSON.stringify({ session_type: "assessment" }),
  });
  if (!made.ok) {
    trSetStatus("tr-status", `Could not start the assessment (${made.status}).`);
    return;
  }
  trSession = await made.json();
  trRunKind = "assessment";
  const box = getElement("tr-assess");
  if (box) box.style.display = "none";
  trRenderSession();
  trStartRunner(data.items);
}

function trRunnerVisible(on) {
  const r = getElement("tr-runner-section");
  if (r) r.style.display = on ? "" : "none";
}

function trRenderRunner() {
  const body = getElement("tr-run-body");
  const head = getElement("tr-run-progress");
  if (!body || !trRun) return;
  trTimerStop();
  body.replaceChildren();

  const blocks = trRun.plan.blocks;
  if (trRun.idx >= blocks.length) {
    head.textContent = "Session complete";
    body.appendChild(trEl("p", "Every exercise has been worked through.", "tr-body"));
    const row = trEl("div", null, "tr-nav");
    const back = trEl("button", "Back", "secondary");
    back.type = "button";
    back.addEventListener("click", () => { trRun.idx = blocks.length - 1; trRenderRunner(); });
    const fin = trEl("button", "Finish and save", "primary tr-big");
    fin.type = "button";
    fin.addEventListener("click", trFinishSession);
    row.append(back, fin);
    body.appendChild(row);
    return;
  }

  const b = blocks[trRun.idx];
  const doneCount = trRun.done[trRun.idx] || 0;
  // "3 sets each side" means six logged sets, so the target counts both.
  const needed = b.per_side ? b.sets * 2 : b.sets;
  const groupLabel = { practice: "practice", knee: "knee maintenance", strength: "strength" }[b.group] || b.group;
  head.textContent = `${trRun.idx + 1} of ${blocks.length} — ${groupLabel}`;

  // An exercise the engine swapped out from under you is worth saying out
  // loud, once, before you start it.
  if (b.notice) body.appendChild(trEl("p", b.notice, "tr-warn"));
  body.appendChild(trEl("h4", b.exercise));
  body.appendChild(trEl("p", b.prescription));
  // Strength comes from working close to your limit, not from reaching it, so
  // the target is a stopping point rather than a challenge.
  const effort = {
    load: "Stop about 2 reps short of failure — that is the point of the number.",
    reps: "Stop about 2 reps short of failure, or when form goes.",
    iso: "Stop when form breaks, not at collapse.",
  }[b.scheme];
  if (effort) body.appendChild(trEl("p", effort, "tr-hint"));
  if (b.why) body.appendChild(trEl("p", b.why, "logs-loading"));
  if (b.form_cues) body.appendChild(trEl("p", b.form_cues, "tr-cues"));
  if (b.video_url) {
    const a = trEl("a", "Form guide →");
    a.href = b.video_url;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    body.appendChild(a);
  }
  body.appendChild(trEl("p", `Sets done: ${doneCount} of ${needed}`
    + (b.per_side ? ` (${b.sets} each side)` : ""), "logs-loading"));

  if (b.scheme === "check") trRenderCheck(body, b);
  else if (b.scheme === "iso") trRenderTimer(body, b);
  else trRenderCounter(body, b);

  // Pain is asked for every exercise because it is what drives the back-off
  // rule, but never required — a blank is honest, a zero would not be.
  const painWrap = trEl("div", null, "form-row tr-field");
  painWrap.appendChild(trEl("label", "Pain 0-10 (optional)"));
  const painIn = document.createElement("input");
  painIn.type = "number"; painIn.min = "0"; painIn.max = "10"; painIn.id = "tr-run-pain";
  painWrap.appendChild(painIn);
  body.appendChild(painWrap);

  // One way out, matched to where you actually are. With nothing logged,
  // moving on IS skipping, so offering both was a distinction without a
  // difference. Part-way through it is a real choice: some sets are done and
  // that is not a skip.
  const nav = trEl("div", null, "tr-nav");
  if (trRun.idx > 0) {
    // Sets already logged for the earlier exercise are kept, so stepping back
    // resumes it rather than restarting it.
    const back = trEl("button", "Back", "secondary");
    back.type = "button";
    back.addEventListener("click", () => { trRun.idx -= 1; trRenderRunner(); });
    nav.appendChild(back);
  }
  if (doneCount === 0) {
    const skip = trEl("button", "Skip this one", "secondary");
    skip.type = "button";
    skip.addEventListener("click", () => {
      trRun.skipped.push(b.exercise);
      trRun.idx += 1;
      trRenderRunner();
    });
    nav.appendChild(skip);
  } else {
    const stop = trEl("button", `Move on — ${doneCount} of ${needed} done`, "secondary");
    stop.type = "button";
    stop.addEventListener("click", () => { trRun.idx += 1; trRenderRunner(); });
    nav.appendChild(stop);
  }
  body.appendChild(nav);
  body.appendChild(trEl("p", "", "logs-loading")).id = "tr-run-status";
}

function trRenderCheck(body, b) {
  const btn = trEl("button", "Done", "primary tr-big tr-block");
  btn.type = "button";
  btn.addEventListener("click", () => trLogRunSet(b, {}));
  body.appendChild(btn);
}

function trRenderCounter(body, b) {
  const row = trEl("div", null, "tr-counter");
  const dec = trEl("button", "−"); dec.type = "button";
  const val = trEl("span", b.target_reps || 0);
  val.id = "tr-run-reps";
  const inc = trEl("button", "+"); inc.type = "button";
  dec.addEventListener("click", () => {
    val.textContent = Math.max(0, Number(val.textContent) - 1);
  });
  inc.addEventListener("click", () => {
    val.textContent = Number(val.textContent) + 1;
  });
  row.append(dec, val, inc, trEl("span", " reps"));
  body.appendChild(row);

  let weightIn = null;
  if (b.scheme === "load") {
    const wRow = trEl("div", null, "form-row");
    wRow.appendChild(trEl("label", "Weight (kg)"));
    weightIn = document.createElement("input");
    weightIn.type = "number"; weightIn.step = "0.25"; weightIn.min = "0";
    if (b.target_weight !== null && b.target_weight !== undefined) {
      weightIn.value = b.target_weight;
    }
    wRow.appendChild(weightIn);
    body.appendChild(wRow);
  }

  let sideSel = null;
  if (b.per_side) {
    const sRow = trEl("div", null, "form-row");
    sRow.appendChild(trEl("label", "Side"));
    sideSel = document.createElement("select");
    [["left", "Left"], ["right", "Right"]].forEach(([v, label]) => {
      const o = trEl("option", label); o.value = v; sideSel.appendChild(o);
    });
    sRow.appendChild(sideSel);
    body.appendChild(sRow);
  }

  const log = trEl("button", "Log set", "primary tr-big tr-block");
  log.type = "button";
  log.addEventListener("click", () => {
    const payload = { reps: Number(val.textContent) };
    if (weightIn && weightIn.value !== "") payload.weight_kg = Number(weightIn.value);
    if (sideSel) {
      payload.side = sideSel.value;
      // Offer the other side next, since unilateral work alternates.
      sideSel.value = sideSel.value === "left" ? "right" : "left";
    }
    trLogRunSet(b, payload);
  });
  body.appendChild(log);
}

function trRenderTimer(body, b) {
  const target = b.target_seconds || 0;

  // Counts down, so what is on screen is how much is left rather than how
  // much has gone. With no target to count towards it falls back to counting
  // up, which is the only sensible thing to show.
  const held = () => trTimer.elapsed
    + (trTimer.handle ? Math.floor((Date.now() - trTimer.startedAt) / 1000) : 0);
  const shown = (secs) => (target ? `${Math.max(0, target - secs)}s` : `${secs}s`);

  const display = trEl("div", shown(0), "tr-timer");
  body.appendChild(display);
  body.appendChild(trEl("p", target ? `of ${target}s` : "counting up", "tr-hint"));

  const showStart = (label) => { startBtn.textContent = label; };

  const tick = () => {
    const secs = held();
    display.textContent = shown(secs);
    // Stop at the target rather than running on: the prescription is the
    // point, and holding to failure every time is how this knee gets angry.
    if (target && secs >= target) {
      trTimerStop();
      trTimer.elapsed = secs;
      display.textContent = "done";
      showStart("Restart");
    }
  };

  // Big targets: these are pressed mid-hold, with shaky hands, without
  // looking properly.
  const controls = trEl("div", null, "tr-timer-controls");

  const startBtn = trEl("button", "Start", "primary tr-big");
  startBtn.type = "button";
  startBtn.addEventListener("click", () => {
    if (trTimer.handle) {
      // Pause: form broke or it needed cutting short.
      trTimer.elapsed += Math.floor((Date.now() - trTimer.startedAt) / 1000);
      clearInterval(trTimer.handle);
      trTimer.handle = null;
      showStart("Resume");
      display.textContent = shown(trTimer.elapsed);
      return;
    }
    if (startBtn.textContent === "Restart") trTimer.elapsed = 0;
    trTimer.startedAt = Date.now();
    trTimer.handle = setInterval(tick, 250);
    showStart("Pause");
  });

  const resetBtn = trEl("button", "Reset", "secondary");
  resetBtn.type = "button";
  resetBtn.addEventListener("click", () => {
    trTimerStop();
    display.textContent = shown(0);
    showStart("Start");
  });

  const log = trEl("button", "Log", "primary tr-big");
  log.type = "button";
  log.addEventListener("click", () => {
    // Logs seconds actually held, not what is left on the clock.
    const secs = held();
    trTimerStop();
    display.textContent = shown(0);
    showStart("Start");
    // Falling back to the target lets a hold be logged without the timer,
    // which is what happens when you forget to press start.
    trLogRunSet(b, { hold_seconds: secs || target });
  });

  controls.append(startBtn, resetBtn, log);
  body.appendChild(controls);
}

async function trLogRunSet(b, fields) {
  if (!trSession) return;
  const painEl = getElement("tr-run-pain");
  const pain = painEl && painEl.value !== "" ? Number(painEl.value) : null;
  const idx = trRun.idx;
  const payload = {
    exercise_id: b.exercise_id,
    set_number: (trRun.done[idx] || 0) + 1,
    pain,
    ...fields,
  };
  const res = await fetch(`${API_URL}/training/sessions/${trSession.session_id}/sets`, {
    method: "POST",
    headers: { ...trAuth(), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const s = getElement("tr-run-status");
    if (s) s.textContent = `Could not save that set (${res.status}).`;
    return;
  }
  trSession = await res.json();
  trRun.done[idx] = (trRun.done[idx] || 0) + 1;

  // Move on once the prescribed sets are in, rather than making the user
  // decide whether they are finished.
  const needed = b.per_side ? b.sets * 2 : b.sets;
  if (trRun.done[idx] >= needed) {
    trRun.idx += 1;
  }
  trRenderRunner();
}

async function trFinishSession() {
  if (!trSession) return;
  // Classify by what was actually logged. A session where every strength
  // exercise was skipped is not a strength session, and counting it as one
  // would advance the phase on work that never happened.
  const didStrength = trSession.sets.some((s) => {
    const b = trRun && trRun.plan.blocks.find((x) => x.exercise_id === s.exercise_id);
    return b && b.group === "strength";   // knee-minimum days do not count
  });
  // An assessment is a measurement. Counting it as a strength session would
  // let a test of what you can do stand in for having done it.
  const sessionType = trRunKind === "assessment"
    ? "assessment"
    : (didStrength ? "strength" : "tai_chi");
  const notes = trRun && trRun.skipped.length
    ? `Skipped: ${trRun.skipped.join(", ")}`
    : null;

  await fetch(`${API_URL}/training/sessions/${trSession.session_id}`, {
    method: "PATCH",
    headers: { ...trAuth(), "Content-Type": "application/json" },
    body: JSON.stringify({
      session_type: sessionType,
      ...(notes ? { notes } : {}),
    }),
  });

  trTimerStop();
  trKindOverride = null;
  trRunKind = "plan";
  trRun = null;
  trSession = null;
  trRunnerVisible(false);
  trRenderSession();
  await trLoadPlan();
  await trLoadHistory();
}
