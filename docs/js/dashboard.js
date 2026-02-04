import { getCurrentUser, API_URL } from "./api.js";

document.addEventListener("DOMContentLoaded", async () => {
  await init();

  // =========================================================
  // Elements
  // =========================================================

  const logoutBtn = document.getElementById("logout-btn");
  const dateInput = document.getElementById("allergen-date");
  const allergenSelect = document.getElementById("allergen-select");
  const unitSelect = document.getElementById("allergen-unit");
  const allergenQuantity = document.getElementById("allergen-quantity");
  
  const allergenIntInput = document.getElementById("allergen-intensity-input");
  const allergenIntIdInput = document.getElementById("allergen-intensity-id");
  const symptomGroupInput = document.getElementById("symptom-group-input");
  const lagWindowInput = document.getElementById("lag-window");

  // ... (keep your existing element declarations, but REMOVE the old allergenInput, allergenIdInput)

  // Remove or comment out the old allergen input elements that conflict
  // const allergenInput = document.getElementById("allergen-input");
  // const allergenIdInput = document.getElementById("allergen-id");

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
  
  const localDateTimeForInput = (date = new Date()) => {
    const tzOffsetMs = date.getTimezoneOffset() * 60000;
    const localTime = new Date(date.getTime() - tzOffsetMs);
    return localTime.toISOString().slice(0, 16);
  };

  if (dateInput) dateInput.value = localDateTimeForInput();

  // =========================================================
  // Fetch and populate allergens
  // =========================================================
  
  async function fetchAndPopulateAllergens() {
    try {
      const res = await fetch(`${API_URL}/allergens`, {
        headers: { 
          Authorization: `Bearer ${localStorage.getItem("access_token")}` 
        }
      });
      
      if (!res.ok) throw new Error('Failed to fetch allergens');
      
      const allergens = await res.json();
      const select = document.getElementById('allergen-select');
      
      // Clear existing options except the first one (placeholder)
      select.innerHTML = '<option value="">Select an allergen...</option>';
      
      allergens.forEach(allergen => {
        const option = document.createElement('option');
        option.value = allergen.allergen_id;
        option.textContent = allergen.allergen_name;
        select.appendChild(option);
      });
    } catch (err) {
      console.error("Failed to fetch allergens:", err);
    }
  }

  // =========================================================
  // Fetch units for the unit dropdown
  // =========================================================
  
  async function fetchAndPopulateUnits() {
    try {
      const res = await fetch(`${API_URL}/units`, {
        headers: { 
          Authorization: `Bearer ${localStorage.getItem("access_token")}` 
        }
      });
      
      if (!res.ok) throw new Error('Failed to fetch units');
      
      const units = await res.json();
      unitSelect.innerHTML = '<option value="">Select unit...</option>';
      
      units.forEach(unit => {
        const option = document.createElement('option');
        option.value = unit.unit_id;
        option.textContent = unit.unit_name;
        unitSelect.appendChild(option);
      });
    } catch (err) {
      console.error("Failed to fetch units:", err);
    }
  }

  // =========================================================
  // Allergen Form Submission
  // =========================================================
  
  async function handleAllergenFormSubmit(e) {
    e.preventDefault();
    
    const allergenId = document.getElementById('allergen-select').value;
    const quantity = document.getElementById('allergen-quantity').value;
    const date = document.getElementById('allergen-date').value;
    const unitId = document.getElementById('allergen-unit').value;
    
    if (!allergenId) {
      alert('Please select an allergen');
      return;
    }
    
    try {
      const payload = {
        allergen_id: parseInt(allergenId),
        date_time: new Date(date).toISOString(),
        quantity: quantity ? parseFloat(quantity) : null,
        unit_id: unitId ? parseInt(unitId) : null
      };
      
      const res = await fetch(`${API_URL}/entries/allergens`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${localStorage.getItem("access_token")}`
        },
        body: JSON.stringify(payload)
      });
      
      if (res.ok) {
        alert('Allergen logged successfully!');
        document.getElementById('allergen-form').reset();
        // Reset allergen select to placeholder
        document.getElementById('allergen-select').selectedIndex = 0;
      } else {
        throw new Error('Failed to log allergen');
      }
    } catch (err) {
      console.error('Error:', err);
      alert('Error logging allergen');
    }
  }

  // =========================================================
  // Initialize
  // =========================================================
  
  async function init() {
    if (!localStorage.getItem("access_token")) {
      window.location.href = "index.html";
      return;
    }

    try {
      const user = await getCurrentUser();
      document.getElementById("user-email").textContent = user.email;
      
      // Initialize forms and data
      await fetchAndPopulateAllergens();
      await fetchAndPopulateUnits();
      
      // Set default date to now
      if (dateInput) {
        dateInput.value = localDateTimeForInput();
      }
      
      // Event listeners
      const allergenForm = document.getElementById('allergen-form');
      if (allergenForm) {
        allergenForm.addEventListener('submit', handleAllergenFormSubmit);
      }
      
      // Load initial analysis data if on analysis tab
      if (window.location.hash === '#analysis') {
        await fetchAnalysisPlot();
      }
      
    } catch (err) {
      localStorage.removeItem("access_token");
      window.location.href = "index.html";
    }
  }

  // =========================================================
  // The rest of your existing code for tabs, analysis, etc. goes here
  // Keep all your existing analysis and other functions...
  // =========================================================

  // Initialize everything
  init();
});