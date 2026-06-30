import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { api } from '../services/api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const token = localStorage.getItem('auth_token')
    if (!token) {
      setLoading(false)
      return
    }
    api.get('/auth/me/')
      .then((data) => {
        setUser(data)
      })
      .catch(() => {
        localStorage.removeItem('auth_token')
      })
      .finally(() => {
        setLoading(false)
      })
  }, [])

  const login = useCallback(async (username, password) => {
    const data = await api.post('/auth/login/', { username, password })
    localStorage.setItem('auth_token', data.token)
    setUser(data.user)
    return data
  }, [])

  const logout = useCallback(async () => {
    try {
      await api.post('/auth/logout/')
    } catch {
      // ignore — even if the server call fails, clear local state
    }
    localStorage.removeItem('auth_token')
    setUser(null)
  }, [])

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return ctx
}
