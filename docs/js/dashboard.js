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

  if (selected === "time-series") {
    const tsPanel = getElement("panel-time-series");
    if (tsPanel) tsPanel.classList.add("visible");
    return;
  }

  if (selected === "deeper-analysis") {
    if (deeperPanel) deeperPanel.classList.add("visible");
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
    if (range === "all") return {};
    if (range === "custom") {
      const params = {};
      if (dateFrom?.value) params.date_from = dateFrom.value;
      if (dateTo?.value)   params.date_to   = dateTo.value;
      return params;
    }
    const months = range === "3m" ? 3 : 1;
    const from = new Date();
    from.setMonth(from.getMonth() - months);
    return {
      date_from: from.toISOString().slice(0, 10),
      date_to:   new Date().toISOString().slice(0, 10),
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
    const win   = periWindow?.value ?? "7";
    if (!name || !type2 || !name2) return;

    const params = new URLSearchParams({ type, name, type2, name2, window_days: win });
    Object.entries(getDateRange()).forEach(([k, v]) => params.set(k, v));

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
        <input type="date" class="med-change-date" value="${new Date().toISOString().slice(0, 10)}" />
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

  if (startInput) startInput.value = new Date().toISOString().slice(0, 10);
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
      startInput.value = new Date().toISOString().slice(0, 10);
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

// =========================================================
// Analysis tab load
// =========================================================
function loadAnalysisTab() {
  fetchAnalysisStats({ force: true }).catch(err => {
    console.error("Analysis refresh failed:", err);
  });

  if (currentUser?.user_id === 4) {
    const analysisSelect = getElement("analysis-select");
    if (analysisSelect && !analysisSelect.value) {
      analysisSelect.value = "time-series";
      showAnalysisPanel("time-series");
    }
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

      if (target === "analysis") {
        loadAnalysisTab();
      }
      if (target === "medication") {
        loadMedicationsTab();
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

    // Set up UI components
    setupLogout();
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
