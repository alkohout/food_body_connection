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
// Safe element getter
// =========================================================

const elementCache = new Map();
const getElement = (id) => {
  if (elementCache.has(id)) return elementCache.get(id);
  
  const el = document.getElementById(id);
  if (!el && !elementCache.has(id)) {
    console.warn(`Element "${id}" not found in DOM`);
  }
  
  elementCache.set(id, el);
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
// Setup Functions (safe to fail)
// =========================================================

function setupLogout() {
  const logoutBtn = getElement("logout-btn");
  if (!logoutBtn) return;

  logoutBtn.addEventListener("click", () => {
    localStorage.removeItem("access_token");
    window.location.href = "index.html";
  });
}

function setupDefaults() {
  const dateInput = getElement("allergen-date");
  const symptomDateInput = getElement("symptom-date");

  if (dateInput) dateInput.value = localDateTimeForInput();
  if (symptomDateInput) symptomDateInput.value = localDateTimeForInput();
}

function setupTabs() {
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
}

function setupForms() {
  // Allergen form - FIXED: uses select element
  const allergenForm = getElement("allergen-form");
  const allergenSelect = getElement("allergen-select");
  const allergenQuantityInput = getElement("allergen-quantity");
  const dateInput = getElement("allergen-date");
  const unitSelect = getElement("allergen-unit");

  if (allergenForm) {
    submitForm(
      allergenForm,
      "entries/allergens",
      () => ({
        allergen_id: Number(allergenSelect?.value || 0),
        date_time: new Date(dateInput?.value || Date.now()).toISOString(),
        quantity: Number(allergenQuantityInput?.value) || null,
        unit_id: Number(unitSelect?.value) || null
      }),
      getElement("log-success"),
      getElement("log-error"),
      [allergenQuantityInput, dateInput]
    );
  }

  // Symptom form
  const symptomForm = getElement("symptom-form");
  const symptomIdInput = getElement("symptom-id");
  const symptomInput = getElement("symptom-input");
  const symptomDateInput = getElement("symptom-date");
  const symptomIntensityInput = getElement("symptom-intensity");

  if (symptomForm) {
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
}

function setupAnalysis() {
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
      
      // Fetch all plots in parallel
      const plotRequests = [];
      
      const intensityVolumePlotImg = getElement("analysis-intensity-volume-plot");
      if (intensityVolumePlotImg) {
        plotRequests.push(
          fetch(
            `${API_URL}/analysis/intensity_volume?allergen_name=${encodeURIComponent(allergenName)}&lag_start=${start}&lag_end=${end}&_=${cacheBust}`,
            { headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` }, cache: "no-store" }
          ).then(res => res.blob()).then(blob => {
            if (intensityVolumePlotImg.src) URL.revokeObjectURL(intensityVolumePlotImg.src);
            intensityVolumePlotImg.src = URL.createObjectURL(blob);
          })
        );
      }

      const timeSeriesPlotImg = getElement("analysis-time-series-plot");
      if (timeSeriesPlotImg) {
        plotRequests.push(
          fetch(
            `${API_URL}/analysis/plot_time_series?allergen_name=${encodeURIComponent(allergenName)}`,
            { headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` } }
          ).then(res => res.blob()).then(blob => {
            timeSeriesPlotImg.src = URL.createObjectURL(blob);
          })
        );
      }

      const barPlotImg = getElement("analysis-bar-plot");
      if (barPlotImg && symptomGroup) {
        plotRequests.push(
          fetch(
            `${API_URL}/analysis/plot_bar_plots?allergen_name=${encodeURIComponent(allergenName)}&lag_start=${start}&lag_end=${end}&symptom_group=${encodeURIComponent(symptomGroup)}&_=${cacheBust}`,
            { headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` } }
          ).then(res => res.blob()).then(blob => {
            if (barPlotImg.src) URL.revokeObjectURL(barPlotImg.src);
            barPlotImg.src = URL.createObjectURL(blob);
          })
        );
      }

      const riskPlotImg = getElement("analysis-risk-plot");
      if (riskPlotImg && symptomGroup) {
        plotRequests.push(
          fetch(
            `${API_URL}/analysis/plot_risk?allergen_name=${encodeURIComponent(allergenName)}&lag_start=${start}&lag_end=${end}&symptom_group=${encodeURIComponent(symptomGroup)}&_=${cacheBust}`,
            { headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` } }
          ).then(res => res.blob()).then(blob => {
            if (riskPlotImg.src) URL.revokeObjectURL(riskPlotImg.src);
            riskPlotImg.src = URL.createObjectURL(blob);
          })
        );
      }

      await Promise.all(plotRequests);
      await fetchTemporalStats(allergenName);

    } catch (err) {
      console.error("Failed to update analysis plots:", err);
    }
  });
}

// =========================================================
// Data Fetching (safe to fail)
// =========================================================

