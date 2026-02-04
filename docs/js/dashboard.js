import { getCurrentUser, API_URL } from "./api.js";

// Store a reference to the initialization promise to avoid multiple inits
let initializationStarted = false;

document.addEventListener("DOMContentLoaded", async () => {
  // Only initialize once
  if (initializationStarted) return;
  initializationStarted = true;
  
  await init();
  
  // =========================================================
  // Elements
  // =========================================================
  
  const logoutBtn = document.getElementById("logout-btn");
  const dateInput = document.getElementById("allergen-date");
  const unitSelect = document.getElementById("allergen-unit");
  const allergenSelect = document.getElementById("allergen-select");
  const symptomInput = document.getElementById("symptom-input");
  const allergenIntInput = document.getElementById("allergen-intensity-input");
  const symptomGroupInput = document.getElementById("symptom-group-input");
  const lagWindowInput = document.getElementById("lag-window");

  const fetchAndPopulateAllergens = async () => {
    try {
      const res = await fetch(`${API_URL}/allergens`, {
        headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` }
      });
      
      if (!res.ok) {
        if (res.status === 422) {
          // Some APIs might require query parameters or have changed
          const res2 = await fetch(`${API_URL}/allergens?q=`, {
            headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` }
          });
          
          if (res2.ok) {
            const allergens = await res2.json();
            populateAllergenDropdown(allergens);
          } else {
            console.error("Failed to fetch allergens");
          }
        }
      } else {
        const allergens = await res.json();
        populateAllergenDropdown(allergens);
      }
    } catch (err) {
      console.error("Error fetching allergens:", err);
    }
  };
  
  const populateAllergenDropdown = (allergens) => {
    // Clear existing options except the first one
    while (allergenSelect.options.length > 1) {
      allergenSelect.remove(1);
    }
    
    allergens.forEach(allergen => {
      const option = document.createElement("option");
      option.value = allergen.allergen_id;
      option.textContent = allergen.allergen_name;
      allergenSelect.appendChild(option);
    });
  };
  
  // Initialize the date inputs
  if (dateInput) {
    const now = new Date();
    const offset = now.getTimezoneOffset() * 60000;
    const localISOTime = new Date(now - offset).toISOString().slice(0, 16);
    dateInput.value = localISOTime.slice(0, 16);
  }

  // =========================================================
  // Fetch Allergens for dropdown
  // =========================================================
  await fetchAndPopulateAllergens();

  // =========================================================
  // Fetch Units for unit dropdown
  // =========================================================
  const fetchUnits = async () => {
    try {
      const res = await fetch(`${API_URL}/units`, {
        headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` }
      });
      
      if (res.ok) {
        const units = await res.json();
        // Clear existing options except first one
        while (unitSelect.options.length > 1) {
          unitSelect.remove(1);
        }
        
        units.forEach(unit => {
          const option = document.createElement("option");
          option.value = unit.unit_id;
          option.textContent = unit.unit_name;
          unitSelect.appendChild(option);
        });
      }
    } catch (err) {
      console.error("Failed to fetch units:", err);
    }
  };
  
  await fetchUnits();

  // =========================================================
  // Event Listeners
  // =========================================================

  // Logout
  if (logoutBtn) {
    logoutBtn.addEventListener("click", () => {
      localStorage.removeItem("access_token");
      window.location.href = "index.html";
    });
  }

  // Form Submission Handler
  const submitForm = async (formElement, endpoint, payload) => {
    try {
      const res = await fetch(`${API_URL}/${endpoint}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${localStorage.getItem("access_token")}`
        },
        body: JSON.stringify(payload)
      });
      
      if (!res.ok) throw new Error('Submission failed');
      alert('Logged successfully!');
      formElement.reset();
    } catch (err) {
      alert('Error submitting form');
    }
  };

  // Allergen Form Submission
  const allergenForm = document.getElementById('allergen-form');
  if (allergenForm) {
    allergenForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      
      const payload = {
        allergen_id: parseInt(allergenSelect.value),
        date_time: new Date(dateInput.value).toISOString(),
        quantity: document.getElementById('allergen-quantity').value ? 
                 parseFloat(document.getElementById('allergen-quantity').value) : null,
        unit_id: unitSelect.value ? parseInt(unitSelect.value) : null
      };
      
      await submitForm(allergenForm, 'entries/allergens', payload);
    });
  }

  // =========================================================
  // Initialize
  // =========================================================
  
  async function init() {
    const token = localStorage.getItem("access_token");
    if (!token) {
      window.location.href = "index.html";
      return;
    }

    try {
      const user = await getCurrentUser();
      if (!user || !user.email) {
        throw new Error('Invalid user session');
      }
      document.getElementById("user-email").textContent = user.email;
    } catch (error) {
      console.error('Init error:', error);
      localStorage.removeItem("access_token");
      window.location.href = "index.html";
    }
  }

  await init();

  // Tabs functionality
  document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
      const targetTab = tab.dataset.tab;
      
      // Update tab classes
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      
      // Show target form
      document.querySelectorAll('.form').forEach(form => form.classList.remove('active'));
      document.getElementById(targetTab + '-form').classList.add('active');
    });
  });
});