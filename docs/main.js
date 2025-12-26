const API_URL = "https://foodbodyconnection.54.253.73.35.nip.io";

document.getElementById("login-form").addEventListener("submit", async (e) => {
  e.preventDefault();

  const email = document.getElementById("email").value;
  const password = document.getElementById("password").value;

  // Clear previous messages
  document.getElementById("error").textContent = "";
  document.getElementById("success").textContent = "";

  try {

    const formData = new URLSearchParams();
        formData.append("username", email); // OAuth2 uses "username"
        formData.append("password", password);

    const response = await fetch(`${API_URL}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: formData,
    });

    if (!response.ok) {
      throw new Error("Invalid email or password");
    }

    const data = await response.json();

    // ✅ SUCCESS
    document.getElementById("success").textContent =
      "✅ Successfully logged in!";

    console.log("User ID:", data.user_id);

  } catch (err) {
    document.getElementById("error").textContent =
      "❌ Login failed. Please check your details.";
  }
});
