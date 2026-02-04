import { getCurrentUser, API_URL } from "./api.js";

let currentUser = null;

document.addEventListener("DOMContentLoaded", async () => {
  // Check authentication on page load
  if (!localStorage.getItem("access_token")) {
    window.location.href = "index.html";
    return;
  }

  // Set current date/time for forms
  const localDateTimeForInput = (date = new Date()) => {
    const tzOffset = date.getTimezoneOffset() * 60000;
    return new Date(date.getTime() - tzOffset).toISOString().slice(0, 16);
  };

  // Elements
  const logoutBtn = document.getElementById("logout-btn");
  const allergenForm = document.getElementById("allergen-form");
  const allergenSelect = document.getElementById("allergen-select");
  const unitSelect = document.getElementById("allergen-unit");
  const allergenDateInput = document.getElementById("allergen-date");
  const allergenQuantity = document.getElementById("allergen-quantity");
  const allergenSuccess = document.getElementById("log-success");
  const allergenError = document.getElementById("log-error");

  // Set initial values
  if (allergenDateInput) {
    allergenDateInput.value = localDateTimeForInput();
  }

  // Check authentication and get current user
  const init = async () => {
    try {
      const token = localStorage.getItem("access_token");
      if (!token) {
        window.location.href = "index.html";
        return;
      }

      // Get current user
      try {
        currentUser = await getCurrentUser();
        if (currentUser && currentUser.email) {
          document.getElementById("user-email").textContent = currentUser.email;
        } else {
          throw new Error("No user data received");
        }
      } catch (error) {
        console.error("Auth error:", error);
        logout();
        return;
      }

      // Load initial data
      await loadAllergens();
      await loadUnits();
      await populateAllergens();

      setupEventListeners();
      setupTabs();
      
      // Show the content now that we're logged in
      document.body.classList.remove("loading");
      
    } catch (error) {
      console.error("Initialization error:", error);
      logout();
    }
  };

  // Fetch allergens and populate dropdown
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
        if (response.status === 401) {
          logout();
          return;
        }
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const allergens = await response.json();
      return allergens;
    } catch (error) {
      console.error('Error fetching allergens:', error);
      throw error;
    }
  };

  // Load allergens into dropdown
  const populateAllergens = async () => {
    try {
      const allergens = await fetchAllergens();
      const select = document.getElementById('allergen-select');
      if (select) {
        // Clear existing options except the first option
        select.innerHTML = '<option value="" selected disabled>Select an allergen...</option>';
        
        allergens.forEach(allergen => {
          if (allergen && allergen.allergen_name && allergen.allergen_id) {
            const option = document.createElement('option');
            option.value = allergen.allergen_id;
            option.textContent = allergen.allergen_name;
            select.appendChild(option);
          }
        });
      }
    } catch (error) {
      console.error('Error loading allergens:', error);
      alert('Failed to load allergens. Please refresh the page.');
    }
  };

  // Load units into dropdown
  const loadUnits = async () => {
    try {
      const token = localStorage.getItem("access_token");
      const response = await fetch(`${API_URL}/units`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      
      if (response.ok) {
        const units = await response.json();
        const select = document.getElementById('unit-select');
        if (select) {
          // Clear and populate unit dropdown
          while (select.firstChild) {
            select.removeChild(select.firstChild);
          }
          
          // Add default option
          const defaultOption = document.createElement('option');
          defaultOption.value = '';
          defaultOption.textContent = 'Select unit...';
          defaultOption.disabled = true;
          defaultOption.selected = true;
          select.appendChild(defaultOption);
          
          // Add unit options
          units.forEach(unit => {
            if (unit.unit_name) {
              const option = document.createElement('option');
              option.value = unit.unit_id;
              option.textContent = unit.unit_name;
              select.appendChild(option);
            }
          });
        }
      }
    } catch (error) {
      console.error('Error loading units:', error);
    }
  };

  // Setup event listeners
  const setupEventListeners = () => {
    if (logoutBtn) {
      logoutBtn.addEventListener('click', logout);
    }

    // Allergen form submission
    if (allergenForm) {
      allergenForm.addEventListener('submit', handleAllergenSubmit);
    }
  };

  // Handle allergen form submission
  const handleAllergenSubmit = async (event) => {
    event.preventDefault();
    
    const allergenId = allergenSelect.value;
    const unitId = unitSelect.value;
    const quantity = allergenQuantity.value || null;
    const dateTime = allergenDateInput.value;

    if (!allergenId || isNaN(allergenId)) {
      showError("Please select an allergen.");
      return;
    }

    try {
      const token = localStorage.getItem("access_token");
      const response = await fetch(`${API_URL}/entries/allergens`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          allergen_id: parseInt(allergenId),
          quantity: quantity ? parseFloat(quantity) : null,
          unit_id: unitId || null,
          date_time: new Date(dateTime).toISOString()
        })
      });

      if (response.ok) {
        // Clear form and show success message
        allergenForm.reset();
        allergenSuccess.style.display = 'block';
        allergenError.style.display = 'none';
        
        // Reset form time to now
        if (allergenDateInput) {
          allergenDateInput.value = new Date().toISOString().slice(0, 16);
        }
      } else {
        throw new Error('Failed to log allergen');
      }
    } catch (error) {
      console.error('Error logging allergen:', error);
      showError('Error logging allergen. Please try again.');
    }
  };

  const showError = (message) => {
    if (allergenError) {
      allergenError.textContent = message;
      allergenError.style.display = 'block';
    }
  };

  const setupTabs = () => {
    const tabButtons = document.querySelectorAll('.tab');
    tabButtons.forEach(button => {
      button.addEventListener('click', (e) => {
        const tabId = e.target.dataset.tab;
        showTab(tabId);
      });
    });
  };

  const showTab = (tabName) => {
    // Hide all tab content
    document.querySelectorAll('.tab-content').forEach(tab => {
      tab.style.display = 'none';
    });
    
    // Show selected tab content
    const activeTab = document.getElementById(`${tabName}-tab`);
    if (activeTab) {
      activeTab.style.display = 'block';
    }
  };

  const logout = () => {
    localStorage.removeItem("access_token");
    window.location.href = "index.html";
  };

  // Initialize application
  init();

  // Setup tabs
  setupTabs();
});