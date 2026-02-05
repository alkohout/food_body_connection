import { getCurrentUser, API_URL } from "./api.js";

document.addEventListener("DOMContentLoaded", async () => {
  await init();
});

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
// Elements
// =========================================================

const logoutBtn = document.getElementById("logout-btn");
const dateInput = document.getElementById("allergen-date");
const unitSelect = document.getElementById("allergen-unit");
const allergenSelect = document.getElementById("allergen-select");
const allergenInput = document.getElementById("allergen-input");
const allergenIdInput = document.getElementById("allergen-id");
const allergenSuggestions = document.getElementById("allergen-suggestions");
const symptomInput = document.getElementById("symptom-input");
const symptomIdInput = document.getElementById("symptom-id");
const symptomSuggestions = document.getElementById("symptom-suggestions");
const symptomDateInput = document.getElementById("symptom-date");
const allergenIntInput = document.getElementById("allergen-intensity-input");
const allergenIntIdInput = document.getElementById("allergen-intensity-id");
const allergenIntSuggestions = document.getElementById("allergen-intensity-suggestions");
const symptomGroupInput = document.getElementById("symptom-group-input");
const symptomGroupIdInput = document.getElementById("symptom-group-id");
const symptomGroupSuggestions = document.getElementById("symptom-group-suggestions");
const lagWindowInput = document.getElementById("lag-window");
const histogramPlotImg = document.getElementById("group_histogram");
const allergenrankPlotImg = document.getElementById("allergenrank-plot");
const intensityVolumePlotImg = document.getElementById("analysis-intensity-volume-plot");
const timeSeriesPlotImg = document.getElementById("analysis-time-series-plot");
const barPlotImg = document.getElementById("analysis-bar-plot");
const riskPlotImg = document.getElementById("analysis-risk-plot");
const predictOut = document.getElementById("predict-out");

// =========================================================
// Initialize Captions (with null checks)
// =========================================================

function initializeCaptions() {
  const captionAllergen = document.getElementById("caption-allergen");
  const captionSymptomGroup = document.getElementById("caption-symptom-group");
  const captionLag = document.getElementById("caption-lag");
  const captionLagDose = document.getElementById("caption-lag-dose");
  const captionAllergenDose = document.getElementById("caption-allergen-dose");

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
// Logout
// =========================================================

if (logoutBtn) {
  logoutBtn.addEventListener("click", () => {
    localStorage.removeItem("access_token");
    window.location.href = "index.html";
  });
}

// =========================================================
// Defaults
// =========================================================

if (dateInput) dateInput.value = localDateTimeForInput();
if (symptomDateInput) symptomDateInput.value = localDateTimeForInput();

// =========================================================
// Fetch units
// =========================================================

const fetchUnits = async () => {
  if (!unitSelect) return; // Add null check
  
  try {
    const res = await fetch(`${API_URL}/units`, {
      headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` }
    });
    if (!res.ok) throw new Error(res.statusText);

    const units = await res.json();
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
// Fetch allergens
// =========================================================

const fetchAllergens = async () => {
  if (!allergenSelect) return; // Add null check
  
  try {
    const res = await fetch(`${API_URL}/allergens`, {
      headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` }
    });
    if (!res.ok) throw new Error(res.statusText);

    const allergens = await res.json();
    allergens.forEach(u => {
      const opt_allergen = document.createElement("option");
      opt_allergen.value = u.allergen_id;
      opt_allergen.textContent = u.allergen_name;
      allergenSelect.appendChild(opt_allergen);
    });
  } catch (err) {
    console.error("Failed to fetch allergens:", err);
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
  if (!inputEl || !suggestionsEl) return; // Add null check for suggestionsEl

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
// Allergen form
// =========================================================

const allergenQuantityInput = document.getElementById("allergen-quantity");

submitForm(
  document.getElementById("allergen-form"),
  "entries/allergens",
  () => ({
    allergen_id: Number(allergenIdInput?.value || 0),
    date_time: new Date(dateInput?.value || Date.now()).toISOString(),
    quantity: Number(allergenQuantityInput?.value) || null,
    unit_id: Number(unitSelect?.value) || null
  }),
  document.getElementById("log-success"),
  document.getElementById("log-error"),
  [allergenInput, allergenIdInput, dateInput, allergenQuantityInput]
);

// =========================================================
// Symptom form
// =========================================================

const symptomIntensityInput = document.getElementById("symptom-intensity");

submitForm(
  document.getElementById("symptom-form"),
  "entries/symptoms",
  () => ({
    symptom_id: Number(symptomIdInput?.value || 0),
    date_time: new Date(symptomDateInput?.value || Date.now()).toISOString(),
    intensity: Number(symptomIntensityInput?.value) || null
  }),
  document.getElementById("symptom-success"),
  document.getElementById("symptom-error"),
  [symptomInput, symptomIdInput, symptomDateInput]
);

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

const updatePlotButton = document.getElementById("update-plot-btn");
if (updatePlotButton) {
  updatePlotButton.addEventListener("click", async () => {
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

      // Fetch all plots
      const plotPromises = [];

      if (intensityVolumePlotImg) {
        plotPromises.push(
          fetch(
            `${API_URL}/analysis/intensity_volume?allergen_name=${encodeURIComponent(allergenName)}&lag_start=${start}&lag_end=${end}&_=${cacheBust}`,
            { headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` }, cache: "no-store" }
          ).then(res => res.blob()).then(blob => {
            if (intensityVolumePlotImg.src) URL.revokeObjectURL(intensityVolumePlotImg.src);
            intensityVolumePlotImg.src = URL.createObjectURL(blob);
          })
        );
      }

      if (timeSeriesPlotImg) {
        plotPromises.push(
          fetch(
            `${API_URL}/analysis/plot_time_series?allergen_name=${encodeURIComponent(allergenName)}`,
            { headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` } }
          ).then(res => res.blob()).then(blob => {
            timeSeriesPlotImg.src = URL.createObjectURL(blob);
          })
        );
      }

      if (barPlotImg && symptomGroup) {
        plotPromises.push(
          fetch(
            `${API_URL}/analysis/plot_bar_plots?allergen_name=${encodeURIComponent(allergenName)}&lag_start=${start}&lag_end=${end}&symptom_group=${encodeURIComponent(symptomGroup)}&_=${cacheBust}`,
            { headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` } }
          ).then(res => res.blob()).then(blob => {
            if (barPlotImg.src) URL.revokeObjectURL(barPlotImg.src);
            barPlotImg.src = URL.createObjectURL(blob);
          })
        );
      }

      if (riskPlotImg && symptomGroup) {
        plotPromises.push(
          fetch(
            `${API_URL}/analysis/plot_risk?allergen_name=${encodeURIComponent(allergenName)}&lag_start=${start}&lag_end=${end}&symptom_group=${encodeURIComponent(symptomGroup)}&_=${cacheBust}`,
            { headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` } }
          ).then(res => res.blob()).then(blob => {
            if (riskPlotImg.src) URL.revokeObjectURL(riskPlotImg.src);
            riskPlotImg.src = URL.createObjectURL(blob);
          })
        );
      }

      await Promise.all(plotPromises);
      await fetchTemporalStats(allergenName);

    } catch (err) {
      console.error("Failed to update plots:", err);
    }
  });
}

