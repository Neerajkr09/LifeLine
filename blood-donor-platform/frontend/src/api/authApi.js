import axiosInstance from './axiosInstance'

export const sendOtp = (email, purpose = 'registration') =>
  axiosInstance.post('/auth/send-otp', { email, purpose }).then((res) => res.data)

export const verifyOtp = (email, otp, purpose = 'registration') =>
  axiosInstance.post('/auth/verify-otp', { email, otp, purpose }).then((res) => res.data)

// Both return { access_token, token_type, user } -- registration auto-logs-in.
export const registerUser = (payload) =>
  axiosInstance.post('/auth/register', payload).then((res) => res.data)

export const loginUser = (email, password) =>
  axiosInstance.post('/auth/login', { email, password }).then((res) => res.data)

export const fetchMyProfile = () => axiosInstance.get('/users/me').then((res) => res.data)
