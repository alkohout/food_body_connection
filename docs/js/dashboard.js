import { getCurrentUser, API_URL } from "./api.js";

document.addEventListener("DOMContentLoaded", async () => {
  // Elements
  const logoutBtn = document.getElementById("logout-btn");
  const allergenSelect = document.getElementById("allergen-select");
  const unitSelect = document.getElementById("allergen-unit");
  const allergenQuantity = document.getElementById("allergen-quantity");
  const dateInput = document.getElementById("allergen-date");
  const allergenForm = document.getElementById("allergen-form");
  const allergenFormSuccess = document.getElementById("log-success");
  const allergenFormError = document.getElementById("log-error");

  // Debounce helper
  const debounce = (fn, delay = 300) => {
    let timer;
    return (...args) => {
      clearTimeout(timer);
      timer = setTimeout(() => fn(...args), delay);
    };
  };

  // Get local date time for input
  const localDateTimeForInput = (date = new Date()) => {
    const tzOffset = date.getTimezoneOffset() * 60000;
    return new Date(date.getTime() - tzOffset).toISOString().slice(0, 16);
  };

  // Initialize
  const init = async () => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      window.location.href = "index.html";
      return;
    }

    try {
      const user = await getCurrentUser();
      if (!user || !user.email) {
        throw new Error("No user data");
      }
      
      document.getElementById("user-email").textContent = user.email;
      
      // Set current date and time for the allergen form
      if (dateInput) {
        dateInput.value = localDateTimeForInput();
      }
      
      // Load data after authentication
      await loadData();
      
      setupEventListeners();
      fetchAnalysisPlots();
      
    } catch (error) {
      console.error("Auth error:", error);
      localStorage.removeItem("access_token");
      window.location.href = "index.html";
    }
  };

  const loadData = async () => {
    // Fetch and populate allergens
    const allergens = await fetchAllergens();
    populateDropdown(allergenSelect, allergens, allergen => ({
      value: allergen.allergen_id,
      text: allergen.allergen_name
    }));
    
    // Fetch and populate units
    const units = await fetchUnits();
    populateDropdown(unitSelect, units, unit => ({
      value: unit.unit_id,
      text: unit.unit_name
    }));
  };

  const fetchAllergens = async () => {
    try {
      const token = localStorage.getItem("access_token");
      const response = await fetch(`${API_URL}/allergens`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });
      
      if (!response.ok) {
        throw new Error('Failed to fetch allergens');
      }
      
      return await response.json();
    } catch (error) {
      console.error('Error fetching allergens:', error);
      return [];
    }
  };

  const fetchUnits = async () => {
    try {
      const token = localStorage.getItem("access_token");
      const response = await fetch(`${API_URL}/units`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });
      
      if (!response.ok) {
        throw new Error('Failed to fetch units');
      }
      
      return await response.json();
    } catch (error) {
      console.error('Error fetching units:', error);
      return [];
    }
  };

  const populateDropdown = (selectElement, data, mapper) => {
    if (!selectElement) return;
    
    // Clear existing options except the first one (if it's a placeholder)
    while (selectElement.options.length > 1) {
      selectElement.remove(1);
    }
    
    data.forEach(item => {
      const mapped = mapper(item);
      const option = document.createElement('option');
      option.value = mapped.value;
      option.textContent = mapped.text;
      selectElement.appendChild(option);
    });
  };

  const populateUnitDropdown = (selectElement, units) => {
    if (!selectElement) return;
    
    // Clear existing options (except first)
    while (selectElement.options.length > 0) {
      selectElement.remove(0);
    }
    
    // Add default option
    const defaultOption = document.createElement('option');
    defaultOption.value = '';
    defaultOption.textContent = 'Select unit...';
    defaultOption.disabled = true;
    defaultOption.selected = true;
    selectElement.appendChild(defaultOption);
    
    // Add unit options
    units.forEach(unit => {
      const option = document.createElement('option');
      option.value = unit.unit_id;
      option.textContent = unit.unit_name;
      selectElement.appendChild(option);
    });
  };

  const handleLogout = () => {
    localStorage.removeItem("access_token");
    window.location.href = "index.html";
  };

  const handleAllergenSubmit = async (e) => {
    e.preventDefault();
    
    const formData = {
      allergen_id: allergenSelect.value,
      date_time: dateInput.value,
      quantity: allergenQuantity.value,
      unit_id: unitSelect.value
    };

    try {
      const response = await fetch(`${API_URL}/entries/allergens`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(formData)
      });
      
      if (!response.ok) throw new Error('Submission failed');
      
      allergenFormSuccess.textContent = 'Allergen logged successfully!';
      allergenFormError.textContent = '';
      
      // Reset form
      allergenSelect.value = '';
      allergenQuantity.value = '';
      unitSelect.value = '';
      dateInput.value = localDateTimeForInput();
      
      // Clear success message after 3 seconds
      setTimeout(() => {
        allergenFormSuccess.textContent = '';
      }, 3000);
      
    } catch (error) {
      allergenFormError.textContent = 'Error logging allergen. Please try again.';
      console.error('Error logging allergen:', error);
    }
  };

  const setupEventListeners = () => {
    // Logout
    if (logoutBtn) {
      logoutBtn.addEventListener('click', handleLogout);
    }
    
    // Allergen form submission
    if (allergenForm) {
      allergenForm.addEventListener('submit', handleAllergenSubmit);
    }
    
    // Tab switching
    document.querySelectorAll('.tab').forEach(tab => {
      tab.addEventListener('click', () => {
        const targetTab = tab.dataset.tab;
        
        // Update active tab button
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        
        // Show/hide forms
        document.querySelectorAll('.form').forEach(form => form.classList.remove('active'));
        document.getElementById(`${targetTab}-form`).classList.add('active');
        
        // Load analysis data if on analysis tab
        if (targetTab === 'analysis') {
          fetchAnalysisPlots();
        }
      });
    });
  };

  const fetchAnalysisPlots = async () => {
    // Your existing analysis plotting code here
    // (Keep your existing analysis plot fetching logic)
  };

  // Initialize everything
  init();
});