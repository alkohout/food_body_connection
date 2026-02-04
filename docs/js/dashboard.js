import { getCurrentUser, API_URL } from "./api.js";

// Simple logging for debugging
const debugLog = (msg, data) => {
    console.log(`[DEBUG] ${msg}:`, data);
};

document.addEventListener("DOMContentLoaded", async () => {
    let currentUser = null;

    // Helper functions
    const checkAuth = () => {
        const token = localStorage.getItem("access_token");
        if (!token) {
            window.location.href = "index.html";
            return false;
        }
        return true;
    };

    const localDateTimeForInput = (date = new Date()) => {
        const offset = date.getTimezoneOffset();
        const localDate = new Date(date.getTime() - offset * 60 * 1000);
        return localDate.toISOString().slice(0, 16);
    };

    // Initialize
    const init = async () => {
        debugLog("Starting initialization");
        
        const token = localStorage.getItem("access_token");
        if (!token) {
            window.location.href = "index.html";
            return;
        }

        try {
            // Check current user
            currentUser = await getCurrentUser();
            if (currentUser && currentUser.email) {
                document.getElementById("user-email").textContent = currentUser.email;
            } else {
                window.location.href = "index.html";
                return;
            }

            // Initialize data
            await fetchAndPopulateAllergens();
            await fetchAndPopulateUnits();
            setupEventListeners();

        } catch (error) {
            console.error("Initialization error:", error);
            alert("Error initializing dashboard. Please login again.");
            localStorage.removeItem("access_token");
            window.location.href = "index.html";
        }
    };

    const fetchAndPopulateAllergens = async () => {
        debugLog("Fetching allergens");
        try {
            const token = localStorage.getItem("access_token");
            
            // Try the endpoint that's more likely to work - maybe the endpoint expects user_id
            const response = await fetch(`${API_URL}/allergens`, {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            debugLog("Fetch allergens response status:", response.status);
            
            if (!response.ok) {
                // Try a different endpoint or method
                debugLog("Attempting different endpoint or method");
                
                // Maybe the endpoint expects query parameters or different method
                const response = await fetch(`${API_URL}/allergens`, {
                    headers: {
                        'Authorization': `Bearer ${token}`,
                        'Content-Type': 'application/json'
                    }
                });
                
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${await response.text()}`);
                }
            }
            
            const allergens = await response.json();
            debugLog("Allergens data received:", allergens);
            
            const allergenSelect = document.getElementById("allergen-select");
            allergenSelect.innerHTML = '<option value="" disabled selected>Select an allergen...</option>';
            
            if (allergens && allergens.length > 0) {
                allergens.forEach(allergen => {
                    const option = document.createElement("option");
                    option.value = allergen.allergen_id;
                    option.textContent = allergen.allergen_name;
                    allergenSelect.appendChild(option);
                });
            }
        } catch (error) {
            console.error("Error fetching allergens:", error);
            // Try fallback endpoint or show error
        }
    };

    const fetchAndPopulateUnits = async () => {
        debugLog("Fetching units");
        const token = localStorage.getItem("access_token");
        
        try {
            const response = await fetch(`${API_URL}/units`, {
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Accept': 'application/json'
                }
            });
            
            if (!response.ok) {
                throw new Error(`Failed to fetch units: ${response.status}`);
            }
            
            const units = await response.json();
            const unitSelect = document.getElementById("unit-select");
            unitSelect.innerHTML = '<option value="">Select unit...</option>';
            
            units.forEach(unit => {
                const option = document.createElement("option");
                option.value = unit.unit_id;
                option.textContent = unit.unit_name || unit.name || unit.unit_name;
                unitSelect.appendChild(option);
            });
        } catch (error) {
            console.error("Error fetching units:", error);
        }
    };

    const setupEventListeners = () => {
        const logoutBtn = document.getElementById("logout-btn");
        const allergenForm = document.getElementById("allergen-form");
        const tabButtons = document.querySelectorAll(".tab");

        if (logoutBtn) {
            logoutBtn.addEventListener("click", () => {
                localStorage.removeItem("access_token");
                window.location.href = "index.html";
            });
        }

        if (allergenForm) {
            allergenForm.addEventListener("submit", handleAllergenSubmit);
        }

        // Tab switching
        tabButtons.forEach(button => {
            button.addEventListener("click", () => {
                const target = button.dataset.tab;
                switchTab(target);
            });
        });

        // Date initialization
        const dateInputs = document.querySelectorAll('input[type="datetime-local"]');
        dateInputs.forEach(input => {
            const now = new Date();
            const offset = now.getTimezoneOffset();
            const localDate = new Date(now.getTime() - (offset * 60000));
                input.value = localDate.toISOString().slice(0, 16);
        });
    };

    const handleAllergenSubmit = async (e) => {
        e.preventDefault();
        
        const allergenSelect = document.getElementById("allergen-select");
        const quantityInput = document.getElementById("quantity");
        const unitSelect = document.getElementById("unit-select");
        const dateInput = document.getElementById("allergen-date");
        
        const payload = {
            allergen_id: allergenSelect.value,
            quantity: parseFloat(quantityInput.value) || null,
            unit_id: unitSelect.value || null,
            date_time: dateInput.value
        };

        const token = localStorage.getItem("access_token");

        try {
            const response = await fetch(`${API_URL}/entries/allergens`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            alert("Allergen logged successfully!");
            allergenForm.reset();
            
        } catch (error) {
            console.error("Error logging allergen:", error);
            alert("Failed to log allergen. Please try again.");
        }
    };

    const switchTab = (target) => {
        document.querySelectorAll('.tab').forEach(btn => btn.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
        
        document.querySelector(`[data-tab="${target}"]`).classList.add('active');
        document.getElementById(`${target}-tab`).classList.add('active');
    };

    // Main initialization
    init();
});