// docs/js/tabs.js

const tabs = document.querySelectorAll(".tab");
const forms = document.querySelectorAll(".form");

tabs.forEach(tab => {
  tab.addEventListener("click", () => {
    tabs.forEach(t => t.classList.remove("active"));
    forms.forEach(f => f.classList.remove("active"));

    tab.classList.add("active");
    document
      .querySelector(`#${tab.dataset.tab}-form`)
      .classList.add("active");
  });
});

