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
    [dateInput, allergenQuantityInput]
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
    [symptomIdInput, symptomDateInput]
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
    console.log("Fetching analysis stats...");
    const statsRes = await fetch(`${API_URL}/analysis/stats`, {
      headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` }
    });

    if (!statsRes.ok) {
      console.error("Failed to fetch stats:", statsRes.status);
      return;
    }

    if (statsRes.ok) {
      const stats = await statsRes.json();
      console.log("Stats fetched successfully:", stats);

      const totalAllergensEl = getElement("stat-total-allergens");
      if (totalAllergensEl) {
        totalAllergensEl.textContent = stats["Total allergens logged"] || 0;
        console.log("Updated total allergens:", totalAllergensEl.textContent);
      } else {
        console.warn("Element stat-total-allergens not found");
      }

      const totalSymptomsEl = getElement("stat-total-symptoms");
      if (totalSymptomsEl) {
        totalSymptomsEl.textContent = stats["Total symptoms logged"] || 0;
        console.log("Updated total symptoms:", totalSymptomsEl.textContent);
      } else {
        console.warn("Element stat-total-symptoms not found");
      }

      const totalEntriesEl = getElement("stat-total-entries");
      if (totalEntriesEl) {
        totalEntriesEl.textContent = 
          (stats["Total allergens logged"] || 0) + (stats["Total symptoms logged"] || 0);
        console.log("Updated total entries:", totalEntriesEl.textContent);
      } else {
        console.warn("Element stat-total-entries not found");
      }

      const daysEl = getElement("stat-days");
      if (daysEl) {
        daysEl.textContent = stats["Total days tracked"] || 0;
        console.log("Updated days tracked:", daysEl.textContent);
      } else {
        console.warn("Element stat-days not found");
      }

      const avgAllergensPerDayEl = getElement("stat-avg-allergens-per-day");
      if (avgAllergensPerDayEl) {
        avgAllergensPerDayEl.textContent = stats["Average allergens logged per day"] || 0;
        console.log("Updated avg allergens per day:", avgAllergensPerDayEl.textContent);
      } else {
        console.warn("Element stat-avg-allergens-per-day not found");
      }

      const avgSymptomsPerDayEl = getElement("stat-avg-symptoms-per-day");
      if (avgSymptomsPerDayEl) {
        avgSymptomsPerDayEl.textContent = stats["Average symptoms logged per day"] || 0;
        console.log("Updated avg symptoms per day:", avgSymptomsPerDayEl.textContent);
      } else {
        console.warn("Element stat-avg-symptoms-per-day not found");
      }

      const emptyState = getElement("analysis-empty-state");
      const content = getElement("analysis-content");

      if ((totalAllergensEl.textContent === "0") || (totalSymptomsEl.textContent === "0")) {
        if (emptyState) emptyState.style.display = "block";
        if (content) content.style.display = "none";
        return;
      } else {
        if (emptyState) emptyState.style.display = "none";
        if (content) content.style.display = "block";
      }

      // Histogram plot
      console.log("Fetching histogram plot...");
      const histogramPlotImg = getElement("group_histogram");
      if (histogramPlotImg) {
        const res = await fetch(`${API_URL}/analysis/symptom_group_histogram`, {
          headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` }
        });
        if (res.ok) {
          const blob = await res.blob();
          histogramPlotImg.src = URL.createObjectURL(blob);
          console.log("Histogram plot fetched successfully");
        } else {
          console.error("Failed to fetch histogram plot:", res.status, res.statusText);
        }
      } else {
        console.warn("Element group_histogram not found");
      }

      // Allergen rank plot
      console.log("Fetching allergen rank plot...");
      const allergenrankPlotImg = getElement("allergenrank-plot");
      if (allergenrankPlotImg) {
        const res = await fetch(`${API_URL}/analysis/plot_allergen_rank`, {
          headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` }
        });
        if (res.ok) {
          const blob = await res.blob();
          allergenrankPlotImg.src = URL.createObjectURL(blob);
          console.log("Allergen rank plot fetched successfully");
        } else {
          console.error("Failed to fetch allergen rank plot:", res.status, res.statusText);
        }
      } else {
        console.warn("Element allergenrank-plot not found");
      }

      await getSummaryText();
      console.log("Summary text fetched");
    }

  } catch (err) {
      console.error("Failed to fetch analysis plots:", err);
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

      populateAllergenSelect(allergens, recentAllergens);
      populateSymptomSelect(symptoms, recentSymptoms);

      setupAddAllergen();
      setupAddSymptom();
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
    setupAnalysis();

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

fetch(API_URL + "/auth/me", {
   headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` }
})
.then(r => r.text())
.then(t => console.log("AUTH RAW RESPONSE:", t));

