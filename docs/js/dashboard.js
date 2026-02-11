import { getCurrentUser, API_URL } from "./api.js";

// Log when this module loads (helps debug script execution order)
console.log("Dashboard module loading...");

// =========================================================
// Helpers
// =========================================================

// Debounce helper to limit how often a function runs (used for autocomplete)
const debounce = (fn, delay = 300) => {
  let timer;
  return (...args) => {
    clearTimeout(timer); // Clear previous timer
    timer = setTimeout(() => fn(...args), delay); // Run after delay
  };
};

// Convert a Date object to a local datetime string formatted for <input type="datetime-local">
const localDateTimeForInput = (date = new Date()) => {
  const tzOffsetMs = date.getTimezoneOffset() * 60000;
  return new Date(date.getTime() - tzOffsetMs).toISOString().slice(0, 16);
};

// Position labels evenly along a range slider based on their data-value
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

// Safely get element by ID (avoids caching stale references)
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

// Wait until DOM fully loads before running init
document.addEventListener("DOMContentLoaded", async () => {
  console.log("DOMContentLoaded fired");
  await init();
});

// =========================================================
// Logout
// =========================================================

// Set up logout button behavior
function setupLogout() {
  const logoutBtn = getElement("logout-btn");
  if (!logoutBtn) return;

  logoutBtn.addEventListener("click", () => {
    localStorage.removeItem("access_token"); // Clear token
    window.location.href = "index.html";     // Redirect to login
  });
}

// =========================================================
// Defaults
// =========================================================

// Set default date/time values for forms
function setupDefaults() {
  const dateInput = getElement("allergen-date");
  const symptomDateInput = getElement("symptom-date");

  if (dateInput) dateInput.value = localDateTimeForInput();
  if (symptomDateInput) symptomDateInput.value = localDateTimeForInput();
}

// =========================================================
// Fetch units
// =========================================================

// Fetch measurement units for allergens (e.g., grams, ml)
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
    
    // Populate <select> with unit options
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

// Fetch full allergen list
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

// Fetch recently used allergens (for quicker selection)
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
    throw new Error("Invalid data format for /allergens/recent: expected array");
  }

  return recentAllergens;
};

// =========================================================
// Populate allergen <select> with recent + all
// =========================================================

// Populate dropdown with grouped recent + full allergen list
const populateAllergenSelect = (allergens, recentAllergens) => {
  const allergenSelect = getElement("allergen-select");
  if (!allergenSelect) return;

  allergenSelect.innerHTML = ""; // Clear existing options

  // Placeholder option
  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = "Select an allergen…";
  allergenSelect.appendChild(placeholder);

  const usedIds = new Set(); // Track recent allergens to avoid duplicates

  // ---- Recent allergens group ----
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

  // Divider line
  if (Array.isArray(allergens) && allergens.length > 0) {
    const divider = document.createElement("option");
    divider.disabled = true;
    divider.textContent = "──────────────";
    allergenSelect.appendChild(divider);
  }

  // ---- All allergens group ----
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