import { getCurrentUser, API_URL } from "./api.js";

document.addEventListener("DOMContentLoaded", async () => {
  await init();

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

  const allergenInput = document.getElementById("allergen-input");
  const allergenIdInput = document.getElementById("allergen-id");
  const allergenSuggestions = document.getElementById("allergen-suggestions");
  const toggleBtn = document.getElementById("toggle-allergen-suggestions");

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
  // Logout
  // =========================================================
  logoutBtn?.addEventListener("click", () => {
    localStorage.removeItem("access_token");
    window.location.href = "index.html";
  });

  // =========================================================
  // Defaults
  // =========================================================
  if (dateInput) dateInput.value = localDateTimeForInput();
  if (symptomDateInput) symptomDateInput.value = localDateTimeForInput();

  // =========================================================
  // Fetch units
  // =========================================================
  const fetchUnits = async () => {
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
  fetchUnits();

  // =========================================================
  // Allergen cache + toggle
  // =========================================================
  let allAllergensCache = [];

  const fetchAllAllergens = async () => {
    try {
      const res = await fetch(`${API_URL}/allergens`, {
        headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` }
      });
      if (!res.ok) throw new Error(res.statusText);

      const data = await res.json();
      // store objects {id, name} for autocomplete
      allAllergensCache = data.map(a => ({ id: a.allergen_id, name: a.allergen_name }));
    } catch (err) {
      console.error("Failed to fetch all allergens:", err);
    }
  };
  fetchAllAllergens();

  const showSuggestions = (inputEl, suggestionsEl, filter = "") => {
    suggestionsEl.innerHTML = "";

    let filtered = allAllergensCache.filter(a =>
      a.name.toLowerCase().includes(filter.toLowerCase())
    );

    filtered.forEach(a => {
      const li = document.createElement("li");
      li.textContent = a.name;
      li.onclick = () => {
        inputEl.value = a.name;
        if (inputEl === allergenInput || inputEl === allergenIntInput) {
          allergenIdInput.value = a.id;
        }
        suggestionsEl.classList.remove("visible");
      };
      suggestionsEl.appendChild(li);
    });

    if (filtered.length > 0) suggestionsEl.classList.add("visible");
  };

  toggleBtn?.addEventListener("click", () => {
    if (allergenSuggestions.classList.contains("visible")) {
      allergenSuggestions.classList.remove("visible");
    } else {
      showSuggestions(allergenInput, allergenSuggestions, ""); // show all allergens
    }
  });

  allergenInput?.addEventListener("input", debounce(() => {
    showSuggestions(allergenInput, allergenSuggestions, allergenInput.value.trim());
  }, 300));

  // =========================================================
  // Symptom autocomplete (existing logic)
  // =========================================================
  const fetchSuggestions = async (query, type) => {
    if (!query) return [];

    const endpoint =
      type === "allergen" ? "allergens" :
      type === "symptom_group" ? "symptom_groups" :
      type === "symptom" ? "symptoms" :
      "allergens";

    const res = await fetch(`${API_URL}/${endpoint}?q=${encodeURIComponent(query)}`, {
      headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` }
    });
    if (!res.ok) return [];
    return await res.json();
  };

  const setupAutocomplete = (inputEl, idEl, suggestionsEl, type) => {
    if (!inputEl) return;

    inputEl.addEventListener("input", debounce(async () => {
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

      if (data.length > 0) suggestionsEl.classList.add("visible");
    }, 300));
  };

  setupAutocomplete(symptomInput, symptomIdInput, symptomSuggestions, "symptom");
  setupAutocomplete(allergenIntInput, allergenIntIdInput, allergenIntSuggestions, "allergen");
  setupAutocomplete(symptomGroupInput, null, symptomGroupSuggestions, "symptom_group");

  // =========================================================
  // Fix stray G in getSummaryText
  // =========================================================
  async function getSummaryText() {
    try {
      const response = await fetch(`${API_URL}/analysis/generate_summary_text`, {
        headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` }
      });
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
      const text = await response.text();
      document.getElementById("summaryDiv").innerText = text; // removed stray G
    } catch (error) {
      console.error("Error fetching summary text:", error);
    }
  }

  // =========================================================
  // Init function
  // =========================================================
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

});
