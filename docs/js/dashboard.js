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
  } catch (err) {
    console.error("Failed to fetch units:", err);
  }
};

// =========================================================
// Fetch allergens (ROBUST VERSION)
// =========================================================

const fetchAllergens = async () => {
  const allergenSelect = getElement("allergen-select");
  if (!allergenSelect) {
    console.error("CRITICAL: allergen-select element not found!");
    return;
  }

  console.log("Starting to fetch allergens...");
  
  try {
    const url = `${API_URL}/allergens`;
    console.log("API URL:", url);
    
    const token = localStorage.getItem("access_token");
    if (!token) {
      console.error("No access token found");
      return;
    }
    
    console.log("Making authenticated request...");
    const res = await fetch(url, {
      headers: { 
        "Authorization": `Bearer ${token}`,
        "Accept": "application/json"
      }
    });
    
    console.log("Response status:", res.status, res.statusText);
    
    if (!res.ok) {
      const errorText = await res.text();
      throw new Error(`HTTP ${res.status}: ${res.statusText} - ${errorText}`);
    }

    const allergens = await res.json();
    console.log("Raw allergens data:", allergens);
    
    if (!Array.isArray(allergens)) {
      console.error("Expected array but got:", typeof allergens, allergens);
      throw new Error("Invalid data format: expected array");
    }

    console.log(`Processing ${allergens.length} allergens...`);
    
    // Clear and repopulate
    allergenSelect.innerHTML = '<option value="">Select an allergen...</option>';
    
    if (allergens.length === 0) {
      console.warn("API returned empty allergens array");
      const opt = document.createElement("option");
      opt.value = "";
      opt.textContent = "No allergens available";
      allergenSelect.appendChild(opt);
      return;
    }

    allergens.forEach((u, i) => {
      if (!u.allergen_id || !u.allergen_name) {
        console.warn(`Allergen ${i} missing properties:`, u);
        return;
      }
      const opt_allergen = document.createElement("option");
      opt_allergen.value = u.allergen_id;
      opt_allergen.textContent = u.allergen_name;
      allergenSelect.appendChild(opt_allergen);
    });
    
    console.log(`✅ Successfully populated dropdown with ${allergens.length} allergens`);
    console.log("Dropdown HTML:", allergenSelect.innerHTML.substring(0, 200) + "...");
    
  } catch (err) {
    console.error("❌ Failed to fetch allergens:", err);
    
    // Show error in dropdown
    allergenSelect.innerHTML = '<option value="">Error loading allergens</option>';
  }
};

// =========================================================
// Autocomplete
// =========================================================

const fetchSuggestions = async (query, type) => {
  if (!query) return [];

  const endpoint =
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
  }, 300);

  inputEl.addEventListener("input", handleInput);
};

// =========================================================
// Generic form submitter
// =========================================================

const submitForm = (formEl, endpoint, payloadFn, successEl, errorEl, resetFields = []) => {
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
  const allergenInput = getElement("allergen-input");
  const allergenQuantityInput = getElement("allergen-quantity");
  const dateInput = getElement("allergen-date");
  const unitSelect = getElement("allergen-unit");

  submitForm(
    allergenForm,
    "entries/allergens",
    () => ({
      allergen_id: Number(allergenIdInput?.value || 0),
      date_time: new Date(dateInput?.value || Date.now()).toISOString(),
      quantity: Number(allergenQuantityInput?.value) || null,
      unit_id: Number(unitSelect?.value) || null
    }),
    getElement("log-success"),
    getElement("log-error"),
    [allergenInput, allergenIdInput, dateInput, allergenQuantityInput]
  );

  // Symptom form
  const symptomForm = getElement("symptom-form");
  const symptomIdInput = getElement("symptom-id");
  const symptomInput = getElement("symptom-input");
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
    [symptomInput, symptomIdInput, symptomDateInput]
  );
}

// =========================================================
// Analysis
// =========================================================

