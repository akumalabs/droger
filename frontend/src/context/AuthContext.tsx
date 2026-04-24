import { createContext, useCallback, useContext, useEffect, useState } from "react"
import { api } from "../lib/api"

type AuthUser = {
  user_id: string
  email: string
  name?: string
  picture?: string
  role?: string
  auth_provider?: string
  email_verified?: boolean
}

type AuthContextValue = {
  user: AuthUser | null
  loading: boolean
  login: (email: string, password: string) => Promise<AuthUser>
  register: (email: string, password: string, name?: string) => Promise<AuthUser>
  logout: () => Promise<void>
  refresh: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [loading, setLoading] = useState(true)

  const checkAuth = useCallback(async () => {
    try {
      const { data } = await api.get<AuthUser>("/auth/me")
      setUser(data)
    } catch {
      setUser(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void checkAuth()
  }, [checkAuth])

  const login = async (email: string, password: string) => {
    const { data } = await api.post<AuthUser>("/auth/login", { email, password })
    setUser(data)
    return data
  }

  const register = async (email: string, password: string, name?: string) => {
    const { data } = await api.post<AuthUser>("/auth/register", { email, password, name })
    setUser(data)
    return data
  }

  const logout = async () => {
    try {
      await api.post("/auth/logout")
    } catch {
      
    }
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, refresh: checkAuth }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error("useAuth must be used inside AuthProvider")
  }
  return ctx
}
