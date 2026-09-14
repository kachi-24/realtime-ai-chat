import {
  createContext,
  useContext,
  useEffect,
  useState,
} from "react";

import {
  refreshSession,
  logout as logoutApi,
} from "./api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [authenticated, setAuthenticated] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function checkSession() {
      try {
        const success = await refreshSession();

        setAuthenticated(success);
      } catch (error) {
        console.error("Session check failed:", error);
        setAuthenticated(false);
      } finally {
        setLoading(false);
      }
    }

    checkSession();
  }, []);

  async function logout() {
    await logoutApi();
    setAuthenticated(false);
  }

  return (
    <AuthContext.Provider
      value={{
        authenticated,
        loading,
        setAuthenticated,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}