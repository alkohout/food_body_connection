// docs/js/tabs.js

// Select all tab buttons
const tabs = document.querySelectorAll(".tab");

// Select all form sections associated with tabs
const forms = document.querySelectorAll(".form");

// Loop through each tab and attach click event listener
tabs.forEach(tab => {
  tab.addEventListener("click", () => {

    // Remove "active" class from all tabs
    tabs.forEach(t => t.classList.remove("active"));

    // Remove "active" class from all forms
    forms.forEach(f => f.classList.remove("active"));

    // Add "active" class to the clicked tab
    tab.classList.add("active");

    // Find the form that matches the tab's data-tab attribute
    // Example: if data-tab="login", it activates #login-form
    document
      .querySelector(`#${tab.dataset.tab}-form`)
      .classList.add("active");
  });
});