const fetchUnits = async () => {
  const unitSelect = getElement("allergen-unit");
  if (!unitSelect) return;

  try {
    console.log("Fetching units...");
    const res = await fetch(`${API_URL}/units`, {
      headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` }
    });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);

    const units = await res.json();
    console.log(`✅ Loaded ${units.length} units`);
    
    units.forEach(u => {
      const opt = document.createElement("option");
      opt.value = u.unit_id;
      opt.textContent = u.unit_name;
      unitSelect.appendChild(opt);
    });
  } catch (err) {
    console.error("❌ Failed to fetch units:", err);
    // Don't throw - let the app continue
  }
};

const fetchAllergens = async () => {
  const allergenSelect = getElement("allergen-select");
  if (!allergenSelect) return;

  // Show loading state
  allergenSelect.innerHTML = '<option value="">Loading allergens...</option>';
  
  try {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token");

    // Call search endpoint with empty query to get all
    const url = `${API_URL}/allergens?q=`;
    console.log("Fetching allergens from:", url);
    
    const res = await fetch(url, {
      headers: { 
        "Authorization": `Bearer ${token}`,
        "Accept": "application/json"
      }
    });
    
    if (!res.ok) {
      const errorText = await res.text();
      throw new Error(`HTTP ${res.status}: ${res.statusText} - ${errorText}`);
    }

    const allergens = await res.json();
    console.log("✅ API response:", allergens);
    
    if (!Array.isArray(allergens)) {
      throw new Error(`Invalid data format: expected array, got ${typeof allergens}`);
    }

    // Clear and repopulate
    allergenSelect.innerHTML = '<option value="">Select an allergen...</option>';
    
    if (allergens.length === 0) {
      console.warn("⚠️ API returned empty allergens array!");
      
      // FOR DEVELOPMENT ONLY: Uncomment to use mock data
      /*
      const mockAllergens = [
        { allergen_id: 1, allergen_name: "Dairy" },
        { allergen_id: 2, allergen_name: "Gluten" },
        { allergen_id: 3, allergen_name: "Nuts" }
      ];
      allergens = mockAllergens;
      */
      
      if (allergens.length === 0) {
        const opt = document.createElement("option");
        opt.value = "";
        opt.textContent = "No allergens found";
        allergenSelect.appendChild(opt);
        return;
      }
    }

    allergens.forEach((u, i) => {
      if (!u.allergen_id || !u.allergen_name) {
        console.warn(`Allergen ${i} missing properties:`, u);
        return;
      }
      const opt = document.createElement("option");
      opt.value = u.allergen_id;
      opt.textContent = u.allergen_name;
      allergenSelect.appendChild(opt);
    });
    
    console.log(`✅ Populated dropdown with ${allergens.length} allergens`);
    
  } catch (err) {
    console.error("❌ Failed to fetch allergens:", err);
    allergenSelect.innerHTML = '<option value="">Error loading allergens</option>';
    // Don't throw - let the app continue
  }
};

// =========================================================
// Autocomplete (only for elements that exist)
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
  // Silent return if elements don't exist
  if (!inputEl || !suggestionsEl) return;

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
  if (!formEl) return;

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

      if (successEl) {
        successEl.textContent = "Logged successfully!";
        setTimeout(() => { successEl.textContent = ""; }, 3000);
      }
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

// =========================================================
// Captions
// =========================================================

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
// Global click handler
// =========================================================

document.addEventListener("click", (e) => {
  if (!e.target.closest(".autocomplete-wrapper")) {
    document.querySelectorAll(".suggestions").forEach(s => s.classList.remove("visible"));
  }
});

// =========================================================
// Init (FIXED: Only log out on auth errors)
// =========================================================

async function init() {
  console.log("init() started");
  
  if (!localStorage.getItem("access_token")) {
    console.log("No access token, redirecting to login");
    window.location.href = "index.html";
    return;
  }

  // Set up core UI first (safe operations)
  setupLogout();
  setupDefaults();
  setupTabs();

  // Try to authenticate user (this is the only critical step)
  let user;
  try {
    user = await getCurrentUser();
    console.log("✅ User authenticated:", user?.email);
  } catch (err) {
    console.error("❌ Authentication failed:", err);
    localStorage.removeItem("access_token");
    window.location.href = "index.html";
    return; // Stop here - don't proceed if auth fails
  }

  // Display user info
  const userEmailEl = getElement("user-email");
  if (userEmailEl) userEmailEl.textContent = user.email;

  // Load data and set up UI (non-critical - errors here won't log you out)
  try {
    console.log("Loading data...");
    await Promise.all([
      fetchUnits(),
      fetchAllergens()
    ]);
    console.log("✅ Data loaded");
  } catch (err) {
    console.error("❌ Data loading error (non-critical):", err);
    // Continue anyway - don't log out for data issues
  }

  try {
    // Set up UI components
    setupForms();
    setupAnalysis();
    initializeCaptions();
    
    console.log("✅ UI setup complete");
  } catch (err) {
    console.error("❌ UI setup error (non-critical):", err);
    // Continue anyway
  }

  console.log("✅ init() completed successfully");
}