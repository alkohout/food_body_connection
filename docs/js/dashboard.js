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

  //const analysisPlotImg = document.getElementById("analysis-plot");
  const histogramPlotImg = document.getElementById("group_histogram");
  const allergenrankPlotImg = document.getElementById("allergenrank-plot");
  const intensityVolumePlotImg = document.getElementById("analysis-intensity-volume-plot");
  const timeSeriesPlotImg = document.getElementById("analysis-time-series-plot");
  const barPlotImg = document.getElementById("analysis-bar-plot");
  const riskPlotImg = document.getElementById("analysis-risk-plot");

  const predictOut = document.getElementById("predict-out");

  //const statsTableBody = document.querySelector("#temporal-stats-table tbody");

  document.getElementById("caption-allergen").textContent =
  document.getElementById("allergen-intensity-input").value;

  document.getElementById("caption-symptom-group").textContent =
  document.getElementById("symptom-group-input").value;

  document.getElementById("caption-lag").textContent =
  document.getElementById("lag-window").selectedOptions[0].text;


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
  // Autocomplete
  // =========================================================

  const fetchSuggestions = async (query, type) => {
    if (!query) return [];

    const endpoint =
      type === "allergen" ? "allergens" :
      type === "symptom_group" ? "symptom_groups" :
      type === "symptom"  ? "symptoms"  :
                            "allergens";

    const res = await fetch(
      `${API_URL}/${endpoint}?q=${encodeURIComponent(query)}`,
      { headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` } }
    );

    if (!res.ok) return [];
    return await res.json();
  };

  const setupAutocomplete = (inputEl, idEl, suggestionsEl, type) => {
    if (!inputEl) return;

    inputEl.addEventListener("input", debounce(async () => {
      const query = inputEl.value.trim();

      // ONLY clear idEl if it exists
      if (idEl !== null && idEl !== undefined) idEl.value = "";

      // clear suggestions
      suggestionsEl.innerHTML = "";

      if (!query) return;

      const data = await fetchSuggestions(query, type);

      data.forEach(item => {
        const li = document.createElement("li");
        li.textContent =
          type === "symptom" ? item.symptom_name :
          type === "symptom_group" ? item.symptom_group : // just the string
          item.allergen_name;

        li.addEventListener("click", () => {
          inputEl.value = li.textContent;

          // ONLY set idEl if it exists and the type is not symptom_group
          if (idEl !== null && idEl !== undefined && type !== "symptom_group") {
            idEl.value = type === "symptom" ? item.symptom_id : item.allergen_id;
          }

          suggestionsEl.innerHTML = "";
        });

        suggestionsEl.appendChild(li);
      });
    }, 300));
  };

  setupAutocomplete(allergenInput, allergenIdInput, allergenSuggestions, "allergen");
  setupAutocomplete(symptomInput, symptomIdInput, symptomSuggestions, "symptom");
  setupAutocomplete(allergenIntInput, allergenIntIdInput, allergenIntSuggestions, "allergen");
  setupAutocomplete(symptomGroupInput, null, symptomGroupSuggestions, "symptom_group");


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

        successEl.textContent = "Logged successfully!";
        errorEl.textContent = "";
        resetFields.forEach(f => f.value = "");
      } catch (err) {
        errorEl.textContent = `Error: ${err.message}`;
      }
    });
  };

  // =========================================================
  // Allergen form
  // =========================================================

  submitForm(
    document.getElementById("allergen-form"),
    "entries/allergens",
    () => ({
      allergen_id: Number(allergenIdInput.value),
      date_time: new Date(dateInput.value).toISOString(),
      quantity: Number(document.getElementById("allergen-quantity").value) || null,
      unit_id: Number(unitSelect.value) || null
    }),
    document.getElementById("log-success"),
    document.getElementById("log-error"),
    [allergenInput, allergenIdInput, dateInput, document.getElementById("allergen-quantity")]
  );

  // =========================================================
  // Symptom form
  // =========================================================

  submitForm(
    document.getElementById("symptom-form"),
    "entries/symptoms",
    () => ({
      symptom_id: Number(symptomIdInput.value),
      date_time: new Date(symptomDateInput.value).toISOString(),
      intensity: Number(document.getElementById("symptom-intensity").value) || null
    }),
    document.getElementById("symptom-success"),
    document.getElementById("symptom-error"),
    [symptomInput, symptomIdInput, symptomDateInput]
  );

  // =========================================================
  // Analysis
  // =========================================================

  const fetchTemporalStats = async (allergenName) => {
    //try {
      const res = await fetch(
        `${API_URL}/analysis/temporal_stats?allergen_name=${encodeURIComponent(allergenName)}`,
        { headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` } }
      );

      if (!res.ok) throw new Error(res.statusText);
      const data = await res.json();
  };

      //statsTableBody.innerHTML = "";

      //if (statsTableBody){
      //  if (!data.length) {
      //    statsTableBody.innerHTML =
      //      `<tr><td colspan="7" style="text-align:center">No significant relationships found.</td></tr>`;
      //    return;
      //  }

      //  const formatP = p =>
      //    p === null ? "—" :
      //    p < 1e-4 ? "0.0000" :
      //    p.toFixed(4);

      //  data.forEach(row => {
      //    const tr = document.createElement("tr");

      //    tr.innerHTML = `
      //      <td>${row.allergen_name}</td>
      //      <td>${row.symptom_group}</td>
      //      <td>${row.post_count}</td>
      //      <td>${row.pre_count}</td>
      //      <td>${formatP(row.p_value)}</td>
      //      <td>${row.evidence}</td>
      //    `;

      //    statsTableBody.appendChild(tr);
      //  });

    //} catch (err) {
    //  console.error(err);
    //  statsTableBody.innerHTML =
    //    `<tr><td colspan="7" style="color:red;text-align:center">Failed to load data</td></tr>`;
    //}

  document.getElementById("update-plot-btn")?.addEventListener("click", async () => {

    const allergenName = allergenIntInput.value || "Dairy";
    //const lagWindow = lagWindowInput.value || "0_6";
    const lagWindow = lagWindowInput.value;
    const LAG_WINDOWS = {
      "0_6":  { start: 0,  end: 6 },
      "6_24": { start: 6,  end: 24 },
      "24_48":{ start: 24, end: 48 },
      "0_24":{ start: 0, end: 24 },
      "0_48":{ start: 0, end: 48 },
      "0_72":{ start: 0, end: 72 }
    };
    const { start, end } = LAG_WINDOWS[lagWindow];
    const symptomGroup = symptomGroupInput.value
    const lagWindowText = '${start} - ${end} hrs'

    updateCaptions(allergenName, symptomGroup, lagWindowText);

    try {
 
      const cacheBust = Date.now();

      const res = await fetch(
        `${API_URL}/analysis/intensity_volume` +
        `?allergen_name=${encodeURIComponent(allergenName)}` +
        `&lag_start=${start}&lag_end=${end}` +
        `&_=${cacheBust}`,
        {
          headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` },
          cache: "no-store"
        }
      );

      const blob = await res.blob();
      if (intensityVolumePlotImg.src) {
        URL.revokeObjectURL(intensityVolumePlotImg.src);
      }
      intensityVolumePlotImg.src = URL.createObjectURL(blob);


      const res_ts = await fetch(
        `${API_URL}/analysis/plot_time_series?allergen_name=${encodeURIComponent(allergenName)}`,
        {
          headers: {
            Authorization: `Bearer ${localStorage.getItem("access_token")}`
          }
        }
      );
      if (!res_ts.ok) throw new Error(res_ts.statusText);
        const blob_ts = await res_ts.blob();
        timeSeriesPlotImg.src = URL.createObjectURL(blob_ts);
      
      const res_bp = await fetch(
        `${API_URL}/analysis/plot_bar_plots` +
        `?allergen_name=${encodeURIComponent(allergenName)}` +
        `&lag_start=${start}&lag_end=${end}` +
        `&symptom_group=${encodeURIComponent(symptomGroup)}` +
        `&_=${cacheBust}`,
        {
          headers: {
            Authorization: `Bearer ${localStorage.getItem("access_token")}`
          }
        }
      );
      if (!res_bp.ok) throw new Error(res_bp.statusText);
        const blob_bp = await res_bp.blob();
        if (barPlotImg.src) {
          URL.revokeObjectURL(barPlotImg.src);
        }
        barPlotImg.src = URL.createObjectURL(blob_bp);
      
      const res_r = await fetch(
        `${API_URL}/analysis/plot_risk` +
        `?allergen_name=${encodeURIComponent(allergenName)}` +
        `&lag_start=${start}&lag_end=${end}` +
        `&symptom_group=${encodeURIComponent(symptomGroup)}` +
        `&_=${cacheBust}`,
        {
          headers: {
            Authorization: `Bearer ${localStorage.getItem("access_token")}`
          }
        }
      );
      if (!res_r.ok) throw new Error(res_r.statusText);
        const blob_r = await res_r.blob();
        if (riskPlotImg.src) {
          URL.revokeObjectURL(riskPlotImg.src);
        }
        riskPlotImg.src = URL.createObjectURL(blob_r);
      
    } catch (err) {
      console.error(err);
    }
    await fetchTemporalStats(allergenName);
  });

  const fetchAnalysisPlot = async () => {
  try {
    // Stats
    const statsRes = await fetch(`${API_URL}/analysis/stats`, {
      headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` }
    });

    if (!statsRes.ok) throw new Error(statsRes.statusText);
    const stats = await statsRes.json();

    document.getElementById("stat-total-entries").textContent =
      stats["Total allergens logged"] + stats["Total symptoms logged"];

    document.getElementById("stat-days").textContent =
      stats["Total days tracked"];

    // Symptom rate Plot
    //const plotRes = await fetch(`${API_URL}/analysis/plot_eda`, {
    //  headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` }
    //});

    //if (!plotRes.ok) throw new Error(plotRes.statusText);
    //const blob = await plotRes.blob();
    //analysisPlotImg.src = URL.createObjectURL(blob);

    // Symptom Histogram Plot 
    const group_hist = await fetch(`${API_URL}/analysis/system_group_histogram`, {
      headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` }
    });

    if (!group_hist.ok) throw new Error(group_hist.statusText);
    const blob_hist = await group_hist.blob();
    histogramPlotImg.src = URL.createObjectURL(blob_hist);

    // Allergen Rank Plot 
    const plotAllergenRank = await fetch(`${API_URL}/analysis/plot_allergen_rank`, {
      headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` }
    });

    if (!plotAllergenRank.ok) throw new Error(plotAllergenRank.statusText);
    const blobAllergenRank = await plotAllergenRank.blob();
    allergenrankPlotImg.src = URL.createObjectURL(blobAllergenRank);

    // Model Predict output 
    const predict = await fetch(`${API_URL}/analysis/predict`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${localStorage.getItem("access_token")}`
      }
    });

    if (!predict.ok) throw new Error(predict.statusText);

    const predictionText = await predict.text();
    if (predictOut){
      predictOut.textContent = predictionText;
    }


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
      document.getElementById(`${target}-form`).classList.add("active");

      if (target === "analysis") fetchAnalysisPlot();
    });
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
      document.getElementById("user-email").textContent = user.email;
    } catch {
      localStorage.removeItem("access_token");
      window.location.href = "index.html";
    }
  }
});


function updateCaptions(allergenName, symptomGroup, lagText) {

  document.getElementById("caption-allergen").textContent = allergenName;
  document.getElementById("caption-symptom-group").textContent = symptomGroup;
  document.getElementById("caption-lag").textContent = lagText;
}



