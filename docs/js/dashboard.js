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
  const unitSelect = document.getElementById("allergen-unit"); // Make sure this matches your HTML
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
          const userEmailEl = document.getElementById("user-email");
          if (userEmailEl) {
            userEmailEl.textContent = currentUser.email;
          }
        } else {
          throw new Error("No user data received");
        }
      } catch (error) {
        console.error("Auth error:", error);
        logout();
        return;
      }

      // Load initial data
      await populateAllergens(); // Removed loadAllergens() call
      await loadUnits();

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
      console.log("Fetching allergens with token:", token ? "Present" : "Missing");
      
      const response = await fetch(`${API_URL}/allergens`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        }
      });

      console.log("Response status:", response.status);
      console.log("Response headers:", [...response.headers.entries()]);

      if (!response.ok) {
        // Try to get error details from response
        let errorDetails;
        try {
          errorDetails = await response.json();
          console.error("Error response body:", errorDetails);
        } catch (e) {
          errorDetails = await response.text();
          console.error("Error response text:", errorDetails);
        }
        
        if (response.status === 401) {
          logout();
          return null;
        }
        
        throw new Error(`HTTP error! status: ${response.status}, details: ${JSON.stringify(errorDetails)}`);
      }

      const allergens = await response.json();
      console.log("Fetched allergens:", allergens);
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
      if (!allergens) return; // Handle case where fetchAllergens returns null due to auth error
      
      if (allergenSelect) {
        // Clear existing options except the first option
        allergenSelect.innerHTML = '<option value="" selected disabled>Select an allergen...</option>';
        
        allergens.forEach(allergen => {
          if (allergen && allergen.allergen_name && allergen.allergen_id) {
            const option = document.createElement('option');
            option.value = allergen.allergen_id;
            option.textContent = allergen.allergen_name;
            allergenSelect.appendChild(option);
          }
        });
      }
    } catch (error) {
      console.error('Error loading allergens:', error);
      showError('Failed to load allergens. Please refresh the page.');
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
        // Use the same element reference as in form submission
        if (unitSelect) {
          // Clear and populate unit dropdown
          unitSelect.innerHTML = '';
          
          // Add default option
          const defaultOption = document.createElement('option');
          defaultOption.value = '';
          defaultOption.textContent = 'Select unit...';
          defaultOption.disabled = true;
          defaultOption.selected = true;
          unitSelect.appendChild(defaultOption);
          
          // Add unit options
          units.forEach(unit => {
            if (unit.unit_name) {
              const option = document.createElement('option');
              option.value = unit.unit_id;
              option.textContent = unit.unit_name;
              unitSelect.appendChild(option);
            }
          });
        }
      } else if (response.status === 401) {
        logout();
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
    
    // Clear previous messages
    if (allergenSuccess) allergenSuccess.style.display = 'none';
    if (allergenError) allergenError.style.display = 'none';
    
    const allergenId = allergenSelect?.value;
    const unitId = unitSelect?.value;
    const quantity = allergenQuantity?.value || null;
    const dateTime = allergenDateInput?.value;

    if (!allergenId || isNaN(allergenId)) {
      showError("Please select an allergen.");
      return;
    }

    if (!dateTime) {
      showError("Please select a date and time.");
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
        if (allergenSuccess) {
          allergenSuccess.style.display = 'block';
        }
        
        // Reset form time to now
        if (allergenDateInput) {
          allergenDateInput.value = localDateTimeForInput();
        }
      } else if (response.status === 401) {
        logout();
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
    if (allergenSuccess) {
      allergenSuccess.style.display = 'none';
    }
  };

  const setupTabs = () => {
    const tabButtons = document.querySelectorAll('.tab');
    tabButtons.forEach(button => {
      button.addEventListener('click', (e) => {
        const tabId = e.target.dataset.tab;
        showTab(tabId);
        
        // Update active tab button
        tabButtons.forEach(btn => btn.classList.remove('active'));
        e.target.classList.add('active');
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
  await init(); // Make sure init completes before continuing
});