const fetchTemporalStats = async (allergenName) => {
  try {
    const res = await fetch(
      `${API_URL}/analysis/temporal_stats?allergen_name=${encodeURIComponent(allergenName)}`,
      { headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` } }
    );

    if (!res.ok) throw new Error(res.statusText);
    const data = await res.json();
    return data;
  } catch (err) {
    console.error("Failed to fetch temporal stats:", err);
    return [];
  }
};

const setupAnalysis = () => {
  const updatePlotButton = getElement("update-plot-btn");
  if (!updatePlotButton) return;

  updatePlotButton.addEventListener("click", async () => {
    const allergenIntInput = getElement("allergen-intensity-input");
    const lagWindowInput = getElement("lag-window");
    const symptomGroupInput = getElement("symptom-group-input");
    
    const allergenName = allergenIntInput?.value || "Dairy";
    const lagWindow = lagWindowInput?.value || "0_6";
    
    const LAG_WINDOWS = {
      "0_6": { start: 0, end: 6 },
      "6_24": { start: 6, end: 24 },
      "24_48": { start: 24, end: 48 },
      "0_24": { start: 0, end: 24 },
      "0_48": { start: 0, end: 48 },
      "0_72": { start: 0, end: 72 }
    };
    
    const { start, end } = LAG_WINDOWS[lagWindow] || LAG_WINDOWS["0_6"];
    const symptomGroup = symptomGroupInput?.value || "";
    const lagWindowText = `${start} - ${end} hrs`;

    updateCaptions(allergenName, symptomGroup, lagWindowText);

    try {
      const cacheBust = Date.now();
      
      // Fetch intensity-volume plot
      const intensityVolumePlotImg = getElement("analysis-intensity-volume-plot");
      if (intensityVolumePlotImg) {
        const res = await fetch(
          `${API_URL}/analysis/intensity_volume?allergen_name=${encodeURIComponent(allergenName)}&lag_start=${start}&lag_end=${end}&_=${cacheBust}`,
          { headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` }, cache: "no-store" }
        );
        const blob = await res.blob();
        if (intensityVolumePlotImg.src) URL.revokeObjectURL(intensityVolumePlotImg.src);
        intensityVolumePlotImg.src = URL.createObjectURL(blob);
      }

      // Fetch time series plot
      const timeSeriesPlotImg = getElement("analysis-time-series-plot");
      if (timeSeriesPlotImg) {
        const res = await fetch(
          `${API_URL}/analysis/plot_time_series?allergen_name=${encodeURIComponent(allergenName)}`,
          { headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` } }
        );
        const blob = await res.blob();
        timeSeriesPlotImg.src = URL.createObjectURL(blob);
      }

      // Fetch bar plot
      const barPlotImg = getElement("analysis-bar-plot");
      if (barPlotImg && symptomGroup) {
        const res = await fetch(
          `${API_URL}/analysis/plot_bar_plots?allergen_name=${encodeURIComponent(allergenName)}&lag_start=${start}&lag_end=${end}&symptom_group=${encodeURIComponent(symptomGroup)}&_=${cacheBust}`,
          { headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` } }
        );
        const blob = await res.blob();
        if (barPlotImg.src) URL.revokeObjectURL(barPlotImg.src);
        barPlotImg.src = URL.createObjectURL(blob);
      }

      // Fetch risk plot
      const riskPlotImg = getElement("analysis-risk-plot");
      if (riskPlotImg && symptomGroup) {
        const res = await fetch(
          `${API_URL}/analysis/plot_risk?allergen_name=${encodeURIComponent(allergenName)}&lag_start=${start}&lag_end=${end}&symptom_group=${encodeURIComponent(symptomGroup)}&_=${cacheBust}`,
          { headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` } }
        );
        const blob = await res.blob();
        if (riskPlotImg.src) URL.revokeObjectURL(riskPlotImg.src);
        riskPlotImg.src = URL.createObjectURL(blob);
      }

      await fetchTemporalStats(allergenName);

    } catch (err) {
      console.error("Failed to update analysis plots:", err);
    }
  });
};

const fetchAnalysisPlot = async () => {
  try {
    // Stats
    const statsRes = await fetch(`${API_URL}/analysis/stats`, {
      headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` }
    });

    if (statsRes.ok) {
      const stats = await statsRes.json();
      
      const totalEntriesEl = getElement("stat-total-entries");
      if (totalEntriesEl) {
        totalEntriesEl.textContent = 
          (stats["Total allergens logged"] || 0) + (stats["Total symptoms logged"] || 0);
      }

      const daysEl = getElement("stat-days");
      if (daysEl) {
        daysEl.textContent = stats["Total days tracked"] || 0;
      }
    }

    // Histogram plot
    const histogramPlotImg = getElement("group_histogram");
    if (histogramPlotImg) {
      const res = await fetch(`${API_URL}/analysis/symptom_group_histogram`, {
        headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` }
      });
      if (res.ok) {
        const blob = await res.blob();
        histogramPlotImg.src = URL.createObjectURL(blob);
      }
    }

    // Allergen rank plot
    const allergenrankPlotImg = getElement("allergenrank-plot");
    if (allergenrankPlotImg) {
      const res = await fetch(`${API_URL}/analysis/plot_allergen_rank`, {
        headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` }
      });
      if (res.ok) {
        const blob = await res.blob();
        allergenrankPlotImg.src = URL.createObjectURL(blob);
      }
    }

    // Prediction
    const predictOut = getElement("predict-out");
    if (predictOut) {
      const res = await fetch(`${API_URL}/analysis/predict`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${localStorage.getItem("access_token")}`
        }
      });
      if (res.ok) {
        predictOut.textContent = await res.text();
      }
    }

    await getSummaryText();

  } catch (err) {
    console.error("Failed to fetch analysis plots:", err);
  }
};

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

      if (target === "analysis") fetchAnalysisPlot();
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

async function getSummaryText() {
  try {
    const response = await fetch(`${API_URL}/analysis/generate_summary_text`, {
      headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` }
    });

    if (response.ok) {
      const text = await response.text();
      console.log("Summary text:", text);
      const summaryDiv = getElement("summaryDiv");
      if (summaryDiv) summaryDiv.innerText = text;
    }
  } catch (error) {
    console.error("Error fetching summary text:", error);
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
// Init
// =========================================================

async function init() {
  console.log("init() started");
  
  if (!localStorage.getItem("access_token")) {
    console.log("No access token, redirecting to login");
    window.location.href = "index.html";
    return;
  }

  try {
    const user = await getCurrentUser();
    console.log("Current user:", user);
    
    const userEmailEl = getElement("user-email");
    if (userEmailEl) userEmailEl.textContent = user.email;

    // Set up UI components
    setupLogout();
    setupDefaults();
    setupTabs();

    // Load data (run in parallel)
    console.log("Loading units and allergens...");
    await Promise.all([
      fetchUnits(),
      fetchAllergens()
    ]);
    console.log("Data loading complete");

    // -----------------------------------------
    // Sync allergen select → inputs
    // -----------------------------------------
    const allergenSelect = getElement("allergen-select");
    const allergenInput = getElement("allergen-input");
    const allergenIdInput = getElement("allergen-id");

    if (allergenSelect) {
      allergenSelect.addEventListener("change", () => {
        const selectedOption = allergenSelect.selectedOptions[0];

        if (!selectedOption || !allergenSelect.value) {
          allergenInput.value = "";
          allergenIdInput.value = "";
          return;
        }

        allergenIdInput.value = allergenSelect.value;
        allergenInput.value = selectedOption.textContent;
      });
    }

    // Set up autocomplete (after data is loaded)
    console.log("Setting up autocomplete...");
    setupAutocomplete(
      getElement("symptom-input"),
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