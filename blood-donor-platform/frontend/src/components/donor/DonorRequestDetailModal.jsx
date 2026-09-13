import { useEffect, useState } from 'react'
import { CheckCircle2, FileText, Loader2, Mail, MapPin, Phone, User, XCircle } from 'lucide-react'
import Modal from '../common/Modal.jsx'
import Button from '../common/Button.jsx'
import Alert from '../common/Alert.jsx'
import {
  fetchRequestDetail,
  rejectRequest,
  viewHospitalDocument,
  volunteerForRequest,
} from '../../api/bloodRequestApi'
import { getApiErrorMessage } from '../../api/axiosInstance'

export default function DonorRequestDetailModal({ requestId, isOpen, onClose, onResolved }) {
  const [detail, setDetail] = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [isActing, setIsActing] = useState(false)
  const [isViewingDoc, setIsViewingDoc] = useState(false)
  const [showRejectForm, setShowRejectForm] = useState(false)
  const [rejectReason, setRejectReason] = useState('')
  const [rejectError, setRejectError] = useState('')
  const [acceptedMessage, setAcceptedMessage] = useState('')

  useEffect(() => {
    if (!isOpen || !requestId) return
    setIsLoading(true)
    setError('')
    setShowRejectForm(false)
    setRejectReason('')
    setAcceptedMessage('')
    fetchRequestDetail(requestId)
      .then(setDetail)
      .catch((err) => setError(getApiErrorMessage(err)))
      .finally(() => setIsLoading(false))
  }, [isOpen, requestId])

  const handleViewDocument = async () => {
    setIsViewingDoc(true)
    setError('')
    try {
      await viewHospitalDocument(requestId)
    } catch (err) {
      setError(getApiErrorMessage(err))
    } finally {
      setIsViewingDoc(false)
    }
  }

  const handleAccept = async () => {
    setIsActing(true)
    setError('')
    try {
      const res = await volunteerForRequest(requestId)
      setAcceptedMessage(res.message)
      onResolved?.('willing', requestId)
    } catch (err) {
      // Covers the race condition: someone else may have just been accepted,
      // or the request otherwise stopped being active/eligible in the meantime.
      setError(getApiErrorMessage(err))
    } finally {
      setIsActing(false)
    }
  }

  const handleReject = async () => {
    setRejectError('')
    if (rejectReason.trim().length < 5) {
      setRejectError('Please provide a reason of at least 5 characters.')
      return
    }
    setIsActing(true)
    try {
      await rejectRequest(requestId, rejectReason.trim())
      onResolved?.('rejected', requestId)
      onClose()
    } catch (err) {
      setRejectError(getApiErrorMessage(err))
    } finally {
      setIsActing(false)
    }
  }

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Request details">
      {isLoading ? (
        <div className="flex justify-center py-8">
          <Loader2 className="w-6 h-6 animate-spin text-teal-500" />
        </div>
      ) : error && !detail ? (
        <Alert variant="error">{error}</Alert>
      ) : detail ? (
        <div className="space-y-5">
          {error && <Alert variant="error">{error}</Alert>}

          {acceptedMessage && (
            <Alert variant="success" title="Thank you for showing up for this good cause!">
              {acceptedMessage}
            </Alert>
          )}

          <div>
            <div className="flex items-center gap-2 mb-3">
              <span className="font-mono font-bold text-xl text-crimson-600">{detail.blood_group}</span>
              <span className="text-xs text-ink-400 border border-ink-200 rounded-full px-2 py-0.5 capitalize">
                {detail.status}
              </span>
              {detail.distance_km != null && (
                <span className="flex items-center gap-1 text-xs text-ink-500">
                  <MapPin className="w-3.5 h-3.5" /> {detail.distance_km} km away
                </span>
              )}
            </div>

            <dl className="space-y-2.5 text-sm">
              <div className="flex items-center gap-2.5">
                <User className="w-4 h-4 text-ink-400 shrink-0" />
                <span className="text-ink-800">
                  {detail.first_name} {detail.last_name}, age {detail.age}
                </span>
              </div>
              <div className="flex items-center gap-2.5">
                <Mail className="w-4 h-4 text-ink-400 shrink-0" />
                <span className="text-ink-800">{detail.email}</span>
              </div>
              {/* Contact number is only present once the backend decides to reveal it
                  (currently: as soon as a donor opens this detail view). */}
              {detail.contact && (
                <div className="flex items-center gap-2.5">
                  {/* <Phone className="w-4 h-4 text-ink-400 shrink-0" /> */}
                  {/* <span className="text-ink-800">{detail.contact}</span> */}
                </div>
              )}
              <div className="text-ink-500 pl-6.5 ml-0.5">
                {detail.address.address_line}, {detail.address.city_town} {detail.address.postcode}
              </div>
            </dl>
          </div>

          <Button
            variant="outline"
            size="sm"
            fullWidth
            onClick={handleViewDocument}
            isLoading={isViewingDoc}
          >
            <FileText className="w-4 h-4" /> View hospital approval document
          </Button>

          {detail.my_response_status ? (
            <Alert variant="info">
              You already responded to this request ({detail.my_response_status.replace('_', ' ')}).
            </Alert>
          ) : acceptedMessage ? null : !showRejectForm ? (
            <div className="grid grid-cols-2 gap-3">
              <Button variant="primary" onClick={handleAccept} isLoading={isActing}>
                <CheckCircle2 className="w-4 h-4" /> I'm willing to donate
              </Button>
              <Button variant="outline" onClick={() => setShowRejectForm(true)} disabled={isActing}>
                <XCircle className="w-4 h-4" /> Reject
              </Button>
            </div>
          ) : (
            <div className="space-y-2.5 border-t border-ink-100 pt-4">
              <label htmlFor="reject-reason" className="block text-sm font-medium text-ink-800">
                Reason for rejecting <span className="text-crimson-500">*</span>
              </label>
              <textarea
                id="reject-reason"
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                rows={3}
                placeholder="E.g. Not available at the moment, too far to travel, medical reason..."
                className="w-full px-3.5 py-2.5 rounded-xl border border-ink-200 focus:border-teal-500 text-sm"
              />
              {rejectError && <p className="text-xs text-crimson-600">{rejectError}</p>}
              <div className="grid grid-cols-2 gap-3">
                <Button variant="danger" onClick={handleReject} isLoading={isActing}>
                  Submit rejection
                </Button>
                <Button variant="ghost" onClick={() => setShowRejectForm(false)} disabled={isActing}>
                  Cancel
                </Button>
              </div>
            </div>
          )}
        </div>
      ) : null}
    </Modal>
  )
}
