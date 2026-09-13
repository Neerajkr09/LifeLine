import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'

const axiosInstance = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Attach the JWT (if present) to every outgoing request.
axiosInstance.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Centralize the "session expired -> log out" behavior in one place.
axiosInstance.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('auth_user')
      if (!window.location.pathname.startsWith('/login')) {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  },
)

/** Extracts a human-readable message from any API error shape. */
export function getApiErrorMessage(error) {
  const data = error?.response?.data
  if (!data) return 'Something went wrong. Please check your connection and try again.'
  if (Array.isArray(data.errors) && data.errors.length > 0) {
    return data.errors.map((e) => e.message).join(' ')
  }
  if (Array.isArray(data.detail) && data.detail.length > 0) {
    return data.detail.map((e) => e.message || e.msg).join(' ')
  }
  if (typeof data.message === 'string') return data.message
  if (typeof data.detail === 'string') return data.detail
  return 'Something went wrong. Please try again.'
}

export default axiosInstance
