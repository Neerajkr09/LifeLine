import axiosInstance from './axiosInstance'

export const fetchRecipientDashboard = () =>
  axiosInstance.get('/dashboard/recipient').then((res) => res.data)

export const fetchDonorDashboard = () => axiosInstance.get('/dashboard/donor').then((res) => res.data)
