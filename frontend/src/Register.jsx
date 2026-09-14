import { useState } from "react";
import { register } from "./api";

export default function Register() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function handleRegister(event) {
    event.preventDefault();

    setMessage("");
    setError("");

    try {
      const response = await register(email, password);

      const data = await response.json();

      if (!response.ok) {
        setError(data.detail || "Registration failed");
        return;
      }

      setMessage(
        "Registration successful. Check your email to verify your account."
      );
    } catch (error) {
      setError("Unable to connect to the server.");
    }
  }

  return (
    <div>
      <h1>Create Account</h1>

      <form onSubmit={handleRegister}>
        <input
          type="email"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />

        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />

        <button type="submit">
          Register
        </button>
      </form>

      {message && <p>{message}</p>}
      {error && <p>{error}</p>}
    </div>
  );
}