import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { api, ApiError, session } from "../services/api";
import type { LoginRequest, User } from "../types/api";

interface AuthState {
  user: User | null;
  loading: boolean;
  error: string;
  signIn: (credentials: LoginRequest) => Promise<void>;
  signOut: () => void;
  restore: () => Promise<void>;
}
const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const signOut = useCallback(() => {
    session.clear();
    setUser(null);
    setError("");
  }, []);
  const restore = useCallback(async () => {
    setLoading(true);
    setError("");
    const token = session.get();
    if (token) {
      try {
        const profile = await api.me();
        if (session.get() === token) setUser(profile);
      } catch (failure) {
        if (session.get() === token)
          setError(
            failure instanceof Error
              ? failure.message
              : "Unable to load your account.",
          );
      }
    }
    setLoading(false);
  }, []);
  useEffect(() => {
    const unsubscribe = session.onUnauthorized(() => {
      setUser(null);
      setError("");
    });
    void restore();
    return unsubscribe;
  }, [restore]);
  const signIn = async (credentials: LoginRequest) => {
    try {
      const response = await api.login(credentials);
      session.set(response.access_token);
      const profile = await api.me();
      setUser(profile);
    } catch (failure) {
      session.clear();
      if (failure instanceof ApiError && failure.status === 401) {
        throw new ApiError(
          401,
          "Email or password is incorrect. Please try again.",
        );
      }
      throw failure;
    }
  };
  return (
    <AuthContext.Provider
      value={{ user, loading, error, signIn, signOut, restore }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const auth = useContext(AuthContext);
  if (!auth) throw new Error("useAuth must be used within AuthProvider");
  return auth;
}
