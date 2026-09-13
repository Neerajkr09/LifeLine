import { createContext, useCallback, useEffect, useState } from 'react'
import { fetchMyProfile, loginUser as apiLoginUser, registerUser as apiRegisterUser } from '../api/authApi'

export const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [isLoading, setIsLoading] = useState(true)

  // On first load, if a token is already stored, fetch the profile it
  // belongs to so a page refresh doesn't lose the session.
  useEffect(() => {
    const token = localStorage.getItem('access_token')
    if (!token) {
      setIsLoading(false)
      return
    }
    fetchMyProfile()
      .then((profile) => setUser(profile))
      .catch(() => {
        localStorage.removeItem('access_token')
      })
      .finally(() => setIsLoading(false))
  }, [])

  const login = useCallback(async (email, password) => {
    const data = await apiLoginUser(email, password)
    localStorage.setItem('access_token', data.access_token)
    setUser(data.user)
    return data.user
  }, [])

  // Registration auto-logs-in the user (backend returns a token), matching
  // "After successful registration redirect user to respective dashboard".
  const register = useCallback(async (payload) => {
    const data = await apiRegisterUser(payload)
    localStorage.setItem('access_token', data.access_token)
    setUser(data.user)
    return data.user
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem('access_token')
    setUser(null)
  }, [])

  return (
    <AuthContext.Provider value={{ user, isLoading, login, register, logout, isAuthenticated: !!user }}>
      {children}
    </AuthContext.Provider>
  )
}
