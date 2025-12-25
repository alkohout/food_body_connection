const API_URL = "http://54.253.73.35:8000";

document.getElementById("login-form").addEventListener("submit", async (e) => {
  e.preventDefault();

  const email = document.getElementById("email").value;
  const password = document.getElementById("password").value;

  const response = await fetch(`${API_URL}/auth/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ email, password })
  });

  if (!response.ok) {
    document.getElementById("error").textContent = "Login failed";
    return;
  }

  const data = await response.json();
  console.log("Logged in:", data);
});
