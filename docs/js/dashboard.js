import { getCurrentUser, API_URL } from "./api.js";

// Store the current user
let currentUser = null;

document.addEventListener("DOMContentLoaded", async () => {
  console.log("Dashboard script loading...");
  
  // Store all variables at the top level to avoid "not defined" errors
  let currentUser = null;
  
  const init = async () => {
    console.log("Initializing dashboard...");
    
    // Check authentication
    const token = localStorage.getItem("access_token");
    if (!token) {
      console.warn("No access token found, redirecting to login");
      window.location.href = "index.html";
      return;
    }

    // Initialize the app
    await checkAuthAndInit();
  };

  const checkAuthAndInit = async () => {
    try {
      console.log("Fetching current user...");
      currentUser = await getCurrentUser();
      console.log("Current user:", currentUser);
      
      if (currentUser && currentUser.email) {
        document.getElementById("user-email").textContent = currentUser.email;
        console.log("User authenticated:", currentUser.email);
        await initDashboard();
      } else {
        console.warn("No user data, redirecting to login");
        window.location.href = "index.html";
      }
    } catch (error) {
      console.error("Auth error:", error);
      localStorage.removeItem("access_token");
      window.location.href = "index.html";
    }
  };

  const fetchAllergensDropdown = async () => {
    const allergenSelect = document.getElementById('allergen-select');
    if (!allergenSelect) {
      console.error("Allergen select element not found!");
      return;
    }
    
    try {
      const res = await fetch(`${API_URL}/allergens`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        }
      });
      
      if (res.ok) {
        const allergens = await res.json();
        console.log("Fetched allergens:", allergens);
        
        // Add a default "Select allergen..." option
        allergenSelect.innerHTML = '<option value="">Select an allergen...</option>';
        
        allergens.forEach(allergen => {
          const option = document.createElement('option');
          option.value = allergen.allergen_id;
          option.textContent = allergen.allergen_name;
          allergenSelect.appendChild(option);
        });
      } else {
        console.error('Failed to fetch allergens:', res.status);
      }
    } catch (error) {
      console.error('Error fetching allergens:', error);
    }
  };

  const fetchUnits = async () => {
    const unitSelect = document.getElementById('unit-select');
    if (!unitSelect) {
      console.warn('Unit select element not found');
      return;
    }
    
    try {
      const res = await fetch(`${API_URL}/units`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        }
      });
      
      if (res.ok) {
        const units = await res.json();
        // Keep the placeholder
        unitSelect.innerHTML = '<option value="">Select unit...</option>';
        
        units.forEach(unit => {
          const option = document.createElement('option');
          option.value = unit.unit_id;
          option.textContent = unit.unit_name || unit.name;
          unitSelect.appendChild(option);
        });
      }
    } catch (error) {
      console.error('Error fetching units:', error);
    }
  };

  const setupAllergenForm = () => {
    const form = document.getElementById('allergen-form');
    const allergenSelect = document.getElementById('allergen-select');
    const quantityInput = document.getElementById('allergen-quantity');
    const unitSelect = document.getElementById('unit-select');
    const dateInput = document.getElementById('allergen-date');
    const submitBtn = form.querySelector('button[type="submit"]');
    const successMsg = document.getElementById('log-success');
    const errorMsg = document.getElementById('log-error');

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      
      const formData = {
        allergen_id: allergenSelect.value,
        quantity: parseFloat(quantityInput.value) || null,
        unit_id: unitSelect.value,
        date_time: new Date(dateInput.value).toISOString()
      };
      
      try {
        const res = await fetch(`${API_URL}/entries/allergens`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${localStorage.getItem('access_token')}`
          },
          body: JSON.stringify(formData)
        });
        
        if (res.ok) {
          // Show success message
          successMsg.textContent = 'Allergen logged successfully!';
          errorMsg.textContent = '';
          
          // Reset form
          form.reset();
          
          // Hide success message after 3 seconds
          setTimeout(() => {
            successMsg.textContent = '';
          }, 3000);
          
        } else {
          const errorText = await res.text();
          errorMsg.textContent = `Error: ${errorText}`;
          successMsg.textContent = '';
        }
      } catch (error) {
        console.error('Error submitting form:', error);
        errorMsg.textContent = 'Failed to submit. Please try again.';
        successMsg.textContent = '';
      }
    });
  };

  const fetchAndPopulateSymptoms = async () => {
    try {
      const res = await fetch(`${API_URL}/symptoms`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        }
      });
      
      if (res.ok) {
        const symptoms = await res.json();
        const symptomSelect = document.getElementById('symptom-select');
        
        symptomSelect.innerHTML = '<option value="">Select symptom...</option>';
        symptoms.forEach(symptom => {
          const option = document.createElement('option');
          option.value = symptom.symptom_id;
          option.textContent = symptom.symptom_name;
          symptomSelect.appendChild(option);
        });
      }
    } catch (error) {
      console.error('Error fetching symptoms:', error);
    }
  };

  const setupTabs = () => {
    const tabs = document.querySelectorAll('.tab');
    tabs.forEach(tab => {
      tab.addEventListener('click', (e) => {
        const targetTab = e.target.dataset.tab;
        
        // Remove active class from all tabs and forms
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.form').forEach(f => f.classList.remove('active'));
        
        // Add active class to clicked tab and corresponding form
        e.target.classList.add('active');
        document.getElementById(`${targetTab}-form`).classList.add('active');
        
        // Fetch data for analysis tab if needed
        if (targetTab === 'analysis') {
          loadAnalysisData();
        }
      });
    });
  };

  const loadAnalysisData = async () => {
    try {
      // Fetch analysis data if needed
      const summaryResponse = await fetch(`${API_URL}/analysis/summary`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        }
      });
      
      if (summaryResponse.ok) {
        const summaryData = await summaryResponse.json();
        // Populate summary statistics
        // ... (your existing summary logic)
      }
    } catch (error) {
      console.error('Error loading analysis data:', error);
    }
  };

  const initializeDashboard = async () => {
    try {
      // Load allergens and units for form
      await fetchAllergens();
      await fetchUnits();
      
      // Set current date for forms
      const now = new Date();
      const timezoneOffset = now.getTimezoneOffset() * 60000; // Offset in milliseconds
      const localISOTime = new Date(Date.now() - timezoneOffset).toISOString().slice(0, 16);
      
      const dateInputs = document.querySelectorAll('input[type="datetime-local"]');
      dateInputs.forEach(input => {
        input.value = localISOTime;
      });

      // Setup form event listeners
      setupAllergenForm();
      
      // Setup tabs
      setupTabs();
      
      // Initialize analysis data if on analysis tab
      if (document.getElementById('analysis-form')?.classList.contains('active')) {
        await fetchAnalysisData();
      }
    } catch (error) {
      console.error('Initialization error:', error);
    }
  };

  // Utility function for debouncing
  const debounce = (fn, delay = 300) => {
    let timer;
    return (...args) => {
      clearTimeout(timer);
      timer = setTimeout(() => fn(...args), delay);
    };
  };

  // Initialize on DOMContentLoaded
  init();
});