const fetchAnalysisPlot = async () => {
  try {
    // Stats
    const statsRes = await fetch(`${API_URL}/analysis/stats`, {
      headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` }
    });

    if (statsRes.ok) {
      const stats = await statsRes.json();

      const totalEntriesEl = document.getElementById("stat-total-entries");
      if (totalEntriesEl) {
        totalEntriesEl.textContent = 
          (stats["Total allergens logged"] || 0) + (stats["Total symptoms logged"] || 0);
      }

      const daysEl = document.getElementById("stat-days");
      if (daysEl) {
        daysEl.textContent = stats["Total days tracked"] || 0;
      }
    }

    // Histogram Plot
    if (histogramPlotImg) {
      const group_hist = await fetch(`${API_URL}/analysis/symptom_group_histogram`, {
        headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` }
      });

      if (group_hist.ok) {
        const blob_hist = await group_hist.blob();
        histogramPlotImg.src = URL.createObjectURL(blob_hist);
      }
    }

    // Allergen Rank Plot
    if (allergenrankPlotImg) {
      const plotAllergenRank = await fetch(`${API_URL}/analysis/plot_allergen_rank`, {
        headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` }
      });

      if (plotAllergenRank.ok) {
        const blobAllergenRank = await plotAllergenRank.blob();
        allergenrankPlotImg.src = URL.createObjectURL(blobAllergenRank);
      }
    }

    // Model Predict output
    if (predictOut) {
      const predict = await fetch(`${API_URL}/analysis/predict`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${localStorage.getItem("access_token")}`
        }
      });

      if (predict.ok) {
        const predictionText = await predict.text();
        predictOut.textContent = predictionText;
      }
    }

    // Call the summary analysis function
    await getSummaryText();

  } catch (err) {
    console.error("Failed to fetch analysis plots:", err);
  }
};

// =========================================================
// Tabs
// =========================================================

document.querySelectorAll(".tab").forEach(tab => {
  tab.addEventListener("click", () => {
    const target = tab.dataset.tab;

    document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
    document.querySelectorAll(".form").forEach(f => f.classList.remove("active"));

    tab.classList.add("active");
    const targetForm = document.getElementById(`${target}-form`);
    if (targetForm) targetForm.classList.add("active");

    if (target === "analysis") fetchAnalysisPlot();
  });
});

// =========================================================
// Helper Functions
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
    const el = document.getElementById(id);
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

      const summaryDiv = document.getElementById("summaryDiv");
      if (summaryDiv) summaryDiv.innerText = text;
    }
  } catch (error) {
    console.error("Error fetching summary text:", error);
  }
}

// =========================================================
// Hide suggestions when clicking outside
// =========================================================

document.addEventListener("click", (e) => {
  if (!e.target.closest(".autocomplete-wrapper")) {
    const allSuggestions = document.querySelectorAll(".suggestions");
    allSuggestions.forEach(s => s.classList.remove("visible"));
  }
});

// =========================================================
// Init
// =========================================================

async function init() {
  if (!localStorage.getItem("access_token")) {
    window.location.href = "index.html";
    return;
  }

  try {
    const user = await getCurrentUser();
    const userEmailEl = document.getElementById("user-email");
    if (userEmailEl) userEmailEl.textContent = user.email;

    // Initialize all data
    await Promise.all([
      fetchUnits(),
      fetchAllergens()
    ]);

    // Setup autocomplete
    setupAutocomplete(allergenInput, allergenIdInput, allergenSuggestions, "allergen");
    setupAutocomplete(symptomInput, symptomIdInput, symptomSuggestions, "symptom");
    setupAutocomplete(allergenIntInput, allergenIntIdInput, allergenIntSuggestions, "allergen");
    setupAutocomplete(symptomGroupInput, null, symptomGroupSuggestions, "symptom_group");

    // Initialize captions
    initializeCaptions();

  } catch (err) {
    console.error("Initialization error:", err);
    localStorage.removeItem("access_token");
    window.location.href = "index.html";
  }
}