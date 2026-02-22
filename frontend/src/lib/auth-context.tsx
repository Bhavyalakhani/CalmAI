// auth context - provides current user, login/logout, token management
// wraps the entire app to give all pages access to auth state

"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  type ReactNode,
} from "react";
import { useRouter, usePathname } from "next/navigation";
import type { Therapist, Patient, UserRole } from "@/types";
import {
  login as apiLogin,
  signup as apiSignup,
  getMe,
  logout as apiLogout,
  getAccessToken,
  clearTokens,
  type SignupPayload,
} from "@/lib/api";

// auth context types

interface AuthContextType {
  user: Therapist | Patient | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (payload: SignupPayload) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  isLoading: true,
  isAuthenticated: false,
  login: async () => {},
  signup: async () => {},
  logout: () => {},
});

// public routes that don't require auth
const PUBLIC_ROUTES = ["/", "/login", "/signup"];

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Therapist | Patient | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();
  const pathname = usePathname();

  // check auth state on mount
  useEffect(() => {
    const checkAuth = async () => {
      const token = getAccessToken();
      if (!token) {
        setIsLoading(false);
        return;
      }

      try {
        const me = await getMe();
        setUser(me);
      } catch {
        clearTokens();
      } finally {
        setIsLoading(false);
      }
    };

    checkAuth();
  }, []);

  // redirect unauthenticated users away from protected routes
  useEffect(() => {
    if (isLoading) return;

    const isPublic = PUBLIC_ROUTES.includes(pathname);
    if (!user && !isPublic) {
      router.push("/login");
    }
  }, [user, isLoading, pathname, router]);

  const login = useCallback(
    async (email: string, password: string) => {
      await apiLogin(email, password);
      const me = await getMe();
      setUser(me);

      // redirect based on role
      if (me.role === "therapist") {
        router.push("/dashboard");
      } else {
        router.push("/journal");
      }
    },
    [router]
  );

  const signup = useCallback(
    async (payload: SignupPayload) => {
      await apiSignup(payload);
      const me = await getMe();
      setUser(me);

      if (me.role === "therapist") {
        router.push("/dashboard");
      } else {
        router.push("/journal");
      }
    },
    [router]
  );

  const logout = useCallback(() => {
    setUser(null);
    apiLogout();
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        isAuthenticated: !!user,
        login,
        signup,
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
