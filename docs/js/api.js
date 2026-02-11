// docs/js/api.js

// Base URL for all API requests
export const API_URL = "https://foodbodyconnection.54.253.73.35.nip.io";

// Generic helper function for making authenticated API requests
export async function apiFetch(endpoint, options = {}) {
  // Retrieve stored JWT access token from localStorage
  const token = localStorage.getItem("access_token");

  // Build request headers
  // If token exists, include Authorization header
  const headers = {
    ...(token && { Authorization: `Bearer ${token}` }),
    ...options.headers,
  };

  // Make the HTTP request using fetch
  const response = await fetch(`${API_URL}${endpoint}`, {
    ...options,
    headers,
  });

  // If the response is not successful, throw an error with the response text
  if (!response.ok) {
    throw new Error(await response.text());
  }

  // Return parsed JSON response
  return response.json();
}

// Login function - authenticates user and retrieves access token
export async function login(email, password) {
  // Create form data in x-www-form-urlencoded format (OAuth2 standard)
  const formData = new URLSearchParams();
  formData.append("username", email);
  formData.append("password", password);

  // Send POST request to login endpoint
  const response = await fetch(`${API_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: formData,
  });

  // If login fails, throw a generic invalid credentials error
  if (!response.ok) {
    throw new Error("Invalid credentials");
  }

  // Return parsed JSON (typically contains access token)
  return response.json();
}

// Register function - creates a new user account
export async function register(email, password) {

  // Send POST request to register endpoint with JSON body
  const response = await fetch(`${API_URL}/auth/register`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      email: email,
      password: password,
    }),
  });

  // Handle unsuccessful registration
  if (!response.ok) {
    const err = await response.json();
    console.error("REGISTER ERROR:", err);
    //throw new Error(err.detail || "Registration failed");
    // Throw full error object as string for debugging/handling upstream
    throw new Error(JSON.stringify(err));

  }

  // Return parsed JSON response (newly created user or confirmation message)
  return await response.json();
}

// Fetch currently authenticated user's details
export async function getCurrentUser() {
  return apiFetch("/auth/me");
}
