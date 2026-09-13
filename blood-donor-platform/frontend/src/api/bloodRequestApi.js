import axiosInstance from './axiosInstance'

/**
 * Creates a blood request. Must be multipart/form-data because a hospital
 * approval document upload is mandatory alongside the text fields.
 */
export const createBloodRequest = (formFields, documentFile) => {
  const formData = new FormData()
  Object.entries(formFields).forEach(([key, value]) => {
    formData.append(key, value)
  })
  formData.append('document', documentFile)

  return axiosInstance
    .post('/blood-requests', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    .then((res) => res.data)
}

export const fetchMyRequests = () => axiosInstance.get('/blood-requests/mine').then((res) => res.data)

export const fetchMatchingRequests = (page = 1, pageSize = 20) =>
  axiosInstance
    .get('/blood-requests/matching', { params: { page, page_size: pageSize } })
    .then((res) => res.data)

/** Full detail (incl. contact number + document link) for one specific request, shown before a donor decides. */
export const fetchRequestDetail = (requestId) =>
  axiosInstance.get(`/blood-requests/${requestId}/detail`).then((res) => res.data)

export const volunteerForRequest = (requestId) =>
  axiosInstance.post(`/blood-requests/${requestId}/volunteer`).then((res) => res.data)

/** Donor rejects a request outright; reason is mandatory (min 5 chars, enforced server-side too). */
export const rejectRequest = (requestId, reason) =>
  axiosInstance.post(`/blood-requests/${requestId}/reject`, { reason }).then((res) => res.data)

/** Recipient-only: donors currently WILLING on one of their own requests, for accept/deny review. */
export const fetchWillingDonors = (requestId) =>
  axiosInstance.get(`/blood-requests/${requestId}/willing-donors`).then((res) => res.data)

export const acceptDonor = (requestId, donorId) =>
  axiosInstance.post(`/blood-requests/${requestId}/accept-donor`, { donor_id: donorId }).then((res) => res.data)

export const denyDonor = (requestId, donorId) =>
  axiosInstance.post(`/blood-requests/${requestId}/deny-donor`, { donor_id: donorId }).then((res) => res.data)

export const getDocumentDownloadUrl = (requestId) => {
  const base = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'
  return `${base}/blood-requests/${requestId}/document`
}

/**
 * The document endpoint requires the caller's JWT, so a plain <a href> link
 * won't work (no way to attach an Authorization header to a navigation).
 * This fetches it as a blob via the authenticated axios instance instead,
 * then triggers a normal browser file download.
 */
export const downloadHospitalDocument = async (requestId, filename = 'hospital-approval') => {
  const response = await axiosInstance.get(`/blood-requests/${requestId}/document`, {
    responseType: 'blob',
  })
  const url = window.URL.createObjectURL(response.data)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(url)
}

/**
 * Same idea as downloadHospitalDocument, but opens the file in a new tab
 * instead of forcing a download -- used where someone just wants to *review*
 * the document (e.g. a donor deciding whether to volunteer), not save it.
 * PDFs open in the browser's native viewer; images open directly.
 */
export const viewHospitalDocument = async (requestId) => {
  const response = await axiosInstance.get(`/blood-requests/${requestId}/document`, {
    responseType: 'blob',
  })
  const url = window.URL.createObjectURL(response.data)
  window.open(url, '_blank', 'noopener,noreferrer')
  // Revoke well after the new tab has had time to load the blob URL.
  setTimeout(() => window.URL.revokeObjectURL(url), 60_000)
}
