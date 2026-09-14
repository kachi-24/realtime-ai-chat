import { useState } from "react";
import { login } from "./api";
import { useAuth } from "./AuthContext";

export default function Login() {
  const { setAuthenticated } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const [error, setError] = useState("");

  async function handleLogin(event) {
    event.preventDefault();

    setError("");

    try {
      const result = await login(email, password);

      if (!result || result.detail) {
        setError(
          result?.detail || "Invalid email or password."
        );
        return;
      }

      setAuthenticated(true);

      window.location.href = "/";
    } catch (error) {
      setError("Unable to connect to the server.");
    }
  }

  return (
    <div>
      <h1>Login</h1>

      <form onSubmit={handleLogin}>
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
          Login
        </button>
      </form>

      {error && <p>{error}</p>}
    </div>
  );
}