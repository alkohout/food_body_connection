import { getCurrentUser, API_URL } from "./api.js";

document.addEventListener("DOMContentLoaded", async () => {
  await init();

  // -------------------------
  // Helper functions
  // -------------------------

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

  // -------------------------
  // Elements
  // -------------------------
  const logoutBtn = document.getElementById("logout-btn");
  const dateInput = document.getElementById("allergen-date");
  const unitSelect = document.getElementById("allergen-unit");

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

  const analysisPlotImg = document.getElementById("analysis-plot");
  const intensityVolumePlotImg = document.getElementById("analysis-intensity-volume-plot");

  // -------------------------
  // Logout
  // -------------------------
  if (logoutBtn) {
    logoutBtn.addEventListener("click", () => {
      localStorage.removeItem("access_token");
      window.location.href = "index.html";
    });
  }

  // -------------------------
  // Set default datetime
  // -------------------------
  dateInput.value = localDateTimeForInput();
  symptomDateInput.value = localDateTimeForInput();

  // -------------------------
  // Fetch units
  // -------------------------
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

  // -------------------------
  // Autocomplete fetcher
  // -------------------------
  const fetchSuggestions = async (query, type = "allergen") => {
    if (!query) return [];
    const url = `${API_URL}/${type === "allergen" ? "allergens" : "symptoms"}?q=${encodeURIComponent(query)}`;
    const res = await fetch(url, { headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` } });
    if (!res.ok) return [];
    return await res.json();
  };

  const setupAutocomplete = (inputEl, idEl, suggestionsEl, type) => {
    inputEl.addEventListener("input", debounce(async () => {
      const query = inputEl.value.trim();
      idEl.value = "";
      suggestionsEl.innerHTML = "";
      if (!query) return;

      const data = await fetchSuggestions(query, type);
      data.forEach(item => {
        const li = document.createElement("li");
        li.textContent = type === "allergen" ? item.allergen_name : item.symptom_name;
        li.addEventListener("click", () => {
          inputEl.value = li.textContent;
          idEl.value = type === "allergen" ? item.allergen_id : item.symptom_id;
          suggestionsEl.innerHTML = "";
        });
        suggestionsEl.appendChild(li);
      });
    }, 300));
  };

  setupAutocomplete(allergenInput, allergenIdInput, allergenSuggestions, "allergen");
  setupAutocomplete(symptomInput, symptomIdInput, symptomSuggestions, "symptom");
  setupAutocomplete(allergenIntInput, allergenIntIdInput, allergenIntSuggestions, "allergen");

  // -------------------------
  // Form submissions
  // -------------------------
  const submitForm = (formEl, url, body, successEl, errorEl, resetFields = []) => {
    formEl.addEventListener("submit", async e => {
      e.preventDefault();
      try {
        const res = await fetch(`${API_URL}/${url}`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${localStorage.getItem("access_token")}`
          },
          body: JSON.stringify(body())
        });
        if (!res.ok) {
          const err = await res.text();
          throw new Error(err);
        }
        successEl.textContent = "Logged successfully!";
        errorEl.textContent = "";
        resetFields.forEach(f => f.value = "");
      } catch (err) {
        errorEl.textContent = `Error: ${err.message}`;
      }
    });
  };

  // Allergen form
  submitForm(
    document.getElementById("allergen-form"),
    "entries/allergens",
    () => ({
      allergen_id: parseInt(allergenIdInput.value),
      date_time: new Date(dateInput.value).toISOString(),
      quantity: parseFloat(document.getElementById("allergen-quantity").value) || null,
      unit_id: parseInt(unitSelect.value) || null
    }),
    document.getElementById("log-success"),
    document.getElementById("log-error"),
    [allergenInput, allergenIdInput, dateInput, document.getElementById("allergen-quantity"), unitSelect]
  );

  // Symptom form
  submitForm(
    document.getElementById("symptom-form"),
    "entries/symptoms",
    () => ({
      symptom_id: parseInt(symptomIdInput.value),
      date_time: new Date(symptomDateInput.value).toISOString(),
      intensity: parseInt(document.getElementById("symptom-intensity").value) || null
    }),
    document.getElementById("symptom-success"),
    document.getElementById("symptom-error"),
    [symptomInput, symptomIdInput, symptomDateInput, document.getElementById("symptom-intensity")]
  );

  // -------------------------
  // Analysis plots
  // -------------------------
  document.getElementById("update-plot-btn").addEventListener("click", async () => {
    const allergenName = allergenIntInput.value || "Dairy";

    try {
      const res = await fetch(`${API_URL}/analysis/intensity-volume?allergen_name=${allergenName}`,{
        headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` }
      });
      if (!res.ok) throw new Error(res.statusText);
      const blob = await res.blob();
      intensityVolumePlotImg.src = URL.createObjectURL(blob);
    } catch (err) {
      console.error(err);
    }
  });

  const fetchAnalysisPlot = async () => {
    try {
      const statsRes = await fetch(`${API_URL}/analysis/stats`, {
        headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` }
      });
      if (!statsRes.ok) throw new Error(statsRes.statusText);
      const stats = await statsRes.json();

      document.getElementById("stat-total-entries").textContent =
        stats["Total allergens logged"] + stats["Total symptoms logged"];
      document.getElementById("stat-days").textContent =
        stats["Total days tracked"];

      const plotRes = await fetch(`${API_URL}/analysis/plot-eda`, {
        headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` }
      });
      if (!plotRes.ok) throw new Error(plotRes.statusText);
      const blob = await plotRes.blob();
      analysisPlotImg.src = URL.createObjectURL(blob);
    } catch (err) {
      console.error(err);
    }
  };

  // -------------------------
  // Tabs
  // -------------------------
  document.querySelectorAll(".tab").forEach(tab => {
    tab.addEventListener("click", () => {
      const target = tab.dataset.tab;
      document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
      tab.classList.add("active");
      document.querySelectorAll(".form").forEach(f => f.classList.remove("active"));
      document.getElementById(`${target}-form`).classList.add("active");
      if (target === "analysis") fetchAnalysisPlot();
    });
  });

  // -------------------------
  // Init user
  // -------------------------
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
